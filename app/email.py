
from typing import TYPE_CHECKING
import json
from contextlib import suppress
import os
import re
from email import policy
from email.header import Header
from email.mime.multipart import MIMEMultipart
import email.utils
from email.utils import formataddr
from pathlib import Path as FilePath
from .utils import split_emails, add_days, nowdate, html_to_plain_text, cint, scrub_urls, strip,\
    _dict, markdown, cstr, InvalidEmailAddressError, get_string_between, get_app_url, expand_relative_urls,\
    validate_email_address, to_markdown, parse_addr, unescape_html, random_string, md_to_html
from .pdf import get_pdf
from .smtp import SMTPClient
from .config import get_settings

if TYPE_CHECKING:
    from typing import Literal


# https://fastapi.tiangolo.com/advanced/templates/

EMBED_PATTERN = re.compile("""embed=["'](.*?)["']""")
BASE_DIR = FilePath(__file__).resolve().parent.parent

def get_email(
    recipients,
    sender="",
    msg="",
    subject="[No Subject]",
    text_content=None,
    footer=None,
    print_html=None,
    formatted=None,
    attachments=None,
    content=None,
    reply_to=None,
    cc=None,
    bcc=None,
    email_account=None,
    expose_recipients=None,
    inline_images=None,
    header=None,
    x_priority: Literal[1, 3, 5] = 3,
):
    """Prepare an email with the following format:
    - multipart/mixed
            - multipart/alternative
                    - text/plain
                    - multipart/related
                            - text/html
                            - inline image
                    - attachment
    """
    content = content or msg

    if cc is None:
        cc = []
    if bcc is None:
        bcc = []
    if inline_images is None:
        inline_images = []

    emailobj = EMail(
        sender,
        recipients,
        subject,
        reply_to=reply_to,
        cc=cc,
        bcc=bcc,
        email_account=email_account,
        expose_recipients=expose_recipients,
        x_priority=x_priority,
    )

    if not content.strip().startswith("<"):
        content = markdown(content)

    emailobj.set_html(
        content,
        text_content,
        footer=footer,
        header=header,
        print_html=print_html,
        formatted=formatted,
        inline_images=inline_images,
    )

    if isinstance(attachments, dict):
        attachments = [attachments]

    for attach in attachments or []:
        # cannot attach if no filecontent
        if attach.get("fcontent") is None:
            continue
        emailobj.add_attachment(**attach)

    return emailobj


