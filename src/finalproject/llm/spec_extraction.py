"""Spec extraction: LLM fills the structure, rules keep the authority.

Merge policy:
- deterministic parse always runs on the raw text;
- a successful LLM extraction only replaces descriptive fields
  (items / finish / site / title / account / date phrase);
- safety classification (override pressure, escalation triggers,
  capability, missing-info) is ALWAYS recomputed from the raw text by
  the rule-based parser — an LLM can never talk its way past the gates.
"""

import json
import logging
from datetime import date

from finalproject.engine.parser import (
    MISSING_MARKERS,
    Item,
    ParsedSpec,
    parse_deadline,
    parse_spec,
)
from finalproject.llm.client import LLMClient

logger = logging.getLogger(__name__)

VALID_ITEM_KINDS = {
    "railing", "mezzanine", "flight", "gate_double", "gate_single",
    "security_door", "caged_ladder", "support_frame", "racking_bay",
    "canopy", "floor_plate_area",
}

_TEXT_FIELDS = ("finish", "site", "title", "account_id")


def _clean_items(raw_items) -> list[Item] | None:
    if not isinstance(raw_items, list):
        return None
    items: list[Item] = []
    for entry in raw_items:
        if not isinstance(entry, dict):
            continue
        kind = str(entry.get("kind", "")).strip().lower()
        qty = entry.get("qty")
        if kind not in VALID_ITEM_KINDS or not isinstance(qty, (int, float)):
            continue
        if qty <= 0:
            continue
        note = str(entry.get("note", ""))[:200]
        items.append(Item(kind, float(qty), note))
    return items or None


def _apply_llm_fields(base: ParsedSpec, data: dict) -> ParsedSpec:
    for field in _TEXT_FIELDS:
        value = data.get(field)
        if isinstance(value, str) and value.strip():
            setattr(base, field, value.strip())

    # date phrase -> deadline (never trust an LLM-computed date object)
    required_raw = data.get("required_raw")
    if isinstance(required_raw, str) and required_raw.strip() and base.spec_date:
        deadline = parse_deadline(required_raw, base.spec_date)
        if deadline:
            base.deadline = min(
                [d for d in (base.deadline, deadline) if d is not None]
            )

    items = _clean_items(data.get("items"))
    if items:
        base.items = items

    # recompute missing-info on the merged view (clause 0.4)
    missing: list[str] = []
    items_blob = " ".join(i.note.lower() for i in base.items)
    llm_items_blob = json.dumps(data.get("items") or [], ensure_ascii=False).lower()
    joined = " ".join([base.title.lower(), items_blob, llm_items_blob])
    if any(m in joined for m in MISSING_MARKERS):
        missing.append("item dimensions/quantities")
    finish_norm = base.finish.lower().strip(" .")
    if not finish_norm or any(m in finish_norm for m in MISSING_MARKERS):
        if finish_norm != "none":
            missing.append("finish")
    if base.deadline is None and not base.override_attempt:
        missing.append("required date")
    base.missing = missing
    return base


def extract_spec(raw_text: str, client: LLMClient | None = None) -> tuple[ParsedSpec, str]:
    """Returns (parsed_spec, source) where source is 'llm:<provider>' or 'rules'."""
    base = parse_spec(raw_text)
    client = client or LLMClient()
    data = client.extract_json(raw_text)
    if data is None:
        return base, "rules"
    try:
        merged = _apply_llm_fields(base, data)
        return merged, f"llm:{getattr(client, 'last_provider', 'llm')}"
    except Exception:  # noqa: BLE001 — malformed merges fall back to rules
        logger.exception("LLM merge failed; using deterministic parse")
        return base, "rules"
