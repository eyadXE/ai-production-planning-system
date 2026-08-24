"""One-off script: shift mock-data dates so scenarios are valid relative to today.

Logic-preserving rules (per supervisor decision):
- Uniform WEEK_DELTA = +7 on explicit ISO-week labels. The fully-booked block
  (originally W30-W33) lands strictly in the future, and the original gap of
  one week between spec dates (W27) and the first capacity week (W28) is kept.
- All 27 spec "Date:" lines move from 2026-07-01 to the Monday of the week
  before the first capacity week (preserves every relative deadline).
- Project stage dates are recomputed per-project so each status stays truthful:
    overdue        -> planned_stage_finish just in the past
    on_track/blocked -> planned_stage_finish in the near future
  Durations between stage_started and planned_stage_finish are preserved.
- answer_key.json: only human-readable week mentions inside rationale strings
  are remapped; decisions/hours/tools stay byte-identical.
"""

import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

DATA = Path("OUSUS/Ousus_data")

WEEK_RE = re.compile(r"\b(20\d\d)-W(\d{2})\b")
DATE_RE = re.compile(r"\b(20\d\d)-\d\d-\d\d\b")


def iso_week_monday(year: int, week: int) -> date:
    return date.fromisocalendar(year, week, 1)


def week_label(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def current_week_start() -> date:
    t = date.today()
    return t - timedelta(days=t.weekday())


BARE_WEEK_RE = re.compile(r"\bW(\d{2})\b")
MOCK_YEAR = 2026


def shift_week_text(text: str, weeks: int) -> str:
    def repl(m: re.Match) -> str:
        new = iso_week_monday(int(m.group(1)), int(m.group(2))) + timedelta(weeks=weeks)
        return week_label(new)

    def repl_bare(m: re.Match) -> str:
        new = iso_week_monday(MOCK_YEAR, int(m.group(1))) + timedelta(weeks=weeks)
        _, w, _ = new.isocalendar()
        return f"W{w:02d}"

    text = WEEK_RE.sub(repl, text)
    return BARE_WEEK_RE.sub(repl_bare, text)


def main() -> None:
    # ---- idempotency guard ----------------------------------------------
    cap_path = DATA / "capacity.json"
    cap_probe = json.loads(cap_path.read_text())
    if WEEK_RE.match(cap_probe[0]["week"]) and iso_week_monday(
        int(WEEK_RE.match(cap_probe[0]["week"]).group(1)),
        int(WEEK_RE.match(cap_probe[0]["week"]).group(2)),
    ) >= current_week_start():
        print("already fixed; nothing to do")
        return

    # ---- target anchor -------------------------------------------------
    first_cap_old = iso_week_monday(2026, 28)
    cur_monday = current_week_start()
    week_delta = (cur_monday - first_cap_old).days // 7
    print(f"today={date.today()} current_week={week_label(cur_monday)} week_delta=+{week_delta}")

    # ---- capacity.json: relabel weeks ----------------------------------
    cap = json.loads(cap_path.read_text())
    for row in cap:
        old = row["week"]
        m = WEEK_RE.match(old)
        assert m, f"unexpected week label {old}"
        new_d = iso_week_monday(int(m.group(1)), int(m.group(2))) + timedelta(weeks=week_delta)
        row["week"] = week_label(new_d)
    cap_path.write_text(json.dumps(cap, indent=1) + "\n")
    print(f"capacity: {cap[0]['week']} .. {cap[-1]['week']}")

    # ---- specs: Date lines + explicit week labels -----------------------
    spec_date_new = cur_monday - timedelta(weeks=1)  # keep original W27 vs W28 gap
    for spec in sorted((DATA / "specs").glob("J-*.txt")):
        txt = spec.read_text()
        txt = DATE_RE.sub(spec_date_new.isoformat(), txt)
        txt = shift_week_text(txt, week_delta)
        spec.write_text(txt)

    # ---- answer_key.json: remap week mentions in text fields only -------
    key_path = DATA / "answer_key.json"
    key = json.loads(key_path.read_text())
    for entry in key.values():
        for field in ("rationale",):
            if isinstance(entry.get(field), str):
                entry[field] = shift_week_text(entry[field], week_delta)
    key_path.write_text(json.dumps(key, indent=1) + "\n")

    # ---- projects_in_progress.json: status-consistent dates -------------
    proj_path = DATA / "projects_in_progress.json"
    projects = json.loads(proj_path.read_text())
    today = date.today()
    for i, p in enumerate(projects):
        started = datetime.strptime(p["stage_started"], "%Y-%m-%d").date()
        planned = datetime.strptime(p["planned_stage_finish"], "%Y-%m-%d").date()
        dur = planned - started
        # stagger starts so the board looks alive: 3..N days back
        new_start = cur_monday - timedelta(days=(i % 5) + 1)
        new_planned = new_start + dur
        if p["status"] == "overdue":
            if new_planned >= today:
                overshoot = (new_planned - today).days + 1
                new_planned -= timedelta(days=max(overshoot, dur.days))
                new_start = new_planned - dur
        else:  # on_track / blocked_material must finish in the future
            if new_planned <= today:
                new_planned = today + timedelta(days=dur.days % 6 + 2)
                new_start = new_planned - dur
        p["stage_started"] = new_start.isoformat()
        p["planned_stage_finish"] = new_planned.isoformat()
        print(
            f"{p['project_id']}: {new_start} -> {new_planned} ({p['status']})"
        )
    proj_path.write_text(json.dumps(projects, indent=1) + "\n")
    print("done")


if __name__ == "__main__":
    main()