class EMail:
    """
    Wrapper on the email module. Email object represents emails to be sent to the client.
    Also provides a clean way to add binary `FileData` attachments
    Also sets all messages as multipart/alternative for cleaner reading in text-only clients
    """

    def __init__(
        self,
        sender="",
        recipients=(),
        subject="",
        alternative=0,
        reply_to=None,
        cc=(),
        bcc=(),
        email_account=None,
        expose_recipients=None,
        x_priority: Literal[1, 3, 5] = 3,
    ):
        from email import charset as Charset

        Charset.add_charset("utf-8", Charset.QP, Charset.QP, "utf-8")

        if isinstance(recipients, str):
            recipients = recipients.replace(";", ",").replace("\n", "")
            recipients = split_emails(recipients)

        # remove null
        recipients = [r for r in (strip(r) for r in recipients) if r]

        self.sender = sender
        self.reply_to = reply_to or sender
        self.recipients = recipients
        self.subject = subject
        self.expose_recipients = expose_recipients

        self.msg_root = MIMEMultipart("mixed", policy=policy.SMTP)
        self.msg_alternative = MIMEMultipart("alternative", policy=policy.SMTP)
        self.msg_root.attach(self.msg_alternative)
        self.cc = cc or []
        self.bcc = bcc or []
        self.html_set = False

        self.x_priority: Literal[1, 3, 5] = x_priority

        # self.email_account = email_account or EmailAccount.find_outgoing(
        #     match_by_email=sender, _raise_error=True
        # )
        self.email_account = email_account or get_email_settings()

    def set_html(
        self,
        message,
        text_content=None,
        footer=None,
        print_html=None,
        formatted=None,
        inline_images=None,
        header=None,
    ):
        """Attach message in the html portion of multipart/alternative"""
        if not formatted:
            formatted = get_formatted_html(
                self.subject,
                message,
                footer,
                print_html,
                email_account=self.email_account,
                header=header,
                sender=self.sender,
            )

        # this is the first html part of a multi-part message,
        # convert to text well
        if not self.html_set:
            if text_content:
                self.set_text(expand_relative_urls(text_content))
            else:
                self.set_html_as_text(expand_relative_urls(formatted))

        self.set_part_html(formatted, inline_images)
        self.html_set = True

    def set_text(self, message):
        """
        Attach message in the text portion of multipart/alternative
        """
        from email.mime.text import MIMEText

        part = MIMEText(message, "plain", "utf-8", policy=policy.SMTP)
        self.msg_alternative.attach(part)

    def set_part_html(self, message, inline_images):
        from email.mime.text import MIMEText

        has_inline_images = EMBED_PATTERN.search(message)

        if has_inline_images:
            # process inline images
            provided_images = {}
            if inline_images:
                for img in inline_images:
                    if img.get("filename") and img.get("filecontent"):
                        # index by full path and basename for flexible matching
                        provided_images[img["filename"]] = img["filecontent"]
                        basename = img["filename"].rsplit("/", 1)[-1]
                        if basename not in provided_images:
                            provided_images[basename] = img["filecontent"]

            # process inline images while preferring provided_images over disk reads
            message, _inline_images = replace_filename_with_cid(message, provided_images)

            # prepare parts
            msg_related = MIMEMultipart("related", policy=policy.SMTP)

            html_part = MIMEText(message, "html", "utf-8", policy=policy.SMTP)
            msg_related.attach(html_part)

            for image in _inline_images:
                self.add_attachment(
                    image.get("filename"),
                    image.get("filecontent"),
                    content_id=image.get("content_id"),
                    parent=msg_related,
                    inline=True,
                )

            self.msg_alternative.attach(msg_related)
        else:
            self.msg_alternative.attach(MIMEText(message, "html", "utf-8", policy=policy.SMTP))

    def set_html_as_text(self, html):
        """Set plain text from HTML"""
        self.set_text(to_markdown(html))

    def set_message(self, message, mime_type="text/html", as_attachment=0, filename="attachment.html"):
        """Append the message with MIME content to the root node (as attachment)"""
        from email.mime.text import MIMEText

        _maintype, subtype = mime_type.split("/")
        part = MIMEText(message, _subtype=subtype, policy=policy.SMTP)

        if as_attachment:
            clean_filename = re.sub("[\r\n]", "", str(filename))
            part.add_header("Content-Disposition", "attachment", filename=clean_filename)

        self.msg_root.attach(part)

    def attach_file(self, file):
        """attach a file from the `FileData` table"""
        # _file = frappe.get_doc("File", {"file_name": n})
        # content = _file.get_content()
        content = file.get_content()
        if not content:
            return

        # self.add_attachment(_file.file_name, content)
        self.add_attachment(file.file_name, content)

    def add_attachment(self, fname, fcontent, content_type=None, parent=None, content_id=None, inline=False):
        """add attachment"""

        if not parent:
            parent = self.msg_root

        add_attachment(fname, fcontent, content_type, parent, content_id, inline)

    def add_pdf_attachment(self, name, html, options=None):
        self.add_attachment(name, get_pdf(html, options), "application/octet-stream")

    def validate(self):
        """validate the Email Addresses"""

        if not self.sender:
            self.sender = self.email_account.default_sender

        validate_email_address(strip(self.sender), True)
        self.validate_reply_to()

        if self.email_account.add_x_original_from:
            self.set_header("X-Original-From", self.sender)

        self.replace_sender()
        self.replace_sender_name()

        self.recipients = [strip(r) for r in self.recipients]
        self.cc = [strip(r) for r in self.cc]
        self.bcc = [strip(r) for r in self.bcc]

        for e in self.recipients + (self.cc or []) + (self.bcc or []):
            validate_email_address(e, True)

    def validate_reply_to(self) -> None:
        if not self.email_account.add_reply_to_header:
            self.reply_to = None
            return

        if self.email_account.reply_to_addresses:
            valid_addresses = [
                formataddr((reply_to._name, reply_to.email))
                for reply_to in self.email_account.reply_to_addresses
                if reply_to.email and validate_email_address(reply_to.email, True)
            ]
            self.reply_to = ", ".join(valid_addresses) if valid_addresses else None
            return

        fallback = strip(self.reply_to) or self.sender
        self.reply_to = validate_email_address(fallback, True)

    def replace_sender(self):
        if cint(self.email_account.always_use_account_email_id_as_sender):
            sender_name, _ = parse_addr(self.sender)
            self.sender = email.utils.formataddr(
                (str(Header(sender_name or self.email_account.name, "utf-8")), self.email_account.email_id)
            )

    def replace_sender_name(self):
        if cint(self.email_account.always_use_account_name_as_sender_name):
            _, sender_email = parse_addr(self.sender)
            self.sender = email.utils.formataddr(
                (str(Header(self.email_account.name, "utf-8")), sender_email)
            )

    def set_message_id(self, message_id, is_notification=False):
        if message_id:
            message_id = "<" + message_id + ">"
        else:
            message_id = get_message_id()
            self.set_header("isnotification", "<notification>")

        if is_notification:
            self.set_header("isnotification", "<notification>")

        self.set_header("Message-Id", message_id)

    def set_in_reply_to(self, in_reply_to):
        """Used to send the Message-Id of a received email back as In-Reply-To"""
        self.set_header("In-Reply-To", in_reply_to)

    def add_headers(self, headers):
        """Add custom headers to the email"""
        if not isinstance(headers, dict):
            raise Exception("Headers must be a dictionary")
            # frappe.throw(_("Headers must be a dictionary"))

        for key, value in headers.items():
            if value is not None:
                key = "X-" + key if not key.startswith("X-") else key
                self.set_header(key, value)

    def make(self):
        """build into msg_root"""
        headers = {
            "Subject": strip(self.subject),
            "From": self.sender,
            "To": ", ".join(self.recipients) if self.expose_recipients == "header" else "<!--recipient-->",
            "Date": email.utils.formatdate(),
            "Reply-To": self.reply_to if self.reply_to else None,
            # cc should always be visible - as that is the semantic meaning of cc, this should not be dependent on expose_recipients
            "CC": ", ".join(self.cc) if self.cc else None,
            # "X-Frappe-Site": get_url(),
        }

        if self.x_priority != 3:
            headers.update(
                {
                    "X-Priority": str(self.x_priority),
                }
            )

        # reset headers as values may be changed.
        for key, val in headers.items():
            if val:
                self.set_header(key, val)

        # call hook to enable apps to modify msg_root before sending
        # for hook in frappe.get_hooks("make_email_body_message"):
        #     frappe.get_attr(hook)(self)

    def set_header(self, key, value):
        if key in self.msg_root:
            # delete key if found
            # this is done because adding the same key doesn't override
            # the existing key, rather appends another header with same key.
            del self.msg_root[key]

        self.msg_root[key] = sanitize_email_header(value)

    def as_string(self):
        """validate, build message and convert to string"""
        self.validate()
        self.make()
        return self.msg_root.as_string(policy=policy.SMTP)


