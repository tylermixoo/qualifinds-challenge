from fastapi import APIRouter, Depends, HTTPException, status

from app.core.security import AuthContext, require_auth
from app.domain.workflow import (
    ExecutionRequest,
    WorkflowCreateRequest,
    WorkflowExecution,
    WorkflowPlan,
)
from app.integrations.mocks import build_mock_registry
from app.services.executor import WorkflowExecutor
from app.services.planner import RuleBasedPlanner
from app.services.store import WorkflowStore

router = APIRouter()


def get_planner() -> RuleBasedPlanner:
        return RuleBasedPlanner()


def get_executor() -> WorkflowExecutor:
        return WorkflowExecutor(connector_registry=build_mock_registry())


def get_store() -> WorkflowStore:
        return WorkflowStore()


@router.get("/health")
async def health() -> dict[str, str]:
        return {"status": "ok"}


@router.post("/workflows/plan", response_model=WorkflowPlan, status_code=status.HTTP_201_CREATED)
async def plan_workflow(
        request: WorkflowCreateRequest,
        auth: AuthContext = Depends(require_auth),
        planner: RuleBasedPlanner = Depends(get_planner),
        store: WorkflowStore = Depends(get_store),
) -> WorkflowPlan:
        ensure_tenant_access(request.tenant_id, auth)
        try:
                    workflow = await planner.plan(request)
except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return await store.save_workflow(workflow)


@router.get("/workflows", response_model=list[WorkflowPlan])
async def list_workflows(
        tenant_id: str,
        auth: AuthContext = Depends(require_auth),
        store: WorkflowStore = Depends(get_store),
) -> list[WorkflowPlan]:
        ensure_tenant_access(tenant_id, auth)
        return await store.list_workflows(tenant_id)


@router.get("/workflows/{workflow_id}", response_model=WorkflowPlan)
async def get_workflow(
        workflow_id: str,
        auth: AuthContext = Depends(require_auth),
        store: WorkflowStore = Depends(get_store),
) -> WorkflowPlan:
        workflow = await store.get_workflow(workflow_id)
        if workflow is None:
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found.")
                ensure_tenant_access(workflow.tenant_id, auth)
    return workflow


@router.post("/workflows/{workflow_id}/execute", response_model=WorkflowExecution)
async def execute_workflow(
        workflow_id: str,
        request: ExecutionRequest,
        auth: AuthContext = Depends(require_auth),
        executor: WorkflowExecutor = Depends(get_executor),
        store: WorkflowStore = Depends(get_store),
) -> WorkflowExecution:
        ensure_tenant_access(request.tenant_id, auth)
    if workflow_id != request.workflow_id:
                raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="Path workflow_id does not match request.workflow_id.",
                )
            workflow = await store.get_workflow(workflow_id)
    if workflow is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found.")
            ensure_tenant_access(workflow.tenant_id, auth)
    execution = await executor.execute(workflow, request)
    return await store.save_execution(execution)


@router.get("/workflows/{workflow_id}/executions", response_model=list[WorkflowExecution])
async def list_executions(
        workflow_id: str,
        auth: AuthContext = Depends(require_auth),
        store: WorkflowStore = Depends(get_store),
) -> list[WorkflowExecution]:
        workflow = await store.get_workflow(workflow_id)
    if workflow is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found.")
            ensure_tenant_access(workflow.tenant_id, auth)
    return await store.list_executions(workflow_id)


@router.get("/executions/{execution_id}", response_model=WorkflowExecution)
async def get_execution(
        execution_id: str,
        auth: AuthContext = Depends(require_auth),
        store: WorkflowStore = Depends(get_store),
) -> WorkflowExecution:
        execution = await store.get_execution(execution_id)
    if execution is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found.")
            ensure_tenant_access(execution.tenant_id, auth)
    return execution


def ensure_tenant_access(tenant_id: str, auth: AuthContext) -> None:
        if tenant_id != auth.tenant_id:
                    raise HTTPException(
                                    status_code=status.HTTP_403_FORBIDDEN,
                                    detail="Authenticated tenant does not match requested tenant.",
                    )
            
