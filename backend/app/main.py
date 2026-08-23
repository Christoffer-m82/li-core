from fastapi import Depends, FastAPI, HTTPException, Query, status

from app.auth import require_api_token
from app.database import (
    DatabaseHealthError,
    MemoryReadError,
    MemoryWriteError,
    database_health,
    get_primary_user,
    recall_memory,
    store_explicit_memory,
)
from app.schemas import (
    ExplicitMemoryCreate,
    ExplicitMemoryCreated,
    RecalledMemory,
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
    return {
        "service": APP_NAME,
        "version": APP_VERSION,
        "status": "online",
    }


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": APP_NAME,
        "version": APP_VERSION,
    }


@app.get(
    "/health/database",
    tags=["system"],
    dependencies=[Depends(require_api_token)],
)
def database_health_endpoint() -> dict[str, str | int]:
    try:
        return database_health()

    except DatabaseHealthError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Li OS memory database is unavailable.",
        ) from exc


@app.get(
    "/memory/primary-user",
    tags=["memory"],
    dependencies=[Depends(require_api_token)],
)
def primary_user_endpoint() -> dict[str, str]:
    try:
        return get_primary_user()

    except MemoryReadError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Li OS could not retrieve the primary user.",
        ) from exc


@app.post(
    "/memory/explicit",
    response_model=ExplicitMemoryCreated,
    status_code=status.HTTP_201_CREATED,
    tags=["memory"],
    dependencies=[Depends(require_api_token)],
)
def explicit_memory_endpoint(
    payload: ExplicitMemoryCreate,
) -> ExplicitMemoryCreated:
    try:
        memory_id = store_explicit_memory(
            memory_class=payload.memory_class,
            domain=payload.domain,
            value=payload.value,
            title=payload.title,
            sensitivity=payload.sensitivity,
            private_to_li=payload.private_to_li,
            source_reference=payload.source_reference,
        )

    except MemoryWriteError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Li OS could not store the memory.",
        ) from exc

    return ExplicitMemoryCreated(
        memory_id=memory_id,
    )


@app.get(
    "/memory/recall",
    response_model=list[RecalledMemory],
    tags=["memory"],
    dependencies=[Depends(require_api_token)],
)
def recall_memory_endpoint(
    q: str = Query(
        ...,
        min_length=1,
        max_length=500,
        description="Memory search query.",
    ),
    domain: list[str] | None = Query(
        default=None,
        description="Optional memory domains to search.",
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=50,
    ),
) -> list[RecalledMemory]:
    try:
        memories = recall_memory(
            query=q,
            domains=domain,
            limit=limit,
        )

    except MemoryReadError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Li OS could not recall memory.",
        ) from exc

    return [
        RecalledMemory.model_validate(memory)
        for memory in memories
    ]