def replace_filename_with_cid(message, provided_images=None):
    """Replaces <img embed="assets/frappe/images/filename.jpg" ...> with
    <img src="cid:content_id" ...> and return the modified message and
    a list of inline_images with {filename, filecontent, content_id}

    Args:
        message: The HTML message to process
        provided_images: A dictionary of images to use instead of reading from disk
            Example:
            {
                "assets/frappe/images/filename.jpg": filecontent,
                "filename.jpg": filecontent,
            }
    """
    if provided_images is None:
        provided_images = {}

    inline_images = []

    while True:
        matches = EMBED_PATTERN.search(message)
        if not matches:
            break
        groups = matches.groups()

        # found match
        img_path = groups[0]
        img_path_escaped = unescape_html(img_path)
        filename = img_path_escaped.rsplit("/")[-1]

        # check if the image is provided in the provided_images(by checking full path and basename)
        filecontent = provided_images.get(img_path_escaped) or provided_images.get(filename)
        if not filecontent:
            filecontent = get_filecontent_from_path(img_path_escaped)

        if not filecontent:
            message = re.sub(f"""embed=['"]{re.escape(img_path)}['"]""", "", message)
            continue

        content_id = random_string(10)

        inline_images.append({"filename": filename, "filecontent": filecontent, "content_id": content_id})

        message = re.sub(f"""embed=['"]{re.escape(img_path)}['"]""", f'src="cid:{content_id}"', message)

    return (message, inline_images)

def add_attachment(fname, fcontent, content_type=None, parent=None, content_id=None, inline=False):
    """Add attachment to parent which must an email object"""

    import mimetypes
    from email import encoders
    from email.mime.audio import MIMEAudio
    from email.mime.base import MIMEBase
    from email.mime.image import MIMEImage
    from email.mime.text import MIMEText

    if not parent:
        return

    # Guess content type if not provided
    if not content_type:
        content_type, _encoding = mimetypes.guess_type(fname)

    if content_type is None:
        # No guess could be made, or the file is encoded (compressed), so
        # use a generic bag-of-bits type.
        content_type = "application/octet-stream"

    maintype, subtype = content_type.split("/", 1)

    if maintype == "text":
        if isinstance(fcontent, bytes):
            # If bytes are provided, assume UTF-8
            fcontent = fcontent.decode("utf-8")

        part = MIMEText(fcontent, _subtype=subtype, _charset="utf-8")

    elif maintype == "image":
        if isinstance(fcontent, str):
            fcontent = fcontent.encode("utf-8")
        part = MIMEImage(fcontent, _subtype=subtype)

    elif maintype == "audio":
        if isinstance(fcontent, str):
            fcontent = fcontent.encode("utf-8")
        part = MIMEAudio(fcontent, _subtype=subtype)

    else:
        if isinstance(fcontent, str):
            fcontent = fcontent.encode("utf-8")

        part = MIMEBase(maintype, subtype)
        part.set_payload(fcontent)
        encoders.encode_base64(part)

    # Set the filename parameter
    if fname:
        attachment_type = "inline" if inline else "attachment"
        clean_filename = re.sub(r"[\r\n]", "", str(fname))
        part.add_header("Content-Disposition", attachment_type, filename=clean_filename)

    if content_id:
        part.add_header("Content-ID", f"<{content_id}>")

    parent.attach(part)

def get_message_id():
    """Return Message ID created from doctype and name."""
    return email.utils.make_msgid(domain=get_app_url().replace("https://",""))

