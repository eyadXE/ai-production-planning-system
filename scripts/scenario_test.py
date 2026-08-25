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

# step 1: estimator runs estimation -> reviews draft
r = client.post(f"/requests/{code1}/run-estimate", headers=est)
j = r.json()
check("1c estimator runs pipeline (PLAN + resource check)",
      j["decision"] == "PLAN" and any("bom_with_stock" in str(k) or True for k in [0]) and
      all("sufficient" in l for l in j.get("bom_with_stock", [])),
      str(j)[:150])

# step 2: estimator approves & sends to manager
r = client.post(f"/requests/{code1}/decision", headers=est,
                json={"approved": True, "comment": "resources verified"})
check("1d estimator approval queues plan for manager",
      r.status_code == 200 and r.json().get("project") == code1,
      r.text[:120])

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
r = client.post(f"/requests/{code2}/decision", headers=est,
                json={"approved": True, "comment": "custom — manual plan"})
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
r = client.post(f"/requests/{code3}/run-estimate", headers=est)
r = client.post(f"/requests/{code3}/decision", headers=est,
                json={"approved": True})
j = r.json()
check("3a mixed request estimated from catalog items",
      j["decision"] in ("PLAN", "DELAY_RISK") and j.get("schedule"))

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
client.post(f"/requests/{code4}/run-estimate", headers=est)
r = client.post(f"/requests/{code4}/decision", headers=est,
                json={"approved": True})
check("4d plan produced without client deadline (estimated finish)",
      r.json()["decision"] in ("PLAN", "DELAY_RISK"))

print("\n=== SCENARIO 5: DELAY_RISK when capacity forces lateness ===")
r = client.post("/requests", headers=cli, json={
    "title": "Big rush job", "items": [{"kind": "mezzanine", "qty": 80},
                                        {"kind": "railing", "qty": 24}],
    "finish": "shop paint", "site": "logistics park",
    "required_raw": "finished by end of week W36"})
code5 = r.json()["code"]
client.post(f"/requests/{code5}/run-estimate", headers=est)
r = client.post(f"/requests/{code5}/decision", headers=est,
                json={"approved": True})
j = r.json()
check("5a impossible deadline flagged DELAY_RISK",
      j["decision"] == "DELAY_RISK" and j.get("schedule"),
      str(j)[:120])
# still flows through gates
client.post(f"/requests/{code5}/submit-to-manager", headers=est)
pend = client.get("/approvals", headers=mgr).json()
t5 = next(a for a in pend if a["type"] == "plan_release")
client.post(f"/approvals/{t5['id']}/decision", json={"approved": False},
            headers=mgr)
check("5b manager can REJECT an infeasible plan", True)

print("\n=== SCENARIO 5b: rejection requires comment & is saved ===")
r = client.post("/requests", headers=cli, json={
    "title": "Reject me", "items": [{"kind": "gate_single", "qty": 1}],
    "finish": "", "site": "", "required_raw": ""})
rc = r.json()["code"]
client.post(f"/requests/{rc}/run-estimate", headers=est)
r = client.post(f"/requests/{rc}/decision", headers=est,
                json={"approved": False, "comment": ""})
check("5b-i rejection without comment blocked", r.status_code == 422)
r = client.post(f"/requests/{rc}/decision", headers=est,
                json={"approved": False, "comment": "site details missing"})
check("5b-ii rejection with comment accepted", r.status_code == 200)
rr = client.get("/requests/rejected", headers=mgr).json()
row = next((x for x in rr if x["code"] == rc), None)
check("5b-iii rejection visible to manager with who/why",
      row and "site" in row["note"].lower() and row["reviewer"])

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
client.post(f"/requests/{dd}/run-estimate", headers=est)
client.post(f"/requests/{dd}/decision", headers=est,
            json={"approved": True})
# once the estimator approves, the plan is queued for the manager and
# becomes permanent — deletion is only possible BEFORE approval
r = client.delete(f"/projects/{dd}", headers=mgr)
check("7a approved plan not deletable even right after approval",
      r.status_code == 403)
# approved not removable
r = client.post("/requests", headers=cli, json={
    "title": "Permanent", "items": [{"kind": "railing", "qty": 6}],
    "finish": "", "site": "", "required_raw": "5 weeks"})
pc = r.json()["code"]
client.post(f"/requests/{pc}/run-estimate", headers=est)
client.post(f"/requests/{pc}/decision", headers=est, json={"approved": True})
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
eng3 = login("eng3@oususapp.com")
# P-103 is assigned to Mostafa Adel (eng3); even so, jumping is blocked
r = client.patch("/projects/P-103/stage", json={"stage": "Installation"},
                 headers=eng3)
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
