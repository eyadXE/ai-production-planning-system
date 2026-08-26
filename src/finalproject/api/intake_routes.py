"""Client intake requests + engineer review + manager deletion."""

import re
import uuid
from datetime import date
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from finalproject.auth.dependencies import get_current_user, require_roles
from finalproject.db.database import get_session
from finalproject.db.models import Account, Estimate, Material, Project, Spec, StageEvent, User
from finalproject.engine.estimator import estimate as run_estimate
from finalproject.engine.parser import Item, parse_deadline, parse_spec
from finalproject.tracking import approvals as approvals_svc
from finalproject.tracking.notify import send_email

router = APIRouter(tags=["intake"])

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

VALID_ITEM_KINDS = {
    "railing", "mezzanine", "flight", "gate_double", "gate_single",
    "security_door", "caged_ladder", "support_frame", "racking_bay",
    "canopy", "floor_plate_area",
}


class RequestItem(BaseModel):
    kind: str
    qty: float = Field(gt=0)
    note: str = ""


class CustomItem(BaseModel):
    name: str
    description: str = ""
    photo: str = ""          # /uploads/xx.png from the upload endpoint


class EstimatorDecision(BaseModel):
    approved: bool
    comment: str = ""


class RequestIn(BaseModel):
    title: str
    items: list[RequestItem] = []
    custom: list[CustomItem] = []
    finish: str = ""
    site: str = ""
    required_raw: str = ""


@router.get("/products")
def list_products(category: str | None = None):
    """Public catalog — no login needed to browse."""
    from finalproject.db.database import SessionLocal
    from finalproject.db.models import Product

    with SessionLocal() as s:
        q = select(Product).order_by(Product.category, Product.id)
        rows = s.scalars(q).all()
        if category:
            rows = [r for r in rows if r.category == category]
        cats = sorted({r.category for r in rows})
        from finalproject.db.products_data import CATALOGUES

        return {
            "catalogs": [{"title": t, "url": u} for t, u in CATALOGUES],
            "categories": cats,
            "products": [
                {"id": r.id, "category": r.category, "name": r.name,
                 "description": r.description, "image": r.image,
                 "est_kind": r.est_kind, "unit": r.unit}
                for r in rows
            ],
        }


def next_spec_code(session: Session) -> str:
    codes = session.scalars(select(Spec.code)).all()
    nums = [int(m.group(1)) for c in codes if (m := re.match(r"J-(\d+)", c))]
    return f"J-{max(nums, default=0) + 1:03d}"


@router.post("/requests")
def submit_request(body: RequestIn,
                   user: User = Depends(get_current_user),
                   session: Session = Depends(get_session)):
    """Client submits a cart/custom request -> waits for engineer review."""
    if not user.account_id:
        raise HTTPException(403, "client accounts only")
    bad = [i.kind for i in body.items if i.kind not in VALID_ITEM_KINDS]
    if bad:
        raise HTTPException(422, f"unknown item kinds: {bad}")
    if not body.items and not body.custom:
        raise HTTPException(422, "request is empty — add catalog items or a custom object")

    code = next_spec_code(session)
    structured = {
        "items": [i.model_dump() for i in body.items],
        "custom": [c.model_dump() for c in body.custom],
        "finish": body.finish or None,
        "site": body.site or None,
        "required_raw": body.required_raw,
    }
    spec = Spec(
        code=code,
        account_id=user.account_id,
        title=body.title[:200],
        raw_text=_render_raw(code, body),
        structured_json=structured,
        source="chat_intake",
        status="pending_review",
    )
    session.add(spec)
    session.commit()
    return {"code": spec.code, "status": spec.status,
            "message": ("Request submitted — an engineer will review it and "
                        "you will be notified.")}


@router.post("/uploads")
async def upload_photo(file: UploadFile = File(...),
                       user: User = Depends(get_current_user)):
    """Custom-object reference photos. Saved under data/uploads, served at /uploads/<name>."""
    ext = Path(file.filename or "photo.png").suffix.lower()
    if ext not in (".png", ".jpg", ".jpeg", ".webp"):
        raise HTTPException(422, "only png/jpg/webp images are allowed")
    name = f"{uuid.uuid4().hex[:12]}{ext}"
    dest = UPLOAD_DIR / name
    dest.write_bytes(await file.read())
    return {"url": f"/uploads/{name}"}





