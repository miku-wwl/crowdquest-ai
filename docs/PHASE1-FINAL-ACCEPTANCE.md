# Phase 1 final engineering acceptance

Date: 2026-10-26, Pacific/Auckland. **Final status: PARTIAL; Phase 2 is BLOCKED.**

The real viewer-to-OBS display chain passed user observation and is corroborated by
live EventSub/SQLite evidence. The user subsequently authorized a controlled restart;
the tested security/recovery fixes are now loaded and EventSub is genuinely listening.
Post-start owner login, OBS pairing, a fresh real message and OBS expiry observation
await user actions. Formal raw-image archival remains incomplete and is reported
separately. No standard was lowered to announce PASS.

## Git provenance and scope

Git baseline: `77eb57bba4d76d7d884a4d1ab5fbaf207bb7463c`, main, HTTPS origin
`miku-wwl/crowdquest-ai`. Six existing uncommitted diagnostic paths were inspected
and preserved. Tested implementation commit:
`97b023048f695bbee4ca170c1e968eaf4b4c4720`.
[GitHub CI 40260251492](https://github.com/miku-wwl/crowdquest-ai/actions/runs/40260251492)
completed successfully for that exact commit. The final response identifies final
main without self-referential SHA claims.

No AIG core, pin, private credentials or real candidate records were modified. The
complete 12,127-byte upstream consumer instructions remain intact. AIG stays
`0.3.0` at `bb8e8fb1234128613a750bee17967b225072bb14`.

## Acceptance status

| Required status | Result | Evidence and exact boundary |
| --- | --- | --- |
| PHASE1_REAL_TWITCH_INGESTION | PASS | Real OAuth validation 200; scope exactly user:read:chat; matching enabled channel.chat.message v1 subscription; actual notification and ACCEPTED journal entry |
| PHASE1_SQLITE_PERSISTENCE | PASS | Real integrity_check=ok, 1 delivery/message/candidate, previewed; actual unique indexes; controlled duplicate/concurrency/process/service-restart tests |
| PHASE1_DASHBOARD_SELECTION | PASS | USER_OBSERVED_REAL_E2E: supplied dashboard image shows Selected/Previously previewed; agent read-only DB confirms previewed |
| PHASE1_OBS_RENDER | PASS | USER_PROVIDED_VISUAL_EVIDENCE: actual OBS window/canvas screenshot, not an agent browser screenshot |
| PHASE1_SECURITY | PARTIAL | Tested hardening is loaded; old owner/overlay sessions denied; user verification of new real owner login/pairing remains pending |
| PHASE1_RESILIENCE | PASS | Controlled temporary-service, actual temporary SQLite write-lock/restart, mock API-error and browser offline/reconnect tests; live fault injection is NOT_RUN |
| PHASE1_REGRESSION | PASS | 79 backend, 9 frontend, lint, type/build, actual Chromium synthetic E2E, dependency and advisory checks; see commands below |
| PHASE1_EVIDENCE_ARCHIVE | PARTIAL | Redacted real proof and two-image visual index saved; PNG original bytes/local paths/hashes unavailable, raw-image import USER_ACTION_REQUIRED |
| PHASE1_FINAL_STATUS | PARTIAL | Post-start real owner/OBS validation is pending; raw-image archival remains explicitly PARTIAL |

Formal Phase 1 Definition of Done is not fully satisfied. The successful OBS display
does not automatically close security or archival gates.

## Real evidence

[final-real-chain.json](evidence/phase1/final-real-chain.json) was produced by
read-only inspection on 2026-10-26 at 02:30:38 UTC / 15:30:38 NZDT:

- Token and configured owner/client match; only `user:read:chat`.
- One enabled subscription matches the exact active session and both owner IDs.
- Live backend PID 47404, receiving keepalives, 2 notifications, 1 admitted candidate.
- One notification was `NOT_QUEST`; the other was `ACCEPTED`. **Two notifications
  are not evidence of real duplicate-delivery suppression.**
- Real candidate timestamp: `2026-10-26T01:51:02.688668Z` / 14:51:02 NZDT.
  Delivery hash `9d6daadf3891`, chat hash `59171c230b77`, channel hash `180988ab5012`.
- That genuine delivery ID fails the former alphabet restriction, confirming the
  compatibility defect on real data. The earlier two lost frames were not retained;
  their exact payloads cannot be reconstructed or claimed verified.

The two final images were visually inspected directly in the user's message:
[visual evidence index](evidence/phase1/user-provided/INDEX.json). They show actual
OBS rendering, matching dashboard text, 2 Ready and Previously previewed. They are
**USER_OBSERVED_REAL_E2E**, not AGENT_VERIFIED_AUTOMATED_E2E. Their original local paths
are unknown, not fabricated. The two historical screenshots excluded by the user
are not required or searched further.

## Bugs fixed

1. Preserve bounded opaque delivery IDs, including Base64 punctuation/padding;
   accept valid RFC3339 offsets and transport connection metadata without weakening
   exact subscription/session/channel identity checks.
2. Record bounded redacted lifecycle, notification hashes, input rejection and safe
   SQLite error classification. Bad frames no longer silently kill a healthy stream.
3. Pairing codes now use 64 random bits, a five-minute pending TTL, one-use approval,
   five-failure/minute throttle, owner/CSRF/Origin checks and separate 256-bit HttpOnly
   read-only cookies. Reusing a code cannot extend a paired session's authority.
4. Preview/cache lifetimes use server monotonic time. The browser uses remaining
   duration and performance.now, not its wall clock. A compatibility path uses the
   running legacy server's HTTP Date header, preserving its existing display behavior.
   Clear/expiry return Waiting; each deliberate Preview replaces the 60-second window.
5. Temporary auth/API failures deny access but retain existing consent and back off;
   confirmed revocation still invalidates it. Rotated refresh tokens are stored before
   subsequent validation, so a transient validation error cannot discard the rotation.
6. Chromium fixture cleanup previously returned WinError 32 after scenario assertions.
   That run is retained as **FAIL**. The helper now checks fixture identity, app shutdown
   acknowledgement and released owner lock before reaping a Windows launcher; PASS is
   printed only after complete cleanup. The corrected command subsequently exited 0.

Monotonic timing follows [MDN performance.now](https://developer.mozilla.org/en-US/docs/Web/API/Performance/now).
Credential-role/cookie review used [OWASP session guidance](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html).
Refresh persistence was checked against [Twitch token refresh documentation](https://dev.twitch.tv/docs/authentication/refresh-tokens/).

## Current test results

All fault/destructive tests use temporary databases, fixture credentials and local
fixture services. They never clear or replay events into the real development DB.

| Command | Actual result / evidence class |
| --- | --- |
| uv run pytest -q | 79 passed; 1 existing Starlette TestClient HTTPX deprecation warning; SYNTHETIC_TEST / actual SQLite and process tests |
| npm --prefix frontend run test | 9 passed; includes forward/backward client-clock skew and legacy protocol |
| npm --prefix frontend run build | PASS; actual TypeScript check and Vite production build |
| uv run python -m tests.browser_e2e | PASS, exit 0; AGENT_VERIFIED_AUTOMATED_E2E using SYNTHETIC_TEST OAuth/chat, actual Chromium and HTTP server |
| uv run ruff check crowdquest tests | PASS |
| uv run ruff format --check crowdquest tests | PASS |
| uv run python -I scripts/verify_baseline.py | PASS; installed AIG provenance/public API/upstream template |
| uv lock --check --offline; uv pip check | PASS |
| npm --prefix frontend audit | 0 reported vulnerabilities from official registry at verification time |

Source review scanned 67 tracked/candidate files. Pattern, credential-URL and exact
in-memory comparisons against configured secret/token values found no matches. No
credential value or fingerprint was printed. Private databases, environment files,
generated bundles and node_modules are excluded; local Markdown targets and Python
syntax passed. This is a scoped review, not a universal security guarantee.

Cases include duplicate delivery/chat IDs, conflicting identity payloads, distinct
messages, actual SQL uniqueness, 16 concurrent duplicates, fresh Python processes,
temporary server restart preserving candidate IDs/text, wrong owner/source/schema,
malformed input, length/control characters, rate/capacity bounds, unauthenticated/CSRF
denials, cookie roles, one-use/expiry/throttled pairing, clear/60-second expiry,
explicit repeated Preview, two authorized overlay sessions, refresh/reconnect no replay,
XSS literal rendering, clock skew, transient 503 recovery, refresh rotation persistence,
confirmed revocation and actual SQLITE_BUSY diagnosis/recovery.

Live Twitch disconnect/revocation/API-failure injection, actual OBS refresh automation
and real exact-delivery replay are **NOT_RUN**. The authorized actual service start
is recorded below. Controlled fault tests do not establish unobserved live behaviors.

## Controlled service start and current manual boundary

Initially the user's Part B6 / Part G4 constraint prevented a restart requiring real
login/pairing. The user then chose option 2 and explicitly authorized one controlled
restart, with private SQLite backup and manual login/pairing. At execution time the
old PID 47404 was already absent and port 8000 was not listening, so no process was
terminated. Only CrowdQuest was started; other projects were untouched.

[controlled-restart.json](evidence/phase1/controlled-restart.json) records the checks
at 2026-10-26 04:01:14 UTC / 17:01:14 NZDT:

- SQLite backup API produced a private backup outside Git. Source and backup both
  returned integrity_check=ok; complete logical contents matched. After startup the
  real DB still had exactly 1 delivery, 1 message and 1 candidate, with unchanged
  logical contents. Original records were not cleared or replayed.
- New service PID 19880 owns only 127.0.0.1:8000. Imported module hashes match the
  tested commit; 64-bit pairing code and transient-auth handling are loaded.
- In-memory comparisons confirmed unchanged Access Token, Refresh Token and Client
  Secret values. No credential value or credential fingerprint was printed/exported.
- Real token validation and subscription lookup returned 200; exact scope remains
  user:read:chat. One enabled channel.chat.message v1 subscription matches the new
  session and both configured owner IDs. Welcome, fresh keepalives, an open socket
  and active receive wait establish EVENTSUB_READY=YES.
- Frontend returns 200. Old/absent owner and overlay sessions return 401; a wrong
  Host returns 400. New owner authentication and OBS pairing require the user.
- Targeted rerun: `uv run pytest -q tests/test_auth.py tests/test_service_restart.py
  tests/test_persistence_process.py` returned 14 passed, one existing deprecation warning.
  These remain controlled tests, not real duplicate delivery evidence.

The user was asked to sign in, refresh/pair the actual OBS source, send one fresh
real !quest message, manually Preview it, and observe expiry after approximately
65 seconds. Those post-start observations are pending. Phase 1 stays PARTIAL and
Phase 2 remains BLOCKED until the mandatory checks are complete. No Twitch stream
was started, and the agent sent no chat.

## Phase 2 gate

PHASE2_SCOPE_VERIFIED=PASS. Original scope is [PHASE_PLAN.md, Phase 2](PHASE_PLAN.md):
one frozen `enqueue_overlay_challenge` capability, five-second runtime budget, strict
domain Plan, persistent Run, exact Approval, separate Action Authorization, one durable
claim and transactional local queue/receipt, with Unknown quarantine and negative tests.
No new product feature, provider call, paid service or deployment is inferred.

PHASE2_IMPLEMENTATION_STATUS=BLOCKED; PHASE2_TEST_STATUS=NOT_RUN;
PHASE2_FINAL_STATUS=BLOCKED. The user's automatic progression is conditional on all
mandatory gates passing. Phase 1 is still PARTIAL, so no Phase 2 source or AIG execution
was started. Competition eligibility/reuse ambiguity remains UNVERIFIED separately.
