# Phase 4.5 Broadcast Studio — final engineering acceptance

Date: 2026-10-28, Pacific/Auckland. Baseline:
`5bc09eb785c71cd6519216b4dbc2bb43c0beb7e9`.

**Engineering qualification PASS; overall acceptance PARTIAL.** The OBS-free
Canvas/record/export implementation passes local regression and actual Chromium
recording/playback. An earlier real IAB Waiting recording is preserved and decodes.
The resumed session's IAB host is unavailable, so final-build IAB reacceptance and
a fresh genuine Twitch-to-Studio session have not been claimed. No new real Twitch
message, Plan or Action was created. Historical Phase 4 overall remains PARTIAL.

## Evidence classes and actual observations

| Evidence | Result and limits |
| --- | --- |
| AGENT_VERIFIED — earlier IAB session | User personally completed OAuth; actual Dashboard showed miku_wwl, Connected and EventSub listening. Studio showed Backend connected, Worker ready, EXPIRED historical challenge and Skipped/ENDED status without replay. Four local layout controls were inspected and Follow live state restored. |
| AGENT_VERIFIED — IAB recording | Actual UI Start/Stop/download, 1920×1080 silent VP8 WebM, 73.286699 s. Video player advanced beyond 0.1 s, readyState 4, no media error. Original preserved byte-for-byte; full FFmpeg decode reconfirmed after interruption. It records Waiting, not a new live challenge. |
| AGENT_VERIFIED — resumed IAB access | Two attach attempts returned `The browser access host is unavailable`. This is an automation-host limitation, not evidence of localhost network isolation. Separately, HTTP request to the safely restored Studio returned 200. No tunnel, native automation or alternative login bypass was used. |
| SYNTHETIC_TEST — final Chromium recording | Real Canvas, MediaRecorder, video playback, temporary SQLite, installed AIG and separate worker. Synthetic OAuth/chat/model/consent; one isolated Action/job. Waiting → Open votes 2:1 → Closed/winner → active challenge/countdown → expiry → persisted Skipped result → Waiting. Reload Idle and no replay. |
| USER_OBSERVED | Owner's login completion is attributed to the user; agent subsequently observed the authenticated UI in the earlier IAB session. No new user OBS observation was requested or counted. |
| NOT_RUN | New real Twitch messages/votes/model/Action, actual OBS controls, OBS uninstallation, native desktop capture, MP4 final acceptance, streaming, upload, deployment and submission. |

The earlier OBS Admin inspection belongs to the superseded task and remains in its
historical report. `COMPUTER_USE=NOT_USED` below describes the replacement OBS-free
task, not that earlier inspection.

## Exported files and content inspection

Files remain local and ignored by Git. Paths below are repository-relative and
exist; screenshots not archived as original files are not assigned invented paths.

| Recording | File / integrity |
| --- | --- |
| Actual IAB Waiting | `.artifacts/phase45-browser/iab-real/crowdquest-iab-waiting-73s.webm`; 16,074,845 bytes; SHA256 `068449c120c27889e8f613051646babf4f2989cd19f02aae27bcf1d5d918c887`. Original browser download also retained. |
| Final synthetic full chain | `.artifacts/phase45-browser/qualified/synthetic-crowdquest-20261028075209-d88fb997.webm`; 7,345,796 bytes; SHA256 `bf756dd29d5d302ceb094b212dbd385706f0f502346410a79844b5e95d95cae4`. |

Final synthetic file: 1920×1080, 31.9265 s container duration, 32.00 s decoded end,
813 decoded frames, average **25.41 FPS**. Full FFmpeg 7.1 decode with `-xerror`
returned 0, with no unknown-size Cluster warning. Browser playback readyState 4 and
no media error. Preview-versus-recorded-frame mean absolute RGB error was 2.2797/255
(threshold 6); both use the same Canvas rather than separately drawn graphics.

The actual IAB file decodes all 2149 frames, decoded end 73.43 s (~29.27 FPS), and its
2-second decoded frame was visually inspected. It predates the final metadata fix:
an unknown-size Cluster nested in a finite parent causes a nonfatal FFmpeg warning.
The original was not patched or substituted. The final fix parses metadata only
before the first Cluster, preserves the encoded media tail, and was independently
qualified by the new Chromium recording. Its final IAB rerun remains unverified.

Visual inspection used **decoded video frames**, not just live screenshots:

