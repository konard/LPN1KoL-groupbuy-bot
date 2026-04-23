"""Добавление модулей по ТЗ: новости, запросы покупателей, поставщик, приглашения

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-23

Добавляет:
- Поле city в purchase.participants
- Таблица public.news (лента новостей)
- Таблица public.buyer_requests (запросы покупателей на товары)
- Таблица public.company_cards (карты компаний поставщиков)
- Таблица public.price_lists (прайс-листы поставщиков)
- Таблица public.closing_documents (закрывающие документы)
- Таблица public.invitations (приглашения)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── purchase.participants — add city field ────────────────────────────────
    op.add_column(
        "participants",
        sa.Column("city", sa.String(100), nullable=True),
        schema="purchase",
    )

    # ── public.news ───────────────────────────────────────────────────────────
    op.create_table(
        "news",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="public",
    )

    # ── public.buyer_requests ─────────────────────────────────────────────────
    op.create_table(
        "buyer_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("buyer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("quantity", sa.String(100), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="public",
    )

    # ── public.company_cards ──────────────────────────────────────────────────
    op.create_table(
        "company_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("legal_address", sa.Text(), nullable=False),
        sa.Column("postal_address", sa.Text(), nullable=False),
        sa.Column("actual_address", sa.Text(), nullable=False),
        sa.Column("okved", sa.String(20), nullable=False),
        sa.Column("ogrn", sa.String(20), nullable=False),
        sa.Column("inn", sa.String(12), nullable=False),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="public",
    )

    # ── public.price_lists ────────────────────────────────────────────────────
    op.create_table(
        "price_lists",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_url", sa.String(500), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("popular_items", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="public",
    )

    # ── public.closing_documents ──────────────────────────────────────────────
    op.create_table(
        "closing_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("purchase_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("file_url", sa.String(500), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="public",
    )

    # ── public.invitations ────────────────────────────────────────────────────
    op.create_table(
        "invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_email", sa.String(255), nullable=True),
        sa.Column("recipient_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("purchase_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("invitation_type", sa.String(20), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="public",
    )


def downgrade() -> None:
    op.drop_table("invitations", schema="public")
    op.drop_table("closing_documents", schema="public")
    op.drop_table("price_lists", schema="public")
    op.drop_table("company_cards", schema="public")
    op.drop_table("buyer_requests", schema="public")
    op.drop_table("news", schema="public")
    op.drop_column("participants", "city", schema="purchase")
