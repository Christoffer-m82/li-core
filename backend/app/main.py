from fastapi import FastAPI, HTTPException, status

from app.database import (
    DatabaseHealthError,
    MemoryReadError,
    database_health,
    get_primary_user,
)


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
    """
    return {
        "service": APP_NAME,
        "version": APP_VERSION,
        "status": "online",
    }


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """
    Verify that the FastAPI application itself is running.
    """
    return {
        "status": "ok",
        "service": APP_NAME,
        "version": APP_VERSION,
    }


@app.get("/health/database", tags=["system"])
def database_health_endpoint() -> dict[str, str | int]:
    """
    Verify the controlled connection between Li OS and PostgreSQL.
    """

    try:
        return database_health()

    except DatabaseHealthError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Li OS memory database is unavailable.",
        ) from exc


@app.get("/memory/primary-user", tags=["memory"])
def primary_user_endpoint() -> dict[str, str]:
    """
    Retrieve the active primary Li OS user through the controlled
    Memory API boundary.
    """

    try:
        return get_primary_user()

    except MemoryReadError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Li OS could not retrieve the primary user.",
        ) from exc