- IAB: `iab-real/decoded-iab-waiting.png` — actual Waiting presentation.
- Final synthetic: `qualified/decoded-voting.png` at 4 s — 2:1 totals/countdown;
  `decoded-challenge.png` at 12 s and `decoded-second-21.png` — same title/description,
  diminishing countdown; `decoded-second-26.png` / `28.png` — persisted Skipped result.
- A 24-second sample (`decoded-outcome.png`, retained filename) actually shows
  **Challenge expired**, not a result. It is not presented as result evidence.
- Actual Chromium screenshots `qualified/synthetic-*-preview.png` and
  `synthetic-studio.png` show the Canvas/layout; all fixture footage is watermarked
  SYNTHETIC TEST. Historical images and prior recordings were preserved.

30 FPS is a target. It was not continuously achieved, and no constant-30-FPS claim
is made. The current IAB/Chromium evidence supports usable silent local WebM; it is
not an audio, MP4, game-capture, real Twitch demo or competition-video acceptance.

## Regression and safety gates

| Gate | Measured result |
| --- | --- |
| Backend | **225 passed**, 109.92 s, exit 0; one existing Starlette/httpx deprecation warning. Temporary fixtures only. |
| Frontend | **49 passed**, six files; TypeScript, strict lint and Prettier pass. |
| Browser regression | All **five** actual Chromium suites pass: Phase 1, Phase 3 + worker, Phase 4 voting/outcome, optional OBS Admin fixture, Studio recording/playback. All external input/consent is synthetic. |
| Recorder | Unsupported MIME/fallback, safe filename validation, double start/stop, stop failure, interrupted/failed playback, one Canvas, final media decoding, bounded duration/size/file-count implementation and reload Idle. Bounds are not a guarantee against process/OS memory exhaustion. |
| Admin security | Loopback socket peer including forwarded-header spoof denial; exact Host/Origin/Fetch Metadata; owner/session/CSRF; no upload/path-write/stream/generic RPC; no credentials in Canvas or status. Optional OBS has its own auth/allowlist and remains disabled. |
| AIG | Installed 0.3.0 at `bb8e8fb1234128613a750bee17967b225072bb14`; 45 installed source RECORD hashes and 12,127-byte upstream instruction prefix verified. Single tool, five-second default, separate gates, Unknown/no retry and durable receipt tests pass. No core source changes. |
| Twitch/voting/outcome | Existing narrow scope, identity/delivery deduplication, concurrency/deadline/winner binding, outcome idempotency and no-replay regression pass. Historical real evidence remains separately attributed. |
| Dependencies | Locked uv/npm, `uv pip check`, Ruff pass; npm audit zero; pip-audit zero known registry-package vulnerabilities. Git-only AIG is skipped by pip-audit and checked separately by pin/RECORD verification; this is not a comprehensive security certification. |
| OBS-free installation | Core-only environment has no `obsws_python`; app import and actual loopback backend startup pass without OBS SDK, password or WebSocket. Optional SDK remains in development tests/`obs` extra only. |

New backend tests exercise owner/peer/CSRF separation, idempotent display connection,
authoritative voting and existing durable ACK/no-replay behavior. Recorder unit
tests use explicitly mocked media; real media proof comes from IAB/Chromium and
the downloaded files. Synthetic consent does not stand in for human approval.

## Real data preservation and service recovery

Before the initial safe activation, five real SQLite databases were backed up using
SQLite online backup, integrity checked and logically compared with their originals.
After the interruption, port 8000 was no longer listening. Read-only comparison to
those backups found all candidate/vote/Plan/Action/receipt/render/outcome rows intact;
only the expected worker leader lease differed. Counts included five intake
candidates, one voting round/vote, two succeeded Actions/attempts, two admitted jobs,
two expired renders and one ended outcome. No pending Action or unrendered job existed.

A **new** set of five verified backups was created before safe startup. No live
service was stopped, no store was cleared/restored, no credentials were overwritten,
and no Action command was issued. Existing private profile and narrow read scope
were retained. Backend and separate worker started from a core-only environment;
HTTP Studio returned 200. Owner cookies are in-memory and a fresh login may be needed
after startup. Current authenticated EventSub/UI status cannot be re-observed while
IAB host access is unavailable; earlier session evidence is not substituted for it.
Final read-only audit reconfirmed all five integrity checks, unchanged protected
rows, a fresh worker lease, the exact isolated frontend being served and empty
backend/worker error logs. These checks do not prove current authenticated EventSub.

