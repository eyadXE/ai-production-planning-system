"""Deterministic spec parser: free text -> structured fields.

The LLM layer later replaces/augments this for messy client chat input, but
the golden pipeline stays hermetic: same text in, same structure out.
"""

import re
from dataclasses import dataclass, field
from datetime import date, timedelta

WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

MISSING_MARKERS = (
    "to be confirmed", "tbc", "unknown", "similar to last time",
    "unstated", "survey pending", "not stated",
)

CAPABILITY_EXCLUSIONS = (
    "aluminium", "curtain wall", "pressure vessel", "cast work",
)

ESCALATION_PATTERNS = (
    (r"skip[^.]*(inspection)|without the weld inspection|(skip|fake|pre-sign)[^.]*(inspection)", "4.3",
     "Request to bypass quality inspection — inspection is never skipped."),
    (r"issue the galvanising certificate|galvanising certificate now", "5.1",
     "Request to issue a galvanising certificate without galvanising — altered certificates are escalated."),
    (r"method statement", "5.1",
     "Installation over an occupied/live site without a method statement."),
    (r"(remov\w*|eliminat\w*)[^.]*(column|support|beam)|no revised engineer drawings|structural change", "5.1",
     "Structural/load-bearing change without engineer-approved drawings."),
)

OVERRIDE_PATTERNS = (
    r"skip (the )?(manager|sign-off|approval)",
    r"mark (the plan |it )?approved",
    r"approved by phone",
    r"release .{0,30}(today|now)",
    r"order (all )?(the )?steel now",
    r"start fabrication tomorrow",
)


@dataclass
class Item:
    kind: str                 # railing | mezzanine | flight | gate_double | ...
    qty: float = 1.0          # count, metres or m2 depending on kind
    note: str = ""


@dataclass
class ParsedSpec:
    code: str
    account_id: str
    title: str
    spec_date: date | None
    items: list[Item] = field(default_factory=list)
    finish: str = ""
    site: str = ""
    deadline: date | None = None            # binding required-by date
    missing: list[str] = field(default_factory=list)
    out_of_capability: bool = False
    override_attempt: bool = False
    escalation: tuple[str, str] | None = None   # (clause, reason)
    stainless_316: bool = False
    galvanised: bool = False


def _word_or_int(m: re.Match) -> int:
    token = m.group(1).lower()
    if token in WORD_NUMBERS:
        return WORD_NUMBERS[token]
    return int(token)


def parse_deadline(text: str, spec_date: date | None) -> date | None:
    candidates: list[date] = []
    for m in re.finditer(r"within\s+(\d+)\s*weeks?|(?:required|finishe?d?)?:?\s*(\d+)\s*weeks?\b", text, re.I):
        n = int(m.group(1) or m.group(2))
        if spec_date and n:
            candidates.append(spec_date + timedelta(weeks=n))
    for m in re.finditer(r"end of week W(\d\d)|by end W(\d\d)", text, re.I):
        week = int(m.group(1) or m.group(2))
        try:
            sunday = date.fromisocalendar(spec_date.year if spec_date else 2026, week, 7)
        except ValueError:
            continue
        candidates.append(sunday)
    if re.search(r"\bimmediate\b|\bASAP\b", text, re.I):
        candidates.append(spec_date or date.today())
    return min(candidates) if candidates else None


def _items_block(text: str) -> str:
    """Only the Items: section — titles/sites must not create line items."""
    m = re.search(r"^Items:\s*(.*?)(?=^\w[\w ]*:|\Z)", text, re.M | re.S)
    return m.group(1) if m else text


