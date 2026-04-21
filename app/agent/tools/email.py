import asyncio
import smtplib
from email.message import EmailMessage

from app.config import get_settings


async def send_email_tool(to: str, subject: str, body: str) -> str:
    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_user or settings.smtp_password is None:
        return "error: SMTP is not configured"

    def _send() -> None:
        msg = EmailMessage()
        msg["From"] = str(settings.smtp_from)
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        with smtplib.SMTP(settings.smtp_host, int(settings.smtp_port)) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)

    try:
        await asyncio.to_thread(_send)
        return "success: email sent"
    except Exception as exc:
        return f"error: {exc}"
