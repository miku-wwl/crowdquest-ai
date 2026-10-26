# Decision log

All decisions dated 2026-10-26. Implementation remains deferred unless stated.

| ID | Decision | Reason / consequence |
| --- | --- | --- |
| D01 | Preserve existing public README-only repository/history | Inspection found the requested target already created during the period; no recreation, fork, import or force push. |
| D02 | Phase 0 only | Documents, dependency/provenance verifier and minimal CI; no Twitch/AI/application scaffold. |
| D03 | Install complete authoritative consumer instructions | Exact upstream source commit/blob and bytes preserved, with separate CrowdQuest suffix. Upstream safety takes precedence. |
| D04 | AIG v0.3.0 full commit pin; Python 3.13; uv.lock | Reproducible installed public dependency; no moving main dependency, core patch or adjacent checkout. |
| D05 | Single local channel/owner, FastAPI + SQLite | Narrow demo scope consistent with AIG single-owner limits; not multi-tenant production service. |
| D06 | React/TypeScript dashboard and overlay, tooling deferred | No empty Node scaffold in Phase 0; add exact frontend lock during Phase 1. |
| D07 | EventSub WebSocket + user:read:chat | Local installed-bot path; no webhook HMAC confusion or unnecessary chat-write/moderation scopes. |
| D08 | OBS Browser Source with read-only app updates | Avoid Extension review latency, game mutation and arbitrary OBS control. |
| D09 | One trusted enqueue tool and five-second budget | Admit a durable local job; longer render lifecycle belongs to worker. No extended profile required. |
| D10 | Independent Action Authorization after exact human Approval | Human review never dispatches/authorizes by itself; local AIG bearer is not user login. |
| D11 | Separate admission and rendering records | AIG success proves admission; matching durable success releases job; Unknown quarantines it. |
| D12 | No uncertain effect/render replay | Preserve receipts/fences and terminal ambiguity; do not promise remote exactly-once execution. |
| D13 | Consumer ModelProvider selected in Phase 3 | Bundled service-demo prompt is unsuitable; no provider calls or credentials in Phase 0. |
| D14 | MIT with explicit AIG attribution | License permission does not establish competition eligibility for own prior runtime. |
| D15 | Rules Pacific deadline controls over FAQ UTC example | Verified Nov 3 11:00 NZDT; note discrepancy and retain early submission buffer. |
| D16 | Eligibility PARTIAL; own-runtime reuse UNVERIFIED | Organizer question prepared; no contact authorized. Entrant checks and answer needed before submission. |
| D17 | Baseline CI checks only what exists | Locked install, provenance/API/document checks and whitespace; no placeholder product tests or live claims. |
| D18 | Secrets/private state outside source | Separate Twitch/provider/runtime/dashboard/overlay identities; no raw Codex transcripts committed. |
| D19 | Subsequent user instruction authorizes Phase 1 only | Implement read-only OAuth/EventSub, durable intake and owner-selected development preview; no AI/AIG execution. Live Twitch/OBS gates remain outstanding. |
| D20 | HTTP polling and owner-paired overlay cookie | Small local Phase 1 transport; no credential in OBS URL, no automatic display/replay, separate read-only role. |

Revisit D05/D07 only with a reviewed hosting change; D09 only through upstream's
reviewed budget mechanism; D13 only with provider-specific validation and live evidence.
No deadline pressure permits weakening the root AGENTS safety contract.
