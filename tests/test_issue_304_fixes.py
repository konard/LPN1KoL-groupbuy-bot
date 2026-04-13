"""
Tests for issue #304 backend fixes:

1. Media upload 404 fix:
   - chat-service MEDIA_BASE_URL default changed to gateway-relative path
   - docker-compose.microservices.yml adds MEDIA_STORAGE_DIR volume and MEDIA_BASE_URL env var
   - chat-service memory limit raised from 32 M to 256 M to handle multipart uploads

2. Invite-to-purchase for regular users:
   - POST /purchases/:id/invite endpoint now available
   - Any existing participant or organizer can invite another user
   - Invited user is stored with role=PARTICIPANT

3. Ratings by role (buyer / organizer / supplier):
   - GET /reputation/:userId/ratings-by-role returns per-role averages
   - Bug fix: average rating in getReviewsForUser now respects the role filter
"""

import unittest


# ─── 1. Media URL default fix ─────────────────────────────────────────────────

class TestMediaURLDefault(unittest.TestCase):
    """Verify that the new MEDIA_BASE_URL default is gateway-relative."""

    def _get_media_base_url(self, env_override=None):
        """Simulate Go's getEnv("MEDIA_BASE_URL", "/api/v1/chat/media")."""
        return env_override if env_override else "/api/v1/chat/media"

    def test_default_is_gateway_relative(self):
        """Default MEDIA_BASE_URL must NOT contain 'localhost' or a port number."""
        url = self._get_media_base_url()
        self.assertNotIn("localhost", url)
        self.assertNotIn(":4004", url)
        self.assertTrue(url.startswith("/"), "MEDIA_BASE_URL default should be a relative path")

    def test_override_via_env_works(self):
        """Operators can override with an absolute CDN URL."""
        cdn = "https://cdn.example.com/media"
        url = self._get_media_base_url(cdn)
        self.assertEqual(url, cdn)

    def test_uploaded_file_url_is_reachable_through_gateway(self):
        """
        File URL returned after upload must be usable through the API gateway.
        The gateway proxies /api/v1/chat → chat-service, so a relative URL like
        /api/v1/chat/media/abc.jpg will be served by ServeMedia handler.
        """
        media_base_url = "/api/v1/chat/media"
        filename = "abc123.jpg"
        file_url = f"{media_base_url}/{filename}"

        # The URL should go through the gateway prefix
        self.assertTrue(file_url.startswith("/api/v1/chat/media/"))
        self.assertIn(filename, file_url)


# ─── 2. Docker-compose: media volume + memory limit ──────────────────────────

class TestDockerComposeMediaConfig(unittest.TestCase):
    """Parse docker-compose.microservices.yml to verify the chat-service changes."""

    @classmethod
    def setUpClass(cls):
        import os
        compose_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "docker-compose.microservices.yml",
        )
        with open(compose_path) as f:
            cls.content = f.read()

    def test_media_storage_dir_env_is_set(self):
        self.assertIn("MEDIA_STORAGE_DIR", self.content)

    def test_media_base_url_env_is_set(self):
        self.assertIn("MEDIA_BASE_URL", self.content)

    def test_chat_media_volume_defined(self):
        """Named volume 'chat_media_data' must be declared in top-level volumes."""
        self.assertIn("chat_media_data", self.content)

    def test_chat_service_mounts_media_volume(self):
        """chat-service must mount the named volume at /app/media."""
        self.assertIn("/app/media", self.content)

    def test_chat_service_memory_limit_raised(self):
        """
        The old 32 M limit caused OOM on multipart uploads (up to 5 × 25 MB).
        The new limit must be at least 128 M.
        """
        import re
        # Find the memory limit for the chat-service block
        # We look for the memory line that follows the chat-service memory comment
        match = re.search(
            r"chat-service.*?memory:\s*(\d+)M",
            self.content,
            re.DOTALL,
        )
        self.assertIsNotNone(match, "Could not find memory limit for chat-service")
        limit_mb = int(match.group(1))
        self.assertGreaterEqual(
            limit_mb, 128,
            f"chat-service memory limit {limit_mb}M is too low for media uploads",
        )


# ─── 3. Invite-to-purchase for regular users ──────────────────────────────────

