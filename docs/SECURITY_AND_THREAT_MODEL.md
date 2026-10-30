# Security and threat model

Current context reviewed 2026-10-30: the Phase 1/3 real Twitch/OBS reports remain
historical and scoped; Phase 4 overall is PARTIAL. Clear Demo History advances only
owner-scoped dashboard watermarks and preserves durable business/audit state. New
post-clear real Twitch-to-Studio acceptance is NOT_RUN. OBS references below describe
historical evidence or optional legacy compatibility, not a primary requirement. This
is not a penetration test or production/multi-user security certification.

Assets: exact consent, execution authority, channel identity, credentials,
effect/receipt integrity, availability, viewer privacy and broadcast content.
Trust boundaries: public chat → intake; model → validator; dashboard → authenticated
backend; backend → AIG public API; executor → consumer queue; worker → read-only overlay.
A trusted local operator/OS is assumed. AIG does not sandbox malicious host Python or
provide production user authentication, distributed HA or remote exactly-once effects.

| Threat | Required control | Verification phase |
| --- | --- | --- |
| Malicious Twitch text / XSS / abusive content | Bound Unicode/byte sizes; normalize command parsing; render as text; reject control/unsafe content; no HTML, executable URLs or game-control semantics | 1 parser/browser tests; 3 content tests |
| Prompt injection | Isolate suggestion as data; trusted domain prompt and schema; reject authority fields, extra steps/tools/targets; deterministic semantic validation plus streamer review | 2 negative Plans; 3 real-provider adversarial cases |
| Unauthorized approval / CSRF / session theft | Validate Twitch channel owner; server session, HttpOnly/SameSite cookie, CSRF and origin checks; reject viewer/overlay requests; require exact Run/version | 2 API tests; 3 real human UI |
| Token or source exposure | Separate credential roles, private storage outside checkout, redacted logs, no tokens in URLs/overlay/model; secret review before commit/video | Each phase |
| Replayed EventSub delivery | Check configured session, type/version/status/channel and timestamps; durable unique delivery and channel/message IDs; reject unexpected shared-chat source | 1 fixtures plus real chat |
| Duplicate chat/commands/Actions | Candidate and command IDs are distinct; AIG owns execution idempotency/effect key; consumer queue binds unique effect and immutable payload | 1 intake; 2 SQLite tests |
| Excessive volume / cost | Early length caps; per-viewer/channel/global limits; finite queues; one generation per accepted candidate; bounded provider deadlines; no fallback/retry loop | 1 overload tests; 3 provider tests |
| Stale or altered approval | Show exact current Plan; optimistic versions; edits regenerate and require review; reject stale Run/Action commands | 2 stale/version tests |
| Conflicting actions / worker races | AIG CAS/owner fencing; one active channel job; transactional worker claim and persistent dispatch marker; bounded SQLite lock waits | 2 process/concurrency tests |
| Ambiguous external effect | Terminal AIG Unknown; quarantine job until matching durable success; rendering Unknown tracked separately; never reset or replay ambiguous dispatch | 2 crash/lost-ack tests; 3 disconnect tests |
| OAuth interception / reconnect target abuse | Exact registered redirect and state, backend code exchange, TLS verification; restrict Twitch reconnect destinations to reviewed official hosts | 1 auth/reconnect tests |
| Overlay credential misuse | Separate read-only channel credential; authenticate subscription; restrict origins; redact query/cookie values in logs; rotate on disclosure | 1 browser/API tests; 3 OBS test |

## Proposed limits and retained state

Before model generation: max suggestion 280 characters and 1120 UTF-8 bytes; proposed
viewer limit one candidate per 30 seconds, channel 10/minute, global 20/minute, queue
50 waiting candidates. Values are initial product defaults, not Twitch platform quotas.
Drop/reject over-limit work with an audit reason rather than silently buffering forever.
Retain dedup IDs for the demo/submission evidence period; do not expire them while a
candidate, Run, Action or associated job can remain actionable. Reject events older
than a reviewed freshness window (initial proposal 10 minutes) with a documented
clock-skew policy. Never imply disconnected Twitch events are recoverable.

