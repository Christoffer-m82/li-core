from fastapi import FastAPI, HTTPException, status

from app.database import DatabaseHealthError, database_health


APP_NAME = "Li OS Backend"
APP_VERSION = "0.1.0"


app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="Private backend and orchestration service for Li OS.",
)


@app.get("/", tags=["system"])
async def root() -> dict[str, str]:
    """
    Basic service identification endpoint.

    This endpoint intentionally exposes no personal information,
    database information, credentials, or internal configuration.
    """
    return {
        "service": APP_NAME,
        "version": APP_VERSION,
        "status": "online",
    }


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """
    Basic application health check.

    This verifies that the FastAPI application itself is running.
    """
    return {
        "status": "ok",
        "service": APP_NAME,
        "version": APP_VERSION,
    }


@app.get("/health/database", tags=["system"])
def database_health_endpoint() -> dict[str, str | int]:
    """
    Verify the controlled connection between the Li OS backend
    and the private memory database.

    The backend uses the restricted runtime database account and
    calls only the approved li_api.health_check() function.
    """

    try:
        return database_health()

    except DatabaseHealthError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Li OS memory database is unavailable.",
        ) from exc