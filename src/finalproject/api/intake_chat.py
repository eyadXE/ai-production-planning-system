"""Conversational custom-work intake — LLM conducts the interview.

When complete, returns collected fields to the frontend for cart storage.
The client keeps shopping and submits everything at checkout.
Falls back to deterministic guided interview when all providers fail.
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
from finalproject.db.database import get_session
from finalproject.api.intake_guided import guided_turn
from finalproject.db.models import ChatMessage, ChatSession, User
from finalproject.llm.base import configured_chain
from finalproject.llm.client import LLMClient, extract_json

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/intake", tags=["intake"])

REQUIRED_FIELDS = ("description", "quantity", "material_finish")
OPTIONAL_FIELDS = ("site", "required_raw")
ALL_FIELDS = REQUIRED_FIELDS + OPTIONAL_FIELDS

SYSTEM_PROMPT = """You are Ousus's friendly intake assistant. Collect these \
fields from the client one at a time:
- description: what to build + key dimensions/size
- quantity: how many units
- material_finish: material + finish (suggest default if unsure)
- site: delivery/installation location
- required_raw: deadline phrase

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
        words = str(known["description"]).split()
        known["name"] = " ".join(words[:5]).strip(" ,.-").title()
    missing = [k for k in ("description", "quantity", "material_finish")
               if k not in known]
    lines = [f"KNOWN: {json.dumps(known, ensure_ascii=False)}",
             f"MISSING: {missing or 'nothing'}"]
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
    if configured_chain():
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
    return {"session_id": cs.id, "reply": greeting, "llm": bool(configured_chain())}


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


@router.post("/{session_id}/message")
def chat_message(session_id: int, body: MessageIn,
                 user: User = Depends(get_current_user),
                 session: Session = Depends(get_session)):
    """Chat with assistant. When complete, returns collected custom_line
    for the frontend to add to localStorage cart — does NOT submit.

    Never raises 500 for provider/internal failures: falls back to the
    deterministic guided interview and always returns valid JSON."""
    cs = session.get(ChatSession, session_id)
    if not cs or cs.user_id != user.id:
        raise HTTPException(404, "chat session not found")
    if cs.status != "active":
        raise HTTPException(409, "request already submitted")
    try:
        return _chat_turn(session, cs, user, body.text)
    except Exception as exc:  # noqa: BLE001 — chat must never 500
        logger.warning("chat turn failed (%s): %s", type(exc).__name__, exc)
        session.rollback()
        cs = session.get(ChatSession, session_id)
        if not cs or cs.status != "active":
            raise HTTPException(409, "chat session is no longer active")
        try:
            stored = dict(cs.collected_json or {})
            stored["guided"] = True
            cs.collected_json = stored
            session.commit()
            fields = _merge_fields(stored, stored.get("pending_data"))
            result = guided_turn(session, cs, user, stored, fields, body.text)
            result["guided"] = True
            result.setdefault("reply",
                              "Sorry, something glitched on our side — "
                              "let's continue here. What would you like "
                              "us to build?")
            return result
        except Exception:  # noqa: BLE001 — absolute last resort
            logger.exception("guided fallback also failed")
            session.rollback()
            reply = ("I'm having trouble right now — please try again in "
                     "a moment, or use the guided request form.")
            session.add(ChatMessage(session_id=session_id,
                                    role="assistant", content=reply))
            session.commit()
            return {"llm": False, "guided": True, "complete": False,
                    "reply": reply}


def _chat_turn(session: Session, cs: ChatSession, user: User,
               text: str) -> dict:
    session.add(ChatMessage(session_id=cs.id, role="client", content=text))

    stored = dict(cs.collected_json or {})
    fields = _merge_fields(stored, stored.get("pending_data"))

    # try LLM
    if configured_chain():
        prompt = (_history(session, cs) +
                  f"\nCLIENT: {text}" +
                  "\n\nSERVER CONTEXT:\n" +
                  _context(fields, stored.get("photo")))
        resp = LLMClient().complete(prompt, SYSTEM_PROMPT)
        if resp:
            data = extract_json(resp.content)
            if data and data.get("reply"):
                new_fields = _merge_fields(fields, data.get("data"))
                missing = [f for f in REQUIRED_FIELDS if f not in new_fields]
                if data.get("complete") and not missing:
                    # return collected fields — frontend adds to cart
                    cs.status = "collected"
                    cs.collected_json = {"fields": new_fields,
                                         "photo": stored.get("photo", "")}
                    session.commit()
                    return {"llm": True, "complete": True,
                            "custom_line": {
                                "name": new_fields.get("name",
                                    new_fields["description"][:60].title()),
                                "description":
                                    new_fields.get("description", ""),
                                "photo": stored.get("photo", ""),
                                "quantity": _safe_quantity(
                                    new_fields.get("quantity", 1)),
                                "material_finish": new_fields.get(
                                    "material_finish", ""),
                            },
                            "reply": data["reply"]}
                session.add(ChatMessage(session_id=cs.id,
                                        role="assistant",
                                        content=data["reply"]))
                cs.collected_json = {"fields": new_fields}
                session.commit()
                return {"llm": True, "complete": False,
                        "reply": data["reply"]}

    # all providers failed -> guided fallback
    stored["guided"] = True
    cs.collected_json = stored
    session.commit()
    result = guided_turn(session, cs, user, stored, fields, text)
    result["guided"] = True
    return result


def _safe_quantity(value) -> float:
    try:
        q = float(value)
        return q if q > 0 else 1.0
    except (TypeError, ValueError):
        return 1.0


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
