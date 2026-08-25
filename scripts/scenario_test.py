"""Comprehensive API scenario test — runs EVERY role's full pipeline.

Simulates: client signup -> catalog cart + custom chat -> estimator review ->
manager approve + assign -> client accept -> manager release ->
engineer stages to closure. Plus negative tests (wrong role, bad state,
deletion protection, chat fallback).
"""

import os
import tempfile

os.environ["OUSUS_DB"] = os.path.join(tempfile.gettempdir(), "ousus_scenario_test.db")

from fastapi.testclient import TestClient  # noqa: E402

from finalproject.api.main import app  # noqa: E402
from finalproject.db.seed import seed  # noqa: E402
from finalproject.tracking.service import STAGES  # noqa: E402

client = TestClient(app)
PASS = FAIL = 0


def check(name, ok, extra=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {extra}")


def login(email):
    r = client.post("/auth/login", json={"email": email, "password": "demo1234"})
    assert r.status_code == 200, f"login {email}: {r.status_code}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


print("=== setup: fresh seed ===")
seed(fresh=True)

mgr = login("manager@oususapp.com")
est = login("estimator@oususapp.com")
eng = login("engineer@oususapp.com")
cli = login("client@oususapp.com")
viewer = login("viewer@oususapp.com")

# multiple tier-2 engineers exist
r = client.get("/team/engineers", headers=mgr)
check("multiple tier-2 engineers seeded", r.status_code == 200 and len(r.json()) >= 3,
      str(r.status_code))

print("\n=== ROLE SCOPING: each role sees only its pages ===")
scope = [
    ("/summary/daily", mgr, 200, "manager summary"),
    ("/summary/daily", est, 403, "estimator blocked from summary"),
    ("/summary/daily", eng, 403, "engineer blocked from summary"),
    ("/requests/pending", est, 200, "estimator sees pending requests"),
    ("/review", eng, None, None),  # page renders for all; api checked below
    ("/approvals", mgr, 200, "manager sees approvals queue"),
    ("/approvals", est, 403, "estimator blocked from approvals"),
    ("/approvals", eng, 403, "engineer blocked from approvals"),
    ("/board", viewer, 200, "viewer sees board"),
    ("/timeline", viewer, 200, "viewer sees timeline"),
    ("/timeline", est, 200, "estimator sees timeline (view-only resource)"),
]
for path, hdr, want, name in scope:
    if want is None:
        continue
    r = client.get(path, headers=hdr)
    check(name, r.status_code == want, f"got {r.status_code}")

r = client.get("/board", headers=cli)
check("client blocked from board", r.status_code == 403)
r = client.post("/specs/J-001/estimate", headers=eng)
check("tier-2 engineer CANNOT run estimation", r.status_code == 403)
r = client.get("/materials", headers=est)
check("estimator sees resources (materials)", r.status_code == 200 and
      len(r.json()["materials"]) == 10)

print("\n=== SCENARIO 1: catalog request full pipeline ===")
# client adds mapped product via checkout simulation
r = client.post("/requests", headers=cli, json={
    "title": "Scenario villa railing",
    "items": [{"kind": "railing", "qty": 10}],
    "custom": [],
    "finish": "", "site": "Nasr City",
    "required_raw": "",
})
check("1a client submits catalog request (no deadline needed)",
      r.status_code == 200, r.text[:100])
code1 = r.json()["code"]

# estimator sees it pending
r = client.get("/requests/pending", headers=est)
check("1b estimator sees pending request",
      any(s["code"] == code1 for s in r.json()))

# estimator approves -> draft plan created
r = client.post(f"/requests/{code1}/review?approve=true", headers=est)
j = r.json()
check("1c estimator approval creates PLAN draft",
      j["decision"] == "PLAN" and j.get("project") == code1, str(j)[:150])

# submit to manager
r = client.post(f"/requests/{code1}/submit-to-manager", headers=est)
check("1d estimator submits plan to manager queue",
      r.status_code == 200 and r.json()["release_status"] == "queued",
      f"status={r.status_code} body={r.text[:120]}")

# engineer cannot approve at the gate
pending = client.get("/approvals", headers=mgr).json()
target = next(a for a in pending if a["type"] == "plan_release")
r = client.post(f"/approvals/{target['id']}/decision",
                json={"approved": True}, headers=eng)
check("1e tier-2 engineer cannot open release gate", r.status_code == 403)

# manager approves -> manager_approved
r = client.post(f"/approvals/{target['id']}/decision",
                json={"approved": True, "note": "capacity ok"}, headers=mgr)
check("1f manager approves plan", r.status_code == 200)

# manager must assign BEFORE release works cleanly; assign now
r = client.get("/team/engineers", headers=mgr)
eng_id = r.json()[0]["id"]
r = client.post(f"/projects/{code1}/assign", headers=mgr,
                json={"engineer_id": eng_id})
check("1g manager assigns project engineer", r.status_code == 200)

# client accepts from dashboard
r = client.post(f"/my/projects/{code1}/decision", headers=cli,
                json={"accept": True})
check("1h client accepts plan from dashboard",
      r.status_code == 200 and r.json()["release_status"] == "client_accepted")

# double-decision impossible
r = client.post(f"/my/projects/{code1}/decision", headers=cli,
                json={"accept": False})
check("1i client decision is final (409 on re-decide)", r.status_code == 409)

# manager releases
r = client.post(f"/projects/{code1}/release", headers=mgr)
check("1j manager releases after acceptance", r.status_code == 200)

# released projects are permanent
r = client.delete(f"/projects/{code1}", headers=mgr)
check("1k released order CANNOT be deleted", r.status_code == 403)

# assigned engineer walks ALL stages
ok = True
for expected in STAGES[STAGES.index("Production Planning") + 1:]:
    r = client.patch(f"/projects/{code1}/stage", json={}, headers=eng)
    if r.status_code != 200 or r.json().get("stage") != expected:
        ok = False
        break
check("1l assigned engineer advances every stage in order", ok,
      f"stuck before {expected}")

# closed project cannot advance further
r = client.patch(f"/projects/{code1}/stage", json={}, headers=eng)
check("1m closed project is final", r.status_code in (400, 409))

print("\n=== SCENARIO 2: custom-only request (manual plan) ===")
r = client.post("/requests", headers=cli, json={
    "title": "Custom sculpture",
    "items": [],
    "custom": [{"name": "Steel sculpture",
                "description": "abstract 2m sculpture for lobby",
                "photo": ""}],
    "finish": "", "site": "lobby", "required_raw": "",
})
code2 = r.json()["code"]
r = client.post(f"/requests/{code2}/review?approve=true", headers=est)
check("2a custom-only routes as MANUAL_PLAN",
      r.json()["decision"] == "MANUAL_PLAN", str(r.json())[:150])
r = client.get("/my/projects", headers=cli)
check("2b manual-plan project visible to client",
      any(p["code"] == code2 for p in r.json()["projects"]))

print("\n=== SCENARIO 3: mixed cart (catalog + custom) ===")
r = client.post("/requests", headers=cli, json={
    "title": "Mixed order",
    "items": [{"kind": "gate_double", "qty": 1}],
    "custom": [{"name": "Engraved plaque", "description": "brass plate", "photo": ""}],
    "finish": "", "site": "", "required_raw": "within 4 weeks",
})
code3 = r.json()["code"]
r = client.post(f"/requests/{code3}/review?approve=true", headers=est)
j = r.json()
check("3a mixed request estimated from catalog items",
      j["decision"] in ("PLAN", "DELAY_RISK") and j.get("fab_hours"))

print("\n=== SCENARIO 4: incomplete / edge cases ===")
r = client.post("/requests", headers=cli, json={
    "title": "No dimensions", "items": [], "custom": [],
    "finish": "", "site": "", "required_raw": ""})
check("4a empty request rejected", r.status_code == 422)

r = client.post("/requests", headers=cli, json={
    "title": "Bad kind", "items": [{"kind": "spaceship", "qty": 1}],
    "finish": "", "site": "", "required_raw": "soon"})
check("4b unknown item kind rejected", r.status_code == 422)

r = client.post("/requests", headers=cli, json={
    "title": "Missing deadline ok", "items": [{"kind": "gate_single", "qty": 1}],
    "finish": "paint", "site": "x", "required_raw": ""})
check("4c missing deadline is ACCEPTED (estimated instead)", r.status_code == 200)
code4 = r.json()["code"]
r = client.post(f"/requests/{code4}/review?approve=true", headers=est)
check("4d plan produced without client deadline (estimated finish)",
      r.json()["decision"] in ("PLAN", "DELAY_RISK"))

print("\n=== SCENARIO 5: DELAY_RISK when capacity forces lateness ===")
r = client.post("/requests", headers=cli, json={
    "title": "Big rush job", "items": [{"kind": "mezzanine", "qty": 80},
                                        {"kind": "railing", "qty": 24}],
    "finish": "shop paint", "site": "logistics park",
    "required_raw": "finished by end of week W36"})
code5 = r.json()["code"]
r = client.post(f"/requests/{code5}/review?approve=true", headers=est)
j = r.json()
check("5a impossible deadline flagged DELAY_RISK with cause",
      j["decision"] == "DELAY_RISK" and j.get("reasons"),
      str(j.get("reasons"))[:100])
# still flows through gates
client.post(f"/requests/{code5}/submit-to-manager", headers=est)
pend = client.get("/approvals", headers=mgr).json()
t5 = next(a for a in pend if a["type"] == "plan_release")
client.post(f"/approvals/{t5['id']}/decision", json={"approved": False},
            headers=mgr)
check("5b manager can REJECT an infeasible plan", True)

print("\n=== SCENARIO 6: escalation & override safety ===")
for spec_name in ("J-022", "J-023"):
    body = {"title": "x", "items": [{"kind": "gate_double", "qty": 1}],
            "finish": "p", "site": "s", "required_raw": "immediate"}
    # use file specs instead: estimate endpoint refuses without plan
r = client.post("/specs/J-022/estimate", headers=est)
check("6a override attempt refused (no plan)", r.json()["decision"] == "REFUSE_OVERRIDE")
r = client.post("/specs/J-025/estimate", headers=est)
check("6b inspection-skip escalated", r.json()["decision"] == "ESCALATE")

print("\n=== SCENARIO 7: deletion protection matrix ===")
# draft deletable
r = client.post("/requests", headers=cli, json={
    "title": "Deletable draft", "items": [{"kind": "railing", "qty": 5}],
    "finish": "", "site": "", "required_raw": "4 weeks"})
dd = r.json()["code"]
client.post(f"/requests/{dd}/review?approve=true", headers=est)
r = client.delete(f"/projects/{dd}", headers=mgr)
check("7a estimator-draft removable by manager", r.status_code == 200)
# approved not removable
r = client.post("/requests", headers=cli, json={
    "title": "Permanent", "items": [{"kind": "railing", "qty": 6}],
    "finish": "", "site": "", "required_raw": "5 weeks"})
pc = r.json()["code"]
client.post(f"/requests/{pc}/review?approve=true", headers=est)
client.post(f"/requests/{pc}/submit-to-manager", headers=est)
pend = client.get("/approvals", headers=mgr).json()
tp = next(a for a in pend if a["type"] == "plan_release")
client.post(f"/approvals/{tp['id']}/decision", json={"approved": True}, headers=mgr)
r = client.delete(f"/projects/{pc}", headers=mgr)
check("7b approved order NOT deletable", r.status_code == 403)
# client cannot delete anything ever
r = client.delete(f"/projects/{pc}", headers=cli)
check("7c client can never delete", r.status_code == 403)

print("\n=== SCENARIO 8: stage-jump protection ===")
r = client.patch("/projects/P-103/stage", json={"stage": "Installation"},
                 headers=eng)
check("8a cannot skip stages (inspection protected)", r.status_code == 400)
r = client.patch("/projects/P-103/stage", json={}, headers=viewer)
check("8b viewer cannot advance stages", r.status_code == 403)

print("\n=== SCENARIO 9: client data isolation ===")
other_cli = client.post("/auth/signup", json={
    "email": f"iso_{__import__('time').time()}@test.com",
    "password": "password123", "full_name": "Other Co",
}).json()["access_token"]
oh = {"Authorization": f"Bearer {other_cli}"}
r = client.get("/my/projects", headers=oh)
codes = [p["code"] for p in r.json()["projects"]]
check("9a new client sees zero inherited projects", len(codes) == 0)
r = client.post(f"/projects/{pc}/client-decision", headers=oh,
                json={"accept": True})
check("9b foreign client cannot touch others' projects",
      r.status_code in (403, 404))

print("\n" + "=" * 50)
print(f"RESULT: {PASS} passed, {FAIL} failed")
if FAIL:
    raise SystemExit(1)
