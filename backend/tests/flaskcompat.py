"""Lets tests written against the original Flask app run unchanged against FastAPI.

The 82 test files ported from `backend_py/tests` use Flask's test client
(`client.get(..., query_string=..., data=...)`, `resp.get_json()`, `resp.data`) and
Flask-SQLAlchemy's `db.session`. Rather than rewrite ~600 tests - and risk changing what they
assert - this module gives them the same surface over `fastapi.testclient.TestClient` and the
scoped `SessionLocal`. It carries no behaviour of its own: a request is passed straight through.
"""

from __future__ import annotations

import contextlib
import uuid
from typing import Any

import sqlalchemy as sa
from fastapi.testclient import TestClient

from app.core.db import SessionLocal, _request_scope


class _DB:
    """Stand-in for Flask-SQLAlchemy's `db` (only the parts the tests use)."""

    session = SessionLocal
    func = sa.func
    or_ = staticmethod(sa.or_)
    and_ = staticmethod(sa.and_)


db = _DB()


class FlaskResponse:
    """A httpx response with Flask's response helpers on top."""

    def __init__(self, resp):
        self._resp = resp

    def __getattr__(self, name: str):
        return getattr(self._resp, name)

    def get_json(self, silent: bool = False):
        try:
            return self._resp.json()
        except ValueError:
            if silent:
                return None
            raise

    @property
    def data(self) -> bytes:
        return self._resp.content

    def get_data(self, as_text: bool = False):
        return self._resp.text if as_text else self._resp.content

    @property
    def content_type(self) -> str:
        return self._resp.headers.get("content-type", "")

    @property
    def mimetype(self) -> str:
        return self.content_type.split(";")[0].strip()


class FlaskClient:
    def __init__(self, client: TestClient):
        self._client = client
        self.application = client.app  # Flask's `client.application`

    def _send(self, method: str, url: str, *, json: Any = None, headers: dict | None = None, query_string: dict | None = None, data: Any = None, content_type: str | None = None, params: dict | None = None, content: Any = None, environ_base: dict | None = None):
        hdrs = dict(headers or {})
        if content_type:
            hdrs["Content-Type"] = content_type
        kwargs: dict[str, Any] = {"headers": hdrs, "params": query_string if query_string is not None else params}
        if json is not None:
            kwargs["json"] = json
        elif data is not None or content is not None:
            kwargs["content"] = data if data is not None else content
        client = self._client
        peer = (environ_base or {}).get("REMOTE_ADDR")
        if peer:  # Flask's environ_base={"REMOTE_ADDR": ...}: the socket peer for this request
            client = TestClient(self.application, client=(peer, 50000))
        return FlaskResponse(client.request(method, url, **kwargs))

    def get(self, url: str, **kw):
        return self._send("GET", url, **kw)

    def post(self, url: str, **kw):
        return self._send("POST", url, **kw)

    def put(self, url: str, **kw):
        return self._send("PUT", url, **kw)

    def patch(self, url: str, **kw):
        return self._send("PATCH", url, **kw)

    def delete(self, url: str, **kw):
        return self._send("DELETE", url, **kw)


@contextlib.contextmanager
def _app_context():
    """Flask-SQLAlchemy scopes a session to the app context and discards it when the context ends, and
    nested contexts get their own. Do the same: each block gets a fresh scope (so it never reads rows an
    earlier block cached before a request changed them) while an enclosing block's session - a fixture
    that yields inside `with app.app_context():` - is left intact."""
    token = _request_scope.set(uuid.uuid4().hex)
    try:
        yield
    finally:
        SessionLocal.remove()
        _request_scope.reset(token)


def install(application) -> None:
    """Give the FastAPI app Flask's `app.app_context()` / `app.test_client()`."""
    application.app_context = _app_context
    application.test_client = lambda: FlaskClient(TestClient(application))
