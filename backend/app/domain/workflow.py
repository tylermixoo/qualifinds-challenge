from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class IntegrationName(StrEnum):
        hubspot = "hubspot"
        sap = "sap"
        slack = "slack"


class ExecutionStatus(StrEnum):
        queued = "queued"
        running = "running"
        succeeded = "succeeded"
        failed = "failed"
        cancelled = "cancelled"


class StepStatus(StrEnum):
        pending = "pending"
        running = "running"
        succeeded = "succeeded"
        failed = "failed"
        skipped = "skipped"


class WorkflowCreateRequest(BaseModel):
        tenant_id: str = Field(min_length=1)
        instruction: str = Field(min_length=10, max_length=5_000)


class WorkflowStep(BaseModel):
        step_id: str = Field(min_length=1)
        name: str = Field(min_length=1)
        integration: IntegrationName
        action: str = Field(min_length=1)
        input: dict[str, Any] = Field(default_factory=dict)
        depends_on: list[str] = Field(default_factory=list)
        condition: str | None = None


class WorkflowPlan(BaseModel):
        workflow_id: str = Field(min_length=1)
        tenant_id: str = Field(min_length=1)
        instruction: str = Field(min_length=10)
        steps: list[WorkflowStep] = Field(min_length=1)
        assumptions: list[str] = Field(default_factory=list)
        risks: list[str] = Field(default_factory=list)
        created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExecutionRequest(BaseModel):
        tenant_id: str = Field(min_length=1)
        workflow_id: str = Field(min_length=1)
        trigger_payload: dict[str, Any] = Field(default_factory=dict)


class StepExecutionResult(BaseModel):
        step_id: str = Field(min_length=1)
        status: StepStatus
        output: dict[str, Any] = Field(default_factory=dict)
        error: str | None = None


class WorkflowExecution(BaseModel):
        execution_id: str = Field(min_length=1)
        workflow_id: str = Field(min_length=1)
        tenant_id: str = Field(min_length=1)
        status: ExecutionStatus
        step_results: list[StepExecutionResult] = Field(default_factory=list)
        created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
