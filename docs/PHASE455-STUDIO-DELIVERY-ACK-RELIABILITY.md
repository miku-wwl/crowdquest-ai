# Phase 4.5.5 — Broadcast Studio delivery and ACK reliability

Date: 2026-10-29, Pacific/Auckland. Source: `68de50b63268b34f641478b436a0046e3f208684`.
Codex session: `01a185d0-23c9-7c70-a4b4-f3a3bf8f6bd1`.

**Result: PARTIAL.** The repair and synthetic qualification pass. Native background-tab
visibility remains PARTIAL: this host's Playwright Chromium reports both tabs visible,
including a separate headed probe. The two-tab regression therefore explicitly controls
`document.hidden`. Actual Canvas drawing, HTTP ACK and durable acknowledgement are verified
with synthetic data. This is not another real Twitch acceptance or OBS verification.

The final commit SHA, push verification and completed CI URL/status are supplied in the
owner's review package `delivery.json`, written after this report is committed. This report
does not predict a CI result or embed its own impossible self-referential commit SHA.

## Confirmed defects and historical limits

The original Studio issued `/api/studio/current` while hidden or outside its Live layout.
The check occurred after that GET. `RenderStore.current()` inserted an `ISSUED` observation
before returning the challenge. If painting/ACK did not happen, maintenance eventually
made that observation and potentially the SENT render UNKNOWN. The catch block also
rotated the View ID for every polling error, preventing the previous view from continuing.
Visibility was not rechecked between the two animation frames and the ACK request.

These are confirmed source defects and reproducible failure mechanisms. The exact runtime
trigger of the user's Phase 4.5.4 failure has **not** been proven by browser telemetry.
The user-provided historical failure description is the repair's authoritative problem
statement; old reports are neither reconciled nor rewritten. An old UNKNOWN render stays
UNKNOWN. No historical rendering or owner outcome is invented.

## Reproduction and comparison

Before changing production code, the new
`test_studio_peek_does_not_issue_a_delivery` was executed against the original source.
Two GET requests produced one observation where zero were required: **1 failed**, exit 1.
The existing deterministic missing-ACK test already demonstrates the subsequent terminal
UNKNOWN transition with an injected clock and continuing worker heartbeat.

For an independent frontend comparison, `git archive HEAD frontend` exported the original
source into ignored `.artifacts/phase455/baseline`. The new Studio test file was copied there;
only the existing node_modules directory was shared by a junction. The main checkout and
running frontend/dist were not swapped. `npm run test` in that archive produced **7 failed,
52 passed**, exit 1 (59-test comparison snapshot). In particular, the hidden test observed
one GET instead of zero, and the transient-error test observed two View IDs instead of one.
Other failures expose the changed claim/ACK contract rather than independently proving
the historical runtime trigger. Three additional Canvas-failure/slow-expiry/continuous-presentation tests were added afterwards.
The final patched suite has **62 passed**, exit 0.

To reproduce the fixed protocol with owned temporary SQLite, synthetic OAuth/model/chat/
consent and a separate fixture worker:

```powershell
uv run --no-sync pytest -q tests/test_studio.py tests/test_studio_delivery.py
cd frontend
npm run test
npm run build:studio
cd ..
$env:CROWDQUEST_TEST_FRONTEND = (Resolve-Path '.artifacts/phase45-browser/frontend').Path
uv run --no-sync python -m tests.studio_browser_e2e --output-dir .artifacts/phase455/retest
```

The Studio browser command includes the new two-tab regression, so the unchanged CI
workflow runs it too. `CROWDQUEST_HEADED=1` optionally selects a test-owned headed Chromium
for that regression. It does not guarantee that the host supplies native hidden-tab state.
No test attaches to a production browser, IAB, Desktop Work or real Twitch session.

## Implemented protocol

