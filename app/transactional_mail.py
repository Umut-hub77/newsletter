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


def send_simple_email(to_email: str, subject: str, body_text: str) -> bool:
    if not settings.SMTP_USER or not settings.SMTP_PASSWORD or not settings.MAIL_FROM:
        logger.error("SMTP ayarlanmamış, işlemsel e-posta gönderilemedi: %s -> %s", subject, to_email)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = settings.MAIL_FROM
    msg["To"] = to_email
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    msg.attach(MIMEText(body_text, "plain", "utf-8"))

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
            server.ehlo()
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            reddedilenler = server.sendmail(settings.MAIL_FROM, [to_email], msg.as_string())
            if reddedilenler:
                logger.error("SMTP sunucusu bazı alıcıları reddetti: %s", reddedilenler)
                return False
        return True
    except Exception as exc:
        logger.error("İşlemsel e-posta gönderilemedi (%s -> %s): %s", subject, to_email, exc)
        return False
