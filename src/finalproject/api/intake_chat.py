"""Conversational custom-work intake — LLM conducts the interview.

Server owns collected-state. When every provider fails, the deterministic
guided interview takes over automatically — the chat can never dead-end.
"""

import json
import logging
import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from finalproject.auth.dependencies import get_current_user
from finalproject.api.intake_guided import guided_turn
from finalproject.api.intake_routes import next_spec_code
from finalproject.db.database import get_session
from finalproject.db.models import ChatMessage, ChatSession, Spec, User
from finalproject.llm.base import configured_chain
from finalproject.llm.client import LLMClient, extract_json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/intake", tags=["intake"])

VALID_KINDS = {"railing", "mezzanine", "flight", "gate_double", "gate_single",
               "security_door", "caged_ladder", "support_frame",
               "racking_bay", "canopy", "floor_plate_area"}

REQUIRED_FIELDS = ("description", "quantity", "material_finish")
OPTIONAL_FIELDS = ("site", "required_raw")
ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS

SYSTEM_PROMPT = """You are Ousus's friendly intake assistant. Collect these \
fields from the client one at a time:
- description: what to build + key dimensions/size
- quantity: how many units
- material_finish: material + finish (suggest default if unsure)
- site: delivery/installation location
- required_raw: deadline phrase (optional)

RULES:
- Ask ONE missing field per message.
- If answer contains multiple fields, accept them ALL silently.
- Never invent values. Never compute prices/dates.
- When nothing is MISSING, summarise and ask to confirm.
- Only set complete=true AFTER client confirms.

OUTPUT raw JSON only:
{"reply":"...","complete":false,"data":{...known fields...}}
{"reply":"...","complete":true,"data":{"description":"...","quantity":1,\
"material_finish":"...","site":"...","required_raw":"..."}}"""


class MessageIn(BaseModel):
    text: str


def _history(db: Session, cs) -> str:
    msgs = db.scalars(
        select(ChatMessage).where(ChatMessage.session_id == cs.id)
        .order_by(ChatMessage.id)).all()
    return "\n".join(f"{m.role.upper()}: {m.content}" for m in msgs[-8:])


def _merge_fields(stored: dict, data: dict | None) -> dict:
    fields = dict((stored or {}).get("fields") or {})
    for k, v in (data or {}).items():
        if v not in (None, ""):
            fields[k] = str(v).strip()
    return fields


def _context(fields: dict, photo: str | None) -> str:
    known = dict(fields)
    if known.get("description") and not known.get("name"):
        words = known["description"].split()
        known["name"] = " ".join(words[:5]).strip(" ,.-").title()
    missing = [k for k in REQUIRED_FIELDS if k not in known]
    lines = [f"KNOWN: {json.dumps(known, ensure_ascii=False)}",
             f"MISSING: {missing or 'nothing — summarise & confirm'}"]
    if photo:
        lines.append("A reference photo was attached.")
    return "\n".join(lines)


@router.post("/start")
def start_chat(user: User = Depends(get_current_user),
               session: Session = Depends(get_session)):
    if not user.account_id:
        raise HTTPException(403, "client accounts only")

    cs = ChatSession(account_id=user.account_id, user_id=user.id,
                     purpose="spec_intake", collected_json={"fields": {}},
                     status="active")
    session.add(cs)
    session.flush()

    greeting = ("Hi! I'm the Ousus assistant. Tell me what you'd "
                "like us to build.")
    llm_ok = bool(configured_chain())
    if llm_ok:
        try:
            cl = LLMClient()
            resp = cl.complete("The client just opened the chat.")
            if resp:
                d = extract_json(resp.content) or {}
                greeting = d.get("reply") or greeting
        except Exception:
            pass

    session.add(ChatMessage(session_id=cs.id, role="assistant", content=greeting))
    session.commit()
    return {"session_id": cs.id, "reply": greeting, "llm": llm_ok}


class PhotoIn(BaseModel):
    url: str


@router.post("/{session_id}/photo")
def attach_photo(session_id: int, body: PhotoIn,
                 user: User = Depends(get_current_user),
                 session: Session = Depends(get_session)):
    cs = session.get(ChatSession, session_id)
    if not cs or cs.user_id != user.id:
        raise HTTPException(404, "chat session not found")
    if not body.url.startswith("/uploads/"):
        raise HTTPException(422, "invalid upload URL")
    stored = dict(cs.collected_json or {})
    stored["photo"] = body.url
    cs.collected_json = stored
    session.commit()
    return {"ok": True}


