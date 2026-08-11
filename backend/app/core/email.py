import logging
import smtplib
from email.message import EmailMessage

from app.models.instance_settings import InstanceSettings

logger = logging.getLogger("app.email")


def send_email(settings: InstanceSettings | None, *, to: str, subject: str, body: str) -> bool:
    """Sends via the instance's configured SMTP relay. Returns False (and
    logs instead of raising) whenever settings are missing/disabled rather
    than failing the caller — forgot-password must stay usable on a fresh
    install before anyone has configured SMTP; the token is still created
    either way, so an admin can still manually hand a user their reset link
    from the logs if needed.
    """
    if settings is None or not settings.smtp_enabled or not settings.smtp_host or not settings.smtp_from_address:
        logger.info("SMTP not configured — skipping send. Would have emailed %s: %s", to, subject)
        return False

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from_address
    message["To"] = to
    message.set_content(body)

    port = settings.smtp_port or (587 if settings.smtp_use_tls else 25)
    try:
        with smtplib.SMTP(settings.smtp_host, port, timeout=10) as smtp:
            if settings.smtp_use_tls:
                smtp.starttls()
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
        return True
    except (OSError, smtplib.SMTPException):
        logger.exception("Failed to send email to %s", to)
        return False
