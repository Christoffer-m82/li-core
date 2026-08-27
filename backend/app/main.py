from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, status

from app.auth import (
    require_api_token,
    require_owner_api_token,
    require_theo_api_token,
)
from app.claude import ClaudeError
from app.database import (
    ConversationHistoryError,
    DatabaseHealthError,
    MemoryProposalError,
    MemoryReadError,
    MemoryWriteError,
    OwnerConfirmationError,
    append_conversation_message,
    confirm_memory_proposal,
    create_conversation,
    database_health,
    get_pending_memory_proposals,
    get_primary_user,
    get_recent_conversation_messages,
    propose_memory,
    recall_memory,
    review_memory_proposal,
    store_explicit_memory,
)
from app.li_runtime import LiRuntimeError, talk_to_li
from app.memory_capture import (
    MemoryCaptureAnalysis,
    MemoryCaptureError,
    analyze_memory_capture,
    apply_memory_capture,
    is_contextual_memory_change,
)
from app.schemas import (
    ExplicitMemoryCreate,
    ExplicitMemoryCreated,
    LiChatRequest,
    LiChatResponse,
    LiMemoryCaptureOutcome,
    MemoryProposalCreate,
    MemoryProposalCreated,
    MemoryProposalReview,
    MemoryProposalReviewResult,
    OwnerMemoryConfirmation,
    OwnerMemoryConfirmationResult,
    PendingMemoryProposal,
    RecalledMemory,
    TheoAutomatedReviewResult,
)
from app.theo_runtime import TheoRuntimeError, process_next_memory_proposal

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


@app.post(
    "/memory/proposals",
    response_model=MemoryProposalCreated,
    status_code=status.HTTP_201_CREATED,
    tags=["memory"],
    dependencies=[Depends(require_api_token)],
)
def create_memory_proposal_endpoint(
    payload: MemoryProposalCreate,
) -> MemoryProposalCreated:
    try:
        proposal_id = propose_memory(
            proposed_by_agent=payload.proposed_by_agent,
            memory_class=payload.memory_class,
            domain=payload.domain,
            value_text=payload.value_text,
            reason=payload.reason,
            truth_status=payload.truth_status,
            temporal_status=payload.temporal_status,
            sensitivity=payload.sensitivity,
            source_reference=payload.source_reference,
        )

    except MemoryProposalError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Li OS could not create the memory proposal.",
        ) from exc

    return MemoryProposalCreated(
        proposal_id=proposal_id,
    )


@app.get(
    "/theo/memory/proposals",
    response_model=list[PendingMemoryProposal],
    tags=["theo"],
    dependencies=[Depends(require_theo_api_token)],
)
def pending_memory_proposals_endpoint(
    limit: int = Query(
        default=20,
        ge=1,
        le=100,
    ),
) -> list[PendingMemoryProposal]:
    try:
        proposals = get_pending_memory_proposals(
            limit=limit,
        )

    except MemoryProposalError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Theo could not retrieve memory proposals.",
        ) from exc

    return [
        PendingMemoryProposal.model_validate(proposal)
        for proposal in proposals
    ]


@app.post(
    "/theo/memory/proposals/{proposal_id}/review",
    response_model=MemoryProposalReviewResult,
    tags=["theo"],
    dependencies=[Depends(require_theo_api_token)],
)
def review_memory_proposal_endpoint(
    proposal_id: UUID,
    payload: MemoryProposalReview,
) -> MemoryProposalReviewResult:
    try:
        result = review_memory_proposal(
            proposal_id=str(proposal_id),
            decision=payload.decision,
            review_note=payload.review_note,
            final_truth_status=payload.final_truth_status,
            final_temporal_status=payload.final_temporal_status,
            final_confidence=payload.final_confidence,
        )

    except MemoryProposalError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Theo could not review the memory proposal.",
        ) from exc

    return MemoryProposalReviewResult.model_validate(result)


@app.post(
    "/theo/memory/proposals/process-next",
    response_model=TheoAutomatedReviewResult,
    tags=["theo"],
    dependencies=[Depends(require_theo_api_token)],
)
def process_next_memory_proposal_endpoint() -> TheoAutomatedReviewResult:
    try:
        result = process_next_memory_proposal()
    except TheoRuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Theo could not safely complete the automated review.",
        ) from exc
    return TheoAutomatedReviewResult.model_validate(result.model_dump())


