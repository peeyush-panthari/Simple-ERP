"""Email/SMS transport - ported 1:1 (behavior) from domain/transport.ts.

SMTP via stdlib smtplib/email.mime (no new dependency - matches Node using
nodemailer as its one and only transport regardless of EMAIL_PROVIDER, which
is decorative). Twilio SMS via stdlib urllib (same stdlib-preference as
document_pdf.py's Gotenberg client). Push is a permanent-fail stub, never
attempted.

The SMTP permanent/transient heuristic is a regex over the STRINGIFIED
error text, not structured inspection of a response-code field - preserve
exactly, don't switch to real SMTP response-code inspection even though
Python's smtplib actually gives you one (that would be a real behavior
change, catching cases Node's text-matching heuristic misses).

Twilio's polarity is INVERTED from SMTP's (status<500 => permanent for
Twilio HTTP responses, vs 5xx => permanent for SMTP) - a genuinely different
rule, don't unify them. A raised exception talking to Twilio carries no
`permanent` flag at all (treated as transient).
"""

from __future__ import annotations

import base64
import logging
import re
import smtplib
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import parseaddr

from app.core.config import settings

logger = logging.getLogger("axon.notification.transport")

_PERMANENT_SMTP_RE = re.compile(r"\b5\d\d\b")
_PERMANENT_SMTP_PHRASES_RE = re.compile(r"no recipients|invalid address", re.IGNORECASE)

_smtp_singleton: smtplib.SMTP | None = None


@dataclass(frozen=True)
class MailSettings:
    """Everything needed to open a connection and address one message. `source` is "tenant" for a mailbox saved
    under Foundation > Email Config, "environment" for the deployment's SMTP_* settings."""

    host: str
    port: int
    security: str  # none | starttls | ssl
    user: str
    password: str
    from_header: str  # what recipients see, e.g. "Acme Accounts <accounts@acme.com>"
    reply_to: str | None = None
    source: str = "environment"

    @property
    def envelope_from(self) -> str:
        return parseaddr(self.from_header)[1] or self.from_header


def env_mail_settings() -> MailSettings:
    security = "ssl" if settings.smtp_secure else ("starttls" if settings.smtp_starttls else "none")
    return MailSettings(settings.smtp_host, settings.smtp_port, security, settings.smtp_user, settings.smtp_password, settings.smtp_from)


def _connect(mail: MailSettings, timeout: int = 10) -> smtplib.SMTP:
    if mail.security == "ssl":
        conn: smtplib.SMTP = smtplib.SMTP_SSL(mail.host, mail.port, timeout=timeout, context=ssl.create_default_context())
    else:
        conn = smtplib.SMTP(mail.host, mail.port, timeout=timeout)
        if mail.security == "starttls":
            conn.ehlo()
            conn.starttls(context=ssl.create_default_context())
            conn.ehlo()
    if mail.user:
        conn.login(mail.user, mail.password or "")
    return conn


def _get_transport() -> smtplib.SMTP:
    global _smtp_singleton
    if _smtp_singleton is None:
        _smtp_singleton = _connect(env_mail_settings())
    return _smtp_singleton


def verify_transport() -> bool:
    try:
        transport = _get_transport()
        transport.noop()
        return True
    except Exception as exc:  # noqa: BLE001
        logger.warning("SMTP verify failed: %s", exc)
        return False


def send_email(*, to: list[str], cc: list[str], bcc: list[str], subject: str, text: str, html: str | None, mail: MailSettings | None = None) -> dict:
    """Returns {ok, provider, error?, permanent?, providerMessageId?}. `mail` picks the mailbox (a tenant's Email
    Config); without it the deployment's SMTP_* settings are used, exactly as before."""
    mail = mail or env_mail_settings()
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = mail.from_header
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    if mail.reply_to:
        msg["Reply-To"] = mail.reply_to
    msg.attach(MIMEText(text, "plain"))
    if html:
        msg.attach(MIMEText(html, "html"))

    all_recipients = [*to, *cc, *bcc]
    global _smtp_singleton
    if mail.source == "environment":
        try:
            transport = _get_transport()
            transport.sendmail(mail.envelope_from, all_recipients, msg.as_string())
            return {"ok": True, "provider": "smtp"}
        except Exception as exc:  # noqa: BLE001
            _smtp_singleton = None  # a failed connection shouldn't be reused as the "singleton" next time
            return _smtp_failure(exc)
    # A tenant's own mailbox: one short-lived connection per message, so credentials edited in the UI apply at once.
    conn = None
    try:
        conn = _connect(mail)
        conn.sendmail(mail.envelope_from, all_recipients, msg.as_string())
        return {"ok": True, "provider": "smtp"}
    except Exception as exc:  # noqa: BLE001
        return _smtp_failure(exc)
    finally:
        if conn is not None:
            try:
                conn.quit()
            except Exception:  # noqa: BLE001
                pass


def _smtp_failure(exc: Exception) -> dict:
    error_text = str(exc)
    permanent = bool(_PERMANENT_SMTP_RE.search(error_text) or _PERMANENT_SMTP_PHRASES_RE.search(error_text))
    return {"ok": False, "provider": "smtp", "error": error_text, "permanent": permanent}


def send_sms(*, to: str, body: str) -> dict:
    if not settings.twilio_account_sid or not settings.twilio_auth_token:
        return {"ok": False, "provider": "twilio", "error": "SMS is not configured — set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_FROM", "permanent": True}

    form = urllib.parse.urlencode({"To": to, "From": settings.twilio_from or "", "Body": body}).encode("utf-8")
    auth = base64.b64encode(f"{settings.twilio_account_sid}:{settings.twilio_auth_token}".encode()).decode()
    req = urllib.request.Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json",
        data=form,
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return {"ok": True, "provider": "twilio"}
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")[:500]
        # Inverted polarity from SMTP: for an HTTP API, a 4xx is the caller's
        # own fault (permanent), a 5xx is the provider's fault (transient).
        return {"ok": False, "provider": "twilio", "error": body_text, "permanent": exc.code < 500}
    except (urllib.error.URLError, OSError) as exc:
        # No `permanent` key at all here - treated as transient/falsy,
        # matching Node exactly (a network-level exception sets no flag).
        return {"ok": False, "provider": "twilio", "error": str(exc)}


def send_push(*, to: str, body: str) -> dict:
    return {"ok": False, "provider": "fcm", "error": "Push delivery is not configured", "permanent": True}
