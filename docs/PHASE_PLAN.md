# Implementation phases and gates

The subsequent user instruction authorizes Phase 1 implementation/tests and normal
main delivery. Phase 2 onward still needs new authorization; no deployment/submission.
Historical Phase 0 scope remains recorded below.

Phase 1 is **PARTIAL**: real ingestion and user-observed Dashboard/OBS rendering now
pass, while final security activation and formal raw-image archival remain explicit
gaps. Current regression: 79 backend tests, 9 frontend tests and Chromium synthetic E2E.
See [PHASE1-FINAL-ACCEPTANCE.md](PHASE1-FINAL-ACCEPTANCE.md). The user's latest request
authorizes automatic Phase 2 only after mandatory quality gates pass; do not bypass them.

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

## Phase 4 — Submission (target 2026-11-01 to 02 NZDT)

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
