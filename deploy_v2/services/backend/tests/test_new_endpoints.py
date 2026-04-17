"""Integration tests for deploy_v2 backend endpoints added in the full migration.

Covers: votes, invitations, notifications, chat POST + unread counters,
reviews, complaints, user search / by-email / balance, procurement receipt /
supplier approval / stop-amount / close, admin analytics / broadcast /
activity log / toggle-featured, and full-text search.

Uses FastAPI's TestClient against a SQLite DB in a temporary path.
"""

import os
import sys
import tempfile
import pytest
from fastapi.testclient import TestClient

# Make the `app` package importable when running `pytest` from the repo root
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


@pytest.fixture()
def client():
    db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db.close()
    os.environ["DATABASE_URL"] = f"sqlite:///{db.name}"
    # Ensure a fresh import per test for DB isolation
    for mod in list(sys.modules):
        if mod.startswith("app"):
            sys.modules.pop(mod, None)
    from app.main import app, SessionLocal, UserModel  # noqa: WPS433

    c = TestClient(app)
    # Register alice (admin) and bob (user)
    c.post("/auth/register", json={"username": "alice", "email": "alice@ex.com", "password": "secretpw"})
    with SessionLocal() as s:
        u = s.query(UserModel).filter_by(username="alice").first()
        u.is_admin = True
        s.commit()
    c.post("/auth/register", json={"username": "bob", "email": "bob@ex.com", "password": "secretpw"})
    tok_a = c.post("/auth/login", json={"username": "alice", "password": "secretpw"}).json()["access_token"]
    tok_b = c.post("/auth/login", json={"username": "bob", "password": "secretpw"}).json()["access_token"]

    yield c, {"Authorization": f"Bearer {tok_a}"}, {"Authorization": f"Bearer {tok_b}"}
    try:
        os.unlink(db.name)
    except OSError:
        pass


def test_user_search_and_by_email(client):
    c, ha, hb = client
    r = c.get("/users/search?q=ali", headers=hb)
    assert r.status_code == 200
    assert any(u["username"] == "alice" for u in r.json())

    r = c.get("/users/by-email/alice@ex.com", headers=ha)
    assert r.status_code == 200
    assert r.json()["username"] == "alice"

    # Non-admin cannot use by-email
    r = c.get("/users/by-email/alice@ex.com", headers=hb)
    assert r.status_code == 403


def test_admin_balance_update(client):
    c, ha, hb = client
    # Bob's initial balance
    r = c.get("/users/2/balance", headers=hb)
    assert r.status_code == 200
    assert r.json()["balance"] == 0.0

    # Admin tops up
    r = c.post("/users/2/balance", json={"amount": 150.0, "reason": "test"}, headers=ha)
    assert r.status_code == 200, r.text
    assert r.json()["balance"] == 150.0


def _make_active_procurement(client, headers):
    r = client.post("/procurements", json={
        "title": "Olive oil bulk",
        "description": "Great deal on olive oil",
        "target_amount": 500.0,
        "price_per_unit": 5.0,
        "commission_percent": 10.0,
        "deadline": "2030-01-01T00:00:00",
        "city": "Moscow",
    }, headers=headers)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    r = client.patch(f"/procurements/{pid}", json={"status": "active"}, headers=headers)
    assert r.status_code == 200
    return pid


def test_receipt_and_stop_amount_and_close(client):
    c, ha, hb = client
    pid = _make_active_procurement(c, ha)

    # Bob joins with quantity 3 → amount = 15.0
    r = c.post(f"/procurements/{pid}/join", json={"quantity": 3.0}, headers=hb)
    assert r.status_code == 201

    # Receipt
    r = c.get(f"/procurements/{pid}/receipt", headers=ha)
    assert r.status_code == 200
    data = r.json()
    assert data["participant_count"] == 1
    assert data["total_amount"] == 15.0
    assert data["commission_amount"] == 1.5
    assert data["grand_total"] == 16.5

    # Stop-at-amount below current → triggers 'stopped'
    r = c.post(f"/procurements/{pid}/stop-amount", json={"stop_at_amount": 10.0}, headers=ha)
    assert r.status_code == 200
    assert r.json()["status"] == "stopped"

    # Close
    r = c.post(f"/procurements/{pid}/close", json={"status": "completed"}, headers=ha)
    assert r.status_code == 200
    assert r.json()["status"] == "completed"


