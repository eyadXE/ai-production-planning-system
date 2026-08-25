"""Conversational custom-work intake — LLM conducts the interview.

The server owns the collected-state: after every turn it merges whatever the
model extracted into `collected_json.fields`, and the next prompt states
explicitly what is KNOWN vs MISSING so the model can never re-ask.
Minimum schema to submit: name, description (with size), quantity,
material_finish. Site / deadline asked once but optional.
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
from finalproject.auth.service import VALID_ROLES  # noqa
from finalproject.api.intake_routes import next_spec_code
from finalproject.db.models import ChatMessage, ChatSession, Spec, User
from finalproject.llm.base import configured_chain
from finalproject.llm.client import LLMClient, extract_json

router = APIRouter(prefix="/intake", tags=["intake"])

FIELD_ORDER = [
    ("description", "what it is + key dimensions/size"),
    ("quantity", "how many units"),
    ("material_finish", "material and finish"),
    ("quantity", "how many units"),
    ("material_finish", "material and finish (suggest a default if unsure)"),
    ("site", "delivery/installation location"),
    ("required_raw", "deadline phrase (optional — we estimate completion ourselves)"),
]
REQUIRED = {"description", "quantity", "material_finish"}

SYSTEM_PROMPT = """You are the friendly custom-work assistant for Ousus, a \
steel fabrication company. The client wants something CUSTOM built. Your job \
is to collect the missing fields listed in the CONTEXT the server gives you \
each turn.

HARD RULES
- NEVER ask about a field already present under KNOWN. Not to confirm it, \
not to rephrase it. Once is enough.
- Ask about exactly ONE missing field per message (follow the MISSING order).
- If the client's answer contains several answers, accept them all silently.
- If an answer is vague, ask one concrete clarifying question about it.
- Never invent values. Never compute prices or dates. We estimate completion \
ourselves — if the client has no deadline, say that's fine.
- When nothing is MISSING, summarise all fields briefly and ask the client \
to confirm. Only set complete=true AFTER they confirm.

