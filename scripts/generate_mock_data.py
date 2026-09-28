"""Generator for OUSUS/Ousus_data/ — a synthetic demo dataset (the real
business data was never committed to this repo; see HOW_TO_RUN.md).

Run from the repo root:
    .venv/Scripts/python.exe scripts/generate_mock_data.py

capacity.json is anchored to "today" (2026-W40 at generation time), so the
daily-summary assertions in tests/test_tracking.py (fully_booked_weeks /
first_meaningful_free_week) are tied to this specific run. Regenerating on a
different date will shift the week labels and those two literals will need
updating to match.
"""
import json
from pathlib import Path

DATA = Path("OUSUS/Ousus_data")
(DATA / "specs").mkdir(parents=True, exist_ok=True)
(DATA / "handbook").mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- accounts
accounts = [
    {"account_id": "AC-01", "client": "Rowad Contracting", "tier": "retail", "margin_floor": 0.28},
    {"account_id": "AC-02", "client": "Delta Steel Works", "tier": "standard", "margin_floor": 0.22},
    {"account_id": "AC-03", "client": "Nile Construction Group", "tier": "key", "margin_floor": 0.18},
    {"account_id": "AC-04", "client": "Al-Fanar Developers", "tier": "standard", "margin_floor": 0.22},
    {"account_id": "AC-05", "client": "Cairo Industrial Partners", "tier": "retail", "margin_floor": 0.28},
    {"account_id": "AC-06", "client": "Zamalek Facilities Co", "tier": "key", "margin_floor": 0.18},
]
(DATA / "accounts.json").write_text(json.dumps(accounts, indent=1) + "\n")

# ---------------------------------------------------------------- materials
materials = [
    {"code": "SHS-50", "name": "Square Hollow Section 50x50x3mm", "unit": "bar", "price_egp": 180, "stock": 4000, "lead_time_weeks": 1},
    {"code": "FLT-40", "name": "Flat Bar 40x5mm", "unit": "bar", "price_egp": 95, "stock": 3000, "lead_time_weeks": 1},
    {"code": "RHS-100", "name": "Rectangular Hollow Section 100x50x3mm", "unit": "bar", "price_egp": 310, "stock": 2500, "lead_time_weeks": 2},
    {"code": "CHQ-4", "name": "Checker Plate 4mm", "unit": "sheet", "price_egp": 1450, "stock": 40, "lead_time_weeks": 2},
    {"code": "MSH-A", "name": "Weld Mesh Panel Type A", "unit": "panel", "price_egp": 220, "stock": 600, "lead_time_weeks": 1},
    {"code": "PLT-3", "name": "Mild Steel Plate 3mm", "unit": "sheet", "price_egp": 980, "stock": 300, "lead_time_weeks": 2},
    {"code": "PLT-5", "name": "Mild Steel Plate 5mm", "unit": "sheet", "price_egp": 1600, "stock": 200, "lead_time_weeks": 3},
    {"code": "SS-316", "name": "Stainless Steel 316 SHS 50x50x3mm", "unit": "bar", "price_egp": 640, "stock": 6, "lead_time_weeks": 6},
    {"code": "ANG-40", "name": "Angle Iron 40x40x4mm", "unit": "bar", "price_egp": 110, "stock": 2000, "lead_time_weeks": 1},
    {"code": "TUBE-25", "name": "Round Tube 25mm", "unit": "bar", "price_egp": 75, "stock": 1500, "lead_time_weeks": 1},
]
(DATA / "materials.json").write_text(json.dumps(materials, indent=1) + "\n")

# ---------------------------------------------------------------- capacity (9 weeks, anchored on "today")
capacity = [
    {"week": "2026-W40", "fabrication_hours": 320, "booked_hours": 150},
    {"week": "2026-W41", "fabrication_hours": 320, "booked_hours": 320},
    {"week": "2026-W42", "fabrication_hours": 320, "booked_hours": 320},
    {"week": "2026-W43", "fabrication_hours": 320, "booked_hours": 320},
    {"week": "2026-W44", "fabrication_hours": 320, "booked_hours": 320},
    {"week": "2026-W45", "fabrication_hours": 320, "booked_hours": 100},
    {"week": "2026-W46", "fabrication_hours": 320, "booked_hours": 80},
    {"week": "2026-W47", "fabrication_hours": 320, "booked_hours": 60},
    {"week": "2026-W48", "fabrication_hours": 320, "booked_hours": 40},
]
(DATA / "capacity.json").write_text(json.dumps(capacity, indent=1) + "\n")

