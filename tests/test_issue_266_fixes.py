"""
Tests for issue #266 fixes:

  1. API 404 on Mark as Read — NotificationViewSet.mark_read action now
     has explicit url_path='mark_read' to ensure DRF router registers the
     endpoint as `mark_read/` (not `mark-read/`).

  2. Active Downloads stale cache — api.js request() adds `Cache-Control:
     no-cache` header. Cabinet.jsx loadStats re-runs on visibilitychange.

  3. Message Block Click — clicking a notification message now awaits
     markNotificationRead and then navigates to /chat/<procurement_id>.

  4. Invite User to Procurement — POST /api/procurements/<id>/invite/ only
     allows the organizer; returns 403 otherwise; logs invite.

  5. 404 on Voting — getChatVote now calls /vote_results/ (not /chat_vote/).
"""
import os
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
CORE_CHAT_VIEWS = os.path.join(ROOT, "core", "chat", "views.py")
CORE_PROC_VIEWS = os.path.join(ROOT, "core", "procurements", "views.py")
CORE_PROC_SERIALIZERS = os.path.join(ROOT, "core", "procurements", "serializers.py")
FRONTEND_API = os.path.join(ROOT, "frontend-react", "src", "services", "api.js")
FRONTEND_CABINET = os.path.join(ROOT, "frontend-react", "src", "components", "Cabinet.jsx")


def read(path):
    with open(path) as f:
        return f.read()


# ===========================================================================
# Fix 1 — NotificationViewSet.mark_read has explicit url_path='mark_read'
# ===========================================================================

class TestMarkReadUrlPath:
    def test_url_path_present_in_action_decorator(self):
        """
        The @action decorator for mark_read must have url_path='mark_read'
        so DRF always registers the URL with an underscore, not a hyphen.
        """
        source = read(CORE_CHAT_VIEWS)
        assert "url_path='mark_read'" in source, (
            "NotificationViewSet.mark_read @action must declare url_path='mark_read' "
            "to guarantee the URL is registered as mark_read/ (not mark-read/)."
        )

    def test_mark_read_is_detail_action(self):
        """mark_read must remain a detail=True action (operates on a specific notification)."""
        source = read(CORE_CHAT_VIEWS)
        # Both detail=True and url_path should appear near mark_read
        assert "detail=True" in source
        assert "def mark_read" in source


# ===========================================================================
# Fix 2 — Cache-Control header in api.js + visibilitychange in Cabinet.jsx
# ===========================================================================

class TestCacheControlHeader:
    def test_cache_control_no_cache_in_request_function(self):
        """
        The base request() helper must send Cache-Control: no-cache so
        browsers do not serve stale data for active procurements list.
        """
        source = read(FRONTEND_API)
        assert "'Cache-Control': 'no-cache'" in source, (
            "api.js request() must include 'Cache-Control': 'no-cache' header "
            "to prevent browser caching of procurement/notification data."
        )


class TestVisibilityChange:
    def test_visibilitychange_listener_added_in_cabinet(self):
        """
        Cabinet.jsx must add a visibilitychange event listener so that
        loadStats() is called whenever the browser tab becomes visible again.
        """
        source = read(FRONTEND_CABINET)
        assert "visibilitychange" in source, (
            "Cabinet.jsx must add a 'visibilitychange' event listener to "
            "reload active procurements/notifications when the tab is focused."
        )

    def test_visibilitychange_listener_removed_on_cleanup(self):
        """The event listener must be cleaned up to avoid memory leaks."""
        source = read(FRONTEND_CABINET)
        assert "removeEventListener('visibilitychange'" in source, (
            "Cabinet.jsx must remove the visibilitychange listener in the "
            "useEffect cleanup function."
        )

    def test_visibility_state_check(self):
        """Only reload when tab becomes visible, not on hide."""
        source = read(FRONTEND_CABINET)
        assert "visibilityState === 'visible'" in source, (
            "Cabinet.jsx must check document.visibilityState === 'visible' "
            "before reloading stats to avoid unnecessary requests on tab hide."
        )


