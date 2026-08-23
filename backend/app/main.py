from fastapi import FastAPI


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

    Database and dependency checks will be added separately.
    """
    return {
        "status": "ok",
        "service": APP_NAME,
        "version": APP_VERSION,
    }
