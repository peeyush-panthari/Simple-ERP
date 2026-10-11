"""PDF rendering fallback chain - ported 1:1 (behavior) from domain/pdf.ts.

Node's real tiers are Gotenberg -> Chromium (via puppeteer-core, OS-path
binary discovery) -> raw HTML passthrough, each falling through silently to
the next on any failure (never raising). This port keeps the same 3-tier,
silent-fallthrough shape, substituting WeasyPrint (a Python library-presence
check) for Chromium (an OS-binary-presence check) - the same "attempt it,
and gracefully degrade if it's not available" philosophy, not a behavior
change. Default `pdf_engine="html"` so the module works out of the box
without WeasyPrint's system-level dependencies (Pango/cairo/gdk-pixbuf)
being installed - "html" is one of Node's own genuine supported engine
values, not a fabricated stub.
"""

from __future__ import annotations

import logging
import uuid
import urllib.error
import urllib.request

from app.core.config import settings

logger = logging.getLogger("axon.document.pdf")

_weasyprint_checked = False
_weasyprint_available = False


def _weasyprint_module():
    global _weasyprint_checked, _weasyprint_available
    if not _weasyprint_checked:
        _weasyprint_checked = True
        try:
            import weasyprint  # noqa: F401

            _weasyprint_available = True
        except Exception as exc:  # pragma: no cover - depends on optional system deps
            logger.warning("weasyprint not available (%s) - falling back to the next PDF tier", exc)
            _weasyprint_available = False
    if _weasyprint_available:
        import weasyprint

        return weasyprint
    return None


def _try_gotenberg(html: str) -> dict | None:
    if settings.pdf_engine != "gotenberg" or not settings.gotenberg_url:
        return None
    boundary = uuid.uuid4().hex
    body = (
        (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="files"; filename="index.html"\r\n'
            "Content-Type: text/html\r\n\r\n"
        ).encode("utf-8")
        + html.encode("utf-8")
        + (
            f'\r\n--{boundary}\r\n'
            'Content-Disposition: form-data; name="landscape"\r\n\r\n'
            "false\r\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")
    )
    req = urllib.request.Request(
        f"{settings.gotenberg_url}/forms/chromium/convert/html",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status != 200:
                logger.warning("gotenberg returned %s - falling through", resp.status)
                return None
            return {"body": resp.read(), "content_type": "application/pdf", "engine": "gotenberg"}
    except (urllib.error.URLError, OSError) as exc:
        logger.warning("gotenberg render failed (%s) - falling through", exc)
        return None


def _try_weasyprint(html: str) -> dict | None:
    if settings.pdf_engine == "html":
        return None
    wp = _weasyprint_module()
    if wp is None:
        return None
    try:
        pdf_bytes = wp.HTML(string=html).write_pdf()
        return {"body": pdf_bytes, "content_type": "application/pdf", "engine": "weasyprint"}
    except Exception as exc:  # noqa: BLE001
        logger.warning("weasyprint render failed (%s) - falling through", exc)
        return None


def html_to_pdf(html: str) -> dict:
    """Returns {body: bytes, content_type: str, engine: str}. Always
    succeeds - the terminal "html" tier is a raw passthrough."""
    result = _try_gotenberg(html)
    if result:
        return result
    result = _try_weasyprint(html)
    if result:
        return result
    return {"body": html.encode("utf-8"), "content_type": "text/html; charset=utf-8", "engine": "html"}


def pdf_engine_available() -> bool:
    """Used by a readiness/diagnostic check, mirrors Node's pdfEngineAvailable()."""
    if settings.pdf_engine == "html":
        return True
    if settings.pdf_engine == "gotenberg":
        return bool(settings.gotenberg_url)
    return _weasyprint_module() is not None
