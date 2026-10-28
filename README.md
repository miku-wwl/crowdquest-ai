# CrowdQuest AI

**Your Chat Becomes the Game Director.**

AI-powered Twitch audience challenges with streamer approval, safe execution, and reliable Agent runtime.

## Current status

**The real Twitch → SQLite → owner-selected Dashboard → OBS display chain is evidenced.**
Phase 1 engineering acceptance is PASS: tested backend security hardening is loaded,
real EventSub/SQLite recovery is verified, and the user confirmed new owner login,
OBS pairing, rendering and preview expiry. Raw-image archival remains PARTIAL; supplied
visual evidence and explicit user observation are attributed separately.

Phase 2 installed-AIG integration and Phase 3 local engineering/CI are PASS.
The **genuine Phase 3 Twitch → real local model → explicit human Approval → independent
Authorization → AIG → actual OBS** single-Action session is now **PASS**, including
countdown expiry and no replay after OBS refresh. See the dated
[real session record](docs/PHASE3-REAL-ACCEPTANCE.md); earlier pre-activation reports
remain historical. Original live screenshot files were not exported to Git.

Phase 4 adds two-candidate crowd voting (`!vote 1` / `!vote 2`), exact winner-to-Plan
binding, owner-reported Completed/Failed/Skipped outcomes and a transparent broadcast
UI. **Phase 4 local engineering and exact-commit CI are PASS**
([acceptance/CI receipt](docs/PHASE4-ACCEPTANCE.md)). Qualification uses temporary SQLite and actual Chromium, with synthetic
chat/model/consent. Subsequent Phase 4 real acceptance established
**CORE_ACTION_CHAIN=PASS / PHASE4_OVERALL=PARTIAL**. The intermediate Open 1:0 OBS
frame was not independently captured, and a RECONNECT_URL rejection recovered in
approximately 4.83 seconds without a resolved root cause. Historical reports retain
their original dates and scope; no historical Action is replayed.

**Phase 4.5 introduces OBS-free Broadcast Studio:** one Canvas for live scenes,
countdowns and silent local WebM recording. Open **http://localhost:8000/broadcast-studio**
after owner sign-in. OBS is optional and disabled by default. Engineering regression
and actual Chromium recording/playback pass; final IAB reacceptance remains PARTIAL
because the browser access host was unavailable after the interrupted session.
The earlier genuine IAB Waiting recording is preserved separately from fixture
footage. See [usage and limits](docs/PHASE45-BROADCAST-STUDIO.md),
[acceptance report](docs/PHASE45-BROADCAST-STUDIO-ACCEPTANCE.md) and
[prepared Phase 5 demo runbook](docs/PHASE5-DEMO-RUNBOOK.md).

Phase 4.5.1 recovers the interrupted EventSub fix: documented root reconnect URLs,
continuous old-socket intake through handover, strict destination/redirect controls
and shutdown/restart regressions. Current local qualification is 276 backend tests,
49 frontend tests and five Chromium suites. Restored IAB access shows the real
Studio's owner sign-in gate. New controlled live acceptance requires readiness,
explicit GO and exact Plan approval; see the [Phase 4.5.1 record](docs/PHASE451-FINAL-ACCEPTANCE.md).

**Your Chat Becomes the Game Director.** Viewers propose, the community chooses,
the local model structures the challenge, and the streamer keeps the final say.
The four operations remain separate: Approve Plan, Admit Action, Authorize Action,
Execute Action. Voting never grants execution authority.

![Actual Chromium voting screenshot — SYNTHETIC TEST, not real Twitch or OBS evidence](docs/evidence/phase4/synthetic-voting.png)

The public repository already existed with one README-only initial commit
(`639eabc8b6947a44048b220faea5fea4990587d1`, created 2026-10-25 UTC).
Phase 0 preserves that history; it does not fork or import another project's source.

