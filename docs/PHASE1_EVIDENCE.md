# Phase 1 evidence — PARTIAL

Date: 2026-10-26, Pacific/Auckland. Engineering implementation is available; real
Twitch authentication/chat and actual OBS observation remain unverified. Phase 2/3
have not started. Personal eligibility/Devpost registration are unconfirmed and
own pre-existing AIG reuse remains UNVERIFIED. No organizer contact or submission.

## Provenance and delivery

- Baseline ancestor: `59fe6d264caf9aec5ee77270608498b5e789ad97`.
- Repository: https://github.com/miku-wwl/crowdquest-ai ; branch main; HTTPS origin.
- Initial Phase 1 preflight: clean working tree; fetched origin/main matched baseline.
- Complete upstream 12,127-byte AGENTS prefix preserved; only a separate dated Phase 1
  authorization section appended. AIG v0.3.0 pin unchanged at
  `bb8e8fb1234128613a750bee17967b225072bb14`.
- Implementation commit and observed CI URL will be recorded in the delivery receipt
  after the authorized push. No remote CI pass is claimed in this pre-push snapshot.
- Codex thread: `01a172e3-9804-73c2-b597-8c5df928a56c` (shared Phase 0/1 thread).

## Implemented boundary

`crowdquest/` implements fixed-endpoint backend code exchange, browser-bound one-use
state, exact owner/client/scope validation, refresh/rotation/hourly validation/revocation,
Windows Credential Manager storage, EventSub welcome/subscription/notification/keepalive/
reconnect/revocation, bounded command parsing and transactional SQLite intake.

The React/TypeScript/Vite dashboard requires an owner session, manual selection, CSRF
and Origin checks. OBS URLs carry no credentials; a code matched by the owner provisions
a separate HttpOnly read-only overlay cookie. Text is escaped, warnings are permanent,
previews expire in 60s and fresh views/reconnects/restarts do not replay previous text.
No public candidate injection endpoint, test-mode configuration flag, AIG runtime,
AI Plan, execution tool, production Approval or Action Authorization was added.

## Actual local verification

Environment: Windows; Python 3.13.9; SQLite 3.51.0; uv 0.11.16; Node 26.5.0;
npm 12.0.1; React 19.3.1; Vite 8.3.5; Playwright 1.64.1/actual Chromium.
CI uses Linux/Python 3.13/Node 24. Both ecosystems have committed lockfiles.

| Check | Actual local result |
| --- | --- |
| Phase 0 installed dependency/template/public API verifier | PASS |
| `uv lock --check --offline`, `uv pip check` | PASS |
| `uv run ruff check crowdquest tests` | PASS |
| `uv run ruff format --check crowdquest tests` | PASS |
| `uv run pytest -q` | 65 passed; one Starlette TestClient deprecation warning about HTTPX |
| `npm --prefix frontend run test` | 7 passed |
| `npm --prefix frontend run build` | PASS; TypeScript and production Vite build |
| `npm --prefix frontend audit` against official registry | PASS; 0 reported vulnerabilities at verification time |
| `uv run python -m tests.browser_e2e` | PASS; real Chromium, synthetic OAuth/EventSub |
| Windows credential backend availability | Accessible; no Client Secret configured at inspection |
| Actual Twitch registration/OAuth/subscription/chat | NOT_RUN / USER_ACTION_REQUIRED |
| OBS Browser Source | NOT_RUN; no controllable OBS app or executable in checked common paths |

The TestClient warning does not fail tests. AIG still requires HTTPX 0.28; its dependency
has not been replaced to suppress that warning. It is not a live-provider result.
The machine's default npm mirror did not implement audit; a project-local `.npmrc`
and freshly resolved official-registry lock avoid that dependency. Global npm settings
were not changed. Audit results are a point-in-time advisory check, not exhaustive security proof.

Backend cases cover wrong/expired/replayed state, wrong owner/client/scope/expiry,
refresh rotation/revocation, malformed/incorrect channel/subscription/session/source,
timestamp boundaries, size/control limits, identity conflicts, concurrent duplicates,
rate/queue limits, unauthenticated and CSRF/cross-origin preview denial, cookie scopes,
pairing/expiry, logout/revocation and read-only overlay separation.

