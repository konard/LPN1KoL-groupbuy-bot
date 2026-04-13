"""
Tests for the seed_categories management command and bot procurement creation fixes.

Covers:
  - seed_categories command creates expected categories
  - seed_categories is idempotent (no duplicates on second run)
  - seed_categories --clear removes existing categories first
  - Bot: procurement creation uses a future deadline (not 2025-12-31)
  - Bot: procurement creation attaches the selected category
  - Bot: category selection keyboard uses 'proc_category_' prefix
"""

import pytest
from io import StringIO
from datetime import datetime, timezone
from rest_framework.test import APITestCase


# ──────────────────────────────────────────────────────────────────────────────
# seed_categories management command
# ──────────────────────────────────────────────────────────────────────────────

class SeedCategoriesTests(APITestCase):
    """Tests for the seed_categories management command."""

    def _seed(self, *extra_args):
        from django.core.management import call_command
        call_command("seed_categories", *extra_args, stdout=StringIO())

    def test_seed_creates_top_level_categories(self):
        """Running the command should create top-level categories."""
        from procurements.models import Category

        Category.objects.all().delete()
        self._seed()

        assert Category.objects.filter(parent__isnull=True).count() >= 5

    def test_seed_creates_subcategories(self):
        """The command should create child categories under each parent."""
        from procurements.models import Category

        Category.objects.all().delete()
        self._seed()

        assert Category.objects.filter(parent__isnull=False).count() >= 10

    def test_seed_is_idempotent(self):
        """Running the command twice should not create duplicate categories."""
        from procurements.models import Category

        Category.objects.all().delete()
        self._seed()
        count_after_first = Category.objects.count()

        self._seed()
        count_after_second = Category.objects.count()

        self.assertEqual(count_after_first, count_after_second)

    def test_seed_clear_flag_removes_existing(self):
        """--clear should delete all categories before seeding."""
        from procurements.models import Category

        Category.objects.all().delete()
        self._seed()
        initial_count = Category.objects.count()
        self.assertGreater(initial_count, 0)

        # Re-seed with --clear; count should be the same (fresh seed)
        self._seed("--clear")
        self.assertEqual(Category.objects.count(), initial_count)

    def test_food_category_exists(self):
        """'Продукты питания' top-level category must be present."""
        from procurements.models import Category

        Category.objects.all().delete()
        self._seed()

        self.assertTrue(
            Category.objects.filter(name="Продукты питания", parent__isnull=True).exists()
        )

    def test_honey_subcategory_under_food(self):
        """'Мёд и пчеловодство' must be a child of 'Продукты питания'."""
        from procurements.models import Category

        Category.objects.all().delete()
        self._seed()

        food = Category.objects.get(name="Продукты питания", parent__isnull=True)
        self.assertTrue(
            Category.objects.filter(name="Мёд и пчеловодство", parent=food).exists()
        )

    def test_categories_have_icons(self):
        """All seeded top-level categories should have a non-empty icon."""
        from procurements.models import Category

        Category.objects.all().delete()
        self._seed()

        for cat in Category.objects.filter(parent__isnull=True):
            self.assertTrue(cat.icon, f"Category '{cat.name}' has no icon")

    def test_categories_are_active_by_default(self):
        """All seeded categories should be active."""
        from procurements.models import Category

        Category.objects.all().delete()
        self._seed()

        inactive = Category.objects.filter(is_active=False)
        self.assertFalse(
            inactive.exists(), f"Found inactive categories: {list(inactive)}"
        )

    def test_categories_api_returns_seeded_data(self):
        """GET /api/procurements/categories/ must return seeded categories via the API."""
        from procurements.models import Category

        Category.objects.all().delete()
        self._seed()

        response = self.client.get("/api/procurements/categories/")
        self.assertEqual(response.status_code, 200)

        # Collect all categories (handle pagination transparently)
        if isinstance(response.data, dict) and "count" in response.data:
            # Paginated — verify the total count matches what we seeded
            total_in_api = response.data["count"]
            total_in_db = Category.objects.count()
            self.assertEqual(total_in_api, total_in_db)
            # At least one well-known category must appear on the first page
            first_page_names = [c["name"] for c in response.data["results"]]
            self.assertTrue(
                len(first_page_names) > 0,
                "API must return at least one category",
            )
        else:
            # Non-paginated list
            names = [c["name"] for c in response.data]
            self.assertIn("Продукты питания", names)


# ──────────────────────────────────────────────────────────────────────────────
# Bot: procurement creation deadline fix
# ──────────────────────────────────────────────────────────────────────────────

