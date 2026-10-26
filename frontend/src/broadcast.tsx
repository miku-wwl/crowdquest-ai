import { VoteBars, type VoteRound } from "./voting";

export function VotingDisplay({
  round,
  state,
  remaining,
}: {
  round: VoteRound;
  state: string;
  remaining: number;
}) {
  const winner = round.choices.find((choice) => choice.number === round.winner);
  return (
    <div className="broadcast-voting">
      {round.evidence === "SYNTHETIC_TEST" && (
        <p className="synthetic-evidence">SYNTHETIC TEST · ISOLATED FIXTURE</p>
      )}
      <div className="broadcast-heading">
        <div>
          <p className="eyebrow">YOUR CHAT. YOUR NEXT CHALLENGE.</p>
          <h1>
            {state === "voting"
              ? "Chat, make the call."
              : !winner
                ? "It’s a tie. Streamer decides."
                : state === "pending_approval"
                  ? "Your pick is in review."
                  : "Chat has spoken."}
          </h1>
        </div>
        {state === "voting" && (
          <output className="vote-countdown" aria-label="Voting time remaining">
            {Math.ceil(remaining)}
            <small>SEC</small>
          </output>
        )}
      </div>
      <VoteBars round={round} />
      <p className="voting-instructions">
        {state === "voting" ? (
          <>
            Twitch chat: <code>!vote 1</code> or <code>!vote 2</code>{" "}
            <span>ONE VOTE PER VIEWER</span>
          </>
        ) : (
          <>
            {winner
              ? `Chosen by Chat · ${round.total_votes} votes`
              : "Equal votes · no automatic winner"}
            <span>STREAMER REVIEW REQUIRED</span>
          </>
        )}
      </p>
    </div>
  );
}

export function OutcomeDisplay({ kind }: { kind: string }) {
  return (
    <div className={`outcome-display outcome-${kind.toLowerCase()}`}>
      <span className="outcome-symbol" aria-hidden="true">
        {kind === "Completed" ? "✦" : kind === "Failed" ? "×" : "—"}
      </span>
      <p className="eyebrow">STREAMER-REPORTED RESULT</p>
      <h1>
        {kind === "Completed"
          ? "Challenge complete."
          : kind === "Failed"
            ? "That was a tough one."
            : "On to the next idea."}
      </h1>
      <p>{kind} · Reported by the streamer</p>
      <span className="fine">Ready for what chat dreams up next.</span>
    </div>
  );
}
