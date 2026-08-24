"""Board / tracking / approvals / summary endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from finalproject.auth.dependencies import get_current_user, require_roles
from finalproject.db.database import get_session
from finalproject.db.models import Account, Estimate, Project, Spec, User
from finalproject.engine.estimator import estimate as run_estimate
from finalproject.engine.parser import parse_spec
from finalproject.llm.spec_extraction import extract_spec
from finalproject.tracking import approvals as approvals_svc
from finalproject.tracking import service as tracking
from finalproject.tracking.service import STAGES

router = APIRouter(tags=["tracking"])


# ---------- request/response models --------------------------------------

class StageIn(BaseModel):
    stage: str | None = None


class DecisionIn(BaseModel):
    approved: bool
    note: str = ""


def _project_out(p: Project, ev) -> dict:
    return {
        "code": p.code,
        "title": p.title,
        "stage": p.stage,
        "status": p.status,
        "release_status": p.release_status,
        "overdue": tracking.is_overdue(p, ev),
        "required_date": p.required_date.isoformat() if p.required_date else None,
    }


# ---------- estimate -> project -> approval queue -------------------------


@router.post("/specs/{code}/estimate")
def estimate_spec(code: str,
                  user: User = Depends(require_roles("engineer", "manager")),
                  session: Session = Depends(get_session)):
    """Runs the pipeline on a spec; creates/updates the project and queues
    the plan for manager release (clause 0.2). Uses the LLM extraction chain
    when keys are configured, falling back to the deterministic parser."""
    spec = session.scalar(select(Spec).where(Spec.code == code))
    if not spec:
        raise HTTPException(404, f"spec {code} not found")

    parsed, source = extract_spec(spec.raw_text)
    result = run_estimate(session, spec.raw_text, parsed)
    if result.decision in ("ESCALATE", "REFUSE_OVERRIDE"):
        return {"spec": code, "decision": result.decision,
                "key_clause": result.key_clause, "reasons": result.reasons}

    project = session.scalar(select(Project).where(Project.code == code))
    if not project:
        project = Project(
            code=spec.code,
            account_id=spec.account_id,
            spec_id=spec.id,
            title=spec.title or code,
            stage="Production Planning",
            status="on_track",
            required_date=parse_spec(spec.raw_text).deadline,
            release_status="queued",
        )
        session.add(project)
        session.flush()

    version = 1 + len(session.scalars(
        select(Estimate).where(Estimate.project_id == project.id)).all())
    est = Estimate(
        project_id=project.id,
        version=version,
        decision=result.decision,
        material_cost_egp=result.material_cost_egp or 0.0,
        consumables_egp=result.consumables_egp or 0.0,
        fab_hours=result.fab_hours or 0.0,
        install_hours=result.install_hours or 0.0,
        labour_cost_egp=result.labour_cost_egp or 0.0,
        margin_applied=result.margin_applied or 0.0,
        final_price_egp=result.final_price_egp or 0.0,
        citations_json={"citations": result.citations,
                        "reasons": result.reasons,
                        "schedule": result.schedule,
                        "bom": result.bom_lines},
        created_by=user.id,
    )
    session.add(est)
    session.flush()
    approval = approvals_svc.queue_plan_release(session, est, project)
    return {
        "spec": code,
        "project": project.code,
        "estimate_version": version,
        "decision": result.decision,
        "parsed_by": source,
        "fab_hours": result.fab_hours,
        "install_hours": result.install_hours,
        "final_price_egp": result.final_price_egp,
        "schedule": result.schedule,
        "reasons": result.reasons,
        "approval_id": approval.id,
        "release_status": project.release_status,
    }


# ---------- board & portal -------------------------------------------------


@router.get("/board")
def board(user: User = Depends(require_roles("engineer", "manager", "viewer")),
          session: Session = Depends(get_session)):
    projects = session.scalars(select(Project)).all()
    columns = {s: [] for s in STAGES}
    for p in projects:
        ev = tracking.current_event(session, p)
        columns.setdefault(p.stage, []).append(_project_out(p, ev))
    return {"stages": STAGES, "columns": columns}


@router.get("/my/projects")
def my_projects(user: User = Depends(get_current_user),
                session: Session = Depends(get_session)):
    if user.role != "client" or not user.account_id:
        raise HTTPException(403, "client accounts only")
    projects = session.scalars(
        select(Project).where(Project.account_id == user.account_id)
    ).all()
    out = []
    for p in projects:
        ev = tracking.current_event(session, p)
        entry = _project_out(p, ev)
        entry["title"] = p.title
        out.append(entry)
    return {"projects": out}


@router.patch("/projects/{code}/stage")
def advance(code: str, body: StageIn,
            user: User = Depends(require_roles("engineer", "manager")),
            session: Session = Depends(get_session)):
    project = session.scalar(select(Project).where(Project.code == code))
    if not project:
        raise HTTPException(404, f"project {code} not found")
    try:
        project = tracking.advance_stage(session, project, body.stage)
    except tracking.TrackingError as exc:
        raise HTTPException(exc.status_code, exc.message)
    ev = tracking.current_event(session, project)
    return _project_out(project, ev)


# ---------- approvals (the gate) -------------------------------------------


@router.get("/approvals")
def list_approvals(user: User = Depends(require_roles("manager")),
                   session: Session = Depends(get_session)):
    return [
        {"id": a.id, "type": a.approval_type, "entity_id": a.entity_id,
         "note": a.note}
        for a in approvals_svc.pending(session)
    ]


@router.post("/approvals/{approval_id}/decision")
def decide(approval_id: int, body: DecisionIn,
           user: User = Depends(require_roles("manager")),
           session: Session = Depends(get_session)):
    try:
        approval = approvals_svc.decide(session, approval_id, user,
                                        body.approved, body.note)
    except approvals_svc.ApprovalError as exc:
        raise HTTPException(exc.status_code, exc.message)
    return {"id": approval.id, "decision": approval.decision,
            "approver": user.email, "at": approval.created_at.isoformat()}


@router.get("/audit")
def audit(user: User = Depends(require_roles("manager")),
          session: Session = Depends(get_session)):
    return approvals_svc.audit_trail(session)


# ---------- daily summary ---------------------------------------------------


@router.get("/summary/daily")
def daily_summary(user: User = Depends(require_roles("engineer", "manager")),
                  session: Session = Depends(get_session)):
    return tracking.daily_summary(session)


@router.get("/llm/status")
def llm_status(user: User = Depends(get_current_user)):
    """Which LLM providers are configured, for the UI status chip."""
    from finalproject.llm.base import configured_chain

    return {
        "providers": [c.name for c in configured_chain()],
        "primary": (configured_chain() or [None])[0].name if configured_chain() else None,
    }