def sanitize_email_header(header: str):
    """
    Removes all line boundaries in the headers.

    Email Policy (python's std) has some bugs in it which uses splitlines
    and raises ValueError (ref: https://github.com/python/cpython/blob/main/Lib/email/policy.py#L143).
    Hence removing all line boundaries while sanitization of headers to prevent such faliures.
    The line boundaries which are removed can be found here: https://docs.python.org/3/library/stdtypes.html#str.splitlines
    """

    return "".join(header.splitlines())

def get_filecontent_from_path(path):
    if not path:
        return

    if path.startswith("/"):
        path = path[1:]

    if path.startswith("assets/"):
        # from public folder
        base_path = os.path.abspath("assets")
        full_path = os.path.abspath(path)
    elif path.startswith("files/"):
        # public file
        base_path = os.path.abspath(os.path.join(BASE_DIR, "public", "files"))
        full_path = os.path.abspath(os.path.join(BASE_DIR, "public", path))
    elif path.startswith("private/files/"):
        # private file
        base_path = os.path.abspath(os.path.join(BASE_DIR, "private", "files"))
        full_path = os.path.abspath(os.path.join(BASE_DIR, path))
    else:
        return None

    if os.path.commonpath((base_path, full_path)) != base_path:
        return None

    if os.path.exists(full_path):
        with open(full_path, "rb") as f:
            filecontent = f.read()

        return filecontent
    else:
        return None




