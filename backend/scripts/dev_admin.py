"""Create (or reset) a known-password System Admin for local development:

    cd backend && .venv/bin/python scripts/dev_admin.py [email] [password]

The first-run bootstrap only creates an admin when the tenant has no users, so
this is the way to get a login you know into a database that already has some.
"""

import sys
import uuid

from app.core.bootstrap import bootstrap_tenant
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User
from app.models.user_role import UserRole

email = sys.argv[1] if len(sys.argv) > 1 else "dev-admin@example.test"
password = sys.argv[2] if len(sys.argv) > 2 else "DevAdmin#Pass2026"

bootstrap_tenant()
tenant_id = uuid.UUID(settings.default_tenant_id)
role = Role.query.filter_by(tenant_id=tenant_id, name="System Admin").first()
user = User.query.filter_by(tenant_id=tenant_id, email=email).first()
if user is None:
    user = User(tenant_id=tenant_id, email=email, display_name="Dev Admin", status="active", password_hash=hash_password(password))
    SessionLocal.add(user)
    SessionLocal.flush()
    SessionLocal.add(UserRole(user_id=user.id, role_id=role.id))
else:
    user.password_hash = hash_password(password)
    user.status = "active"
    user.failed_attempts = 0
    user.locked_until = None
SessionLocal.commit()
print(f"dev admin ready: {email} / {password}")
