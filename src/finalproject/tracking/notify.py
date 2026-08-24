"""Email notifications — queued in DB, delivered to SMTP if configured,
otherwise written to the outbox log (demo-safe: never crashes a release)."""

import logging
import os
import smtplib
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from sqlalchemy.orm import Session

from finalproject.db.models import Notification, User

log = logging.getLogger(__name__)

OUTBOX_LOG = Path("data/email_outbox.log")

TEMPLATES = {
    "plan_accepted": (
        "Your Ousus project {code} is planned",
        "Good news!\n\nYour request '{title}' ({code}) has been planned and "
        "released to production.\nEstimated completion: {finish}\n\n"
        "Track it any time in your Ousus portal.\n\n— Ousus Production Platform",
    ),
    "spec_approved": (
        "Your Ousus request {code} was approved for planning",
        "Your request '{title}' ({code}) passed engineering review and is now "
        "in the planning phase. We will notify you when the plan is ready.\n\n"
        "— Ousus Production Platform",
    ),
}


def send_email(session: Session, account_id: int, template: str,
               payload: dict) -> Notification:
    subject_tpl, body_tpl = TEMPLATES[template]
    subject = subject_tpl.format(**payload)
    body = body_tpl.format(**payload)

    recipients = [
        u.email for u in session.query(User)
        .filter(User.account_id == account_id, User.role == "client").all()
    ]
    notification = Notification(
        account_id=account_id,
        to_email=", ".join(recipients),
        template=template,
        payload_json={**payload, "subject": subject},
        status="queued",
    )
    session.add(notification)

    try:
        _deliver(recipients, subject, body)
        notification.status = "sent"
    except Exception as exc:  # noqa: BLE001 — delivery must never break the flow
        log.warning("email delivery failed: %s", exc)
        notification.status = "failed"
    notification.sent_at = datetime.utcnow()
    session.commit()
    return notification


def _deliver(recipients: list[str], subject: str, body: str) -> None:
    host = os.environ.get("OUSUS_SMTP_HOST")
    if host:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = os.environ.get("OUSUS_SMTP_FROM", "no-reply@ousus.example")
        msg["To"] = ", ".join(recipients)
        msg.set_content(body)
        port = int(os.environ.get("OUSUS_SMTP_PORT", "587"))
        with smtplib.SMTP(host, port) as smtp:
            if os.environ.get("OUSUS_SMTP_USER"):
                smtp.starttls()
                smtp.login(os.environ.get("OUSUS_SMTP_USER"),
                           os.environ.get("OUSUS_SMTP_PASS", ""))
            smtp.send_message(msg)
    else:
        OUTBOX_LOG.parent.mkdir(parents=True, exist_ok=True)
        with OUTBOX_LOG.open("a") as f:
            f.write(
                f"[{datetime.utcnow().isoformat()}] TO: {', '.join(recipients)} | "
                f"SUBJECT: {subject}\n{body}\n{'-' * 60}\n"
            )
