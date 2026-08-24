"""Bill-of-materials builder — quantities grounded in Section 1 clauses."""

import math
from dataclasses import dataclass, field

from finalproject.engine.parser import Item, ParsedSpec
from finalproject.engine.rates import (
    CONSUMABLES_PCT,
    WASTE_BARS_PCT,
    WASTE_SHEETS_PCT,
)

SHEET_AREA_M2 = 2.976  # 2440x1220 sheet


@dataclass
class BomLine:
    material_code: str
    qty: float
    waste_pct: float
    line_cost_egp: float
    citation: str


@dataclass
class BomResult:
    lines: list[BomLine] = field(default_factory=list)
    material_cost_egp: float = 0.0
    consumables_egp: float = 0.0
    shortages: list[dict] = field(default_factory=list)


def _add(lines: dict[str, float], code: str, qty: float) -> None:
    lines[code] = lines.get(code, 0.0) + qty


def _railing_bom(meters: float, raw: dict) -> None:
    """Clause 1.1 — per metre of run."""
    _add(raw, "SHS-50", math.ceil(meters / 1.2))       # posts: 1 per 1.2 m
    _add(raw, "SHS-50", 0.9 * meters / 10)             # top+mid rail continuous
    _add(raw, "FLT-40", 2 * meters / 10)               # flat-bar infill


def _mezzanine_bom(area_m2: float, raw: dict) -> None:
    """Clause 1.2 — per m2."""
    _add(raw, "RHS-100", 0.4 * area_m2)
    _add(raw, "SHS-50", 0.6 * area_m2)
    _add(raw, "CHQ-4", 0.45 * area_m2)


def _flight_bom(count: int, raw: dict) -> None:
    """Clause 1.3 — per straight flight."""
    _add(raw, "RHS-100", 2 * count)
    _add(raw, "CHQ-4", 16 * 0.25 * count)              # treads = quarter-sheets


# Clause 1.4 standard build-ups (documented platform configuration; the
# handbook defers these to the rate table's item standards).
STANDARD_BUILDUPS: dict[str, dict] = {
    "gate_double": {"SHS-50": 4, "MSH-A": 2},
    "gate_single": {"SHS-50": 2, "MSH-A": 1},
    "security_door": {"SHS-50": 2, "PLT-3": 0.5},
    "caged_ladder": {"SHS-50": 2, "FLT-40": 2},
    "support_frame": {"RHS-100": 4},
    "racking_bay": {"RHS-100": 1.5, "CHQ-4": 0.25},
}


def build_bom(parsed: ParsedSpec, prices: dict[str, float],
              stock: dict[str, float]) -> BomResult:
    result = BomResult()
    raw: dict[str, float] = {}
    sheet_codes = {"PLT-3", "PLT-5", "CHQ-4"}
    structural = "SS-316" if parsed.stainless_316 else "SHS-50"

    for item in parsed.items:
        if item.kind == "railing":
            _railing_bom(item.qty, raw)
        elif item.kind == "mezzanine":
            _mezzanine_bom(item.qty, raw)
        elif item.kind == "flight":
            _flight_bom(int(item.qty), raw)
        elif item.kind in STANDARD_BUILDUPS:
            for code, per in STANDARD_BUILDUPS[item.kind].items():
                _add(raw, code, per * item.qty)
        elif item.kind == "canopy":
            _add(raw, "RHS-100", 0.3 * item.qty)
            _add(raw, "PLT-3", item.qty / SHEET_AREA_M2 * 0.9)
        elif item.kind == "floor_plate_area":
            _add(raw, "PLT-5", item.qty / SHEET_AREA_M2)

    # clause 1.6 — the specified grade is the planned grade; no silent
    # substitution of stainless with mild steel (or vice versa).
    if structural == "SS-316" and "SHS-50" in raw:
        raw["SS-316"] = raw.pop("SHS-50")

    for code, qty in sorted(raw.items()):
        is_sheet = code in sheet_codes
        waste = WASTE_SHEETS_PCT if is_sheet else WASTE_BARS_PCT
        needed = qty * (1 + waste)
        price = prices.get(code, 0.0)
        result.lines.append(BomLine(code, round(needed, 3), waste,
                                    round(needed * price, 2),
                                    f"clause 1.5 waste {int(waste*100)}%"))
        result.material_cost_egp += needed * price

        # clause 3.4 — availability is verified against the base quantity;
        # the waste allowance is a procurement rounding, not extra demand.
        if stock.get(code, 0) < qty:
            result.shortages.append({
                "code": code, "needed": round(qty, 2),
                "stock": stock.get(code, 0),
            })

    result.material_cost_egp = round(result.material_cost_egp, 2)
    result.consumables_egp = round(result.material_cost_egp * CONSUMABLES_PCT, 2)
    return result
