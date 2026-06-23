import logging
from pathlib import Path

import aiosqlite

from app.core.config import settings
from app.domain.workflow import WorkflowExecution, WorkflowPlan

logger = logging.getLogger(__name__)

_DB_PATH = settings.database_url.removeprefix("sqlite+aiosqlite:///")


async def _get_conn() -> aiosqlite.Connection:
        path = _DB_PATH.lstrip("/")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(path)
        conn.row_factory = aiosqlite.Row
        await conn.execute("PRAGMA journal_mode=WAL")
        return conn


async def init_db() -> None:
        """Create tables if they don't exist. Call once at startup."""
        async with await _get_conn() as db:
                    await db.execute(
                                    """
                                                CREATE TABLE IF NOT EXISTS workflows (
                                                                workflow_id TEXT PRIMARY KEY,
                                                                                tenant_id   TEXT NOT NULL,
                                                                                                data        TEXT NOT NULL
                                                                                                            )
                                                                                                                        """
                    )
                    await db.execute(
                        """
                        CREATE TABLE IF NOT EXISTS executions (
                            execution_id TEXT PRIMARY KEY,
                            workflow_id  TEXT NOT NULL,
                            tenant_id    TEXT NOT NULL,
                            data         TEXT NOT NULL
                        )
                        """
                    )
                    await db.commit()


class WorkflowStore:
        """Async SQLite-backed store."""

    async def save_workflow(self, workflow: WorkflowPlan) -> WorkflowPlan:
                async with await _get_conn() as db:
                                await db.execute(
                                                    """
                                                                    INSERT INTO workflows (workflow_id, tenant_id, data)
                                                                                    VALUES (?, ?, ?)
                                                                                                    ON CONFLICT(workflow_id) DO UPDATE SET data = excluded.data
                                                                                                                    """,
                                                    (workflow.workflow_id, workflow.tenant_id, workflow.model_dump_json()),
                                )
                                await db.commit()
                            return workflow

    async def get_workflow(self, workflow_id: str) -> WorkflowPlan | None:
                async with await _get_conn() as db:
                                async with db.execute(
                                                    "SELECT data FROM workflows WHERE workflow_id = ?", (workflow_id,)
                                ) as cursor:
                                                    row = await cursor.fetchone()
                                            if row is None:
                                                            return None
                                                        return WorkflowPlan.model_validate_json(row["data"])

    async def list_workflows(self, tenant_id: str) -> list[WorkflowPlan]:
                async with await _get_conn() as db:
                                async with db.execute(
                                    "SELECT data FROM workflows WHERE tenant_id = ? ORDER BY rowid DESC LIMIT 50",
                                    (tenant_id,),
                ) as cursor:
                                    rows = await cursor.fetchall()
                            return [WorkflowPlan.model_validate_json(row["data"]) for row in rows]

    async def save_execution(self, execution: WorkflowExecution) -> WorkflowExecution:
                async with await _get_conn() as db:
                                await db.execute(
                                    """
                                                    INSERT INTO executions (execution_id, workflow_id, tenant_id, data)
                                                                    VALUES (?, ?, ?, ?)
                                                                                    ON CONFLICT(execution_id) DO UPDATE SET data = excluded.data
                                                                                                    """,
                                    (
                                                            execution.execution_id,
                                                            execution.workflow_id,
                                                            execution.tenant_id,
                                                            execution.model_dump_json(),
                                    ),
                )
            await db.commit()
        return execution

    async def get_execution(self, execution_id: str) -> WorkflowExecution | None:
                async with await _get_conn() as db:
                                async with db.execute(
                                    "SELECT data FROM executions WHERE execution_id = ?", (execution_id,)
                ) as cursor:
                                    row = await cursor.fetchone()
                            if row is None:
                                            return None
                                        return WorkflowExecution.model_validate_json(row["data"])

    async def list_executions(self, workflow_id: str) -> list[WorkflowExecution]:
                async with await _get_conn() as db:
                                async with db.execute(
                                    "SELECT data FROM executions WHERE workflow_id = ? ORDER BY rowid DESC LIMIT 50",
                                    (workflow_id,),
                ) as cursor:
                                    rows = await cursor.fetchall()
                            return [WorkflowExecution.model_validate_json(row["data"]) for row in rows]


class InMemoryStore:
        """In-memory store used in tests."""

    def __init__(self) -> None:
                self._workflows: dict[str, WorkflowPlan] = {}
        self._executions: dict[str, WorkflowExecution] = {}

    async def save_workflow(self, workflow: WorkflowPlan) -> WorkflowPlan:
                self._workflows[workflow.workflow_id] = workflow
        return workflow

    async def get_workflow(self, workflow_id: str) -> WorkflowPlan | None:
                return self._workflows.get(workflow_id)

    async def list_workflows(self, tenant_id: str) -> list[WorkflowPlan]:
                return [w for w in self._workflows.values() if w.tenant_id == tenant_id]

    async def save_execution(self, execution: WorkflowExecution) -> WorkflowExecution:
                self._executions[execution.execution_id] = execution
        return execution

    async def get_execution(self, execution_id: str) -> WorkflowExecution | None:
                return self._executions.get(execution_id)

    async def list_executions(self, workflow_id: str) -> list[WorkflowExecution]:
                return [e for e in self._executions.values() if e.workflow_id == workflow_id]
