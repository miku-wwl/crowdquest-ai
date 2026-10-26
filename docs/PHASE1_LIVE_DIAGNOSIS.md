# Live EventSub diagnosis — 2026-10-26

Status: Phase 1 diagnosis in progress; no real chat acceptance is claimed yet.
User authorizes read-only chat for owned channel `miku_wwl`; no stream startup or chat writes.

## Actual observations before the fix

- Twitch `/oauth2/validate` returned HTTP 200; configured client and `miku_wwl`
  identity matched; granted scopes were exactly `user:read:chat`.
- GET EventSub subscriptions returned HTTP 200. Both condition IDs matched the
  validated owner. The active subscription was `channel.chat.message`, version 1.
- Twitch's retained subscription history records disconnects at **14:13:05** and
  **14:15:41 NZDT**, close to the user's two reported sends. This localizes the
  symptom to receiving/validating frames before intake; it does not prove a specific
  rejected payload because the original frames were not retained.
- Actual intake SQLite had 0 deliveries, messages and candidates, and no rejection
  counters. The prior receive loop swallowed exceptions and retained no diagnostic
  detail. Dashboard Connected alone was insufficient evidence.
- A real direct WebSocket welcome passed the existing welcome validator. With the
  first diagnostic build, the real app recorded a welcome, subscription HTTP 202,
  enabled identity checks and 17 consecutive heartbeats without a notification.

## Scoped fixes and diagnostic evidence

- Delivery IDs are opaque bounded strings. The former `[A-Za-z0-9_-]` constraint
  rejected Base64 padding/punctuation. Regression cases demonstrate that rejection
  and verify durable deduplication with the corrected exact opaque identity.
- RFC3339 timestamps accept explicit offsets; transport validation still requires
  exact WebSocket method/session identity while tolerating connection metadata.
- Invalid frames are rejected and counted without disconnecting a healthy stream.
- Private bounded structured logs record welcome, subscription HTTP status, keepalive,
  notification hash, intake result and safe exception classification. No raw frames,
  chat text, OAuth parameters, headers, tokens or exception input are logged.
- An authenticated API diagnostic reports actual socket/wait/heartbeat/subscription
  readiness; the UI distinguishes listening, notifications and stored candidates.

These are confirmed code/observability defects. Whether an opaque-ID rejection caused
the two historical losses remains unconfirmed until a fresh genuine notification is
observed. New diagnostics record a boolean identifying that legacy rejection condition.
No synthetic event is inserted into the real database and old notifications are not replayed.

Local regression: 69 backend tests and 7 frontend tests passed; one existing TestClient
deprecation warning remains. Chromium synthetic E2E is reported separately from live
Twitch. Phase 1 remains PARTIAL until new genuine intake, owner selection and actual
OBS rendering are observed. AIG pin and upstream instructions are unchanged.

After the final service restart, verify current socket waiting, a recent real heartbeat
and a matching enabled Twitch subscription before announcing EVENTSUB_READY=YES and
asking the user to send a fresh message. Do not infer readiness from dashboard text.
