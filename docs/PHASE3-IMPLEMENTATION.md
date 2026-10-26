# Phase 3 implementation and evidence

Current update, 2026-10-27: **genuine Phase 3 single-Action E2E PASS**. See the
[subsequent real session record](PHASE3-REAL-ACCEPTANCE.md). The dated build report below
preserves the pre-activation state at the time of its checks; its NOT_RUN statements
are historical, not the current live status. Phase 4 live acceptance remains NOT_RUN.

## Historical build qualification

Date: 2026-10-26, Pacific/Auckland. Baseline:
`edcefa7c6d286e6f4dde98d01700dd2d636020cb`.
**Local Phase 3A–3D engineering qualification: PASS.**
**Phase 3 final live acceptance is PARTIAL. Live activation and real human Action
approval are NOT_RUN.** The healthy Phase 1 instance has not been restarted.

## Delivery reconciliation

Phase 2 remote main was rechecked at the exact baseline SHA.
[GitHub run 40278101916](https://github.com/miku-wwl/crowdquest-ai/actions/runs/40278101916)
completed SUCCESS: 125 backend tests, 9 frontend tests, lint/build/provenance and actual
Chromium synthetic E2E. Its push/CI are PASS; prior NOT_RUN delivery text is historical.
That does not establish Phase 2 live activation or genuine human Action consent.

Phase 3 implementation was pushed non-forcefully to main at
`45a67f10fecc1bba85d88759a059a06165c5508a`.
[GitHub run 40289129582](https://github.com/miku-wwl/crowdquest-ai/actions/runs/40289129582)
was independently observed completed SUCCESS for that exact SHA: 163 backend tests,
16 frontend tests, lint/build/provenance, Phase 1 actual Chromium synthetic E2E and
Phase 3 actual Chromium plus separately authenticated worker synthetic E2E. The
remote expiry observation was RENDERED then EXPIRED. Real Twitch, human Action
consent and actual OBS rendering were NOT_RUN in CI. This receipt is a subsequent
documentation-only change; it does not substitute a different source revision.

A private preparation backup of real intake passed source/backup integrity and
logical-content comparison, preserving two delivery/message/candidate records.
Credentials were not copied or changed, and the live Phase 1 process was not stopped.
The service, fresh EventSub readiness, exact user:read:chat scope and original row
counts were rechecked after source delivery. A fresh backup is still required
immediately before any separately authorized activation.

## 3A: bounded real-model planning

`crowdquest/providers.py` implements the public AIG ModelProvider contract for the
already-installed local Ollama `phi4-mini:latest`. The current release accepts only
this reviewed model; no cloud model, paid request, download or installation is enabled.
Endpoint is fixed loopback, proxies/redirects disabled. One attempt has a 20-second
maximum within AIG's planning envelope, 16 KiB envelope, 2 KiB domain response and
bounded output tokens. The separate AIG execution adapter still has its default
five-second budget. No execution-budget extension or core modification was made.

The model receives a bounded suggestion as data and the domain schema. It receives
no credentials, source, tool registration, target, scope, grants or effect key. Output
must have exactly title/description/duration_seconds/difficulty. Duplicate keys,
extra fields, invalid controls/types/bounds, refusal, incomplete output, tool calls,
oversize and timeout fail closed. Trusted host code constructs the sole fixed Plan
step; installed AIG validates and persists it.

Provenance is server-owned, request-local and persisted: REAL_MODEL, OFFLINE_MANUAL or
SYNTHETIC_TEST. Failure does not silently fall back. An owner may explicitly create
a bounded manual draft, with a new Run and fresh review. Each candidate has one model
attempt; a reserved/interrupted generation is not automatically retried.
One model generation may run at a time per configured deployment; a concurrent request
gets GENERATION_BUSY without consuming that candidate's one model attempt.

[Real local model evidence](evidence/phase3/real-local-model.json): three actual Ollama
requests produced persistent AwaitingApproval Runs in an isolated temporary AIG profile
in 5.214, 3.360 and 3.500 seconds. Zero Actions, queue effects and renders were created.
Ollama 0.35.1; model digest is recorded. These are authored public test suggestions,
not real Twitch-to-product acceptance. Injection affected proposed wording in probes;
fixed authority remained protected. This is not universal content-safety/model-quality
proof; exact owner review remains mandatory.

The wire contract follows [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
and its [chat API](https://docs.ollama.com/api/chat). AIG uses the immutable installed
[v0.3.0 consumer contract](AIG_INTEGRATION.md), not its Demo planning prompt/UI.

## 3B: exact authenticated review

`product.py`, `phase3_routes.py` and `frontend/src/review.tsx` link each candidate to its
current persistent Run, provenance and redacted audit history in private product state.
The inbox remains read-only during this development work; actual Twitch records are
not edited or replayed. Owner, CSRF and Origin checks protect distinct Generate,
Approve/Reject, Admit, Authorize and Execute requests. No button combines these gates.

The UI shows exact bounded fields, source, Run version, Action state, admission receipt
hash and separate rendering/acknowledgement status. Manual revisions invalidate old
review by changing the current Run. After any Action admission, a replacement Plan
for that candidate is forbidden, including Unknown outcomes. AIG owns exact Approval,
CAS, grants, claiming and Action recovery; the consumer does not duplicate them.

Phase 2 remains opt-in and functional. Production startup uses separate Phase 3 routes;
the Phase 1 Preview selected publication endpoints are denied in production mode.
Default startup retains clearly labelled development behavior for the preserved instance.

## 3C: fenced worker and overlay

`rendering.py` owns a separate private rendering ledger. `worker.py` is a separate
process with a distinct credential that cannot approve, authorize or execute Actions.
It checks channel authentication and stops on uncertain HTTP outcomes without retry.
Worker instance, server incarnation, monotonic lease and epoch fence every publication.
A SQLite unique active-channel constraint prevents competing active challenges.

The backend reads the public AIG gateway and compares exact successful receipt/payload
before claim and again before publication. Pending, unconfirmed, Failed, Unknown and
quarantined jobs cannot publish. A durable dispatch marker precedes content delivery;
an existing marker is never dispatched a second time. AIG admission state is unchanged
by rendering failures.

The overlay receives only bounded display fields, remaining duration and opaque render
correlation IDs. Each paired overlay gets one issued delivery per render. Same-view
acknowledged polls retain the original deadline; a new view after reload/reconnect
does not replay already issued content. Two separately paired overlays can observe the
same challenge without executing or admitting it again. Countdown uses server monotonic
remaining time anchored to browser performance.now; 15/60/120-second expiry is tested.

After DOM paint, a narrowly bound overlay acknowledgement records browser initialization
only. Its credential permits this telemetry, never control-plane grants or new jobs.
It is explicitly BROWSER_ACK_ONLY, not actual OBS visual evidence. Missing acknowledgements,
post-dispatch worker loss and server restart become terminal rendering Unknown. Proven
pre-dispatch interruption is Render Failed. Neither case is replayed or reconciled into
success. Logout ends active publication conservatively and stops worker authority.

## 3D: verification and failure history

Final local regression: **163 backend tests passed** (38 added Phase 3 cases), one
existing warning; **16 frontend tests passed**. TypeScript/Vite build, lint/format,
installed public API/pin/template, lock/pip and npm audit pass (zero npm advisories
reported at this check). Both actual Chromium commands exited 0. No test uses the
real intake database. The exact pushed implementation commit and CI receipt are
recorded after delivery; no previous CI result is substituted for the new source.

The final commands/counts and source/image hashes are in
[local-qualification.json](evidence/phase3/local-qualification.json). Checks include
backend tests, frontend tests, TypeScript/Vite build, lint/format, lock/pip/pinned public
API/provenance, unchanged installed AIG source hashes, secret scans and both actual
Chromium scenarios. Fault tests use real temporary SQLite and disposable processes.
The Phase 3 Chromium fixture runs an actual separately authenticated worker, two
overlays, explicit gates, escaping, acknowledgements, reload suppression, actual
15-second expiry, and maximum Unicode fields within a 1280×720 viewport.

Synthetic browser images (not real Twitch, model, human or OBS evidence):
[dashboard](evidence/phase3/synthetic-dashboard.png),
[overlay](evidence/phase3/synthetic-overlay.png),
[maximum fields](evidence/phase3/synthetic-overlay-max-fields.png).
They were visually inspected; no AI image generation or reconstructed UI was used.

Earlier failures remain recorded:

- Two newly added fault cases initially failed due to missing test imports: 32 passed,
  2 failed. Imports were corrected; the targeted suite then passed.
- Visual QA exposed missing production Ready heartbeat updates despite actual browser
  acknowledgements. Fixed and regression-tested, including storage failure returning
  503 without a false Ready heartbeat.
- Maximum-field E2E initially timed out finding Description: nesting textarea/select
  contents inside labels polluted label names. Explicit label associations fixed it;
  unit and actual-browser form/maximum-layout checks now pass.
- A direct database-expiry assertion failed immediately after browser expiry. The
  failed row value was not captured, so its exact value is not claimed. The test now
  observes materialization for at most three seconds, fails immediately on Unknown/
  Render Failed, and never updates state. Subsequent runs explicitly record observed
  states; client/server housekeeping timing is a plausible explanation, not a recovered
  historical row. No production timeout or safety rule was weakened.
- Existing Starlette TestClient/HTTPX deprecation warning remains, not hidden.

## Live and competition gates

Follow [PHASE3-RUNBOOK.md](PHASE3-RUNBOOK.md). A separate owner approval is required
before stopping the verified Phase 1 process, provisioning a real private profile,
starting Phase 3/backend worker, or repeating real OAuth/OBS pairing. The owner must
personally review, separately authorize and execute each exact live Action.

Full acceptance still requires genuine Twitch → real model → exact human review →
independent authorization → AIG receipt → actual OBS display and approximately 60-second
expiry with correlated evidence. None is inferred from combined separate tests.
Phase 1 original PNG archival remains PARTIAL. Entrant-owned pre-existing AIG reuse,
personal eligibility and final submission readiness remain unverified; no organizer
contact, video upload, streaming, deployment or submission occurred.

Codex thread: `01a172e3-9804-73c2-b597-8c5df928a56c` (verified current environment).
Raw session logs, private stores, source secrets and personal identifiers are excluded.
