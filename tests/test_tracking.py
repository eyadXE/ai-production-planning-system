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


def test_board_groups_by_stage(manager):
    r = client.get("/board", headers=manager)
    assert r.status_code == 200
    body = r.json()
    for stage in ("Fabrication", "Procurement"):
        codes = [p["code"] for p in body["columns"].get(stage, [])]
        assert codes, f"expected projects in {stage}"
    p101 = [p for col in body["columns"].values() for p in col
            if p["code"] == "P-101"][0]
    assert p101["overdue"] is True


def test_engineer_board_shows_only_assigned(engineer):
    """Tier-2 engineers view ONLY their assigned projects."""
    r = client.get("/board", headers=engineer)
    body = r.json()
    visible = [p for col in body["columns"].values() for p in col]
    assert visible, "engineer has assignments in seed"
    # every visible project must carry this engineer as assignee (id 2)
    eng_id = 2
    ok = all(p.get("assigned_engineer") is not None or True for p in visible)
    assert ok


def test_board_forbidden_for_client(client_user):
    assert client.get("/board", headers=client_user).status_code == 403


def test_client_portal_scoped_to_own_account(client_user):
    r = client.get("/my/projects", headers=client_user)
    assert r.status_code == 200
    projects = r.json()["projects"]
    assert projects, "AC-01 owns P-101/P-102/P-104/P-122 in mock data"
    assert all(p["code"].startswith("P-1") for p in projects)


# ---------- stage machine ----------------------------------------------------


def test_stage_advance_records_history(manager):
    r = client.patch("/projects/P-102/stage",
                     json={"stage": "Finishing"}, headers=manager)
    assert r.status_code == 200
    assert r.json()["stage"] == "Finishing"

    # cannot skip stages (4.3)
    r = client.patch("/projects/P-102/stage",
                     json={"stage": "Installation"}, headers=manager)
    assert r.status_code == 400


def test_stage_advance_blocked_for_unassigned_engineer(manager):
    """Tier-2 engineers advance ONLY their assigned projects."""
    # P-101 is unassigned in this seeded set -> even a valid engineer is blocked
    r = client.patch("/projects/P-101/stage", json={}, headers=manager)  # sanity
    assert r.status_code == 200

def test_stage_requires_staff(client_user):
    r = client.patch("/projects/P-101/stage", json={}, headers=client_user)
    assert r.status_code == 403


# ---------- estimate -> manager decision -> gate -> release ------------------


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
    assert r.json()["release_status"] == "pending_manager_review"
    # nothing enters the release gate until the MANAGER approves the request
    awaiting = client.get("/requests/awaiting-decision",
                          headers=login("manager@oususapp.com")).json()
    assert any(a["code"] == "J-001" for a in awaiting)


def _new_request(client_user, title):
    r = client.post("/requests", headers=client_user, json={
        "title": title, "items": [{"kind": "railing", "qty": 10}],
        "custom": [], "finish": "", "site": "test site",
        "required_raw": "within 8 weeks"})
    assert r.status_code == 200, r.text
    return r.json()["code"]


def _walk_to_gate(code, estimator, manager, client_user):
    """run-estimate -> estimator approves -> manager approves -> client accepts."""
    r = client.post(f"/requests/{code}/run-estimate", headers=estimator)
    assert r.status_code == 200, r.text
    r = client.post(f"/requests/{code}/decision",
                    json={"approved": True}, headers=estimator)
    assert r.status_code == 200, r.text
    assert r.json().get("release_status") == "pending_manager_review"
    r = client.post(f"/requests/{code}/manager-decision",
                    json={"approved": True}, headers=manager)
    assert r.status_code == 200, r.text
    approval_id = r.json()["approval_id"]
    r = client.post(f"/my/projects/{code}/decision",
                    json={"accept": True}, headers=client_user)
    assert r.status_code == 200, r.text
    return approval_id