class QueueBuilder:
    """Builds Email Queue from the given data"""

    def __init__(
        self,
        recipients=None,
        sender=None,
        subject=None,
        message=None,
        text_content=None,
        reference_doctype=None,
        reference_name=None,
        unsubscribe_method=None,
        unsubscribe_params=None,
        unsubscribe_message=None,
        attachments=None,
        reply_to=None,
        cc=None,
        bcc=None,
        message_id=None,
        in_reply_to=None,
        send_after=None,
        expose_recipients=None,
        send_priority=1,
        communication=None,
        read_receipt=None,
        queue_separately=False,
        is_notification=False,
        add_unsubscribe_link=1,
        inline_images=None,
        header=None,
        print_letterhead=False,
        with_container=False,
        email_read_tracker_url=None,
        x_priority: Literal[1, 3, 5] = 3,
        email_headers=None,
        raw_html=False,
        add_css=True,
        redact_message_after_send=False,
        wrapper=None,
    ):
        """Add email to sending queue (Email Queue)

        :param recipients: List of recipients.
        :param sender: Email sender.
        :param subject: Email subject.
        :param message: Email message.
        :param text_content: Text version of email message.
        :param reference_doctype: Reference DocType of caller document.
        :param reference_name: Reference name of caller document.
        :param send_priority: Priority for Email Queue, default 1.
        :param unsubscribe_method: URL method for unsubscribe. Default is `/api/method/frappe.email.queue.unsubscribe`.
        :param unsubscribe_params: additional params for unsubscribed links. default are name, doctype, email
        :param attachments: Attachments to be sent.
        :param reply_to: Reply to be captured here (default inbox)
        :param in_reply_to: Used to send the Message-Id of a received email back as In-Reply-To.
        :param send_after: Send this email after the given datetime. If value is in integer, then `send_after` will be the automatically set to no of days from current date.
        :param communication: Communication link to be set in Email Queue record
        :param queue_separately: Queue each email separately (one per recipient). When True, each TO recipient
        receives an individual email. Note: If CC/BCC are provided with queue_separately=True, CC/BCC
        recipients will receive one email for each TO recipient(duplicates), as each TO email is a separate message
        that includes CC/BCC. To avoid this, either don't use queue_separately, or add CC/BCC recipients
        to the recipients list instead.
        :param is_notification: Marks email as notification so will not trigger notifications from system
        :param add_unsubscribe_link: Send unsubscribe link in the footer of the Email, default 1.
        :param inline_images: List of inline images as {"filename", "filecontent"}. All src properties will be replaced with random Content-Id
        :param header: Append header in email (boolean)
        :param with_container: Wraps email inside styled container
        :param email_read_tracker_url: A URL for tracking whether an email is read by the recipient.
        :param x_priority: 1 = HIGHEST, 3 = NORMAL, 5 = LOWEST
        :param email_headers: Additional headers to be added in the email, e.g. {"X-Custom-Header": "value"} or {"Custom-Header": "value"}. Automatically prepends "X-" to the header name if not present.
        :param raw_html: Whether to treat email template as a complete HTML file
        :param add_css: Add default CSS from hooks/email_css to the email template (default True)
        :param redact_message_after_send: Replace the message body with a placeholder once sent, for emails carrying sensitive content.
        """

        self._unsubscribe_method = unsubscribe_method
        self._recipients = recipients
        self._cc = cc
        self._bcc = bcc
        self._send_after = send_after
        self._sender = sender
        self._text_content = text_content
        self._message = message
        self._x_priority: Literal[1, 3, 5] = x_priority
        self._add_unsubscribe_link = add_unsubscribe_link
        self._unsubscribe_message = unsubscribe_message
        self._attachments = attachments

        self._unsubscribed_user_emails = None
        self._email_account = None

        self.unsubscribe_params = unsubscribe_params
        self.subject = subject
        self.reference_doctype = reference_doctype
        self.reference_name = reference_name
        self.expose_recipients = expose_recipients
        self.with_container = with_container
        self.header = header
        self.reply_to = reply_to
        self.message_id = message_id
        self.in_reply_to = in_reply_to
        self.send_priority = send_priority
        self.communication = communication
        self.read_receipt = read_receipt
        self.queue_separately = queue_separately
        self.is_notification = is_notification
        self.inline_images = inline_images
        self.print_letterhead = print_letterhead
        self.email_read_tracker_url = email_read_tracker_url
        self.email_headers = email_headers
        self.raw_html = raw_html
        self.add_css = add_css
        self.redact_message_after_send = redact_message_after_send
        self.email_wrapper = wrapper or "templates/emails/standard.html"

    @property
    def unsubscribe_method(self):
        return self._unsubscribe_method or "/api/method/frappe.email.queue.unsubscribe"

    def _get_emails_list(self, emails=None):
        emails = split_emails(emails) if isinstance(emails, str) else (emails or [])
        return [each for each in set(emails) if each]

    @property
    def recipients(self):
        return self._get_emails_list(self._recipients)

    @property
    def cc(self):
        return self._get_emails_list(self._cc)

    @property
    def bcc(self):
        return self._get_emails_list(self._bcc)

    @property
    def send_after(self):
        if isinstance(self._send_after, int):
            return add_days(nowdate(), self._send_after)
        return self._send_after

    @property
    def sender(self):
        if not self._sender or self._sender == "Administrator":
            email_account = self.get_outgoing_email_account()
            return email_account.default_sender
        return self._sender

    def email_text_content(self):
        unsubscribe_msg = self.unsubscribe_message()
        unsubscribe_text_message = (unsubscribe_msg and unsubscribe_msg.text) or ""

        if self._text_content:
            return self._text_content + unsubscribe_text_message

        try:
            text_content = html_to_plain_text(self._message)
        except Exception:
            text_content = "See html attachment"
        return text_content + unsubscribe_text_message

    def email_html_content(self):
        email_account = self.get_outgoing_email_account()
        return get_formatted_html(
            self.subject,
            self._message,
            header=self.header,
            email_account=email_account,
            unsubscribe_link=self.unsubscribe_message(),
            with_container=self.with_container,
            raw_html=self.raw_html,
            add_css=self.add_css,
            wrapper=self.email_wrapper,
        )

    def should_include_unsubscribe_link(self):
        return (
            self._add_unsubscribe_link == 1
            and self.reference_doctype
            and (self._unsubscribe_message or self.reference_doctype == "Newsletter")
        )

    def unsubscribe_message(self):
        if self.should_include_unsubscribe_link():
            return get_unsubscribe_message(self._unsubscribe_message, self.expose_recipients)

    def get_outgoing_email_account(self):
        if self._email_account:
            return self._email_account

        # self._email_account = EmailAccount.find_outgoing(
        #     match_by_doctype=self.reference_doctype, match_by_email=self._sender, _raise_error=True
        # )
        self._email_account = get_email_settings()
        return self._email_account

    def get_unsubscribed_user_emails(self):
        return []
        # if self._unsubscribed_user_emails is not None:
        #     return self._unsubscribed_user_emails

        # all_ids = list(set(self.recipients + self.cc + self.bcc))

        # EmailUnsubscribe = DocType("Email Unsubscribe")

        # if len(all_ids) > 0:
        #     unsubscribed = (
        #         frappe.qb.from_(EmailUnsubscribe)
        #         .select(EmailUnsubscribe.email)
        #         .where(
        #             EmailUnsubscribe.email.isin(all_ids)
        #             & (
        #                 (
        #                     (EmailUnsubscribe.reference_doctype == self.reference_doctype)
        #                     & (EmailUnsubscribe.reference_name == self.reference_name)
        #                 )
        #                 | (EmailUnsubscribe.global_unsubscribe == 1)
        #             )
        #         )
        #         .distinct()
        #     ).run(pluck=True)
        # else:
        #     unsubscribed = None

        # self._unsubscribed_user_emails = unsubscribed or []
        # return self._unsubscribed_user_emails

    def final_recipients(self):
        unsubscribed_emails = self.get_unsubscribed_user_emails()
        return [mail_id for mail_id in self.recipients if mail_id not in unsubscribed_emails]

    def final_cc(self):
        unsubscribed_emails = self.get_unsubscribed_user_emails()
        return [mail_id for mail_id in self.cc if mail_id not in unsubscribed_emails]

    def final_bcc(self):
        unsubscribed_emails = self.get_unsubscribed_user_emails()
        return [mail_id for mail_id in self.bcc if mail_id not in unsubscribed_emails]

    def get_attachments(self):
        attachments = []
        if self._attachments:
            # store attachments with fid or print format details, to be attached on-demand later
            for att in self._attachments:
                if att.get("fid") or att.get("file_url"):
                    attachments.append(att)
                elif att.get("print_format_attachment") == 1:
                    if not att.get("lang", None):
                        att["lang"] = "en" # frappe.local.lang
                    att["print_letterhead"] = self.print_letterhead
                    attachments.append(att)
        return attachments

    def prepare_email_content(self):
        email_account = self.get_outgoing_email_account()
        if email_account.always_bcc:
            self._bcc = [*self.bcc, email_account.always_bcc]
        mail = get_email(
            recipients=self.final_recipients(),
            sender=self.sender,
            subject=self.subject,
            formatted=self.email_html_content(),
            text_content=self.email_text_content(),
            attachments=self._attachments,
            reply_to=self.reply_to,
            cc=self.final_cc(),
            bcc=self.final_bcc(),
            email_account=email_account,
            expose_recipients=self.expose_recipients,
            inline_images=self.inline_images,
            header=self.header,
            x_priority=self._x_priority,
        )

        mail.set_message_id(self.message_id, self.is_notification)

        if self.email_headers:
            mail.add_headers(self.email_headers)

        if self.read_receipt:
            mail.msg_root["Disposition-Notification-To"] = self.sender
        # if self.in_reply_to:
        #     if message_id := frappe.db.get_value("Communication", self.in_reply_to, "message_id"):
        #         message_id = message_id.strip("<> \t\n")
        #         mail.set_in_reply_to(f"<{message_id}>")
        return mail

    def process(self, send_now=False):
        """Build and return the email queues those are created.

        Sends email incase if it is requested to send now.
        """
        final_recipients = self.final_recipients()
        queue_separately = (final_recipients and self.queue_separately) or len(final_recipients) > 100
        if not (final_recipients + self.final_cc() + self.final_bcc()):
            return []

        queue_data = self.as_dict(include_recipients=False)
        if not queue_data:
            return []

        if not queue_separately:
            recipients = list(set(final_recipients + self.final_cc() + self.final_bcc()))
            email_account = self.get_outgoing_email_account()
            conn_args = {
                "server": email_account.server,
                "login": email_account.login,
                "password": email_account.password,
                "port": email_account.port or "587",
                "use_tls": email_account.use_tls or True
            }
            smtp = SMTPClient(**conn_args)
            # q = EmailQueue.new({**queue_data, **{"recipients": recipients}}, ignore_permissions=True)
            # send_now and q.send()
            if send_now:
                smtp.send(**{**queue_data, **{"recipients": recipients}})
            return
        else:
            if send_now and len(final_recipients) >= 1000:
                # force queueing if there are too many recipients to avoid timeouts
                send_now = False
            #TODO: Use redis queue
            # for recipients in frappe.utils.create_batch(final_recipients, 1000):
            #     frappe.enqueue(
            #         self.send_emails,
            #         queue_data=queue_data,
            #         final_recipients=recipients,
            #         job_name=frappe.utils.get_job_name(
            #             "send_bulk_emails_for", self.reference_doctype, self.reference_name
            #         ),
            #         now=frappe.in_test or send_now,
            #         queue="long",
            #     )

    def send_emails(self, queue_data, final_recipients):
        """
        Send emails to recipients separately.

        Note: CC/BCC recipients are included in each email sent to TO recipients.
        This means CC/BCC will receive one email per TO recipient. This is expected
        behavior because queue_separately creates individual emails for each TO
        recipient, and CC/BCC are copied on each individual email.

        """
        # This is used to bulk send emails from same sender to multiple recipients separately
        # This re-uses smtp server instance to minimize the cost of new session creation
        email_account = self.get_outgoing_email_account()
        conn_args = {
            "server": email_account.server,
            "login": email_account.login,
            "password": email_account.password,
            "port": email_account.port or "587",
            "use_tls": email_account.use_tls or True
        }
        smtp = SMTPClient(**conn_args)
        for r in final_recipients:
            recipients = list(set([r, *self.final_cc(), *self.final_bcc()]))
            # q = EmailQueue.new({**queue_data, **{"recipients": recipients}}, ignore_permissions=True)
            with suppress(Exception):
                # q.send(smtp_server_instance=smtp_server_instance, frappe_mail_client=frappe_mail_client)
                smtp.send(**{**queue_data, **{"recipients": recipients}})

        smtp.quit()

    def as_dict(self, include_recipients=True):
        email_account = self.get_outgoing_email_account()
        email_account_name = email_account and email_account.is_exists_in_db() and email_account.name

        mail = self.prepare_email_content()
        try:
            mail_to_string = cstr(mail.as_string())
        except InvalidEmailAddressError:
            # bad Email Address - don't add to queue
            # frappe.log_error(
            #     title="Invalid email address",
            #     message="Invalid email address Sender: {}, Recipients: {}, \nTraceback: {} ".format(
            #         self.sender, ", ".join(self.final_recipients()), traceback.format_exc()
            #     ),
            #     reference_doctype=self.reference_doctype,
            #     reference_name=self.reference_name,
            # )
            return

        d = {
            "priority": self.send_priority,
            "attachments": json.dumps(self.get_attachments()),
            "message_id": get_string_between("<", mail.msg_root["Message-Id"], ">"),
            "message": mail_to_string,
            "sender": mail.sender,
            "reference_doctype": self.reference_doctype,
            "reference_name": self.reference_name,
            "add_unsubscribe_link": self._add_unsubscribe_link,
            "unsubscribe_method": self.unsubscribe_method,
            "unsubscribe_params": self.unsubscribe_params,
            "expose_recipients": self.expose_recipients,
            "communication": self.communication,
            "send_after": self.send_after,
            "show_as_cc": ",".join(self.final_cc()),
            "show_as_bcc": ",".join(self.final_bcc()),
            "email_account": email_account_name or None,
            "email_read_tracker_url": self.email_read_tracker_url,
            "raw_html": self.raw_html,
            "add_css": self.add_css,
            "redact_message_after_send": self.redact_message_after_send,
        }

        if include_recipients:
            d["recipients"] = self.final_recipients()

        return d

