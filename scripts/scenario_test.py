"""Full 5-gate pipeline verification — every step checked explicitly."""
import json, urllib.request, urllib.error

STAGES = ("Award", "Engineering", "Procurement", "Production Planning",
          "Fabrication", "Quality Inspection", "Finishing", "Delivery",
          "Installation", "Closed")

B = "http://localhost:8000"
PASS = FAIL = 0

def req(path, method="GET", token=None, body=None):
    r = urllib.request.Request(B + path, method=method,
        headers={"Content-Type": "application/json",
                 **({"Authorization": f"Bearer {token}"} if token else {})},
        data=json.dumps(body).encode() if body is not None else None)
    try:
        resp = urllib.request.urlopen(r)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {}

def check(name, ok, extra=""):
    global PASS, FAIL
    if ok: PASS += 1; print(f"  ✓ {name}")
    else: FAIL += 1; print(f"  ✗ {name} {extra}")

def login(email):
    _, d = req("/auth/login", "POST", body={"email": email, "password": "demo1234"})
    return d["access_token"]

MGR = login("manager@oususapp.com")
EST = login("estimator@oususapp.com")

CLI = login("client@oususapp.com")
ENG = login("engineer@oususapp.com")

print("\n=== FULL PIPELINE ===")

# Step 1: Client submits
s, r = req("/requests", "POST", CLI, {
    "title": "Pipeline test", "items": [{"kind": "railing", "qty": 10}],
    "custom": [], "finish": "", "site": "Test site",
    "required_raw": "within 6 weeks"})
code = r["code"]
check("1 client submits", s == 200 and code)

# Step 2: Estimator runs estimation
s, j = req(f"/requests/{code}/run-estimate", "POST", EST)
check("2 estimator runs estimation (PLAN)", j["decision"] == "PLAN" and j.get("fab_hours"))
check("2b resource check included", isinstance(j.get("bom_with_stock"), list))

# Step 3: Estimator approves & sends to manager
s, r = req(f"/requests/{code}/decision", "POST", EST,
           {"approved": True, "comment": ""})
check("3 estimator approves -> project created",
      s == 200 and r.get("project") == code
      and r.get("release_status") == "pending_manager_review")

# Step 4: Manager sees it in Requests and approves it there
s, awt = req("/requests/awaiting-decision", "GET", MGR)
check("4 request awaiting manager decision in requests",
      s == 200 and any(a["code"] == code for a in awt), str(awt)[:120])

# estimator may NOT decide — manager only
s, _ = req(f"/requests/{code}/manager-decision", "POST", EST,
           {"approved": True})
check("4a estimator cannot decide request", s == 403)

s, r = req(f"/requests/{code}/manager-decision", "POST", MGR,
           {"approved": True})
aid = r.get("approval_id", 0)
check("4b manager approves request -> plan queued for client",
      s == 200 and r.get("release_status") == "queued" and aid > 0,
      str(r)[:120])

# Verify board shows queued (waiting on the client)
_, board = req("/board", "GET", MGR)
queued_items = [p for col in board["columns"].values() for p in col
                if p["code"] == code]
check("4c board shows queued (awaiting client)",
      queued_items and queued_items[0]["release_status"] == "queued")

# The release gate stays shut until the client accepts
s, _ = req(f"/approvals/{aid}/decision", "POST", MGR, {"approved": True})
check("4d gate blocked before client acceptance", s == 409)

# Step 5: Client accepts from dashboard
s, j = req(f"/my/projects/{code}/decision", "POST", CLI, {"accept": True})
check("5 client accepts plan",
      s == 200 and j.get("release_status") == "client_accepted")

# Step 6: Manager opens the release gate
s, j = req(f"/approvals/{aid}/decision", "POST", MGR,
           {"approved": True, "note": "verified"})
check("6 manager approves at the gate",
      s == 200 and j["decision"] == "approved")

