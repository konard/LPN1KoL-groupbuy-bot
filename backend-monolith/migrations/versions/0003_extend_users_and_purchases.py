"""Extend users table and purchases with full procurement lifecycle models

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-20

Adds:
- Extended user fields (platform, role, balance, profile, ban fields)
- purchase.categories table
- Extended purchase.purchases columns (city, supplier_id, status lifecycle, deadlines, etc.)
- purchase.participants table
- Extended purchase.votes (candidate_id)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── auth.users — add extended fields ─────────────────────────────────────
    op.add_column(
        "users",
        sa.Column("platform", sa.String(20), nullable=False, server_default="websocket"),
        schema="auth",
    )
    op.add_column(
        "users",
        sa.Column("platform_user_id", sa.String(100), nullable=True),
        schema="auth",
    )
    op.add_column(
        "users",
        sa.Column("username", sa.String(100), nullable=True),
        schema="auth",
    )
    op.add_column(
        "users",
        sa.Column("first_name", sa.String(100), nullable=True),
        schema="auth",
    )
    op.add_column(
        "users",
        sa.Column("last_name", sa.String(100), nullable=True),
        schema="auth",
    )
    op.add_column(
        "users",
        sa.Column("phone", sa.String(30), nullable=True),
        schema="auth",
    )
    op.add_column(
        "users",
        sa.Column("role", sa.String(20), nullable=False, server_default="buyer"),
        schema="auth",
    )
    op.add_column(
        "users",
        sa.Column("balance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        schema="auth",
    )
    op.add_column(
        "users",
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        schema="auth",
    )
    op.add_column(
        "users",
        sa.Column("is_banned", sa.Boolean(), nullable=False, server_default="false"),
        schema="auth",
    )
    op.add_column(
        "users",
        sa.Column("ban_reason", sa.Text(), nullable=True),
        schema="auth",
    )
    op.add_column(
        "users",
        sa.Column("language_code", sa.String(10), nullable=False, server_default="ru"),
        schema="auth",
    )

    # ── purchase.categories ───────────────────────────────────────────────────
    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["parent_id"], ["purchase.categories.id"], name="fk_categories_parent"
        ),
        schema="purchase",
    )

    # ── purchase.purchases — extend columns ───────────────────────────────────
    op.add_column(
        "purchases",
        sa.Column("supplier_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema="purchase",
    )
    op.add_column(
        "purchases",
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("purchase.categories.id"),
            nullable=True,
        ),
        schema="purchase",
    )
    op.add_column(
        "purchases",
        sa.Column("city", sa.String(100), nullable=True),
        schema="purchase",
    )
    op.add_column(
        "purchases",
        sa.Column("delivery_address", sa.Text(), nullable=True),
        schema="purchase",
    )
    op.add_column(
        "purchases",
        sa.Column("stop_at_amount", sa.Numeric(12, 2), nullable=True),
        schema="purchase",
    )
    op.add_column(
        "purchases",
        sa.Column("unit", sa.String(20), nullable=False, server_default="units"),
        schema="purchase",
    )
    op.add_column(
        "purchases",
        sa.Column("price_per_unit", sa.Numeric(10, 2), nullable=True),
        schema="purchase",
    )
    op.add_column(
        "purchases",
        sa.Column("min_quantity", sa.Numeric(10, 2), nullable=True),
        schema="purchase",
    )
    op.add_column(
        "purchases",
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        schema="purchase",
    )
    op.add_column(
        "purchases",
        sa.Column("image_url", sa.String(500), nullable=True),
        schema="purchase",
    )
    op.add_column(
        "purchases",
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default="false"),
        schema="purchase",
    )
    # Rename old 'open' default status to 'active' to match the lifecycle
    op.execute(
        "UPDATE purchase.purchases SET status = 'active' WHERE status = 'open'"
    )

    # ── purchase.votes — add candidate_id ────────────────────────────────────
    op.add_column(
        "votes",
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema="purchase",
    )

    # ── purchase.participants ─────────────────────────────────────────────────
    op.create_table(
        "participants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "purchase_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("purchase.purchases.id"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False, server_default="1"),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="purchase",
    )


def downgrade() -> None:
    op.drop_table("participants", schema="purchase")

    op.drop_column("votes", "candidate_id", schema="purchase")

    for col in [
        "is_featured",
        "image_url",
        "deadline",
        "min_quantity",
        "price_per_unit",
        "unit",
        "stop_at_amount",
        "delivery_address",
        "city",
        "category_id",
        "supplier_id",
    ]:
        op.drop_column("purchases", col, schema="purchase")

    op.drop_table("categories", schema="purchase")

    for col in [
        "language_code",
        "ban_reason",
        "is_banned",
        "is_verified",
        "balance",
        "role",
        "phone",
        "last_name",
        "first_name",
        "username",
        "platform_user_id",
        "platform",
    ]:
        op.drop_column("users", col, schema="auth")
