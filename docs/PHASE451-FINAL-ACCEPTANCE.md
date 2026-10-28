# Phase 4.5.1 — recovered EventSub engineering and live acceptance

Date: 2026-10-28, Pacific/Auckland. Root Codex session:
`01a172e3-9804-73c2-b597-8c5df928a56c`.
Starting main/remote baseline: `c7d4ab1fbb65b694ffed7c54b5aac0bfe5a99dc1`.

**Engineering tests PASS locally. Real E2E NOT_RUN at this checkpoint.**
This report is new; Phase 3, Phase 4 and Phase 4.5 reports/archives are preserved.
The final source/CI receipt and live observations are added only after verification.
No historical Action is replayed and no live event has been sent in this phase.

## Interrupted work recovered

Initial status was two unstaged modifications (`crowdquest/eventsub.py`,
`tests/test_eventsub.py`) and the untracked `tests/test_eventsub_reconnect.py`;
the index was empty. HEAD and origin/main matched the stated baseline. Those exact
three files were copied byte-for-byte into a new ignored recovery directory with a
SHA256 manifest before continuing. No reset, clean or overwrite of user work occurred.

The resumed implementation retained the root-path and continuously-reading handover
changes. Additional work completed repeated-control handling, fail-closed abnormal
closure, redirect denial and lifecycle/restart regression coverage. The only other
test edit establishes a missing precondition in Phase 4's existing no-replay E2E.

## Reconnect findings and correction