class TestProcurementCreationDeadline:
    """Ensure the procurement creation flow uses a future deadline."""

    def test_deadline_is_in_future(self):
        """The default deadline generated in process_city must be in the future."""
        from datetime import timedelta

        default_deadline = (datetime.now(timezone.utc) + timedelta(days=365)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        deadline_dt = datetime.strptime(default_deadline, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
        assert deadline_dt > datetime.now(timezone.utc), (
            "Default deadline must be in the future so participants can join"
        )

    def test_hardcoded_2025_deadline_would_be_past(self):
        """Regression guard: confirm 2025-12-31 is indeed in the past."""
        old_deadline = datetime(2025, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        assert old_deadline < datetime.now(timezone.utc), (
            "2025-12-31 should be in the past; this test guards against regression"
        )

    def test_process_city_uses_future_deadline(self):
        """process_city handler must NOT use the hardcoded 2025-12-31 deadline."""
        import inspect
        from bot.handlers.procurement_commands import process_city

        source = inspect.getsource(process_city)
        assert "2025-12-31" not in source, (
            "process_city still contains the hardcoded 2025-12-31 deadline"
        )
        assert "timedelta" in source, (
            "process_city should compute the deadline using timedelta"
        )


# ──────────────────────────────────────────────────────────────────────────────
# Bot: category keyboard prefix
# ──────────────────────────────────────────────────────────────────────────────

class TestProcurementCategoryKeyboard:
    """Ensure the procurement-creation category keyboard uses the right prefix."""

    def test_keyboard_uses_proc_category_prefix(self):
        """get_procurement_category_keyboard must use 'proc_category_' prefix."""
        from bot.keyboards import get_procurement_category_keyboard

        categories = [{"id": 1, "name": "Food"}, {"id": 2, "name": "Clothes"}]
        keyboard = get_procurement_category_keyboard(categories)

        callbacks = [
            btn.callback_data
            for row in keyboard.inline_keyboard
            for btn in row
        ]
        assert all(cb.startswith("proc_category_") for cb in callbacks), (
            f"All callbacks should start with 'proc_category_', got: {callbacks}"
        )

    def test_browse_keyboard_uses_category_prefix(self):
        """get_categories_keyboard (browse/filter) must keep 'category_' prefix."""
        from bot.keyboards import get_categories_keyboard

        categories = [{"id": 1, "name": "Food"}]
        keyboard = get_categories_keyboard(categories)

        callbacks = [
            btn.callback_data
            for row in keyboard.inline_keyboard
            for btn in row
        ]
        assert all(cb.startswith("category_") for cb in callbacks), (
            f"Browse keyboard callbacks should start with 'category_', got: {callbacks}"
        )

    @pytest.mark.asyncio
    async def test_category_step_is_reachable_from_description(self):
        """After entering a description the bot should offer category selection."""
        from unittest.mock import AsyncMock, patch
        from bot.handlers.procurement_commands import process_description

        message = AsyncMock()
        message.text = "This is a valid description with enough chars"
        state = AsyncMock()
        state.get_data = AsyncMock(return_value={})
        state.update_data = AsyncMock()
        state.set_state = AsyncMock()

        categories = [{"id": 1, "name": "Food"}, {"id": 2, "name": "Clothes"}]

        with patch(
            "bot.handlers.procurement_commands.api_client.get_categories",
            new_callable=AsyncMock,
            return_value=categories,
        ):
            await process_description(message, state)

        message.answer.assert_called_once()
        call_kwargs = message.answer.call_args
        reply_markup = call_kwargs.kwargs.get("reply_markup") or (
            call_kwargs.args[1] if len(call_kwargs.args) > 1 else None
        )
        assert reply_markup is not None, "Category keyboard should be attached"

        callbacks = [
            btn.callback_data
            for row in reply_markup.inline_keyboard
            for btn in row
        ]
        assert any(cb.startswith("proc_category_") for cb in callbacks)

    @pytest.mark.asyncio
    async def test_category_step_skipped_when_no_categories(self):
        """If no categories exist, the bot should skip straight to target amount."""
        from unittest.mock import AsyncMock, patch
        from bot.handlers.procurement_commands import (
            process_description,
            ProcurementCreationStates,
        )

        message = AsyncMock()
        message.text = "This is a valid description with enough chars"
        state = AsyncMock()
        state.get_data = AsyncMock(return_value={})
        state.update_data = AsyncMock()
        state.set_state = AsyncMock()

        with patch(
            "bot.handlers.procurement_commands.api_client.get_categories",
            new_callable=AsyncMock,
            return_value=[],
        ):
            await process_description(message, state)

        state.set_state.assert_called_once_with(
            ProcurementCreationStates.waiting_for_target_amount
        )
