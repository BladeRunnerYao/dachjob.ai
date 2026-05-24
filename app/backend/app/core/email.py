import logging
import sys

import resend

from app.core.config import get_settings

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s:\t%(name)s:\t%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def send_reset_email(to_email: str, reset_link: str) -> bool:
    settings = get_settings()
    if not settings.resend_api_key:
        logger.warning("Resend API key not configured – cannot send email to %s", to_email)
        return False

    try:
        resend.api_key = settings.resend_api_key
        params: resend.Emails.SendParams = {
            "from": settings.resend_from_email,
            "to": [to_email],
            "subject": "dachjob.ai – Password Reset",
            "html": f"""<p>Hello,</p>
<p>A password reset was requested for your dachjob.ai account.</p>
<p>Click the link below to reset your password:</p>
<p><a href="{reset_link}">{reset_link}</a></p>
<p>This link expires in {settings.password_reset_token_minutes} minutes.</p>
<p>If you did not request this, please ignore this email.</p>""",
        }
        resend.Emails.send(params)
        logger.info("Reset email sent to %s", to_email)
        return True
    except Exception:
        logger.exception("Failed to send reset email to %s", to_email)
        return False
