# Product requirements

Status reviewed 2026-10-30: Phase 1–3 acceptance is recorded in dated reports. Phase 4
local qualification passed but **PHASE4_OVERALL remains PARTIAL**. Phase 4.5.5
reliability changes passed CI; native background-tab retest remains pending. Phase
4.5.6 Clear Demo History is persistent; a user-provided screenshot showed the clean
view and a separate read-only database check confirmed its watermarks. The owner's
login and click were not independently observed. New post-clear real Twitch-to-Studio
acceptance remains NOT_RUN. Broadcast Studio is the current primary presentation; OBS
is optional legacy compatibility.

Owner: miku-wwl.

## Problem and users

Chat suggestions are entertaining but noisy and difficult to convert into clear,
timed challenges during a livestream. Streamers need control over what appears on
their broadcast and a reliable record of what they approved and what actually ran.

Primary users are a single Twitch streamer operating a local demo and viewers in
that stream's chat. The viewer needs a simple command and understandable on-stream
feedback. The streamer needs a bounded preview, clear approval controls and accurate
status without becoming an agent-runtime operator.

## Viewer journey

1. Send `!quest Beat the next boss without healing` in the configured channel.
2. The application accepts at most one candidate for that chat event, subject to limits.
3. The streamer may shortlist exactly two ideas; viewers send !vote 1 or !vote 2.
   The server closes the round; an equal result needs an explicit owner choice.
4. The winning candidate becomes a bounded local-model Plan; the streamer may reject it.
5. An approved, independently authorized challenge appears with a countdown.
6. The overlay shows its own lifecycle; it does not claim to verify gameplay compliance.

## Streamer journey

1. Authenticate as the configured channel owner and use Broadcast Studio as the
   primary presentation. A read-only OBS Browser Source is optional legacy
   compatibility.
2. Review incoming suggestions, then an exact generated title, description, duration
   and difficulty. Reject unsafe, irrelevant or misleading suggestions.
3. Approve the current Plan explicitly. A changed/stale Plan requires fresh review.
4. The application independently checks Action authority before execution.
5. Inspect separate admission, rendering and audit results. Ambiguous outcomes halt
   progression and show a clear operator status; they never trigger automatic replay.

## MVP

Receive real EventSub chat; recognize `!quest`; validate source, deduplicate and rate
limit; persist candidates; generate one bounded Plan; preview and approve/reject;
use installed AIG for exact Approval binding, independent Authorization and one
`enqueue_overlay_challenge` action; persist admission receipts; render through a
separate worker and the primary Broadcast Studio Canvas; demonstrate duplicate/conflict
and Unknown safety. The read-only OBS Browser Source is optional legacy compatibility.

Proposed bounds: suggestion 1–280 characters after command; title 1–80; description
1–240; duration integer 15–120 seconds; difficulty Easy/Medium/Hard. Final values
must be encoded in trusted schemas and tested in Phase 2. The example 60-second
challenge is one possible value, not evidence of generation. No links or markup
are executable. A challenge describes gameplay; it never controls the game.

## Non-goals and stretch work

No Twitch Extension, OBS scene control, bans, moderation punishment, game modification,
money movement, arbitrary execution, multi-agent orchestration, multi-tenant SaaS or
AIG rewrite. Voting, bounded outcome presentations and broadcast design are authorized Phase 4 work.
History/analytics, provider UI and complex achievements remain out of scope.

## Success criteria

- A real viewer command produces one validated candidate; duplicate deliveries do not.
- The streamer understands the preview and can reject it without an effect.
- Missing approval or Authorization prevents job admission.
- An authorized approval yields one durable admission receipt and at most one active
  challenge for the configured channel; the overlay acknowledges actual rendering.
- Disconnects, stale versions, crashes and Unknown outcomes are visible and safe.
- A recorded real Twitch demo shows the flow and Codex development in under 3 minutes.

Acceptance requires evidence in [ACCEPTANCE_CRITERIA.md](ACCEPTANCE_CRITERIA.md).
Latency, viewer enjoyment and model quality remain unmeasured. Proposed demo targets:
preview within 30 seconds and render acknowledgement within 3 seconds of confirmed
admission on a healthy local setup; measure them rather than assume them.

## Phase 4 audience direction and outcomes

The owner shortlists exactly two valid unused candidates, creates Draft, then explicitly
opens one bounded round. EventSub-compatible votes are durably deduplicated and unique
per keyed viewer/round. Persisted server deadlines and transactional closure determine
totals; ties never pick a winner. The winning candidate is frozen into Run provenance.
No vote generates a grant or executes an Action. Four separate human operations remain.
After an acknowledged successful challenge, the owner can record one immutable Completed,
Failed or Skipped report. Its brief presentation has separate no-replay state and never
executes the original Action again. The overlay labels gameplay results as streamer reports.

## Phase 4.5.6 display reset

The owner may advance the current Dashboard demo session to hide earlier candidate and
voting-round rows from the display. `dashboard_sessions` stores generation and rowid
watermarks; the reset preserves audit/business records, receipts, renders and terminal
UNKNOWN. New post-watermark suggestions remain eligible for the current view. The
user-provided screenshot showed the clean view on 2026-10-30. A separate read-only
database check confirmed persistent watermarks and retained rows. The owner's
login and click were not independently observed. A new real Twitch suggestion/voting/
Studio challenge remains NOT_RUN.