def _parse_items(text: str) -> list[Item]:
    items: list[Item] = []
    text = _items_block(text)

    # mezzanine / deck / storage platform areas
    for m in re.finditer(
        r"(mezzanine|deck|storage platform)[^.]*?(\d+(?:\.\d+)?)\s*m(?:2|²)|"
        r"(\d+(?:\.\d+)?)\s*m(?:2|²)[^.]*?(mezzanine|deck)",
        text, re.I,
    ):
        area = float(m.group(2) or m.group(3))
        items.append(Item("mezzanine", area))
        low = m.group(0).lower()
        if "no railing" in low or "against walls" in low:
            pass  # explicit exclusion handled by not adding a railing item

    # edge/with railings attached to other items, and standalone runs
    for m in re.finditer(
        r"(\d+(?:\.\d+)?)\s*m\b(?![a-z])[^.]{0,40}?"
        r"(railing|balustrade|guard rail)|(railing|balustrade|guard rail)[^.]{0,40}?"
        r"(\d+(?:\.\d+)?)\s*m\b(?![a-z])",
        text, re.I,
    ):
        meters = float(m.group(1) or m.group(4))
        snippet = text[max(0, m.start() - 60): m.end()].lower()
        if "edge" in snippet or True:
            items.append(Item("railing", meters))

    # staircase flights
    for m in re.finditer(r"(one|two|three|\d+)\s+straight\s+flights?", text, re.I):
        items.append(Item("flight", _word_or_int(m)))

    # gates (double / single)
    for m in re.finditer(r"(two|three|\d+)?\s*(double)[^.]*?\bgates?\b|"
                         r"\b(double gates?)\b", text, re.I):
        n = _word_or_int(m) if m.group(1) else 1
        items.append(Item("gate_double", n))
    for m in re.finditer(r"(one|two|three|\d+)\s+single[^.]*?\bgate", text, re.I):
        items.append(Item("gate_single", _word_or_int(m)))

    # security doors
    for m in re.finditer(r"(one|two|three|four|five|six|\d+)\s+single\s+security\s+doors?",
                         text, re.I):
        items.append(Item("security_door", _word_or_int(m)))

    # caged ladders
    for m in re.finditer(r"(one|two|three|four|\d+)\s+caged\s+access\s+ladders?", text, re.I):
        items.append(Item("caged_ladder", _word_or_int(m)))

    # support frames
    for m in re.finditer(r"(one|two|three|four|five|\d+)\s+support\s+frames?", text, re.I):
        items.append(Item("support_frame", _word_or_int(m)))

    # racking bays
    for m in re.finditer(r"(\d+)\s+bays?\b", text, re.I):
        items.append(Item("racking_bay", int(m.group(1))))

    # canopies
    for m in re.finditer(r"canopy\s+(\d+(?:\.\d+)?)\s*m(?:2|²)|"
                         r"canopy[^.]*?(\d+(?:\.\d+)?)\s*m(?:2|²)", text, re.I):
        items.append(Item("canopy", float(m.group(1) or m.group(2))))

    # floor plates (material-only job; no fabrication rate applies)
    if re.search(r"floor plates", text, re.I):
        m = re.search(r"over\s+(\d+)\s*m2", text, re.I)
        if m:
            items.append(Item("floor_plate_area", float(m.group(1))))

    return items


def parse_spec(raw_text: str) -> ParsedSpec:
    text = raw_text.strip()
    low = text.lower()

    code_m = re.search(r"Project ID:\s*(\S+)", text)
    acc_m = re.search(r"Client account:\s*(AC-\d+)", text)
    title_m = re.search(r"Title:\s*(.+)", text)
    date_m = re.search(r"Date:\s*(\d{4}-\d{2}-\d{2})", text)
    finish_m = re.search(r"Finish:\s*(.+)", text)
    site_m = re.search(r"Site:\s*(.+)", text)

    spec_date = date.fromisoformat(date_m.group(1)) if date_m else None
    finish = finish_m.group(1).strip() if finish_m else ""
    site = site_m.group(1).strip() if site_m else ""

    parsed = ParsedSpec(
        code=code_m.group(1) if code_m else "J-???",
        account_id=acc_m.group(1) if acc_m else "",
        title=title_m.group(1).strip() if title_m else "",
        spec_date=spec_date,
        items=_parse_items(text),
        finish=finish,
        site=site,
        deadline=parse_deadline(text, spec_date),
        stainless_316="ss-316" in low or "stainless" in low,
        galvanised="galv" in low,
    )

    # escalation triggers first (clause 5.1 / 4.3)
    for pattern, clause, reason in ESCALATION_PATTERNS:
        if re.search(pattern, low):
            parsed.escalation = (clause, reason)
            break

    # release-gate pressure (clause 0.2 / 0.3)
    parsed.override_attempt = any(
        re.search(p, low) for p in OVERRIDE_PATTERNS
    )

    parsed.out_of_capability = any(k in low for k in CAPABILITY_EXCLUSIONS)

    # incomplete-spec detection (clause 0.4)
    items_blob = " ".join(
        line for line in text.splitlines() if line.lower().startswith("items")
    ).lower()
    if any(marker in items_blob for marker in MISSING_MARKERS):
        parsed.missing.append("item dimensions/quantities")
    if not finish or any(marker in finish.lower() for marker in MISSING_MARKERS):
        normalized = finish.lower().strip(" .")
        if normalized != "none":
            parsed.missing.append("finish")
    if parsed.deadline is None and not parsed.override_attempt:
        parsed.missing.append("required date")

    return parsed
