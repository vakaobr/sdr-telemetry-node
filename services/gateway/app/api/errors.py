"""RFC-7807 problem+json error responses (03_ARCHITECTURE §4)."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_CONTENT_TYPE = "application/problem+json"


class Problem(Exception):
    """Raise anywhere in a route to produce an RFC-7807 response."""

    def __init__(
        self, status: int, title: str, detail: str = "", type_: str = "about:blank"
    ) -> None:
        self.status, self.title, self.detail, self.type = status, title, detail, type_


def _problem_response(
    status: int, title: str, detail: str = "", type_: str = "about:blank"
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        media_type=PROBLEM_CONTENT_TYPE,
        content={"type": type_, "title": title, "status": status, "detail": detail},
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(Problem)
    async def _problem(_req: Request, exc: Problem) -> JSONResponse:
        return _problem_response(exc.status, exc.title, exc.detail, exc.type)

    @app.exception_handler(StarletteHTTPException)
    async def _http(_req: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _problem_response(exc.status_code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation(_req: Request, exc: RequestValidationError) -> JSONResponse:
        return _problem_response(422, "validation error", str(exc.errors()[:3]))
