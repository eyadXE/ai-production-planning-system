"""Seed the SQLite database from OUSUS/Ousus_data mock files.

Usage:
    python -m finalproject.db.seed [--fresh]
"""

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import select

from finalproject.core.security import hash_password
from finalproject.db.database import Base, SessionLocal, engine, init_db
from finalproject.db.models import (
    Account,
    CapacityWeek,
    FxRate,
    HandbookClause,
    Material,
    Project,
    Spec,
    StageEvent,
    User,
)

DATA_DIR = Path("OUSUS/Ousus_data")
DEFAULT_PASSWORD = "demo1234"
FX_DEFAULTS = {"USD": 48.0, "SAR": 12.90}  # EGP per 1 unit (config, display-only)

CLAUSE_RE = re.compile(
    r"\*\*Clause (\d+\.\d+) — (.+?)\.\*\*"
)
SECTION_RE = re.compile(r"^## Section (\d+) · (.+)$", re.MULTILINE)


def load_accounts(session) -> dict[str, int]:
    rows = json.loads((DATA_DIR / "accounts.json").read_text())
    ids = {}
    for r in rows:
        a = Account(
            code=r["account_id"],
            name=r["client"],
            tier=r["tier"],
            margin_floor=r["margin_floor"],
        )
        session.add(a)
        session.flush()
        ids[a.code] = a.id
    return ids


def load_materials(session) -> None:
    rows = json.loads((DATA_DIR / "materials.json").read_text())
    for r in rows:
        session.add(
            Material(
                code=r["code"],
                name=r["name"],
                unit=r["unit"],
                price_egp=r["price_egp"],
                stock_qty=r["stock"],
                lead_time_weeks=r["lead_time_weeks"],
            )
        )


def load_capacity(session) -> None:
    rows = json.loads((DATA_DIR / "capacity.json").read_text())
    for r in rows:
        year, week = int(r["week"][:4]), int(r["week"][6:])
        session.add(
            CapacityWeek(
                week_label=r["week"],
                start_date=date.fromisocalendar(year, week, 1),
                total_hours=r["fabrication_hours"],
                booked_hours=r["booked_hours"],
            )
        )


def load_specs(session, account_ids: dict[str, int]) -> dict[str, int]:
    spec_ids = {}
    for path in sorted((DATA_DIR / "specs").glob("J-*.txt")):
        text = path.read_text()
        code_m = re.search(r"Project ID:\s*(\S+)", text)
        acc_m = re.search(r"Client account:\s*(\S+)", text)
        title_m = re.search(r"Title:\s*(.+)", text)
        code = code_m.group(1) if code_m else path.stem
        account_code = acc_m.group(1) if acc_m else "AC-01"
        s = Spec(
            code=code,
            account_id=account_ids.get(account_code) or next(iter(account_ids.values())),
            title=title_m.group(1).strip() if title_m else "",
            raw_text=text,
            source="file",
            status="approved",
        )
        session.add(s)
        session.flush()
        spec_ids[code] = s.id
    return spec_ids


def load_projects(session, account_ids: dict[str, int], spec_ids: dict[str, int]) -> None:
    rows = json.loads((DATA_DIR / "projects_in_progress.json").read_text())
    accounts = {a.code: a for a in session.scalars(select(Account))}
    name_to_code = {a.name: a.code for a in accounts.values()}
    fallback_account = next(iter(account_ids.values()))
    for r in rows:
        acc_code = name_to_code.get(r["client"])
        p = Project(
            code=r["project_id"],
            account_id=account_ids.get(acc_code, fallback_account),
            spec_id=spec_ids.get(r["project_id"]),
            title=r["name"],
            stage=r["stage"],  # keep the original stage string verbatim
            status=r["status"],
            required_date=datetime.strptime(
                r["planned_stage_finish"], "%Y-%m-%d"
            ).date(),
        )
        session.add(p)
        session.flush()
        session.add(
            StageEvent(
                project_id=p.id,
                stage=r["stage"],
                started_at=datetime.strptime(r["stage_started"], "%Y-%m-%d").date(),
                planned_finish_at=datetime.strptime(
                    r["planned_stage_finish"], "%Y-%m-%d"
                ).date(),
                finished_at=None,
            )
        )


def load_handbook(session) -> int:
    count = 0
    for path in sorted((DATA_DIR / "handbook").glob("*.md")):
        text = path.read_text()
        sections = SECTION_RE.findall(text)
        section_map = {}
        for num, title in sections:
            section_map[num] = title.strip()
        matches = list(CLAUSE_RE.finditer(text))
        for i, m in enumerate(matches):
            clause_no, title = m.group(1), m.group(2)
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            body_full = text[m.end() : end].strip()
            if "\n**" in body_full:
                body_full = body_full[: body_full.find("\n**")]
            session.add(
                HandbookClause(
                    clause_no=clause_no,
                    title=title.strip(),
                    body_text=body_full,
                    section=section_map.get(clause_no.split(".")[0], ""),
                )
            )
            count += 1
    return count


def load_fx_rates(session) -> None:
    for cur, rate in FX_DEFAULTS.items():
        session.add(FxRate(currency=cur, egp_per_unit=rate))


def load_products(session) -> int:
    from finalproject.db.products_data import seed_products

    return seed_products(session)


def create_demo_users(session, account_ids: dict[str, int]) -> None:
    users = [
        User(email="manager@oususapp.com", full_name="Production Manager",
             password_hash=hash_password(DEFAULT_PASSWORD), role="manager"),
        User(email="engineer@oususapp.com", full_name="Senior Estimator",
             password_hash=hash_password(DEFAULT_PASSWORD), role="engineer"),
        User(email="viewer@oususapp.com", full_name="Stakeholder",
             password_hash=hash_password(DEFAULT_PASSWORD), role="viewer"),
    ]
    first_account = next(iter(account_ids.values()))
    users.append(
        User(email="client@oususapp.com", full_name="Client Contact",
             password_hash=hash_password(DEFAULT_PASSWORD), role="client",
             account_id=first_account)
    )
    session.add_all(users)


def seed(fresh: bool = False) -> None:
    init_db()
    if fresh:
        Base.metadata.drop_all(engine)
        init_db()
    with SessionLocal() as session:
        account_ids = load_accounts(session)
        load_materials(session)
        load_capacity(session)
        spec_ids = load_specs(session, account_ids)
        load_projects(session, account_ids, spec_ids)
        clauses = load_handbook(session)
        load_fx_rates(session)
        products = load_products(session)
        create_demo_users(session, account_ids)
        session.commit()

        print(
            "seeded: "
            f"accounts={len(account_ids)} "
            f"materials={len(session.scalars(select(Material)).all())} "
            f"weeks={len(session.scalars(select(CapacityWeek)).all())} "
            f"specs={len(spec_ids)} "
            f"projects={len(session.scalars(select(Project)).all())} "
            f"clauses={clauses} "
            f"products={products}"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fresh", action="store_true", help="drop tables first")
    args = parser.parse_args()
    try:
        seed(fresh=args.fresh)
    except Exception as exc:  # pragma: no cover
        print(f"seed failed: {exc}", file=sys.stderr)
        raise
