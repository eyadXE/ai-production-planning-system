"""Auth API tests: signup/login/me + role guards.

Uses a temp SQLite DB and FastAPI TestClient.
"""

import os
import tempfile

os.environ["OUSUS_DB"] = os.path.join(tempfile.gettempdir(), "ousus_auth_test.db")

from fastapi.testclient import TestClient  # noqa: E402

from finalproject.api.main import app  # noqa: E402
from finalproject.db.seed import seed  # noqa: E402

client = TestClient(app)


def setup_module(module):
    seed(fresh=True)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200


def test_login_seeded_manager():
    r = client.post(
        "/auth/login",
        json={"email": "manager@oususapp.com", "password": "demo1234"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "manager"


def test_signup_client_with_account():
    r = client.post(
        "/auth/signup",
        json={
            "email": "newclient@rowad.com",
            "password": "supersecret1",
            "full_name": "Rowad Contact",
            "role": "client",
            "account_code": "AC-01",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["account_id"] is not None

    me = client.get(
        "/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == "newclient@rowad.com"


def test_signup_client_requires_account_code():
    r = client.post(
        "/auth/signup",
        json={
            "email": "noclient@x.com",
            "password": "supersecret1",
            "full_name": "X",
            "role": "client",
        },
    )
    assert r.status_code == 400


def test_signup_duplicate_email_conflict():
    payload = {
        "email": "dup@oususapp.com",
        "password": "supersecret1",
        "full_name": "Dup",
        "role": "client",
        "account_code": "AC-03",
    }
    assert client.post("/auth/signup", json=payload).status_code == 201
    assert client.post("/auth/signup", json=payload).status_code == 409


def test_signup_staff_roles_forbidden():
    """Staff accounts are admin-provisioned — self-registration is refused."""
    r = client.post("/auth/signup", json={
        "email": "selfmade-manager@oususapp.com",
        "password": "supersecret1", "full_name": "Sneaky", "role": "manager",
    })
    assert r.status_code == 403


def test_login_wrong_password():
    r = client.post(
        "/auth/login", json={"email": "manager@oususapp.com", "password": "wrong-pass"}
    )
    assert r.status_code == 401


def test_me_requires_token():
    assert client.get("/auth/me").status_code == 401
    assert (
        client.get("/auth/me", headers={"Authorization": "Bearer garbage"}).status_code
        == 401
    )


def test_role_guard():
    login = client.post(
        "/auth/login", json={"email": "client@oususapp.com", "password": "demo1234"}
    ).json()["access_token"]
    manager_login = client.post(
        "/auth/login", json={"email": "manager@oususapp.com", "password": "demo1234"}
    ).json()["access_token"]

    from fastapi import Depends

    from finalproject.auth.dependencies import require_roles
    from finalproject.api.main import app

    @app.get("/test/manager-only", tags=["test"])
    def manager_only(user=Depends(require_roles("manager"))):
        return {"ok": True}

    forbidden = client.get(
        "/test/manager-only", headers={"Authorization": f"Bearer {login}"}
    )
    assert forbidden.status_code == 403
    allowed = client.get(
        "/test/manager-only", headers={"Authorization": f"Bearer {manager_login}"}
    )
    assert allowed.status_code == 200
