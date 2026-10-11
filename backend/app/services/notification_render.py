"""The notification service's bespoke tiny template language - ported 1:1
from domain/render.ts. Deliberately NOT Jinja2 (present only as an unused
transitive Flask dependency) and NOT the same mechanism as
document_templates.py's plain-function HTML builders - a different design
for a different reason: tenant-editable content needs a sandboxed, non-
Turing-complete language, quoted from the original file: "No arbitrary
expressions, no helpers that can reach outside the data object - templates
are tenant-editable content, so anything Turing-complete here would be a
sandbox-escape waiting to happen."

Supports `{{ path.to.value }}`, `{{#each list}}...{{/each}}`,
`{{#if value}}...{{/if}}`. Escaping is applied the SAME way to both the
plain-text and HTML bodies (see assert_no_header_injection/render below) -
do not give text and HTML separate rendering paths, that would silently
diverge from Node's real (if surprising) behavior.
"""

from __future__ import annotations

import re

from app.core.errors import rule_violation

_TOKEN_RE = re.compile(r"\{\{\s*([#/]?)([\w.]+)\s*\}\}")
_BLOCK_RE = re.compile(r"\{\{#(each|if)\s+([\w.]+)\s*\}\}([\s\S]*?)\{\{/\1\}\}")

_MAX_DEPTH = 8


def _resolve(data: dict, path: str):
    if path == "this":
        return data.get("this")
    value = data
    for part in path.split("."):
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return None
    return value


def _truthy(value) -> bool:
    if isinstance(value, list):
        return len(value) > 0
    return bool(value)


def escape_html(value: str) -> str:
    """Escapes &amp;/&lt;/&gt;/"/' - deliberately a WIDER escape set than
    document_templates.py's esc() (which only escapes &/</>). Applied to
    both text and HTML bodies since the render() function is shared - see
    module docstring."""
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")


def render_block(template: str, data: dict, depth: int = 0) -> str:
    if depth > _MAX_DEPTH:
        raise rule_violation("Template nesting is too deep", code="TEMPLATE_TOO_DEEP")

    def _block_sub(m: re.Match) -> str:
        helper, path, body = m.group(1), m.group(2), m.group(3)
        value = _resolve(data, path)
        if helper == "if":
            return render_block(body, data, depth + 1) if _truthy(value) else ""
        # helper == "each"
        if not isinstance(value, list):
            return ""
        pieces = []
        for item in value:
            if isinstance(item, dict):
                item_data = {**data, **item, "this": item}
            else:
                item_data = {**data, "this": item}
            pieces.append(render_block(body, item_data, depth + 1))
        return "".join(pieces)

    output = _BLOCK_RE.sub(_block_sub, template)

    def _token_sub(m: re.Match) -> str:
        marker, path = m.group(1), m.group(2)
        if marker:
            return ""  # stray #/ tokens outside a matched block render as empty
        value = _resolve(data, path)
        if value is None:
            return ""
        return escape_html(str(value))

    return _TOKEN_RE.sub(_token_sub, output)


def assert_no_header_injection(field: str, value: str) -> str:
    if re.search(r"[\r\n]", value):
        raise rule_violation(f"{field} may not contain line breaks", code="HEADER_INJECTION_BLOCKED")
    return value.strip()


_EMAIL_RE = re.compile(r'^[^\s@,;:<>"\']+@[^\s@,;:<>"\']+\.[A-Za-z]{2,}$')


def is_plausible_email(value: str) -> bool:
    return bool(_EMAIL_RE.match(value.strip()))


def render(*, subject: str | None, body_text: str, body_html: str | None, data: dict) -> dict:
    return {
        "subject": assert_no_header_injection("subject", render_block(subject, data)) if subject else None,
        "text": render_block(body_text, data),
        "html": render_block(body_html, data) if body_html else None,
    }


def next_attempt_delay_seconds(attempt: int, base_seconds: int) -> int:
    import random

    exponential = base_seconds * (2 ** max(attempt - 1, 0))
    jitter = random.uniform(0, base_seconds)
    return min(int(exponential + jitter), 3600)