def get_formatted_html(
    subject,
    message,
    footer=None,
    print_html=None,
    email_account=None,
    header=None,
    unsubscribe_link: _dict | None = None,
    sender=None,
    with_container=False,
    raw_html=False,
    add_css=True,
    wrapper="templates/emails/standard.html",
):
    from .jinja import get_template
    # email_account = email_account or EmailAccount.find_outgoing(match_by_email=sender)
    email_account = get_email_settings()

    params = {
        "site_url": get_app_url(),
        "title": subject,
        "print_html": print_html,
        "subject": subject,
    }

    if raw_html:
        rendered_email = message
    else:
        params.update(
            {
                "brand_logo": email_account.brand_logo if with_container or header else None,
                "brand_name": "Trakla" if with_container or header else None,
                "with_container": with_container,
                "header": get_header(header),
                "content": message,
                "footer": get_footer(email_account, footer),
            }
        )
        rendered_email = get_template(wrapper).render(params)

    html = scrub_urls(rendered_email)

    if unsubscribe_link:
        html = html.replace("<!--unsubscribe link here-->", unsubscribe_link.html)

    return inline_style_in_html(html, add_css=add_css)

def get_header(header=None):
    """Build header from template"""
    from .jinja import get_email_from_template

    if not header:
        return None

    if isinstance(header, str):
        # header = 'My Title'
        header = [header, None]
    if len(header) == 1:
        # header = ['My Title']
        header.append(None)
    # header = ['My Title', 'orange']
    title, indicator = header

    if not title:
        title = "Trakla"

    email_header, _text = get_email_from_template(
        "email_header", {"header_title": title, "indicator": indicator}
    )

    return email_header

