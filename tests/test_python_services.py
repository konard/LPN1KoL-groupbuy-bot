"""
Tests for Python FastAPI microservices migration.

These tests use httpx.AsyncClient with an in-process ASGI transport so they
run without any external dependencies (no Postgres, Redis, Kafka required).
DB calls are patched via unittest.mock.
"""

import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _reload_app(service_path: str):
    """Remove 'app' from sys.modules and insert the service path so a fresh
    import picks up the correct service's app.py."""
    sys.modules.pop("app", None)
    if service_path not in sys.path:
        sys.path.insert(0, service_path)


# ─── Gateway ──────────────────────────────────────────────────────────────────

class TestGateway:
    def setup_method(self):
        sys.modules.pop("main", None)
        gw_path = "/tmp/gh-issue-solver-1777665163791/services/gateway"
        if gw_path not in sys.path:
            sys.path.insert(0, gw_path)
        import main as gw_main
        self.app = gw_main.app
        self.client = TestClient(self.app, raise_server_exceptions=False)

    def test_health(self):
        resp = self.client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert resp.json()["service"] == "gateway"

    def test_rate_limiter_allows_first_request(self):
        """Rate limiter should not block a single request."""
        import main as gw_main
        # Reset bucket state
        gw_main._buckets.clear()
        assert gw_main._check_rate_limit("1.2.3.4") is True

    def test_rate_limiter_blocks_after_limit(self):
        """Rate limiter should block after RPM is exhausted."""
        import main as gw_main
        gw_main._buckets.clear()
        gw_main.RATE_LIMIT_RPM = 2
        # Drain all tokens
        for _ in range(10):
            gw_main._check_rate_limit("192.0.2.1")
        assert gw_main._check_rate_limit("192.0.2.1") is False
        # Restore
        gw_main.RATE_LIMIT_RPM = 60

    def test_voting_rate_limit_is_higher(self):
        """Voting endpoints get a separate, higher-capacity bucket."""
        import main as gw_main
        assert gw_main.VOTING_RATE_LIMIT_RPM >= gw_main.RATE_LIMIT_RPM

    def test_resolve_service_auth(self):
        import main as gw_main
        result = gw_main._resolve_service("/auth/login")
        assert result is not None
        base_url, path = result
        assert "auth-service" in base_url or "4001" in base_url

    def test_resolve_service_purchases(self):
        import main as gw_main
        result = gw_main._resolve_service("/purchases/abc/vote")
        assert result is not None

    def test_resolve_service_unknown(self):
        import main as gw_main
        assert gw_main._resolve_service("/unknown-path") is None


# ─── Auth Service ─────────────────────────────────────────────────────────────

class TestAuthService:
    def setup_method(self):
        _reload_app("/tmp/gh-issue-solver-1777665163791/services/auth-service")

    def _make_token(self, user_id: str = None):
        import app as auth_app
        uid = user_id or str(uuid.uuid4())
        return auth_app._make_token(uid, auth_app.JWT_SECRET, auth_app.JWT_EXPIRES_IN)

    def test_make_and_decode_token(self):
        import app as auth_app
        uid = str(uuid.uuid4())
        token = auth_app._make_token(uid, auth_app.JWT_SECRET, 900)
        decoded = auth_app._decode_token(token, auth_app.JWT_SECRET)
        assert decoded["sub"] == uid

    def test_decode_invalid_token_raises(self):
        import app as auth_app
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            auth_app._decode_token("not.a.valid.token", auth_app.JWT_SECRET)
        assert exc_info.value.status_code == 401

    def test_password_hashing(self):
        import app as auth_app
        raw = "supersecret123"
        hashed = auth_app.pwd_ctx.hash(raw)
        assert auth_app.pwd_ctx.verify(raw, hashed)
        assert not auth_app.pwd_ctx.verify("wrongpassword", hashed)

    def test_health_endpoint(self):
        import app as auth_app
        with patch.object(auth_app, "_pool", MagicMock()):
            import asyncio
            result = asyncio.run(auth_app.health())
            assert result["status"] == "ok"
            assert result["service"] == "auth-service"


# ─── Purchase Service ─────────────────────────────────────────────────────────

