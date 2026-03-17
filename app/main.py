from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.auth import AuthError
from app.core.cache import build_startup_caches, reset_startup_caches
from app.database import AsyncSessionLocal
from app.routers import (
    accidents,
    analytics,
    auth_probe,
    casualties,
    clusters,
    health,
    local_authorities,
    reference,
    regions,
    vehicles,
    weather_stations,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    if settings.cache_preload_on_startup:
        async with AsyncSessionLocal() as session:
            await build_startup_caches(session)
    else:
        reset_startup_caches()
    yield


app = FastAPI(
    title="UK Road Traffic Accidents API",
    description=(
        "A data-driven REST API combining STATS19 accident records with MIDAS weather "
        "observations, spatial clustering, and route risk scoring."
    ),
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(auth_probe.router)
app.include_router(accidents.router)
app.include_router(vehicles.router)
app.include_router(casualties.router)
app.include_router(reference.router)
app.include_router(regions.router)
app.include_router(local_authorities.router)
app.include_router(weather_stations.router)
app.include_router(clusters.router)
app.include_router(analytics.router)


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    details = [
        {
            "loc": list(error.get("loc", [])),
            "msg": error.get("msg", "Invalid value."),
            "type": error.get("type", "value_error"),
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed.",
                "details": details,
            }
        },
    )


@app.exception_handler(422)
async def unprocessable_entity_handler(request: Request, exc: Exception) -> JSONResponse:
    message = "Request validation failed."
    details: list[object] = []
    if isinstance(exc, HTTPException):
        message = exc.detail if isinstance(exc.detail, str) else message
        details = exc.detail if isinstance(exc.detail, list) else []

    return JSONResponse(
        status_code=422,
        content={"error": {"code": "VALIDATION_ERROR", "message": message, "details": details}},
    )


@app.exception_handler(400)
async def bad_request_handler(request: Request, exc: Exception) -> JSONResponse:
    message = "Bad request."
    details: list[object] = []
    if isinstance(exc, HTTPException):
        message = exc.detail if isinstance(exc.detail, str) else message
        details = exc.detail if isinstance(exc.detail, list) else []

    return JSONResponse(
        status_code=400,
        content={"error": {"code": "BAD_REQUEST", "message": message, "details": details}},
    )


@app.exception_handler(AuthError)
async def auth_error_handler(request: Request, exc: AuthError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "details": []}},
        headers=exc.headers,
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error": {
                "code": "NOT_FOUND",
                "message": "The requested resource was not found.",
                "details": [],
            }
        },
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred.",
                "details": [],
            }
        },
    )
