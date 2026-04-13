"""
Tests for issue #322 fix:

  Emails were not delivered even though SMTP credentials were correct.

  Root cause: the ``SMTP_FROM`` environment variable was defined in ``.env.example``
  and consumed by the notification-service code (``process.env.SMTP_FROM``), but
  it was never forwarded to the notification-service container in any of the
  docker-compose files or the Kubernetes manifest.

  As a result, the ``from`` address always fell back to the hard-coded default
  ``Groupbuy <notifications@example.com>``, which does not match ``SMTP_USER``.
  Providers such as Yandex reject messages where the envelope sender doesn't
  match the authenticated user, so every outgoing email was silently dropped.

  Fix: add ``SMTP_FROM: ${SMTP_FROM:-Groupbuy <notifications@example.com>}``
  to the notification-service ``environment`` block in all docker-compose files
  and add the corresponding ``SMTP_FROM`` env entry in the Kubernetes Deployment
  (sourced from the existing ``notification-service-secret`` Secret) plus the
  matching key in the Secret's ``stringData``.
"""
import os
import re
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")

COMPOSE_FILES = [
    os.path.join(ROOT, "docker-compose.light.yml"),
    os.path.join(ROOT, "docker-compose.microservices.yml"),
    os.path.join(ROOT, "docker-compose.unified.yml"),
]

K8S_NOTIFICATION = os.path.join(ROOT, "infrastructure", "k8s", "notification-service.yaml")
NOTIFICATION_SVC = os.path.join(ROOT, "services", "notification-service", "src", "index.js")


def read(path):
    with open(path) as f:
        return f.read()


# ===========================================================================
# Source-level checks — notification-service reads SMTP_FROM from env
# ===========================================================================

class TestNotificationServiceReadsSmtpFrom:
    def test_smtp_from_read_from_env(self):
        """
        The notification-service must read SMTP_FROM from the environment so
        that operators can override the sender address without rebuilding the
        image.
        """
        source = read(NOTIFICATION_SVC)
        assert "process.env.SMTP_FROM" in source, (
            "notification-service/src/index.js must read SMTP_FROM from "
            "process.env so the value can be supplied via docker-compose or k8s."
        )

    def test_smtp_from_used_in_sendmail(self):
        """
        The resolved ``config.smtp.from`` value must be passed as the ``from``
        field in every sendMail call.
        """
        source = read(NOTIFICATION_SVC)
        assert "from: config.smtp.from" in source, (
            "sendMail must use config.smtp.from so that the SMTP_FROM env var "
            "actually controls the sender address."
        )


# ===========================================================================
# Docker-compose checks — SMTP_FROM forwarded to notification-service
# ===========================================================================

class TestDockerComposeSmtpFrom:
    @pytest.mark.parametrize("compose_path", COMPOSE_FILES)
    def test_smtp_from_present_in_notification_service_env(self, compose_path):
        """
        Each docker-compose file must forward SMTP_FROM into the
        notification-service container so that operators can configure the
        sender address via the .env file without rebuilding images.
        """
        source = read(compose_path)
        filename = os.path.basename(compose_path)

        # Find the notification-service block and check SMTP_FROM appears
        # somewhere after it (before the next top-level service definition).
        # Match the top-level service definition (exactly two leading spaces)
        service_match = re.search(r"^  notification-service:\s*$", source, re.MULTILINE)
        assert service_match is not None, (
            f"{filename}: could not find top-level 'notification-service:' section."
        )

        service_pos = service_match.start()
        # Look for SMTP_FROM in the portion of the file that belongs to
        # notification-service (up to the next peer-level service definition).
        after_service = source[service_pos:]
        next_service_match = re.search(r"\n  \w[\w-]+:\s*$", after_service[1:], re.MULTILINE)
        if next_service_match:
            service_block = after_service[: 1 + next_service_match.start()]
        else:
            service_block = after_service

        assert "SMTP_FROM" in service_block, (
            f"{filename}: SMTP_FROM is missing from the notification-service "
            f"environment block. Without it the container always uses the "
            f"hard-coded default sender and Yandex SMTP rejects the emails."
        )


# ===========================================================================
# Kubernetes checks — SMTP_FROM in Deployment and Secret
# ===========================================================================

class TestKubernetesSmtpFrom:
    def test_smtp_from_in_k8s_deployment(self):
        """
        The Kubernetes Deployment for notification-service must include an
        SMTP_FROM env entry so that the sender address can be managed via the
        existing notification-service-secret Secret.
        """
        source = read(K8S_NOTIFICATION)
        assert "SMTP_FROM" in source, (
            "infrastructure/k8s/notification-service.yaml must define SMTP_FROM "
            "in the container env list (sourced from notification-service-secret)."
        )

    def test_smtp_from_in_k8s_secret(self):
        """
        The notification-service-secret Secret stringData must include an
        smtp-from key so operators know where to set the sender address.
        """
        source = read(K8S_NOTIFICATION)
        assert "smtp-from" in source, (
            "The notification-service-secret Secret in notification-service.yaml "
            "must include an 'smtp-from' key so operators can configure the "
            "sender address without editing the Deployment manifest."
        )