def test_votes_and_invitations_and_notifications(client):
    c, ha, hb = client
    pid = _make_active_procurement(c, ha)

    # Invite bob → should create a notification
    r = c.post(f"/procurements/{pid}/invitations", json={"invitee_id": 2}, headers=ha)
    assert r.status_code == 201
    inv_id = r.json()["id"]

    # Bob sees the invitation & notification
    r = c.get("/invitations", headers=hb)
    assert r.status_code == 200
    assert any(i["id"] == inv_id for i in r.json())

    r = c.get("/notifications", headers=hb)
    assert r.status_code == 200
    assert len(r.json()) >= 1

    # Unread count reflects new notifications
    r = c.get("/notifications/unread-count", headers=hb)
    assert r.status_code == 200
    assert r.json()["count"] >= 1

    # Bob accepts the invitation
    r = c.post(f"/invitations/{inv_id}/respond?accept=true", headers=hb)
    assert r.status_code == 200
    assert r.json()["status"] == "accepted"

    # Bob joins and votes
    c.post(f"/procurements/{pid}/join", json={"quantity": 1.0}, headers=hb)
    r = c.post(f"/procurements/{pid}/votes", json={"option": "supplier-A"}, headers=hb)
    assert r.status_code == 201
    # Re-casting overwrites
    r = c.post(f"/procurements/{pid}/votes", json={"option": "supplier-B"}, headers=hb)
    assert r.status_code == 201

    r = c.get(f"/procurements/{pid}/votes", headers=hb)
    assert r.status_code == 200
    data = r.json()
    assert data["total_votes"] == 1
    assert data["tally"] == {"supplier-B": 1}
    assert data["winner"] == "supplier-B"

    # Mark all notifications read
    r = c.post("/notifications/mark-all-read", headers=hb)
    assert r.status_code == 204
    r = c.get("/notifications/unread-count", headers=hb)
    assert r.json()["count"] == 0


def test_chat_message_post_and_unread(client):
    c, ha, hb = client
    room = "procurement_1"
    # alice posts
    r = c.post(f"/chat/{room}/messages", json={"text": "Hello chat"}, headers=ha)
    assert r.status_code == 201

    # bob sees the unread count
    r = c.get(f"/chat/{room}/unread-count", headers=hb)
    assert r.status_code == 200
    assert r.json()["count"] == 1

    r = c.post(f"/chat/{room}/mark-read", headers=hb)
    assert r.status_code == 204

    r = c.get(f"/chat/{room}/unread-count", headers=hb)
    assert r.json()["count"] == 0


def test_reviews_and_complaints(client):
    c, ha, hb = client
    # Bob reviews alice
    r = c.post("/reviews", json={"target_user_id": 1, "rating": 4, "body": "Great"}, headers=hb)
    assert r.status_code == 201

    # Self-review forbidden
    r = c.post("/reviews", json={"target_user_id": 2, "rating": 5}, headers=hb)
    assert r.status_code == 400

    # Invalid rating
    r = c.post("/reviews", json={"target_user_id": 1, "rating": 9}, headers=hb)
    assert r.status_code == 400

    # User reviews listing + rating
    r = c.get("/users/1/reviews")
    assert r.status_code == 200
    assert len(r.json()) == 1

    r = c.get("/users/1/rating")
    assert r.status_code == 200
    assert r.json()["average"] == 4.0
    assert r.json()["count"] == 1

    # Bob files a complaint
    r = c.post("/complaints", json={"subject": "spam", "body": "annoying"}, headers=hb)
    assert r.status_code == 201
    cid = r.json()["id"]

    # Admin lists all (including bob's)
    r = c.get("/complaints", headers=ha)
    assert r.status_code == 200
    assert any(x["id"] == cid for x in r.json())

    # Non-admin only sees their own (mine=true)
    r = c.get("/complaints?mine=true", headers=hb)
    assert r.status_code == 200
    assert all(x["reporter_id"] == 2 for x in r.json())

    # Admin resolves
    r = c.patch(f"/complaints/{cid}", json={"status": "resolved", "resolution": "ok"}, headers=ha)
    assert r.status_code == 200
    assert r.json()["status"] == "resolved"


def test_admin_analytics_broadcast_activity(client):
    c, ha, hb = client
    _ = _make_active_procurement(c, ha)

    r = c.get("/admin/analytics", headers=ha)
    assert r.status_code == 200
    data = r.json()
    assert "status_breakdown" in data
    assert data["new_procurements_30d"] >= 1

    # Broadcast reaches active users
    r = c.post("/admin/broadcast", json={"title": "News", "body": "Hello"}, headers=ha)
    assert r.status_code == 200
    assert r.json()["sent"] >= 2

    # Activity log records admin balance adjustments (run one)
    c.post("/users/2/balance", json={"amount": 5.0, "reason": "gift"}, headers=ha)
    r = c.get("/admin/activity-log", headers=ha)
    assert r.status_code == 200
    assert any(row["action"] == "balance_adjusted" for row in r.json())


def test_search_procurements_and_toggle_featured(client):
    c, ha, _ = client
    pid = _make_active_procurement(c, ha)

    r = c.get("/search/procurements?q=olive")
    assert r.status_code == 200
    assert any(p["id"] == pid for p in r.json())

    r = c.get("/search/procurements?city=Moscow&status=active")
    assert r.status_code == 200
    assert any(p["id"] == pid for p in r.json())

    # Toggle featured
    r = c.post(f"/procurements/{pid}/toggle-featured", headers=ha)
    assert r.status_code == 200
    assert r.json()["is_featured"] is True
