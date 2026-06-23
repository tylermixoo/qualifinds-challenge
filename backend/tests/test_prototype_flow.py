import pytest
from fastapi.testclient import TestClient

from app.api.routes import get_store
from app.main import create_app
from app.services.store import InMemoryStore

AUTH_HEADERS = {
    "Authorization": "Bearer demo-token",
    "X-Tenant-Id": "tenant_acme",
    "X-User-Id": "user_123",
}


def build_test_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_store] = lambda: InMemoryStore()
    return TestClient(app)


def test_prototype_can_plan_and_execute_workflow() -> None:
    client = build_test_client()

    plan_response = client.post(
        "/workflows/plan",
        headers=AUTH_HEADERS,
        json={
            "tenant_id": "tenant_acme",
            "instruction": (
                "When a new HubSpot lead has more than 500 employees, "
                "enrich the company profile, create a follow-up task, and notify Slack."
            ),
        },
    )

    assert plan_response.status_code == 201
    workflow = plan_response.json()
    assert workflow["workflow_id"].startswith("wf_")
    assert len(workflow["steps"]) >= 3
    assert "created_at" in workflow

    execute_response = client.post(
        f"/workflows/{workflow['workflow_id']}/execute",
        headers=AUTH_HEADERS,
        json={
            "tenant_id": "tenant_acme",
            "workflow_id": workflow["workflow_id"],
            "trigger_payload": {"company_id": "company_demo"},
        },
    )

    assert execute_response.status_code == 200
    execution = execute_response.json()
    assert execution["status"] == "succeeded"
    assert execution["workflow_id"] == workflow["workflow_id"]
    assert "created_at" in execution


def test_list_workflows() -> None:
    client = build_test_client()
    for _ in range(2):
        client.post(
            "/workflows/plan",
            headers=AUTH_HEADERS,
            json={"tenant_id": "tenant_acme", "instruction": "enrich and notify Slack please"},
        )
    resp = client.get("/workflows", headers=AUTH_HEADERS, params={"tenant_id": "tenant_acme"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_nonexistent_workflow_returns_404() -> None:
    client = build_test_client()
    resp = client.get("/workflows/wf_doesnotexist", headers=AUTH_HEADERS)
    assert resp.status_code == 404


def test_wrong_tenant_returns_403() -> None:
    client = build_test_client()
    resp = client.post(
        "/workflows/plan",
        headers={**AUTH_HEADERS, "X-Tenant-Id": "tenant_evil"},
        json={"tenant_id": "tenant_acme", "instruction": "enrich and notify Slack please"},
    )
    assert resp.status_code == 403
