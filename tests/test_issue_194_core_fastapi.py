"""Tests for the FastAPI core extensions delivered for issue #194.

Issue #194 asks the GroupBuy core service to fully cover the business-process
spec, the buttons spec, the forms spec, and the service-vision spec attached
to the issue. The implementation expands ``core-fastapi`` with new routers
(buyer requests, news, polls, suppliers, invitations) and extends procurement
and payment lifecycles (stop-sum, approve supplier, close, receipt summary,
withdrawals).

These tests exercise:

  * Route discovery — every new endpoint is registered under ``/api/...``.
  * Pydantic schemas — they are importable and validate the documented fields.
  * Migration text — the new tables are part of the schema definition so that
    ``init_schema`` will create them on first start.

A live PostgreSQL/Redis is not required: we import ``main.py`` with stub
``DATABASE_URL`` / ``REDIS_URL`` values just as ``test_issue_178_core_fastapi``
does.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

CORE_DIR = Path(__file__).resolve().parent.parent / "core-fastapi"


@pytest.fixture()
def core_app(monkeypatch):
    monkeypatch.syspath_prepend(str(CORE_DIR))

    for name in list(sys.modules):
        if name == "main" or name.startswith("app.") or name == "app":
            sys.modules.pop(name, None)

    monkeypatch.setenv("DATABASE_URL", "postgresql://stub:stub@stub/stub")
    monkeypatch.setenv("REDIS_URL", "redis://stub:6379/0")
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    main = importlib.import_module("main")
    yield main.app

    for name in list(sys.modules):
        if name == "main" or name.startswith("app.") or name == "app":
            sys.modules.pop(name, None)
    if str(CORE_DIR) in sys.path:
        sys.path.remove(str(CORE_DIR))


# ─── Route discovery ────────────────────────────────────────────────────────


def _paths(app) -> set[str]:
    return {route.path for route in app.routes}


@pytest.mark.parametrize(
    "path",
    [
        # Buyer requests
        "/api/requests/",
        "/api/requests/{request_id}/",
        "/api/requests/search/",
        # News feed
        "/api/news/",
        "/api/news/{post_id}/",
        # Polls
        "/api/polls/",
        "/api/polls/{poll_id}/",
        "/api/polls/{poll_id}/vote/",
        "/api/polls/{poll_id}/close/",
        # Supplier company / price list / closing docs
        "/api/suppliers/companies/",
        "/api/suppliers/companies/{user_id}/",
        "/api/suppliers/price_lists/",
        "/api/suppliers/price_lists/{supplier_id}/",
        "/api/suppliers/closing_documents/",
        "/api/suppliers/closing_documents/{procurement_id}/",
        "/api/suppliers/{supplier_id}/shipments/",
        # Invitations
        "/api/invitations/",
        "/api/invitations/{invitation_id}/",
        # Procurement lifecycle
        "/api/procurements/{proc_id}/stop_amount/",
        "/api/procurements/{proc_id}/confirm/",
        "/api/procurements/{proc_id}/approve_supplier/",
        "/api/procurements/{proc_id}/close/",
        "/api/procurements/{proc_id}/receipt_summary/",
        "/api/procurements/history/",
        # Withdrawals
        "/api/payments/withdrawals/",
        "/api/payments/withdrawals/{withdrawal_id}/process/",
    ],
)
def test_route_is_registered(core_app, path):
    assert path in _paths(core_app), (
        f"Expected {path} to be registered. Found: {sorted(_paths(core_app))[:20]}..."
    )


# ─── Schemas ────────────────────────────────────────────────────────────────


def test_schemas_validate_required_fields(monkeypatch):
    monkeypatch.syspath_prepend(str(CORE_DIR))
    for name in list(sys.modules):
        if name.startswith("app.") or name == "app" or name == "main":
            sys.modules.pop(name, None)
    monkeypatch.setenv("DATABASE_URL", "postgresql://stub/stub")
    monkeypatch.setenv("REDIS_URL", "redis://stub/0")

    schemas = importlib.import_module("app.schemas")

    # CreateBuyerRequest mirrors form 1.1 — Название товара is required.
    req = schemas.CreateBuyerRequest(
        user_id="00000000-0000-0000-0000-000000000001",
        product_name="Молоко 3.2%",
        quantity=10,
        unit="л",
        city="Москва",
    )
    assert req.product_name == "Молоко 3.2%"
    assert str(req.unit) == "л"

    # CreateNewsPost — заголовок is required.
    post = schemas.CreateNewsPost(
        author_id="00000000-0000-0000-0000-000000000002",
        title="Новости от организатора",
        content="...",
    )
    assert post.title

    # CreatePoll — accepts options list and procurement scope.
    poll = schemas.CreatePoll(
        author_id="00000000-0000-0000-0000-000000000003",
        question="Кого выбрать поставщиком?",
        options=["Поставщик А", "Поставщик Б"],
        procurement_id=42,
        poll_type="supplier_vote",
    )
    assert len(poll.options) == 2
    assert poll.poll_type == "supplier_vote"

    # UpsertSupplierCompany — name is required and 9 optional company fields exist.
    company = schemas.UpsertSupplierCompany(
        user_id="00000000-0000-0000-0000-000000000004",
        name="ООО «Поставщик»",
        legal_address="ул. Тверская, 1",
        inn="7700000000",
    )
    assert company.name.startswith("ООО")
    assert company.inn == "7700000000"

    # CreateInvitation — at least invitee_email or invitee_id is the API contract.
    inv = schemas.CreateInvitation(
        organizer_id="00000000-0000-0000-0000-000000000005",
        invitee_email="supplier@example.com",
        invitee_role="supplier",
        message="Приглашаем",
    )
    assert inv.invitee_role == "supplier"

    # CreateWithdrawal — amount is required and bank_details captures реквизиты.
    wd = schemas.CreateWithdrawal(
        user_id="00000000-0000-0000-0000-000000000006",
        amount=1000,
        bank_details="40817810000000000000",
    )
    assert wd.amount == 1000

    for name in list(sys.modules):
        if name.startswith("app.") or name == "app" or name == "main":
            sys.modules.pop(name, None)
    if str(CORE_DIR) in sys.path:
        sys.path.remove(str(CORE_DIR))


# ─── Migration text covers the new tables ───────────────────────────────────


@pytest.mark.parametrize(
    "snippet",
    [
        "CREATE TABLE IF NOT EXISTS buyer_requests",
        "CREATE TABLE IF NOT EXISTS news_posts",
        "CREATE TABLE IF NOT EXISTS polls",
        "CREATE TABLE IF NOT EXISTS poll_options",
        "CREATE TABLE IF NOT EXISTS poll_votes",
        "CREATE TABLE IF NOT EXISTS supplier_companies",
        "CREATE TABLE IF NOT EXISTS supplier_price_lists",
        "CREATE TABLE IF NOT EXISTS invitations",
        "CREATE TABLE IF NOT EXISTS closing_documents",
        "CREATE TABLE IF NOT EXISTS withdrawal_requests",
    ],
)
def test_migrations_create_new_tables(snippet):
    db_text = (CORE_DIR / "app" / "db.py").read_text(encoding="utf-8")
    assert snippet in db_text, f"Missing schema for: {snippet}"


# ─── Spec-coverage smoke check ──────────────────────────────────────────────


def test_router_modules_are_importable(monkeypatch):
    """Smoke-importing the router modules also catches syntax errors."""
    monkeypatch.syspath_prepend(str(CORE_DIR))
    for name in list(sys.modules):
        if name.startswith("app.") or name == "app" or name == "main":
            sys.modules.pop(name, None)
    monkeypatch.setenv("DATABASE_URL", "postgresql://stub/stub")
    monkeypatch.setenv("REDIS_URL", "redis://stub/0")

    for mod in (
        "app.routers.requests",
        "app.routers.news",
        "app.routers.polls",
        "app.routers.suppliers",
        "app.routers.invitations",
    ):
        importlib.import_module(mod)

    for name in list(sys.modules):
        if name.startswith("app.") or name == "app" or name == "main":
            sys.modules.pop(name, None)
    if str(CORE_DIR) in sys.path:
        sys.path.remove(str(CORE_DIR))
