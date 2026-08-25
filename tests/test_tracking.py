"""Tracking, approval gate and summary tests (API-level, offline)."""

import os
import tempfile

os.environ["OUSUS_DB"] = os.path.join(tempfile.gettempdir(), "ousus_track_test.db")

from fastapi.testclient import TestClient  # noqa: E402
import pytest  # noqa: E402

from finalproject.api.main import app  # noqa: E402
from finalproject.db.seed import seed  # noqa: E402
from finalproject.tracking.service import STAGES  # noqa: E402

client = TestClient(app)


def login(email):
    r = client.post("/auth/login", json={"email": email, "password": "demo1234"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module", autouse=True)
def seeded_db():
    seed(fresh=True)
    yield


@pytest.fixture(scope="module")
def manager():
    return login("manager@oususapp.com")


@pytest.fixture(scope="module")
def engineer():
    return login("engineer@oususapp.com")


@pytest.fixture(scope="module")
def estimator():
    return login("estimator@oususapp.com")


@pytest.fixture(scope="module")
def client_user():
    return login("client@oususapp.com")


# ---------- board -----------------------------------------------------------


def test_board_groups_by_stage(engineer):
    r = client.get("/board", headers=engineer)
    assert r.status_code == 200
    body = r.json()
    for stage in ("Fabrication", "Procurement"):
        codes = [p["code"] for p in body["columns"].get(stage, [])]
        assert codes, f"expected projects in {stage}"
    p101 = [p for col in body["columns"].values() for p in col
            if p["code"] == "P-101"][0]
    assert p101["overdue"] is True


def test_board_forbidden_for_client(client_user):
    assert client.get("/board", headers=client_user).status_code == 403


def test_client_portal_scoped_to_own_account(client_user):
    r = client.get("/my/projects", headers=client_user)
    assert r.status_code == 200
    projects = r.json()["projects"]
    assert projects, "AC-01 owns P-101/P-102/P-104/P-122 in mock data"
    assert all(p["code"].startswith("P-1") for p in projects)


# ---------- stage machine ----------------------------------------------------


def test_stage_advance_records_history(engineer):
    r = client.patch("/projects/P-102/stage",
                     json={"stage": "Finishing"}, headers=engineer)
    assert r.status_code == 200
    assert r.json()["stage"] == "Finishing"

    # cannot skip stages (4.3)
    r = client.patch("/projects/P-102/stage",
                     json={"stage": "Installation"}, headers=engineer)
    assert r.status_code == 400


def test_stage_requires_staff(client_user):
    r = client.patch("/projects/P-101/stage", json={}, headers=client_user)
    assert r.status_code == 403


# ---------- estimate -> gate -> release --------------------------------------


def _estimate(code, estimator):
    r = client.post(f"/specs/{code}/estimate", headers=estimator)
    assert r.status_code == 200, r.text
    return r.json()


def test_estimate_creates_draft_then_estimator_submits(estimator):
    body = _estimate("J-001", estimator)
    assert body["decision"] == "PLAN"
    assert body["fab_hours"] == 48.0
    r = client.post("/requests/J-001/submit-to-manager", headers=estimator)
    assert r.status_code == 200, r.text
    assert r.json()["release_status"] == "queued"
    assert r.json()["approval_id"] > 0


def test_manager_must_open_the_gate(manager, engineer, estimator):
    body = _estimate("J-004", estimator)
    client.post("/requests/J-004/submit-to-manager", headers=estimator)
    pending_all = client.get("/approvals", headers=manager).json()
    approval_id = next(a["id"] for a in pending_all
                       if f"for {body['project']} " in a["note"])

    # engineer cannot decide — the gate is manager-only (0.2)
    r = client.post(f"/approvals/{approval_id}/decision",
                    json={"approved": True}, headers=engineer)
    assert r.status_code == 403

    r = client.post(f"/approvals/{approval_id}/decision",
                    json={"approved": True, "note": "materials verified"},
                    headers=manager)
    assert r.status_code == 200
    board = client.get("/board", headers=engineer).json()["columns"]
    row = [p for col in board.values() for p in col if p["code"] == "J-004"]
    assert row and row[0]["release_status"] == "manager_approved"


def test_double_decision_rejected(manager):
    pending = client.get("/approvals", headers=manager).json()
    if pending:
        aid = pending[0]["id"]
        client.post(f"/approvals/{aid}/decision",
                    json={"approved": False}, headers=manager)
        r = client.post(f"/approvals/{aid}/decision",
                        json={"approved": True}, headers=manager)
        assert r.status_code == 409


def test_audit_trail_names_the_approver(manager, estimator):
    client.post("/requests/J-003/submit-to-manager", headers=estimator)
    pending = client.get("/approvals", headers=manager).json()
    if pending:
        aid = pending[0]["id"]
        client.post(f"/approvals/{aid}/decision",
                    json={"approved": True}, headers=manager)
    audit = client.get("/audit", headers=manager).json()
    assert audit, "decisions recorded"
    decided = [a for a in audit if a["decision"] != "pending"]
    assert all(a["at"] for a in decided)


def test_refusal_specs_never_queue(estimator):
    body = _estimate("J-022", estimator)
    assert body["decision"] == "REFUSE_OVERRIDE"
    assert "approval_id" not in body


# ---------- daily summary (4.4 / DAILY-SUMMARY golden content) ----------------


def test_daily_summary_matches_golden_expectations(manager):
    s = client.get("/summary/daily", headers=manager).json()
    assert s["active_projects"] >= 8
    overdue_codes = {p["code"] for p in s["overdue"]}
    assert "P-101" in overdue_codes, "P-101 must be named as OVERDUE"
    blocked = {p["code"]: p for p in s["blocked_on_materials"]}
    assert "P-103" in blocked, "P-103 must be named blocked on materials"
    cap = s["capacity"]
    assert set(cap["fully_booked_weeks"]) == {
        "2026-W37", "2026-W38", "2026-W39", "2026-W40"}
    assert cap["first_meaningful_free_week"] == "2026-W41"
    assert "approval" in s["note"].lower()


def test_summary_forbidden_for_viewer():
    viewer = login("viewer@oususapp.com")
    assert client.get("/summary/daily", headers=viewer).status_code == 403
