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
check("4b manager approves request -> offer queued for client",
      s == 200 and r.get("release_status") == "queued",
      str(r)[:120])

# Verify board shows queued (waiting on the client)
_, board = req("/board", "GET", MGR)
queued_items = [p for col in board["columns"].values() for p in col
                if p["code"] == code]
check("4c board shows AWAITING CLIENT",
      queued_items and queued_items[0]["release_status"] == "queued")

# Step 5: Client accepts from dashboard -> ONLY NOW it is releasable
s, j = req(f"/my/projects/{code}/decision", "POST", CLI, {"accept": True})
check("5 client accepts offer",
      s == 200 and j.get("release_status") == "client_accepted")

# not in the timeline yet — only released projects appear
_, tl = req("/timeline", "GET", MGR)
check("5b timeline hides unreleased project",
      all(p["code"] != code for p in tl["projects"]))

# release without an assigned engineer fails
s, _ = req(f"/projects/{code}/release", "POST", MGR)
check("5c release blocked until engineer assigned", s == 409)

# Step 6: Assign engineer on the Release page flow
_, eng_list = req("/team/engineers", "GET", MGR)
assigned_eng_email = eng_list[0]["email"]
s, _ = req(f"/projects/{code}/assign", "POST", MGR,
           {"engineer_id": eng_list[0]["id"]})
check("6 manager assigns engineer", s == 200)

# Step 7: Manager releases -> NOW it appears in the timeline
s, j = req(f"/projects/{code}/release", "POST", MGR)
check("7 manager releases after client acceptance",
      s == 200 and j.get("release_status") == "released")
_, tl = req("/timeline", "GET", MGR)
check("7b released project appears in timeline",
      any(p["code"] == code for p in tl["projects"]))

# Step 8: Cannot delete released order
s, _ = req(f"/projects/{code}", "DELETE", MGR)
check("8 released order cannot be deleted", s == 403)

# Step 9: Assigned engineer walks stagesENG = MGR  # manager can always advance
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

print("\n=== CUSTOM TWO-LEVEL PIPELINE ===")
s, r = req("/requests", "POST", CLI, {
    "title": "Custom flow test", "items": [],
    "custom": [{"name": "Art gate", "description": "decorative 3 m gate"}],
    "finish": "", "site": "Giza", "required_raw": ""})
cc = r["code"]
check("C1 client submits custom request", s == 200 and cc)

# run-estimate returns NO fabricated figures
s, j = req(f"/requests/{cc}/run-estimate", "POST", EST)
check("C2 manual plan has no engine figures",
      j.get("decision") == "MANUAL_PLAN" and j.get("needs_manual_planning")
      and not j.get("final_price_egp"), str(j)[:120])

# plain estimator approve is blocked
s, _ = req(f"/requests/{cc}/decision", "POST", EST, {"approved": True})
check("C3 approve blocked before engineering input", s == 409)

# level 1: estimator fills scope + hours
s, j = req(f"/requests/{cc}/custom/estimator-info", "POST", EST,
           {"scope": "decorative gate 3m SHS frame",
            "materials_note": "SHS + mesh, shop paint",
            "fab_hours": 80, "install_hours": 20})
check("C4 estimator completes level 1",
      s == 200 and j.get("release_status") == "pending_manager_review",
      str(j)[:120])

# manager must complete pricing (level 2) before approving
s, _ = req(f"/requests/{cc}/manager-decision", "POST", MGR,
           {"approved": True})
check("C5 manager pricing required", s == 422)

s, j = req(f"/requests/{cc}/manager-decision", "POST", MGR,
           {"approved": True, "material_cost_egp": 12000,
            "margin_applied": 22, "planned_finish": "2026-11-15"})
check("C6 manager completes level 2 -> offer to client",
      s == 200 and j.get("release_status") == "queued", str(j)[:120])

s, j = req(f"/my/projects/{cc}/decision", "POST", CLI, {"accept": True})
check("C7 client accepts custom offer",
      s == 200 and j.get("release_status") == "client_accepted")

_, eng_list = req("/team/engineers", "GET", MGR)
req(f"/projects/{cc}/assign", "POST", MGR,
    {"engineer_id": eng_list[0]["id"]})
s, j = req(f"/projects/{cc}/release", "POST", MGR)
check("C8 assign & release custom order",
      s == 200 and j.get("release_status") == "released")

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
