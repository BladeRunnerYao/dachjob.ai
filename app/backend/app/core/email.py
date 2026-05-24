import logging
import smtplib
from email.mime.text import MIMEText

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def send_reset_email(to_email: str, reset_link: str) -> bool:
    settings = get_settings()
    if not settings.smtp_host:
        logger.info(f"SMTP not configured. Reset link for {to_email}: {reset_link}")
        return False

    body = f"""Hello,

A password reset was requested for your dachjob.ai account.
Click the link below to reset your password:

{reset_link}

This link expires in {settings.password_reset_token_minutes} minutes.

If you did not request this, please ignore this email.
"""
    msg = MIMEText(body)
    msg["Subject"] = "dachjob.ai – Password Reset"
    msg["From"] = settings.smtp_from_email
    msg["To"] = to_email

    try:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port)
        if settings.smtp_use_tls:
            server.starttls()
        if settings.smtp_username and settings.smtp_password:
            server.login(settings.smtp_username, settings.smtp_password)
        server.send_message(msg)
        server.quit()
        logger.info(f"Reset email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send reset email to {to_email}: {e}")
        return False
