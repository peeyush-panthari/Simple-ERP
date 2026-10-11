"""Request bodies, ported verbatim from backend_py/app/routes/auth.py,
users.py and roles.py - same Pydantic v2 `extra="forbid"` schemas, unchanged
field names/validators, so FastAPI's native body parsing accepts exactly
what the Flask routes accepted."""

from __future__ import annotations

import uuid as uuid_mod
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.email_type import Email
from app.core.permissions import ALL_PERMISSIONS

_PHONE_RE = r"^\+?[0-9 ()-]{7,20}$"


# ---- auth -------------------------------------------------------------


class LoginBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: Email
    password: str = Field(min_length=1, max_length=200)
    mfaCode: str | None = Field(default=None, pattern=r"^\d{6}$")
    mfaRecoveryCode: str | None = Field(default=None, min_length=4, max_length=64)
    tenantSlug: str | None = None




class RefreshBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refreshToken: str = Field(min_length=10)


class LogoutBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refreshToken: str | None = Field(default=None, min_length=10)


class ChangePasswordBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    currentPassword: str = Field(min_length=1)
    newPassword: str = Field(min_length=1, max_length=200)


class ForgotPasswordBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: Email
    tenantSlug: str | None = None


class ResetPasswordBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=10, max_length=256)
    newPassword: str = Field(min_length=1, max_length=200)
    tenantSlug: str | None = None


class AcceptInviteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=10, max_length=256)
    password: str = Field(min_length=1, max_length=200)
    displayName: str | None = Field(default=None, min_length=1, max_length=120)
    tenantSlug: str | None = None


# ---- users --------------------------------------------------------------


class RoleAssignment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    roleId: uuid_mod.UUID
    effectiveFrom: date | None = None
    effectiveTo: date | None = None
    scopes: list[str] = Field(default_factory=list)
    warehouseIds: list[uuid_mod.UUID] = Field(default_factory=list)
    factoryIds: list[uuid_mod.UUID] = Field(default_factory=list)


class CreateUserBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: Email
    displayName: str = Field(min_length=2, max_length=120)
    businessUnit: str | None = Field(default=None, max_length=80)
    managerId: uuid_mod.UUID | None = None
    phone: str | None = Field(default=None, pattern=_PHONE_RE)
    password: str | None = Field(default=None, max_length=200)
    status: str = "invited"
    roles: list[RoleAssignment] = Field(default_factory=list)

    @field_validator("email")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.lower()

    @field_validator("status")
    @classmethod
    def _status_ok(cls, v: str) -> str:
        if v not in ("invited", "active"):
            raise ValueError("must be 'invited' or 'active'")
        return v


class PatchUserBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    displayName: str | None = Field(default=None, min_length=2, max_length=120)
    businessUnit: str | None = Field(default=None, max_length=80)
    managerId: uuid_mod.UUID | None = None
    phone: str | None = Field(default=None, max_length=20)
    status: str | None = None
    mfaEnabled: bool | None = None
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("status")
    @classmethod
    def _status_ok(cls, v: str | None) -> str | None:
        if v is not None and v not in ("invited", "active", "suspended", "deactivated"):
            raise ValueError("invalid status")
        return v


class AssignRolesBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    roles: list[RoleAssignment]
    mode: str = "replace"

    @field_validator("mode")
    @classmethod
    def _mode_ok(cls, v: str) -> str:
        if v not in ("replace", "merge"):
            raise ValueError("must be 'replace' or 'merge'")
        return v


class MfaConfirmBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(pattern=r"^\d{6}$")


# ---- roles ----------------------------------------------------------------


class RoleBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=80)
    description: str = Field(default="", max_length=500)
    businessUnit: str | None = Field(default=None, max_length=80)
    permissions: list[str] = Field(default_factory=list)
    status: str = "active"

    @field_validator("permissions")
    @classmethod
    def _valid_perms(cls, v: list[str]) -> list[str]:
        for p in v:
            if p not in ALL_PERMISSIONS:
                raise ValueError(f"unknown permission: {p}")
        return v

    @field_validator("status")
    @classmethod
    def _status_ok(cls, v: str) -> str:
        if v not in ("active", "suspended"):
            raise ValueError("must be 'active' or 'suspended'")
        return v


class RolePatchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=2, max_length=80)
    description: str | None = Field(default=None, max_length=500)
    businessUnit: str | None = None
    permissions: list[str] | None = None
    status: str | None = None

    @field_validator("permissions")
    @classmethod
    def _valid_perms(cls, v):
        if v is not None:
            for p in v:
                if p not in ALL_PERMISSIONS:
                    raise ValueError(f"unknown permission: {p}")
        return v


class ReplacePermissionsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    permissions: list[str]

    @field_validator("permissions")
    @classmethod
    def _valid_perms(cls, v):
        for p in v:
            if p not in ALL_PERMISSIONS:
                raise ValueError(f"unknown permission: {p}")
        return v
