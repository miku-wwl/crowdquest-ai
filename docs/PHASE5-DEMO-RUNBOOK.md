# Phase 5 — OBS-free demo runbook (prepared, not executed)

Prepared 2026-10-30. This document authorizes no new Twitch events, votes, Plans,
Actions, livestream, recording, upload, organizer contact or competition submission.
Historical Phase 4 overall acceptance remains PARTIAL. Phase 4.5.5 native
background-tab retest and the post-clear real Twitch-to-Studio end-to-end retest
remain pending. See the [Phase 4.5.5 report](PHASE455-STUDIO-DELIVERY-ACK-RELIABILITY.md),
[Phase 4.5.6 status](PHASE456-DASHBOARD-HISTORY-CLEANUP.md) and
[current submission checklist](PHASE5-SUBMISSION-CHECKLIST.md).

## Readiness record as of 2026-10-30

A user-provided screenshot showed the clean Clear Demo History view. Read-only SQLite
state independently confirmed display generation 1, zero candidates/rounds above the
watermarks, and nine candidate rows plus four voting rounds still stored. The screenshot
does not independently verify the owner's login or click sequence. The evidence shows
persistent display state, not a new Twitch suggestion, vote, Plan, Action or Studio
challenge. EventSub showed listening with zero notifications/stored new events.

Before any separately authorized capture:

1. Recheck the current Git SHA/CI, local listener and Worker status. Do not treat this
   dated note or an old process ID as current runtime proof.
2. Preserve the existing private profile, history and credentials. Never reprovision
   or clear databases. A service restart is outside this runbook; it requires separate
   authorization and the verified-backup/no-active-work procedure in the operator guide.
3. Sign in as the configured channel owner and verify only `user:read:chat`. Confirm
   EventSub welcome, matching enabled channel chat subscription and fresh keepalives;
   verify Worker readiness separately.
4. Refresh the Dashboard. Confirm the “Previous demo records are hidden” notice,
   zero old inbox entries, no old voting round and the waiting state. This is the
   expected clean display; it does not mean history was deleted.
5. Keep Broadcast Studio visible at `http://localhost:8000/broadcast-studio` and select
   Follow live state. OBS is optional legacy compatibility, not a required runtime or
   recording path.

## Bounded real-flow plan (requires fresh, explicit owner authorization)

- The real post-clear Twitch test is still **NOT_RUN**. Only after authorization, the
  owner/viewers may send two distinct fresh `!quest` suggestions. Verify their new
  candidate records and current Dashboard display; do not replay historical chat.
- Shortlist those two candidates, create one bounded voting round, and record actual
  vote totals. Evidence so far involved one real unique voter; do not claim
  multi-viewer participation. A single viewer cannot count as several voters.
- If separately authorized to continue beyond voting, generate one local-model Plan
  for the closed round’s exact winner. Show the exact Plan/version and its provenance.
  A failed inference is not a pass; no silent retry or manual draft may be called
  real-model output.
- Approval, Action admission, independent Authorization and Execute remain separate.
  Execute a new real Action only after fresh, exact owner consent; at most once. Never
  reset or replay an old `UNKNOWN`/`EXPIRED` record or substitute prior consent.
- Report the external challenge outcome truthfully. CrowdQuest does not observe or
  verify gameplay.

## Capture the three-tab product flow

Use **Windows Snipping Tool desktop-region recording** for the actual Twitch chat,
Dashboard and Broadcast Studio sequence. Arrange readable views; close unrelated
windows and redact personal or private content before capture. This is future recording
instruction only; no desktop recording was made during this documentation pass.

Studio’s native WebM is an optional independent check. It records the Canvas only,
with no chat, Dashboard, Codex UI, microphone or system audio. Keep that tab visible;
background-tab transitions can interrupt the recording. Download the WebM before
refresh/close and verify playback, dimensions, duration and any frame-rate limits.
It cannot replace three-tab footage.

Target a **2:45 edited English demo**, with a hard limit below 3:00. Use the
[storyboard](PHASE5-DEMO-STORYBOARD.md) as a timed shot plan, not proof that the shots
exist. Show actual Twitch functionality and actual Codex development evidence. Label
all fixture footage `SYNTHETIC TEST`; never present it as a real Twitch/model/consent
result. The principal development thread recorded for this project is
`01a172e3-9804-73d1-87d8-4e01f1f75043`.

## Claims and export review

Keep these separate in narration and captions:

- **AIG `Succeeded` / admission receipt:** the consumer executor durably admitted the
  overlay job; this alone does not show that a browser displayed it.
- **Worker/render state:** separate delivery lifecycle and fencing evidence.
- **Browser ACK:** a correlated browser acknowledgement; not proof of gameplay or a
  human seeing the stream.
- **Visible Canvas:** inspect the actual Studio Canvas in the captured footage.
- **Owner outcome:** a truthful owner report, not automatic gameplay recognition.

Record the actual challenge interval; label any measured time compression. Review the
final file for legibility, English narration/subtitles, duration, third-party media
permissions, redaction and correspondence to the actual take. Avoid third-party
trademarks and copyrighted music/footage without permission. Upload and submission
remain separate owner-authorized actions. Devpost’s [Official Rules](https://twitchcon-codex.devpost.com/rules)
and [FAQ](https://twitchcon-codex.devpost.com/resources) are linked in the checklist.