The initial endpoint remains `wss://eventsub.wss.twitch.tv/ws`. The
[official reconnect example](https://dev.twitch.tv/docs/eventsub/handling-websocket-events/#reconnect-message)
uses the EventSub hostname with an opaque query and no explicit `/ws`. The original
validator rejected that form. A successful handover must retain subscriptions and
keep the old socket receiving until a valid welcome arrives on the replacement.

Before the production change, focused reproduction produced **five failures and two
passes**: four root-path/port combinations were incorrectly rejected, and a fixture
withheld the new welcome until old notifications were ingested, exposing the stopped
reader. This is isolated defect evidence, not a genuine Twitch reconnect observation.

The historical redacted Phase 4 report confirms `RECONNECT_URL` rejection followed
by recovery in about 4.83 seconds, but retains no original reconnect URI. Therefore
the compatibility defect is confirmed while the exact cause of that past incident
remains **UNCONFIRMED**. No live socket was disrupted to manufacture a reconnect.

Changes are confined to consumer EventSub transport/processing:

- Accept only WSS, exact Twitch EventSub authority, absent/default 443 port, and the
  documented empty/root or existing `/ws` path. Return the original string unchanged,
  including opaque query order and escaping. No URI decoding or reconstruction.
- Reject userinfo including empty userinfo, foreign/local/private destinations,
  nonstandard/malformed ports, fragments, controls/whitespace, backslashes and
  normalization-dependent paths. This does not introduce general URL fetching.
- A supported `ClientConnection` factory rejects HTTP 3xx before the WebSocket
  library can follow redirects. Real loopback wire tests verify the redirected
  destination receives no connection. TLS verification/proxy restrictions remain.
- One replacement attempt runs alongside the old receiver. Existing parsing,
  identity checks, SQLite intake and durable dedup are shared, not duplicated.
  Old queued frames are drained under the old session identity after the new
  welcome and before switching identities; no second subscription POST occurs.
- Identical repeated reconnect controls are ignored during that same attempt;
  conflicting ones fail closed without creating another replacement. Revocation,
  failed/missing welcome, source loss or abnormal close abort safely. Cancellation
  and app shutdown cancel/join both tasks and close unadopted sockets.
- Handover has a trusted 25-second deadline, inside Twitch's 30-second grace period,
  with bounded library close cleanup. There is no new handover retry loop. Ordinary
  connection loss retains the existing service loop with capped 30-second backoff
  and fresh subscription; no missed-chat replay or exactly-once network guarantee
  is claimed. AIG's unrelated adapter budget remains five seconds.

Diagnostics contain fixed categories, counts and stage transitions, never raw URLs,
queries, frames or credentials. Added events include reconnect start/completion and
ignored repeated control; the safe status counter includes successful reconnects.

References reviewed: [Twitch WebSocket handling](https://dev.twitch.tv/docs/eventsub/handling-websocket-events),
[WebSocket message contract](https://dev.twitch.tv/docs/eventsub/websocket-reference/),
[official CLI fixture](https://dev.twitch.tv/docs/cli/websocket-event-command/), and
[supported WebSocket connection factory](https://websockets.readthedocs.io/en/stable/reference/asyncio/client.html).
Installed websockets 17.3 and its actual handshake API were inspected. The Twitch CLI
was not installed; it was NOT_RUN. Controlled queues and an actual loopback WebSocket
server provide explicitly SYNTHETIC coverage without relaxing production destinations.

## Regression results

| Check | Current observed result |
| --- | --- |
| Focused EventSub | **60 passed**, including 51 new parameterized cases. URL forms, SSRF/redirect denial, old-frame preservation before/at welcome, duplicates, timeout/failure/revocation/cancellation, real loopback transport, app shutdown with no leaked tasks and persisted intake across instance restart. |
| Full backend | **276 passed**, 110.04 s; one existing Starlette/httpx deprecation warning. No skips. |
| Frontend | **49 passed**, six files. TypeScript, strict lint, Prettier and isolated build pass; no frontend application source change. |
| Chromium | All **five** suites pass: Phase 1, Phase 3/worker, Phase 4, optional OBS fixture and Studio recording. Temporary stores and synthetic OAuth/chat/model/consent only. |
| AIG | Installed 0.3.0 full commit `bb8e8fb1234128613a750bee17967b225072bb14`, 45 installed RECORD files and 12,127-byte upstream instructions verified. Single tool, separate gates, default five seconds, Unknown/no retry and receipt persistence regressions remain. |
| Dependencies/security | Locked uv/npm unchanged; compatibility, Ruff, formatting and scoped input/security tests pass; npm audit zero known vulnerabilities. Exact-source CI includes its own Python dependency audit. |

One browser attempt failed before the final pass: Phase 4 reloaded the second overlay
before establishing that its old view had received the outcome. A first presentation
to an unseen view is valid under the existing durable `outcome_issues` contract.
The test now verifies **both** old views display the result before reloading one.
Its original waiting/no-replay, eight-second expiry, one-job and one-outcome assertions
remain. No production timeout/state rule was changed to pass it.

The current synthetic Studio WebM is 1920×1080, 32.06 s, 8,375,372 bytes, 938 decoded
frames and **29.22 average FPS**. SHA256:
`7d13f5b1df70dba48b1d8c869d6744765dc2b306c12df827b0ef0aab979780bf`.
Full FFmpeg decode passes; browser playback readyState 4/no error; preview/recorded
frame mean absolute RGB error 1.9241/255. This is a real media file generated with
synthetic application state, **not live Twitch video**. Sustained 30 FPS is not claimed.

## Windows service and IAB observations

At recovery, the verified CrowdQuest loopback listener was PID 19744, matching its
private EventSub status. Both `/` and `/broadcast-studio` returned HTTP 200 and the
expected existing isolated frontend index (SHA256
`9bed990c6296371d0cc77c143b8e11b28beae2ed5c067d1eaf1c87e7f4550f81`).
The core-only environment does not contain the OBS SDK; optional adapter stays off.
The existing worker lease and EventSub welcome/subscription/keepalives were healthy.

The earlier browser-host error and the user's manual render are separate evidence.
After reopening, the bounded IAB inspection **succeeded**: actual Studio pixels and
DOM displayed Disconnected / Sign in as the channel owner / Connect Twitch. This
is the expected unauthenticated owner-session gate, not proof that EventSub is down.
The prior 404 was corrected by the user as a malformed URL with extra text; the exact
route works. No native desktop driver, cookie extraction, fake session or tunnel was
used. Owner login remains required after final activation.

Existing local Ollama was stopped at readiness inspection. Its already installed
`phi4-mini:latest` was found in the configured D: model store. The existing executable
was started loopback-only without download. An empty request preloaded the model:
zero generated tokens, zero Plans; CPU residency verified. This is preparation,
not the one permitted real Plan generation. No paid provider is configured.

Before activation, five real SQLite databases passed read-only integrity checks and
new online backups passed integrity plus consistent-snapshot logical comparison.
No pending Action, Draft/Open voting round, active result or unrendered job existed.
Private identity, credentials and historical records remain outside Git. Activation
is limited to the freshly verified CrowdQuest process and worker, after another
idle check; post-start health and protected-row comparison are recorded separately.

## Evidence index and live gate

| Evidence | Classification / location |
| --- | --- |
| Interrupted file backup | Ignored `.artifacts/phase451/recovered-*/manifest.json`; exact three-file copies. |
| Isolated regression/recording | `.artifacts/phase451/synthetic-qualified/qualification.json` and watermarked WebM; SYNTHETIC_TEST. |
| IAB sign-in screenshot | Private phase451 operation `original-images/studio-owner-signin.jpg`; actual IAB screenshot, 43,952 bytes, SHA256 `ce7e2be9799f29c1929688b915b5b2b76b7cfc9fce973032ed14114bea86d172`. AGENT_VERIFIED, not authenticated live acceptance. |
| Database backups/readiness | New private `%LOCALAPPDATA%/CrowdQuestAI/engineering/phase451-real-*` operation; originals excluded from Git/public review. |
| Public qualification | Sanitized `docs/evidence/phase451/` counts, classifications and later exact CI receipt; no private databases, cookies or tokens. |
| Human browser render | USER_REPORTED in the recovery request, independently corroborated by the restored agent IAB observation. |

**No fresh live suggestion, vote, round, Plan, Action or outcome has been created.**
The latest recovery instruction requires a new explicit **GO after readiness**.
Then the bound is two genuine suggestions, one round, one account vote, one real
model Plan and at most one Action. Existing per-viewer intake limits require spacing
the two account suggestions by more than 30 seconds; limits are not weakened.

After generation, show the exact Plan/version/parameters and await explicit approval.
Keep Approve, Admit, Authorize and Execute distinct. Unknown or uncertain execution
stops the run, with no second Execute. Ask for the truthful owner outcome. Save the
one acceptance WebM before any refresh; record real Open tally, countdown, result
expiry and no replay from actual IAB pixels. No old Action is used as a substitute.

At this checkpoint the real workflow and real acceptance recording are **NOT_RUN**;
Phase 4.5.1 overall and Phase 5 readiness remain **PARTIAL**. Engineering delivery
does not substitute for those gates. No livestream, OBS control, cloud deployment,
YouTube upload, Devpost submission or automatic Phase 5 work is performed.

## Rollback and continuation

If rollback becomes necessary, first preserve new recordings/evidence and confirm no
active or ambiguous Action/round. Stop only verified CrowdQuest processes during the
authorized safe window. Return source/environment/assets to the previously qualified
revision using a separate reviewed checkout or normal corrective commit; do not
reset/clean user work, delete databases or replay old Actions. No schema migration
was introduced. Keep the existing private profile/identity/receipts and inspect any
Unknown history. A code rollback does not justify replacing real SQLite with backups.

The next required human step, after final service/CI verification, is owner login
through the ordinary IAB Twitch flow with only user:read:chat. The agent then checks
readiness and requests the specific one-round GO. Exact Plan approval and factual
outcome confirmation remain later checkpoints. See the final delivery receipt for
the eventual exact source HEAD and CI; a report cannot embed its own commit hash.
