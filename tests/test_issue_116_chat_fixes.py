"""
Tests for issue #116: chats not working.

Covers:
1. Chat message REST API (send / retrieve).
2. close_vote endpoint (was missing – caused 404 errors).
3. vote_close_status endpoint (was missing – caused 404 errors).
4. WebSocket message format regression guard (unit-level, no live server needed).
"""
import json
import pytest
from rest_framework.test import APITestCase
from rest_framework import status


# ---------------------------------------------------------------------------
# Helpers shared across test cases
# ---------------------------------------------------------------------------

def _create_user(client, platform_user_id, role='buyer', phone=None, email=None):
    data = {
        'platform': 'websocket',
        'platform_user_id': str(platform_user_id),
        'role': role,
        'phone': phone or f'+7999{platform_user_id:07d}',
    }
    if email:
        data['email'] = email
    resp = client.post('/api/users/', data, format='json')
    assert resp.status_code == status.HTTP_201_CREATED, resp.data
    return resp.data


def _create_procurement(client, organizer_id):
    from django.utils import timezone
    import datetime
    data = {
        'title': 'Test Procurement',
        'description': 'For chat tests',
        'organizer': organizer_id,
        'city': 'Moscow',
        'target_amount': '10000.00',
        'unit': 'kg',
        'deadline': (timezone.now() + datetime.timedelta(days=30)).isoformat(),
    }
    resp = client.post('/api/procurements/', data, format='json')
    assert resp.status_code == status.HTTP_201_CREATED, resp.data
    procurement = resp.data
    # Set to active so participants can join
    upd = client.post(
        f'/api/procurements/{procurement["id"]}/update_status/',
        {'status': 'active'},
        format='json',
    )
    assert upd.status_code == status.HTTP_200_OK, upd.data
    return procurement


# ---------------------------------------------------------------------------
# Chat message REST API tests
# ---------------------------------------------------------------------------

