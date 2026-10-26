# Security and threat model

Status: design review only; controls are required for later implementation and are
not yet runtime-tested for future AI/AIG phases. Phase 1 OAuth/intake/CSRF/preview
controls now have synthetic backend and actual Chromium tests; real Twitch and OBS
remain unverified. Assets: exact consent, execution authority, channel identity,
credentials, effect/receipt integrity, availability, viewer privacy and broadcast content.

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
