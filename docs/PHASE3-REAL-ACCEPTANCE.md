# Phase 3 real end-to-end acceptance

Recorded 2026-10-27, Pacific/Auckland, from the completed 2026-10-26 Codex/desktop
session. Source: `369ec862465705225f8781dd867ecd23fdf90028`.
**PHASE3_REAL_E2E=PASS for the single explicitly authorized Action.**

This is a subsequent session evidence record, not a rewrite of the earlier local/CI
reports. No new live operation was performed to create this document.

| Gate | Evidence/class |
| --- | --- |
| OAuth | Existing owner login and exact user:read:chat validated; no extra scope. AGENT_VERIFIED with user-completed login. |
| Twitch ingestion | One genuine acceptance `!quest` message; Dashboard EventSub listening, Notifications 1 / Stored 1, fresh candidate. REAL_TWITCH / AGENT_VERIFIED. |
| Plan | REAL_MODEL, existing local phi4-mini:latest; title Survive Phase 3; description Survive 60 seconds without healing - Phase 3 acceptance; 60 seconds; Medium. REAL_MODEL / AGENT_VERIFIED. |
| Human review | User explicitly approved Plan version 4; the unchanged Plan then displayed Run version 5 after Approval. HUMAN_APPROVED. |
| Admission and authority | Same Action admitted; the user subsequently authorized both the independent Authorize operation and exactly one Execute operation for its precise payload. HUMAN_APPROVED / AGENT_VERIFIED. |
| AIG and receipt | Dashboard Succeeded; audit correlation 52da06c119af; receipt hash a180bbd5cb11, ELIGIBLE. AIG_EXECUTED / AGENT_VERIFIED_UI. |
| Worker and browser | RENDERED, one browser acknowledgement, then EXPIRED. BROWSER_ACK; this alone does not establish OBS visibility. |
| Actual OBS | Agent raised the OBS Studio native window and observed the matching title/description and countdown at 36s, then 8s. REAL_OBS_OBSERVED / AGENT_VERIFIED. |
| Expiry/reload | Actual OBS changed to Challenge expired. Refreshing its Browser Source did not replay it; Dashboard remained EXPIRED, one acknowledgement. AGENT_VERIFIED. |

The desktop screenshot observations are present in the session. No original PNG was
exported into this repository; no local image filename, hash or archive is invented.
**EVIDENCE_ARCHIVE=SESSION_ONLY.** The first native screenshot attempt showed another
foreground window; it was excluded, OBS was raised, and actual OBS images were then
observed. No browser ACK was substituted for those images.

This scoped PASS does not verify Phase 4 voting/outcomes, competition eligibility,
fresh-machine installation or universal exactly-once effects. Earlier synthetic reports
and earlier user-provided Phase 1 screenshots retain their original evidence classes.
Principal Codex build thread: `01a172e3-9804-73c2-b597-8c5df928a56c`.
