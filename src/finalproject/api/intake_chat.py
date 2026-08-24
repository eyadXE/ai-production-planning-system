"""Conversational intake agent — the LLM conducts the interview.

No predefined script: the model decides what to ask next based on what is
still missing. The server only validates the final structure and creates
the request. If every provider is down, the endpoint reports llm=false so
the client falls back to the deterministic form flow (never breaks).
"""

import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from finalproject.api.intake_routes import _render_raw, next_spec_code
from finalproject.auth.dependencies import get_current_user
from finalproject.db.database import get_session
from finalproject.db.models import ChatMessage, ChatSession, Spec, User
from finalproject.llm.base import configured_chain
from finalproject.llm.client import LLMClient, extract_json

router = APIRouter(prefix="/intake", tags=["intake"])

VALID_ITEM_KINDS = {
    "railing", "mezzanine", "flight", "gate_double", "gate_single",
    "security_door", "caged_ladder", "support_frame", "racking_bay",
    "canopy", "floor_plate_area",
}

# models often append units ("railing(metres)") or use synonyms
KIND_ALIASES = {
    "fence": "railing", "balustrade": "railing", "guard_rail": "railing",
    "guardrail": "railing",
    "deck": "mezzanine", "platform": "mezzanine",
    "staircase": "flight", "stairs": "flight", "straight_flight": "flight",
    "double_gate": "gate_double", "single_gate": "gate_single",
    "door": "security_door", "ladder": "caged_ladder",
    "frame": "support_frame", "rack": "racking_bay",
}


def normalize_kind(raw: str) -> str | None:
    k = str(raw).strip().lower().split("(")[0].strip().replace(" ", "_")
    if k in VALID_ITEM_KINDS:
        return k
    return KIND_ALIASES.get(k)


def clean_items(raw_items) -> list[dict]:
    out = []
    for i in raw_items or []:
        if not isinstance(i, dict):
            continue
        kind = normalize_kind(i.get("kind", ""))
        qty = i.get("qty")
        try:
            qty = float(qty)
        except (TypeError, ValueError):
            continue
        if kind and qty > 0:
            out.append({"kind": kind, "qty": qty})
    return out

SYSTEM_PROMPT = """You are the friendly custom-work assistant for Ousus, a \
steel fabrication company. The client wants something CUSTOM made that is not \
in the standard catalog. Conduct a short natural conversation to collect the \
MINIMUM set of details an engineer needs to plan and quote it:

REQUIRED (cannot submit without):
- name: short item name
- description: what it is + key dimensions/size (L x W x H, or area, or rise)
- quantity: how many units
- material_finish: mild steel / stainless / aluminium, and finish (paint RAL,
  galvanised, polished...) — if unknown, suggest a sensible default and confirm

OPTIONAL but ask once if not offered:
- site: delivery/installation location
- required_raw: deadline phrase copied verbatim (e.g. "within 6 weeks")

RULES
- One topic per message. Short, warm, professional.
- If the client's answer already contains several answers, accept them all —
  never re-ask something they told you.
- Never invent values. Never compute prices or dates.
- When REQUIRED fields are collected, summarise everything in your reply and
  ask the client to confirm submission. Only after they confirm, set
  complete=true.

OUTPUT — raw JSON only, nothing else:
{"reply": "<your message>", "complete": false, "data": null}
or on confirmation:
{"reply": "...", "complete": true, "data": {"name": "...",
 "description": "...", "quantity": 1, "material_finish": "...",
 "site": "...", "required_raw": "..."}}"""


class MessageIn(BaseModel):
    text: str


def _history(session_db: Session, cs: ChatSession) -> str:
    msgs = session_db.scalars(
        select(ChatMessage).where(ChatMessage.session_id == cs.id)
        .order_by(ChatMessage.id)
    ).all()
    return "\n".join(f"{m.role.upper()}: {m.content}" for m in msgs[-14:])


@router.post("/start")
def start(user: User = Depends(get_current_user),
          session: Session = Depends(get_session)):
    if not user.account_id:
        raise HTTPException(403, "client accounts only")
    if not configured_chain():
        return {"session_id": None, "reply": None, "llm": False}

    cs = ChatSession(account_id=user.account_id, user_id=user.id,
                     purpose="spec_intake", collected_json={}, status="active")
    session.add(cs)
    session.flush()

    client = LLMClient()
    resp = client.complete(
        "The client just opened the intake chat. Greet them and ask what "
        "they would like built.")
    if resp is None:
        session.rollback()
        return {"session_id": None, "reply": None, "llm": False}
    data = extract_json(resp.content) or {}
    reply = data.get("reply") or (
        "Hi! I'm the Ousus assistant. Tell me what you'd like us to build.")
    session.add(ChatMessage(session_id=cs.id, role="assistant", content=reply))
    session.commit()
    return {"session_id": cs.id, "reply": reply, "llm": True}


