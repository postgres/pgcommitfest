from django.template.loader import get_template

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.nonmultipart import MIMENonMultipart
from email.utils import formatdate
from email import encoders

from .models import QueuedMail


def send_simple_mail(
    sender, receiver, subject, msgtxt, sending_username, attachments=None
):
    # attachment format, each is a tuple of (name, mimetype,contents)
    # content should already be base64 encoded
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["To"] = receiver
    msg["From"] = sender
    msg["Date"] = formatdate(localtime=True)
    msg["User-Agent"] = "pgcommitfest"
    if sending_username:
        msg["X-cfsender"] = sending_username

    msg.attach(MIMEText(msgtxt, _charset="utf-8"))

    if attachments:
        for filename, contenttype, content in attachments:
            main, sub = contenttype.split("/")
            part = MIMENonMultipart(main, sub)
            part.set_payload(content)
            part.add_header(
                "Content-Disposition", 'attachment; filename="%s"' % filename
            )
            encoders.encode_base64(part)
            msg.attach(part)

    # Just write it to the queue, so it will be transactionally rolled back
    QueuedMail(sender=sender, receiver=receiver, fullmsg=msg.as_string()).save()


def send_mail(sender, receiver, fullmsg):
    # Send an email, prepared as the full MIME encoded mail already
    QueuedMail(sender=sender, receiver=receiver, fullmsg=fullmsg).save()


def send_template_mail(
    sender,
    senderaccountname,
    receiver,
    subject,
    templatename,
    templateattr={},
    usergenerated=False,
):
    send_simple_mail(
        sender,
        receiver,
        subject,
        get_template(templatename).render(templateattr),
        senderaccountname,
    )