def _render_raw(code: str, body: RequestIn) -> str:
    items_txt = "; ".join(
        f"{i.kind} {i.qty}" + (f" ({i.note})" if i.note else "")
        for i in body.items
    )
    return (
        f"Project ID: {code}\n"
        f"Client account: AC-xx\nTitle: {body.title}\n"
        f"Date: auto\n\nItems: {items_txt}\n"
        f"Finish: {body.finish or 'unstated'}\nSite: {body.site or 'unstated'}\n"
        f"Required: {body.required_raw}\n"
    )


@router.get("/requests/pending")
def pending_requests(user: User = Depends(require_roles("estimator", "manager")),
                     session: Session = Depends(get_session)):
    from finalproject.db.models import Account

    specs = session.scalars(
        select(Spec).where(Spec.status == "pending_review").order_by(Spec.id)
    ).all()
    out = []
    for s in specs:
        account = session.get(Account, s.account_id)
        out.append({
            "code": s.code,
            "title": s.title,
            "account": account.name if account else "?",
            "structured": s.structured_json,
            "raw_text": s.raw_text,
        })
    return out


@router.post("/requests/{code}/run-estimate")
def run_estimate_endpoint(code: str,
                          user: User = Depends(require_roles("estimator", "manager")),
                          session: Session = Depends(get_session)):
    """Step 1 — estimator runs the pipeline and reviews the draft plan."""
    spec = session.scalar(select(Spec).where(Spec.code == code))
    if not spec or spec.status != "pending_review":
        raise HTTPException(404 if not spec else 409,
                            f"request {code} not pending" if spec else f"{code} not found")

    parsed = parse_spec(spec.raw_text)
    parsed.account_id = _account_code(session, spec.account_id)
    structured = spec.structured_json or {}
    if structured:
        from finalproject.engine.parser import Item
        from finalproject.engine.rates import WEEKLY_CAPACITY_DEFAULT as _W
        parsed.items = [
            Item(i["kind"], float(i["qty"]), i.get("note", ""))
            for i in structured.get("items") or []
        ]
        parsed.finish = structured.get("finish") or ""
        parsed.site = structured.get("site") or ""
        if structured.get("required_raw"):
            base = parsed.spec_date or date.today()
            parsed.deadline = (parse_deadline(structured["required_raw"], base)
                               or parsed.deadline)
        missing = []
        if not parsed.items and not structured.get("custom"):
            missing.append("item dimensions/quantities")
        parsed.missing = missing
        if structured.get("custom") and not structured.get("items"):
            # manual-plan path handled at decision time
            pass

    # custom-only requests get a manual-plan estimate with realistic
    # placeholder data so the estimator has something to review
    if structured.get("custom") and not parsed.items:
        customs = structured.get("custom") or []
        total_desc = " ".join(c.get("description", "") for c in customs).lower()
        # rough estimation heuristics
        base_hours = 40 + len(customs) * 20  # min 60h for any custom job
        if "large" in total_desc or "industrial" in total_desc:
            base_hours += 80
        fab_h = float(base_hours)
        inst_h = round(fab_h * 0.25, 1)
        mat_cost = len(customs) * 8500.0  # conservative material allowance
        cons_cost = mat_cost * 0.04
        labour = fab_h * 95.0 + inst_h * 120.0
        margin = 0.22  # standard tier
        price = (mat_cost + cons_cost + labour) * (1 + margin)
        from datetime import timedelta
        est_finish = (date.today() + timedelta(weeks=6)).isoformat()
        return {
            "code": code, "title": spec.title,
            "decision": "MANUAL_PLAN", "key_clause": "0.5",
            "reasons": ["Custom build — engineer will verify these "
                        "preliminary figures before production."],
            "fab_hours": float(fab_h), "install_hours": float(inst_h),
            "final_price_egp": round(price, 2),
            "material_cost_egp": round(mat_cost, 2),
            "schedule": {"start_week": "TBD", "planned_finish": est_finish},
            "bom_with_stock": [],
            "shortages": [],
            "citations": ["Manual plan — preliminary engineering estimate"],
            "custom_items": customs,
        }

    materials = session.scalars(select(Material)).all()
    stock_map = {m.code: m.stock_qty for m in materials}
    leads = {m.code: m.lead_time_weeks for m in materials}

    result = run_estimate(session, spec.raw_text, parsed)

    shortages = []
    bom_lines = []
    for l in getattr(result, "bom_lines", []):
        code_l = l.get("code", "")
        needed = l.get("qty", 0)
        stk = stock_map.get(code_l, 0)
        sufficient = stk >= needed
        if not sufficient:
            shortages.append({"code": code_l, "needed": needed,
                              "stock": stk,
                              "lead_time_weeks": leads.get(code_l, 0)})
        bom_lines.append({**l, "stock": stk, "sufficient": sufficient})
    result.bom_with_stock = bom_lines
    result.shortages = shortages

    return {
        "code": code, "title": spec.title,
        "decision": result.decision, "key_clause": result.key_clause,
        "reasons": result.reasons, "fab_hours": result.fab_hours,
        "install_hours": result.install_hours,
        "final_price_egp": result.final_price_egp,
        "material_cost_egp": result.material_cost_egp,
        "schedule": result.schedule,
        "bom_with_stock": bom_lines,
        "shortages": shortages,
        "citations": result.citations,
        "estimated_finish": (result.schedule or {}).get("planned_finish"),
    }


