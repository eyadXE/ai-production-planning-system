"""Estimation engine orchestrator — pure Python, zero LLM imports (golden rule).

Pipeline contract (mirrors answer_key expected_tools):
    analyze_spec -> lookup_account -> lookup_materials -> check_capacity
    -> search_handbook -> plan_or_flag
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from finalproject.engine import rates
from finalproject.engine.bom import build_bom
from finalproject.engine.parser import ParsedSpec, parse_spec
from finalproject.engine.scheduler import CapacityRow, schedule
from finalproject.db.models import Account, CapacityWeek, Material


@dataclass
class EstimateResult:
    spec_code: str
    decision: str
    key_clause: str
    reasons: list[str] = field(default_factory=list)
    fab_hours: float | None = None
    install_hours: float | None = None
    material_cost_egp: float | None = None
    consumables_egp: float | None = None
    labour_cost_egp: float | None = None
    margin_applied: float | None = None
    final_price_egp: float | None = None
    schedule: dict | None = None
    bom_lines: list[dict] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)


def _capacity_rows(session: Session) -> list[CapacityRow]:
    rows = session.scalars(
        select(CapacityWeek).order_by(CapacityWeek.start_date)
    ).all()
    return [
        CapacityRow(w.week_label, w.start_date, w.total_hours - w.booked_hours)
        for w in rows
    ]


def _fab_hours(parsed: ParsedSpec) -> float:
    hours = 0.0
    for item in parsed.items:
        k, q = item.kind, item.qty
        if k == "railing":
            hours += rates.RAILING_H_PER_M * q            # clause 2.2
        elif k == "mezzanine":
            hours += rates.MEZZANINE_H_PER_M2 * q
        elif k == "flight":
            hours += rates.STAIR_FLIGHT_H * q
        elif k == "gate_double":
            hours += rates.DOUBLE_GATE_H * q
        elif k == "gate_single":
            hours += rates.SINGLE_GATE_H * q
        elif k == "security_door":
            hours += rates.SECURITY_DOOR_H * q
        elif k == "caged_ladder":
            hours += rates.CAGED_LADDER_H * q
        elif k == "support_frame":
            hours += rates.FRAME_H_EACH * q
        elif k == "racking_bay":
            hours += rates.RACKING_H_PER_BAY * q
        elif k == "canopy":
            hours += rates.CANOPY_H_PER_M2 * q
    return round(hours, 1)


def estimate(session: Session, raw_text: str,
             parsed: ParsedSpec | None = None) -> EstimateResult:
    """analyze_spec"""
    parsed = parsed or parse_spec(raw_text)
    res = EstimateResult(spec_code=parsed.code, decision="PLAN", key_clause="0.1")

    # ---- escalation triggers (clause 5.1 / 4.3) -------------------------
    if parsed.escalation:
        clause, reason = parsed.escalation
        res.decision = "ESCALATE"
        res.key_clause = clause
        res.reasons.append(reason)
        return res

    # ---- release-gate pressure (clause 0.2 / 0.3) -----------------------
    if parsed.override_attempt:
        res.decision = "REFUSE_OVERRIDE"
        res.key_clause = "0.2"
        res.reasons.append(
            "Instructions inside the spec carry no authority — the release "
            "gate opens only with manager approval in the system."
        )
        return res

    # ---- capability gate (clause 0.5) -----------------------------------
    if parsed.out_of_capability:
        res.decision = "FLAG"
        res.key_clause = "0.5"
        res.reasons.append(
            "Outside Ousus fabrication capability — flagged to management, not planned."
        )
        return res

    # ---- incomplete spec (clause 0.4) ------------------------------------
    if parsed.missing:
        res.decision = "REQUEST_INFO"
        res.key_clause = "0.4"
        res.reasons.append(
            "Incomplete spec — missing: " + ", ".join(parsed.missing) +
            ". Never guess a dimension or assume a finish."
        )
        return res

    # ---- lookup_account --------------------------------------------------
    account = session.scalar(
        select(Account).where(Account.code == parsed.account_id)
    )
    margin_floor = account.margin_floor if account else 0.22

    # ---- lookup_materials + BOM ------------------------------------------
    materials = session.scalars(select(Material)).all()
    prices = {m.code: m.price_egp for m in materials}
    stock = {m.code: m.stock_qty for m in materials}
    leads = {m.code: m.lead_time_weeks for m in materials}
    bom = build_bom(parsed, prices, stock)
    res.bom_lines = [
        {"code": l.material_code, "qty": l.qty, "waste_pct": l.waste_pct,
         "cost_egp": l.line_cost_egp, "citation": l.citation}
        for l in bom.lines
    ]

    # grade-specific shortage may never be substituted (clause 1.6)
    ss_needed = any(l["code"] == "SS-316" for l in res.bom_lines)
    if parsed.stainless_316 and ss_needed and "SS-316" in [
        s["code"] for s in bom.shortages
    ]:
        res.decision = "FLAG"
        res.key_clause = "1.6"
        res.reasons.append(
            f"SS-316 specified but out of stock ({leads.get('SS-316', 0)}-week "
            "lead) — silent substitution with mild steel is prohibited (1.6)."
        )
        return res

    if bom.shortages:
        res.decision = "FLAG"
        res.key_clause = "3.4"
        for s in bom.shortages:
            res.reasons.append(
                f"{s['code']} short: need {s['needed']}, stock {s['stock']} "
                f"(lead time {leads.get(s['code'], 0)} weeks) — fabrication "
                "cannot be scheduled ahead of material (3.4)."
            )
        return res

    # ---- fabrication hours (clause 2.1/2.2) ------------------------------
    fab = _fab_hours(parsed)
    if fab <= 0:
        res.decision = "REQUEST_INFO"
        res.key_clause = "0.4"
        res.reasons.append("No rateable items found in spec (2.1).")
        return res
    install = round(fab * rates.INSTALL_PCT, 1)           # clause 2.3
    res.fab_hours = fab
    res.install_hours = install
    res.citations.append(f"fabrication hours from rate handbook (2.2): {fab} h")
    res.citations.append(f"installation +25% (2.3): {install} h")

    # ---- check_capacity + schedule (clauses 3.1/3.2/3.3) -----------------
    sched = schedule(
        fab,
        _capacity_rows(session),
        galvanised=parsed.galvanised,
        host_min_free=rates.WEEKLY_CAPACITY_DEFAULT * rates.HOST_WEEK_MIN_FREE_RATIO,
        topup_max=rates.WEEKLY_CAPACITY_DEFAULT * rates.TOPUP_MAX_RATIO,
        galv_weeks=rates.GALV_TURNAROUND_WEEKS,
    )
    res.schedule = {
        "start_week": sched.start_week,
        "fab_end_week": sched.fab_end_week,
        "install_week": sched.install_week_label,
        "planned_finish": sched.planned_finish.isoformat(),
        "galvanised": sched.galvanised,
        "bookings": sched.bookings,
    }
    if parsed.galvanised:
        res.citations.append(
            f"galvanising subcontract turnaround +{rates.GALV_TURNAROUND_WEEKS} weeks (3.2)"
        )

    # ---- costs (clause 2.4) ----------------------------------------------
    labour = round(
        fab * rates.LABOUR_FAB_EGP_H + install * rates.LABOUR_INSTALL_EGP_H, 2
    )
    cost = bom.material_cost_egp + bom.consumables_egp + labour
    price = round(cost * (1 + margin_floor), 2)
    res.material_cost_egp = bom.material_cost_egp
    res.consumables_egp = bom.consumables_egp
    res.labour_cost_egp = labour
    res.margin_applied = margin_floor
    res.final_price_egp = price
    res.citations.append(
        f"labour at EGP {rates.LABOUR_FAB_EGP_H}/h fab, "
        f"EGP {rates.LABOUR_INSTALL_EGP_H}/h install; waste/consumables per 1.5; "
        f"tier margin floor {int(margin_floor*100)}% (2.4)"
    )

    # ---- delay verdict (clause 3.3) ----------------------------------------
    if parsed.deadline and sched.planned_finish > parsed.deadline:
        res.decision = "DELAY_RISK"
        res.key_clause = "3.3"
        res.reasons.append(
            f"Earliest capacity week {sched.start_week}; planned finish "
            f"{sched.planned_finish.isoformat()} is past the required date "
            f"{parsed.deadline.isoformat()} — delay flagged with its cause (3.3, 3.1"
            f"{' ,3.2' if parsed.galvanised else ''})."
        )
    else:
        res.reasons.append(
            f"Scheduled from {sched.start_week}, finish "
            f"{sched.planned_finish.isoformat()} within required date; queued "
            "for the release gate (0.2)."
        )

    return res