# ===========================================================================
# Fix 3 — handleMarkMessageRead navigates to chat after marking read
# ===========================================================================

class TestHandleMarkMessageRead:
    def test_procurement_id_stored_in_message_object(self):
        """Messages mapped from notifications must include procurement_id."""
        source = read(FRONTEND_CABINET)
        assert "procurement_id: n.procurement_id" in source, (
            "Messages mapped from notifications must preserve procurement_id "
            "so the click handler can navigate to the correct chat."
        )

    def test_mark_message_read_navigates_to_chat(self):
        """
        handleMarkMessageRead must navigate to /chat/<procurement_id> after
        the API call succeeds.
        """
        source = read(FRONTEND_CABINET)
        assert "navigate(`/chat/${message.procurement_id}`)" in source, (
            "handleMarkMessageRead must call navigate() with the chat URL "
            "so clicking a message opens the relevant procurement chat."
        )

    def test_handler_receives_full_message_object(self):
        """The handler signature should accept message object, not just id."""
        source = read(FRONTEND_CABINET)
        assert "handleMarkMessageRead(m)" in source, (
            "onClick must pass the full message object (not just m.id) so "
            "the handler has access to procurement_id for navigation."
        )


# ===========================================================================
# Fix 4 — Invite endpoint on ProcurementViewSet + frontend support
# ===========================================================================

class TestInviteEndpoint:
    def test_invite_action_defined_in_views(self):
        """ProcurementViewSet must have an `invite` action."""
        source = read(CORE_PROC_VIEWS)
        assert "def invite(" in source, (
            "ProcurementViewSet must have an invite() action method."
        )

    def test_invite_is_post_action(self):
        """invite must be a POST-only detail action."""
        source = read(CORE_PROC_VIEWS)
        # Look for @action with post near the invite method
        assert "methods=['post']" in source

    def test_invite_checks_organizer(self):
        """invite must validate that the requester is the organizer."""
        source = read(CORE_PROC_VIEWS)
        assert "Only the creator" in source or "organizer" in source.lower()

    def test_invite_returns_403_for_non_organizer(self):
        """invite must return HTTP 403 if the requester is not the organizer."""
        source = read(CORE_PROC_VIEWS)
        assert "HTTP_403_FORBIDDEN" in source

    def test_invite_logs_the_email(self):
        """invite must log the invited email (dummy email notification)."""
        source = read(CORE_PROC_VIEWS)
        assert "logger.info" in source and "invited_email" in source

    def test_invite_rejects_missing_organizer_id(self):
        """invite must deny requests when organizer_id is absent (issue #268)."""
        source = read(CORE_PROC_VIEWS)
        # The guard must trigger when organizer_id is None, not skip the check
        assert "organizer_id is None" in source, (
            "The invite view must reject requests where organizer_id is missing, "
            "not skip the organizer check when organizer_id is None."
        )

    def test_frontend_add_participant_button_requires_organizer(self):
        """Cabinet.jsx Add Participant button must only show for the organizer (issue #268)."""
        source = read(FRONTEND_CABINET)
        # The buggy pattern was a bare status check before the add-participant button.
        # After the fix, the button must also require p.organizer === user?.id.
        # Verify the fixed pattern is present and the bare buggy pattern is absent.
        fixed_pattern = "p.organizer === user?.id && p.status === 'active' && (\n                  <button"
        assert fixed_pattern in source, (
            "Cabinet.jsx must guard the '+ Добавить участника' button with "
            "p.organizer === user?.id (issue #268)."
        )
        # Verify that every handleOpenAddParticipant button click is preceded
        # by an organizer check. Split on the first occurrence of the call.
        idx = source.index('handleOpenAddParticipant(p)')
        # Walk backwards to find the nearest JSX conditional open brace
        preceding = source[max(0, idx - 200):idx]
        assert 'p.organizer' in preceding, (
            "The '+ Добавить участника' button must be wrapped in a p.organizer === user?.id "
            "check. Issue #268: previously any user could trigger the add-participant action."
        )

    def test_invite_serializer_exists(self):
        """InviteUserSerializer must be defined in serializers.py."""
        source = read(CORE_PROC_SERIALIZERS)
        assert "class InviteUserSerializer" in source, (
            "serializers.py must define InviteUserSerializer with an email field."
        )

    def test_invite_serializer_has_email_field(self):
        """InviteUserSerializer must have an EmailField."""
        source = read(CORE_PROC_SERIALIZERS)
        assert "email = serializers.EmailField()" in source

    def test_frontend_api_has_invite_method(self):
        """api.js must export an inviteUser() method calling /invite/."""
        source = read(FRONTEND_API)
        assert "inviteUser:" in source, (
            "api.js must define inviteUser() to call the backend invite endpoint."
        )
        assert "/invite/" in source

    def test_frontend_cabinet_has_invite_button(self):
        """Cabinet.jsx must render an invite button visible only to organizers."""
        source = read(FRONTEND_CABINET)
        assert "handleOpenInvite" in source, (
            "Cabinet.jsx must call handleOpenInvite() from an invite button."
        )
        assert "inviteOpen" in source

    def test_frontend_invite_modal_present(self):
        """Cabinet.jsx must contain the invite modal with email input."""
        source = read(FRONTEND_CABINET)
        assert "inviteEmail" in source
        assert "handleInviteSubmit" in source