@app.post(
    "/owner/memory/proposals/{proposal_id}/confirm",
    response_model=OwnerMemoryConfirmationResult,
    tags=["owner"],
    dependencies=[Depends(require_owner_api_token)],
)
def owner_confirm_memory_proposal_endpoint(
    proposal_id: UUID,
    payload: OwnerMemoryConfirmation,
) -> OwnerMemoryConfirmationResult:
    try:
        result = confirm_memory_proposal(
            proposal_id=str(proposal_id),
            decision=payload.decision,
            note=payload.note,
        )

    except OwnerConfirmationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Owner memory confirmation failed.",
        ) from exc

    return OwnerMemoryConfirmationResult.model_validate(result)


@app.post(
    "/li/chat",
    response_model=LiChatResponse,
    tags=["li"],
    dependencies=[Depends(require_api_token)],
)
def li_chat_endpoint(
    payload: LiChatRequest,
) -> LiChatResponse:
    """
    Talk directly to Li.

    Governed correction and forgetting requests are applied before Li
    answers so the response can reflect the actual operation result.
    Other capture actions remain deferred until after the answer.

    Memory-capture or message-persistence failure does not prevent Li from
    answering. Failure to establish a valid conversation does.
    """

    try:
        conversation_id = (
            str(payload.conversation_id)
            if payload.conversation_id is not None
            else create_conversation(
                retention_policy=payload.retention_policy,
                retain_until=payload.retain_until,
                privacy_metadata=payload.privacy_metadata,
            )
        )
        recent_messages = get_recent_conversation_messages(
            conversation_id=conversation_id,
            limit=12,
        )
    except ConversationHistoryError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Li could not establish conversation history.",
        ) from exc

    conversation_context = "\n".join(
        f"{message['role']}: {message['content']}"
        for message in recent_messages
    ) or None
    conversation_history_error: str | None = None
    try:
        append_conversation_message(
            conversation_id=conversation_id,
            role="user",
            content=payload.message,
            privacy_metadata=payload.privacy_metadata,
        )
    except ConversationHistoryError:
        conversation_history_error = (
            "The user message could not be saved to conversation history."
        )

    capture_reference = f"li-chat:{conversation_id}:{uuid4()}"
    capture_outcomes = []
    capture_error: str | None = None
    runtime_context: str | None = None

    try:
        analysis = analyze_memory_capture(
            payload.message,
            conversation_context=conversation_context,
        )
    except MemoryCaptureError:
        analysis = None
        capture_error = "Automatic memory capture failed."

    if analysis is not None:
        change_analysis = MemoryCaptureAnalysis(
            candidates=[
                candidate
                for candidate in analysis.candidates
                if candidate.action in {"correct_explicit", "forget"}
            ]
        )

        if change_analysis.candidates:
            try:
                capture_outcomes = apply_memory_capture(
                    change_analysis,
                    source_reference=capture_reference,
                )
                statuses = ", ".join(
                    outcome.status for outcome in capture_outcomes
                )
                runtime_context = (
                    "Governed memory change result: success "
                    f"({statuses})."
                )
            except MemoryCaptureError:
                capture_error = "Automatic memory capture failed."
                runtime_context = (
                    "Governed memory change result: failed or blocked. "
                    "No success may be claimed."
                )
        elif is_contextual_memory_change(payload.message):
            runtime_context = (
                "Governed memory change result: blocked because the contextual "
                "request did not resolve to one safe, specific memory change. "
                "No memory was changed; ask the user to clarify the target or "
                "replacement value."
            )

    try:
        response = talk_to_li(
            payload.message,
            trusted_runtime_context=runtime_context,
            conversation_context=conversation_context,
        )

    except (ClaudeError, LiRuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Li could not complete the conversation.",
        ) from exc

    if analysis is not None and capture_error is None:
        deferred_analysis = MemoryCaptureAnalysis(
            candidates=[
                candidate
                for candidate in analysis.candidates
                if candidate.action not in {"correct_explicit", "forget"}
            ]
        )
        if deferred_analysis.candidates:
            try:
                capture_outcomes.extend(
                    apply_memory_capture(
                        deferred_analysis,
                        source_reference=capture_reference,
                    )
                )
            except MemoryCaptureError:
                capture_error = "Automatic memory capture failed."

    try:
        append_conversation_message(
            conversation_id=conversation_id,
            role="assistant",
            content=response,
        )
    except ConversationHistoryError:
        conversation_history_error = (
            "The latest exchange was not fully saved to conversation history."
        )

    return LiChatResponse(
        response=response,
        conversation_id=conversation_id,
        memory_capture=[
            LiMemoryCaptureOutcome.model_validate(
                outcome.model_dump()
            )
            for outcome in capture_outcomes
        ],
        memory_capture_reference=capture_reference,
        memory_capture_error=capture_error,
        conversation_history_error=conversation_history_error,
    )