Product flow: Twitch `!quest` → validated candidate → AI Plan → streamer preview and
explicit approval → independent AIG Authorization → durable overlay-job admission →
separate worker → browser Broadcast Studio (or optional OBS Browser Source).
Admission and rendering have separate outcomes.

## Local Windows setup

Primary presentation/recording: **http://localhost:8000/broadcast-studio**.
Sign in through the Dashboard, choose Follow live state, start/stop recording,
wait for playback verification and download the WebM before closing the page.
No OBS setup, microphone or screen capture is needed. Capture targets 30 FPS;
measured output and browser-memory limits are in the acceptance report.

The preserved [Local OBS Admin](docs/PHASE45-OBS-ADMIN.md) is optional compatibility,
requiring the `obs` extra and explicit `--obs-admin` flag. It is not part of the
core dependency chain. OBS has not been uninstalled automatically.

Requirements: Python 3.13, uv and Node.js 22.12+ (CI uses 24; locally verified with 26.5).
In this repository:

```powershell
uv sync --locked --python 3.13
npm --prefix frontend ci
npm --prefix frontend run build
```

1. Register a dedicated application in the [Twitch Developer Console](https://dev.twitch.tv/console/apps).
   Twitch requires account verification and 2FA. Select a suitable category and Confidential
   client type. Set the exact redirect to **http://localhost:8000/auth/twitch/callback**.
2. Run `uv run python -m crowdquest.setup` in your terminal. Enter the Client ID, your
   **own confirmed test channel login**, and hidden Client Secret. Never paste secrets
   into chat or command arguments. Secrets/tokens go to Windows Credential Manager;
   non-secret config and SQLite use `%LOCALAPPDATA%\CrowdQuestAI\phase1` outside Git.
3. Run `uv run python -m crowdquest`. Open **http://localhost:8000**, click Connect Twitch,
   and complete legitimate Twitch consent yourself. Only `user:read:chat` is requested;
   the authenticated login must match the configured channel owner. Restart after setup
   changes. Use one server process; a private file lock enforces it.
4. Manually send `!quest Survive 60 seconds without healing` in that owned channel. Wait
   for a candidate and connected status. Missed/disconnected events are not replayed.
5. Open Broadcast Studio using the same owner session, then select a candidate in
   Dashboard and Preview selected. The Studio uses its own read-only display cookie
   without OBS pairing. Nothing is automatically approved or executed.

Every preview says **DEVELOPMENT PREVIEW — NOT APPROVED / NOT EXECUTED** and expires in
60 seconds. Refresh/reconnect/restart do not replay old previews. Text is escaped.

For optional OBS compatibility: add a Browser Source using **http://localhost:8000/overlay**, size 1280×720.
Pair the code shown **inside OBS**, wait for Ready, then select a fresh preview. The
URL has no credential. Inspect the actual OBS canvas; a normal browser screenshot is
not OBS proof. Historical real OBS evidence and current browser Studio evidence
remain separate; the unresolved Phase 4 limitations above are not erased.

Use the exact localhost URL; the server binds 127.0.0.1 and rejects other Host/Origin
values, LAN aliases and tunnels. No plaintext secret fallback. The consumer does not
load `.env` automatically. Optional process variable `CROWDQUEST_STATE_DIR` selects a
private directory outside the checkout. Configuration changes require restart.

## Phase 4 product setup

Use the existing local Ollama `phi4-mini:latest` and the production composition in the
[operator runbook](docs/PHASE3-RUNBOOK.md). Reuse a provisioned private profile; never
reset its identities, receipts or Unknown history. The default startup above retains
Phase 1 development previews for compatibility. A new installation should build the
frontend normally; an operator preserving a real running instance should use the
isolated build/test procedure below until controlled activation is authorized.

The [upgrade architecture](docs/PHASE4-COMPETITIVE-UPGRADE.md),
[acceptance evidence](docs/PHASE4-ACCEPTANCE.md), [live runbook](docs/PHASE4-LIVE-RUNBOOK.md),
[English 2:45 demo plan](docs/PHASE5-DEMO-STORYBOARD.md) and
[submission checklist](docs/PHASE5-SUBMISSION-CHECKLIST.md) describe the current scope.
Outcomes are streamer reports, not automatic gameplay recognition.

## Verification

Install Python 3.13 and [uv](https://docs.astral.sh/uv/), then from this repository:

```powershell
$env:UV_PROJECT_ENVIRONMENT = Join-Path (Get-Location) ".artifacts/phase4/venv"
uv sync --locked --python 3.13
uv lock --check --offline
uv pip check
uv run --locked python -I scripts/verify_baseline.py --environment $env:UV_PROJECT_ENVIRONMENT
uv run ruff check crowdquest tests
uv run ruff format --check crowdquest tests
uv run pytest -q
npm --prefix frontend run test
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run build:test
# Keep real frontend/dist intact; test fixture servers use the isolated build:
$env:CROWDQUEST_TEST_FRONTEND = Join-Path (Get-Location) ".artifacts/phase4/frontend"
uv run python -m playwright install chromium
uv run python -m tests.browser_e2e
uv run python -m tests.phase3_browser_e2e
uv run python -m tests.phase4_browser_e2e
git diff --check
```

These tests need no Twitch credentials. Browser E2E runs a temporary local server with
synthetic OAuth/EventSub and blocks external browser requests. It is not live Twitch
proof. After a genuine event, `uv run python -m crowdquest.evidence` reads persisted
counts, timestamps and hashed IDs without modifying state or exposing text/tokens.

AIG remains at full commit `bb8e8fb1234128613a750bee17967b225072bb14`, version `0.3.0`.
Its complete upstream instructions and Phase 0 checks are preserved. Python and frontend
dependencies are locked in `uv.lock` and `frontend/package-lock.json`.

## Competition and reuse

[Official rules](https://twitchcon-codex.devpost.com/rules) and
[FAQ/resources](https://twitchcon-codex.devpost.com/resources) were checked on
2026-10-27. Submissions are open. The rules' Pacific deadline converts to
**2026-11-03 11:00 NZDT** (2026-11-02 22:00 UTC).

AIG is a pre-existing MIT runtime, transparently reused as a dependency. Its eligibility
as the entrant's own pre-existing library is **UNVERIFIED**. Personal eligibility and
Devpost registration are also unconfirmed. See [originality and reuse](docs/ORIGINALITY_AND_REUSE.md)
and the [submission checklist](docs/SUBMISSION_CHECKLIST.md); this is not a claim of
fully verified competition eligibility. No organizer has been contacted.

## Project documents

- [Product requirements](docs/PRD.md)
- [Architecture and lifecycle](docs/ARCHITECTURE.md)
- [Security and threat model](docs/SECURITY_AND_THREAT_MODEL.md)
- [AIG integration contract](docs/AIG_INTEGRATION.md)
- [Twitch integration plan](docs/TWITCH_INTEGRATION.md)
- [Phases and gates](docs/PHASE_PLAN.md)
- [Acceptance criteria](docs/ACCEPTANCE_CRITERIA.md)
- [Decisions](docs/DECISIONS.md)
- [Phase 0 evidence](docs/PHASE0_EVIDENCE.md)
- [Phase 1 evidence and live-user steps](docs/PHASE1_EVIDENCE.md)
- [Phase 1 final engineering acceptance](docs/PHASE1-FINAL-ACCEPTANCE.md)

Read [AGENTS.md](AGENTS.md) before development. It preserves the entire authoritative
AIG consumer template and appends CrowdQuest constraints. No AIG core changes are allowed.

License: [MIT](LICENSE). The pre-existing dependency's original notice is retained in
[third-party notices](docs/THIRD_PARTY_NOTICES.md).
