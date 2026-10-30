# Phase 5.1 Worker and Render Reliability Fix

Observed and implemented: 2026-10-30. Validation below is from the isolated local checkout; it is not evidence of production activation or real Twitch delivery.

## Result

The Worker now writes one bounded JSON diagnostic to standard error when it exits. Records identify the operation stage, a fixed error category, HTTP status when available, diagnostic retryability, explicit `automatic_retry=false`, exit classification, and a UTC timestamp. Diagnostics do not include exception text, response bodies, request headers, credentials, private paths, or full request URLs. The existing Worker still exits on an uncertain request and does not retry or restart itself.

During same-boot maintenance, a Render with a persisted `ACKNOWLEDGED` observation remains `RENDERED` when the Worker lease expires. Its existing Render deadline can subsequently move it to `EXPIRED`. A `CLAIMED` Render with no publication becomes `RENDER_FAILED`; an unacknowledged `SENT` Render becomes terminal `UNKNOWN`. ACK remains evidence that the browser acknowledged delivery; it does not establish gameplay completion or owner outcome.

## Historical evidence and limits

The preserved read-only diagnosis observed the prior Worker exit as `WORKER_STOPPED_UNCONFIRMED` and found the exact HTTP status or exception unavailable. That historical root cause remains **UNDETERMINED**. The new diagnostics improve future evidence; they do not retroactively identify the old failure.

The diagnosis found a prior Render whose stored state was `UNKNOWN` while its observation remained `ACKNOWLEDGED`. Source inspection tied this to the same-boot stale-lease transition that previously changed every active Render to `UNKNOWN`. The correction is narrowly limited to that lease-maintenance transition.

Boot recovery is intentionally more conservative than same-boot lease maintenance. The schema does not persist a trustworthy monotonic-clock epoch across OS restarts, so active `SENT` and `RENDERED` rows still recover as `UNKNOWN`; existing ACK observation records remain audit evidence. No recovery path converts an old `UNKNOWN` into success or releases an old payload for replay. Existing `EXPIRED` and `UNKNOWN` rows remain terminal.

## State transitions

| Condition | Result | Delivery behavior |
| --- | --- | --- |
| Same-boot lease expires while Render is `CLAIMED` | `RENDER_FAILED` | No published payload is retried by this transition. |
| Same-boot lease expires while Render is `SENT` without a durable ACK | `UNKNOWN` | Quarantined; no replay. |
| Same-boot lease expires after a durable ACK | Remains `RENDERED` | ACK is retained; the original deadline can later expire it. |
| A valid ACK races with an expired/fenced lease | ACK is rejected; ambiguous delivery remains `UNKNOWN` | No replay. |
| Backend boot recovery sees active `CLAIMED` | `RENDER_FAILED` | No replay. |
| Backend boot recovery sees active `SENT` or `RENDERED` | `UNKNOWN` | Conservative across clock epochs; no replay. |
| Existing row is `UNKNOWN` or `EXPIRED` | State is retained | No delivery or Action re-execution. |

Fencing, epochs, unique effect keys, one-Render-per-effect protection, and the separation between AIG Action success, browser ACK, and owner outcome are unchanged.

## Regression evidence

Added fake-HTTP Worker tests for session 401/403, session/tick 409, tick 500/503, connection failure, timeout, unexpected exceptions, interrupted in-flight requests, clean shutdown, stderr output, secret redaction, and absence of automatic retries. Added disposable-SQLite tests for ACK preservation and deadline expiry, pre-publication and ambiguous lease expiry, ACK races, boot recovery, and processing one new eligible synthetic Action without replaying an older `UNKNOWN` Render or re-executing Actions.

All tests used isolated fixtures. No test used the real private Profile or production databases.

### Commands and measured results