def _create_custom_spec(session: Session, cs, user: User, fields: dict,
                        photo: str | None) -> dict:
    """Create the spec from fully-collected chat fields."""
    code = next_spec_code(session)
    name = fields.get("name") or fields.get("description", "")[:60].title()
    desc = fields.get("description", "")
    material = fields.get("material_finish") or ""
    structured = {
        "items": [],
        "custom": [{"name": name, "description": desc,
                     "photo": photo or "", "quantity": fields.get("quantity", 1),
                     "material_finish": material}],
        "finish": material,
        "site": fields.get("site") or "",
        "required_raw": fields.get("required_raw") or "",
    }
    spec = Spec(
        code=code, account_id=user.account_id,
        title=name[:200], raw_text=f"Custom: {desc}",
        structured_json=structured,
        source="chat_intake", status="pending_review",
    )
    session.add(spec)
    cs.status = "submitted"
    cs.collected_json = {"fields": fields, "photo": photo}
    session.commit()
    return {"code": code, "status": spec.status}


@router.post("/{session_id}/message")
def chat_message(session_id: int, body: MessageIn,
                 user: User = Depends(get_current_user),
                 session: Session = Depends(get_session)):
    cs = session.get(ChatSession, session_id)
    if not cs or cs.user_id != user.id:
        raise HTTPException(404, "chat session not found")
    if cs.status != "active":
        raise HTTPException(409, "request already submitted")
    session.add(ChatMessage(session_id=cs.id, role="client",
                            content=body.text))

    stored = dict(cs.collected_json or {})
    fields = _merge_fields(stored, stored.get("pending_data"))

    # try LLM first
    if configured_chain():
        prompt = (_history(session, cs) +
                  f"\nCLIENT: {body.text}" +
                  "\n\nSERVER CONTEXT:\n" +
                  _context(fields, stored.get("photo")))
        resp = LLMClient().complete(prompt, SYSTEM_PROMPT)
        if resp:
            data = extract_json(resp.content)
            if data and data.get("reply"):
                # merge model-extracted fields
                new_fields = _merge_fields(fields, data.get("data"))
                missing = [f for f in REQUIRED_FIELDS if f not in new_fields]
                if data.get("complete") and not missing:
                    result = _create_custom_spec(session, cs, user,
                                                 new_fields,
                                                 stored.get("photo"))
                    return {**result, "llm": True}
                session.add(ChatMessage(session_id=cs.id,
                                        role="assistant",
                                        content=data["reply"]))
                cs.collected_json = {"fields": new_fields}
                session.commit()
                return {"llm": True, "complete": False,
                        "reply": data["reply"]}

    # all providers failed -> deterministic guided interview
    stored["guided"] = True
    cs.collected_json = stored
    session.commit()
    result = guided_turn(session, cs, user, stored, fields, body.text)
    result["guided"] = True
    return result


def next_spec_code(session: Session) -> str:
    codes = session.scalars(select(Spec.code)).all()
    nums = [int(m.group(1)) for c in codes if (m := re.match(r"J-(\d+)", c))]
    return f"J-{max(nums, default=0) + 1:03d}"


@router.get("/sessions/mine")
def my_sessions(user: User = Depends(get_current_user),
                session: Session = Depends(get_session)):
    sessions = session.scalars(
        select(ChatSession).where(ChatSession.user_id == user.id)
        .order_by(ChatSession.id.desc())).all()
    return [{"id": s.id, "status": s.status} for s in sessions]


@router.post("/{session_id}/guided-switch")
def switch_to_guided(session_id: int,
                     user: User = Depends(get_current_user),
                     session: Session = Depends(get_session)):
    cs = session.get(ChatSession, session_id)
    if not cs or cs.user_id != user.id:
        raise HTTPException(404, "chat session not found")
    stored = dict(cs.collected_json or {})
    stored["guided"] = True
    cs.collected_json = stored
    session.commit()
    return guided_turn(session, cs, user, stored, {},
                       stored.get("pending_text", ""))
