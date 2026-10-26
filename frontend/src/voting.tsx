import { useEffect, useRef, useState } from "react";
import type { Candidate } from "./ui";

export type VoteChoice = {
  number: number;
  candidate_id: string;
  text: string;
  votes: number;
  percentage: number;
};
export type VoteRound = {
  id: string;
  state: "Draft" | "Open" | "Closed" | "Cancelled";
  version: number;
  choices: VoteChoice[];
  remaining_seconds: number;
  total_votes: number;
  winner: number | null;
  plan_bound: boolean;
  reason?: string;
  evidence?: string;
};

async function request<T>(
  path: string,
  csrf: string,
  body?: object,
): Promise<T> {
  const response = await fetch(path, {
    credentials: "same-origin",
    cache: "no-store",
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
      response.status === 401
        ? "Sign in again to manage voting."
        : response.status === 503
          ? "Voting storage is unavailable. Operations are paused."
          : "The round changed or this operation was rejected. Review its current state before continuing.",
    );
  return response.json();
}

export function VoteBars({
  round,
}: {
  round: Pick<VoteRound, "choices" | "winner" | "state">;
}) {
  return (
    <div className="vote-choices">
      {round.choices.map((choice) => (
        <article
          key={choice.number}
          className={`vote-choice choice-${choice.number} ${choice.text.length > 160 ? "long-choice" : ""} ${round.winner === choice.number ? "vote-winner" : ""}`}
        >
          <div className="vote-choice-head">
            <span className="vote-number">{choice.number}</span>
            <span>
              {round.winner === choice.number
                ? "CHAT’S PICK"
                : `OPTION ${choice.number}`}
            </span>
            <strong>
              {choice.votes} {choice.votes === 1 ? "vote" : "votes"}
            </strong>
          </div>
          <p className="vote-suggestion">{choice.text}</p>
          <meter
            className="vote-track"
            aria-label={`Candidate ${choice.number} vote share`}
            min={0}
            max={100}
            value={Math.max(0, Math.min(100, choice.percentage))}
          >
            {choice.percentage}%
          </meter>
          <div className="vote-choice-foot">
            <code>!vote {choice.number}</code>
            <strong>{choice.percentage}%</strong>
          </div>
        </article>
      ))}
    </div>
  );
}

export function VotingPanel({
  candidates,
  csrf,
  onReview,
}: {
  candidates: Candidate[];
  csrf: string;
  onReview: (id: string) => void;
}) {
  const [round, setRound] = useState<VoteRound | null>(null);
  const [shortlist, setShortlist] = useState<string[]>([]);
  const [duration, setDuration] = useState(30);
  const [busy, setBusy] = useState(false);
  const [fresh, setFresh] = useState(false);
  const [error, setError] = useState("");
  const [remaining, setRemaining] = useState(0);
  const anchor = useRef(0),
    generation = useRef(0);
  function accept(value: VoteRound | null) {
    setRound(value);
    setError((current) =>
      current.startsWith("Voting connection lost") ? "" : current,
    );
    anchor.current = performance.now() + (value?.remaining_seconds || 0) * 1000;
    setRemaining(value?.remaining_seconds || 0);
    setFresh(true);
  }
  useEffect(() => {
    let active = true,
      working = false;
    async function refresh() {
      if (working) return;
      working = true;
      const revision = generation.current;
      try {
        const value = await request<{ round: VoteRound | null }>(
          "/api/phase4/voting",
          csrf,
        );
        if (active && revision === generation.current) accept(value.round);
      } catch {
        if (active) {
          setFresh(false);
          setError(
            "Voting connection lost. Controls are paused until current state is confirmed.",
          );
        }
      } finally {
        working = false;
      }
    }
    void refresh();
    const poll = setInterval(refresh, 1000),
      tick = setInterval(
        () =>
          setRemaining(
            Math.max(0, (anchor.current - performance.now()) / 1000),
          ),
        250,
      );
    return () => {
      active = false;
      clearInterval(poll);
      clearInterval(tick);
    };
  }, [csrf]);
  async function act(path: string, body: object) {
    generation.current++;
    setBusy(true);
    setFresh(false);
    setError("");
    try {
      const value = await request<{ round?: VoteRound; candidate_id?: string }>(
        path,
        csrf,
        body,
      );
      if (value.candidate_id) onReview(value.candidate_id);
      const current = await request<{ round: VoteRound | null }>(
        "/api/phase4/voting",
        csrf,
      );
      accept(current.round);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      generation.current++;
    }
  }
  const unfinished = round?.state === "Draft" || round?.state === "Open";
  const enabled = fresh && !busy;
  const winner = round?.choices.find(
    (choice) => choice.number === round.winner,
  );
  function command(operation: string, choice?: number) {
    if (round)
      void act(`/api/phase4/rounds/${round.id}/${operation}`, {
        expected_version: round.version,
        idempotency_key: crypto.randomUUID(),
        ...(choice ? { choice } : {}),
      });
  }
  return (
    <section className="voting-panel" aria-label="Crowd voting">
      <div className="voting-heading">
        <div>
          <p className="eyebrow">THE COMMUNITY CALLS IT</p>
          <h2>Let chat choose the next challenge.</h2>
        </div>
        <span className={`round-pill ${round?.state === "Open" ? "open" : ""}`}>
          {round?.state === "Open"
            ? "VOTING LIVE"
            : round?.state || "NO ROUND YET"}
        </span>
      </div>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <div className="voting-layout">
        <div className="shortlist">
          <h3>01 / Shortlist two ideas</h3>
          <p className="muted">
            Pick two suggestions, then open the vote on stream.
          </p>
          <fieldset disabled={unfinished || busy} className="shortlist-options">
            <legend className="sr-only">
              Shortlist exactly two candidates
            </legend>
            {candidates.map((candidate) => (
              <label
                key={candidate.id}
                className={
                  shortlist.includes(candidate.id) ? "shortlisted" : ""
                }
              >
                <input
                  type="checkbox"
                  aria-label={`Shortlist ${candidate.suggestion}`}
                  checked={shortlist.includes(candidate.id)}
                  disabled={
                    !shortlist.includes(candidate.id) && shortlist.length === 2
                  }
                  onChange={() =>
                    setShortlist((current) =>
                      current.includes(candidate.id)
                        ? current.filter((id) => id !== candidate.id)
                        : [...current, candidate.id],
                    )
                  }
                />
                <span>{candidate.suggestion}</span>
              </label>
            ))}
          </fieldset>
          <div className="shortlist-footer">
            <div className="duration-field">
              <label htmlFor="vote-duration">Voting time</label>
              <select
                id="vote-duration"
                value={duration}
                disabled={unfinished || busy}
                onChange={(e) => setDuration(Number(e.target.value))}
              >
                <option value={15}>15 seconds</option>
                <option value={30}>30 seconds</option>
                <option value={60}>60 seconds</option>
              </select>
            </div>
            <button
              className="secondary"
              disabled={!enabled || unfinished || shortlist.length !== 2}
              onClick={() =>
                void act("/api/phase4/rounds", {
                  candidate_ids: shortlist,
                  duration_seconds: duration,
                  idempotency_key: crypto.randomUUID(),
                })
              }
            >
              Create voting round
            </button>
          </div>
        </div>
        <div className="round-live" aria-live="polite">
          {!round ? (
            <div className="vote-empty">
              <span>
                1 <i>vs</i> 2
              </span>
              <h3>Two ideas. One crowd decision.</h3>
              <p>
                Votes choose an idea. You approve the Plan and authorize its
                Action.
              </p>
            </div>
          ) : (
            <>
              <div className="round-topline">
                <h3>
                  {round.state === "Open"
                    ? "02 / Chat is deciding"
                    : round.state === "Draft"
                      ? "02 / Ready for chat"
                      : round.state === "Cancelled"
                        ? "Round cancelled"
                        : winner
                          ? "03 / Chat has spoken"
                          : "03 / A tie. Your call."}
                </h3>
                <output aria-label="Voting time remaining">
                  {round.state === "Open"
                    ? `${Math.ceil(remaining)}s`
                    : `${round.total_votes} votes`}
                </output>
              </div>
              <VoteBars round={round} />
              {round.state === "Open" && (
                <p className="voting-instructions">
                  Type <code>!vote 1</code> or <code>!vote 2</code> in Twitch
                  chat. One vote per viewer.
                </p>
              )}
              <div className="round-actions">
                {round.state === "Draft" && (
                  <button
                    className="primary"
                    disabled={!enabled}
                    onClick={() => command("start")}
                  >
                    Start voting
                  </button>
                )}
                {round.state === "Open" && (
                  <button
                    className="secondary"
                    disabled={!enabled}
                    onClick={() => command("close")}
                  >
                    Close voting now
                  </button>
                )}
                {unfinished && (
                  <button
                    className="quiet"
                    disabled={!enabled}
                    onClick={() => command("cancel")}
                  >
                    Cancel round
                  </button>
                )}
                {round.state === "Closed" && !winner && (
                  <>
                    {[1, 2].map((choice) => (
                      <button
                        className="secondary"
                        key={choice}
                        disabled={!enabled}
                        onClick={() => command("winner", choice)}
                      >
                        Choose candidate {choice} as winner
                      </button>
                    ))}
                  </>
                )}
                {round.state === "Closed" && winner && !round.plan_bound && (
                  <button
                    className="primary"
                    disabled={!enabled}
                    onClick={() =>
                      void act(`/api/phase4/rounds/${round.id}/plan`, {
                        expected_version: round.version,
                      })
                    }
                  >
                    {busy ? "Generating…" : "Generate winning Plan"}
                  </button>
                )}
                {winner && round.plan_bound && (
                  <button
                    className="secondary"
                    disabled={!enabled}
                    onClick={() => onReview(winner.candidate_id)}
                  >
                    Review winning Plan →
                  </button>
                )}
              </div>
              {round.state === "Closed" && (
                <p className="fine">
                  {winner
                    ? "The winner still needs your exact Plan review and independent Action authorization."
                    : "Equal totals never select a winner automatically."}
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
