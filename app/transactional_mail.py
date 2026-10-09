"""
Bülten (newsletter.py) dışındaki tekil/işlemsel e-postalar için ortak
gönderici: e-posta doğrulama, ödeme başarısız uyarısı (dunning) vb.
"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid

from app.config import settings

logger = logging.getLogger("transactional_mail")


def send_simple_email(to_email: str, subject: str, body_text: str, body_html: str | None = None) -> bool:
    smtp_user = settings.clean_smtp_user
    smtp_password = settings.clean_smtp_password
    mail_from = settings.clean_mail_from

    if not smtp_user or not smtp_password or not mail_from:
        logger.error("SMTP ayarlanmamış, işlemsel e-posta gönderilemedi: %s -> %s", subject, to_email)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    from_name = settings.MAIL_FROM_NAME or "NewsLetter"
    msg["From"] = f"{from_name} <{mail_from}>"
    msg["To"] = to_email
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    msg.attach(MIMEText(body_text, "plain", "utf-8"))
    if body_html:
        msg.attach(MIMEText(body_html, "html", "utf-8"))

    try:
        if settings.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=25)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=25)
            server.ehlo()
            server.starttls()
            server.ehlo()
        with server:
            server.login(smtp_user, smtp_password)
            reddedilenler = server.sendmail(mail_from, [to_email], msg.as_string())
            if reddedilenler:
                logger.error("SMTP sunucusu bazı alıcıları reddetti: %s", reddedilenler)
                return False
        logger.info("E-posta başarıyla gönderildi: %s -> %s", subject, to_email)
        return True
    except Exception as exc:
        logger.error("İşlemsel e-posta gönderilemedi (%s -> %s): %s", subject, to_email, exc)
        return False
