"""
Tests for the modular backend service (backend/main.py).

Covers: auth, users, categories, procurements, participants, payments, chat.
Uses an in-process TestClient with SQLite so no external services are needed.
"""
import sys
import os
import pytest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# Override DB to use in-memory SQLite before importing app
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_modular.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from fastapi.testclient import TestClient
from main import app, Base, engine, SessionLocal, UserModel, hash_password

# Re-create tables for test isolation
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_db():
    """Wipe all tables between tests."""
    yield
    db = SessionLocal()
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
    db.close()


client = TestClient(app)


# ── Helpers ───────────────────────────────────────────────────────────────────

def register_and_login(username="alice", email="alice@example.com", password="pass123"):
    client.post("/auth/register", json={"username": username, "email": email, "password": password})
    r = client.post("/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def make_admin(username="alice"):
    db = SessionLocal()
    user = db.query(UserModel).filter(UserModel.username == username).first()
    if user:
        user.is_admin = True
        db.commit()
    db.close()


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def future_deadline():
    return (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()


# ── Auth ──────────────────────────────────────────────────────────────────────

class TestAuth:
    def test_register_and_login(self):
        r = client.post("/auth/register", json={"username": "bob", "email": "bob@example.com", "password": "secret"})
        assert r.status_code == 201
        assert r.json()["username"] == "bob"
        assert r.json()["balance"] == 0.0

        r2 = client.post("/auth/login", json={"username": "bob", "password": "secret"})
        assert r2.status_code == 200
        assert "access_token" in r2.json()

    def test_duplicate_register_fails(self):
        client.post("/auth/register", json={"username": "bob", "email": "bob@example.com", "password": "s"})
        r = client.post("/auth/register", json={"username": "bob", "email": "bob@example.com", "password": "s"})
        assert r.status_code == 400

    def test_wrong_password(self):
        client.post("/auth/register", json={"username": "bob", "email": "bob@example.com", "password": "correct"})
        r = client.post("/auth/login", json={"username": "bob", "password": "wrong"})
        assert r.status_code == 401

    def test_me(self):
        token = register_and_login("carol", "carol@example.com")
        r = client.get("/auth/me", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["username"] == "carol"


# ── Users (admin only) ────────────────────────────────────────────────────────

class TestUsers:
    def test_list_users_requires_admin(self):
        token = register_and_login()
        r = client.get("/users", headers=auth_headers(token))
        assert r.status_code == 403

    def test_admin_can_list_users(self):
        token = register_and_login()
        make_admin()
        r = client.get("/users", headers=auth_headers(token))
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_toggle_active(self):
        token = register_and_login()
        make_admin()
        user_id = client.get("/auth/me", headers=auth_headers(token)).json()["id"]
        r = client.patch(f"/users/{user_id}", json={"is_active": False}, headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["is_active"] is False


# ── Categories ────────────────────────────────────────────────────────────────

class TestCategories:
    def test_list_categories_public(self):
        r = client.get("/categories")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_create_category_requires_admin(self):
        token = register_and_login()
        r = client.post("/categories", json={"name": "Electronics"}, headers=auth_headers(token))
        assert r.status_code == 403

    def test_admin_creates_category(self):
        token = register_and_login()
        make_admin()
        r = client.post("/categories", json={"name": "Electronics", "icon": "💻"}, headers=auth_headers(token))
        assert r.status_code == 201
        assert r.json()["name"] == "Electronics"

        cats = client.get("/categories").json()
        assert any(c["name"] == "Electronics" for c in cats)


# ── Procurements ──────────────────────────────────────────────────────────────

class TestProcurements:
    def test_list_procurements_public(self):
        r = client.get("/procurements")
        assert r.status_code == 200

    def test_create_procurement(self):
        token = register_and_login()
        r = client.post("/procurements", json={
            "title": "Group Sugar Buy",
            "target_amount": 10000,
            "deadline": future_deadline(),
        }, headers=auth_headers(token))
        assert r.status_code == 201
        data = r.json()
        assert data["title"] == "Group Sugar Buy"
        assert data["status"] == "draft"
        assert data["organizer_username"] == "alice"

    def test_create_requires_auth(self):
        r = client.post("/procurements", json={"title": "x", "target_amount": 100, "deadline": future_deadline()})
        assert r.status_code == 401

    def test_get_procurement(self):
        token = register_and_login()
        proc_id = client.post("/procurements", json={
            "title": "Sugar", "target_amount": 5000, "deadline": future_deadline(),
        }, headers=auth_headers(token)).json()["id"]

        r = client.get(f"/procurements/{proc_id}")
        assert r.status_code == 200
        assert r.json()["title"] == "Sugar"

    def test_update_procurement(self):
        token = register_and_login()
        proc_id = client.post("/procurements", json={
            "title": "Original", "target_amount": 1000, "deadline": future_deadline(),
        }, headers=auth_headers(token)).json()["id"]

        r = client.patch(f"/procurements/{proc_id}", json={"status": "active"}, headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["status"] == "active"

    def test_non_organizer_cannot_update(self):
        token = register_and_login()
        proc_id = client.post("/procurements", json={
            "title": "Mine", "target_amount": 1000, "deadline": future_deadline(),
        }, headers=auth_headers(token)).json()["id"]

        token2 = register_and_login("bob", "bob@example.com")
        r = client.patch(f"/procurements/{proc_id}", json={"status": "cancelled"}, headers=auth_headers(token2))
        assert r.status_code == 403

    def test_filter_by_status(self):
        token = register_and_login()
        client.post("/procurements", json={
            "title": "Draft proc", "target_amount": 100, "deadline": future_deadline(),
        }, headers=auth_headers(token))
        client.patch("/procurements/1", json={"status": "active"}, headers=auth_headers(token))

        r = client.get("/procurements?status=active")
        assert r.status_code == 200
        assert all(p["status"] == "active" for p in r.json())


# ── Participants ──────────────────────────────────────────────────────────────

class TestParticipants:
    def _active_procurement(self, token):
        r = client.post("/procurements", json={
            "title": "Buy Apples",
            "target_amount": 1000,
            "price_per_unit": 50.0,
            "deadline": future_deadline(),
        }, headers=auth_headers(token))
        proc_id = r.json()["id"]
        client.patch(f"/procurements/{proc_id}", json={"status": "active"}, headers=auth_headers(token))
        return proc_id

    def test_join_active_procurement(self):
        token = register_and_login()
        proc_id = self._active_procurement(token)

        token2 = register_and_login("bob", "bob@example.com")
        r = client.post(f"/procurements/{proc_id}/join", json={"quantity": 2}, headers=auth_headers(token2))
        assert r.status_code == 201
        assert r.json()["quantity"] == 2.0
        assert r.json()["amount"] == 100.0

    def test_cannot_join_draft(self):
        token = register_and_login()
        proc_id = client.post("/procurements", json={
            "title": "Draft", "target_amount": 100, "deadline": future_deadline(),
        }, headers=auth_headers(token)).json()["id"]

        token2 = register_and_login("bob", "bob@example.com")
        r = client.post(f"/procurements/{proc_id}/join", json={"quantity": 1}, headers=auth_headers(token2))
        assert r.status_code == 400

    def test_cannot_join_twice(self):
        token = register_and_login()
        proc_id = self._active_procurement(token)

        token2 = register_and_login("bob", "bob@example.com")
        client.post(f"/procurements/{proc_id}/join", json={"quantity": 1}, headers=auth_headers(token2))
        r = client.post(f"/procurements/{proc_id}/join", json={"quantity": 1}, headers=auth_headers(token2))
        assert r.status_code == 400

    def test_leave_procurement(self):
        token = register_and_login()
        proc_id = self._active_procurement(token)

        token2 = register_and_login("bob", "bob@example.com")
        client.post(f"/procurements/{proc_id}/join", json={"quantity": 1}, headers=auth_headers(token2))
        r = client.delete(f"/procurements/{proc_id}/leave", headers=auth_headers(token2))
        assert r.status_code == 204

    def test_current_amount_updates_on_join(self):
        token = register_and_login()
        proc_id = self._active_procurement(token)

        token2 = register_and_login("bob", "bob@example.com")
        client.post(f"/procurements/{proc_id}/join", json={"quantity": 3}, headers=auth_headers(token2))
        proc = client.get(f"/procurements/{proc_id}").json()
        assert proc["current_amount"] == pytest.approx(150.0)


# ── Payments ──────────────────────────────────────────────────────────────────

class TestPayments:
    def test_deposit(self):
        token = register_and_login()
        r = client.post("/payments", json={"payment_type": "deposit", "amount": 500.0}, headers=auth_headers(token))
        assert r.status_code == 201
        assert r.json()["status"] == "succeeded"

        me = client.get("/auth/me", headers=auth_headers(token)).json()
        assert me["balance"] == pytest.approx(500.0)

    def test_withdrawal(self):
        token = register_and_login()
        client.post("/payments", json={"payment_type": "deposit", "amount": 1000.0}, headers=auth_headers(token))
        r = client.post("/payments", json={"payment_type": "withdrawal", "amount": 300.0}, headers=auth_headers(token))
        assert r.status_code == 201
        me = client.get("/auth/me", headers=auth_headers(token)).json()
        assert me["balance"] == pytest.approx(700.0)

    def test_insufficient_balance(self):
        token = register_and_login()
        r = client.post("/payments", json={"payment_type": "withdrawal", "amount": 100.0}, headers=auth_headers(token))
        assert r.status_code == 400

    def test_list_payments(self):
        token = register_and_login()
        client.post("/payments", json={"payment_type": "deposit", "amount": 50.0}, headers=auth_headers(token))
        r = client.get("/payments", headers=auth_headers(token))
        assert r.status_code == 200
        assert len(r.json()) >= 1

    def test_invalid_payment_type(self):
        token = register_and_login()
        r = client.post("/payments", json={"payment_type": "gift", "amount": 10.0}, headers=auth_headers(token))
        assert r.status_code == 400


# ── Chat ──────────────────────────────────────────────────────────────────────

class TestChat:
    def test_empty_room_history(self):
        token = register_and_login()
        r = client.get("/chat/general/messages", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json() == []

    def test_socket_event_persists_message(self):
        client.post("/internal/socket-event", json={
            "type": "message",
            "room": "general",
            "user_id": "1",
            "text": "Hello world",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        token = register_and_login()
        r = client.get("/chat/general/messages", headers=auth_headers(token))
        assert r.status_code == 200
        msgs = r.json()
        assert len(msgs) == 1
        assert msgs[0]["text"] == "Hello world"
        assert msgs[0]["room"] == "general"

    def test_socket_event_with_system_type(self):
        client.post("/internal/socket-event", json={
            "type": "system",
            "room": "sales",
            "user_id": "2",
            "text": "User 2 joined",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        token = register_and_login()
        r = client.get("/chat/sales/messages", headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()[0]["msg_type"] == "system"

    def test_chat_requires_auth(self):
        r = client.get("/chat/general/messages")
        assert r.status_code == 401


# ── Health ────────────────────────────────────────────────────────────────────

class TestHealth:
    def test_health(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        assert r.json()["database"] == "ok"
