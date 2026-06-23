"""Tests for the workflow executor - the most critical piece of the backend."""
import pytest

from app.domain.workflow import (
    ExecutionRequest,
    ExecutionStatus,
    IntegrationName,
    StepStatus,
    WorkflowPlan,
    WorkflowStep,
)
from app.integrations.mocks import build_mock_registry
from app.services.executor import WorkflowExecutor, evaluate_condition, resolve_payload

REGISTRY = build_mock_registry()
EXECUTOR = WorkflowExecutor(connector_registry=REGISTRY)

BASE_REQUEST = ExecutionRequest(
    tenant_id="tenant_test",
    workflow_id="wf_test",
    trigger_payload={"company_id": "company_demo"},
)


def make_plan(*steps: WorkflowStep) -> WorkflowPlan:
    return WorkflowPlan(
        workflow_id="wf_test",
        tenant_id="tenant_test",
        instruction="test instruction here",
        steps=list(steps),
    )


@pytest.mark.asyncio
async def test_full_happy_path() -> None:
    plan = make_plan(
        WorkflowStep(
            step_id="s1",
            name="Get company",
            integration=IntegrationName.hubspot,
            action="get_company",
            input={"company_id": "{{trigger.company_id}}"},
        ),
        WorkflowStep(
            step_id="s2",
            name="Enrich",
            integration=IntegrationName.sap,
            action="enrich_company",
            input={"company_id": "{{steps.s1.company_id}}"},
            depends_on=["s1"],
            condition="{{steps.s1.employee_count}} > 500",
        ),
        WorkflowStep(
            step_id="s3",
            name="Notify",
            integration=IntegrationName.slack,
            action="send_message",
            input={"channel": "#sales", "text": "Ready"},
            depends_on=["s2"],
        ),
    )
    execution = await EXECUTOR.execute(plan, BASE_REQUEST)
    assert execution.status == ExecutionStatus.succeeded
    results = {r.step_id: r for r in execution.step_results}
    assert results["s1"].status == StepStatus.succeeded
    assert results["s2"].status == StepStatus.succeeded
    assert results["s3"].status == StepStatus.succeeded


@pytest.mark.asyncio
async def test_condition_false_skips_step_execution_still_succeeds() -> None:
    plan = make_plan(
        WorkflowStep(
            step_id="s1",
            name="Get company",
            integration=IntegrationName.hubspot,
            action="get_company",
            input={"company_id": "{{trigger.company_id}}"},
        ),
        WorkflowStep(
            step_id="s2",
            name="Enrich",
            integration=IntegrationName.sap,
            action="enrich_company",
            input={},
            depends_on=["s1"],
            condition="{{steps.s1.employee_count}} > 1000",
        ),
    )
    execution = await EXECUTOR.execute(plan, BASE_REQUEST)
    assert execution.status == ExecutionStatus.succeeded
    results = {r.step_id: r for r in execution.step_results}
    assert results["s1"].status == StepStatus.succeeded
    assert results["s2"].status == StepStatus.skipped


@pytest.mark.asyncio
async def test_step_failure_does_not_abort_independent_steps() -> None:
    plan = make_plan(
        WorkflowStep(
            step_id="s_bad",
            name="Bad step",
            integration=IntegrationName.hubspot,
            action="nonexistent_action",
            input={},
        ),
        WorkflowStep(
            step_id="s_independent",
            name="Independent step",
            integration=IntegrationName.slack,
            action="send_message",
            input={"channel": "#sales", "text": "hello"},
        ),
    )
    execution = await EXECUTOR.execute(plan, BASE_REQUEST)
    results = {r.step_id: r for r in execution.step_results}
    assert results["s_bad"].status == StepStatus.failed
    assert results["s_independent"].status == StepStatus.succeeded
    assert execution.status == ExecutionStatus.failed


@pytest.mark.asyncio
async def test_dependent_step_skipped_when_dependency_fails() -> None:
    plan = make_plan(
        WorkflowStep(
            step_id="s1",
            name="Bad",
            integration=IntegrationName.hubspot,
            action="nonexistent_action",
            input={},
        ),
        WorkflowStep(
            step_id="s2",
            name="Depends on bad",
            integration=IntegrationName.slack,
            action="send_message",
            input={"channel": "#x", "text": "hi"},
            depends_on=["s1"],
        ),
    )
    execution = await EXECUTOR.execute(plan, BASE_REQUEST)
    results = {r.step_id: r for r in execution.step_results}
    assert results["s1"].status == StepStatus.failed
    assert results["s2"].status == StepStatus.skipped


@pytest.mark.asyncio
async def test_missing_connector_marks_step_failed() -> None:
    executor = WorkflowExecutor(connector_registry={})
    plan = make_plan(
        WorkflowStep(
            step_id="s1",
            name="No connector",
            integration=IntegrationName.hubspot,
            action="get_company",
            input={},
        ),
    )
    execution = await executor.execute(plan, BASE_REQUEST)
    assert execution.status == ExecutionStatus.failed
    assert execution.step_results[0].status == StepStatus.failed


def test_resolve_payload_trigger() -> None:
    result = resolve_payload(
        {"cid": "{{trigger.company_id}}"},
        trigger_payload={"company_id": "acme"},
        step_outputs={},
    )
    assert result["cid"] == "acme"


def test_resolve_payload_step_output() -> None:
    result = resolve_payload(
        {"name": "{{steps.s1.name}}"},
        trigger_payload={},
        step_outputs={"s1": {"name": "Acme Corp"}},
    )
    assert result["name"] == "Acme Corp"


def test_resolve_payload_missing_step_returns_empty() -> None:
    result = resolve_payload(
        {"x": "{{steps.missing.field}}"},
        trigger_payload={},
        step_outputs={},
    )
    assert result["x"] == ""


def test_condition_gt_true() -> None:
    assert evaluate_condition(
        "{{steps.s1.employee_count}} > 500",
        step_outputs={"s1": {"employee_count": 750}},
        trigger_payload={},
    )


def test_condition_gt_false() -> None:
    assert not evaluate_condition(
        "{{steps.s1.employee_count}} > 500",
        step_outputs={"s1": {"employee_count": 100}},
        trigger_payload={},
    )


def test_condition_none_always_runs() -> None:
    assert evaluate_condition(None, {}, {})


def test_condition_unknown_format_defaults_to_true() -> None:
    assert evaluate_condition("some unknown condition", {}, {})
