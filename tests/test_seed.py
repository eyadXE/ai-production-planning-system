"""End-to-end checks for the seeding pipeline.

Runs a fresh seed against a temporary SQLite file and verifies row counts,
relationships, and the date-fix invariants (capacity starts at/after current
ISO week; fully-booked block lies in the future).
"""

import os
import tempfile
from datetime import date, timedelta

import pytest

os.environ["OUSUS_DB"] = os.path.join(tempfile.gettempdir(), "ousus_test.db")

from finalproject.core.security import verify_password  # noqa: E402
from finalproject.db.database import SessionLocal  # noqa: E402
from finalproject.db.models import (  # noqa: E402
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
from finalproject.db.seed import DEFAULT_PASSWORD, seed  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
def seeded_db():
    seed(fresh=True)
    yield


def test_row_counts():
    with SessionLocal() as s:
        assert len(s.query(Account).all()) == 6
        assert len(s.query(Material).all()) == 10
        assert len(s.query(CapacityWeek).all()) == 9
        assert len(s.query(Spec).all()) == 27
        assert len(s.query(Project).all()) == 8
        assert len(s.query(HandbookClause).all()) == 27
        assert len(s.query(User).all()) == 4
        assert len(s.query(FxRate).all()) == 2


def test_relationships():
    with SessionLocal() as s:
        p101 = s.query(Project).filter_by(code="P-101").one()
        assert p101.account.name == "Rowad Contracting"
        assert p101.status == "overdue"
        assert p101.stage_events, "stage event recorded"

        spec = s.query(Spec).filter_by(code="J-001").one()
        assert spec.raw_text.startswith("Project ID: J-001")
        assert spec.account.tier == "retail"


def test_capacity_dates_valid_for_today():
    today = date.today()
    with SessionLocal() as s:
        weeks = s.query(CapacityWeek).order_by(CapacityWeek.start_date).all()
        assert weeks[0].start_date >= today - timedelta(days=6), "window starts at current week"
        full = [w for w in weeks if w.booked_hours == w.total_hours]
        assert full, "fully-booked block exists"
        assert all(w.start_date > today for w in full), "block must be upcoming"


def test_overdue_projects_are_actually_past_due():
    today = date.today()
    with SessionLocal() as s:
        overdue = s.query(Project).filter_by(status="overdue").all()
        assert overdue
        for p in overdue:
            assert p.required_date < today


def test_clause_citations_present():
    with SessionLocal() as s:
        nos = {c.clause_no for c in s.query(HandbookClause).all()}
        assert {"0.2", "1.5", "2.2", "3.2"} <= nos
        clause = s.query(HandbookClause).filter_by(clause_no="0.2").one()
        assert "release gate" in clause.title.lower()
        assert "approves the plan" in clause.body_text.lower()


def test_demo_user_login():
    with SessionLocal() as s:
        manager = s.query(User).filter_by(email="manager@oususapp.com").one()
        assert manager.role == "manager"
        assert verify_password(DEFAULT_PASSWORD, manager.password_hash)
        assert not verify_password("wrong", manager.password_hash)
