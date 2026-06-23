"use client";

import { FormEvent, useState } from "react";
import { executeWorkflow, planWorkflow } from "../lib/api";
import type { WorkflowExecution, WorkflowPlan } from "../lib/api";

const sampleInstruction =
  "When a new HubSpot lead has more than 500 employees, enrich the company profile, create a follow-up task, and notify the sales team in Slack.";

const STATUS_EMOJI: Record<string, string> = {
  succeeded: "✅",
  failed: "❌",
  skipped: "⏭️",
  pending: "⏳",
  running: "🔄",
};

export default function Home() {
  const [instruction, setInstruction] = useState(sampleInstruction);
  const [companyId, setCompanyId] = useState("company_demo");
  const [plan, setPlan] = useState<WorkflowPlan | null>(null);
  const [execution, setExecution] = useState<WorkflowExecution | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setPlan(null);
    setExecution(null);
    try {
      const result = await planWorkflow({ tenantId: "tenant_acme", instruction });
      setPlan(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setLoading(false);
    }
  }

  async function onExecute() {
    if (!plan) return;
    setExecuting(true);
    setError(null);
    try {
      const result = await executeWorkflow({
        tenantId: "tenant_acme",
        workflowId: plan.workflow_id,
        triggerPayload: { company_id: companyId },
      });
      setExecution(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setExecuting(false);
    }
  }

  return (
    <main className="page">
      <section className="shell">
        <div className="header">
          <div>
            <p className="eyebrow">AI Workflow MVP</p>
            <h1>Workflow Planner</h1>
          </div>
          <span className="status">tenant_acme</span>
        </div>

        <form className="composer" onSubmit={onSubmit}>
          <label htmlFor="instruction">Natural-language instruction</label>
          <textarea
            id="instruction"
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            rows={5}
          />
          <label htmlFor="companyId">Trigger: company_id</label>
          <input
            id="companyId"
            type="text"
            value={companyId}
            onChange={(e) => setCompanyId(e.target.value)}
          />
          <button type="submit" disabled={loading}>
            {loading ? "Planning..." : "Plan workflow"}
          </button>
        </form>

        {error ? <pre className="error">{error}</pre> : null}

        <section className="results" aria-label="Workflow plan">
          {plan ? (
            <>
              <div className="resultsHeader">
                <h2>{plan.workflow_id}</h2>
                <div className="actions">
                  <span>{plan.steps.length} steps</span>
                  <button type="button" onClick={onExecute} disabled={executing}>
                    {executing ? "Executing..." : "Execute"}
                  </button>
                </div>
              </div>

              <ol className="steps">
                {plan.steps.map((step) => (
                  <li key={step.step_id}>
                    <div>
                      <strong>{step.name}</strong>
                      <p>
                        {step.integration}.{step.action}
                      </p>
                    </div>
                    {step.condition ? <code>{step.condition}</code> : null}
                  </li>
                ))}
              </ol>

              {plan.assumptions.length > 0 && (
                <div className="assumptions">
                  <h3>Assumptions</h3>
                  <ul>
                    {plan.assumptions.map((a, i) => (
                      <li key={i}>{a}</li>
                    ))}
                  </ul>
                </div>
              )}

              {plan.risks.length > 0 && (
                <div className="risks">
                  <h3>Risks</h3>
                  <ul>
                    {plan.risks.map((r, i) => (
                      <li key={i}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}

              {execution ? (
                <div className="execution">
                  <div className="resultsHeader">
                    <h2>{execution.execution_id}</h2>
                    <span className={`badge ${execution.status}`}>
                      {STATUS_EMOJI[execution.status] ?? ""} {execution.status}
                    </span>
                  </div>
                  <ol className="steps">
                    {execution.step_results.map((result) => (
                      <li key={result.step_id}>
                        <div>
                          <strong>{result.step_id}</strong>
                          <p>
                            {STATUS_EMOJI[result.status] ?? ""} {result.status}
                          </p>
                        </div>
                        {result.error ? <code>{result.error}</code> : null}
                        {result.output && Object.keys(result.output).length > 0 ? (
                          <pre className="output">
                            {JSON.stringify(result.output, null, 2)}
                          </pre>
                        ) : null}
                      </li>
                    ))}
                  </ol>
                </div>
              ) : null}
            </>
          ) : (
            <p className="empty">Submit an instruction to display the generated workflow.</p>
          )}
        </section>
      </section>
    </main>
  );
}