OUTPUT — raw JSON only. IMPORTANT: "data" must contain ALL fields known so far on EVERY turn (not just new ones):
{"reply": "...", "complete": false, "data": {"name":"..."}} or
{"reply":"...","complete":false,"data":{"name":"...","description":"...","quantity":2}}
or on confirmed submission:
{"reply": "...", "complete": true, "data": {"name":"...","description":"...",
"quantity":1,"material_finish":"...","site":"...","required_raw":"..."}}"""


class MessageIn(BaseModel):
    text: str


def _history(session_db: Session, cs: ChatSession) -> str:
    msgs = session_db.scalars(
        select(ChatMessage).where(ChatMessage.session_id == cs.id)
        .order_by(ChatMessage.id)
    ).all()
    return "\n".join(f"{m.role.upper()}: {m.content}" for m in msgs[-8:])


def _merge_fields(stored: dict, data: dict | None) -> dict:
    fields = dict((stored or {}).get("fields") or {})
    for key, _ in FIELD_ORDER:
        value = (data or {}).get(key)
        if value not in (None, ""):
            fields[key] = value
    return fields


def _context(fields: dict, photo: str | None) -> str:
    known = {k: v for k, v in fields.items()}
    if known.get("description") and not known.get("name"):
        words = str(known["description"]).split()
        known["name"] = " ".join(words[:5]).strip(" ,.-").title()
    missing = [label for key, label in FIELD_ORDER if key not in known]
    lines = [f"KNOWN: {json.dumps(known, ensure_ascii=False)}",
             f"MISSING: {missing or 'nothing — summarise & confirm'}"]
    if photo:
        lines.append("A reference photo was attached by the client.")
    return "\n".join(lines)


@router.post("/start")
def start(user: User = Depends(get_current_user),
          session: Session = Depends(get_session)):
    if not user.account_id:
        raise HTTPException(403, "client accounts only")
    if not configured_chain():
        return {"session_id": None, "reply": None, "llm": False}

    cs = ChatSession(account_id=user.account_id, user_id=user.id,
                     purpose="spec_intake", collected_json={"fields": {}},
                     status="active")
    session.add(cs)
    session.flush()

    client = LLMClient()
    context = _context({}, None)
    resp = client.complete(
        context + "\n\nThe client just opened the chat. Greet them warmly and "
        "ask what they would like us to build.")
    if resp is None:
        session.rollback()
        return {"session_id": None, "reply": None, "llm": False}
    data = extract_json(resp.content) or {}
    reply = data.get("reply") or (
        "Hi! I'm the Ousus assistant. Tell me what you'd like us to build.")
    session.add(ChatMessage(session_id=cs.id, role="assistant", content=reply))
    session.commit()
    return {"session_id": cs.id, "reply": reply, "llm": True}


def _heuristic_fill(session: Session, cs: ChatSession, fields: dict,
                    extra_text: str = "") -> None:
    """Safety net: pull required fields straight from the client's own words
    so completion never depends on the model restating them."""
    msgs = session.scalars(
        select(ChatMessage).where(ChatMessage.session_id == cs.id,
                                  ChatMessage.role == "client")
        .order_by(ChatMessage.id)
    ).all()
    contents = [m.content for m in msgs]
    if extra_text:
        contents.append(extra_text)
    blob = " ".join(contents)
    low = blob.lower()

    if not fields.get("description") and contents and max(
            (len(c) for c in contents), default=0) > 10:
        fields["description"] = max(contents, key=len)[:300]
    if fields.get("description") and not fields.get("name"):
        words = str(fields["description"]).split()
        fields["name"] = " ".join(words[:5]).strip(" ,.-").title()

    if not str(fields.get("quantity") or "").strip():
        m = (re.search(r"(\d+(?:\.\d+)?)\s*(?:units?|pcs|pieces|pieces)", low)
             or re.search(r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\b\s*\w*\s*(?:units?|pcs|pieces)", low)
             or re.search(r"\b(?:quantity|qty)[:,]?\s*(\d+)", low))
        words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                 "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
        if not m:
            m2 = re.findall(r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten)\b", low)
            if m2:
                fields["quantity"] = float(words[m2[-1]])
        else:
            # do NOT auto-submit — hand the collected build back so the
            # client keeps shopping and submits everything at checkout
            cs.status = "collected"
            cs.collected_json = {"fields": fields,
                                 "photo": stored.get("photo", "")}
            session.add(ChatMessage(
                session_id=cs.id, role="assistant",
                content=f"Added '{fields['name']}' to your request."))
            session.commit()
            return {"llm": True, "complete": True,
                    "custom_line": {
                        "name": fields["name"],
                        "description": desc,
                        "photo": stored.get("photo", ""),
                        "quantity": qty if isinstance(qty, float) else 1,
                        "material_finish": material,
                    },
                    "reply": data["reply"]}

    session.add(ChatMessage(session_id=cs.id, role="assistant",
                            content=data.get("reply", "")))
    cs.collected_json = {"fields": fields, "photo": stored.get("photo", ""),
                         "pending_data": data.get("data")}
    session.commit()
    return {"llm": True, "complete": False,
                    "reply": data.get("reply") or "Could you confirm that once more?"}


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
        raise HTTPException(422, "invalid upload url")
    stored = dict(cs.collected_json or {})
    stored["photo"] = body.url
    cs.collected_json = stored
    session.commit()
    return {"ok": True}


@router.get("/sessions/mine")
def my_sessions(user: User = Depends(get_current_user),
                session: Session = Depends(get_session)):
    sessions = session.scalars(
        select(ChatSession).where(ChatSession.user_id == user.id)
        .order_by(ChatSession.id.desc())
    ).all()
    return [{"id": s.id, "status": s.status, "purpose": s.purpose}
            for s in sessions]


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
