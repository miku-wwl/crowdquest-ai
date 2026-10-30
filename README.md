# CrowdQuest AI

**Your Chat Becomes the Game Director.**

CrowdQuest turns Twitch chat suggestions into bounded community votes and
streamer-reviewed challenges. The streamer keeps control: a vote never approves a
Plan, and Plan approval is separate from Action admission, execution authorization
and execution.

## Current status — 2026-10-30

- The genuine Phase 3 Twitch → local model → owner review → AIG Action → admission
  receipt → OBS session passed for one Action. This is historical OBS evidence, not
  evidence of a new Studio session. See the [Phase 3 real acceptance record](docs/PHASE3-REAL-ACCEPTANCE.md).
- Phase 4 local voting, outcomes and broadcast UI qualification passed;
  **PHASE4_OVERALL remains PARTIAL**. Evidence involved one real unique voter, not
  multi-viewer participation. See the [Phase 4 report](docs/PHASE4-ACCEPTANCE.md).
- **Broadcast Studio is the primary display and silent local recording surface.**
  Phase 4.5.5 delivery/ACK changes passed CI and synthetic qualification; native
  background-tab retest remains pending. See the [Studio guide](docs/PHASE45-BROADCAST-STUDIO.md), [Phase 4.5 acceptance](docs/PHASE45-BROADCAST-STUDIO-ACCEPTANCE.md), and
  [delivery/ACK report](docs/PHASE455-STUDIO-DELIVERY-ACK-RELIABILITY.md).
- Phase 4.5.6 Clear Demo History is committed and CI-qualified. A user-provided
  screenshot showed the clean view on 2026-10-30. Read-only database evidence
  confirmed generation 1, zero visible old candidates/rounds, and all 9 earlier
  candidates and 4 voting rounds still stored. The login/click was not independently
  observed; a new real Twitch-to-Studio end-to-end retest is **NOT_RUN**. See the
  [Phase 4.5.6 note](docs/PHASE456-DASHBOARD-HISTORY-CLEANUP.md).

These updates do not upgrade historical partial results. No video has been recorded or uploaded for submission, and competition eligibility questions remain unresolved.

## Product flow and boundaries

Twitch EventSub chat → validated suggestion → server-owned one-viewer-one-vote round → local model Plan → exact owner review → separate Approve / Admit / Authorize / Execute gates → durable admission receipt → fenced worker → Broadcast Studio Canvas and display acknowledgement. The owner reports the actual external challenge outcome; CrowdQuest does not observe or verify gameplay.

An AIG Action marked `Succeeded` and its admission receipt do not prove that a browser displayed the challenge. Worker delivery, browser ACK, visible Canvas content and an owner-reported outcome are separate evidence. Unknown and expired records are terminal and are never replayed.

OBS is **optional legacy compatibility**. It is not required to run the current product, display a challenge or record the Phase 5 demo. See the [optional OBS Admin guide](docs/PHASE45-OBS-ADMIN.md) only when deliberately using that adapter.

## Local Windows setup

Requirements: Windows, Python 3.13, `uv`, and Node.js 22.12 or later. Local state and credentials remain outside Git in `%LOCALAPPDATA%\CrowdQuestAI`; secrets use Windows Credential Manager.

Install the locked Python and frontend dependencies and build the frontend:

```powershell
uv sync --locked --python 3.13
npm --prefix frontend ci
npm --prefix frontend run build
```

For a first-time development-preview setup, run `uv run python -m crowdquest.setup`, then `uv run python -m crowdquest`. Sign in as the configured channel owner. OAuth requests only `user:read:chat`; the app does not send chat messages or perform moderation. This default development startup does not compose the Phase 3 AIG workflow.

For the full local single-channel workflow, follow the [Phase 3 operator runbook](docs/PHASE3-RUNBOOK.md). It explains how to validate the existing private profile and owner identity. Do not provision over an existing profile. After verifying that any predecessor is stopped, start the backend and the separate worker in two terminals:

```powershell
$cqProfile = Join-Path $env:LOCALAPPDATA 'CrowdQuestAI\phase3'
uv run python -m crowdquest --phase3-directory $cqProfile --phase3-owner-id $cqOwnerId --predecessor-stopped
```

```powershell
uv run python -m crowdquest.worker --origin http://localhost:8000 --token-file (Join-Path $cqProfile 'worker-token')
```

