import { useEffect, useState } from "react";
import type { Candidate } from "./ui";
import "./review.css";

type Challenge = {
  title: string;
  description: string;
  duration_seconds: number;
  difficulty: "Easy" | "Medium" | "Hard";
};
type Run = {
  run_id: string;
  version: number;
  state: string;
  plan: { steps: { arguments: Challenge }[] } | null;
  error?: { code: string } | null;
};
type Action = {
  action_id: string;
  version: number;
  state: string;
  admission: { state: string; receipt_hash: string } | null;
  rendering: {
    state: string;
    acknowledgements: number;
    evidence?: string;
    outcome?: { kind: string; recorded: number; state: string } | null;
  };
};
type Proposal = {
  status: string;
  run: Run | null;
  audience_selected?: boolean;
  provenance: { source: string; model?: string; reason?: string } | null;
  action: Action | null;
};
type Audit = { at: number; kind: string; correlation: string };

async function request<T>(
  path: string,
  csrf: string,
  body?: object,
): Promise<T> {
  const response = await fetch(path, {
    cache: "no-store",
    credentials: "same-origin",
    signal: AbortSignal.timeout(25000),
    ...(body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
          body: JSON.stringify(body),
        }),
  });
  if (!response.ok)
    throw new Error(
      response.status === 429
        ? "Another Plan is being generated. Wait for it to finish before choosing another suggestion."
        : response.status === 401
          ? "Sign in again to continue."
          : response.status === 409
            ? "The state changed or the outcome is unconfirmed. Review the current status before continuing."
            : "This operation was rejected. Refresh and review your connection and permissions.",
    );
  return response.json();
}

