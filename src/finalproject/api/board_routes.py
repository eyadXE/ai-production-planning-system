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
    eng = (session_get_user(p.assigned_engineer_id)
           if p.assigned_engineer_id else None)
    return {
        "assigned_engineer": eng.full_name if eng else None,
        "code": p.code,
        "title": p.title,
        "stage": p.stage,
        "status": p.status,
        "release_status": p.release_status,
        "overdue": tracking.is_overdue(p, ev),
        "required_date": p.required_date.isoformat() if p.required_date else None,
        "estimated_finish": (p.estimated_finish.isoformat()
                             if p.estimated_finish else None),
    }


# ---------- estimate -> project -> approval queue -------------------------


@router.post("/specs/{code}/estimate")
def estimate_spec(code: str,
                  user: User = Depends(require_roles("estimator", "manager")),
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
            release_status="draft",
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
    if result.schedule and result.schedule.get("planned_finish"):
        from datetime import date as _date

        project.estimated_finish = _date.fromisoformat(
            result.schedule["planned_finish"])
    session.commit()
    return {
        "spec": code,
        "spec_title": spec.title,
        "account": (session.get(Account, spec.account_id).name
                    if session.get(Account, spec.account_id) else ""),
        "estimated_finish": (project.estimated_finish.isoformat()
                             if project.estimated_finish else None),
        "project": project.code,
        "estimate_version": version,
        "decision": result.decision,
        "parsed_by": source,
        "fab_hours": result.fab_hours,
        "install_hours": result.install_hours,
        "final_price_egp": result.final_price_egp,
        "schedule": result.schedule,
        "reasons": result.reasons,
        "next_step": "review & submit-to-manager",
    }


# ---------- board & portal -------------------------------------------------


@router.get("/board")
def board(user: User = Depends(require_roles("estimator", "engineer", "manager", "viewer")),
          session: Session = Depends(get_session)):
    projects = session.scalars(select(Project)).all()
    if user.role == "engineer":
        # project engineers see ONLY what they are assigned to
        projects = [p for p in projects if p.assigned_engineer_id == user.id]
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
    # tier-2 engineer may only advance THEIR assigned projects
    if user.role == "engineer" and project.assigned_engineer_id != user.id:
        raise HTTPException(403,
            "this project is assigned to another engineer")
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
def daily_summary(user: User = Depends(require_roles("manager")),
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


class AssignIn(BaseModel):
    engineer_id: int


@router.post("/projects/{code}/assign")
def assign_project(code: str, body: AssignIn,
                   user: User = Depends(require_roles("manager")),
                   session: Session = Depends(get_session)):
    """Manager assigns a project engineer who follows all stages."""
    project = session.scalar(select(Project).where(Project.code == code))
    if not project:
        raise HTTPException(404, f"project {code} not found")
    engineer = session.get(User, body.engineer_id)
    if not engineer or engineer.role != "engineer":
        raise HTTPException(422, "assignee must be a user with role 'engineer'")
    project.assigned_engineer_id = engineer.id
    session.commit()
    return {"code": code, "assigned_to": engineer.full_name,
            "engineer_id": engineer.id}


@router.get("/team/engineers")
def list_engineers(user: User = Depends(require_roles("manager")),
                   session: Session = Depends(get_session)):
    engineers = session.scalars(
        select(User).where(User.role == "engineer")).all()
    return [{"id": u.id, "name": u.full_name, "email": u.email}
            for u in engineers]


@router.get("/my-assignments")
def my_assignments(user: User = Depends(get_current_user),
                   session: Session = Depends(get_session)):
    if user.role != "engineer":
        raise HTTPException(403, "project engineers only")
    projects = session.scalars(
        select(Project).where(Project.assigned_engineer_id == user.id)).all()
    out = []
    for p in projects:
        ev = tracking.current_event(session, p)
        entry = _project_out(p, ev)
        entry["estimated_finish"] = (p.estimated_finish.isoformat()
                                     if p.estimated_finish else None)
        out.append(entry)
    return {"projects": out}


@router.get("/timeline")
def timeline(user: User = Depends(require_roles("estimator", "engineer", "manager", "viewer")),
             session: Session = Depends(get_session)):
    """Manager map: every project laid over the coming capacity weeks."""
    from finalproject.db.models import CapacityWeek

    weeks = session.scalars(
        select(CapacityWeek).order_by(CapacityWeek.start_date)).all()
    week_labels = [w.week_label for w in weeks]
    week_free = {w.week_label: w.total_hours - w.booked_hours for w in weeks}

    projects = session.scalars(select(Project)).all()
    rows = []
    for p in projects:
        schedule = None
        est = session.scalar(
            select(Estimate).where(Estimate.project_id == p.id)
            .order_by(Estimate.version.desc()))
        if est:
            schedule = (est.citations_json or {}).get("schedule")
        engineer = (session.get(User, p.assigned_engineer_id)
                    if p.assigned_engineer_id else None)
        ev = tracking.current_event(session, p)
        row = _project_out(p, ev)
        row.update({
            "engineer": engineer.full_name if engineer else None,
            "fab_weeks": (schedule or {}).get("bookings") or [],
            "install_week": (schedule or {}).get("install_week_label"),
            "planned_finish": (schedule or {}).get("planned_finish"),
        })
        rows.append(row)

    account_names = {}
    for r in rows:
        proj = session.scalar(select(Project).where(Project.code == r["code"]))
        if proj and proj.account_id:
            acc = session.get(Account, proj.account_id)
            r["client"] = acc.name if acc else ""
    return {"weeks": [
                {"label": wl, "free_hours": week_free[wl]}
                for wl in week_labels
            ],
            "projects": rows}


class ClientDecision(BaseModel):
    accept: bool


@router.post("/my/projects/{code}/decision")
def my_project_decision(code: str, body: ClientDecision,
                        user: User = Depends(get_current_user),
                        session: Session = Depends(get_session)):
    """Client accepts/declines a manager-approved plan from the portal."""
    from fastapi import HTTPException as _HTTPException

    project = session.scalar(select(Project).where(Project.code == code))
    if not project:
        raise _HTTPException(404, f"project {code} not found")
    if user.role != "client" or user.account_id != project.account_id:
        raise _HTTPException(403, "only the owning client can decide")
    if project.release_status != "manager_approved":
        raise _HTTPException(409, f"no plan awaiting your decision "
                                  f"(status: {project.release_status})")
    if body.accept:
        project.release_status = "client_accepted"
        msg = "Accepted — management will do the final release."
    else:
        project.release_status = "declined_by_client"
        project.status = "cancelled"
        msg = "Declined — our team will contact you."
    session.commit()
    return {"code": code, "release_status": project.release_status,
            "message": msg}


@router.get("/notifications/mine")
def my_notifications(user: User = Depends(get_current_user),
                     session: Session = Depends(get_session)):
    """Client dashboard notifications (mirrors the emails)."""
    from finalproject.db.models import Notification as N

    q = select(N).order_by(N.id.desc()).limit(30)
    rows = session.scalars(q).all()
    acc_ids = {user.account_id}
    out = []
    for n in rows:
        if user.account_id and n.account_id == user.account_id:
            out.append({
                "id": n.id, "template": n.template,
                "subject": (n.payload_json or {}).get("subject", ""),
                "at": n.sent_at.isoformat() if n.sent_at else None,
            })
    return {"notifications": [o for o in out][:20]}


def session_get_user(user_id: int):
    from finalproject.db.database import SessionLocal
    from finalproject.db.models import User as _U

    with SessionLocal() as s:
        u = s.get(_U, user_id)
        return u


@router.get("/materials")
def materials_stock(user: User = Depends(
        require_roles("estimator", "engineer", "manager")),
        session: Session = Depends(get_session)):
    """Resource view: current stock for capacity planning."""
    from finalproject.db.models import Material as M

    rows = session.scalars(select(M).order_by(M.code)).all()
    return {"materials": [
        {"code": m.code, "name": m.name, "unit": m.unit,
         "price_egp": m.price_egp, "stock": m.stock_qty,
         "lead_time_weeks": m.lead_time_weeks}
        for m in rows
    ]}
