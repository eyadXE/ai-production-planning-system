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

SYSTEM_PROMPT = """You are the friendly intake assistant for Ousus, a steel \
fabrication company. Conduct a short natural conversation to collect ALL of:
- title: short project name
- items: list of {"kind","qty"} — kind must be exactly one of:
  railing(metres), mezzanine(m2), flight(count of straight flights),
  gate_double(count), gate_single(count), security_door(count),
  caged_ladder(count), support_frame(count), racking_bay(count),
  canopy(m2), floor_plate_area(m2)
- finish: paint colour / coating, or "none"
- site: delivery or installation location
- required_raw: deadline phrase copied verbatim (e.g. "within 6 weeks")

RULES
- One topic per message. Short, warm, professional.
- If an answer is vague (e.g. "a fence for my yard"), map it to the closest
  kind and confirm quantity with a concrete question ("roughly how many
  metres?").
- Never invent values. Never compute prices or dates.
- When you have everything, summarise all fields in your reply and ask the
  client to confirm. Only after they confirm, set complete=true.

OUTPUT — raw JSON only, nothing else:
{"reply": "<your message>", "complete": false, "data": null}
or on confirmation:
{"reply": "...", "complete": true, "data": {"title": "...", "items":
 [{"kind": "...", "qty": 0}], "finish": "...", "site": "...",
  "required_raw": "..."}}"""


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
        items = clean_items(d.get("items"))
        if not d.get("title") or not items:
            data["complete"] = False
            data["reply"] = ("Before we finish — could you confirm the item "
                             "type(s) and rough dimensions/quantities?")
        else:
            code = next_spec_code(session)
            spec = Spec(
                code=code,
                account_id=user.account_id,
                title=str(d["title"])[:200],
                raw_text=_render_raw(code, _as_request_body(d)),
                structured_json={
                    "items": items,
                    "finish": d.get("finish") or "",
                    "site": d.get("site") or "",
                    "required_raw": d.get("required_raw") or "",
                },
                source="chat_intake",
                status="pending_review",
            )
            session.add(spec)
            cs.status = "submitted"
            cs.collected_json = items
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
