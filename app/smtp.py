# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import smtplib
from contextlib import suppress

# import frappe
# from frappe import _
# from frappe.email.oauth import Oauth
from .utils import cint, cstr, get_traceback


class InvalidEmailCredentials(Exception):
    pass

class OutgoingEmailError(Exception):
    pass


class SMTPServer:
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
        smtp_no_ehlo_after_auth=False
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
        error_title = "Invalid Credentials"
        if email_account:
            error_title = f"Invalid Credentials for Email Account: {email_account}"

        raise InvalidEmailCredentials(error_message)
