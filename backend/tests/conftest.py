"""Ported from backend_py/tests/conftest.py.

Same philosophy as the original: a real local Postgres, a session-scoped app
(create tables + bootstrap once), and NO per-test transaction rollback -
tests write real committed rows and clean up after themselves (see
`fresh_admin`). `fresh_tenant_id` is still preferred over `default_tenant_id`
for any test that writes data, for the same "keep tests independent" reason.

`client` is a `fastapi.testclient.TestClient` in place of Flask's
`app.test_client()` - same synchronous request/response ergonomics.
"""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path


def _point_at_test_database() -> None:
    """Run the suite against its own database, never the dev one.

    The tests create tables and commit real rows, so sharing the dev database
    (whatever `.env` / DATABASE_URL points at) leaks test data into the dev app.
    `TEST_DATABASE_URL` wins; otherwise the dev URL with `_test` appended to the
    database name. Must run before `app.core.config` is imported.
    """
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        dev = os.environ.get("DATABASE_URL")
        env_file = Path(__file__).resolve().parents[1] / ".env"
        if not dev and env_file.exists():
            m = re.search(r"^DATABASE_URL=(.+)$", env_file.read_text(), re.M)
            dev = m.group(1).strip() if m else None
        if not dev:
            raise RuntimeError("Set TEST_DATABASE_URL (or DATABASE_URL) so the tests know which Postgres to use.")
        url = re.sub(r"/([^/?]+)(\?.*)?$", lambda m: f"/{m.group(1)}_test{m.group(2) or ''}", dev) if not re.search(r"_test(\?.*)?$", dev) else dev
    if not re.search(r"_test(\?.*)?$", url):
        raise RuntimeError(f"Refusing to run the tests against {url!r}: the database name must end in _test.")
    os.environ["DATABASE_URL"] = url


_point_at_test_database()

import pytest
from fastapi.testclient import TestClient

from app.core.bootstrap import bootstrap_tenant
from app.core.config import settings
from app.core.db import Base, SessionLocal, engine
from tests import flaskcompat


@pytest.fixture(scope="session")
def app():
    # Every route test logs in through the real login route, which is rate
    # limited to a handful of requests a minute - leave the limiter on and
    # the back half of the suite fails with 429s that look like auth bugs.
    settings.rate_limit_enabled = False

    from app.main import create_app

    application = create_app()
    # The test database is throwaway (its name must end in _test): rebuild the schema from the models
    # every run so a column added since the last run can't leave old tables behind.
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    bootstrap_tenant()
    flaskcompat.install(application)
    yield application


@pytest.fixture
def client(app):
    # Flask-shaped wrapper (see tests/flaskcompat.py) so tests ported from the original run as written.
    return flaskcompat.FlaskClient(TestClient(app))


@pytest.fixture
def default_tenant_id():
    return uuid.UUID(settings.default_tenant_id)


@pytest.fixture
def fresh_tenant_id():
    """A brand-new, never-reused tenant_id for tests that write data."""
    return uuid.uuid4()


@pytest.fixture
def fresh_admin(app, default_tenant_id):
    """A brand-new System-Admin user+password, isolated from any state left by
    manual smoke testing against the same dev database."""
    from app.core.security import hash_password
    from app.models.role import Role
    from app.models.user import User
    from app.models.user_role import UserRole

    email = f"test-admin-{uuid.uuid4().hex[:8]}@example.test"
    password = "TestAdmin#Passw0rd"
    role = Role.query.filter_by(tenant_id=default_tenant_id, name="System Admin").first()
    user = User(
        tenant_id=default_tenant_id,
        email=email,
        display_name="Test Admin",
        status="active",
        password_hash=hash_password(password),
    )
    SessionLocal.add(user)
    SessionLocal.flush()
    SessionLocal.add(UserRole(user_id=user.id, role_id=role.id))
    SessionLocal.commit()
    user_id = user.id
    yield {"email": email, "password": password, "id": str(user_id)}

    from app.models.password_history import PasswordHistory
    from app.models.session import Session

    for model in (Session, PasswordHistory, UserRole):
        model.query.filter_by(user_id=user_id).delete(synchronize_session=False)
    User.query.filter_by(id=user_id).delete(synchronize_session=False)
    SessionLocal.commit()