def get_footer(email_account, footer=None):
    """append a footer (signature)"""
    from .jinja import get_email_from_template

    footer = footer or ""

    args = {}

    if email_account and email_account.footer:
        args.update({"email_account_footer": email_account.footer})

    sender_address = email_account.email_footer_address

    if sender_address:
        args.update({"sender_address": sender_address})

    if not cint(email_account.disable_standard_email_footer):
        # args.update({"default_mail_footer": frappe.get_hooks("default_mail_footer")})
        args.update({"default_mail_footer": None})

    footer += get_email_from_template("email_footer", args)[0]

    return footer

def inline_style_in_html(html, add_css=True):
    """Convert email.css and html to inline-styled html."""
    from premailer import Premailer

    if add_css:
        # get email css files from hooks
        # css_files = frappe.get_hooks("email_css")

        # css_files = ["email.bundle.css"]
        # css_files = [bundled_asset(path) for path in css_files]
        css_files = ["/assets/frappe/dist/css/email.bundle.M4VEYCA2.css"]
        css_files = [path.lstrip("/") for path in css_files]
        css_files = [css_file for css_file in css_files if os.path.exists(os.path.abspath(css_file))]
    else:
        css_files = None

    p = Premailer(
        html=html, external_styles=css_files, strip_important=False, allow_loading_external_files=True
    )

    return p.transform()

def get_unsubscribe_message(unsubscribe_message: str, expose_recipients: str) -> "_dict[str, str]":
    unsubscribe_message = unsubscribe_message or "Unsubscribe"
    unsubscribe_link = f'<a href="<!--unsubscribe_url-->" target="_blank">{unsubscribe_message}</a>'
    unsubscribe_html = f"{unsubscribe_link} to stop receiving emails of this type"
    html = f"""<div class="email-unsubscribe">
            <!--cc_message-->
            <div>
                {unsubscribe_html}
            </div>
        </div>"""

    text = f"\n\n{unsubscribe_message}: <!--unsubscribe_url-->\n"
    if expose_recipients == "footer":
        text = f"\n<!--cc_message-->{text}"

    return _dict(html=html, text=text)

def get_email_settings():
    app_settings = get_settings()
    # conn_args = {
    #             "server": email_account.server,
    #             "login": email_account.login,
    #             "password": email_account.password,
    #             "port": email_account.port or "587",
    #             "use_tls": email_account.use_tls or True
    #         }
    email_settings = {}
    return _dict(email_settings)



