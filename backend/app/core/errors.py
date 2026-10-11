"""RFC 9457 problem+json error handling.

`ProblemError` and the convenience constructors are ported verbatim from
backend_py/app/errors.py (they were already framework-agnostic). What
changes is how they get turned into an HTTP response: Flask used
`@app.errorhandler`; FastAPI uses `@app.exception_handler`. `RequestValidationError`
(FastAPI's native body/query validation failure) is translated into the same
`VALIDATION_FAILED` shape `app/validation.py`'s `parse_body()` produced, so a
client can't tell the difference from the original API.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app")


class ProblemError(Exception):
    def __init__(
        self,
        status: int,
        title: str,
        *,
        detail: str | None = None,
        code: str | None = None,
        type_: str = "about:blank",
        errors: list[dict] | None = None,
        meta: dict | None = None,
    ) -> None:
        super().__init__(title)
        self.status = status
        self.title = title
        self.detail = detail
        self.code = code
        self.type = type_
        self.errors = errors
        self.meta = meta

    def to_dict(self) -> dict:
        body: dict = {"type": self.type, "title": self.title, "status": self.status}
        if self.detail:
            body["detail"] = self.detail
        if self.code:
            body["code"] = self.code
        if self.errors:
            body["errors"] = self.errors
        if self.meta:
            body["meta"] = self.meta
        return body


def bad_request(detail: str, *, code: str | None = None) -> ProblemError:
    return ProblemError(400, "Bad Request", detail=detail, code=code)


def validation_failed(errors: list[dict], detail: str = "Validation failed") -> ProblemError:
    return ProblemError(400, "Validation Failed", detail=detail, code="VALIDATION_FAILED", errors=errors)


def unauthorized(detail: str = "Authentication required", *, code: str | None = None) -> ProblemError:
    return ProblemError(401, "Unauthorized", detail=detail, code=code)


def forbidden(detail: str = "You do not have permission to perform this action", *, code: str | None = None) -> ProblemError:
    return ProblemError(403, "Forbidden", detail=detail, code=code or "FORBIDDEN")


def not_found(detail: str = "Resource not found", *, code: str | None = None) -> ProblemError:
    return ProblemError(404, "Not Found", detail=detail, code=code)


def conflict(detail: str, *, code: str | None = None) -> ProblemError:
    return ProblemError(409, "Conflict", detail=detail, code=code)


def rule_violation(detail: str, *, code: str | None = None, meta: dict | None = None) -> ProblemError:
    return ProblemError(422, "Business Rule Violation", detail=detail, code=code, meta=meta)


def too_many_requests(detail: str = "Too many requests") -> ProblemError:
    return ProblemError(429, "Too Many Requests", detail=detail, code="RATE_LIMITED")


def _problem_response(problem: ProblemError) -> JSONResponse:
    return JSONResponse(
        status_code=problem.status,
        content=problem.to_dict(),
        media_type="application/problem+json",
    )


def _field_errors(exc: RequestValidationError) -> list[dict]:
    out = []
    for e in exc.errors():
        loc = [str(p) for p in e["loc"] if p not in ("body", "query")]
        out.append({"field": ".".join(loc), "message": e["msg"]})
    return out


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemError)
    async def _handle_problem(request: Request, exc: ProblemError):
        return _problem_response(exc)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation(request: Request, exc: RequestValidationError):
        # A malformed path parameter (a non-UUID where an id belongs) is "no such route" to the original
        # (Flask's <uuid:id> converter never matched), so it answers 404, not a body-validation 400.
        errors = exc.errors()
        if errors and all(e.get("loc") and e["loc"][0] == "path" for e in errors):
            return _problem_response(not_found("The requested resource was not found"))
        return _problem_response(validation_failed(_field_errors(exc)))

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(request: Request, exc: StarletteHTTPException):
        if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            return _problem_response(too_many_requests(str(exc.detail)))
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            return _problem_response(not_found("The requested resource was not found"))
        return _problem_response(ProblemError(exc.status_code, exc.detail or "Error", detail=str(exc.detail)))

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception):
        logger.exception("Unhandled error")
        return _problem_response(ProblemError(500, "Internal Server Error", detail="An unexpected error occurred"))
