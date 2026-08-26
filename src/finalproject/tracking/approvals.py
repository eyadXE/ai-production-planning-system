"""Approval queue — the release gate (clause 0.2) with a real audit trail."""

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

from finalproject.db.models import Account, Approval, Estimate, Project, User


class ApprovalError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def account_email(session: Session, account_id: int) -> bool:
    """Whether the client account has any contactable user."""
    return session.scalar(
        select(User.id).where(User.account_id == account_id).limit(1)
    ) is not None


def queue_plan_release(session: Session, estimate: Estimate,
                       project: Project) -> Approval:
    """Every plan waits here; nothing reaches the floor without a manager."""
    project.release_status = "queued"
    approval = Approval(
        approval_type="plan_release",
        entity_id=estimate.id,
        approver_id=0,          # unassigned until decided; replaced on decision
        decision="pending",
        note=f"Plan v{estimate.version} for {project.code} ({estimate.decision})",
    )
    session.add(approval)
    session.commit()
    session.refresh(project)
    return approval


def pending(session: Session) -> list[Approval]:
    return session.scalars(
        select(Approval).where(Approval.decision == "pending")
        .order_by(Approval.id)
    ).all()


def decide(session: Session, approval_id: int, approver: User,
           approved: bool, note: str = "") -> Approval:
    """Records who approved what, when (0.2). Manager-only, enforced by API."""
    if approver.role != "manager":
        raise ApprovalError("only a manager may open the release gate", 403)
    approval = session.get(Approval, approval_id)
    if not approval:
        raise ApprovalError("approval not found", 404)
    if approval.decision != "pending":
        raise ApprovalError("already decided", 409)

    approval.approver_id = approver.id
    approval.decision = "approved" if approved else "rejected"
    if note:
        approval.note = f"{approval.note} | {note}"

    if approval.approval_type == "plan_release":
        estimate = session.get(Estimate, approval.entity_id)
        if not estimate:
            log.error("approval %s: estimate %s not found — rolling back",
                      approval.id, approval.entity_id)
            raise ApprovalError(
                f"approval {approval.id} points to missing estimate "
                f"{approval.entity_id} — cannot decide", 500)
        project = session.get(Project, estimate.project_id)
        if not project:
            log.error("approval %s: project %s not found — rolling back",
                      approval.id, estimate.project_id)
            raise ApprovalError(
                f"estimate {estimate.id} points to missing project "
                f"{estimate.project_id} — cannot decide", 500)
        if project.release_status != "client_accepted":
            raise ApprovalError(
                f"{project.code}: the client must accept the plan before "
                f"this gate (status: {project.release_status})", 409)
        # Client accepted -> manager opens the final gate
        project.release_status = (
            "manager_approved" if approved else "rejected"
        )
        if approved and account_email(session, project.account_id):
            from finalproject.tracking.notify import send_email

            sched = ((estimate.citations_json or {}).get("schedule")
                     or {})
            send_email(
                session, project.account_id, "plan_accepted",
                {
                    "code": project.code,
                    "title": project.title,
                    "items": "see plan details in dashboard",
                    "finish": sched.get("planned_finish", "TBC"),
                    "site": "—", "required":
                        str(project.required_date or "—"),
                    "fab_hours": f"{estimate.fab_hours:g}",
                    "install_hours": f"{estimate.install_hours:g}",
                    "price": (f"{estimate.final_price_egp:,.0f}"
                              if estimate.final_price_egp else "—"),
                    "start_week": sched.get("start_week", "—"),
                    "finish_date": sched.get("planned_finish", "—"),
                },
                estimate=estimate, project=project,
            )
    session.commit()
    session.refresh(approval)
    return approval


def audit_trail(session: Session, limit: int = 100) -> list[dict]:
    """Who decided what, and when."""
    rows = session.scalars(
        select(Approval).order_by(Approval.id.desc()).limit(limit)
    ).all()
    return [
        {
            "id": r.id,
            "type": r.approval_type,
            "entity_id": r.entity_id,
            "decision": r.decision,
            "approver_id": r.approver_id,
            "note": r.note,
            "at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
