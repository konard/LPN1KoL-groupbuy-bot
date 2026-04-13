"""
Tests for issue #320 fix:

  Emails (OTP verification codes) were not being delivered via Yandex SMTP
  because the nodemailer transport was configured with only ``secure: port === 465``.

  On port 587 (STARTTLS) this left ``requireTLS`` unset, so nodemailer could
  attempt a plain-text connection — which Yandex SMTP refuses.

  Fix: ``requireTLS: port !== 465`` is now set so that STARTTLS is mandatory
  on port 587, matching Yandex's requirements.
"""
import os
import re
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
NOTIFICATION_SVC = os.path.join(ROOT, "services", "notification-service", "src", "index.js")
ENV_EXAMPLE = os.path.join(ROOT, ".env.example")
DEPLOY_DOC = os.path.join(ROOT, "docs", "DEPLOY-1GB-SERVER.md")


def read(path):
    with open(path) as f:
        return f.read()


# ===========================================================================
# Static / source-level checks for notification-service SMTP transport
# ===========================================================================

class TestSmtpTransportConfig:
    def test_require_tls_is_set(self):
        """
        The nodemailer transport must set requireTLS so that STARTTLS is
        mandatory on port 587. Without it Yandex SMTP rejects the connection.
        """
        source = read(NOTIFICATION_SVC)
        assert "requireTLS" in source, (
            "nodemailer createTransport must include requireTLS to force "
            "STARTTLS on port 587 (Yandex SMTP requirement)."
        )

    def test_require_tls_disabled_for_port_465(self):
        """
        requireTLS must be false/disabled when port is 465 (implicit SSL),
        because STARTTLS upgrade is not used on that port.
        """
        source = read(NOTIFICATION_SVC)
        # The expression should tie requireTLS to non-465 ports
        assert re.search(r"requireTLS\s*:\s*config\.smtp\.port\s*!==\s*465", source), (
            "requireTLS must be set to `config.smtp.port !== 465` so it is "
            "enabled only for STARTTLS ports (587) and disabled for SSL port 465."
        )

    def test_secure_still_set_for_port_465(self):
        """
        The ``secure`` option must remain tied to port 465 for backwards
        compatibility with implicit-TLS configurations.
        """
        source = read(NOTIFICATION_SVC)
        assert re.search(r"secure\s*:\s*config\.smtp\.port\s*===\s*465", source), (
            "The `secure` option must remain `config.smtp.port === 465` for "
            "implicit-TLS (port 465) support."
        )


# ===========================================================================
# Documentation checks
# ===========================================================================

class TestSmtpDocs:
    def test_env_example_mentions_yandex(self):
        """
        .env.example should contain a comment about Yandex SMTP configuration
        to guide users who encounter this issue.
        """
        source = read(ENV_EXAMPLE)
        assert "yandex" in source.lower() or "Yandex" in source, (
            ".env.example should mention Yandex SMTP settings to guide users."
        )

    def test_env_example_smtp_from_warning(self):
        """
        .env.example should warn that SMTP_FROM email must match SMTP_USER
        for Yandex.
        """
        source = read(ENV_EXAMPLE)
        assert "SMTP_FROM" in source and ("SMTP_USER" in source or "match" in source.lower()), (
            ".env.example should note that SMTP_FROM must match SMTP_USER for Yandex."
        )

    def test_deploy_doc_includes_smtp_from(self):
        """
        The deployment doc (DEPLOY-1GB-SERVER.md) should show an SMTP_FROM
        example that uses the same address as SMTP_USER (Yandex requirement).
        """
        source = read(DEPLOY_DOC)
        assert "SMTP_FROM" in source, (
            "DEPLOY-1GB-SERVER.md should include SMTP_FROM in the Yandex SMTP "
            "example to show that the sender address must match SMTP_USER."
        )