- `uv run --locked --no-sync pytest -q`: **309 passed**, one Starlette deprecation warning.
- Targeted delivery/security regression set (`tests/test_worker.py`, `tests/test_studio_delivery.py`, `tests/test_phase3.py`, `tests/test_phase3_routes.py`, `tests/test_outcomes.py`): **56 passed**, one warning.
- `uv run ruff check crowdquest tests scripts` and `uv run ruff format --check crowdquest tests scripts`: **PASS**; 69 files checked/formatted.
- `uv lock --check --offline`, `uv pip check`, and `uv run --locked --no-sync python -I scripts/verify_baseline.py`: **PASS**. The baseline verifier confirmed the installed AIG package and exact pinned commit.
- `uvx --from pip-audit==2.10.1 pip-audit --path .venv/Lib/site-packages`: **PASS**, no known vulnerabilities in audited packages. The Git-only AIG distribution is omitted by pip-audit and is checked separately by the baseline integrity verifier.
- `npm ci`: **PASS**, 108 packages installed; npm reported zero vulnerabilities.
- `npm run test`: **68 passed** across seven frontend test files. `npm run typecheck`, `npm run lint`, and `npm run format:check`: **PASS**.
- Custom redacted credential-pattern scan over the five intended changed files: **PASS**. Gitleaks, detect-secrets, and TruffleHog were unavailable; the scan checked common GitHub, AWS, Slack, private-key, bearer-token, and credential-assignment patterns and printed no matching values.
- Isolated frontend build: TypeScript `--noEmit` and Vite build to `.artifacts/phase51/frontend`: **PASS**. An initial `npm run build -- --outDir ...` argument-forwarding attempt was rejected by npm before compilation; the equivalent local TypeScript and Vite steps then completed successfully. The live `frontend/dist` was not overwritten.
- Actual Chromium synthetic E2E modules: `tests.browser_e2e`, `tests.phase3_browser_e2e`, `tests.phase4_browser_e2e`, `tests.obs_browser_e2e`, `tests.studio_browser_e2e`, and `tests.studio_delivery_browser_e2e`: **PASS**. These used synthetic fixtures, not Twitch or production Actions. The delivery visibility test used a deterministic `document.hidden` override because native background-tab visibility was unavailable; that visibility aspect remains **PARTIAL**.
- `git diff --check`: **PASS**.

During final validation, Ruff first flagged import ordering in the newly added cancellation test; the import was corrected and the final full lint and format checks passed.

## Security and production boundary

No automatic retries, recovery replay, secret logging, authorization changes, fencing changes, schema migrations, or shared Agentic Intent Gate source changes were introduced. The existing pinned runtime dependency and default budget are unchanged.

The diagnosis identified one real eligible delivery. Its identifier remains only in the separate private diagnostic record. This delivery was not consumed. No production database was modified; no production Worker was started; no production Backend was restarted; no Twitch event, vote, Plan, or Action was created or executed. The diagnosis report remains a separate untracked file and is not part of this fix.

## Safe activation plan — not executed

Production activation requires a separate explicit owner authorization. Before any activation, review the exact pending delivery in the private Profile and decide whether that delivery may be shown. Back up and verify the existing private databases, confirm no active Action, vote, Render, or presentation can be interrupted, and plan a controlled Backend restart so the new Render maintenance code is loaded. Do not reset or replay any `UNKNOWN` or `EXPIRED` record. Only after the owner authorizes delivery of the pending item should the existing Worker be started once against the same private Profile. Observe the single Render and its matching ACK; if the result is uncertain, stop and preserve the state without retrying.

The existing Worker launch form, for a separately authorized activation only, is:

```powershell
$profile = Join-Path $env:LOCALAPPDATA 'CrowdQuestAI\phase3'
uv run --locked --no-sync python -m crowdquest.worker --origin http://localhost:8000 --token-file (Join-Path $profile 'worker-token')
```

Do not run this command as part of this source delivery. Pushing code does not restart the Backend or Worker and does not make the recording environment ready.

## Delivery status

Engineering tests are green locally. GitHub CI for the final pushed commit is reported separately after normal push and exact-commit verification. Production activation and Phase 5 recording readiness remain **NOT RUN / BLOCKED UNTIL SAFE ACTIVATION**.
