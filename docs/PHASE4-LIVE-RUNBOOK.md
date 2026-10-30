# Phase 4 real acceptance runbook

**Historical Phase 4 procedure, prepared 2026-10-27.** Its OBS setup and observations are scoped to the earlier Phase 4 acceptance plan. The current primary presentation is OBS-free Broadcast Studio; use the Phase 5 runbook for a future, separately authorized demo. This historical runbook does not authorize live work.

Prepared 2026-10-27 for ChatGPT Desktop Work and the channel owner.
**NOT_RUN. A separate live-session authorization is required.** Current authorization
covers local development, temporary fixtures and Git/CI only. Preserve the running
Phase 3 instance, its frontend assets, private databases, credentials and paired OBS.

## Preparation and controlled activation

1. Record exact Git SHA and its own successful CI run. Confirm the real listener and
   worker identities read-only; do not reuse a PID from a previous report.
2. With separate owner authorization, use SQLite's online backup API for real intake,
   gate, product, admission and rendering stores; run source/backup integrity and
   logical comparison. Preserve private scope/binding/capabilities, receipt history,
   terminal Unknown records and all credential values. Never reset a real profile.
3. Inspect existing OAuth via Twitch validation without printing the token. Require
   configured owner miku_wwl and scopes exactly `[user:read:chat]`. Extra scope, unknown
   identity or uncertain token state is a blocker. Normal refresh is not new OAuth.
4. Only after separate permission, gracefully stop the verified CrowdQuest backend
   and its worker; load the new source/build with the existing private profile, then
   start backend and separate worker. Recheck database integrity and live EventSub
   session_welcome, enabled matching channel.chat.message subscription and keepalives.
   Dashboard Connected alone is insufficient. New voting tables and a private keyed
   voter identity are additive; keep the new .voting.key with private backups.
5. Open http://localhost:8000. If owner login expired, pause for the user to complete
   it personally with the exact existing scope. In OBS inspect CrowdQuest Demo /
   CrowdQuest Overlay: http://localhost:8000/overlay, 1280x720. Preserve pairing when
   valid; if a new pairing is required, pause for the owner. Do not show/copy its code
   into chat, logs, screenshots or public artifacts. Wait for Ready.

## One genuine voting-to-challenge session

6. The owner/viewers send two distinct genuine suggestions, for example:
   `!quest Beat the next boss without healing` and
   `!quest Survive for 60 seconds using only basic attacks`.
   An agent must not send them under the present authorization. Confirm exactly two
   new candidate correlations, source twitch_eventsub, and durable dedup results.
7. Owner shortlists these two, chooses 30 seconds and creates Draft. Review the two
   frozen texts, then explicitly Start voting. Observe both cards/instructions,
   countdown and zero totals in actual OBS. Overlay access must remain read-only.
8. Genuine viewers send `!vote 1` or `!vote 2`. Record actual accepted voter count;
   never invent a crowd or use two votes from one account as two viewers. With only
   one available account, one unique vote can prove the minimal live path; mark
   multi-viewer live participation NOT_RUN. Repeated delivery/voter tests have separate
   synthetic evidence. Observe matching server/Dashboard and actual OBS totals.
9. Let the server deadline close the round, or explicitly Close voting now. Inspect
   persisted Closed state and totals. Equal totals, including 0:0, require a separate
   owner choice; do not fabricate a majority. Votes after closure must be rejected.
10. Click Generate winning Plan once. Confirm exact winner/candidate binding,
    REAL_MODEL/local phi4-mini provenance, all four bounded fields and current Run
    version. A failed model call is not a successful live model gate; no silent retry
    or manual draft may impersonate it. Show the complete Plan to the owner.
11. Obtain exact current Plan Approval. Click only after explicit user approval.
    Verify Approved/current version; then Admit approved Action and verify Pending.
12. Show the precise admitted Action, payload, channel and version. Obtain independent
    Authorization, click Authorize once and verify Authorized. Obtain explicit Execute
    consent for that same Action, then click Execute exactly once. A user may explicitly
    authorize the remaining operations together for this exact unchanged Action.
13. Require durable AIG Succeeded and matching admission receipt; check worker/render
    state separately. Record BROWSER_ACK independently from actual OBS. Raise the real
    OBS window and visually inspect title, description, difficulty, decreasing timer
    and Chosen by Chat badge. Never infer gameplay compliance.
14. Either observe natural expiry or have the owner choose Completed/Failed/Skipped.
    The latter is OWNER_REPORTED; inspect its immutable Action/receipt linkage and
    brief result display. It must not change AIG Succeeded or create another job.
    Wait for the result to end and return to waiting. A second real challenge solely
    to test the other branch needs separate specific authorization.
15. Refresh OBS Browser Source. Confirm no challenge/result replay or countdown reset,
    unchanged Action/job/render counts, terminal outcome if chosen and intact receipts.
    Do not start streaming/recording, rerun Execute or create replacement Actions.

## Stop and evidence rules

Unknown, unconfirmed execution, stale versions, identity/scope mismatch, storage failure
or an uncertain worker dispatch stops progression. Preserve logs/state. Never retry
Execute, reset terminal rows or reconcile Unknown into success. Safe checks are read-only.

Archive a redacted report with dated SHA, CI, session ID, hashed candidate/Run/Action/
receipt/render correlations, vote totals and result. Capture actual OBS screenshots
without pairing codes, cookies, tokens, raw chat history or private user IDs. Keep
original image files privately, publish only reviewed copies if authorized. Do not
fabricate a local archive if only session observations are available.

Classify each item as REAL_TWITCH, REAL_MODEL, HUMAN_APPROVED, AIG_EXECUTED, BROWSER_ACK,
REAL_OBS_OBSERVED or SYNTHETIC_TEST. A browser screenshot is not an actual OBS screenshot.
Scope the final PASS to the exact completed session and mark missing branches NOT_RUN.
