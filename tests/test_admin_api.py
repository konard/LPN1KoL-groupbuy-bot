"""
Tests for Admin API
"""
import pytest
from django.contrib.auth.models import User as DjangoUser
from rest_framework.test import APITestCase
from rest_framework import status


class AdminAuthTests(APITestCase):
    """Tests for Admin authentication endpoints"""

    def setUp(self):
        """Set up test data"""
        # Create a staff user
        self.admin_user = DjangoUser.objects.create_user(
            username='admin',
            password='adminpass123',
            email='admin@example.com',
            is_staff=True
        )
        # Create a superuser
        self.superuser = DjangoUser.objects.create_superuser(
            username='superadmin',
            password='superpass123',
            email='superadmin@example.com'
        )
        # Create a regular user (not staff)
        self.regular_user = DjangoUser.objects.create_user(
            username='regular',
            password='regularpass123',
            email='regular@example.com',
            is_staff=False
        )

    def test_admin_login_success(self):
        """Test successful admin login"""
        url = '/api/admin/auth/'
        response = self.client.post(url, {
            'username': 'admin',
            'password': 'adminpass123'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'admin')
        self.assertTrue(response.data['is_staff'])

    def test_admin_login_fail_wrong_password(self):
        """Test admin login with wrong password"""
        url = '/api/admin/auth/'
        response = self.client.post(url, {
            'username': 'admin',
            'password': 'wrongpassword'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_login_fail_not_staff(self):
        """Test admin login with non-staff user"""
        url = '/api/admin/auth/'
        response = self.client.post(url, {
            'username': 'regular',
            'password': 'regularpass123'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_check_auth_not_authenticated(self):
        """Test auth check when not logged in"""
        url = '/api/admin/auth/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_check_auth_authenticated(self):
        """Test auth check when logged in"""
        # Login first
        self.client.login(username='admin', password='adminpass123')

        url = '/api/admin/auth/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'admin')

    def test_admin_logout(self):
        """Test admin logout"""
        # Login first
        self.client.login(username='admin', password='adminpass123')

        url = '/api/admin/auth/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify logged out
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AdminDashboardTests(APITestCase):
    """Tests for Admin dashboard endpoint"""

    def setUp(self):
        """Set up test data"""
        self.admin_user = DjangoUser.objects.create_user(
            username='admin',
            password='adminpass123',
            is_staff=True
        )
        # Create some bot users
        from users.models import User
        User.objects.create(
            platform='telegram',
            platform_user_id='123',
            first_name='Test',
            role='buyer'
        )
        User.objects.create(
            platform='websocket',
            platform_user_id='456',
            first_name='Test2',
            role='organizer'
        )

    def test_dashboard_requires_auth(self):
        """Test that dashboard requires authentication"""
        url = '/api/admin/dashboard/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_dashboard_returns_stats(self):
        """Test that dashboard returns statistics"""
        self.client.login(username='admin', password='adminpass123')

        url = '/api/admin/dashboard/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check expected fields
        self.assertIn('total_users', response.data)
        self.assertIn('users_by_role', response.data)
        self.assertIn('users_by_platform', response.data)
        self.assertIn('total_procurements', response.data)
        self.assertIn('total_payments', response.data)
        self.assertIn('total_messages', response.data)

        # Verify counts
        self.assertEqual(response.data['total_users'], 2)


class AdminUserManagementTests(APITestCase):
    """Tests for Admin user management endpoints"""

    def setUp(self):
        """Set up test data"""
        self.admin_user = DjangoUser.objects.create_user(
            username='admin',
            password='adminpass123',
            is_staff=True
        )
        # Create bot users
        from users.models import User
        self.user1 = User.objects.create(
            platform='telegram',
            platform_user_id='123',
            first_name='John',
            last_name='Doe',
            role='buyer',
            balance=1000,
            is_active=True
        )
        self.user2 = User.objects.create(
            platform='websocket',
            platform_user_id='456',
            first_name='Jane',
            role='organizer',
            is_active=True,
            is_verified=True
        )

    def test_list_users(self):
        """Test listing users"""
        self.client.login(username='admin', password='adminpass123')

        url = '/api/admin/users/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_list_users_with_filters(self):
        """Test listing users with filters"""
        self.client.login(username='admin', password='adminpass123')

        # Filter by role
        response = self.client.get('/api/admin/users/', {'role': 'buyer'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

        # Filter by platform
        response = self.client.get('/api/admin/users/', {'platform': 'telegram'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_list_users_search(self):
        """Test searching users"""
        self.client.login(username='admin', password='adminpass123')

        response = self.client.get('/api/admin/users/', {'search': 'John'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['first_name'], 'John')

    def test_toggle_user_active(self):
        """Test toggling user active status"""
        self.client.login(username='admin', password='adminpass123')

        url = f'/api/admin/users/{self.user1.id}/toggle_active/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_active'])

        # Toggle back
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_active'])

    def test_toggle_user_verified(self):
        """Test toggling user verified status"""
        self.client.login(username='admin', password='adminpass123')

        url = f'/api/admin/users/{self.user1.id}/toggle_verified/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_verified'])

    def test_update_user_balance(self):
        """Test updating user balance"""
        self.client.login(username='admin', password='adminpass123')

        url = f'/api/admin/users/{self.user1.id}/update_balance/'
        response = self.client.post(url, {
            'amount': 500,
            'description': 'Test bonus'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['old_balance'], '1000.00')
        self.assertEqual(response.data['new_balance'], '1500.00')

        # Verify transaction was created
        from payments.models import Transaction
        transaction = Transaction.objects.filter(user=self.user1).last()
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.transaction_type, 'bonus')


class AdminProcurementManagementTests(APITestCase):
    """Tests for Admin procurement management endpoints"""

    def setUp(self):
        """Set up test data"""
        self.admin_user = DjangoUser.objects.create_user(
            username='admin',
            password='adminpass123',
            is_staff=True
        )
        from users.models import User
        from procurements.models import Procurement, Category

        self.organizer = User.objects.create(
            platform='telegram',
            platform_user_id='123',
            first_name='Organizer',
            role='organizer'
        )
        self.category = Category.objects.create(name='Test Category')
        self.procurement = Procurement.objects.create(
            title='Test Procurement',
            description='Test description',
            organizer=self.organizer,
            category=self.category,
            city='Test City',
            target_amount=10000,
            deadline='2030-12-31T23:59:59Z',
            status='active'
        )

    def test_list_procurements(self):
        """Test listing procurements"""
        self.client.login(username='admin', password='adminpass123')

        url = '/api/admin/procurements/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_update_procurement_status(self):
        """Test updating procurement status"""
        self.client.login(username='admin', password='adminpass123')

        url = f'/api/admin/procurements/{self.procurement.id}/update_status/'
        response = self.client.post(url, {'status': 'stopped'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['old_status'], 'active')
        self.assertEqual(response.data['new_status'], 'stopped')

    def test_toggle_procurement_featured(self):
        """Test toggling procurement featured status"""
        self.client.login(username='admin', password='adminpass123')

        url = f'/api/admin/procurements/{self.procurement.id}/toggle_featured/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_featured'])

    def test_procurement_serializer_includes_participant_count_and_progress(self):
        """Regression test: participant_count and progress must be serialized from model properties."""
        self.client.login(username='admin', password='adminpass123')

        url = f'/api/admin/procurements/{self.procurement.id}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # participant_count and progress come from @property on Procurement model
        self.assertIn('participant_count', response.data)
        self.assertIn('progress', response.data)
        self.assertIsInstance(response.data['participant_count'], int)
        self.assertIsInstance(response.data['progress'], int)
        self.assertEqual(response.data['participant_count'], 0)
        self.assertEqual(response.data['progress'], 0)


class AdminTransactionViewTests(APITestCase):
    """Tests for Admin transaction viewing endpoints"""

    def setUp(self):
        """Set up test data"""
        self.admin_user = DjangoUser.objects.create_user(
            username='admin',
            password='adminpass123',
            is_staff=True
        )
        from users.models import User
        from payments.models import Transaction

        self.user = User.objects.create(
            platform='telegram',
            platform_user_id='123',
            first_name='Test',
            role='buyer'
        )
        self.transaction = Transaction.objects.create(
            user=self.user,
            transaction_type='bonus',
            amount=500,
            balance_after=500,
            description='Test transaction'
        )

    def test_list_transactions(self):
        """Test listing transactions"""
        self.client.login(username='admin', password='adminpass123')

        url = '/api/admin/transactions/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_get_transaction_by_id(self):
        """Test getting a single transaction by ID."""
        self.client.login(username='admin', password='adminpass123')

        url = f'/api/admin/transactions/{self.transaction.id}/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.transaction.id)
        self.assertEqual(response.data['transaction_type'], 'bonus')
        self.assertIn('user_name', response.data)


class AdminPaymentViewTests(APITestCase):
    """Tests for Admin payment viewing endpoints"""

    def setUp(self):
        """Set up test data"""
        self.admin_user = DjangoUser.objects.create_user(
            username='admin',
            password='adminpass123',
            is_staff=True
        )
        from users.models import User
        from payments.models import Payment

        self.user = User.objects.create(
            platform='telegram',
            platform_user_id='123',
            first_name='Test',
            role='buyer'
        )
        self.payment = Payment.objects.create(
            user=self.user,
            payment_type='deposit',
            amount=1000,
            status='succeeded'
        )

    def test_list_payments(self):
        """Test listing payments"""
        self.client.login(username='admin', password='adminpass123')

        url = '/api/admin/payments/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_payments_summary(self):
        """Test getting payments summary"""
        self.client.login(username='admin', password='adminpass123')

        url = '/api/admin/payments/summary/'
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_count', response.data)
        self.assertIn('total_amount', response.data)


class AdminCategoryManagementTests(APITestCase):
    """Tests for Admin category management endpoints"""

    def setUp(self):
        """Set up test data"""
        self.admin_user = DjangoUser.objects.create_user(
            username='admin',
            password='adminpass123',
            is_staff=True
        )

    def test_create_category(self):
        """Test creating a category"""
        self.client.login(username='admin', password='adminpass123')

        url = '/api/admin/categories/'
        response = self.client.post(url, {
            'name': 'New Category',
            'description': 'Category description',
            'icon': '📦',
            'is_active': True
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New Category')

    def test_update_category(self):
        """Test updating a category"""
        self.client.login(username='admin', password='adminpass123')

        from procurements.models import Category
        category = Category.objects.create(name='Original Name')

        url = f'/api/admin/categories/{category.id}/'
        response = self.client.patch(url, {
            'name': 'Updated Name'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Name')

    def test_delete_category(self):
        """Test deleting a category"""
        self.client.login(username='admin', password='adminpass123')

        from procurements.models import Category
        category = Category.objects.create(name='To Delete')

        url = f'/api/admin/categories/{category.id}/'
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify deleted
        self.assertFalse(Category.objects.filter(id=category.id).exists())


class AdminNotificationTests(APITestCase):
    """Tests for Admin notification endpoints"""

    def setUp(self):
        """Set up test data"""
        self.admin_user = DjangoUser.objects.create_user(
            username='admin',
            password='adminpass123',
            is_staff=True
        )
        from users.models import User
        self.user1 = User.objects.create(
            platform='telegram',
            platform_user_id='123',
            first_name='Test1',
            role='buyer',
            is_active=True
        )
        self.user2 = User.objects.create(
            platform='telegram',
            platform_user_id='456',
            first_name='Test2',
            role='buyer',
            is_active=True
        )

    def test_send_bulk_notification(self):
        """Test sending bulk notification to all users"""
        self.client.login(username='admin', password='adminpass123')

        url = '/api/admin/notifications/send_bulk/'
        response = self.client.post(url, {
            'notification_type': 'system',
            'title': 'Test Notification',
            'message': 'This is a test notification'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['sent'], 2)

        # Verify notifications were created
        from chat.models import Notification
        self.assertEqual(Notification.objects.count(), 2)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