| Boundary | Behavior and durable evidence |
| --- | --- |
| AIG execution | Unchanged installed runtime independently approves, admits, authorizes and executes one queue admission. A queue receipt is not rendering proof. |
| Worker publish | The fenced worker rechecks a confirmed Succeeded Action/eligible receipt, claims once and durably publishes SENT. |
| Studio GET current | Non-consuming peek. Returns a pending presentation ID, an existing claim marker, or bounded waiting/voting/terminal state. Does not issue a challenge or outcome. Normal deadline maintenance can still advance terminal states. |
| Studio POST claim | Exact `presentation_id`, stable View ID, existing Studio cookie, owner session, Origin and CSRF required. The same immediate SQLite transaction checks the current identity and inserts at most one observation per render/overlay key before releasing the payload. |
| ISSUED | Payload release was durably attempted. It does not assert receipt, paint, visibility or acknowledgement. An uncertain claim response is never requested again. |
| Browser paint | Eligible Live document draws the Canvas, waits two animation frames, then checks lifecycle epoch, current visibility/layout and conservative expiry again. |
| Browser ACK | Binds render ID, delivery ID, overlay cookie hash and View ID. Only the existing visible paint can supply it. ACK is not an AIG grant. |
| RENDERED | Requires a valid browser ACK persisted as ACKNOWLEDGED. Duplicate exact ACKs do not create another observation, render, job or effect. |
| Timeout/recovery | ISSUED reaches UNKNOWN at `issued + 5s` (now explicitly inclusive). Missing worker heartbeat, crash and restart remain fail closed. UNKNOWN is terminal. |
| Expiration/outcome | Unclaimed SENT and acknowledged RENDERED expire at the original monotonic deadline. Owner outcome still requires an acknowledged render and stays separate from AIG. Outcome peek/claim is also non-consuming/explicit and bounded to its existing eight-second window. |

The browser retains one View ID for its component/document presentation lifetime. Ordinary
errors never rotate it. An already acknowledged, continuously visible local challenge
keeps its original countdown through a temporary status outage without fetching or
starting the presentation again. A refresh/new presentation instance generates a new ID and cannot
inherit the previous claim. Acknowledged challenge and outcome continuation uses already
held local state; a Studio GET does not resend the payload. Layout changes, visibility
changes, resolution changes and pagehide invalidate outstanding work and clear local
presentation. pageshow/visibility restoration resumes non-overlapping polling promptly.

Requests have a bounded abort signal; a lifecycle epoch also rejects stale responses even
if cancellation loses a race. A hidden page polls only system status. A non-Live layout
cannot claim. A hide during the non-consuming peek discards the result without claiming.
A hide during/after claim discards the payload and ACK work; the consumed delivery is
not released or stolen, and its missing ACK becomes UNKNOWN. This deliberately sacrifices
an uncertain delivery instead of pretending that browser cancellation undoes server commit.

After a visible paint, a lost ACK response permits at most three requests for that **same
ACK tuple**, only in the same uninterrupted presentation and a conservative 4.5-second
window. They never claim or execute again. An ACK rejection, exhausted window, interrupted
presentation or draw failure stops this path. There is no presentation retry, effect retry,
automatic Action replacement or UNKNOWN reconciliation. Polling errors, hidden/layout
pause, pending claim, claimed/no replay, draw failure, rejected ACK and expiry have distinct
Studio status text.

## Compatibility and security review

Studio's GET contract intentionally changes: old Studio JavaScript receives pending/claim
markers instead of consuming a challenge. Deploy the matching frontend/backend together
in a separately authorized activation. A mismatched old Studio fails closed. The existing
OBS/legacy `/api/overlay/current` consuming contract and same-view continuation remain
unchanged; this patch does not claim to qualify visibility behavior of that separate client.
No database migration is needed. No recorder implementation was changed.

The new endpoint is under the existing loopback-only Studio middleware, exact Host/Origin,
request-size, owner-session/generation and CSRF boundaries. It validates closed request
shape and UUIDv4 identities. It cannot approve a Plan, admit an Action, issue Authorization,
execute a tool, choose a binding/scope/budget or expose a runtime capability. Browser
visibility is an honest-client predicate, not server-side attestation or a guarantee against
a malicious authenticated owner. An ACK is browser evidence, not optical proof or OBS proof.

The complete upstream AGENTS prefix, lockfile, installed AIG `0.3.0`, immutable commit
`bb8e8fb1234128613a750bee17967b225072bb14`, all 45 installed source RECORD hashes,
sole tool/binding and default five-second adapter budget are preserved. There is no AIG
source change or alternate execution mechanism. Read-only inspection of the pinned
consumer example, adapter guide and handoff informed this consumer-only repair.

No replay invariants: a consumed claim cannot return another Studio payload; another View
cannot steal it; expired content cannot become fresh; UNKNOWN cannot become SENT/RENDERED;
a forged/late ACK is denied; a duplicate ACK cannot duplicate effects; worker/application
restarts do not republish historical dispatch. Deadline maintenance is committed even when
an ACK is rejected, preserving terminal evidence instead of rolling it back with the error.

## Regression coverage and verification