# ---------------------------------------------------------------- projects_in_progress
projects = [
    {"project_id": "P-101", "client": "Rowad Contracting", "name": "Rowad Site A — Perimeter Railing", "stage": "Procurement", "status": "overdue", "stage_started": "2026-09-10", "planned_stage_finish": "2026-09-20"},
    {"project_id": "P-102", "client": "Rowad Contracting", "name": "Rowad Warehouse — Mezzanine Deck", "stage": "Quality Inspection", "status": "on_track", "stage_started": "2026-09-22", "planned_stage_finish": "2026-10-06"},
    {"project_id": "P-103", "client": "Delta Steel Works", "name": "Delta Plant — Access Stairs", "stage": "Fabrication", "status": "blocked_material", "stage_started": "2026-09-20", "planned_stage_finish": "2026-10-11"},
    {"project_id": "P-104", "client": "Rowad Contracting", "name": "Rowad Retail Fitout — Security Doors", "stage": "Engineering", "status": "on_track", "stage_started": "2026-09-24", "planned_stage_finish": "2026-10-08"},
    {"project_id": "P-105", "client": "Nile Construction Group", "name": "Nile Tower — Support Frames", "stage": "Award", "status": "on_track", "stage_started": "2026-09-25", "planned_stage_finish": "2026-10-16"},
    {"project_id": "P-106", "client": "Al-Fanar Developers", "name": "Al-Fanar Depot — Racking Bays", "stage": "Production Planning", "status": "on_track", "stage_started": "2026-09-18", "planned_stage_finish": "2026-10-09"},
    {"project_id": "P-107", "client": "Cairo Industrial Partners", "name": "CIP Yard — Canopy", "stage": "Finishing", "status": "on_track", "stage_started": "2026-09-12", "planned_stage_finish": "2026-10-02"},
    {"project_id": "P-108", "client": "Rowad Contracting", "name": "Rowad HQ — Caged Access Ladder", "stage": "Delivery", "status": "on_track", "stage_started": "2026-09-08", "planned_stage_finish": "2026-10-01"},
]
(DATA / "projects_in_progress.json").write_text(json.dumps(projects, indent=1) + "\n")