The overlay never receives raw viewer prompts, source files, runtime bearer tokens or
receipt-store paths. Dashboard audit displays bounded, redacted metadata. Store only
required viewer identifiers/text; agree retention/deletion before a real demo. Remove
public-facing content only through an explicit reviewed product path, not a new tool.

## Failure response and residual risks

Disable intake on invalid/revoked authentication; end related sessions. Fail closed if
dedup, identity or ownership storage is unavailable. Preserve durable evidence and
surface Unknown without a retry button that creates equivalent replacement Actions.
A receipt is a queue admission receipt until a separate rendering acknowledgement
exists. Never infer success from an HTTP response, WebSocket send or screenshot alone.

Residual risks: a human may approve harmful text; AI may generate an unsuitable
challenge; local malware can read secrets; an OBS client may lie about acknowledgement;
clock/network failures can lose events; delivery cannot promise exactly-once remote
display. MVP mitigation is one controlled channel/host, explicit review, bounded text,
no arbitrary mutations and measured live evidence. Do not claim production hardening.

Security review in Phase 0 checks design, provenance, staged files and ignore behavior;
it is not penetration testing, a dependency CVE audit, or validation of implemented controls.

## Implemented Phase 3 boundaries

Only the already-reviewed local phi4-mini:latest is enabled. Model input contains no
identity/credential/policy authority; schema validation and a host-owned one-step Plan
scaffold protect those fields. One attempt, bounded response/time and fixed loopback
transport prevent silent provider escalation. Failed generation requires an explicit
OFFLINE_MANUAL draft, never a falsely labelled real-model fallback.

Current candidate/Run fencing makes prior review stale after edits. An admitted Action
blocks replacement drafts for that candidate. The authenticated UI makes Approval,
admission, Authorization and Execution separate requests. Unknown has no retry control.

Worker credential, server incarnation, worker UUID, monotonic lease and epoch protect
publication; a unique active-channel index and pre-delivery marker constrain races.
Public durable AIG success and exact receipt/payload are checked before publication.
Issued overlay deliveries are not replayed after reload/reconnect. Missing render ack,
post-dispatch interruption or restart stays rendering Unknown. Browser telemetry cannot
grant Action authority or prove actual OBS visibility. All stores remain private.

## Phase 4 reviewed controls

Strict !vote parsing and the existing session/channel/subscription/timestamp validation
precede transactional EventSub dedup and keyed per-round viewer uniqueness. Server-only
totals/deadlines, CAS commands, one-active-round uniqueness, per-second vote limits and
finite history caps bound load. Reject votes before opening/after closure, changed
message IDs, shared-chat sources, unsafe commands and unavailable identity state.
Missing/replaced HMAC key fails closed; retain it privately with backups. Owner audit
is scoped to the configured channel; overlay responses omit voter and candidate IDs.

Winner selection is never consent. Explicit winner binding is immutable in consumer
provenance, while AIG still validates the same exact four arguments and independent
Approval/Authorization. No new viewer/model-controlled tool registration exists.

Owner outcomes require a confirmed successful Action, exact admission receipt/job/
payload and acknowledged rendering; missing/Unknown results cannot be relabelled as
Completed. One terminal owner report and bounded issued display per overlay survive
restarts without a second effect. Gameplay is not independently verified. Text remains
React-escaped; native meter values avoid unsafe inline style under the existing CSP.

Voting history is bounded to 500 rounds; original intake dedup capacity remains 10,000
deliveries and vote history has an additional 20,000-row cap. These are deliberate demo
limits, not unlimited production capacity. Reaching a cap rejects intake, never prunes
identity/dedup history silently. No live migration or real store has been touched by tests.