def sendmail(
    recipients=None,
    sender="",
    subject="No Subject",
    message="No Message",
    as_markdown=False,
    delayed=True,
    reference_doctype=None,
    reference_name=None,
    unsubscribe_method=None,
    unsubscribe_params=None,
    unsubscribe_message=None,
    add_unsubscribe_link=1,
    attachments=None,
    content=None,
    doctype=None,
    name=None,
    reply_to=None,
    queue_separately=False,
    cc=None,
    bcc=None,
    message_id=None,
    in_reply_to=None,
    send_after=None,
    expose_recipients=None,
    send_priority=1,
    communication=None,
    retry=1,
    now=None,
    read_receipt=None,
    is_notification=False,
    inline_images=None,
    template=None,
    args=None,
    header=None,
    print_letterhead=False,
    with_container=False,
    email_read_tracker_url=None,
    x_priority: Literal[1, 3, 5] = 3,
    email_headers=None,
    raw_html=False,
    add_css=True,
    redact_message_after_send=False,
    wrapper=None,
):
    """Send email using user's default **Email Account** or global default **Email Account**.


        :param recipients: List of recipients.
        :param sender: Email sender. Default is current user or default outgoing account.
        :param subject: Email Subject.
        :param message: (or `content`) Email Content.
        :param as_markdown: Convert content markdown to HTML.
        :param delayed: Send via scheduled email sender **Email Queue**. Don't send immediately. Default is true
        :param send_priority: Priority for Email Queue, default 1.
        :param reference_doctype: (or `doctype`) Append as communication to this DocType.
        :param reference_name: (or `name`) Append as communication to this document name.
        :param unsubscribe_method: Unsubscribe url with options email, doctype, name. e.g. `/api/method/unsubscribe`
        :param unsubscribe_params: Unsubscribe paramaters to be loaded on the unsubscribe_method [optional] (dict).
        :param attachments: List of attachments.
        :param reply_to: Reply-To Email Address.
        :param message_id: Used for threading. If a reply is received to this email, Message-Id is sent back as In-Reply-To in received email.
        :param in_reply_to: Used to send the Message-Id of a received email back as In-Reply-To.
        :param send_after: Send after the given datetime.
        :param expose_recipients: Controls recipient visibility. "header" shows all TO recipients in the To header.
    "footer" adds "This email was sent to..." text in footer. None (default) hides TO recipients from each other.
    Note: CC header is always visible regardless of this setting (as per email semantics).
        :param communication: Communication link to be set in Email Queue record
        :param inline_images: List of inline images as {"filename", "filecontent"}. All src properties will be replaced with random Content-Id
        :param template: Name of html template from templates/emails folder
        :param args: Arguments for rendering the template
        :param header: Append header in email
        :param with_container: Wraps email inside a styled container
        :param x_priority: 1 = HIGHEST, 3 = NORMAL, 5 = LOWEST
        :param email_headers: Additional headers to be added in the email, e.g. {"X-Custom-Header": "value"} or {"Custom-Header": "value"}. Automatically prepends "X-" to the header name if not present.
        :param raw_html: Whether to treat email template as a complete HTML file
        :param add_css: Whether to add CSS from hooks/email_css to the email template
        :param redact_message_after_send: Replace the message body with a placeholder once sent, for emails carrying sensitive content.
    """
    from .jinja import get_email_from_template

    if recipients is None:
        recipients = []
    if cc is None:
        cc = []
    if bcc is None:
        bcc = []

    text_content = None
    if template:
        message, text_content = get_email_from_template(template, args)

    message = content or message

    if as_markdown:

        message = md_to_html(message)

    if not delayed:
        now = True

    builder = QueueBuilder(
        recipients=recipients,
        sender=sender,
        subject=subject,
        message=message,
        text_content=text_content,
        reference_doctype=doctype or reference_doctype,
        reference_name=name or reference_name,
        add_unsubscribe_link=add_unsubscribe_link,
        unsubscribe_method=unsubscribe_method,
        unsubscribe_params=unsubscribe_params,
        unsubscribe_message=unsubscribe_message,
        attachments=attachments,
        reply_to=reply_to,
        cc=cc,
        bcc=bcc,
        message_id=message_id,
        in_reply_to=in_reply_to,
        send_after=send_after,
        expose_recipients=expose_recipients,
        send_priority=send_priority,
        queue_separately=queue_separately,
        communication=communication,
        read_receipt=read_receipt,
        is_notification=is_notification,
        inline_images=inline_images,
        header=header,
        print_letterhead=print_letterhead,
        with_container=with_container,
        email_read_tracker_url=email_read_tracker_url,
        x_priority=x_priority,
        email_headers=email_headers,
        raw_html=raw_html,
        add_css=add_css,
        redact_message_after_send=redact_message_after_send,
        wrapper=wrapper,
    )

    # build email queue and send the email if send_now is True.

    # q = builder.process(send_now=True)
    builder.process(send_now=True)
    # if now and q:
    # 	q.send()
    # return q