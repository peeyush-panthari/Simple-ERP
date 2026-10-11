"""FastAPI app factory - the equivalent of backend_py/app/__init__.py's create_app().

Differences from the Flask original, each noted where it happens below:
- No Flask-Limiter; rate limiting is `slowapi` (a Starlette/FastAPI port of
  the same limiter library) backed by Redis, matching DEPLOYMENT.md's
  existing RATE_LIMIT_STORAGE_URI guidance - the new stack just makes Redis
  the default rather than an optional upgrade.
- No `db.init_app`/pool config on a Flask app object - the engine is built
  once at import time in app/core/db.py with the identical pool settings.
- Global actor resolution (`@app.before_request` -> `load_actor()`) becomes
  per-router `Depends(get_current_actor)` - see app/core/auth.py's docstring.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.proxy import ProxyFixMiddleware
from app.core.db import SessionCleanupMiddleware, engine
from app.core.errors import register_error_handlers, too_many_requests, _problem_response
from app.core.rate_limit import limiter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("app")


async def _rate_limit_problem(request, exc: RateLimitExceeded):
    response = _problem_response(too_many_requests(f"Rate limit exceeded: {exc.detail}"))
    response.headers["Retry-After"] = "60"
    return response


class ProductionConfigError(RuntimeError):
    """Raised at boot when APP_ENV=production but development defaults remain."""


def create_app() -> FastAPI:
    errors = settings.production_config_errors
    if errors:
        raise ProductionConfigError(
            "APP_ENV=production but the configuration is not production-ready:\n"
            + "\n".join(f"  - {e}" for e in errors)
            + "\nSee DEPLOYMENT.md."
        )
    for warning in settings.production_config_warnings:
        logger.warning("config: %s", warning)

    app = FastAPI(title="Simple ERP API", version="0.1.0")

    app.add_middleware(SessionCleanupMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    limiter.enabled = settings.rate_limit_enabled
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_problem)

    register_error_handlers(app)

    from app.domains.identity.router import router as identity_router
    from app.domains.orders.router import router as orders_router
    from app.domains.warehouses.router import router as warehouses_router
    from app.domains.inventory.router import router as inventory_router
    from app.domains.parties.router import router as parties_router
    from app.domains.products.router import router as products_router
    from app.domains.procurement.router import router as procurement_router
    from app.domains.procurement.vendor_router import router as po_vendor_router
    from app.domains.grn.router import router as grn_router
    from app.domains.bom.router import router as bom_router
    from app.domains.production.router import router as production_router
    from app.domains.foundation.router import router as foundation_router
    from app.domains.foundation.masters_router import router as masters_router
    from app.domains.parties.children_router import router as party_children_router
    from app.domains.documents.router import router as documents_router
    from app.domains.notifications.router import router as notifications_router
    from app.domains.logistics.router import router as logistics_router
    from app.domains.email_config.router import router as email_config_router
    from app.domains.requisitions.router import router as requisitions_router
    from app.domains.sourcing.router import router as sourcing_router
    from app.domains.finance.router import router as finance_router
    from app.domains.system.router import router as system_router
    from app.domains.grn.qr_router import router as grn_qr_router
    from app.domains.mrp.router import router as mrp_router
    from app.domains.returns.router import router as returns_router
    from app.domains.supplier_scorecard.router import router as supplier_scorecard_router
    from app.domains.warehouse.landed_cost_router import router as landed_cost_router
    from app.domains.warehouse.bins_router import router as bins_router
    from app.domains.manufacturing.subcontracting_router import router as subcontracting_router
    from app.domains.drp.router import router as drp_router
    from app.domains.planning.forecasting_router import router as forecasting_router
    from app.domains.procurement.vendor_portal_router import router as vendor_portal_router
    from app.domains.logistics.freight_tms_router import router as freight_tms_router
    from app.domains.operations.traceability_router import router as traceability_router
    from app.domains.inventory.cycle_count_router import router as cycle_count_router
    from app.domains.logistics.statutory_logistics_router import router as statutory_logistics_router
    from app.domains.procurement.blanket_po_router import router as blanket_po_router
    from app.domains.warehouse.wms_mobile_router import router as wms_mobile_router
    from app.domains.warehouse.wave_picking_router import router as wave_picking_router
    from app.domains.sales.customer_portal_router import router as customer_portal_router
    from app.domains.quality.ipqc_router import router as ipqc_router
    from app.domains.procurement.avl_router import router as avl_router
    from app.domains.operations.capacity_planning_router import router as capacity_planning_router
    from app.domains.logistics.shipping_engine_router import router as shipping_engine_router
    from app.domains.planning.control_tower_router import router as control_tower_router

    app.include_router(identity_router)
    app.include_router(orders_router)
    app.include_router(warehouses_router)
    app.include_router(inventory_router)
    app.include_router(parties_router)
    app.include_router(products_router)
    app.include_router(procurement_router)
    app.include_router(po_vendor_router)
    app.include_router(grn_router)
    app.include_router(bom_router)
    app.include_router(production_router)
    app.include_router(foundation_router)
    app.include_router(masters_router)
    app.include_router(party_children_router)
    app.include_router(documents_router)
    app.include_router(notifications_router)
    app.include_router(logistics_router)
    app.include_router(finance_router)
    app.include_router(email_config_router)
    app.include_router(requisitions_router)
    app.include_router(sourcing_router)
    app.include_router(system_router)
    app.include_router(grn_qr_router)
    app.include_router(mrp_router)
    app.include_router(returns_router)
    app.include_router(supplier_scorecard_router)
    app.include_router(landed_cost_router)
    app.include_router(bins_router)
    app.include_router(subcontracting_router)
    app.include_router(drp_router)
    app.include_router(forecasting_router)
    app.include_router(vendor_portal_router)
    app.include_router(freight_tms_router)
    app.include_router(traceability_router)
    app.include_router(cycle_count_router)
    app.include_router(statutory_logistics_router)
    app.include_router(blanket_po_router)
    app.include_router(wms_mobile_router)
    app.include_router(wave_picking_router)
    app.include_router(customer_portal_router)
    app.include_router(ipqc_router)
    app.include_router(avl_router)
    app.include_router(capacity_planning_router)
    app.include_router(shipping_engine_router)
    app.include_router(control_tower_router)

    @app.get("/healthz")
    def healthz():
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz():
        try:
            with engine.connect() as conn:
                from sqlalchemy import text

                conn.execute(text("select 1"))
            return {"status": "ready"}
        except Exception:
            logger.exception("readiness check failed")
            from fastapi.responses import JSONResponse

            return JSONResponse(status_code=503, content={"status": "not-ready"})

    if settings.trusted_proxy_hops > 0:
        # Added last = outermost, so every other middleware and handler sees the real client address and scheme.
        app.add_middleware(ProxyFixMiddleware, hops=settings.trusted_proxy_hops)

    return app


app = create_app()