@router.post("/requests/{code}/decision")
def decide_request(code: str, body: EstimatorDecision,
                   user: User = Depends(require_roles("estimator", "manager")),
                   session: Session = Depends(get_session)):
    """Step 2 — estimator approves (with optional comment) or rejects
    (comment REQUIRED). Rejections are saved permanently for the manager."""
    spec = session.scalar(select(Spec).where(Spec.code == code))
    if not spec:
        raise HTTPException(404, f"request {code} not found")
    if spec.status != "pending_review":
        raise HTTPException(409, f"request already '{spec.status}'")

    comment = (body.comment or "").strip()
    if not body.approved and not comment:
        raise HTTPException(422, "a rejection requires a comment explaining why")

    if not body.approved:
        spec.status = "rejected"
        spec.rejection_note = comment
        spec.reviewed_by = user.id
        session.commit()
        return {"code": code, "status": "rejected", "note": comment}

    spec.status = "approved"
    spec.rejection_note = ""
    spec.reviewed_by = user.id
    structured = spec.structured_json or {}
    custom = structured.get("custom") or []

    project_code = None
    release_status = None

    if custom and not structured.get("items"):
        # manual plan path — create preliminary estimate with real numbers
        project_code = _create_project_from_spec(session, spec)
        proj_row = session.scalar(select(Project).where(Project.code == project_code))
        if proj_row:
            proj_row.release_status = "queued"
            n_items = max(len(structured.get("custom") or []), 1)
            est_fab = 60.0 + n_items * 20.0
            est_inst = round(est_fab * 0.25, 1)
            est_mat = n_items * 8500.0
            est_cons = round(est_mat * 0.04, 2)
            est_labour = round(est_fab * 95 + est_inst * 120, 2)
            est_price = round((est_mat + est_cons + est_labour) * 1.22, 2)
            from datetime import date as _d, timedelta as _td
            est_fin_date = (_d.today() + _td(weeks=6)).isoformat()
            from datetime import timedelta as _td
            est_fin = (date.today() + _td(weeks=6)).isoformat()
            est_row = Estimate(
                project_id=proj_row.id, version=1,
                decision="MANUAL_PLAN",
                material_cost_egp=est_mat, consumables_egp=est_cons,
                fab_hours=est_fab, install_hours=est_inst,
                labour_cost_egp=est_labour, margin_applied=0.22,
                final_price_egp=est_price,
                citations_json={"citations": [
                    "Manual plan — preliminary engineering estimate"],
                    "reasons": ["Custom build outside rate table"],
                    "schedule": {"planned_finish": est_fin_date}},
                created_by=user.id)
            session.add(est_row)
            session.flush()
            approval = approvals_svc.queue_plan_release(session, est_row, proj_row)
        if account_has_client(session, spec.account_id):
            send_email(session, spec.account_id, "custom_manual_plan",
                       {"code": spec.code, "title": spec.title})
        release_status = "queued"
        return {"code": code, "status": "approved",
                "decision": "MANUAL_PLAN", "project": project_code,
                "fab_hours": est_fab, "install_hours": est_inst,
                "final_price_egp": est_price}

    parsed = parse_spec(spec.raw_text)
    parsed.account_id = _account_code(session, spec.account_id)
    if structured:
        from finalproject.engine.parser import Item
        parsed.items = [Item(i["kind"], float(i["qty"]), i.get("note", ""))
                        for i in structured.get("items") or []]
        parsed.finish = structured.get("finish") or ""
        parsed.site = structured.get("site") or ""
        if structured.get("required_raw"):
            base = parsed.spec_date or date.today()
            parsed.deadline = (parse_deadline(structured["required_raw"], base)
                               or parsed.deadline)
        # finish/deadline optional on client requests
        missing = []
        if not parsed.items and not custom:
            missing.append("item dimensions/quantities")
        parsed.missing = missing

    result = run_estimate(session, spec.raw_text, parsed)

    if result.decision not in ("PLAN", "DELAY_RISK"):
        spec.status = "rejected"
        spec.rejection_note = "; ".join(result.reasons)[:500]
        session.commit()
        return {"code": code, "status": "rejected",
                "decision": result.decision, "reasons": result.reasons}

    required = parsed.deadline
    project = Project(
        code=spec.code, account_id=spec.account_id, spec_id=spec.id,
        title=spec.title or spec.code, stage="Production Planning",
        status="on_track", required_date=required, release_status="queued",
    )
    if result.schedule and result.schedule.get("planned_finish"):
        from datetime import date as _d
        project.estimated_finish = _d.fromisoformat(
            result.schedule["planned_finish"])
    session.add(project)
    session.flush()

    est = Estimate(
        project_id=project.id, version=1, decision=result.decision,
        material_cost_egp=result.material_cost_egp or 0.0,
        consumables_egp=result.consumables_egp or 0.0,
        fab_hours=result.fab_hours or 0.0,
        install_hours=result.install_hours or 0.0,
        labour_cost_egp=result.labour_cost_egp or 0.0,
        margin_applied=result.margin_applied or 0.0,
        final_price_egp=result.final_price_egp or 0.0,
        citations_json={"citations": result.citations,
                        "reasons": result.reasons,
                        "schedule": result.schedule},
        created_by=user.id,
    )
    session.add(est)
    session.flush()
    approval = approvals_svc.queue_plan_release(session, est, project)
    approval_id = approval.id
    if account_has_client(session, spec.account_id):
        sched = result.schedule or {}
        send_email(session, spec.account_id, "plan_ready",
                   {"code": spec.code, "title": spec.title,
                    "price": f"{result.final_price_egp:,.0f}" if result.final_price_egp else "—",
                    "fab_hours": f"{result.fab_hours:g}",
                    "install_hours": f"{result.install_hours:g}",
                    "finish_date": sched.get("planned_finish", "TBC")})

    return {"code": code, "status": "approved",
            "decision": result.decision, "project": project.code,
            "approval_id": approval_id,
            "final_price_egp": result.final_price_egp,
            "schedule": result.schedule}


