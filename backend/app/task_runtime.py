from datetime import datetime
from typing import Annotated, Literal, Protocol
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.action_instrumentation import ActionAttribution


class TaskProviderError(RuntimeError):
    """Raised when durable task storage cannot complete an operation."""


class TaskRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    title: str = Field(min_length=1, max_length=500)
    notes: str | None = Field(default=None, max_length=4000)
    due_at: datetime | None = None
    timezone: str | None = Field(default=None, max_length=100)
    status: Literal["open", "completed", "cancelled"]
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError("Task datetimes must include a timezone offset.")
    return value


class CreateTaskAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["task.create"]
    title: str = Field(min_length=1, max_length=500)
    notes: str | None = Field(default=None, max_length=4000)
    due_at: datetime | None = None
    timezone: str | None = Field(default=None, max_length=100)
    idempotency_key: str = Field(min_length=1, max_length=200)

    _validate_due_at = field_validator("due_at")(_aware)

    @model_validator(mode="after")
    def timezone_must_be_valid(self) -> "CreateTaskAction":
        if self.timezone:
            try:
                ZoneInfo(self.timezone)
            except ZoneInfoNotFoundError as exc:
                raise ValueError("Task timezone must be a valid IANA timezone.") from exc
        return self


class ListTasksAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["task.list"]
    due_before: datetime | None = None
    include_undated: bool = True
    max_results: int = Field(default=50, ge=1, le=100)

    _validate_due_before = field_validator("due_before")(_aware)


class CompleteTaskAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["task.complete"]
    task_id: UUID


class CancelTaskAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["task.cancel"]
    task_id: UUID


TaskActionRequest = Annotated[
    CreateTaskAction | ListTasksAction | CompleteTaskAction | CancelTaskAction,
    Field(discriminator="action"),
]


class TaskActionEnvelope(BaseModel):
    """Li-owned envelope; specialist contracts deliberately cannot represent it."""

    request: TaskActionRequest
    approved: bool = False
    attribution: ActionAttribution | None = None


class TaskActionOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["completed", "approval_required", "failed"]
    action: Literal["task.create", "task.list", "task.complete", "task.cancel"]
    tasks: list[TaskRecord] = Field(default_factory=list)
    task: TaskRecord | None = None
    message: str
    failed_items: int = Field(default=0, ge=0)


class TaskProvider(Protocol):
    def create_task(self, request: CreateTaskAction) -> object: ...
    def list_tasks(self, request: ListTasksAction) -> list[object]: ...
    def complete_task(self, request: CompleteTaskAction) -> object: ...
    def cancel_task(self, request: CancelTaskAction) -> object: ...


def execute_task_action(envelope: TaskActionEnvelope, provider: TaskProvider) -> TaskActionOutcome:
    request = envelope.request
    if not isinstance(request, ListTasksAction) and not envelope.approved:
        return TaskActionOutcome(
            status="approval_required",
            action=request.action,
            message=f"Approval required to execute {request.action}.",
        )

    if isinstance(request, ListTasksAction):
        try:
            candidates = provider.list_tasks(request)
        except Exception:  # noqa: BLE001 - provider failures must be quarantined
            return TaskActionOutcome(
                status="failed",
                action=request.action,
                message="Task listing failed; no task state was changed.",
                failed_items=1,
            )
        if not isinstance(candidates, list):
            candidates = [candidates]
        tasks: list[TaskRecord] = []
        failed_items = 0
        for candidate in candidates[: request.max_results]:
            try:
                tasks.append(TaskRecord.model_validate(candidate))
            except (ValidationError, ValueError, TypeError):
                failed_items += 1
        if failed_items and not tasks:
            return TaskActionOutcome(
                status="failed",
                action=request.action,
                message="Task provider returned no valid tasks.",
                failed_items=failed_items,
            )
        return TaskActionOutcome(
            status="completed",
            action=request.action,
            tasks=tasks,
            message=f"Found {len(tasks)} open task(s).",
            failed_items=failed_items,
        )

    operation = {
        CreateTaskAction: provider.create_task,
        CompleteTaskAction: provider.complete_task,
        CancelTaskAction: provider.cancel_task,
    }[type(request)]
    try:
        task = TaskRecord.model_validate(operation(request))
    except Exception:  # noqa: BLE001 - never claim an unvalidated mutation
        return TaskActionOutcome(
            status="failed",
            action=request.action,
            message=f"{request.action} failed; success was not confirmed.",
            failed_items=1,
        )
    return TaskActionOutcome(
        status="completed",
        action=request.action,
        task=task,
        message=f'{request.action} completed for "{task.title}".',
    )


class DatabaseTaskProvider:
    """Internal durable provider backed only by restricted li_api functions."""

    def create_task(self, request: CreateTaskAction) -> object:
        from app.database import create_task

        return create_task(**request.model_dump(exclude={"action"}))

    def list_tasks(self, request: ListTasksAction) -> list[object]:
        from app.database import list_open_tasks

        return list_open_tasks(**request.model_dump(exclude={"action"}))

    def complete_task(self, request: CompleteTaskAction) -> object:
        from app.database import complete_task

        return complete_task(task_id=str(request.task_id))

    def cancel_task(self, request: CancelTaskAction) -> object:
        from app.database import cancel_task

        return cancel_task(task_id=str(request.task_id))
