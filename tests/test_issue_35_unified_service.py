"""
Tests for the unified single-container GroupBuy service (app/main.py).

Covers: all service roles merged into one FastAPI app —
  REST API (auth, users, procurements, payments, chat),
  WebSocket broker endpoints (history, users),
  Admin panel routes,
  Analytics endpoints.

Uses in-process TestClient with SQLite — no external services required.
"""
import sys
import os
import pytest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

os.environ["DATABASE_URL"] = "sqlite:///./test_unified.db"
os.environ["SECRET_KEY"] = "test-secret-unified"
os.environ["REDIS_URL"] = ""  # disable Redis for unit tests

from fastapi.testclient import TestClient
from main import app, Base, engine, SessionLocal, UserModel, hash_password

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_db():
    yield
    db = SessionLocal()
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
    db.close()


client = TestClient(app)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _register_and_login(username="alice", email="alice@example.com", password="pass123"):
    client.post("/api/auth/register", json={"username": username, "email": email, "password": password})
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _make_admin(username="alice"):
    db = SessionLocal()
    user = db.query(UserModel).filter(UserModel.username == username).first()
    if user:
        user.is_admin = True
        db.commit()
    db.close()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── Health ─────────────────────────────────────────────────────────────────────

def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "database" in data
    assert "websocket_rooms" in data
    assert "analytics_events" in data


# ── Auth ───────────────────────────────────────────────────────────────────────