The cross-process persistence test admits a synthetic event, starts a fresh Python
interpreter and replays it. Real SQLite inspection confirms **1 delivery, 1 message,
1 candidate; ACCEPTED=1, DUPLICATE=1**. A separate 16-thread test confirms 1 accepted
candidate and 15 duplicates. These are actual persistence tests using synthetic events.

Chromium uses the actual app backend and built frontend with injected test-only HTTP
and EventSub dependencies. A local consent interceptor exercises real state/cookie
creation but does not contact Twitch; all external browser destinations are blocked.
It observes owner login, two candidate cards, explicit selection, overlay pairing,
development warning, literal injection text with no image/script execution, long-text
wrapping and clearing after reload/offline/reconnect. It does not prove Twitch or OBS.

Reviewed synthetic screenshots contain no credentials or real personal information:

- [Dashboard](evidence/phase1/synthetic-dashboard.png)
- [Overlay](evidence/phase1/synthetic-overlay.png)

## Gate results

| Gate | Status and missing evidence |
| --- | --- |
| P1-01 real Twitch event | NOT_RUN; no genuine delivery/channel/time/subscription evidence |
| P1-02 durable intake | PASS_SYNTHETIC; actual rows and fresh-process restart, live event pending |
| P1-03 negative controls | PASS_SYNTHETIC; actual backend tests |
| P1-04 safe development preview | PARTIAL; actual Chromium with synthetic data passes, actual OBS pending |
| P1-05 regression/CI | Local checks PASS; remote conclusion recorded after push |

Phase status is PARTIAL. Phase 2 readiness is NO_GO until real Phase 1 gates are closed
and the user separately authorizes Phase 2. AI/AIG execution remains NOT_IMPLEMENTED.

## User actions and live smoke procedure

1. Confirm the owned Twitch channel. Register a dedicated Confidential application in
   https://dev.twitch.tv/console/apps with exact redirect
   `http://localhost:8000/auth/twitch/callback`; account verification/2FA may be required.
2. In the repository terminal run `uv run python -m crowdquest.setup`. Enter Client ID,
   owned channel login and hidden Client Secret locally. Never paste tokens/secrets into
   chat. Configuration goes outside Git; secrets go directly to Windows Credential Manager.
3. Build frontend, run `uv run python -m crowdquest`, open http://localhost:8000, click
   Connect Twitch and consent to only `user:read:chat`. No chat-write/moderation scopes.
4. Manually send `!quest Survive 60 seconds without healing` in the owned channel. Observe
   connected status and one real-source candidate. Run `uv run python -m crowdquest.evidence`
   for read-only redacted counts/IDs/time; do not publish raw databases or auth logs.
5. Confirm persistence across a controlled server restart; sign in again after restart.
   Dedup records remain; previews and browser sessions intentionally do not.
6. Open OBS and add a Browser Source: http://localhost:8000/overlay, 1280×720. Match its
   pairing code in the owner dashboard, wait for Ready, then select and Preview. Observe
   text/warning in the actual OBS canvas. Refresh and select anew to prove no stale replay.
7. Record genuine subscription/time/hashed IDs and actual OBS observation separately.
   Review all screenshots for secrets before sharing. Do not mark a saved draft submitted.

Live authentication is the only blocked dependent step; offline work and authorized
Git delivery continue. No credentials were requested in chat or invented, and no Twitch
Chat message, moderation operation, deployment, public video or Devpost entry was made.

## Security review scope

Pre-commit review of 59 tracked/candidate files found no credential/key patterns or
credential-bearing URLs. Private DBs, generated bundles, node_modules and environment
files are excluded. Markdown targets resolve; upstream prefix digests match; the
frontend lock uses only the official npm registry. Screenshots were visually reviewed.

Host/Origin/CSRF denial, session/credential-role separation, fixed outbound endpoints,
private state, safe rendering and replay bounds are tested locally. The deployment is
single-host loopback, with plaintext HTTP restricted to localhost; no LAN/tunnel support.
Trusted local software/OS and OBS remain part of the trust boundary. This is not
multi-tenant production security or an exhaustive vulnerability audit.