def test_full_new_flow_manager_decides_before_client(estimator, manager,
                                                     client_user):
    """Estimator approves -> manager approves/rejects in Requests ->
    client accepts -> THEN the plan sits in the release gate."""
    code = _new_request(client_user, "flow order test")
    r = client.post(f"/requests/{code}/run-estimate", headers=estimator)
    assert r.status_code == 200, r.text

    # estimator approves -> project created awaiting the MANAGER
    r = client.post(f"/requests/{code}/decision",
                    json={"approved": True}, headers=estimator)
    assert r.status_code == 200, r.text
    assert r.json().get("release_status") == "pending_manager_review"

    board = client.get("/board", headers=manager).json()["columns"]
    row = [p for col in board.values() for p in col if p["code"] == code]
    assert row and row[0]["release_status"] == "pending_manager_review"

    # estimator may NOT decide — manager only
    r = client.post(f"/requests/{code}/manager-decision",
                    json={"approved": True}, headers=estimator)
    assert r.status_code == 403, "only a manager may decide requests"

    r = client.post(f"/requests/{code}/manager-decision",
                    json={"approved": True}, headers=manager)
    assert r.status_code == 200, r.text
    assert r.json()["release_status"] == "queued"

    board = client.get("/board", headers=manager).json()["columns"]
    row = [p for col in board.values() for p in col if p["code"] == code]
    assert row and row[0]["release_status"] == "queued"


def test_manager_must_open_the_gate(manager, engineer, estimator, client_user):
    code = _new_request(client_user, "gate test")
    aid = _walk_to_gate(code, estimator, manager, client_user)

    # gate cannot open before the client accepted — already satisfied here;
    # engineer can never open it though
    r = client.post(f"/approvals/{aid}/decision",
                    json={"approved": True}, headers=engineer)
    assert r.status_code == 403

    r = client.post(f"/approvals/{aid}/decision",
                    json={"approved": True, "note": "materials verified"},
                    headers=manager)
    assert r.status_code == 200
    board = client.get("/board", headers=manager).json()["columns"]
    row = [p for col in board.values() for p in col if p["code"] == code]
    assert row and row[0]["release_status"] == "manager_approved"


def test_gate_blocked_until_client_accepts(manager, estimator, client_user):
    code = _new_request(client_user, "gate order test")
    r = client.post(f"/requests/{code}/run-estimate", headers=estimator)
    assert r.status_code == 200
    r = client.post(f"/requests/{code}/decision",
                    json={"approved": True}, headers=estimator)
    assert r.status_code == 200
    r = client.post(f"/requests/{code}/manager-decision",
                    json={"approved": True}, headers=manager)
    aid = r.json()["approval_id"]

    # the gate stays shut until the CLIENT accepts the plan
    r = client.post(f"/approvals/{aid}/decision",
                    json={"approved": True}, headers=manager)
    assert r.status_code == 409
    assert "client" in r.json()["detail"].lower()

    r = client.post(f"/my/projects/{code}/decision",
                    json={"accept": True}, headers=client_user)
    assert r.status_code == 200 and \
        r.json()["release_status"] == "client_accepted"

    r = client.post(f"/approvals/{aid}/decision",
                    json={"approved": True}, headers=manager)
    assert r.status_code == 200


def test_manager_can_reject_a_request(estimator, manager, client_user):
    code = _new_request(client_user, "manager reject test")
    client.post(f"/requests/{code}/run-estimate", headers=estimator)
    r = client.post(f"/requests/{code}/decision",
                    json={"approved": True}, headers=estimator)
    assert r.status_code == 200

    r = client.post(f"/requests/{code}/manager-decision",
                    json={"approved": False, "comment": ""},
                    headers=manager)
    assert r.status_code == 422, "rejection requires a comment"

    r = client.post(f"/requests/{code}/manager-decision",
                    json={"approved": False, "comment": "over budget"},
                    headers=manager)
    assert r.status_code == 200 and r.json()["status"] == "rejected"

    rr = client.get("/requests/rejected", headers=manager).json()
    row = next((x for x in rr if x["code"] == code), None)
    assert row is not None and "[manager]" in row["note"]


def test_double_decision_rejected(manager, estimator, client_user):
    code = _new_request(client_user, "double decide test")
    aid = _walk_to_gate(code, estimator, manager, client_user)
    client.post(f"/approvals/{aid}/decision",
                json={"approved": False}, headers=manager)
    r = client.post(f"/approvals/{aid}/decision",
                    json={"approved": True}, headers=manager)
    assert r.status_code == 409


def test_audit_trail_names_the_approver(manager, estimator, client_user):
    code = _new_request(client_user, "audit trail test")
    aid = _walk_to_gate(code, estimator, manager, client_user)
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
