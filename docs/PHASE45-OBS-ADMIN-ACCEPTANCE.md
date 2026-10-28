# Phase 4.5 OBS Admin acceptance

**Historical checkpoint, superseded on 2026-10-28.** The user replaced the mandatory
OBS path with OBS-free Broadcast Studio. The observations and blocked gates below
describe the earlier attempt and are preserved, including its native-app inspection;
they are not current Broadcast Studio release gates. No native desktop automation
was used during the replacement task. See
[current acceptance](PHASE45-BROADCAST-STUDIO-ACCEPTANCE.md).

Date: 2026-10-28 (Pacific/Auckland). Baseline source:
`5bc09eb785c71cd6519216b4dbc2bb43c0beb7e9`, clean before work.
Implementation is currently an uncommitted scoped working-tree change.
**Local implementation is qualified; final real OBS/release gates remain BLOCKED.**

This is a new report. Phase 1–4 reports, real stores and archived evidence were not
rewritten. Historical Phase 4 real acceptance remains PARTIAL; this feature does not
resolve its missing live voting frame or reconnect root-cause evidence.

| Gate | Result / evidence |
| --- | --- |
| OBS_ADMIN_IMPLEMENTATION | PASS — bounded adapter, existing React theme, `/obs-admin`, independent local session and optional OBS-only launcher. |
| OBS_WEBSOCKET_CONNECTION | BLOCKED for actual OBS — no listener on 4455 at preflight; private configuration absent. Synthetic v5 handshake, wrong password and auth-disabled denial pass. |
| ADMIN_SECURITY | PASS (SYNTHETIC_TEST / source review) — loopback peer/Host/Origin/CSRF, rotated session, rate/body/shape limits, fixed RPC allowlist and credential redaction. Not a hostile-local-user security certification. |
| SCENE_CONTROL | PARTIAL — synthetic listing/validated switch/state confirmation pass; actual native OBS has only one scene, so no real between-scenes switch yet. |
| OVERLAY_REFRESH | PARTIAL — synthetic exact-source validation/refresh and uncertain-ACK denial pass; actual source exists in OBS but no v5 refresh yet. |
| LOCAL_RECORDING | NOT_RUN (real) — no StartRecord/StopRecord was sent to installed OBS; no real output file/playability claim. Synthetic start/stop/state/duplicate/lost-reply checks pass. |
| REAL_OBS_ACCEPTANCE | BLOCKED — requires user WebSocket/password setup and browser Admin login. |
| BACKEND_TESTS | PASS — 220 tests, 127.81 seconds; one existing Starlette/HTTPX deprecation warning. |
| FRONTEND_TESTS | PASS — 30 tests across 4 files. |
| CHROMIUM_E2E | PARTIAL — new Admin suite PASS in actual Chromium with synthetic OBS; original three suites pending final collection. |
| AIG_REGRESSION | PASS — full 220-test run includes existing gates, persistence, receipts, Unknown and outcome/voting tests; installed 0.3.0 pin and 45 RECORD source hashes verified. No real Action run. |
| GITHUB_CI | NOT_RUN for this change — no release commit/push while real mandatory gate is blocked. |
| GIT_FINAL_HEAD | `5bc09eb785c71cd6519216b4dbc2bb43c0beb7e9` (baseline; new implementation not committed). |
| WORKTREE_STATUS | Scoped implementation and docs pending; no unrelated changes at baseline. |

## Current observations and setup handoff

Preflight found no CrowdQuest 8000 listener or OBS process/4455 listener. No CrowdQuest
service was stopped/restarted. The installed OBS 32.2.2 was then opened using native
Computer Use. Its actual window showed one `CrowdQuest Demo` scene, existing enabled
`CrowdQuest Overlay`, Start Streaming and Start Recording buttons, both timers at zero.
No media control or source/scene edit was performed. A read-only configuration probe
returned `OBS_ADMIN_CONFIGURED=False` without printing values.

The user was asked to personally enable OBS WebSocket with password authentication,
keep port 4455, run the hidden-input `python -m crowdquest.obs_setup`, and prepare a
second test scene if full scene-switch acceptance is desired. This follows attachment
section 8: security-setting changes/password entry must be user actions. No password
was requested in chat and no setting was bypassed. An Admin-only startup after setup
can avoid opening real SQLite/EventSub/AIG; it does not serve the live Overlay.

Pending genuine acceptance: authenticated OBS connection, existing scene/source
discovery over v5, switch between two existing scenes and restore original, refresh
the existing source, exactly one short local recording, stop, file existence/playback,
and inactive streaming. Browser ACK alone will not be labeled real OBS rendering.

## Reproducible checks and coverage

- New backend tests: OBS unavailable/cooldown/recovery, correct v5 SDK handshake,
  wrong password/auth-disabled refusal, scenes/invalid scene, exact browser source
  URL/refresh, actual-state checks, one-use revisions, concurrent busy rejection,
  lost StartRecord/StopRecord/scene replies, no blind retries, uncertain refresh,
  disconnection during reconciliation, stream command denial and credential redaction.
- HTTP tests: unauthenticated reads/writes, login cookie/CSRF rotation, logout,
  remote peers/forwarded spoofing, Host/Origin/Fetch Metadata/CSRF rejection, strict
  payload shapes/duplicate keys, bounded bodies, rate limits, forbidden generic and
  streaming endpoints. No real Twitch/OBS endpoints are used by these tests.
- Frontend tests: authenticated and setup-required states, literal scene text,
  explicit operations only, synchronous double-click prevention, start/stop feedback
  from refreshed status, unknown-outcome disabled controls and separate password form.
- Actual Chromium Admin suite: private synthetic login, scene switch, refresh ACK,
  one start under double click, one stop, synthetic path, reload with no auto-record,
  narrow viewport and logout. OBS-only fixture created no application databases.
- Python environment: `.artifacts/phase45/venv` created from locked dependencies,
  leaving prior `.venv` / `.artifacts/phase4/venv` untouched. New libraries are
  `obsws-python==1.8.0` and `websocket-client==1.9.2`. Existing AIG pin unchanged.
- Frontend TypeScript/lint/Prettier and isolated Vite build passed. Output is
  `.artifacts/phase45/frontend`; existing `frontend/dist` was not rebuilt.

Development failures corrected: pytest reserves the parametrization name `request`,
so the new test uses `rpc_name`; initial Chromium text lookup included a child timer,
so the status label now has its own semantic element; local npm rejected CLI argument
forwarding, so isolated builds use Vite's documented CLI directly. No failed attempt
was counted as PASS and no real recording or Action resulted.

Final dependency audits, original Chromium regression collection, source/secret review
and final measured report update are performed before release. A successful offline
test run cannot satisfy the blocked real OBS gate. No commit, push, stream, upload or
submission is implied by this report.
