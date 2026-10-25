# Product requirements

Status: proposed product; implementation has not started. Owner: miku-wwl.

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
3. AI proposes a short display challenge; the streamer may reject it.
4. An approved, independently authorized challenge appears with a countdown.
5. The overlay shows its own lifecycle; it does not claim to verify gameplay compliance.

## Streamer journey

1. Authenticate as the configured channel owner and connect a read-only OBS Browser Source.
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
separate worker and OBS Browser Source; demonstrate duplicate/conflict and Unknown safety.

Proposed bounds: suggestion 1–280 characters after command; title 1–80; description
1–240; duration integer 15–120 seconds; difficulty Easy/Medium/Hard. Final values
must be encoded in trusted schemas and tested in Phase 2. The example 60-second
challenge is one possible value, not evidence of generation. No links or markup
are executable. A challenge describes gameplay; it never controls the game.

## Non-goals and stretch work

No Twitch Extension, OBS scene control, bans, moderation punishment, game modification,
money movement, arbitrary execution, multi-agent orchestration, multi-tenant SaaS or
AIG rewrite. Voting, history UI, preferences, animations, provider UI and analytics
are stretch work only after a real MVP E2E pass and explicit scope approval.

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
