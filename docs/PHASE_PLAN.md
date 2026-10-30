# Implementation phases and gates

Current status reviewed 2026-10-30. Phase 1–3 acceptance and the genuine Phase 3
single-Action session remain recorded in their dated reports. Phase 4 implementation
and CI qualify locally, while **PHASE4_OVERALL remains PARTIAL**. Phase 4.5.5
reliability changes passed CI; genuine native background-tab reacceptance remains
pending. Phase 4.5.6 Clear Demo History is deployed. A user-provided screenshot showed
the clean view, and a separate read-only database check confirmed persistent rowid
watermarks; the owner's login and click were not independently observed. New real
post-clear Twitch-to-Studio E2E remains NOT_RUN. The OBS-free Broadcast Studio is the
primary display; OBS is optional legacy compatibility.

Phase 5 is documentation/demo/submission preparation only. This document pass grants
no new live Twitch events, Action execution, recording, upload, organizer contact or
submission. Historical authorization paragraphs in the phase records below describe
their original scope and dates; they are not current authorization.

## Phase 4.5 — current product acceptance

- Phase 4.5.5 delivery/ACK repair: commit-specific CI passed; native background-tab
  behavior remains PARTIAL until retested.
- Phase 4.5.6 Dashboard history cleanup: implementation and synthetic/CI qualification
  passed. A user screenshot showed the 2026-10-30 clean view; read-only SQLite
  evidence confirmed retained old rows and persistent watermarks. The login/click was
  not independently observed, and the new real Twitch suggestion/vote/Studio E2E has
  not run.
- Phase 5 guide set: [demo runbook](PHASE5-DEMO-RUNBOOK.md),
  [storyboard](PHASE5-DEMO-STORYBOARD.md),
  [submission checklist](PHASE5-SUBMISSION-CHECKLIST.md). Submission eligibility,
  real Studio acceptance, video and final entry remain open.

## Phase 0 — Repository and architecture (2026-10-26)

Dependencies: official period open; authorized GitHub account; existing target inspected;
exact AIG consumer template and release available; Python 3.13.

Deliver required documents, MIT/ignore/env configuration, immutable dependency and lock,
installed API/provenance verifier, minimal CI, recorded Codex session and initial Phase 0
commit/push preserving the README-only ancestor. No application directories are needed.

Gate: local locked sync, lock consistency, pip compatibility, complete template digest,
installed version/commit/path/signatures, required documents, diff and secret review;
then non-force push and verify local/tracking/remote main SHA and actual remote CI.
Record unresolved eligibility as PARTIAL; never invent live evidence. STOP.

## Phase 1 — Real Twitch vertical slice (target 2026-10-27)

Dependencies: separate phase authorization; Twitch account/app registration and owner
consent; channel identity; reviewed OAuth redirect and scopes; resolve or consciously
track competition eligibility before investing in a competition entry.

Work in order:

1. Add a small FastAPI entrypoint, consumer config/private-state provisioning and
   authenticated Twitch code-flow/token lifecycle with `user:read:chat` only.
2. Add EventSub WebSocket session/subscription lifecycle, bounded parsing and durable
   deduplication/rate-limited candidates; no AI or AIG execution integration.
3. Introduce minimal React/TypeScript dashboard and development overlay, select
   compatible frontend tooling and commit its package lock at that time.
4. Permit only owner-selected escaped development previews, visibly distinguished
   from an approved/executed challenge. Keep the preview adapter out of the final path.

Tests: wrong channel/type/version/source, replay IDs across restart, malformed commands,
rate/queue limits, token revocation, OAuth state, escaping, reconnect/drop handling.
Gate/evidence: one real authenticated chat event, duplicate suppression, real browser
preview/OBS capture with matching redacted IDs; safe logs. Mock-only results are PARTIAL.

## Phase 2 — AIG single-action integration (target 2026-10-28 to 29)

Dependencies: Phase 1 gate, exact installed API, separate approval authentication and
reviewed immutable binding/policy/schema/private storage design.

Work in order:

1. Provision stable identity, one executor/capability/registry/verifier/policy using
   public imports; retain five seconds and AIG ownership/recovery behavior.
2. Use synthetic domain Plans for offline integration; create persistent Runs and
   exact version-bound Approval. Keep test consent separate from human UI evidence.