| Requested case | Evidence |
| --- | --- |
| Visible before execution, one draw/ACK | Existing Studio recording Chromium flow plus new unit tests |
| Background Studio during synthetic execution | New two-tab Chromium fixture; 6.2s hidden, SENT, zero observations/claims/ACKs |
| Foreground before expiry | Same fixture: one claim, HTTP 200 ACK, one durable ACKNOWLEDGED/RENDERED |
| Hide during peek/claim or between draw and paint | Deterministic frontend stale-response and animation-frame fencing tests; no false ACK |
| Delayed visibility/deadline | Injected-clock backend: 12s before claim is safe; expired SENT cannot be claimed |
| Two View IDs/concurrent requests | SQLite concurrent claim test; one payload winner; other view cannot steal |
| Duplicate and forged ACK | Exact tuple checks across all four identities; one persisted observation |
| Transient poll error/lost ACK response | Stable View ID; same-tuple ACK confirmation, one claim |
| Refresh/no replay | Chromium reload and backend tests |
| Timeout/restart/crash | Exact five-second boundary, worker-loss and process-crash/recovery tests |
| Non-Live layout, unmount/pagehide | New frontend tests; stale results cannot claim/ACK |
| Canvas/recording integrity | Native Canvas, Waiting/Voting/Active/Result, Follow live, WebM export/playback, dimensions/duration and full FFmpeg decode |

| Executed verification command | Exit | Result |
| --- | --- | --- |
| `uv lock --check --offline` / `uv pip check` | 0 / 0 | Lock valid; 45 installed packages compatible |
| `uv run --locked --offline python -I scripts/verify_baseline.py` (initial), then `uv run --no-sync python -I scripts/verify_baseline.py --output docs/evidence/phase455/dependency.json` | 0 | Pin/API/source/template checks PASS; no runtime created |
| `uv run --no-sync ruff check crowdquest tests scripts` | 0 | PASS |
| `uv run --no-sync ruff format --check crowdquest tests scripts` | 0 | 66 files formatted |
| `uv run --no-sync pytest -q` | 0 | 286 passed, zero skipped; one existing Starlette/httpx deprecation warning |
| `uv run --no-sync pytest -q tests/test_studio.py tests/test_outcomes.py` after outcome continuation tightening | 0 | 14 passed, same warning |
| `npm run test` | 0 | Final 62 passed in six files, zero skipped |
| `npm run build:studio` | 0 | TypeScript + Vite; isolated output, no live dist overwrite |
| `npm run lint` / `npm run format:check` | 0 / 0 | TypeScript strict unused/fallthrough and Prettier PASS |
| `uv run --no-sync python -m tests.browser_e2e` | 0 | Actual Chromium, synthetic session/intake/pairing/escaping/no replay |
| `uv run --no-sync python -m tests.phase3_browser_e2e` | 0 | Separate gates/worker/ACK/expiry/no replay |
| `uv run --no-sync python -m tests.phase4_browser_e2e` | 0 | Vote/winner/outcome/layout safety |
| `uv run --no-sync python -m tests.obs_browser_e2e` | 0 | Synthetic OBS compatibility only; no actual OBS controlled |
| `uv run --no-sync python -m tests.studio_browser_e2e --output-dir .artifacts/phase455/final-studio-verified --ffmpeg D:\Buzz\_internal\ffmpeg.exe` | 0 | Two-tab deterministic protocol + actual Canvas/WebM/playback/decode |
| `git diff --check` | 0 | PASS |

Security regression is included in the complete Python suite: authentication/CSRF/Origin,
owner/tool/binding/scope/grant/version/idempotency fences, ambiguous effects, EventSub
validation/deduplication, render identity and no replay. The new claim tests explicitly
exercise missing/wrong CSRF/Origin, malformed/extra input, stale ID and other View denial.
There are no skipped live tests being counted as real acceptance.

Intermediate failures were corrected, not suppressed: initial TypeScript rejected an
unsupported Testing Library `exact` option (replaced with an anchored role-name regex);
Ruff rejected `re.I` (changed to `re.IGNORECASE`); the first new browser test expected a
descriptive no-replay label while the UI showed `NO_REPLAY` (explicit label mapping added).
An initial status-outage fixture injected its error before the first ACK; it was corrected
to inject only after an observed ACK so it tests continuous presentation deterministically.
Two npm invocations with forwarded formatting/reporter flags failed in this host's npm
CLI; direct local Prettier and the authoritative unadorned scripts succeeded. Expected
pre-fix regression failures are recorded separately above. CI configuration was not edited.

Exact synthetic video metrics and hashes are in `evidence/phase455/recording.json` and its
decode log; Canvas frames are explicitly labeled SYNTHETIC TEST. The full WebM remains
in the ignored local artifact directory, outside Git and the small review ZIP. A screenshot
is supplementary illustration; the ACK HTTP response plus persistent observation provide
the acknowledgement evidence.