@router.post("/{session_id}/message")
def message(session_id: int, body: MessageIn,
            user: User = Depends(get_current_user),
            session: Session = Depends(get_session)):
    cs = session.get(ChatSession, session_id)
    if not cs or cs.user_id != user.id:
        raise HTTPException(404, "chat session not found")
    if cs.status != "active":
        raise HTTPException(409, "request already submitted")
    session.add(ChatMessage(session_id=cs.id, role="client",
                            content=body.text))

    client = LLMClient()
    resp = client.complete(_history(session, cs) + f"\nCLIENT: {body.text}",
                           system=SYSTEM_PROMPT)
    if resp is None:
        session.commit()
        return {"llm": False,
                "reply": ("Our smart assistant is offline right now — please "
                          "use the guided form instead.")}
    data = extract_json(resp.content)
    if not data or "reply" not in data:
        # one retry with a stricter nudge
        resp = client.complete(
            _history(session, cs) +
            "\n\nSYSTEM: Reply with ONLY the JSON object as instructed.",
            system=SYSTEM_PROMPT)
        data = extract_json(resp.content) if resp else None
        if not data:
            session.commit()
            return {"llm": True, "reply": "Could you say that once more?"}

    if data.get("complete") and isinstance(data.get("data"), dict):
        d = data["data"]
        # schema gate: the minimum an engineer needs to plan a custom build
        missing = []
        name = str(d.get("name") or "").strip()
        desc = str(d.get("description") or "").strip()
        qty = d.get("quantity")
        try:
            qty = float(qty)
        except (TypeError, ValueError):
            qty = 0
        if not name:
            missing.append("name")
        if len(desc) < 5:
            missing.append("description/dimensions")
        if not qty or qty <= 0:
            missing.append("quantity")
        material = str(d.get("material_finish") or "").strip()
        if not material:
            d["material_finish"] = "mild steel, shop painted"
        if missing:
            data["complete"] = False
            data["reply"] = ("Before we submit — I still need: "
                             + ", ".join(missing) + ". Could you fill those in?")
        else:
            code = next_spec_code(session)
            structured = {
                "items": [],
                "custom": [{
                    "name": name,
                    "description": desc,
                    "photo": (cs.collected_json or {}).get("photo", ""),
                    "quantity": qty,
                    "material_finish": d.get("material_finish"),
                }],
                "finish": d.get("material_finish") or "",
                "site": d.get("site") or "",
                "required_raw": d.get("required_raw") or "",
            }
            spec = Spec(
                code=code,
                account_id=user.account_id,
                title=name[:200],
                raw_text=(
                    f"Project ID: {code}\nTitle: {name}\nDate: auto\n\n"
                    f"Items: custom — {desc} x{qty:g} ({material})\n"
                    f"Site: {structured['site'] or 'unstated'}\n"
                    f"Required: {structured['required_raw'] or 'unstated'}\n"
                ),
                structured_json=structured,
                source="chat_intake",
                status="pending_review",
            )
            session.add(spec)
            cs.status = "submitted"
            cs.collected_json = structured
            session.add(ChatMessage(
                session_id=cs.id, role="assistant",
                content=f"Submitted as request {spec.code}."))
            session.commit()
            return {"llm": True, "complete": True, "code": spec.code,
                    "reply": data["reply"]}

    session.add(ChatMessage(session_id=cs.id, role="assistant",
                            content=data.get("reply", "")))
    cs.collected_json = data.get("data") or cs.collected_json
    session.commit()
    return {"llm": True, "complete": False, "reply": data["reply"]}


class _ReqItem:
    def __init__(self, kind, qty, note=""):
        self.kind = kind
        self.qty = qty
        self.note = note


def _as_request_body(d: dict):
    """Adapter so _render_raw works with chat data."""

    class B:
        title = d.get("title", "")
        finish = d.get("finish") or ""
        site = d.get("site") or ""
        required_raw = d.get("required_raw", "")
        items = [_ReqItem(i["kind"], i["qty"], "") for i in d["items"]]

    return B()


@router.get("/sessions/mine")
def my_sessions(user: User = Depends(get_current_user),
                session: Session = Depends(get_session)):
    sessions = session.scalars(
        select(ChatSession).where(ChatSession.user_id == user.id)
        .order_by(ChatSession.id.desc())
    ).all()
    return [{"id": s.id, "status": s.status, "purpose": s.purpose}
            for s in sessions]


class PhotoIn(BaseModel):
    url: str


@router.post("/{session_id}/photo")
def attach_photo(session_id: int, body: PhotoIn,
                 user: User = Depends(get_current_user),
                 session: Session = Depends(get_session)):
    """Client attached a reference photo; remembered for the submission."""
    cs = session.get(ChatSession, session_id)
    if not cs or cs.user_id != user.id:
        raise HTTPException(404, "chat session not found")
    if not body.url.startswith("/uploads/"):
        raise HTTPException(422, "invalid upload url")
    collected = dict(cs.collected_json or {})
    collected["photo"] = body.url
    cs.collected_json = collected
    session.commit()
    return {"ok": True}
