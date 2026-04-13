"""
Tests for issue #112 fixes:
- Admin login with Django auth User (session-based authentication)
- User role filtering (supplier select data)
- Categories fixture data availability
- REST Framework SessionAuthentication configuration
"""
import pytest
from django.contrib.auth.models import User as DjangoUser
from rest_framework.test import APITestCase
from rest_framework import status


class AdminLoginSessionAuthTests(APITestCase):
    """Tests verifying admin login works with session-based auth."""

    def setUp(self):
        self.admin_user = DjangoUser.objects.create_user(
            username='testadmin',
            password='testpass123',
            email='admin@test.com',
            is_staff=True,
        )

    def test_admin_login_sets_session_cookie(self):
        """Admin login should set a session cookie for subsequent requests."""
        url = '/api/admin/auth/'
        response = self.client.post(url, {
            'username': 'testadmin',
            'password': 'testpass123',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testadmin')
        self.assertTrue(response.data['is_staff'])

        # Subsequent request should be authenticated via session
        check_response = self.client.get(url)
        self.assertEqual(check_response.status_code, status.HTTP_200_OK)
        self.assertEqual(check_response.data['username'], 'testadmin')

    def test_admin_dashboard_accessible_after_login(self):
        """After login, admin should be able to access protected endpoints."""
        self.client.login(username='testadmin', password='testpass123')
        response = self.client.get('/api/admin/dashboard/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_categories_accessible_after_login(self):
        """After login, admin should be able to access categories."""
        self.client.login(username='testadmin', password='testpass123')
        response = self.client.get('/api/admin/categories/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class UserRoleFilterTests(APITestCase):
    """Tests verifying user role filtering works for supplier selects."""

    def setUp(self):
        from users.models import User
        self.buyer = User.objects.create(
            platform='telegram',
            platform_user_id='buyer1',
            first_name='Buyer',
            role='buyer',
        )
        self.supplier1 = User.objects.create(
            platform='telegram',
            platform_user_id='supplier1',
            first_name='Supplier One',
            role='supplier',
        )
        self.supplier2 = User.objects.create(
            platform='websocket',
            platform_user_id='supplier2',
            first_name='Supplier Two',
            role='supplier',
        )
        self.organizer = User.objects.create(
            platform='telegram',
            platform_user_id='org1',
            first_name='Organizer',
            role='organizer',
        )

    def test_filter_users_by_role_supplier(self):
        """GET /api/users/?role=supplier should return only suppliers."""
        response = self.client.get('/api/users/', {'role': 'supplier'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 2)
        roles = {u['role'] for u in results}
        self.assertEqual(roles, {'supplier'})

    def test_filter_users_by_role_buyer(self):
        """GET /api/users/?role=buyer should return only buyers."""
        response = self.client.get('/api/users/', {'role': 'buyer'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['role'], 'buyer')

    def test_filter_users_by_role_organizer(self):
        """GET /api/users/?role=organizer should return only organizers."""
        response = self.client.get('/api/users/', {'role': 'organizer'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['role'], 'organizer')

    def test_filter_users_by_platform(self):
        """GET /api/users/?platform=telegram should filter by platform."""
        response = self.client.get('/api/users/', {'platform': 'telegram'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 3)  # buyer, supplier1, organizer
        platforms = {u['platform'] for u in results}
        self.assertEqual(platforms, {'telegram'})

    def test_no_filter_returns_all_users(self):
        """GET /api/users/ without filters should return all users."""
        response = self.client.get('/api/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertEqual(len(results), 4)


class CategoryDataTests(APITestCase):
    """Tests verifying category data is available."""

    def test_categories_endpoint_returns_data(self):
        """Categories endpoint should be accessible and return data."""
        from procurements.models import Category
        Category.objects.create(name='Test Category', icon='📦', is_active=True)

        response = self.client.get('/api/procurements/categories/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # CategoryViewSet has pagination_class = None — response is a plain list
        results = response.data if isinstance(response.data, list) else response.data.get('results', response.data)
        self.assertGreaterEqual(len(results), 1)

    def test_inactive_categories_not_returned(self):
        """Inactive categories should not be returned."""
        from procurements.models import Category
        Category.objects.create(name='Active', icon='✅', is_active=True)
        Category.objects.create(name='Inactive', icon='❌', is_active=False)

        response = self.client.get('/api/procurements/categories/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # CategoryViewSet has pagination_class = None — response is a plain list
        results = response.data if isinstance(response.data, list) else response.data.get('results', response.data)
        names = [c['name'] for c in results]
        self.assertIn('Active', names)
        self.assertNotIn('Inactive', names)


class DjangoSettingsTests(APITestCase):
    """Tests verifying Django settings are correctly configured."""

    def test_session_authentication_enabled(self):
        """REST Framework should have SessionAuthentication enabled."""
        from django.conf import settings
        auth_classes = settings.REST_FRAMEWORK.get('DEFAULT_AUTHENTICATION_CLASSES', [])
        self.assertIn(
            'rest_framework.authentication.SessionAuthentication',
            auth_classes,
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
