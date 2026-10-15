# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import smtplib
from contextlib import suppress

# import frappe
from email.parser import Parser
from email.policy import SMTP
import quopri
from .utils import cint, cstr, get_traceback, get_url, parse_json, safe_encode, _dict


class InvalidEmailCredentials(Exception):
    pass

class OutgoingEmailError(Exception):
    pass


class SMTPClient:
    def __init__(
        self,
        server,
        login=None,
        email_account=None,
        password=None,
        port=None,
        use_tls=None,
        use_ssl=None,
        use_oauth=0,
        access_token=None,
        timeout=2 * 60,
        smtp_no_ehlo_after_auth=False,
        dsn_notify_type=None,
        track_email_status=False
    ):
        self.login = login
        self.email_account = email_account
        self.password = password
        self._server = server
        self._port = port
        self.use_tls = use_tls
        self.use_ssl = use_ssl
        self.use_oauth = use_oauth
        self.access_token = access_token
        self._session = None
        self.timeout = timeout
        self.smtp_no_ehlo_after_auth = smtp_no_ehlo_after_auth
        self.dsn_notify_type = dsn_notify_type
        self.track_email_status = track_email_status

        if not self.server:
            raise OutgoingEmailError("Email Account not setup")

    @property
    def port(self):
        port = self._port or (self.use_ssl and 465) or (self.use_tls and 587)
        return cint(port)

    @property
    def server(self):
        return cstr(self._server or "")

    def secure_session(self, conn):
        """Secure the connection incase of TLS."""
        if self.use_tls:
            conn.ehlo()
            conn.starttls()
            conn.ehlo()

    @property
    def session(self):
        """Get SMTP session.

        We make best effort to revive connection if it's disconnected by checking the connection
        health before returning it to user."""
        if self.is_session_active():
            return self._session

        SMTP = smtplib.SMTP_SSL if self.use_ssl else smtplib.SMTP

        try:
            _session = SMTP(self.server, self.port, timeout=self.timeout)
            if not _session:
                raise OutgoingEmailError("Could not connect to outgoing email server")

            self.secure_session(_session)

            # if self.use_oauth:
            #     Oauth(_session, self.email_account, self.login, self.access_token).connect()

            if self.password:
                res = _session.login(str(self.login or ""), str(self.password or ""))

                # check if logged correctly
                if res[0] != 235:
                    raise OutgoingEmailError(res[1])

            # Re-issue EHLO after AUTH to refresh server capabilities
            if not self.smtp_no_ehlo_after_auth:
                _session.ehlo()

            self._session = _session
            self._enqueue_connection_closure()
            return self._session

        except smtplib.SMTPAuthenticationError:
            self.throw_invalid_credentials_exception(email_account=self.email_account)

        except OSError as e:
            # Invalid mail server -- due to refusing connection
            raise InvalidEmailCredentials(f"Invalid Outgoing Mail Server or Port: {str(e)}")

    def _enqueue_connection_closure(self):
        import atexit
        # if frappe.request and hasattr(frappe.request, "after_response"):
        #     frappe.request.after_response.add(self.quit)
        # elif frappe.job:
        #     frappe.job.after_job.add(self.quit)
        # elif not frappe.in_test:
        #     # Console?
        #     atexit.register(self.quit)
        atexit.register(self.quit)

    def is_session_active(self):
        if self._session:
            try:
                return self._session.noop()[0] == 250
            except Exception:
                return False

    def discard_session(self):
        """Drop the cached session so the next `session` access reconnects.

        A failed sendmail() can poison the connection server-side even though NOOP still reports it alive.
        """
        if self._session:
            with suppress(Exception):
                self._session.close()
            self._session = None

    def quit(self):
        with suppress(TimeoutError):
            if self.is_session_active():
                self._session.quit()

    @classmethod
    def throw_invalid_credentials_exception(cls, email_account=None):
        original_exception = get_traceback() or "\n"
        error_message = (
            "Please check your email login credentials." + " " + original_exception.splitlines()[-1]
        )
        # error_title = "Invalid Credentials"
        # if email_account:
        #     error_title = f"Invalid Credentials for Email Account: {email_account}"

        raise InvalidEmailCredentials(error_message)

    # SMTP Client

    def validate_and_prepare_message(self, raw_message: bytes) -> bytes:
        """Validate SIZE extension and return encoded message."""

        msg = raw_message if isinstance(raw_message, bytes) else raw_message.encode("utf-8")

        if self.session.has_extn("SIZE"):
            if max_size := self.session.esmtp_features.get("size"):
                max_size = int(max_size)

                if max_size > 0:
                    msg_size = len(msg)

                    if msg_size > max_size:
                        msg_size_mb = msg_size / (1024 * 1024)
                        max_size_mb = max_size / (1024 * 1024)
                        raise Exception("Email size {0:.2f} MB exceeds the maximum allowed size of {1:.2f} MB".format(msg_size_mb, max_size_mb))

        return msg

    def get_smtp_options(self, message_id) -> tuple[list[str], list[str]]:
        mail_options: list[str] = []
        rcpt_options: list[str] = []

        if not self.session.has_extn("DSN"):
            return mail_options, rcpt_options

        if dsn_notify_type := self.dsn_notify_type:
            mail_options.extend(["RET=FULL", f"ENVID={message_id}"])
            rcpt_options.append(f"NOTIFY={dsn_notify_type}")

        return mail_options, rcpt_options

    def message_placeholder(self, placeholder_key):
        # sourcery skip: avoid-builtin-shadow
        placeholder_map = {
            "tracker": "<!--email_open_check-->",
            "unsubscribe_url": "<!--unsubscribe_url-->",
            "cc": "<!--cc_message-->",
            "recipient": "<!--recipient-->",
        }
        return placeholder_map.get(placeholder_key)

    def get_tracker_str(self, message_id, email_read_tracker_url) -> str:
        tracker_url = ""
        if email_read_tracker_url:
            tracker_url = get_url(f"{email_read_tracker_url}?msg_id={message_id}")

        elif (self.track_email_status and message_id):
            tracker_url = f"{get_url()}/v1/emails/mark_email_as_seen?msg_id={message_id}"

        if tracker_url:
            tracker_url_html = f'<img src="{tracker_url}"/>'
            return quopri.encodestring(tracker_url_html.encode()).decode()

        return ""

    def get_unsubscribe_str(self, recipient_email: str, add_unsubscribe_link: bool) -> str:
        unsubscribe_url = ""

        if add_unsubscribe_link:
            unsubscribe_url = get_unsubcribed_url(
                email=recipient_email,
                unsubscribe_method="/v1/emails/unsubscribe",
                unsubscribe_params=None,
            )

        return quopri.encodestring(unsubscribe_url.encode()).decode()

    def get_receivers_str(self, expose_recipients, recipients):
        message = ""
        if expose_recipients == "footer":
            to_recipients = [recipient.email for recipient in recipients if not recipient.show_as_cc]
            cc_recipients = [recipient.email for recipient in recipients if recipient.show_as_cc]
            to_str = ", ".join(to_recipients)
            cc_str = ", ".join(cc_recipients)
            message = f"This email was sent to {to_str}"
            message = f"{message} and copied to {cc_str}" if cc_str else message
        return message

    def get_recipient_str(self, recipient_email, expose_recipients):
        return recipient_email if expose_recipients != "header" else ""

    def get_message_object(self, message):
        policy = SMTP.clone(refold_source="none")
        return Parser(policy=policy).parsestr(message)

    def include_attachments(self, message):
        message_obj = self.get_message_object(message)
        # attachments = self.queue_doc.attachments_list

        # for attachment in attachments:
        #     if attachment.get("fcontent"):
        #         continue

        #     file_filters = {}
        #     if attachment.get("fid"):
        #         file_filters["name"] = attachment.get("fid")
        #     elif attachment.get("file_url"):
        #         file_filters["file_url"] = attachment.get("file_url")

        #     if file_filters:
        #         _file = frappe.get_doc("File", file_filters)
        #         fcontent = _file.get_content()
        #         attachment.update({"fname": _file.file_name, "fcontent": fcontent, "parent": message_obj})
        #         attachment.pop("fid", None)
        #         attachment.pop("file_url", None)
        #         add_attachment(**attachment)

        #     elif attachment.get("print_format_attachment") == 1:
        #         attachment.pop("print_format_attachment", None)
        #         print_format_file = frappe.attach_print(**attachment)
        #         self._store_file(print_format_file["fname"], print_format_file["fcontent"])
        #         print_format_file.update({"parent": message_obj})
        #         add_attachment(**print_format_file)

        return safe_encode(message_obj.as_string())

    def build_message(
            self,
            recipient_email,
            message,
            message_id,
            email_read_tracker_url,
            add_unsubscribe_link,
            expose_recipients,
            recipients
        ) -> bytes:
        """Build message specific to the recipient."""
        # message = self.queue_doc.message

        if not message:
            return ""

        message = message.replace(self.message_placeholder("tracker"), self.get_tracker_str(message_id, email_read_tracker_url))
        message = message.replace(
            self.message_placeholder("unsubscribe_url"), self.get_unsubscribe_str(recipient_email, add_unsubscribe_link)
        )
        message = message.replace(self.message_placeholder("cc"), self.get_receivers_str(expose_recipients, recipients))
        message = message.replace(
            self.message_placeholder("recipient"), self.get_recipient_str(recipient_email, expose_recipients)
        )
        message = self.include_attachments(message)
        return message

    def parse_recipients(self, recipients):
        _recipients = []
        for r in recipients:
            if isinstance(r, str):
                _recipients.append(_dict({"email": r.strip(), "status": "Not Sent"}))
            else:
                _recipients.append(_dict(r))
        return _recipients

    def send(
        self,
        recipients,
        message,
        message_id: str | None = None,
        email_read_tracker_url: str | None = None,
        add_unsubscribe_link: bool | None = False,
        sender: str | None = "noreply@trakla.africa",
        expose_recipients: str | None = None,
        **kwargs
    ):
        """Send emails to recipients."""

        # with SendMailContext(self, smtp_server_instance, frappe_mail_client) as ctx:

            # last_message = None

        recipients = self.parse_recipients(recipients)

        for recipient in recipients:
            # if recipient.is_mail_sent():
            # 	continue

            # message = ctx.build_message(recipient.recipient)
            message = self.build_message(
                recipient.email, 
                message, 
                message_id, 
                email_read_tracker_url, 
                add_unsubscribe_link, 
                expose_recipients,
                recipients
            )
            # last_message = message

            # if method := get_hook_method("override_email_send"):
            #     method(self, self.sender, recipient.recipient, message)

            # elif not frappe.in_test or frappe.flags.testing_email:
            # if ctx.email_account_doc.service == "Frappe Mail":
            #     ctx.frappe_mail_client.send_raw(
            #         sender=self.sender,
            #         recipients=recipient.recipient,
            #         message=message,
            #         is_newsletter=self.reference_doctype == "Newsletter",
            #     )
            # else:
            msg_bytes = self.validate_and_prepare_message(message)
            mail_options, rcpt_options = self.get_smtp_options(message_id)

            try:
                self.session.sendmail(
                    from_addr=sender,
                    # to_addrs=recipient.recipient,
                    to_addrs=recipient.email,
                    msg=msg_bytes,
                    mail_options=mail_options,
                    rcpt_options=rcpt_options,
                )
            except smtplib.SMTPException:
                # Session can be poisoned server-side even though NOOP
                # still reports it alive; discard so the next recipient reconnects.
                self.discard_session()
                raise

            # ctx.update_recipient_status_to_sent(recipient)


            # if last_message and ctx.email_account_doc.append_emails_to_sent_folder:
            #     ctx.email_account_doc.append_email_to_sent_folder(last_message)

def get_unsubcribed_url(email, unsubscribe_method, unsubscribe_params):
    params = {
        "email": cstr(email)
    }
    if unsubscribe_params:
        params.update(parse_json(unsubscribe_params))

    # return get_url(unsubscribe_method + "?" + get_signed_params(params))
    return get_url(unsubscribe_method)