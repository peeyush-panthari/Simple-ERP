"""Port of the notification service's SMTP/Twilio permanent-vs-transient
failure heuristics, exercised directly against app.services.
notification_transport - no Node test file exists to port 1:1 from, so this
is fresh coverage of the ported behavior. Network calls are stubbed;
nothing here touches a real SMTP server or Twilio."""

import io
import urllib.error

import pytest

from app.services import notification_transport


class _FakeSmtpTransport:
    def __init__(self, exc: Exception | None):
        self._exc = exc

    def sendmail(self, *args, **kwargs):
        if self._exc:
            raise self._exc


class TestSmtpPermanentTransientHeuristic:
    def test_550_smtp_response_code_is_permanent(self, monkeypatch):
        monkeypatch.setattr(notification_transport, "_get_transport", lambda: _FakeSmtpTransport(Exception("550 5.1.1 Mailbox unavailable")))
        result = notification_transport.send_email(to=["a@example.com"], cc=[], bcc=[], subject="s", text="t", html=None)
        assert result == {"ok": False, "provider": "smtp", "error": "550 5.1.1 Mailbox unavailable", "permanent": True}

    def test_421_is_transient_not_permanent(self, monkeypatch):
        monkeypatch.setattr(notification_transport, "_get_transport", lambda: _FakeSmtpTransport(Exception("421 Service not available, closing transmission channel")))
        result = notification_transport.send_email(to=["a@example.com"], cc=[], bcc=[], subject="s", text="t", html=None)
        assert result["permanent"] is False

    def test_no_recipients_phrase_is_permanent_case_insensitively(self, monkeypatch):
        monkeypatch.setattr(notification_transport, "_get_transport", lambda: _FakeSmtpTransport(Exception("SMTPRecipientsRefused: No Recipients accepted")))
        result = notification_transport.send_email(to=["a@example.com"], cc=[], bcc=[], subject="s", text="t", html=None)
        assert result["permanent"] is True

    def test_invalid_address_phrase_is_permanent(self, monkeypatch):
        monkeypatch.setattr(notification_transport, "_get_transport", lambda: _FakeSmtpTransport(Exception("invalid address format")))
        result = notification_transport.send_email(to=["a@example.com"], cc=[], bcc=[], subject="s", text="t", html=None)
        assert result["permanent"] is True

    def test_bare_connection_refused_is_transient(self, monkeypatch):
        monkeypatch.setattr(notification_transport, "_get_transport", lambda: _FakeSmtpTransport(ConnectionRefusedError("[Errno 61] Connection refused")))
        result = notification_transport.send_email(to=["a@example.com"], cc=[], bcc=[], subject="s", text="t", html=None)
        assert result["permanent"] is False

    def test_success_returns_ok_true(self, monkeypatch):
        monkeypatch.setattr(notification_transport, "_get_transport", lambda: _FakeSmtpTransport(None))
        result = notification_transport.send_email(to=["a@example.com"], cc=[], bcc=[], subject="s", text="t", html=None)
        assert result == {"ok": True, "provider": "smtp"}


class TestTwilioInvertedPolarity:
    @pytest.fixture(autouse=True)
    def _configure_twilio(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "twilio_account_sid", "AC_test")
        monkeypatch.setattr(settings, "twilio_auth_token", "test_token")
        monkeypatch.setattr(settings, "twilio_from", "+15550000000")

    def test_unconfigured_sms_is_a_permanent_stub_failure(self, monkeypatch):
        from app.core.config import settings

        monkeypatch.setattr(settings, "twilio_account_sid", "")
        result = notification_transport.send_sms(to="+15551234567", body="hi")
        assert result == {"ok": False, "provider": "twilio", "error": "SMS is not configured — set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_FROM", "permanent": True}

    def test_4xx_http_error_is_permanent_inverted_from_smtp(self, monkeypatch):
        def _raise(*args, **kwargs):
            raise urllib.error.HTTPError("https://api.twilio.com/x", 400, "Bad Request", {}, io.BytesIO(b"bad number"))

        monkeypatch.setattr("urllib.request.urlopen", _raise)
        result = notification_transport.send_sms(to="+15551234567", body="hi")
        assert result["ok"] is False
        assert result["permanent"] is True

    def test_5xx_http_error_is_transient_inverted_from_smtp(self, monkeypatch):
        def _raise(*args, **kwargs):
            raise urllib.error.HTTPError("https://api.twilio.com/x", 503, "Service Unavailable", {}, io.BytesIO(b"try later"))

        monkeypatch.setattr("urllib.request.urlopen", _raise)
        result = notification_transport.send_sms(to="+15551234567", body="hi")
        assert result["ok"] is False
        assert result["permanent"] is False

    def test_network_exception_carries_no_permanent_flag_at_all(self, monkeypatch):
        def _raise(*args, **kwargs):
            raise urllib.error.URLError("connection refused")

        monkeypatch.setattr("urllib.request.urlopen", _raise)
        result = notification_transport.send_sms(to="+15551234567", body="hi")
        assert result["ok"] is False
        assert "permanent" not in result

    def test_success_returns_ok_true(self, monkeypatch):
        class _FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: _FakeResp())
        result = notification_transport.send_sms(to="+15551234567", body="hi")
        assert result == {"ok": True, "provider": "twilio"}


class TestPush:
    def test_push_is_always_a_permanent_immediate_failure_stub(self):
        result = notification_transport.send_push(to="device-token", body="hi")
        assert result == {"ok": False, "provider": "fcm", "error": "Push delivery is not configured", "permanent": True}
