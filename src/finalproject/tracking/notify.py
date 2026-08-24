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
        "Your Ousus project {code} is planned — {title}",
        "Good news!\n\n"
        "Your request has been planned and released to production.\n\n"
        "PROJECT DETAILS\n"
        "---------------\n"
        "Project:      {code} — {title}\n"
        "Items:        {items}\n"
        "Finish:       {finish}\n"
        "Site:         {site}\n"
        "Required by:  {required}\n\n"
        "PLAN SUMMARY\n"
        "------------\n"
        "Fabrication:  {fab_hours} h\n"
        "Installation: {install_hours} h\n"
        "Quoted price: EGP {price}\n"
        "Starts:       {start_week}\n"
        "Estimated completion: {finish_date}\n\n"
        "Track it any time in your Ousus client portal.\n\n"
        "— Ousus Production Platform",
    ),
    "spec_approved": (
        "Your Ousus request {code} was approved for planning",
        "Your request has passed engineering review and is now in the "
        "planning phase.\n\n"
        "REQUEST DETAILS\n"
        "---------------\n"
        "Request:      {code} — {title}\n"
        "Items:        {items}\n\n"
        "We will email you the full plan (schedule, price, completion date) "
        "as soon as management releases it.\n\n"
        "— Ousus Production Platform",
    ),
}


def _estimate_details(estimate, project) -> dict:
    """Human-readable plan details pulled from the stored estimate."""
    details = {"items": "—", "finish": "—", "site": "—", "required": "—",
               "fab_hours": "—", "install_hours": "—", "price": "—",
               "start_week": "—", "finish_date": "—"}
    if not estimate:
        return details
    details["fab_hours"] = f"{estimate.fab_hours:g}"
    details["install_hours"] = f"{estimate.install_hours:g}"
    if estimate.final_price_egp:
        details["price"] = f"{estimate.final_price_egp:,.0f}"
    sched = (estimate.citations_json or {}).get("schedule") or {}
    if sched.get("start_week"):
        details["start_week"] = sched["start_week"]
    if sched.get("planned_finish"):
        details["finish_date"] = sched["planned_finish"]
    if project:
        spec = project.spec_id and SpecGet(project.spec_id)
        if spec is not None and spec.structured_json:
            data = spec.structured_json
            details["finish"] = data.get("finish") or "shop paint"
            details["site"] = data.get("site") or "—"
            items = data.get("items") or []
            if items:
                details["items"] = "; ".join(
                    f"{i['kind']} {i['qty']}" for i in items)
        details["required"] = str(project.required_date or "—")
    return details


def SpecGet(spec_id: int):
    from finalproject.db.models import Spec
    from finalproject.db.database import SessionLocal

    with SessionLocal() as s:
        return s.get(Spec, spec_id)


def send_email(session: Session, account_id: int, template: str,
               payload: dict, estimate=None, project=None) -> Notification:
    subject_tpl, body_tpl = TEMPLATES[template]
    payload = {**_estimate_details(estimate, project), **payload}
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
        _smtp_send(recipients, subject, body)
        notification.status = "sent"
    except Exception as exc:  # noqa: BLE001 — delivery must never break the flow
        log.warning("SMTP delivery failed (%s); written to outbox log", exc)
        _log_write(recipients, subject, body)
        notification.status = "sent" if not os.environ.get(
            "OUSUS_SMTP_HOST") else "failed"
    notification.sent_at = datetime.utcnow()
    session.commit()
    return notification


def _smtp_send(recipients: list[str], subject: str, body: str) -> None:
    host = os.environ.get("OUSUS_SMTP_HOST")
    if not host:
        raise RuntimeError("no SMTP host configured")
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ.get("OUSUS_SMTP_FROM", "no-reply@ousus.example")
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)
    port = int(os.environ.get("OUSUS_SMTP_PORT", "587"))
    with smtplib.SMTP(host, port) as smtp:
        smtp.starttls()
        smtp.login(os.environ.get("OUSUS_SMTP_USER", ""),
                   os.environ.get("OUSUS_SMTP_PASS", ""))
        smtp.send_message(msg)


def _log_write(recipients: list[str], subject: str, body: str) -> None:
    OUTBOX_LOG.parent.mkdir(parents=True, exist_ok=True)
    with OUTBOX_LOG.open("a") as f:
        f.write(
            f"[{datetime.utcnow().isoformat()}] TO: {', '.join(recipients)} | "
            f"SUBJECT: {subject}\n{body}\n{'-' * 60}\n"
        )
