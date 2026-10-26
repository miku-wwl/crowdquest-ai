# CrowdQuest AI

**Crowd-powered challenges. Streamer-approved execution.**

AI-powered Twitch audience challenges with streamer approval, safe execution, and reliable Agent runtime.

## Current status

**The real Twitch → SQLite → owner-selected Dashboard → OBS display chain is evidenced.**
Phase 1 engineering acceptance is PASS: tested backend security hardening is loaded,
real EventSub/SQLite recovery is verified, and the user confirmed new owner login,
OBS pairing, rendering and preview expiry. Raw-image archival remains PARTIAL; supplied
visual evidence and explicit user observation are attributed separately.

Phase 2 local single-action integration is implemented and tested with installed AIG
and real temporary SQLite stores. It is opt-in and has not replaced the running Phase 1
service. See [Phase 2 implementation](docs/PHASE2-IMPLEMENTATION.md) for exact scope,
API/provisioning, tests and the separate live/human-approval boundaries.
See the [final acceptance report](docs/PHASE1-FINAL-ACCEPTANCE.md) for exact evidence classes.
No AI Plans, AIG Runtime execution or production Approval/Authorization are implemented.

The public repository already existed with one README-only initial commit
(`639eabc8b6947a44048b220faea5fea4990587d1`, created 2026-10-25 UTC).
Phase 0 preserves that history; it does not fork or import another project's source.

Planned flow: Twitch `!quest` → validated candidate → AI Plan → streamer preview and
explicit approval → independent AIG Authorization → durable overlay-job admission →
separate worker → OBS Browser Source. Admission and rendering have separate outcomes.

## Local Windows setup

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
5. Open the overlay, match its code in the owner dashboard and click Pair. Wait for Ready.
   Select a candidate, then Preview selected. Nothing is automatically published.

Every preview says **DEVELOPMENT PREVIEW — NOT APPROVED / NOT EXECUTED** and expires in
60 seconds. Refresh/reconnect/restart do not replay old previews. Text is escaped.

For OBS: add a Browser Source using **http://localhost:8000/overlay**, size 1280×720.
Pair the code shown **inside OBS**, wait for Ready, then select a fresh preview. The
URL has no credential. Inspect the actual OBS canvas; a normal browser screenshot is
not OBS proof. Actual OBS observation is still outstanding on this machine.

Use the exact localhost URL; the server binds 127.0.0.1 and rejects other Host/Origin
values, LAN aliases and tunnels. No plaintext secret fallback. The consumer does not
load `.env` automatically. Optional process variable `CROWDQUEST_STATE_DIR` selects a
private directory outside the checkout. Configuration changes require restart.

## Verification

Install Python 3.13 and [uv](https://docs.astral.sh/uv/), then from this repository:

```powershell
uv sync --locked --python 3.13
uv lock --check --offline
uv pip check
uv run --locked python -I scripts/verify_baseline.py
uv run ruff check crowdquest tests
uv run ruff format --check crowdquest tests
uv run pytest -q
npm --prefix frontend run test
npm --prefix frontend run build
uv run python -m playwright install chromium
uv run python -m tests.browser_e2e
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
2026-10-26. Submissions are open. The rules' Pacific deadline converts to
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
