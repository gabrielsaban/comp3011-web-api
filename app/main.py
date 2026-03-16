from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.auth import AuthError
from app.routers import auth_probe, health

app = FastAPI(
    title="UK Road Traffic Accidents API",
    description=(
        "A data-driven REST API combining STATS19 accident records with MIDAS weather "
        "observations, spatial clustering, and route risk scoring."
    ),
    version="1.0.0",
    docs_url="/docs",
    openapi_url="/openapi.json",
)

app.include_router(health.router)
app.include_router(auth_probe.router)


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
            "error": {"code": "NOT_FOUND", "message": "The requested resource was not found."}
        },
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred."}},
    )