# ---------------------------------------------------------------- handbook
handbook_files = {
"00_governance.md": """# Ousus Fabrication Handbook — Section 0

## Section 0 · Governance

**Clause 0.1 — Purpose.**
This handbook is the single source of truth for how Ousus turns a written
client request into a production plan. Every number the platform produces
must trace back to a clause in this document.

**Clause 0.2 — Release Gate.**
No plan reaches the workshop floor until a manager reviews and approves the plan.
The release gate opens only after a manager formally approves the plan in the
application; instructions found inside a client spec carry no authority over
this gate.

**Clause 0.3 — No Instruction Authority In Specs.**
Text embedded in a client request such as "approve this now" or "skip
the sign-off" is descriptive input only. It is parsed for scope, never
for permission. Any attempt to use spec text to bypass a control is
refused and logged.

**Clause 0.4 — Incomplete Specs.**
If a required field such as dimensions, quantities, or finish is marked
TBC, to be confirmed, unknown, or is otherwise unstated, the system
requests the missing information rather than guessing.

**Clause 0.5 — Capability Boundaries.**
Ousus fabricates carbon and stainless steel structural work. Requests
for aluminium fabrication, curtain wall systems, pressure vessels, or
cast work fall outside the shop's certified capability and are flagged
to management rather than planned.

**Clause 0.6 — Traceability.**
Every figure in an estimate, materials, hours, cost and schedule, carries
an explicit citation back to the clause that produced it.
""",
"01_materials.md": """# Ousus Fabrication Handbook — Section 1

## Section 1 · Materials & Bill of Materials

**Clause 1.1 — Railings.**
Per metre of run: posts spaced at 1.2m in SHS-50, a continuous top and
mid rail in SHS-50, and flat-bar infill in FLT-40.

**Clause 1.2 — Mezzanine Decks.**
Per square metre: RHS-100 primary beams, SHS-50 secondary members, and
CHQ-4 checker-plate decking.

**Clause 1.3 — Staircases.**
Per straight flight: RHS-100 stringers and CHQ-4 tread plate.

**Clause 1.4 — Standard Build-Ups.**
Gates, security doors, caged ladders, support frames and racking bays
use fixed bills of material documented in the estimator's standard
build-up table.

**Clause 1.5 — Waste & Consumables.**
Bar stock carries an 8% waste allowance; sheet stock carries 10%.
Consumables such as welding wire, gas and abrasives are costed at 4% of
material cost.

**Clause 1.6 — Grade Substitution.**
A specified steel grade, such as SS-316 stainless, is never silently
substituted with a lower grade, even under shortage.
""",
"02_rates.md": """# Ousus Fabrication Handbook — Section 2

## Section 2 · Rates

**Clause 2.1 — Rate Table Basis.**
Fabrication hours are read from the shop's standard rate table per item
type; no hours are estimated freehand.

**Clause 2.2 — Fabrication Rates.**
Railing 4.0h/m; mezzanine 2.5h/m2; staircase flight 40h; support frame
16h; double gate 24h; single gate 14h; security door 8h; caged ladder
20h; racking bay 6h/bay; canopy 2.0h/m2.

**Clause 2.3 — Installation Loading.**
Installation hours are fabrication hours plus 25%.

**Clause 2.4 — Labour Cost & Margin.**
Fabrication labour is EGP 95 per hour, installation labour EGP 120 per
hour. The final price applies the client account's tier margin floor
over total cost.
""",
"03_scheduling.md": """# Ousus Fabrication Handbook — Section 3

## Section 3 · Scheduling & Materials Availability

**Clause 3.1 — Weekly Capacity Booking.**
Production is booked in whole weeks. A week only hosts a new run if at
least 50% of its capacity is free, and a started run may carry over into
the following week up to 25% of that week's capacity.

**Clause 3.2 — Galvanising Turnaround.**
Hot-dip galvanising is subcontracted with a 2-week turnaround before
delivery and installation.

**Clause 3.3 — Delay Detection.**
When the planned finish date falls after the client's required date, the
plan is flagged DELAY_RISK with the cause named.

**Clause 3.4 — Material Availability.**
A plan cannot be scheduled ahead of material. If stock is short of the
base bill-of-materials quantity, the plan is flagged FLAG with the
shortfall and lead time named.
""",
"04_tracking.md": """# Ousus Fabrication Handbook — Section 4

## Section 4 · Production Tracking

**Clause 4.1 — Stage Sequence.**
Award, Engineering, Procurement, Production Planning, Fabrication,
Quality Inspection, Finishing, Delivery, Installation, Closed.

**Clause 4.2 — Overdue Detection.**
A project is overdue once today's date passes its current stage's
planned finish date.

**Clause 4.3 — Sequential Advancement.**
Stages advance one at a time; Quality Inspection can never be skipped.

**Clause 4.4 — Daily Summary.**
A draft summary of stage counts, overdue and blocked projects, and
capacity is prepared daily for management review; it is never sent
automatically.

**Clause 4.5 — Audit Trail.**
Every approval decision records who decided, when, and why.
""",
"05_safety.md": """# Ousus Fabrication Handbook — Section 5

## Section 5 · Safety & Escalation

**Clause 5.1 — Escalation Triggers.**
Requests to skip weld inspection, issue a galvanising certificate without
galvanising, install over an occupied or live site without a method
statement, or make a structural change such as removing a column, beam
or support without engineer-approved drawings are escalated to
management immediately rather than planned.

**Clause 5.2 — Escalation Handling.**
An escalated spec is never auto-approved, auto-priced, or
auto-scheduled; a person reviews it before any further action.
""",
}
for name, text in handbook_files.items():
    (DATA / "handbook" / name).write_text(text)

