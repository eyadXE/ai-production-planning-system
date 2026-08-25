"""Deterministic guided intake — same schema/state as the LLM agent, but
rule-driven so the feature cannot fail when every provider is down."""

import re

from sqlalchemy.orm import Session

from finalproject.api.intake_routes import next_spec_code
from finalproject.db.models import ChatMessage, Spec, User


def _submit_custom(session: Session, cs, user: User, fields: dict,
                   photo: str | None) -> dict:
    code = next_spec_code(session)
    material = fields.get("material_finish") or ""
    structured = {
        "items": [],
        "custom": [{
            "name": fields.get("name") or "Custom object",
            "description": fields.get("description", ""),
            "photo": photo or "",
            "quantity": fields.get("quantity", 1),
            "material_finish": material,
        }],
        "finish": material,
        "site": fields.get("site") or "",
        "required_raw": fields.get("required_raw") or "",
    }
    spec = Spec(
        code=code,
        account_id=user.account_id,
        title=str(fields.get("name") or "Custom request")[:200],
        raw_text=(
            f"Project ID: {code}\nTitle: {fields.get('name')}\nDate: auto\n\n"
            f"Items: custom — {fields.get('description', '')} "
            f"x{fields.get('quantity', 1)} ({material})\n"
            f"Site: {structured['site'] or 'unstated'}\n"
            f"Required: {structured['required_raw'] or 'no deadline given'}\n"
        ),
        structured_json=structured,
        source="chat_intake",
        status="pending_review",
    )
    session.add(spec)
    cs.status = "submitted"
    cs.collected_json = {"fields": fields, "photo": photo}
    session.add(ChatMessage(session_id=cs.id, role="assistant",
                            content=f"Submitted as request {spec.code}."))
    session.commit()
    return {"llm": False, "complete": True, "code": spec.code,
            "reply": f"Submitted as request {spec.code} — an engineer will review it."}


def guided_turn(session: Session, cs, user: User, stored: dict,
                fields: dict, text: str) -> dict:
    """One step of the rule-driven interview over the same schema."""
    text_l = text.strip()
    low = text_l.lower()
    order = ["description", "quantity", "material_finish",
             "site", "required_raw", "confirm"]
    step = stored.get("guided_step")
    if not step:
        # resume at the first field not already collected (mid-chat switch)
        step = next((s for s in order if not fields.get(s)), "confirm")

    def save(next_step=None):
        new_stored = dict(stored)
        new_stored["fields"] = fields
        if next_step:
            new_stored["guided_step"] = next_step
        cs.collected_json = new_stored
        session.commit()

    if step == "confirm":
        if low.startswith(("y", "ok", "sub", "go")):
            return _submit_custom(session, cs, user, fields,
                                  stored.get("photo"))
        save("description")
        return {"llm": False,
                "reply": ("No problem — describe again what you need built, "
                          "with sizes.")}

    if step == "description":
        if len(text_l) < 8:
            return {"llm": False,
                    "reply": "Please describe it a bit more (what it is + size)."}
        fields["description"] = text_l
        words = text_l.split()
        fields.setdefault("name",
                          " ".join(words[:5]).strip(" ,.-").title())
        save("quantity")
        return {"llm": False, "reply": "How many units do you need?"}

    if step == "quantity":
        m = re.search(
            r"\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten",
            text_l, re.I)
        if not m:
            return {"llm": False,
                    "reply": "Please enter a number (e.g. 2)."}
        token = m.group(0).lower()
        words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                 "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
        try:
            fields["quantity"] = float(words.get(token, token))
        except ValueError:
            return {"llm": False, "reply": "Please enter a number (e.g. 2)."}
        save("material_finish")
        return {"llm": False,
                "reply": ("Material & finish? e.g. 'mild steel painted RAL "
                          "7016' or 'galvanised'. Say 'default' for mild "
                          "steel shop-painted.")}

    if step == "material_finish":
        fields["material_finish"] = (
            "mild steel, shop painted" if low in ("default", "skip") else text_l)
        save("site")
        return {"llm": False,
                "reply": "Delivery/installation location? ('-' to skip)"}

    if step == "site":
        fields["site"] = "" if text_l == "-" else text_l
        save("required_raw")
        return {"llm": False,
                "reply": ("Deadline? e.g. 'within 6 weeks' — optional ('-' to "
                          "skip); we estimate completion ourselves anyway.")}

    if step == "required_raw":
        fields["required_raw"] = "" if text_l == "-" else text_l
        summary = (
            "Please confirm:\n"
            f"- Item: {fields.get('name')}\n"
            f"- Description: {fields.get('description')}\n"
            f"- Quantity: {fields.get('quantity')}\n"
            f"- Material & finish: {fields.get('material_finish')}\n"
            f"- Site: {fields.get('site') or '-'}\n"
            f"- Deadline: {fields.get('required_raw') or 'flexible'}\n"
            "Type YES to submit for engineering review."
        )
        save("confirm")
        return {"llm": False, "reply": summary}

    # unknown state -> restart interview
    save("description")
    return {"llm": False,
            "reply": "Let's start fresh: what would you like us to build?"}
