const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8100";

export type WorkflowStep = {
  step_id: string;
  name: string;
  integration: "hubspot" | "sap" | "slack";
  action: string;
  input: Record<string, unknown>;
  depends_on: string[];
  condition: string | null;
};

export type WorkflowPlan = {
  workflow_id: string;
  tenant_id: string;
  instruction: string;
  steps: WorkflowStep[];
  assumptions: string[];
  risks: string[];
  created_at: string;
};

export type StepExecutionResult = {
  step_id: string;
  status: "pending" | "running" | "succeeded" | "failed" | "skipped";
  output: Record<string, unknown>;
  error: string | null;
};

export type WorkflowExecution = {
  execution_id: string;
  workflow_id: string;
  tenant_id: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  step_results: StepExecutionResult[];
  created_at: string;
};

export async function planWorkflow({
  tenantId,
  instruction,
}: {
  tenantId: string;
  instruction: string;
}): Promise<WorkflowPlan> {
  const response = await fetch(`${API_BASE_URL}/workflows/plan`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer demo-token",
      "X-Tenant-Id": tenantId,
      "X-User-Id": "frontend_user",
    },
    body: JSON.stringify({ tenant_id: tenantId, instruction }),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
  }

  return response.json() as Promise<WorkflowPlan>;
}

export async function executeWorkflow({
  tenantId,
  workflowId,
  triggerPayload = {},
}: {
  tenantId: string;
  workflowId: string;
  triggerPayload?: Record<string, unknown>;
}): Promise<WorkflowExecution> {
  const response = await fetch(`${API_BASE_URL}/workflows/${workflowId}/execute`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer demo-token",
      "X-Tenant-Id": tenantId,
      "X-User-Id": "frontend_user",
    },
    body: JSON.stringify({
      tenant_id: tenantId,
      workflow_id: workflowId,
      trigger_payload: triggerPayload,
    }),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? `Request failed with ${response.status}`);
  }

  return response.json() as Promise<WorkflowExecution>;
}
