"""
Tests for issue #300 fix:

  GET /api/chat/notifications/?user_id=<N> was returning notifications
  belonging to other users because get_queryset() fell back to
  Notification.objects.all() when no user_id was supplied, and also trusted
  the client-supplied user_id without restriction.

  Fix: NotificationViewSet.get_queryset() now returns an empty queryset when
  user_id is absent, so callers always see only their own notifications.
"""
import os
import re
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
CORE_CHAT_VIEWS = os.path.join(ROOT, "core", "chat", "views.py")


def read(path):
    with open(path) as f:
        return f.read()


# ===========================================================================
# Static / source-level checks
# ===========================================================================

class TestGetQuerysetSourceGuard:
    def test_get_queryset_returns_none_when_no_user_id(self):
        """
        NotificationViewSet.get_queryset must short-circuit with
        Notification.objects.none() when user_id is absent — not fall through
        to Notification.objects.all().
        """
        source = read(CORE_CHAT_VIEWS)
        assert "Notification.objects.none()" in source, (
            "NotificationViewSet.get_queryset must return Notification.objects.none() "
            "when user_id query param is absent, to prevent leaking other users' notifications."
        )

    def test_notification_get_queryset_does_not_use_all_as_base(self):
        """
        NotificationViewSet.get_queryset must NOT call super().get_queryset()
        and then conditionally filter — that pattern leaks all rows when
        user_id is absent.  The fix uses an early return of .none().
        """
        source = read(CORE_CHAT_VIEWS)
        # Extract only NotificationViewSet class body
        match = re.search(
            r'class NotificationViewSet\b.*?(?=\nclass |\Z)', source, re.DOTALL
        )
        assert match, "NotificationViewSet class not found in views.py"
        class_body = match.group(0)

        # Extract the get_queryset method within that class
        method_match = re.search(
            r'def get_queryset\(self\):(.*?)(?=\n    def |\Z)', class_body, re.DOTALL
        )
        assert method_match, "get_queryset method not found in NotificationViewSet"
        method_body = method_match.group(1)

        assert "super().get_queryset()" not in method_body, (
            "NotificationViewSet.get_queryset must not call super().get_queryset() "
            "as the base — that returns all rows when user_id is absent."
        )


# ===========================================================================
# Django integration tests (using RequestFactory to avoid jwt dependency)
# ===========================================================================

try:
    import django  # noqa: F401
    DJANGO_AVAILABLE = True
except ImportError:
    DJANGO_AVAILABLE = False


@pytest.mark.skipif(not DJANGO_AVAILABLE, reason="Django not installed")
class TestNotificationLeakDjango:
    """
    Django tests using RequestFactory to call NotificationViewSet directly,
    bypassing conftest_urls.py URL routing which pulls in users.urls and
    triggers a jwt import error.
    """

    def _make_list_request(self, query_string=''):
        """Helper: call NotificationViewSet list action with RequestFactory."""
        from django.test import RequestFactory
        from chat.views import NotificationViewSet

        factory = RequestFactory()
        request = factory.get(f'/api/chat/notifications/{query_string}')
        view = NotificationViewSet.as_view({'get': 'list'})
        return view(request)

    def test_no_user_id_returns_empty_list(self):
        """
        GET /api/chat/notifications/ without user_id must return an empty list,
        not all notifications in the database.
        """
        from users.models import User
        from chat.models import Notification

        user = User.objects.create(
            platform_user_id='300100', username='user_leak_1', first_name='A',
            last_name='B', role='buyer'
        )
        Notification.objects.create(
            user=user, notification_type='system',
            title='Secret', message='Should not be visible without user_id'
        )

        response = self._make_list_request()
        response.accepted_renderer = None
        response.accepted_media_type = 'application/json'
        response.renderer_context = {}

        assert response.status_code == 200, (
            f"Expected 200 OK but got {response.status_code}"
        )
        results = response.data.get('results', response.data)
        assert len(results) == 0, (
            f"Expected empty list when user_id is absent, got {len(results)} notification(s). "
            "Issue #300: notifications leaked to callers who didn't supply a user_id."
        )

        # Cleanup
        Notification.objects.filter(user=user).delete()
        user.delete()

    def test_user_id_returns_only_own_notifications(self):
        """
        GET /api/chat/notifications/?user_id=<N> must return only notifications
        that belong to user N, not notifications belonging to other users.
        """
        from users.models import User
        from chat.models import Notification

        user1 = User.objects.create(
            platform_user_id='300101', username='user_leak_2', first_name='C',
            last_name='D', role='buyer'
        )
        user2 = User.objects.create(
            platform_user_id='300102', username='user_leak_3', first_name='E',
            last_name='F', role='buyer'
        )
        n1 = Notification.objects.create(
            user=user1, notification_type='system',
            title='For User1', message='User1 notification'
        )
        n2 = Notification.objects.create(
            user=user2, notification_type='system',
            title='For User2', message='User2 notification'
        )

        response = self._make_list_request(f'?user_id={user1.id}')
        assert response.status_code == 200, (
            f"Expected 200 OK but got {response.status_code}"
        )
        results = response.data.get('results', response.data)
        assert len(results) == 1, (
            f"Expected exactly 1 notification for user1, got {len(results)}. "
            "Issue #300: other users' notifications may be leaking."
        )
        assert results[0]['title'] == 'For User1', (
            "The returned notification does not belong to the requested user."
        )

        # Cleanup
        n1.delete()
        n2.delete()
        user1.delete()
        user2.delete()