class TestPurchaseService:
    def setup_method(self):
        _reload_app("/tmp/gh-issue-solver-1777665163791/services/purchase-service")

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        import app as ps_app
        result = await ps_app.health()
        assert result["status"] == "ok"
        assert result["service"] == "purchase-service"

    @pytest.mark.asyncio
    async def test_user_id_header_missing_raises(self):
        import app as ps_app
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            ps_app._user_id(x_user_id=None)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_user_id_header_present(self):
        import app as ps_app
        uid = str(uuid.uuid4())
        result = ps_app._user_id(x_user_id=uid)
        assert result == uid

    @pytest.mark.asyncio
    async def test_create_purchase(self):
        import app as ps_app

        mock_pool = MagicMock()
        mock_pool.fetchval = AsyncMock(return_value=uuid.uuid4())

        with patch.object(ps_app, "_producer", None):
            body = ps_app.CreatePurchaseRequest(title="Test Purchase", minQuantity=5)
            result = await ps_app.create_purchase(body, user_id=str(uuid.uuid4()), pool=mock_pool)

        assert result["success"] is True
        assert "purchaseId" in result

    @pytest.mark.asyncio
    async def test_cancel_purchase_not_organizer(self):
        import app as ps_app
        from fastapi import HTTPException

        organizer_id = uuid.uuid4()
        other_user_id = str(uuid.uuid4())

        mock_pool = MagicMock()
        mock_pool.fetchrow = AsyncMock(return_value={"organizer_id": organizer_id})

        with pytest.raises(HTTPException) as exc_info:
            await ps_app.cancel_purchase(
                str(uuid.uuid4()), user_id=other_user_id, pool=mock_pool
            )
        assert exc_info.value.status_code == 403


# ─── Payment Service ──────────────────────────────────────────────────────────

class TestPaymentService:
    def setup_method(self):
        _reload_app("/tmp/gh-issue-solver-1777665163791/services/payment-service")

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        import app as pay_app
        result = await pay_app.health()
        assert result["status"] == "ok"
        assert result["service"] == "payment-service"

    @pytest.mark.asyncio
    async def test_hold_insufficient_balance(self):
        import app as pay_app
        from fastapi import HTTPException

        mock_conn = MagicMock()
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=False)
        mock_conn.fetchrow = AsyncMock(return_value={"id": uuid.uuid4(), "balance": 50, "on_hold": 0})
        mock_conn.execute = AsyncMock()
        mock_conn.fetchval = AsyncMock(return_value=uuid.uuid4())

        mock_tx = MagicMock()
        mock_tx.__aenter__ = AsyncMock(return_value=mock_tx)
        mock_tx.__aexit__ = AsyncMock(return_value=False)
        mock_conn.transaction = MagicMock(return_value=mock_tx)

        mock_pool = MagicMock()
        mock_pool.acquire = MagicMock(return_value=mock_conn)

        with pytest.raises(HTTPException) as exc_info:
            body = pay_app.HoldRequest(amount=100, purchaseId=str(uuid.uuid4()))
            await pay_app.hold_funds(body, user_id=str(uuid.uuid4()), pool=mock_pool)
        assert exc_info.value.status_code == 402


# ─── Chat Service ─────────────────────────────────────────────────────────────

class TestChatService:
    def setup_method(self):
        _reload_app("/tmp/gh-issue-solver-1777665163791/services/chat-service")

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        import app as chat_app
        result = await chat_app.health()
        assert result["status"] == "ok"
        assert result["service"] == "chat-service"

    @pytest.mark.asyncio
    async def test_delete_message_wrong_user(self):
        import app as chat_app
        from fastapi import HTTPException

        owner_id = uuid.uuid4()
        attacker_id = str(uuid.uuid4())

        mock_pool = MagicMock()
        mock_pool.fetchrow = AsyncMock(return_value={"user_id": owner_id})

        with pytest.raises(HTTPException) as exc_info:
            await chat_app.delete_message(
                room_id=str(uuid.uuid4()),
                message_id=str(uuid.uuid4()),
                user_id=attacker_id,
                pool=mock_pool,
            )
        assert exc_info.value.status_code == 403


# ─── Reputation Service ───────────────────────────────────────────────────────

class TestReputationService:
    def setup_method(self):
        _reload_app("/tmp/gh-issue-solver-1777665163791/services/reputation-service")

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        import app as rep_app
        result = await rep_app.health()
        assert result["status"] == "ok"
        assert result["service"] == "reputation-service"

    @pytest.mark.asyncio
    async def test_invalid_rating_raises(self):
        import app as rep_app
        from fastapi import HTTPException

        mock_pool = MagicMock()

        body = rep_app.CreateReviewRequest(
            targetId=str(uuid.uuid4()), rating=6  # invalid: max is 5
        )
        with pytest.raises(HTTPException) as exc_info:
            await rep_app.create_review(body, user_id=str(uuid.uuid4()), pool=mock_pool)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_get_score_missing_user_returns_default(self):
        import app as rep_app

        mock_pool = MagicMock()
        mock_pool.fetchrow = AsyncMock(return_value=None)

        uid = str(uuid.uuid4())
        result = await rep_app.get_score(uid, pool=mock_pool)
        assert result["success"] is True
        assert result["data"]["score"] == 5.0
        assert result["data"]["isBlocked"] is False


