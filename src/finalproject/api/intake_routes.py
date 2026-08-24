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
from finalproject.db.models import Estimate, Project, Spec, StageEvent, User
from finalproject.engine.estimator import estimate as run_estimate
from finalproject.engine.parser import parse_spec
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


class RequestIn(BaseModel):
    title: str
    items: list[RequestItem] = []
    custom: list[CustomItem] = []
    finish: str = ""
    site: str = ""
    required_raw: str


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
def pending_requests(user: User = Depends(require_roles("engineer", "manager")),
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


@router.post("/requests/{code}/review")
def review_request(code: str, approve: bool,
                   user: User = Depends(require_roles("engineer", "manager")),
                   session: Session = Depends(get_session)):
    """Engineer gate: approve moves the request into the planning phase."""
    spec = session.scalar(select(Spec).where(Spec.code == code))
    if not spec:
        raise HTTPException(404, f"request {code} not found")
    if spec.status != "pending_review":
        raise HTTPException(409, f"request already '{spec.status}'")

    if not approve:
        spec.status = "rejected"
        spec.reviewed_by = user.id
        session.commit()
        return {"code": code, "status": "rejected"}

    spec.status = "approved"
    spec.reviewed_by = user.id

    structured = spec.structured_json or {}
    custom = structured.get("custom") or []

    # planning phase — same deterministic pipeline as file specs
    parsed = parse_spec(spec.raw_text)
    parsed.account_id = _account_code(session, spec.account_id)
    # merge chat-structured items so nothing depends on raw-text parsing
    if structured:
        from finalproject.engine.parser import Item

        parsed.items = [
            Item(i["kind"], float(i["qty"]), i.get("note", ""))
            for i in structured.get("items") or []
        ]
        parsed.finish = structured.get("finish") or ""
        parsed.site = structured.get("site") or ""
        deadline = parse_spec(spec.raw_text).deadline  # via Required line
        if spec.structured_json.get("required_raw"):
            base = parsed.spec_date or date.today()
            from finalproject.engine.parser import parse_deadline

            d = parse_deadline(spec.structured_json["required_raw"], base)
            parsed.deadline = d or parsed.deadline
        missing = []
        if not parsed.items and not custom:
            missing.append("item dimensions/quantities")
        fin = parsed.finish.lower().strip(" .")
        if not fin or fin == "unstated":
            if not custom:      # custom objects carry their own description
                missing.append("finish")
        if parsed.deadline is None and not custom:
            missing.append("required date")
        parsed.missing = missing

    # Custom-only requests can't be auto-estimated by the rate handbook —
    # they go straight to the board for manual engineering planning.
    if structured.get("custom") and not structured.get("items"):
        spec.project_ref = _create_project_from_spec(session, spec)
        if account_has_client(session, spec.account_id):
            send_email(session, spec.account_id, "spec_approved",
                       {"code": spec.code, "title": spec.title})
        return {
            "code": spec.code, "status": spec.status,
            "decision": "MANUAL_PLAN",
            "reasons": ["Contains custom object(s) — routed to engineers "
                        "for a manual plan (rate handbook does not apply)."],
            "project": spec.project_ref,
        }

    result = run_estimate(session, spec.raw_text, parsed)

    project = None
    approval_id = None
    if result.decision in ("PLAN", "DELAY_RISK"):
        required = parsed.deadline
        project = Project(
            code=spec.code,
            account_id=spec.account_id,
            spec_id=spec.id,
            title=spec.title or spec.code,
            stage="Production Planning",
            status="on_track",
            required_date=required,
            release_status="queued",
        )
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
            send_email(session, spec.account_id, "spec_approved",
                       {"code": spec.code, "title": spec.title})

    session.refresh(spec)
    return {
        "code": spec.code, "status": spec.status,
        "decision": result.decision, "key_clause": result.key_clause,
        "reasons": result.reasons, "fab_hours": result.fab_hours,
        "install_hours": result.install_hours,
        "final_price_egp": result.final_price_egp,
        "schedule": result.schedule,
        "project": project.code if project else None,
        "approval_id": approval_id,
    }


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
