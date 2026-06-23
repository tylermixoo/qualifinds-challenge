import re
from uuid import uuid4

from app.domain.workflow import (
    ExecutionRequest,
    ExecutionStatus,
    IntegrationName,
    StepExecutionResult,
    StepStatus,
    WorkflowExecution,
    WorkflowPlan,
)
from app.integrations.base import IntegrationCall, IntegrationClient


class WorkflowExecutor:
        def __init__(self, connector_registry: dict[IntegrationName, IntegrationClient]) -> None:
                    self._connector_registry = connector_registry

        async def execute(
                    self, workflow: WorkflowPlan, request: ExecutionRequest
        ) -> WorkflowExecution:
                    execution_id = f"exec_{uuid4().hex[:12]}"
                    step_outputs: dict[str, dict[str, object]] = {}
                    results: list[StepExecutionResult] = []
                    failed_steps: set[str] = set()

            for step in workflow.steps:
                            # Skip if any dependency failed
                            blocking = failed_steps.intersection(step.depends_on)
                            if blocking:
                                                results.append(
                                                                        StepExecutionResult(
                                                                                                    step_id=step.step_id,
                                                                                                    status=StepStatus.skipped,
                                                                                                    error=f"Skipped because dependency failed: {', '.join(blocking)}",
                                                                        )
                                                )
                                                failed_steps.add(step.step_id)
                                                continue

                            # Evaluate condition
                            if not evaluate_condition(step.condition, step_outputs, request.trigger_payload):
                                                results.append(
                                                                        StepExecutionResult(
                                                                                                    step_id=step.step_id,
                                                                                                    status=StepStatus.skipped,
                                                                                                    error="Condition evaluated to false.",
                                                                        )
                                                )
                                                continue

                            client = self._connector_registry.get(step.integration)
                            if client is None:
                                                results.append(
                                                                        StepExecutionResult(
                                                                                                    step_id=step.step_id,
                                                                                                    status=StepStatus.failed,
                                                                                                    error=f"Missing connector: {step.integration}",
                                                                        )
                                                )
                                                failed_steps.add(step.step_id)
                                                continue

                            payload = resolve_payload(step.input, request.trigger_payload, step_outputs)
                            integration_result = await client.call(
                                IntegrationCall(
                                    tenant_id=request.tenant_id,
                                    action=step.action,
                                    payload=payload,
                                    idempotency_key=f"{execution_id}:{step.step_id}",
                                )
                            )

            if integration_result.ok:
                                step_outputs[step.step_id] = integration_result.data
                                results.append(
                                    StepExecutionResult(
                                        step_id=step.step_id,
                                        status=StepStatus.succeeded,
                                        output=integration_result.data,
                                    )
                                )
else:
                results.append(
                                        StepExecutionResult(
                                                                    step_id=step.step_id,
                                                                    status=StepStatus.failed,
                                                                    error=integration_result.error,
                                        )
                )
                    failed_steps.add(step.step_id)

        any_failed = any(r.status == StepStatus.failed for r in results)
        final_status = ExecutionStatus.failed if any_failed else ExecutionStatus.succeeded

        return WorkflowExecution(
                        execution_id=execution_id,
                        workflow_id=workflow.workflow_id,
                        tenant_id=workflow.tenant_id,
                        status=final_status,
                        step_results=results,
        )


_TEMPLATE_RE = re.compile(r"\{\{(.+?)\}\}")


def resolve_template_value(
        expr: str,
        trigger_payload: dict[str, object],
        step_outputs: dict[str, dict[str, object]],
) -> object:
        expr = expr.strip()
    if expr.startswith("trigger."):
                key = expr[len("trigger."):]
        return trigger_payload.get(key, "")
    if expr.startswith("steps."):
                path = expr[len("steps."):]
        step_id, _, field = path.partition(".")
        return step_outputs.get(step_id, {}).get(field, "")
    return f"{{{{{expr}}}}}"


def resolve_value(
        value: object,
        trigger_payload: dict[str, object],
        step_outputs: dict[str, dict[str, object]],
) -> object:
        if not isinstance(value, str):
                    return value
                full_match = re.fullmatch(r"\{\{(.+?)\}\}", value)
    if full_match:
                return resolve_template_value(full_match.group(1), trigger_payload, step_outputs)

    def replacer(m: re.Match) -> str:  # type: ignore[type-arg]
                resolved = resolve_template_value(m.group(1), trigger_payload, step_outputs)
        return str(resolved)

    return _TEMPLATE_RE.sub(replacer, value)


def resolve_payload(
        raw_payload: dict[str, object],
        trigger_payload: dict[str, object],
        step_outputs: dict[str, dict[str, object]],
) -> dict[str, object]:
        return {
                    key: resolve_value(value, trigger_payload, step_outputs)
                    for key, value in raw_payload.items()
        }


_CONDITION_RE = re.compile(
        r"^\{\{(.+?)\}\}\s*(>|>=|<|<=|==|!=)\s*(.+)$"
)


def evaluate_condition(
        condition: str | None,
        step_outputs: dict[str, dict[str, object]],
        trigger_payload: dict[str, object],
) -> bool:
        if condition is None:
                    return True

    match = _CONDITION_RE.match(condition.strip())
    if not match:
                return True

    expr, operator, raw_literal = match.groups()
    lhs = resolve_template_value(expr.strip(), trigger_payload, step_outputs)

    try:
                literal: object = type(lhs)(raw_literal.strip())  # type: ignore[call-arg]
except (TypeError, ValueError):
        literal = raw_literal.strip()

    try:
                if operator == ">":
                                return bool(lhs > literal)  # type: ignore[operator]
        if operator == ">=":
                        return bool(lhs >= literal)  # type: ignore[operator]
        if operator == "<":
                        return bool(lhs < literal)  # type: ignore[operator]
        if operator == "<=":
                        return bool(lhs <= literal)  # type: ignore[operator]
        if operator == "==":
                        return lhs == literal
                    if operator == "!=":
                                    return lhs != literal
except TypeError:
        return True

    return True
