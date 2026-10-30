# Twitch integration plan

The authenticated read-only `user:read:chat` EventSub integration and prior real
owner/chat intake evidence are recorded in Phase 1 reports. The Clear Demo History
view is screenshot-evidenced and its watermarks are read-only database-verified; the
login/click were not independently observed. A new post-clear real suggestion/vote-to-Studio retest remains NOT_RUN. OBS references in earlier acceptance reports describe
those original sessions; Broadcast Studio is now the primary presentation. Recheck
current Twitch documentation before changing scopes or running a live test.

## Authentication and transport

Use the installed/local chatbot pattern: a broadcaster User Access Token with
`user:read:chat`. Configure `condition.broadcaster_user_id` and `condition.user_id`
as the authenticated streamer for the one-channel MVP. No chat writes or moderation
permissions are needed. A future hosted/app-token architecture requires a separate
review of bot/channel scopes; do not copy that broader permission set into this MVP.
[Twitch authentication guide](https://dev.twitch.tv/docs/chat/authenticating/).

Register with exact redirect `http://localhost:8000/auth/twitch/callback`. Run
`uv run python -m crowdquest.setup` for local owner/client config and hidden Client
Secret input to Windows Credential Manager. No plaintext fallback. Use
an OAuth authorization-code flow with validated state; keep exchange/refresh secrets
on the backend. Validate token client, user, scopes and expiry at startup and hourly;
terminate affected sessions on revocation. Do not request tokens in chat or print them.
[Token validation](https://dev.twitch.tv/docs/authentication/validate-tokens/).

Connect to `wss://eventsub.wss.twitch.tv/ws`, receive session welcome, and use its ID
to create a `channel.chat.message`, version `1`, subscription with the user token.
WebSocket transport authenticates subscriptions with OAuth; webhook HMAC fields do
not apply. Dashboard/overlay updates use same-origin HTTP polling (2s/1s).
[Subscription reference](https://dev.twitch.tv/docs/eventsub/eventsub-subscription-types/#channel-chat-message).

## Session management

Subscribe within the welcome timeout (normally 10 seconds). Monitor advertised
keepalive timing and standard ping/pong. Handle Twitch reconnect URLs only after
validating the official destination and preserve subscription continuity as documented.
For an ordinary lost socket, reconnect and resubscribe; do not promise replay of
events lost during the gap. Handle revocation explicitly and expose disconnected state.
[WebSocket events](https://dev.twitch.tv/docs/eventsub/handling-websocket-events/).

## Intake design

Verify notification message type, subscription ID/type/version/status, expected
session/channel/user condition, event shape and timestamp. Use metadata.message_id
as delivery identity and `(broadcaster_user_id, event.message_id)` as chat identity.
Persist both atomically with candidate admission. Shared-chat events from a different
source channel are rejected in the MVP; duplicates never create a second candidate.
Chat parsing is bounded and deterministic; require `!quest` followed by nonempty text.
Normal chat, malformed/oversized commands and expired messages produce no proposal.

Apply per-viewer/channel/global rate limits and a finite candidate queue before any
model call. Keep limits separate from Twitch API quotas; handle API throttling without
repeating effects. Log reason codes and correlation IDs, with no OAuth headers or full
private event history. Implemented limits: suggestion 280 characters/1120 UTF-8 bytes;
command envelope 1120 characters; no control/format/surrogate characters; age 10 minutes
and future skew 30s. Viewer 1 accepted candidate/30s; channel 10/min; global 20/min;
pending queue 50; retained candidates 500; delivery identities 10,000. Capacity exhaustion
fails closed; no automatic dedup expiry/reset. Rejections are bounded reason counters.
Only required text/IDs and hashed viewer identity are retained; no raw event history.

Owner mutations require an HttpOnly SameSite session, CSRF token and exact Origin/Host.
Overlay pairing issues a separate read-only HttpOnly cookie, never a URL credential.
New overlay views start after the current revision; failure/refresh clears old content.
Previews expire after 60s and are not restored after restart.

## Phase 1 connectivity probe

The implemented EventSub adapter, durable intake store and development Browser Source
are independent of AIG. An authenticated streamer manually selects one validated
candidate for a **DEVELOPMENT PREVIEW — NOT APPROVED / NOT EXECUTED** display. Never
auto-publish arbitrary viewer suggestions. This probe uses no AI or AIG effects and
must be clearly isolated/removed when the production approval path arrives. It proves
connectivity and escaped rendering only, not Phase 2 authority or production safety.

Evidence: a genuine chat event's redacted IDs/time, one candidate after duplicate
delivery, same correlation displayed in a real browser/OBS view, and logs reviewed
for secrets. A fixture-only EventSub simulation is labeled synthetic and cannot pass
the live gate. See [PHASE1_EVIDENCE.md](PHASE1_EVIDENCE.md) for actual results and the
remaining user-led registration, consent, chat and OBS steps.