## Preservation and evidence classification

No production HTTP calls, Twitch events/votes, OAuth consent, real model requests, production
Action execution, service restarts, credential changes, publication or submissions were
performed. All test application construction/execution used temporary stores and fixture
services. Tests block non-fixture browser requests; providers/authentication use fixtures.
GitHub fetch/push/CI are the separately authorized delivery network operations.

The three pre-existing untracked Phase 4.5.3/4.5.4 reports and their evidence remain untracked
and untouched. A read-only mid-repair preservation checkpoint checks 48 files, including
those artifacts, live frontend/dist and five production SQLite files. Historical artifacts,
dist and four static databases are byte-identical at recheck. The running render database
changes bytes under its normal worker heartbeat: read-only samples show advancing leader
deadline and stable render/observation/outcome fingerprints. This is **not** a claim of
whole-interval production byte identity. `PRODUCTION_DATABASE_MODIFIED=NO` means zero
repair/test-initiated writes; it does not deny normal activity of the preserved live service.
No production database contents, private hashes or credentials are copied into this evidence.

| Classification | Result |
| --- | --- |
| BROWSER_ACK_VERIFIED | Synthetic browser HTTP ACK and durable ACKNOWLEDGED verified |
| SYNTHETIC_TEST_ONLY | All new browser, Action, consent, Canvas and recording evidence |
| OBS_VISUALLY_VERIFIED | NOT_VERIFIED |
| Native background-tab visibility | PARTIAL, explicit deterministic substitute documented |
| Historical runtime trigger | NOT_VERIFIED |
| New genuine Twitch/model/production E2E | NOT_RUN |

## P1 — winner and Plan fidelity diagnostic

`VotingStore.bind_winner()` checks the closed round/version, chooses the frozen winner's
candidate ID and verifies its stored suggestion equals the frozen choice text.
`phase4_routes.plan()` passes that candidate to `Product.generate()`, which places its exact
suggestion into the Intent. `DomainProvider` sends it as JSON `untrusted_suggestion` in the
local model user message. It validates the response envelope and Challenge, then builds the
trusted sole-tool Plan. Owner review/approval remains mandatory before admission.

The strengthened route fixture verifies the provider received the exact winning text;
the HTTPX provider fixture verifies the exact user message. Source and synthetic binding:
PASS. The historical model request was not replayed and no original browser/provider
telemetry proves its contents; historical exact-input delivery remains unverified.

The old prompt's game-only framing, generic brevity and unconditional 60-second default
could encourage the reported transformation into a quiz. That is a plausible prompt-quality
factor, not a proven historical model cause. Schema-only validation allowed a structurally
valid but semantically different result: **semantic-fidelity gap confirmed**.

The small improvement asks the local model to preserve task/subject/explicit duration and
uses the default only when duration is absent. A narrow deterministic check recognizes an
unambiguous English `in N seconds` or `for N seconds`; mismatch rejects with
`MODEL_DURATION_MISMATCH`, without retries, replacement text or falsified REAL_MODEL
provenance. `semantic_fidelity=OWNER_REVIEW_REQUIRED` explicitly avoids claiming equivalence.
A test intentionally allows a matching-duration generic quiz through structural validation
to demonstrate the remaining semantic limit. Other phrasing, multiple durations, title/task
meaning and translation still require owner review. No second model/service was introduced.
Full semantic fidelity is PARTIAL; a later bounded UI comparison of original suggestion
and proposed text is recommended, not automatic approval or another AI authority gate.

## Gates and exact next step

G1–G8 and G10–G12 pass within the stated synthetic scope. G9 remains PARTIAL for native
tab visibility; its deterministic two-tab protocol, real Canvas and ACK checks pass. G13
must be assessed from the actual repair commit's completed CI in the review package.
The phase must remain **PARTIAL**, even if CI is green, until the native visibility gap
is resolved. P1 semantics also remains PARTIAL. Phase 5 is BLOCKED.

**A new controlled real acceptance is still required for real-world acceptance.** First
review the patch/CI and separately authorize matched frontend/backend activation, preserving
private backups and verifying no pending Action/voting round. Then authorize one bounded
new real round, with Studio background during execution and foreground before expiry.
Verify one legitimate draw/ACK, persistent RENDERED, expiry and no replay, with fresh exact
human gates. Do not reuse the historical failed render or Action. No such activation or
round is performed by this repair phase, and this recommendation grants no consent.
