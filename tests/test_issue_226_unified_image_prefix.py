"""Regression coverage for issue #226.

The unified compose stack must pull the images that this repository's CD
workflow publishes.  If it defaults to the old GHCR namespace, deployments can
run stale frontend/auth images and still return "Cannot POST /auth/register"
even though the current source tree has the correct nginx and gateway routes.
"""

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
COMPOSE = ROOT / "docker-compose.unified.yml"

EXPECTED_PREFIX_DEFAULT = "${IMAGE_PREFIX:-lpn1kol/groupbuy-bot}"
STALE_PREFIX_DEFAULT = "${IMAGE_PREFIX:-mixabyk1996/groupbuy-bot}"
PUBLISHED_IMAGE_SERVICES = {
    "django-admin",
    "core",
    "bot",
    "telegram-adapter",
    "mattermost-adapter",
    "websocket-server",
    "frontend-react",
    "gateway",
    "auth-service",
    "purchase-service",
    "payment-service",
    "chat-service",
    "notification-service",
    "analytics-service",
    "search-service",
    "reputation-service",
}


def _load_compose() -> dict:
    with COMPOSE.open() as f:
        return yaml.safe_load(f)


def test_unified_compose_uses_current_ghcr_namespace_by_default():
    compose = _load_compose()
    offenders = []

    for service_name in PUBLISHED_IMAGE_SERVICES:
        image = compose["services"][service_name].get("image", "")
        if EXPECTED_PREFIX_DEFAULT not in image:
            offenders.append(f"{service_name}: {image}")

    assert not offenders, (
        "docker-compose.unified.yml must default to the GHCR namespace published "
        "by this repository's CD workflow: " + ", ".join(offenders)
    )


def test_unified_frontend_does_not_pull_stale_legacy_frontend_image():
    compose_text = COMPOSE.read_text()
    frontend_image = _load_compose()["services"]["frontend-react"]["image"]

    assert STALE_PREFIX_DEFAULT not in compose_text
    assert frontend_image == (
        "${REGISTRY:-ghcr.io}/${IMAGE_PREFIX:-lpn1kol/groupbuy-bot}/frontend:${IMAGE_TAG:-main}"
    )