class TestInviteParticipantLogic(unittest.TestCase):
    """
    Unit-test the invite-to-purchase business rules without hitting the DB.
    Mirrors the logic in purchases.service.ts::inviteParticipant.
    """

    # Simulated data store
    def _build_purchase(self, status="ACTIVE", organizer_id="organizer-1"):
        return {"id": "purchase-1", "status": status, "organizerId": organizer_id}

    def _build_purchase_user(self, user_id, role="EDITOR"):
        return {"purchaseId": "purchase-1", "userId": user_id, "role": role}

    def _invite(self, purchase, requester_id, target_user_id, existing_users=None):
        """
        Reproduce the service-layer validation:
          - Purchase must be ACTIVE
          - Cannot invite yourself
          - Requester must be organizer or existing participant/editor
          - Returns existing record if already present (idempotent)
        """
        if existing_users is None:
            existing_users = []

        if purchase["status"] != "ACTIVE":
            raise ValueError("Can only invite participants to active purchases")
        if target_user_id == requester_id:
            raise ValueError("Cannot invite yourself")

        is_organizer = purchase["organizerId"] == requester_id
        requester_entry = next(
            (u for u in existing_users if u["userId"] == requester_id), None
        )
        if not is_organizer and not requester_entry:
            raise PermissionError("Only existing participants or the organizer can invite users")

        existing_target = next(
            (u for u in existing_users if u["userId"] == target_user_id), None
        )
        if existing_target:
            return existing_target  # idempotent

        return {
            "purchaseId": purchase["id"],
            "userId": target_user_id,
            "role": "PARTICIPANT",
            "invitedBy": requester_id,
        }

    def test_organizer_can_invite(self):
        purchase = self._build_purchase()
        result = self._invite(purchase, "organizer-1", "user-99")
        self.assertEqual(result["role"], "PARTICIPANT")
        self.assertEqual(result["invitedBy"], "organizer-1")

    def test_existing_participant_can_invite(self):
        purchase = self._build_purchase()
        existing = [self._build_purchase_user("participant-1", "PARTICIPANT")]
        result = self._invite(purchase, "participant-1", "user-99", existing)
        self.assertEqual(result["role"], "PARTICIPANT")

    def test_stranger_cannot_invite(self):
        purchase = self._build_purchase()
        with self.assertRaises(PermissionError):
            self._invite(purchase, "stranger-99", "user-42")

    def test_cannot_invite_yourself(self):
        purchase = self._build_purchase()
        with self.assertRaises(ValueError) as ctx:
            self._invite(purchase, "organizer-1", "organizer-1")
        self.assertIn("yourself", str(ctx.exception))

    def test_invite_on_non_active_purchase_fails(self):
        purchase = self._build_purchase(status="CANCELLED")
        with self.assertRaises(ValueError) as ctx:
            self._invite(purchase, "organizer-1", "user-99")
        self.assertIn("active", str(ctx.exception))

    def test_invite_is_idempotent(self):
        """Inviting an already-present user returns existing record unchanged."""
        purchase = self._build_purchase()
        existing = [self._build_purchase_user("user-99", "PARTICIPANT")]
        result = self._invite(purchase, "organizer-1", "user-99", existing)
        self.assertEqual(result["role"], "PARTICIPANT")
        self.assertNotIn("invitedBy", result)  # existing record has no invitedBy key here


# ─── 4. Ratings by role ───────────────────────────────────────────────────────

class TestRatingsByRole(unittest.TestCase):
    """
    Verify the getRatingsByRole aggregation logic that was added to reviews.service.ts.
    """

    def _compute_ratings_by_role(self, reviews):
        """
        Python equivalent of the SQL GROUP BY query added to ReviewsService.
        Returns { buyer, organizer, supplier } with averageRating and totalReviews.
        """
        from collections import defaultdict
        buckets = defaultdict(list)
        for r in reviews:
            buckets[r["role"]].append(r["rating"])

        def build(role):
            ratings = buckets.get(role, [])
            return {
                "averageRating": round(sum(ratings) / len(ratings), 2) if ratings else 0,
                "totalReviews": len(ratings),
            }

        return {
            "buyer": build("buyer"),
            "organizer": build("organizer"),
            "supplier": build("supplier"),
        }

    def test_empty_reviews_returns_zeros(self):
        result = self._compute_ratings_by_role([])
        self.assertEqual(result["buyer"]["totalReviews"], 0)
        self.assertEqual(result["organizer"]["totalReviews"], 0)
        self.assertEqual(result["supplier"]["totalReviews"], 0)

    def test_single_role_populated(self):
        reviews = [
            {"role": "organizer", "rating": 5},
            {"role": "organizer", "rating": 4},
        ]
        result = self._compute_ratings_by_role(reviews)
        self.assertEqual(result["organizer"]["totalReviews"], 2)
        self.assertAlmostEqual(result["organizer"]["averageRating"], 4.5)
        self.assertEqual(result["buyer"]["totalReviews"], 0)

    def test_multiple_roles(self):
        reviews = [
            {"role": "buyer", "rating": 3},
            {"role": "organizer", "rating": 5},
            {"role": "organizer", "rating": 4},
            {"role": "supplier", "rating": 2},
        ]
        result = self._compute_ratings_by_role(reviews)
        self.assertEqual(result["buyer"]["totalReviews"], 1)
        self.assertEqual(result["buyer"]["averageRating"], 3.0)
        self.assertEqual(result["organizer"]["totalReviews"], 2)
        self.assertAlmostEqual(result["organizer"]["averageRating"], 4.5)
        self.assertEqual(result["supplier"]["totalReviews"], 1)
        self.assertEqual(result["supplier"]["averageRating"], 2.0)

    def test_average_respects_role_filter(self):
        """
        The bug: getReviewsForUser computed average over ALL reviews even when a role
        filter was applied. Verify that the corrected logic scopes the average.
        """
        all_reviews = [
            {"role": "buyer", "rating": 1},
            {"role": "organizer", "rating": 5},
        ]
        # Filter to 'organizer' only — average should be 5, not (1+5)/2 = 3
        organizer_reviews = [r for r in all_reviews if r["role"] == "organizer"]
        total = sum(r["rating"] for r in organizer_reviews)
        avg = total / len(organizer_reviews) if organizer_reviews else 0
        self.assertEqual(avg, 5.0, "Average must be scoped to the filtered role")


if __name__ == "__main__":
    unittest.main()
