"""GET /dashboard (control-tower dashboard) and GET /system-status. Ported 1:1
(behavior) from backend_py/app/routes/{analytics,system_status}.py.

/system-status is the monolith-appropriate replacement for the original
Node app's service-map page: the health of this process's own dependencies
(DB, document storage, PDF engine, mail transport) plus a static
rewrite-progress map. Same `analytics:read` gate as the dashboard.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.core.auth import Actor, require_permission
from app.core.config import settings
from app.core.db import session
from app.core import cache, messaging
from app.services import analytics_repo, document_pdf, document_storage, notification_transport

router = APIRouter(prefix="/api/v1", tags=["system"])

# Rewrite progress is documented here rather than derived - it's a fact
# about this project, not runtime state.
MODULES: list[dict] = [
    {"key": "identity", "label": "Identity & access", "status": "done"},
    {"key": "party", "label": "Vendors & customers", "status": "done"},
    {"key": "product", "label": "Products", "status": "done"},
    {"key": "bom", "label": "Bills of material", "status": "done"},
    {"key": "warehouse", "label": "Warehouses & GRN", "status": "done"},
    {"key": "inventory", "label": "Inventory ledger", "status": "done"},
    {"key": "procurement", "label": "Procurement", "status": "done"},
    {"key": "order", "label": "Orders", "status": "done"},
    {"key": "logistics", "label": "Logistics", "status": "done"},
    {"key": "finance", "label": "Finance", "status": "done"},
    {"key": "document", "label": "Documents", "status": "done"},
    {"key": "notification", "label": "Notifications", "status": "done"},
    {"key": "analytics", "label": "Analytics", "status": "done"},
    {"key": "gateway", "label": "Gateway", "status": "not_applicable"},
]


@router.get("/dashboard")
def dashboard(actor: Actor = Depends(require_permission("analytics:read"))):
    tenant_id = actor["tenant_id"]
    return cache.cached_json(f"dashboard:{tenant_id}", settings.dashboard_cache_seconds, lambda: analytics_repo.dashboard(tenant_id))


@router.get("/system-status")
def system_status(actor: Actor = Depends(require_permission("analytics:read"))):
    db_ok = True
    db_error = None
    try:
        session.execute(text("select 1"))
    except Exception as exc:  # noqa: BLE001
        db_ok = False
        db_error = str(exc)

    redis_used = settings.rate_limit_enabled or settings.dashboard_cache_seconds > 0
    checks = {
        "database": {"healthy": db_ok, "error": db_error},
        "documentStorage": {"backend": document_storage.active_backend(), "healthy": document_storage.healthy()},
        "pdfEngine": {"engine": settings.pdf_engine, "available": document_pdf.pdf_engine_available()},
        "mailTransport": {"healthy": notification_transport.verify_transport()},
        # Redis backs the rate limiter and the dashboard cache; RabbitMQ only
        # matters when notifications are delivered by the worker. Each is
        # reported as not-in-use rather than unhealthy when nothing needs it.
        "redis": {"enabled": redis_used, "healthy": cache.healthy() if redis_used else None},
        "rabbitmq": {"enabled": settings.async_notifications, "healthy": messaging.get_broker().healthy() if settings.async_notifications else None},
    }

    done = sum(1 for m in MODULES if m["status"] == "done")
    applicable = sum(1 for m in MODULES if m["status"] != "not_applicable")

    return {"checks": checks, "modules": MODULES, "modulesDone": done, "modulesTotal": applicable}