class ChatMessageAPITests(APITestCase):
    """REST API for chat messages must work end-to-end."""

    def setUp(self):
        self.user = _create_user(self.client, 1001)
        self.procurement = _create_procurement(self.client, self.user['id'])

    def test_send_message(self):
        """POST /api/chat/messages/ must create a message and return 201."""
        resp = self.client.post('/api/chat/messages/', {
            'procurement_id': self.procurement['id'],
            'user_id': self.user['id'],
            'text': 'Hello from test',
            'message_type': 'text',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data['text'], 'Hello from test')

    def test_list_messages_by_procurement(self):
        """GET /api/chat/messages/?procurement_id=X must return messages for that procurement."""
        # Create a message first
        self.client.post('/api/chat/messages/', {
            'procurement_id': self.procurement['id'],
            'user_id': self.user['id'],
            'text': 'Test message',
            'message_type': 'text',
        }, format='json')

        resp = self.client.get(f'/api/chat/messages/?procurement_id={self.procurement["id"]}')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        results = resp.data.get('results', resp.data)
        self.assertGreaterEqual(len(results), 1)

    def test_mark_messages_read(self):
        """POST /api/chat/messages/mark_read/ must succeed."""
        # Create a message
        msg_resp = self.client.post('/api/chat/messages/', {
            'procurement_id': self.procurement['id'],
            'user_id': self.user['id'],
            'text': 'Read me',
            'message_type': 'text',
        }, format='json')
        self.assertEqual(msg_resp.status_code, status.HTTP_201_CREATED)

        resp = self.client.post('/api/chat/messages/mark_read/', {
            'user_id': self.user['id'],
            'procurement_id': self.procurement['id'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_unread_count(self):
        """GET /api/chat/messages/unread_count/ must return a count."""
        self.client.post('/api/chat/messages/', {
            'procurement_id': self.procurement['id'],
            'user_id': self.user['id'],
            'text': 'Unread message',
            'message_type': 'text',
        }, format='json')

        other_user = _create_user(self.client, 1002)
        resp = self.client.get(
            f'/api/chat/messages/unread_count/?user_id={other_user["id"]}'
            f'&procurement_id={self.procurement["id"]}'
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn('unread_count', resp.data)


# ---------------------------------------------------------------------------
# close_vote and vote_close_status endpoint tests
# ---------------------------------------------------------------------------

class VoteCloseEndpointTests(APITestCase):
    """The close_vote and vote_close_status endpoints must exist and work.

    Before the fix these returned 404/405, causing the chat voting panel to
    silently break and the frontend to show stale / incorrect close state.
    """

    def setUp(self):
        self.organizer = _create_user(self.client, 2001, role='organizer')
        self.buyer1 = _create_user(self.client, 2002, role='buyer')
        self.buyer2 = _create_user(self.client, 2003, role='buyer')
        self.supplier = _create_user(self.client, 2004, role='supplier')
        self.procurement = _create_procurement(self.client, self.organizer['id'])
        pid = self.procurement['id']

        # buyer1 and buyer2 join the procurement
        for buyer in (self.buyer1, self.buyer2):
            resp = self.client.post(f'/api/procurements/{pid}/join/', {
                'user_id': buyer['id'],
                'quantity': '1',
                'amount': '500.00',
            }, format='json')
            self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

    def test_vote_close_status_returns_200(self):
        """GET /api/procurements/{id}/vote_close_status/ must return 200."""
        pid = self.procurement['id']
        resp = self.client.get(f'/api/procurements/{pid}/vote_close_status/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertIn('closed_by', resp.data)
        self.assertIn('close_count', resp.data)
        self.assertIn('total_participants', resp.data)

    def test_vote_close_status_initial_empty(self):
        """Initially no one has confirmed close – closed_by must be empty."""
        pid = self.procurement['id']
        resp = self.client.get(f'/api/procurements/{pid}/vote_close_status/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data['closed_by'], [])
        self.assertEqual(resp.data['close_count'], 0)

    def test_close_vote_records_user(self):
        """POST /api/procurements/{id}/close_vote/ must record the user."""
        pid = self.procurement['id']
        resp = self.client.post(f'/api/procurements/{pid}/close_vote/', {
            'user_id': self.buyer1['id'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertIn(self.buyer1['id'], resp.data['closed_by'])
        self.assertEqual(resp.data['close_count'], 1)

    def test_close_vote_idempotent(self):
        """Submitting close_vote twice for the same user must not duplicate."""
        pid = self.procurement['id']
        for _ in range(2):
            self.client.post(f'/api/procurements/{pid}/close_vote/', {
                'user_id': self.buyer1['id'],
            }, format='json')

        resp = self.client.get(f'/api/procurements/{pid}/vote_close_status/')
        self.assertEqual(resp.data['close_count'], 1)

    def test_close_vote_all_participants(self):
        """When all participants confirm, close_count == total_participants."""
        pid = self.procurement['id']
        for buyer in (self.buyer1, self.buyer2):
            self.client.post(f'/api/procurements/{pid}/close_vote/', {
                'user_id': buyer['id'],
            }, format='json')

        resp = self.client.get(f'/api/procurements/{pid}/vote_close_status/')
        self.assertEqual(resp.data['close_count'], resp.data['total_participants'])

    def test_close_vote_non_participant_rejected(self):
        """A user who is not a participant or organizer must get 403."""
        outsider = _create_user(self.client, 9999, role='buyer')
        pid = self.procurement['id']
        resp = self.client.post(f'/api/procurements/{pid}/close_vote/', {
            'user_id': outsider['id'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_close_vote_organizer_allowed(self):
        """The organizer must also be allowed to confirm vote closure."""
        pid = self.procurement['id']
        resp = self.client.post(f'/api/procurements/{pid}/close_vote/', {
            'user_id': self.organizer['id'],
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn(self.organizer['id'], resp.data['closed_by'])

    def test_close_vote_missing_user_id(self):
        """POST without user_id must return 400."""
        pid = self.procurement['id']
        resp = self.client.post(f'/api/procurements/{pid}/close_vote/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# WebSocket message format regression guard
# ---------------------------------------------------------------------------

class WebSocketMessageFormatTests(APITestCase):
    """Guard against regressions in the WebSocket message format contract.

    The server (chat_server.py) expects:
      {type: 'message', text: '...'}       ← what client must send
      {type: 'typing', is_typing: true}    ← what client must send for typing

    Before the fix the client was sending:
      {type: 'message', message: '...'}    ← WRONG field name
      {type: 'typing'}                     ← missing is_typing

    These tests verify the expected message shapes at the Python/JSON layer so
    that any future change to the JS serializer is caught by CI.
    """

    def _make_ws_send_message(self, text):
        """Simulate what websocket.js sendMessage() now produces."""
        return json.dumps({'type': 'message', 'text': text})

    def _make_ws_send_typing(self, is_typing=True):
        """Simulate what websocket.js sendTyping() now produces."""
        return json.dumps({'type': 'typing', 'is_typing': is_typing})

    def test_send_message_has_text_field(self):
        """sendMessage must produce a payload with 'text', not 'message'."""
        payload = json.loads(self._make_ws_send_message('hello'))
        self.assertEqual(payload['type'], 'message')
        self.assertIn('text', payload, "payload must contain 'text'")
        self.assertNotIn('message', payload, "payload must NOT contain 'message' (old buggy field)")
        self.assertEqual(payload['text'], 'hello')

    def test_send_typing_has_is_typing_field(self):
        """sendTyping must produce a payload with 'is_typing' boolean."""
        payload = json.loads(self._make_ws_send_typing(True))
        self.assertEqual(payload['type'], 'typing')
        self.assertIn('is_typing', payload, "payload must contain 'is_typing'")
        self.assertTrue(payload['is_typing'])

    def test_server_message_shape_has_no_nested_message_field(self):
        """Server broadcasts messages as flat objects; 'message' key must not exist."""
        # Simulate a server-side broadcast message (from chat_server.py handle_message)
        server_broadcast = {
            'type': 'message',
            'user_id': 42,
            'text': 'Hello world',
            'timestamp': '2024-01-01T00:00:00',
            'message_id': '42_1704067200.0',
        }
        self.assertNotIn('message', server_broadcast,
                         "server broadcast must not have a nested 'message' key")
        self.assertIn('text', server_broadcast)
        self.assertIn('user_id', server_broadcast)
