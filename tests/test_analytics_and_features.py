"""
Tests for analytics endpoint, activity log, and bot status command.
Covers the features added for issue #64.
"""
import pytest
from django.contrib.auth.models import User as DjangoUser
from rest_framework.test import APITestCase
from rest_framework import status


class AdminAnalyticsTests(APITestCase):
    """Tests for the analytics endpoint."""

    def setUp(self):
        """Set up test data."""
        self.admin_user = DjangoUser.objects.create_user(
            username='admin',
            password='adminpass123',
            is_staff=True
        )
        from users.models import User
        from procurements.models import Procurement, Category

        self.category = Category.objects.create(
            name='Test Category',
            icon='📦',
            is_active=True
        )
        self.organizer = User.objects.create(
            platform='telegram',
            platform_user_id='org1',
            first_name='Organizer',
            role='organizer'
        )
        self.buyer = User.objects.create(
            platform='websocket',
            platform_user_id='buyer1',
            first_name='Buyer',
            role='buyer'
        )
        self.procurement = Procurement.objects.create(
            title='Test Procurement',
            description='Test description',
            organizer=self.organizer,
            category=self.category,
            city='Moscow',
            target_amount=10000,
            deadline='2030-12-31T23:59:59Z',
            status='active'
        )

    def test_analytics_requires_auth(self):
        """Test that analytics endpoint requires authentication."""
        response = self.client.get('/api/admin/analytics/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_analytics_returns_data(self):
        """Test that analytics returns expected data structure."""
        self.client.login(username='admin', password='adminpass123')

        response = self.client.get('/api/admin/analytics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        # Check expected top-level keys
        self.assertIn('date_from', data)
        self.assertIn('date_to', data)
        self.assertIn('period', data)
        self.assertIn('user_registrations', data)
        self.assertIn('revenue', data)
        self.assertIn('procurements_created', data)
        self.assertIn('messages_sent', data)
        self.assertIn('top_categories', data)
        self.assertIn('top_organizers', data)
        self.assertIn('funnel', data)

    def test_analytics_with_date_filter(self):
        """Test analytics with date range filter."""
        self.client.login(username='admin', password='adminpass123')

        response = self.client.get('/api/admin/analytics/', {
            'date_from': '2020-01-01',
            'date_to': '2030-12-31',
            'period': 'month',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['period'], 'month')

    def test_analytics_with_day_period(self):
        """Test analytics with day period."""
        self.client.login(username='admin', password='adminpass123')

        response = self.client.get('/api/admin/analytics/', {
            'period': 'day',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['period'], 'day')

    def test_analytics_with_week_period(self):
        """Test analytics with week period."""
        self.client.login(username='admin', password='adminpass123')

        response = self.client.get('/api/admin/analytics/', {
            'period': 'week',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['period'], 'week')

    def test_analytics_funnel_data(self):
        """Test that funnel data is returned correctly."""
        self.client.login(username='admin', password='adminpass123')

        response = self.client.get('/api/admin/analytics/', {
            'date_from': '2020-01-01',
            'date_to': '2030-12-31',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        funnel = response.data['funnel']
        self.assertIn('registered', funnel)
        self.assertIn('participated', funnel)
        self.assertIn('paid', funnel)
        # We created 2 users in setUp
        self.assertEqual(funnel['registered'], 2)

    def test_analytics_top_categories(self):
        """Test that top categories are returned."""
        self.client.login(username='admin', password='adminpass123')

        response = self.client.get('/api/admin/analytics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        categories = response.data['top_categories']
        self.assertTrue(len(categories) > 0)
        self.assertEqual(categories[0]['name'], 'Test Category')

    def test_analytics_top_organizers(self):
        """Test that top organizers are returned."""
        self.client.login(username='admin', password='adminpass123')

        response = self.client.get('/api/admin/analytics/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        organizers = response.data['top_organizers']
        self.assertTrue(len(organizers) > 0)
        self.assertEqual(organizers[0]['first_name'], 'Organizer')

    def test_analytics_invalid_date_uses_default(self):
        """Test that invalid date values fall back to defaults."""
        self.client.login(username='admin', password='adminpass123')

        response = self.client.get('/api/admin/analytics/', {
            'date_from': 'not-a-date',
            'date_to': 'also-not-a-date',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_analytics_time_series_user_registrations(self):
        """Test that user registration time series has correct format."""
        self.client.login(username='admin', password='adminpass123')

        response = self.client.get('/api/admin/analytics/', {
            'date_from': '2020-01-01',
            'date_to': '2030-12-31',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        registrations = response.data['user_registrations']
        self.assertIsInstance(registrations, list)
        if len(registrations) > 0:
            self.assertIn('date', registrations[0])
            self.assertIn('count', registrations[0])


class TestBotStatusCommand:
    """Tests for bot /status command."""

    def test_bot_config_has_bot_mode(self):
        """Test that bot config has bot_mode field."""
        from bot.config import BotConfig

        config = BotConfig()
        assert hasattr(config, 'bot_mode')
        assert config.bot_mode == 'polling'

    def test_bot_config_has_webhook_settings(self):
        """Test that bot config has webhook settings."""
        from bot.config import BotConfig

        config = BotConfig()
        assert hasattr(config, 'webhook_host')
        assert hasattr(config, 'webhook_path')
        assert config.webhook_path == '/bot/webhook'

    def test_status_handler_exists(self):
        """Test that /status handler is registered."""
        from bot.handlers.user_commands import router

        handler_names = []
        for handler in router.message.handlers:
            callback = handler.callback
            if hasattr(callback, '__name__'):
                handler_names.append(callback.__name__)

        assert 'cmd_status' in handler_names

    def test_help_text_includes_status(self):
        """Test that /help text includes /status command."""
        import inspect
        from bot.handlers.user_commands import cmd_help

        source = inspect.getsource(cmd_help)
        assert '/status' in source

    def test_bot_start_time_is_set(self):
        """Test that _bot_start_time is initialized."""
        from bot.handlers.user_commands import _bot_start_time

        assert isinstance(_bot_start_time, float)
        assert _bot_start_time > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