def test_register_and_login():
    r = client.post("/api/auth/register", json={"username": "bob", "email": "bob@example.com", "password": "secret"})
    assert r.status_code == 201
    assert r.json()["username"] == "bob"

    r = client.post("/api/auth/login", json={"username": "bob", "password": "secret"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_register_duplicate():
    client.post("/api/auth/register", json={"username": "alice", "email": "alice@example.com", "password": "p"})
    r = client.post("/api/auth/register", json={"username": "alice", "email": "alice2@example.com", "password": "p"})
    assert r.status_code == 400


def test_login_wrong_password():
    client.post("/api/auth/register", json={"username": "carol", "email": "carol@e.com", "password": "right"})
    r = client.post("/api/auth/login", json={"username": "carol", "password": "wrong"})
    assert r.status_code == 401


def test_me():
    token = _register_and_login()
    r = client.get("/api/auth/me", headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["username"] == "alice"


# ── Users (admin) ──────────────────────────────────────────────────────────────

def test_list_users_requires_admin():
    token = _register_and_login()
    r = client.get("/api/users", headers=_auth(token))
    assert r.status_code == 403


def test_list_users_as_admin():
    token = _register_and_login()
    _make_admin("alice")
    r = client.get("/api/users", headers=_auth(token))
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_update_user_as_admin():
    token = _register_and_login()
    _make_admin("alice")
    users = client.get("/api/users", headers=_auth(token)).json()
    user_id = users[0]["id"]
    r = client.patch(f"/api/users/{user_id}", json={"is_active": False}, headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_delete_user_as_admin():
    _register_and_login("delme", "delme@e.com")
    admin_token = _register_and_login("admin", "admin@e.com")
    _make_admin("admin")
    users = client.get("/api/users", headers=_auth(admin_token)).json()
    victim = next(u for u in users if u["username"] == "delme")
    r = client.delete(f"/api/users/{victim['id']}", headers=_auth(admin_token))
    assert r.status_code == 204


# ── Categories ─────────────────────────────────────────────────────────────────

def test_categories_crud():
    token = _register_and_login()
    _make_admin("alice")

    r = client.post("/api/categories", json={"name": "Electronics"}, headers=_auth(token))
    assert r.status_code == 201
    cat_id = r.json()["id"]

    r = client.get("/api/categories")
    assert r.status_code == 200
    assert any(c["id"] == cat_id for c in r.json())

    r = client.delete(f"/api/categories/{cat_id}", headers=_auth(token))
    assert r.status_code == 204


# ── Procurements ───────────────────────────────────────────────────────────────

def test_procurement_lifecycle():
    token = _register_and_login()
    deadline = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    r = client.post("/api/procurements", json={
        "title": "Group buy laptops",
        "target_amount": 1000.0,
        "deadline": deadline,
    }, headers=_auth(token))
    assert r.status_code == 201
    proc_id = r.json()["id"]

    r = client.get(f"/api/procurements/{proc_id}")
    assert r.status_code == 200
    assert r.json()["title"] == "Group buy laptops"

    r = client.patch(f"/api/procurements/{proc_id}", json={"status": "active"}, headers=_auth(token))
    assert r.status_code == 200
    assert r.json()["status"] == "active"

    r = client.delete(f"/api/procurements/{proc_id}", headers=_auth(token))
    assert r.status_code == 204


def test_procurement_list_filter():
    token = _register_and_login()
    _make_admin("alice")
    deadline = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

    client.post("/api/procurements", json={
        "title": "Active proc", "target_amount": 100.0, "deadline": deadline,
        "status": "active",
    }, headers=_auth(token))

    r = client.get("/api/procurements?status=draft")
    assert r.status_code == 200


# ── Payments ───────────────────────────────────────────────────────────────────

def test_deposit_and_balance():
    token = _register_and_login()

    r = client.post("/api/payments", json={"payment_type": "deposit", "amount": 500.0}, headers=_auth(token))
    assert r.status_code == 201
    assert r.json()["status"] == "succeeded"

    r = client.get("/api/auth/me", headers=_auth(token))
    assert r.json()["balance"] == 500.0


def test_withdrawal_insufficient_balance():
    token = _register_and_login()
    r = client.post("/api/payments", json={"payment_type": "withdrawal", "amount": 9999.0}, headers=_auth(token))
    assert r.status_code == 400


def test_invalid_payment_type():
    token = _register_and_login()
    r = client.post("/api/payments", json={"payment_type": "refund", "amount": 10.0}, headers=_auth(token))
    assert r.status_code == 400


# ── Chat ───────────────────────────────────────────────────────────────────────

def test_chat_messages_require_auth():
    r = client.get("/api/chat/room-1/messages")
    assert r.status_code in (401, 403)


def test_chat_messages_empty():
    token = _register_and_login()
    r = client.get("/api/chat/room-1/messages", headers=_auth(token))
    assert r.status_code == 200
    assert r.json() == []


def test_socket_event_persists_chat():
    token = _register_and_login()
    db = SessionLocal()
    user = db.query(UserModel).filter(UserModel.username == "alice").first()
    user_id = str(user.id)
    db.close()

    now = datetime.now(timezone.utc).isoformat()
    r = client.post("/api/internal/socket-event", json={
        "type": "message", "room": "room-1", "user_id": user_id,
        "text": "Hello from socket", "timestamp": now,
    })
    assert r.status_code == 204

    r = client.get("/api/chat/room-1/messages", headers=_auth(token))
    assert r.status_code == 200
    msgs = r.json()
    assert any(m["text"] == "Hello from socket" for m in msgs)


# ── WebSocket broker (REST helpers) ────────────────────────────────────────────

def test_ws_history_empty():
    r = client.get("/rooms/no-room/history")
    assert r.status_code == 200
    assert r.json() == []


def test_ws_users_empty():
    r = client.get("/rooms/no-room/users")
    assert r.status_code == 200
    assert r.json() == []


# ── Analytics ──────────────────────────────────────────────────────────────────

def test_analytics_health():
    r = client.get("/analytics/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_analytics_summary_empty():
    r = client.get("/analytics/stats/summary")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total_events"] == 0


def test_analytics_ingest_and_query():
    r = client.post("/analytics/events", json={
        "topic": "purchase.created",
        "payload": {"purchaseId": "p-001", "userId": "u-1"},
    })
    assert r.status_code == 200

    r = client.get("/analytics/stats/summary")
    assert r.json()["data"]["total_events"] == 1
    assert r.json()["data"]["purchases_tracked"] == 1


def test_analytics_purchases_download():
    r = client.get("/analytics/reports/purchases/download")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]


def test_analytics_payments_download():
    r = client.get("/analytics/reports/payments/download")
    assert r.status_code == 200
    assert "csv" in r.headers["content-type"]


# ── Swagger / OpenAPI ──────────────────────────────────────────────────────────

def test_openapi_schema():
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    assert "/api/auth/login" in paths
    # WebSocket routes are not included in OpenAPI schema by FastAPI
    assert "/analytics/health" in paths


def test_swagger_ui():
    r = client.get("/docs")
    assert r.status_code == 200
    assert "swagger" in r.text.lower()


# ── docker-compose.single.yml sanity ──────────────────────────────────────────

def test_single_compose_file_exists():
    root = os.path.join(os.path.dirname(__file__), "..")
    path = os.path.join(root, "docker-compose.single.yml")
    assert os.path.isfile(path), "docker-compose.single.yml not found"


def test_single_compose_has_one_app_service():
    import re
    root = os.path.join(os.path.dirname(__file__), "..")
    path = os.path.join(root, "docker-compose.single.yml")
    with open(path) as f:
        content = f.read()
    # Must have the 'app' service (single application container)
    assert re.search(r"^\s+app:", content, re.MULTILINE), "No 'app' service found"
    # Must not contain Go, Node, NestJS image references
    for forbidden in ("golang:", "node:", "nestjs"):
        assert forbidden not in content, f"Found '{forbidden}' in single compose file"


def test_single_compose_references_app_build():
    root = os.path.join(os.path.dirname(__file__), "..")
    path = os.path.join(root, "docker-compose.single.yml")
    with open(path) as f:
        content = f.read()
    assert "./app" in content, "App service must build from ./app directory"