Use the runbook’s read-only owner-ID validation procedure to set `$cqOwnerId`; never place OAuth tokens or secrets in command arguments. The `--predecessor-stopped` flag is an operator attestation after verifying shutdown, not a lock bypass.

Open the [Dashboard](http://localhost:8000) and the primary [Broadcast Studio](http://localhost:8000/broadcast-studio). Confirm the owner login, EventSub welcome and matching enabled chat subscription, fresh keepalives, and the separate Worker-ready state. Dashboard “Connected” alone does not prove all three.

## Clear Demo History

After owner sign-in, click **Clear Demo History** in Audience inbox and confirm: “Hide previous demo records and start a clean view? Historical audit records will be preserved.” This advances persistent `dashboard_sessions` display watermarks. It hides earlier candidates and voting rounds from the current dashboard; it does **not** delete candidates, votes, plans, Actions, receipts, renders, ACKs, UNKNOWN records or EventSub deduplication history. Refreshing keeps the clean view. New Twitch suggestions received after the watermark appear in the current view. The operation is owner-authenticated and protected by Origin/CSRF checks; it refuses while workflow or delivery work is active.

## Broadcast Studio and recording

Use **http://localhost:8000/broadcast-studio** as the primary presentation. Its Canvas shows the live product state. The optional native WebM recorder captures only that Canvas, silently; it does not capture Twitch chat, the Dashboard or Codex. Keep the Studio tab visible, download the file before closing, and verify playback. Background-tab transitions can interrupt capture; see the [Studio guide](docs/PHASE45-BROADCAST-STUDIO.md) for limits.

For the eventual three-tab demo, use Windows Snipping Tool to record the desktop region containing Twitch, Dashboard and Studio, with irrelevant private content redacted. The Studio WebM is a separate optional Canvas-only check, not a replacement for the multi-tab footage. The [Phase 5 runbook](docs/PHASE5-DEMO-RUNBOOK.md) and [2:45 English storyboard](docs/PHASE5-DEMO-STORYBOARD.md) are plans, not evidence that a final video exists.

## Competition status

The [official rules](https://twitchcon-codex.devpost.com/rules) and [Devpost FAQ/resources](https://twitchcon-codex.devpost.com/resources) were rechecked on 2026-10-30. The rules deadline is November 2, 2026 at 2:00 PM Pacific, which is November 3 at 11:00 AM NZDT. The FAQ says YouTube Unlisted is acceptable; Private videos cannot be viewed by judges. A submission still requires the complete form and an observed Submitted confirmation.

Agentic Intent Gate is a pre-existing MIT runtime pinned to commit `bb8e8fb1234128613a750bee17967b225072bb14`. The entrant’s eligibility to reuse their own pre-existing runtime, personal eligibility and registration are **UNVERIFIED**. Attribution is not organizer approval. See [originality and reuse](docs/ORIGINALITY_AND_REUSE.md) and the [current submission checklist](docs/PHASE5-SUBMISSION-CHECKLIST.md). No organizer contact, video upload or Devpost submission has been performed here.

## Project documents

- [Product requirements](docs/PRD.md) · [Architecture](docs/ARCHITECTURE.md) · [Security model](docs/SECURITY_AND_THREAT_MODEL.md)
- [AIG contract](docs/AIG_INTEGRATION.md) · [Twitch integration](docs/TWITCH_INTEGRATION.md) · [Phase plan](docs/PHASE_PLAN.md)
- [Acceptance criteria](docs/ACCEPTANCE_CRITERIA.md) · [Phase 4.5.5 delivery/ACK evidence](docs/PHASE455-STUDIO-DELIVERY-ACK-RELIABILITY.md) · [Phase 4.5.6 history-cleanup note](docs/PHASE456-DASHBOARD-HISTORY-CLEANUP.md)
- [Phase 5 demo runbook](docs/PHASE5-DEMO-RUNBOOK.md) · [Phase 5 storyboard](docs/PHASE5-DEMO-STORYBOARD.md) · [Phase 5 submission checklist](docs/PHASE5-SUBMISSION-CHECKLIST.md)
- [Historical submission rules review](docs/SUBMISSION_CHECKLIST.md) · [Third-party notices](docs/THIRD_PARTY_NOTICES.md) · [License](LICENSE)

Read [AGENTS.md](AGENTS.md) before development. It preserves the authoritative AIG consumer template and CrowdQuest safety boundaries.
