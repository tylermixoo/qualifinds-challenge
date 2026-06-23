# SOLUTION.md

## What I Changed and Why

### 1. Executor rewrite (highest priority — correctness bug)

**File:** `backend/app/services/executor.py`

The original executor had two fundamental correctness bugs:

- **It aborted the entire execution on any step failure.** If step 2 failed, steps 3–N were never executed, even if they had no dependency on step 2. I fixed this by tracking `failed_steps` as a set and only skipping steps whose `depends_on` intersects with that set. Independent steps always continue.
- **Conditions and templates were hardcoded.** `should_run_step` only worked for one specific string literal. `resolve_template` only resolved `{{trigger.company_id}}`. I replaced both with generic regex-based engines that work for any `{{trigger.X}}` or `{{steps.STEP_ID.FIELD}}` expression, and any `{{expr}} OP literal` condition (>, >=, <, <=, ==, !=).

Without these fixes, the product was a simulation — it appeared to work for the one hardcoded scenario but would fail silently for anything else.

### 2. SQLite persistence (viability for real users)

**File:** `backend/app/services/store.py`

The original store was in-memory. The docker-compose.yml already configured SQLite with a persistent volume, but it was never used. I connected them by implementing `WorkflowStore` using `aiosqlite`. Data now survives restarts.

I kept `InMemoryStore` for use in tests (via FastAPI's `dependency_overrides`).

### 3. FastAPI lifespan for DB initialization

**File:** `backend/app/main.py`

Added a `lifespan` context manager that calls `init_db()` at startup, creating the SQLite tables if they don't exist. Without this the app crashes on first use.

### 4. Dependency injection in routes

**File:** `backend/app/api/routes.py`

The original code had `planner`, `executor`, and `store` as module-level singletons. This makes testing impossible without monkeypatching. I converted them to `Depends()` functions, enabling `app.dependency_overrides` in tests.

I also:
- Changed `POST /workflows/plan` to return `201 Created` (correct HTTP semantics)
- Added `GET /workflows` to list workflows by tenant
- Added `GET /workflows/{id}/executions` to list executions for a workflow
- Set `idempotency_key` to `{execution_id}:{step_id}` (required for safe retries)

### 5. Domain model improvements

**File:** `backend/app/domain/workflow.py`

Added `created_at: datetime` fields to `WorkflowPlan` and `WorkflowExecution`. Any usable UI needs to sort and display by creation time.

### 6. Tests for the executor

**Files:** `backend/tests/test_executor.py`, `backend/tests/test_prototype_flow.py`

The original test suite had only one integration test covering the happy path. I added `test_executor.py` with 11 tests covering:
- Full happy path end-to-end
- Condition evaluates to false → step skipped, execution still succeeds
- Failed step does not abort independent steps
- Dependent step is skipped when its upstream fails
- Missing connector marks step failed without crashing
- Template resolution for trigger and step output fields
- Condition evaluation (true/false/None/unknown format)

Updated `test_prototype_flow.py` to use `dependency_overrides` with `InMemoryStore`, and added tests for listing workflows, 404 on missing workflow, and 403 on wrong tenant.

### 7. Frontend improvements

**Files:** `frontend/app/page.tsx`, `frontend/lib/api.ts`

- Added `created_at` to TypeScript types
- Made `triggerPayload` a proper parameter in `executeWorkflow`
- Added an editable `company_id` input field (was hardcoded before)
- Display step outputs (the JSON response from each integration)
- Display `assumptions` and `risks` from the plan
- Status emojis for visual clarity (✅ ❌ ⏭️)

---

## How to Run

```bash
docker compose up --build
```

- Frontend: http://localhost:3100
- Backend: http://localhost:8100
- Health: http://localhost:8100/health

**Run backend tests:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

---

## Risks That Remain

- **Planner is still keyword-based.** A real product needs an LLM to parse arbitrary instructions. The rule-based planner only works for the one specific scenario it was built for.
- **No real authentication.** The demo token is a placeholder. A production system needs proper JWT or OAuth.
- **SQLite is single-writer.** Fine for a local MVP, but needs to be replaced with PostgreSQL before any multi-instance deployment.
- **No retry logic.** If an integration call fails transiently, there is no retry mechanism. The step simply fails.
- **In-memory condition evaluation is limited.** The regex-based condition engine handles simple comparisons. Complex conditions (AND/OR, nested fields) are not supported.

---

## What I Would Do Next

1. **Replace the rule-based planner with an LLM call** (GPT-4 or Claude) that produces structured `WorkflowPlan` JSON given a natural-language instruction. This is the core value proposition.
2. **Add PostgreSQL** to support concurrent workers and horizontal scaling.
3. **Add retry logic with exponential backoff** for integration calls.
4. **Add a workflow execution queue** (e.g., Celery or async tasks) so long-running workflows don't block HTTP request cycles.
5. **Add proper authentication** (JWT with tenant scoping).
6. **Add an audit log** for compliance — who created and executed what, and when.