@router.get("/requests/rejected")
def rejected_requests(user: User = Depends(require_roles("estimator", "manager")),
                      session: Session = Depends(get_session)):
    """Rejected requests — permanent record with who/why."""
    specs = session.scalars(
        select(Spec).where(Spec.status == "rejected").order_by(Spec.id.desc())
    ).all()
    out = []
    for s in specs:
        acc = session.get(Account, s.account_id)
        reviewer = session.get(User, s.reviewed_by) if s.reviewed_by else None
        out.append({"code": s.code, "title": s.title,
                    "account": acc.name if acc else "",
                    "note": s.rejection_note,
                    "reviewer": reviewer.full_name if reviewer else "—"})
    return out


def _account_code(session: Session, account_id: int) -> str:
    from finalproject.db.models import Account

    acc = session.get(Account, account_id)
    return acc.code if acc else "AC-01"


def _create_project_from_spec(session: Session, spec) -> str:
    """Custom-only request -> board project awaiting manual planning."""
    existing = session.scalar(select(Project).where(Project.code == spec.code))
    if existing:
        return existing.code
    p = Project(
        code=spec.code,
        account_id=spec.account_id,
        spec_id=spec.id,
        title=spec.title or spec.code,
        stage="Production Planning",
        status="on_track",
        release_status="na",
        required_date=None,
    )
    session.add(p)
    session.commit()
    return p.code


def account_has_client(session: Session, account_id: int) -> bool:
    return session.scalar(
        select(User.id).where(User.account_id == account_id).limit(1)
    ) is not None


@router.delete("/projects/{code}")
def delete_project(code: str,
                   user: User = Depends(require_roles("manager")),
                   session: Session = Depends(get_session)):
    """Manager-only removal when a client cancels; audit trail is kept."""
    project = session.scalar(select(Project).where(Project.code == code))
    if not project:
        raise HTTPException(404, f"project {code} not found")
    if project.release_status != "draft":
        raise HTTPException(403,
            "Only estimator-draft requests can be deleted — approved and "
            "released orders are permanent history.")
        raise HTTPException(
            403, "Released orders are permanent history and cannot be deleted "
            "(needed to track client behaviour). Cancel instead.")

    for ev in session.scalars(select(StageEvent)
                              .where(StageEvent.project_id == project.id)).all():
        session.delete(ev)
    for est in session.scalars(select(Estimate)
                               .where(Estimate.project_id == project.id)).all():
        for line in est.bom_lines:
            session.delete(line)
        session.delete(est)
    session.delete(project)
    session.commit()
    return {"deleted": code}