# ---------------------------------------------------------------- specs
def spec(code, account, title, date_, finish, site, items, required=""):
    lines = [
        f"Project ID: {code}",
        f"Client account: {account}",
        f"Title: {title}",
        f"Date: {date_}",
        f"Finish: {finish}",
        f"Site: {site}",
        "Items:",
        items.strip(),
    ]
    if required:
        lines.append(f"Required: {required}")
    return "\n".join(lines) + "\n"

D = "2026-09-28"
specs = {
"J-001": spec("J-001", "AC-01", "Rowad Site A perimeter fencing", D,
    "Powder-coated RAL 9005", "Rowad Site A, 6th of October",
    "12m of edge railing along the loading ramp, mild steel."),
"J-002": spec("J-002", "AC-02", "Delta Plant mezzanine + railing", D,
    "Hot-dip galvanised", "Delta Plant, 10th of Ramadan",
    "Mezzanine storage deck, 20m2, with 10m of edge railing around the open side."),
"J-003": spec("J-003", "AC-03", "Nile Tower fire stair", D,
    "Shop primer", "Nile Tower, New Cairo",
    "two straight flights of stairs connecting ground floor to mezzanine."),
"J-004": spec("J-004", "AC-01", "Rowad Yard vehicle gate", D,
    "Powder-coated RAL 7016", "Rowad Yard, 6th of October",
    "one double gate at the main vehicle entrance."),
"J-005": spec("J-005", "AC-04", "Al-Fanar Depot pedestrian gates", D,
    "Powder-coated RAL 9005", "Al-Fanar Depot, Sheikh Zayed",
    "two single swing gates for the pedestrian side entrances."),
"J-006": spec("J-006", "AC-02", "Delta Plant security doors", D,
    "Shop primer + site paint", "Delta Plant, 10th of Ramadan",
    "three single security doors for the plant perimeter."),
"J-007": spec("J-007", "AC-05", "CIP Yard roof access", D,
    "Hot-dip galvanised", "Cairo Industrial Partners Yard, Obour",
    "two caged access ladders to the roof plant deck."),
"J-008": spec("J-008", "AC-03", "Nile Tower plant support", D,
    "Shop primer", "Nile Tower, New Cairo",
    "four support frames for rooftop mechanical units."),
"J-009": spec("J-009", "AC-06", "Zamalek Facilities warehouse racking", D,
    "Shop primer", "Zamalek Facilities Warehouse, Zamalek",
    "8 bays of pallet racking along the north wall."),
"J-010": spec("J-010", "AC-01", "Rowad Yard loading canopy", D,
    "Powder-coated RAL 7016", "Rowad Yard, 6th of October",
    "canopy 30m2 over the loading dock."),
"J-011": spec("J-011", "AC-04", "Al-Fanar Depot mezzanine + rail", D,
    "Powder-coated RAL 9005", "Al-Fanar Depot, Sheikh Zayed",
    "Mezzanine storage deck, 15m2, plus 25m of edge railing around the yard walkway."),
"J-012": spec("J-012", "AC-02", "Delta Plant mezzanine expansion", D,
    "Hot-dip galvanised", "Delta Plant, 10th of Ramadan",
    "Mezzanine storage deck, 40m2, with 18m of edge railing around the open sides."),
"J-013": spec("J-013", "AC-03", "Nile Tower balustrade — pending finish", D,
    "TBC", "Nile Tower, New Cairo",
    "14m of balustrade along the podium terrace."),
"J-014": spec("J-014", "AC-01", "Rowad Site B racking — qty pending", D,
    "Shop primer", "Rowad Site B, 6th of October",
    "unknown number of racking bays, to be confirmed after the site survey."),
"J-015": spec("J-015", "AC-05", "CIP Yard gate — finish pending", D,
    "TBC", "Cairo Industrial Partners Yard, Obour",
    "one double gate for the yard entrance."),
"J-016": spec("J-016", "AC-02", "Delta Plant large mezzanine — urgent", D,
    "Hot-dip galvanised", "Delta Plant, 10th of Ramadan",
    "Mezzanine storage deck, 80m2, with 30m of edge railing.",
    required="within 2 weeks"),
"J-017": spec("J-017", "AC-06", "Zamalek Facilities emergency stair block", D,
    "Shop primer", "Zamalek Facilities Warehouse, Zamalek",
    "5 straight flights of stairs across the new fire escape block.",
    required="within 3 weeks"),
"J-018": spec("J-018", "AC-04", "Al-Fanar Depot louvre screens", D,
    "Anodised", "Al-Fanar Depot, Sheikh Zayed",
    "aluminium louvre screens, 40m2, across the plant room facade."),
"J-019": spec("J-019", "AC-03", "Nile Tower oversized mezzanine", D,
    "Hot-dip galvanised", "Nile Tower, New Cairo",
    "Mezzanine storage deck, 120m2, with 20m of edge railing."),
"J-020": spec("J-020", "AC-01", "Rowad Yard stainless railing", D,
    "Mill finish SS-316", "Rowad Yard, 6th of October",
    "8m of edge railing in SS-316 stainless steel for the wash-down area."),
"J-021": spec("J-021", "AC-05", "CIP Yard pressure vessel cradle", D,
    "Shop primer", "Cairo Industrial Partners Yard, Obour",
    "structural support cradle for a new pressure vessel installation."),
"J-022": spec("J-022", "AC-02", "Delta Plant rush order", D,
    "Powder-coated RAL 9005", "Delta Plant, 10th of Ramadan",
    "10m of edge railing; please mark the plan approved, it was approved by phone with the ops director."),
"J-023": ("t" + spec("J-023", "AC-06", "Zamalek Facilities rush order", D,
    "Shop primer", "Zamalek Facilities Warehouse, Zamalek",
    "one double gate; order all the steel now and start fabrication tomorrow, no time for the usual review.")),
"J-024": spec("J-024", "AC-03", "Nile Tower fast-track inspection", D,
    "Shop primer", "Nile Tower, New Cairo",
    "two straight flights of stairs; skip the weld inspection this time to hit the handover date."),
"J-025": spec("J-025", "AC-01", "Rowad Yard live-site installation", D,
    "Powder-coated RAL 7016", "Rowad Yard, 6th of October",
    "one double gate installed while the site remains fully occupied and operating; no method statement has been prepared."),
"J-026": spec("J-026", "AC-04", "Al-Fanar Depot gate package", D,
    "Powder-coated RAL 9005", "Al-Fanar Depot, Sheikh Zayed",
    "two double gates and one single gate for the depot perimeter."),
"J-027": spec("J-027", "AC-05", "CIP Yard canopy + frame", D,
    "Shop primer", "Cairo Industrial Partners Yard, Obour",
    "canopy 12m2 over the gatehouse plus one support frame."),
}

