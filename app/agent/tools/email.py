import asyncio
import imaplib
import smtplib
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import default

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

        with smtplib.SMTP(settings.smtp_host, int(settings.smtp_port), timeout=20) as smtp:
            smtp.starttls()
            smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(msg)

    try:
        await asyncio.to_thread(_send)
        return "success: email sent"
    except Exception as exc:
        return f"error: {exc}"


async def read_email_tool(limit: int = 5) -> str:
    settings = get_settings()
    if (
        not settings.imap_host
        or not settings.imap_user
        or settings.imap_password is None
    ):
        return "error: IMAP is not configured"

    safe_limit = max(1, min(int(limit), 20))

    def _first_text_body(message) -> str:
        if message.is_multipart():
            for part in message.walk():
                if part.get_content_type() == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        return payload.decode(errors="replace")
        payload = message.get_payload(decode=True)
        if payload:
            return payload.decode(errors="replace")
        return ""

    def _read() -> str:
        with imaplib.IMAP4_SSL(settings.imap_host, int(settings.imap_port)) as client:
            client.login(settings.imap_user, settings.imap_password)
            client.select("INBOX")
            status, data = client.search(None, "ALL")
            if status != "OK":
                return "error: failed to list emails"

            ids = data[0].split()
            if not ids:
                return "No emails found."
            selected = ids[-safe_limit:]

            lines: list[str] = []
            for msg_id in reversed(selected):
                f_status, f_data = client.fetch(msg_id, "(RFC822)")
                if f_status != "OK" or not f_data or not isinstance(f_data[0], tuple):
                    continue
                raw_bytes = f_data[0][1]
                message = BytesParser(policy=default).parsebytes(raw_bytes)
                subject = str(message.get("subject", "(no subject)"))
                from_addr = str(message.get("from", "(unknown)"))
                date_str = str(message.get("date", ""))
                snippet = _first_text_body(message).strip().replace("\r", " ").replace("\n", " ")
                snippet = snippet[:200] + ("..." if len(snippet) > 200 else "")
                lines.append(
                    f"- From: {from_addr}\n  Subject: {subject}\n  Date: {date_str}\n  Snippet: {snippet or '(empty)'}"
                )
            return "\n".join(lines) if lines else "No emails found."

    try:
        return await asyncio.to_thread(_read)
    except Exception as exc:
        return f"error: {exc}"
