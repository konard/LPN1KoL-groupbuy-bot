"""Начальная схема базы данных: все таблицы монолита.

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Пользователи ──────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("username", sa.String(64), unique=True, nullable=False),
        sa.Column("email", sa.String(128), unique=True, nullable=False),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("hashed_password", sa.String(256), nullable=False),
        sa.Column("is_active", sa.Boolean, default=True, nullable=False),
        sa.Column("is_admin", sa.Boolean, default=False, nullable=False),
        sa.Column("is_verified", sa.Boolean, default=False, nullable=False),
        sa.Column("totp_secret", sa.String(64), nullable=True),
        sa.Column("totp_enabled", sa.Boolean, default=False, nullable=False),
        sa.Column("balance", sa.Numeric(12, 2), default=0, nullable=False),
        sa.Column("reputation_score", sa.Numeric(3, 2), default=0, nullable=False),
        sa.Column("is_blocked", sa.Boolean, default=False, nullable=False),
        sa.Column("bio", sa.Text, nullable=True),
        sa.Column("avatar_url", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email", "users", ["email"])

    # ── Закупки ───────────────────────────────────────────────────────────────
    op.create_table(
        "purchases",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("organizer_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(128), nullable=True),
        sa.Column("status", sa.String(20), default="draft", nullable=False),
        sa.Column("min_quantity", sa.Integer, default=1, nullable=False),
        sa.Column("commission_pct", sa.Numeric(5, 2), default=0, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_purchases_organizer_id", "purchases", ["organizer_id"])
    op.create_index("ix_purchases_status", "purchases", ["status"])

    # ── Голосование ───────────────────────────────────────────────────────────
    op.create_table(
        "voting_sessions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("purchase_id", sa.Integer, sa.ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), default="active", nullable=False),
        sa.Column("winner_id", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("closed_at", sa.DateTime, nullable=True),
    )

    op.create_table(
        "candidates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("voting_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("supplier_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "votes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("session_id", sa.Integer, sa.ForeignKey("voting_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("candidate_id", sa.Integer, sa.ForeignKey("candidates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("session_id", "user_id", name="uq_vote_session_user"),
    )

    # ── Платежи ───────────────────────────────────────────────────────────────
    op.create_table(
        "wallets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("balance", sa.Numeric(12, 2), default=0, nullable=False),
        sa.Column("on_hold", sa.Numeric(12, 2), default=0, nullable=False),
        sa.Column("status", sa.String(20), default="active", nullable=False),
        sa.Column("currency", sa.String(3), default="RUB", nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("wallet_id", sa.Integer, sa.ForeignKey("wallets.id"), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(20), default="pending", nullable=False),
        sa.Column("reference_id", sa.String(128), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "escrow_accounts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("purchase_id", sa.Integer, sa.ForeignKey("purchases.id"), nullable=False, unique=True),
        sa.Column("total_deposited", sa.Numeric(12, 2), default=0, nullable=False),
        sa.Column("confirmations_received", sa.Integer, default=0, nullable=False),
        sa.Column("confirmations_required", sa.Integer, default=1, nullable=False),
        sa.Column("status", sa.String(20), default="active", nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "commissions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("purchase_id", sa.Integer, sa.ForeignKey("purchases.id"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("status", sa.String(20), default="held", nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    # ── Чат ───────────────────────────────────────────────────────────────────
    op.create_table(
        "rooms",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("type", sa.String(20), default="group", nullable=False),
        sa.Column("purchase_id", sa.Integer, sa.ForeignKey("purchases.id"), nullable=True),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_archived", sa.Boolean, default=False, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "room_members",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("room_id", sa.Integer, sa.ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("joined_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("room_id", "user_id", name="uq_room_member"),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("room_id", sa.Integer, sa.ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("type", sa.String(20), default="text", nullable=False),
        sa.Column("media_url", sa.String(512), nullable=True),
        sa.Column("is_edited", sa.Boolean, default=False, nullable=False),
        sa.Column("is_deleted", sa.Boolean, default=False, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    # ── Репутация ─────────────────────────────────────────────────────────────
    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("author_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("purchase_id", sa.Integer, sa.ForeignKey("purchases.id"), nullable=True),
        sa.Column("rating", sa.Integer, nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("is_anonymous", sa.Boolean, default=False, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "complaints",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("reporter_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("purchase_id", sa.Integer, sa.ForeignKey("purchases.id"), nullable=True),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("evidence_url", sa.String(512), nullable=True),
        sa.Column("status", sa.String(20), default="open", nullable=False),
        sa.Column("resolution", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "reputation_scores",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), unique=True, nullable=False),
        sa.Column("score", sa.Numeric(3, 2), default=0, nullable=False),
        sa.Column("total_reviews", sa.Integer, default=0, nullable=False),
        sa.Column("total_complaints", sa.Integer, default=0, nullable=False),
        sa.Column("is_blocked", sa.Boolean, default=False, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("reputation_scores")
    op.drop_table("complaints")
    op.drop_table("reviews")
    op.drop_table("messages")
    op.drop_table("room_members")
    op.drop_table("rooms")
    op.drop_table("commissions")
    op.drop_table("escrow_accounts")
    op.drop_table("transactions")
    op.drop_table("wallets")
    op.drop_table("votes")
    op.drop_table("candidates")
    op.drop_table("voting_sessions")
    op.drop_table("purchases")
    op.drop_table("users")