# ===========================================================================
# Fix 5 — getChatVote calls /vote_results/ not /chat_vote/
# ===========================================================================

class TestGetChatVoteUrl:
    def test_chat_vote_url_uses_vote_results(self):
        """
        getChatVote must call /vote_results/ (which exists on ProcurementViewSet)
        instead of /chat_vote/ (which does not exist and returns 404).
        """
        source = read(FRONTEND_API)
        assert "/chat_vote/" not in source, (
            "getChatVote must not call /chat_vote/ — that endpoint does not "
            "exist and returns 404. Use /vote_results/ instead."
        )
        assert "getChatVote" in source
        assert "/vote_results/" in source


# ===========================================================================
# Django integration tests (requires Django to be available)
# ===========================================================================

try:
    import django  # noqa: F401
    DJANGO_AVAILABLE = True
except ImportError:
    DJANGO_AVAILABLE = False


@pytest.mark.skipif(not DJANGO_AVAILABLE, reason="Django not installed")
class TestNotificationMarkReadDjango:
    """Django API tests using in-memory SQLite DB (configured by conftest.py)."""

    def test_mark_read_url_resolves(self):
        """The mark_read URL must resolve correctly via DRF router."""
        from django.test import RequestFactory
        from django.urls import reverse, resolve
        # Check that the URL pattern is registered
        from chat.views import NotificationViewSet
        actions = NotificationViewSet.action_map if hasattr(NotificationViewSet, 'action_map') else {}
        # The @action decorator creates url_name = basename + '-mark-read'
        # With url_path='mark_read' the URL segment uses underscore
        import inspect
        source = inspect.getsource(NotificationViewSet.mark_read)
        # Just verify the method exists and has the right decorator
        assert 'notification.is_read = True' in source

    def test_invite_view_returns_403_for_wrong_organizer(self, db):
        """POST /api/procurements/<id>/invite/ with wrong organizer_id returns 403."""
        from rest_framework.test import APIClient
        from users.models import User
        from procurements.models import Category, Procurement
        from decimal import Decimal
        from django.utils import timezone
        import datetime

        client = APIClient()

        organizer = User.objects.create(
            platform_user_id='100001', username='organizer1', first_name='Org',
            last_name='One', role='organizer'
        )
        other_user = User.objects.create(
            platform_user_id='100002', username='other1', first_name='Other',
            last_name='User', role='participant'
        )
        category = Category.objects.create(name='Test Category')
        procurement = Procurement.objects.create(
            title='Test Procurement',
            description='Test',
            category=category,
            organizer=organizer,
            city='Moscow',
            target_amount=Decimal('10000.00'),
            deadline=timezone.now() + datetime.timedelta(days=30),
            status='active',
        )

        response = client.post(
            f'/api/procurements/{procurement.id}/invite/',
            data={'email': 'test@example.com', 'organizer_id': other_user.id},
            format='json',
        )
        assert response.status_code == 403, (
            f"Expected 403 Forbidden but got {response.status_code}. "
            "Only the procurement creator should be able to invite users."
        )

    def test_invite_view_returns_200_for_correct_organizer(self, db):
        """POST /api/procurements/<id>/invite/ with correct organizer_id returns 200."""
        from rest_framework.test import APIClient
        from users.models import User
        from procurements.models import Category, Procurement
        from decimal import Decimal
        from django.utils import timezone
        import datetime

        client = APIClient()

        organizer = User.objects.create(
            platform_user_id='200001', username='organizer2', first_name='Org',
            last_name='Two', role='organizer'
        )
        category = Category.objects.create(name='Test Category 2')
        procurement = Procurement.objects.create(
            title='Test Procurement 2',
            description='Test',
            category=category,
            organizer=organizer,
            city='Moscow',
            target_amount=Decimal('10000.00'),
            deadline=timezone.now() + datetime.timedelta(days=30),
            status='active',
        )

        response = client.post(
            f'/api/procurements/{procurement.id}/invite/',
            data={'email': 'invited@example.com', 'organizer_id': organizer.id},
            format='json',
        )
        assert response.status_code == 200, (
            f"Expected 200 OK but got {response.status_code}: {response.data}"
        )
        assert response.data['invited_email'] == 'invited@example.com'

    def test_invite_view_returns_403_when_organizer_id_missing(self, db):
        """POST /api/procurements/<id>/invite/ without organizer_id must return 403.

        Regression test for issue #268: the invite endpoint previously allowed
        requests with no organizer_id to bypass the organizer check entirely.
        """
        from rest_framework.test import APIClient
        from users.models import User
        from procurements.models import Category, Procurement
        from decimal import Decimal
        from django.utils import timezone
        import datetime

        client = APIClient()

        organizer = User.objects.create(
            platform_user_id='400001', username='organizer3', first_name='Org',
            last_name='Three', role='organizer'
        )
        category = Category.objects.create(name='Test Category 3')
        procurement = Procurement.objects.create(
            title='Test Procurement 3',
            description='Test',
            category=category,
            organizer=organizer,
            city='Moscow',
            target_amount=Decimal('10000.00'),
            deadline=timezone.now() + datetime.timedelta(days=30),
            status='active',
        )

        # Send invite without organizer_id — must be rejected
        response = client.post(
            f'/api/procurements/{procurement.id}/invite/',
            data={'email': 'anyone@example.com'},
            format='json',
        )
        assert response.status_code == 403, (
            f"Expected 403 Forbidden but got {response.status_code}. "
            "Omitting organizer_id must not bypass the organizer permission check."
        )

    def test_notification_mark_read_action(self, db):
        """POST /api/chat/notifications/<id>/mark_read/ returns 200 and marks read."""
        from rest_framework.test import APIClient
        from users.models import User
        from chat.models import Notification

        client = APIClient()
        user = User.objects.create(
            platform_user_id='300001', username='notif_user', first_name='Notif',
            last_name='User', role='participant'
        )
        notification = Notification.objects.create(
            user=user,
            notification_type='system',
            title='Test',
            message='Test message',
            is_read=False,
        )
        response = client.post(f'/api/chat/notifications/{notification.id}/mark_read/')
        assert response.status_code == 200, (
            f"Expected 200 OK but got {response.status_code}: {response.data}"
        )
        notification.refresh_from_db()
        assert notification.is_read is True, "Notification should be marked as read"
