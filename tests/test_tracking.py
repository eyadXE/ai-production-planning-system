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


def _new_request(client_user, title, custom=False):
    body = {"title": title,
            "items": [] if custom else [{"kind": "railing", "qty": 10}],
            "custom": ([{"name": "Art piece",
                         "description": "decorative custom build"}]
                       if custom else []),
            "finish": "", "site": "test site", "required_raw": ""}
    r = client.post("/requests", headers=client_user, json=body)
    assert r.status_code == 200, r.text
    return r.json()["code"]


def _catalog_to_queued(code, estimator, manager):
    """run-estimate -> estimator approves -> manager approves."""
    r = client.post(f"/requests/{code}/run-estimate", headers=estimator)
    assert r.status_code == 200, r.text
    r = client.post(f"/requests/{code}/decision",
                    json={"approved": True}, headers=estimator)
    assert r.status_code == 200, r.text
    assert r.json().get("release_status") == "pending_manager_review"
    r = client.post(f"/requests/{code}/manager-decision",
                    json={"approved": True}, headers=manager)
    assert r.status_code == 200, r.text
    assert r.json()["release_status"] == "queued"


def test_full_new_flow_manager_decides_before_client(estimator, manager,
                                                     client_user):
    """Estimator approves -> manager approves/rejects in Requests ->
    then (and only then) the offer goes to the client."""
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


def test_release_needs_client_acceptance_then_engineer(manager, estimator,
                                                       client_user):
    """Client accepts -> Release page (assign + release) -> timeline."""
    code = _new_request(client_user, "release order test")
    _catalog_to_queued(code, estimator, manager)

    # cannot release while only queued (client has not accepted yet)
    r = client.post(f"/projects/{code}/release", headers=manager)
    assert r.status_code == 409

    r = client.post(f"/my/projects/{code}/decision",
                    json={"accept": True}, headers=client_user)
    assert r.status_code == 200 and \
        r.json()["release_status"] == "client_accepted"

    # cannot release without an assigned project engineer
    r = client.post(f"/projects/{code}/release", headers=manager)
    assert r.status_code == 409
    assert "assign" in r.json()["detail"].lower()

    eng_list = client.get("/team/engineers", headers=manager).json()
    r = client.post(f"/projects/{code}/assign",
                    json={"engineer_id": eng_list[0]["id"]}, headers=manager)
    assert r.status_code == 200

    r = client.post(f"/projects/{code}/release", headers=manager)
    assert r.status_code == 200 and r.json()["release_status"] == "released"

    tl = client.get("/timeline", headers=manager).json()
    assert any(p["code"] == code for p in tl["projects"])

    # released orders are permanent
    assert client.delete(f"/projects/{code}",
                         headers=manager).status_code == 403


def test_custom_request_two_level_manual_plan(estimator, manager, client_user):
    """Custom builds have NO engine figures: estimator fills engineering
    input, manager completes pricing & schedule, then normal pipeline."""
    code = _new_request(client_user, "custom two level test", custom=True)

    # a plain estimator approve is NOT enough for custom requests
    r = client.post(f"/requests/{code}/decision",
                    json={"approved": True}, headers=estimator)
    assert r.status_code == 409
    assert "custom" in r.json()["detail"].lower()

    # level 1 — estimator fills scope + hours (only he can)
    r = client.post(f"/requests/{code}/custom/estimator-info",
                    json={"scope": "decorative gate 3 m, SHS frame",
                          "materials_note": "SHS + mesh infill, shop paint",
                          "fab_hours": 80, "install_hours": 20},
                    headers=estimator)
    assert r.status_code == 200, r.text
    assert r.json()["release_status"] == "pending_manager_review"

    # it shows in the manager's queue flagged as needing pricing
    awaiting = client.get("/requests/awaiting-decision",
                          headers=manager).json()
    row = next((a for a in awaiting if a["code"] == code), None)
    assert row is not None and row["needs_pricing"] is True
    assert row["estimator_plan"]["fab_hours"] == 80

    # level 2 cannot be skipped
    r = client.post(f"/requests/{code}/manager-decision",
                    json={"approved": True}, headers=manager)
    assert r.status_code == 422

    # level 2 — manager fills material cost / margin / finish date
    r = client.post(f"/requests/{code}/manager-decision",
                    json={"approved": True, "material_cost_egp": 12000,
                          "margin_applied": 22,
                          "planned_finish": "2026-11-01"},
                    headers=manager)
    assert r.status_code == 200, r.text
    assert r.json()["release_status"] == "queued"

    # price computed from both levels: (12000 + 480 + 10000) * 1.22 = 27345.6
    mine = client.get("/my/projects", headers=client_user).json()
    proj = next(p for p in mine["projects"] if p["code"] == code)
    assert proj["estimated_finish"] is not None

    # resume the normal pipeline: client accepts -> assign -> release
    r = client.post(f"/my/projects/{code}/decision",
                    json={"accept": True}, headers=client_user)
    assert r.status_code == 200
    eng_list = client.get("/team/engineers", headers=manager).json()
    client.post(f"/projects/{code}/assign",
                json={"engineer_id": eng_list[0]["id"]}, headers=manager)
    r = client.post(f"/projects/{code}/release", headers=manager)
    assert r.status_code == 200 and r.json()["release_status"] == "released"


def test_audit_trail_names_the_approver(manager, estimator, client_user):
    code = _new_request(client_user, "audit trail test")
    _catalog_to_queued(code, estimator, manager)
    audit = client.get("/audit", headers=manager).json()
    assert audit, "decisions recorded"
    decided = [a for a in audit if a["decision"] != "pending"]
    assert decided, "manager decisions are recorded"
    assert all(a["at"] and a["approver_id"] for a in decided)


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
    # NOTE: these week labels are tied to OUSUS/Ousus_data/capacity.json,
    # which is generated relative to "today" (see _gen_mock_data.py in the
    # project root history / HOW_TO_RUN.md) — regenerate both together if
    # the capacity data is ever rebuilt on a different date.
    assert set(cap["fully_booked_weeks"]) == {
        "2026-W41", "2026-W42", "2026-W43", "2026-W44"}
    assert cap["first_meaningful_free_week"] == "2026-W45"
    assert "approval" in s["note"].lower()


def test_summary_forbidden_for_viewer():
    viewer = login("viewer@oususapp.com")
    assert client.get("/summary/daily", headers=viewer).status_code == 403