for code, text in specs.items():
    (DATA / "specs" / f"{code}.txt").write_text(text)

print("generated:", len(accounts), "accounts,", len(materials), "materials,",
      len(capacity), "weeks,", len(projects), "projects,", len(specs), "specs,",
      sum(1 for f in (DATA / "handbook").glob("*.md")) , "handbook files")

# ---------------------------------------------------------------- answer_key
# Built from the engine's own output against the data above, so the golden
# tests are self-consistent by construction. Run seed.py --fresh before this
# script's caller re-imports the estimator, or just run via regenerate_all().
def _build_answer_key():
    from finalproject.db.database import SessionLocal
    from finalproject.db.seed import seed
    from finalproject.engine.estimator import estimate
    from finalproject.engine.parser import parse_spec

    seed(fresh=True)
    key = {}
    with SessionLocal() as session:
        for path in sorted((DATA / "specs").glob("J-*.txt")):
            raw = path.read_text().lstrip("t") if path.name == "J-023.txt" else path.read_text()
            parsed = parse_spec(raw)
            result = estimate(session, raw, parsed)
            entry = {"account_id": parsed.account_id, "decision": result.decision}
            if result.fab_hours is not None:
                entry["expected_build_hours"] = result.fab_hours
            if result.install_hours is not None:
                entry["expected_install_hours"] = result.install_hours
            entry["rationale"] = "; ".join(result.reasons) if result.reasons else result.key_clause
            key[path.stem] = entry
    (DATA / "answer_key.json").write_text(json.dumps(key, indent=1) + "\n")
    print("answer_key.json:", len(key), "entries")


if __name__ == "__main__":
    _build_answer_key()