3. Implement one transactional queue/effect/receipt admission and a strict policy.
4. Expose authenticated owner review and public-gateway admission/authorization/
   execution through consumer routes. Never expose local runtime bearer credentials.
5. Require matching durable AIG success before marking a never-dispatched job eligible.

Tests: successful durable receipt; missing grant, wrong tool/target/scope/binding;
stale/changed Plan and versions; duplicate command/effect; payload conflict; concurrent
claims; restart; post-commit lost acknowledgement; late outcome/timeout; job quarantine
on Unknown. Gate: inspect real SQLite effects/receipts, demonstrate no second effect
after interruption. No AIG patch or replacement state machine is permitted.

## Phase 3 — Complete product (target 2026-10-30 to 31)

Authorized local substages on 2026-10-26:

- 3A: existing local Ollama, one bounded domain proposal, strict host-owned authority,
  persisted provenance and explicitly labelled manual drafting. Real local probes
  have passed; this is not a complete real Twitch acceptance.
- 3B: exact current-Run owner review, Reject/Approve, separate admission, Authorization
  and execution, plus redacted audit/receipt UI. Synthetic browser consent stays separate.
- 3C: separate authenticated worker, durable dispatch fence, one active channel job,
  read-only overlay with bounded acknowledgement telemetry, monotonic countdown,
  conservative Unknown and no replay. Production denies Phase 1 preview publication.
- 3D: temporary SQLite/process/race/fault tests, actual Chromium fixtures, static/build/
  provenance/secret checks and normal scoped main delivery with exact-commit CI.

These local substages do not open the final live gate below. Preserve the currently
healthy Phase 1 instance until the owner separately approves the runbook's activation.

Dependencies: Phase 2 gate, separately configured provider access, authenticated real
streamer session, reviewed worker/overlay credential and dispatch fence.

Add consumer ModelProvider with strict bounded domain output, no authority in prompts
or output, one attempt and bounded response/time limits. Add candidate preview/reject/
approve UI, receipt/audit views, separately owned worker, browser acknowledgement,
countdown and clear failure states. Remove the Phase 1 preview publication path.

Tests: prompt injection, provider refusal/malformed/oversized output, UI auth/CSRF,
actual human approval, worker contention, lost rendering acknowledgement, reconnect,
reload without countdown restart, and separate admission/rendering statuses.
Gate: real Twitch → real model → real human approval → AIG durable admission → real
browser and OBS render evidence with correlated IDs. A synthetic E2E does not pass it.

## Phase 4 — Competitive upgrade (authorized 2026-10-27)

Implement consumer voting, immutable winner-to-Run provenance, owner-reported outcomes
and broadcast UX; preserve every AIG and live-service boundary. Isolated Python, React
and actual Chromium qualification precedes scoped main push and exact-commit CI.
Follow PHASE4-COMPETITIVE-UPGRADE.md, PHASE4-ACCEPTANCE.md and PHASE4-LIVE-RUNBOOK.md.
New real Twitch votes, activation, OBS and another real Action need separate permission.

## Phase 5 — Submission (target 2026-11-01 to 02 NZDT)

Dependencies: real MVP pass, eligibility/reuse clarification, English setup and project
materials, IP/media permissions, explicit authority for public uploads/final submission.

Finish fresh-machine setup instructions and testing access, record a YouTube demo under
3 minutes showing Twitch functionality and Codex use, select the principal Codex thread
ID, verify links as a judge, and complete every item in the submission checklist.
Plan an internal submit target of 2026-11-02 18:00 NZDT, leaving deadline buffer.
The official deadline is 2026-11-03 11:00 NZDT. Save the actual Devpost Submitted
confirmation and timestamp. A draft, upload or successful repository push is not entry.

## Evidence and stop conditions

Each phase records commands, environment, exact commit, meaningful test results, redacted
IDs/receipts, synthetic/live distinction and NOT_RUN gaps. Record browser and OBS results
separately. Do not add always-passing placeholder tests. Re-run relevant checks after
changes; do not cite upstream tests as CrowdQuest results. Dates are targets, not verified
delivery promises. If time is short, reduce stretch work; do not remove approval,
Authorization, durable receipts, Unknown handling or truthful evidence.