# Verify status is manager_approved
_, board = req("/board", "GET", MGR)
items = [p for col in board["columns"].values() for p in col if p["code"] == code]
check("6b release_status is manager_approved",
      items and items[0]["release_status"] == "manager_approved",
      str(items[0]["release_status"] if items else "?"))

# not in the timeline yet — only released projects appear
_, tl = req("/timeline", "GET", MGR)
check("6c timeline hides unreleased project",
      all(p["code"] != code for p in tl["projects"]))

# Step 7: Assign engineer BEFORE release
_, eng_list = req("/team/engineers", "GET", MGR)
assigned_eng_email = eng_list[0]["email"]
s, _ = req(f"/projects/{code}/assign", "POST", MGR,
           {"engineer_id": eng_list[0]["id"]})
check("7 manager assigns engineer", s == 200)

# Step 8: Manager releases -> NOW it appears in the timeline
s, j = req(f"/projects/{code}/release", "POST", MGR)
check("8 manager releases after gate",
      s == 200 and j.get("release_status") == "released")
_, tl = req("/timeline", "GET", MGR)
check("8b released project appears in timeline",
      any(p["code"] == code for p in tl["projects"]))

# Step 9: Cannot delete released order
s, _ = req(f"/projects/{code}", "DELETE", MGR)
check("9 released order cannot be deleted", s == 403)

# Step 10: Assigned engineer walks stagesENG = MGR  # manager can always advance
for expected in STAGES[1:]:
    s, j = req(f"/projects/{code}/stage", "PATCH", ENG, {})
    check(f"10 advance -> {j.get('stage', expected)}",
          s == 200 and j.get("stage") == expected)

# Step 11: Client sees project with estimated finish in dashboard
_, my = req("/my/projects", "GET", CLI)
mine = next((p for p in my["projects"] if p["code"] == code), None)
check("11 client sees project in portal",
      mine is not None and mine.get("estimated_finish") is not None,
      str(mine)[:120] if mine else "not found")

# Step 12: Notifications exist
_, notes = req("/notifications/mine", "GET", CLI)
check("12 client has notifications", len(notes) > 0)

print("\n=== REJECTION SCENARIO ===")
s, r = req("/requests", "POST", CLI, {
    "title": "Reject test", "items": [{"kind": "railing", "qty": 5}],
    "custom": [], "finish": "", "site": "", "required_raw": ""})
rc = r["code"]
req(f"/requests/{rc}/run-estimate", "POST", EST)

# reject without comment -> 422
s, _ = req(f"/requests/{rc}/decision", "POST", EST,
           {"approved": False, "comment": ""})
check("R1 rejection without comment blocked", s == 422)

# reject with comment
s, j = req(f"/requests/{rc}/decision", "POST", EST,
           {"approved": False, "comment": "missing site details"})
check("R2 rejection accepted with comment", s == 200 and j.get("status") == "rejected")

# manager can see rejection
rr = req("/requests/rejected", "GET", MGR)[1]
row = next((x for x in rr if x["code"] == rc), None)
check("R3 rejection visible to manager with reason",
      row is not None and bool(row.get("note")))

print("\n=== NEGATIVE TESTS ===")
# viewer cannot advance
s, _ = req("/projects/P-101/stage", "PATCH", login("viewer@oususapp.com"), {})
check("N1 viewer cannot advance stages", s == 403)
# estimator cannot approve at gate
s, _ = req("/approvals/999/decision", "POST", EST, {"approved": True})
check("N2 estimator cannot open release gate", s == 403)
# client cannot access board
s, _ = req("/board", "GET", CLI)
check("N3 client cannot see full board", s == 403)
# unauthenticated cannot do anything
s, _ = req("/board")
check("N4 unauthenticated blocked", s == 401 or s == 403)

print(f"\n{'='*50}")
print(f"RESULT: {PASS} passed, {FAIL} failed, {PASS+FAIL} total")
if FAIL:
    raise SystemExit(1)