# ─── Search Service ───────────────────────────────────────────────────────────

class TestSearchService:
    def setup_method(self):
        _reload_app("/tmp/gh-issue-solver-1777665163791/services/search-service")

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        import app as search_app
        result = await search_app.health()
        assert result["status"] == "ok"
        assert result["service"] == "search-service"

    @pytest.mark.asyncio
    async def test_search_no_es_returns_empty(self):
        import app as search_app

        mock_redis = MagicMock()
        mock_redis.lpush = AsyncMock()
        mock_redis.ltrim = AsyncMock()
        mock_redis.publish = AsyncMock()

        with patch.object(search_app, "_es", None):
            body = search_app.SearchRequest(query="test query")
            result = await search_app.search(body, user_id=str(uuid.uuid4()), redis=mock_redis)

        assert result["success"] is True
        assert result["data"] == []
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_saved_filters_roundtrip(self):
        import app as search_app

        store = {}

        async def fake_get(key):
            return store.get(key)

        async def fake_set(key, val):
            store[key] = val

        mock_redis = MagicMock()
        mock_redis.get = fake_get
        mock_redis.set = fake_set

        uid = str(uuid.uuid4())
        body = search_app.SavedFilterRequest(name="My Filter", filter={"category": "electronics"})
        result = await search_app.create_saved_filter(body, user_id=uid, redis=mock_redis)
        assert result["success"] is True
        assert result["data"]["name"] == "My Filter"

        filters_result = await search_app.get_saved_filters(user_id=uid, redis=mock_redis)
        assert len(filters_result["data"]) == 1
        assert filters_result["data"][0]["name"] == "My Filter"


# ─── Notification Service ─────────────────────────────────────────────────────

class TestNotificationService:
    def setup_method(self):
        _reload_app("/tmp/gh-issue-solver-1777665163791/services/notification-service")

    @pytest.mark.asyncio
    async def test_health_endpoint(self):
        import app as notif_app
        result = await notif_app.health()
        assert result["status"] == "ok"
        assert result["service"] == "notification-service"

    @pytest.mark.asyncio
    async def test_internal_notify_no_ops_when_empty(self):
        import app as notif_app
        body = notif_app.NotifyRequest(type="test")
        result = await notif_app.internal_notify(body)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_centrifugo_publish_swallows_errors(self):
        """Centrifugo errors must not propagate to callers."""
        import app as notif_app
        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(side_effect=Exception("network error"))
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            # Should not raise
            await notif_app._centrifugo_publish("test:channel", {"data": "value"})


# ─── Shared Library ───────────────────────────────────────────────────────────

class TestSharedLib:
    def setup_method(self):
        shared_path = "/tmp/gh-issue-solver-1777665163791/services/shared-lib"
        if shared_path not in sys.path:
            sys.path.insert(0, shared_path)

    def test_create_and_decode_access_token(self):
        from groupbuy_shared.auth import create_access_token, decode_token
        uid = str(uuid.uuid4())
        secret = "test-secret"
        token = create_access_token(uid, secret, expires_seconds=300)
        decoded = decode_token(token, secret)
        assert decoded["sub"] == uid

    def test_decode_expired_token_raises(self):
        from groupbuy_shared.auth import create_access_token, decode_token
        from fastapi import HTTPException
        token = create_access_token("user1", "secret", expires_seconds=-1)
        with pytest.raises(HTTPException) as exc_info:
            decode_token(token, "secret")
        assert exc_info.value.status_code == 401

    def test_not_found_error(self):
        from groupbuy_shared.exceptions import NotFoundError
        err = NotFoundError("resource missing")
        assert err.status_code == 404
        assert err.detail == "resource missing"

    def test_conflict_error(self):
        from groupbuy_shared.exceptions import ConflictError
        err = ConflictError()
        assert err.status_code == 409

    def test_base_settings_defaults(self):
        from groupbuy_shared.config import BaseServiceSettings
        settings = BaseServiceSettings()
        assert settings.port == 8000
        assert settings.jwt_algorithm == "HS256"
        assert settings.jwt_expires_in == 900