class DecisionIn(BaseModel):
    accept: bool


@router.post("/requests/{code}/submit-to-manager")
def submit_to_manager(code: str,
                      user: User = Depends(require_roles("estimator", "manager")),
                      session: Session = Depends(get_session)):
    """Estimator finished reviewing the plan -> send to manager queue."""
    from finalproject.tracking import approvals as approvals_svc
    from finalproject.db.models import Account, Estimate, Project, User

    project = session.scalar(select(Project).where(Project.code == code))
    if not project:
        raise HTTPException(404, f"project {code} not found")
    if project.release_status not in ("draft",):
        raise HTTPException(409, f"release_status is '{project.release_status}'")
    est = session.scalar(
        select(Estimate).where(Estimate.project_id == project.id)
        .order_by(Estimate.version.desc()))
    if not est:
        raise HTTPException(409, "no estimate to submit")

    project.release_status = "queued"
    approval = approvals_svc.queue_plan_release(session, est, project)
    session.refresh(project)

    # notify the client that the plan is with management
    if account_has_client(session, spec_account_id(session, code)):
        from finalproject.tracking.notify import send_email
        sched = (est.citations_json or {}).get("schedule") or {}
        send_email(session, project.account_id, "plan_ready",
                   {"code": project.code, "title": project.title,
                    "price": f"{est.final_price_egp:,.0f}" if est.final_price_egp else "—",
                    "fab_hours": f"{est.fab_hours:g}",
                    "install_hours": f"{est.install_hours:g}",
                    "finish_date": sched.get("planned_finish", "TBC")})
    return {"code": code, "release_status": "queued",
            "approval_id": approval.id}


@router.post("/projects/{code}/client-decision")
def client_decision(code: str, body: DecisionIn,
                    user: User = Depends(get_current_user),
                    session: Session = Depends(get_session)):
    """Client accepts or declines the manager-approved plan."""
    project = session.scalar(select(Project).where(Project.code == code))
    if not project:
        raise HTTPException(404, f"project {code} not found")
    if user.role != "client" or user.account_id != project.account_id:
        raise HTTPException(403, "only the owning client can decide")
    if project.release_status != "manager_approved":
        raise HTTPException(409, f"no plan awaiting client decision "
                                 f"(status: {project.release_status})")
    if body.accept:
        project.release_status = "client_accepted"
        msg = "Accepted — waiting for final release by management."
    else:
        project.release_status = "declined_by_client"
        project.status = "cancelled"
        msg = "Declined — our team will contact you."
    session.commit()
    return {"code": code, "release_status": project.release_status,
            "message": msg}


@router.post("/projects/{code}/release")
def release_project(code: str,
                    user: User = Depends(require_roles("manager")),
                    session: Session = Depends(get_session)):
    """Final release after client acceptance — records approver, emails client."""
    from finalproject.db.models import Approval, Estimate
    from finalproject.tracking.notify import send_email

    project = session.scalar(select(Project).where(Project.code == code))
    if not project:
        raise HTTPException(404, f"project {code} not found")
    if project.release_status != "client_accepted":
        raise HTTPException(409, "client must accept the plan before release "
                                 f"(status: {project.release_status})")
    if not project.assigned_engineer_id:
        raise HTTPException(409, "assign a project engineer before releasing")

    est = session.scalar(
        select(Estimate).where(Estimate.project_id == project.id)
        .order_by(Estimate.version.desc()))
    session.add(Approval(
        approval_type="final_release", entity_id=est.id if est else project.id,
        approver_id=user.id, decision="approved",
        note=f"Released after client acceptance"))
    project.release_status = "released"
    if account_has_client(session, project.account_id):
        schedule = ((est.citations_json or {}).get("schedule") or {}
                    ) if est else {}
        send_email(session, project.account_id, "plan_accepted",
                   {"code": project.code, "title": project.title,
                    "items": "see plan", "finish": "—", "site": "—",
                    "required": str(project.required_date or "—"),
                    "fab_hours": f"{est.fab_hours:g}" if est else "—",
                    "install_hours": f"{est.install_hours:g}" if est else "—",
                    "price": f"{est.final_price_egp:,.0f}" if est and est.final_price_egp else "—",
                    "start_week": schedule.get("start_week", "—"),
                    "finish_date": schedule.get("planned_finish", "—")},
                   estimate=est, project=project)
    session.commit()
    return {"code": code, "release_status": "released"}


def spec_account_id(session: Session, code: str):
    from finalproject.db.models import Spec as _S

    sp = session.scalar(select(_S).where(_S.code == code))
    return sp.account_id if sp else None