export function ReviewPanel({
  candidate,
  csrf,
}: {
  candidate?: Candidate;
  csrf: string;
}) {
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [audit, setAudit] = useState<Audit[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fresh, setFresh] = useState(false);
  const [manual, setManual] = useState(false);
  const [draft, setDraft] = useState<Challenge>({
    title: candidate?.suggestion.slice(0, 80) || "",
    description: candidate?.suggestion.slice(0, 240) || "",
    duration_seconds: 60,
    difficulty: "Medium",
  });
  const base = candidate ? `/api/phase3/candidates/${candidate.id}` : "";
  useEffect(() => {
    let active = true,
      working = false;
    async function refresh() {
      if (!candidate || working) return;
      working = true;
      try {
        const [value, status] = await Promise.all([
          request<Proposal>(base, csrf),
          request<{ audit: Audit[] }>("/api/phase3/status", csrf),
        ]);
        if (active) {
          setProposal(value);
          setAudit(status.audit);
          setFresh(true);
        }
      } catch {
        if (active) {
          setFresh(false);
          setError(
            "Connection lost. Actions are paused until current state is confirmed.",
          );
        }
      } finally {
        working = false;
      }
    }
    void refresh();
    const timer = setInterval(refresh, 1000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [candidate, base, csrf]);
  async function act(path: string, body: object) {
    setBusy(true);
    setError("");
    setFresh(false);
    try {
      await request(path, csrf, body);
      const current = await request<Proposal>(base, csrf);
      setProposal(current);
      setFresh(true);
      setManual(false);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const run = proposal?.run,
    action = proposal?.action;
  const arguments_ = run?.plan?.steps[0].arguments;
  const ready = !busy && fresh && proposal?.status === "READY";
  function runCommand(operation: string) {
    if (run)
      void act(`/api/phase3/runs/${run.run_id}/${operation}`, {
        expected_version: run.version,
        idempotency_key: crypto.randomUUID(),
      });
  }
  function actionCommand(operation: string) {
    if (action)
      void act(`/api/phase3/actions/${action.action_id}/${operation}`, {
        expected_version: action.version,
        idempotency_key: crypto.randomUUID(),
      });
  }
  return (
    <section className="review-panel" aria-label="Challenge review">
      <p className="eyebrow">YOU HAVE THE FINAL SAY</p>
      <h2>Review. Decide. Play.</h2>
      {!candidate ? (
        <p className="muted">Select a suggestion to begin.</p>
      ) : (
        <>
          <div className="workflow-status" aria-live="polite">
            <span>Candidate</span>
            <span>{run?.state || proposal?.status || "Loading"}</span>
            {action && (
              <>
                <span>{action.state}</span>
                <span>
                  {action.admission?.state === "ELIGIBLE"
                    ? action.rendering.state === "Waiting"
                      ? "Render Eligible"
                      : "Admission verified"
                    : action.admission?.state || "Admitted"}
                </span>
                <span>{action.rendering.state}</span>
              </>
            )}
          </div>
          {proposal?.provenance && (
            <p
              className={`provenance ${proposal.provenance.source === "REAL_MODEL" ? "real" : "manual"}`}
            >
              {proposal.provenance.source}
              {proposal.provenance.model && (
                <small> · {proposal.provenance.model}</small>
              )}
            </p>
          )}
          {proposal?.audience_selected && (
            <span className="chat-badge">Chosen by Chat</span>
          )}
          {arguments_ && (
            <div className="plan-fields" aria-label="Exact proposed Plan">
              <h3>{arguments_.title}</h3>
              <p>{arguments_.description}</p>
              <dl>
                <div>
                  <dt>Duration</dt>
                  <dd>{arguments_.duration_seconds} seconds</dd>
                </div>
                <div>
                  <dt>Difficulty</dt>
                  <dd>{arguments_.difficulty}</dd>
                </div>
              </dl>
              <small>
                Plan version {run?.version}. Approval applies to these exact
                fields.
              </small>
            </div>
          )}
          {run?.state === "PlanRejected" && (
            <p role="status" className="error">
              No valid Plan was generated.{" "}
              {proposal?.provenance?.reason || run.error?.code}. Review a manual
              draft if you wish to continue.
            </p>
          )}
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
          <div className="workflow-actions">
            {!run && (
              <button
                className="primary"
                disabled={busy || !fresh || proposal?.status !== "Candidate"}
                onClick={() => void act(base + "/generate", {})}
              >
                {busy ? "Generating…" : "Generate proposed Plan"}
              </button>
            )}
            {run?.state === "AwaitingApproval" && (
              <>
                <button
                  className="primary"
                  disabled={!ready}
                  onClick={() =>
                    void act(`/api/phase3/runs/${run.run_id}/decision`, {
                      decision: "APPROVE",
                      expected_version: run.version,
                    })
                  }
                >
                  Approve this Plan
                </button>
                <button
                  className="secondary"
                  disabled={!ready}
                  onClick={() =>
                    void act(`/api/phase3/runs/${run.run_id}/decision`, {
                      decision: "REJECT",
                      expected_version: run.version,
                    })
                  }
                >
                  Reject Plan
                </button>
              </>
            )}
            {run?.state === "Approved" && !action && (
              <button
                className="primary"
                disabled={!ready}
                onClick={() => runCommand("admit")}
              >
                Admit approved Action
              </button>
            )}
            {action?.state === "Pending" && (
              <button
                className="primary"
                disabled={!ready}
                onClick={() => actionCommand("authorize")}
              >
                Authorize this Action
              </button>
            )}
            {action?.state === "Authorized" && (
              <button
                className="primary"
                disabled={!ready}
                onClick={() => actionCommand("execute")}
              >
                Execute authorized Action
              </button>
            )}
          </div>
          {action && (
            <p className="fine action-identity">
              enqueue_overlay_challenge / 1 · Action{" "}
              {action.action_id.slice(0, 8)} · version {action.version}
            </p>
          )}
          {action?.state === "Succeeded" &&
            action.rendering.acknowledgements > 0 && (
              <section
                className="outcome-controls"
                aria-label="Record challenge outcome"
              >
                <h3>How did the challenge go?</h3>
                <p className="fine">
                  Your report of gameplay. Recorded separately from AIG
                  execution.
                </p>
                {action.rendering.outcome ? (
                  <p className="outcome-recorded" role="status">
                    {action.rendering.outcome.kind} · Streamer-reported result
                  </p>
                ) : (
                  <div>
                    {["Completed", "Failed", "Skipped"].map((kind) => (
                      <button
                        key={kind}
                        className="secondary"
                        disabled={
                          !ready ||
                          !["RENDERED", "EXPIRED"].includes(
                            action.rendering.state,
                          )
                        }
                        onClick={() =>
                          void act(
                            `/api/phase4/actions/${action.action_id}/outcome`,
                            {
                              kind,
                              expected_version: action.version,
                              idempotency_key: crypto.randomUUID(),
                            },
                          )
                        }
                      >
                        {kind}
                      </button>
                    ))}
                  </div>
                )}
              </section>
            )}
          {action?.state === "Unknown" && (
            <p className="error" role="status">
              Outcome unknown. This Action is stopped permanently; it will not
              be retried or replaced.
            </p>
          )}
          {!action && (
            <button
              className="quiet"
              disabled={busy || !fresh || proposal?.status === "GENERATING"}
              onClick={() => {
                if (arguments_) setDraft(arguments_);
                setManual((v) => !v);
              }}
            >
              Edit a manual draft
            </button>
          )}
          {manual && !action && (
            <form
              className="manual-fields"
              onSubmit={(e) => {
                e.preventDefault();
                void act(base + "/manual", {
                  expected_version: run?.version || 0,
                  challenge: draft,
                });
              }}
            >
              <p className="provenance">OFFLINE_MANUAL · no model request</p>
              <div className="manual-field">
                <label htmlFor="draft-title">Title</label>
                <input
                  id="draft-title"
                  required
                  maxLength={80}
                  value={draft.title}
                  onChange={(e) =>
                    setDraft({ ...draft, title: e.target.value })
                  }
                />
              </div>
              <div className="manual-field">
                <label htmlFor="draft-description">Description</label>
                <textarea
                  id="draft-description"
                  required
                  maxLength={240}
                  value={draft.description}
                  onChange={(e) =>
                    setDraft({ ...draft, description: e.target.value })
                  }
                />
              </div>
              <div className="manual-field">
                <label htmlFor="draft-duration">Duration in seconds</label>
                <input
                  id="draft-duration"
                  required
                  type="number"
                  min={15}
                  max={120}
                  value={draft.duration_seconds}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      duration_seconds: Number(e.target.value),
                    })
                  }
                />
              </div>
              <div className="manual-field">
                <label htmlFor="draft-difficulty">Difficulty</label>
                <select
                  id="draft-difficulty"
                  value={draft.difficulty}
                  onChange={(e) =>
                    setDraft({
                      ...draft,
                      difficulty: e.target.value as Challenge["difficulty"],
                    })
                  }
                >
                  <option>Easy</option>
                  <option>Medium</option>
                  <option>Hard</option>
                </select>
              </div>
              <button className="secondary" disabled={busy || !fresh}>
                Create manual Plan
              </button>
              <small>Creates a new Plan that requires fresh review.</small>
            </form>
          )}
          <p className="fine">
            Approval, admission, authorization and execution are separate steps.
            Admission success does not prove rendering or gameplay.
          </p>
          <details>
            <summary>Receipt and audit</summary>
            {action?.admission && (
              <p>
                Receipt {action.admission.receipt_hash} ·{" "}
                {action.admission.state}
              </p>
            )}
            {action && (
              <p>
                Browser acknowledgements: {action.rendering.acknowledgements}.
                Actual OBS rendering requires visual verification.
              </p>
            )}
            <ol className="audit-list">
              {audit.map((item, i) => (
                <li key={i}>
                  {item.kind} · {item.correlation}
                </li>
              ))}
            </ol>
          </details>
        </>
      )}
    </section>
  );
}
