"""FastAPI app for the compliance dashboard. Run: uvicorn api.main:app --host 0.0.0.0 --port 8000"""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.routes import make_router
from tps.jobs import JobRunner


def _allowed_origins() -> set[str]:
    raw = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000")
    return {o.strip().rstrip("/") for o in raw.split(",") if o.strip()}


def create_app(runner: JobRunner | None = None) -> FastAPI:
    real = runner is None

    @asynccontextmanager
    async def lifespan(_app):
        if real:  # the served app only; tests pass their own runner and never touch the DB
            from tps.config import setup_logging
            from tps.db import ensure_indexes
            setup_logging()
            ensure_indexes()
        yield

    app = FastAPI(lifespan=lifespan)
    allowed = _allowed_origins()

    @app.middleware("http")
    async def check_origin(request, call_next):
        # The browser always sends Origin on cross-site POSTs, uploads included.
        if request.method == "POST" and request.headers.get("origin") not in allowed:
            return JSONResponse({"error": "Cross-site request refused"}, status_code=403)
        return await call_next(request)

    @app.exception_handler(HTTPException)
    async def http_error(_request, exc):
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def bad_request(_request, exc):
        fields = ", ".join(str(e["loc"][-1]) for e in exc.errors())
        return JSONResponse({"error": f"Missing or invalid: {fields}"}, status_code=400)

    app.include_router(make_router(runner or JobRunner()))
    return app


_app = None


def __getattr__(name):  # `app` is built on first access, so importing this module stays cheap
    global _app
    if name == "app":
        _app = _app or create_app()
        return _app
    raise AttributeError(name)