Private backups/operational logs stay outside Git. Qualification contains only
redacted counts/integrity facts. Normal worker lease maintenance is not represented
as an unchanged byte-for-byte database file; protected historical rows are compared
independently. The original `frontend/dist`, old environments and prior review ZIP
were not replaced. New frontend assets were built in the ignored isolated directory.

## Delivery and remaining work

Scoped normal main delivery is authorized for this replacement task. Local software
gates pass; unavailable IAB final acceptance remains openly PARTIAL, as permitted by
the task's fallback instructions. Implementation CI must be verified for its exact
commit; the final documentation receipt's CI must be checked separately. No baseline
CI is substituted. Delivery details are recorded after the commit is known.

To finish the remaining real-browser gate when IAB host access returns: open `/`,
personally complete owner sign-in if required (only user:read:chat), then open
`/broadcast-studio`. Check Waiting and status, record 30–180 seconds, stop, download,
play and reload after saving. No new real challenge, OBS pairing or historical replay
is needed. Fresh real Twitch-to-Studio challenge coverage needs separate permission.

OBS is no longer a required CrowdQuest dependency. Actual uninstallation was NOT_RUN
and remains the user's decision. Full final-build IAB/real demo acceptance and
competition eligibility are incomplete; Phase 5 readiness is PARTIAL. The demo
runbook is prepared, not executed or submitted.

## Required status fields (report cutoff before remote CI)

```text
PROJECT=CrowdQuest AI
PHASE=4.5_OBS_FREE
BASELINE_REVIEW=PASS
EXISTING_WORK_PRESERVED=PASS
BROADCAST_STUDIO_IMPLEMENTATION=PASS
OBS_FREE_STARTUP=PASS_AGENT_VERIFIED_CORE_ONLY
OBS_FREE_PREVIEW=PASS_EARLIER_IAB_AND_FINAL_CHROMIUM
SCENE_MANAGEMENT=PASS_SYNTHETIC_TEST
VOTING_VISUALIZATION=PASS_SYNTHETIC_TEST
CHALLENGE_VISUALIZATION=PASS_SYNTHETIC_TEST
OUTCOME_VISUALIZATION=PASS_SYNTHETIC_TEST
LOCAL_RECORDING=PASS_REAL_CANVAS
VIDEO_EXPORT=PASS_WEBM
REAL_VIDEO_PLAYBACK=PASS_IAB_AND_CHROMIUM_FILES
VIDEO_RESOLUTION=1920x1080
VIDEO_DURATION=73.286699s_IAB__31.9265s_FINAL_CHROMIUM
IAB_ACCESS=BLOCKED_ON_RESUME_HOST_UNAVAILABLE
IAB_REAL_ACCEPTANCE=PARTIAL_EARLIER_WAITING_RECORDING_ONLY
CHROMIUM_E2E=PASS_5_SUITES
ADMIN_SECURITY=PASS_SCOPED_TESTS
TWITCH_REGRESSION=PASS_SYNTHETIC_TEST
AIG_SAFETY_REGRESSION=PASS_SYNTHETIC_TEST
OUTCOME_NO_REPLAY=PASS_SYNTHETIC_TEST
OBS_REQUIRED=NO
OBS_OPTIONAL_ADAPTER=PRESERVED_DISABLED_BY_DEFAULT
OBS_UNINSTALL_READINESS=PARTIAL_CORE_INDEPENDENT_UNINSTALL_NOT_RUN
COMPUTER_USE=NOT_USED
NATIVE_DESKTOP_AUTOMATION=NOT_USED
BACKEND_TESTS=225_PASS
FRONTEND_TESTS=49_PASS
SECURITY_CHECKS=PASS_SCOPED_LOCAL
DEPENDENCY_CHECKS=PASS_PIN_LOCK_RECORD_AND_AUDITS
GITHUB_CI=NOT_RUN_AT_REPORT_CUTOFF
GIT_FINAL_HEAD=PENDING_DELIVERY_RECEIPT
WORKTREE_STATUS=SCOPED_CHANGES_BEFORE_COMMIT
PHASE45_FINAL_STATUS=PARTIAL
PHASE5_READINESS=PARTIAL_RUNBOOK_PREPARED
REAL_TWITCH_ACCEPTANCE=NOT_RUN_THIS_PHASE
```

Final source HEAD, remote equality, CI URL/conclusion and worktree status are reported
after delivery; a commit cannot embed its own hash self-referentially. These cutoff
fields are updated by the subsequent implementation CI receipt without changing the
evidence classes or upgrading overall acceptance.
