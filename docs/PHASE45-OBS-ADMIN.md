# Phase 4.5 — Local OBS Admin

**Optional compatibility only.** The subsequent OBS-free task superseded this
setup/acceptance path. Normal application startup does not load the adapter or its
credentials. Use [Broadcast Studio](PHASE45-BROADCAST-STUDIO.md) for the primary
presentation/recording workflow; do not configure OBS merely to use CrowdQuest.
If deliberately enabling this adapter, install `uv sync --locked --extra obs` and
start the application with `--obs-admin` (or its separate OBS-only launcher).

The optional page is **http://localhost:8000/obs-admin**. It controls the installed
OBS Studio through its built-in authenticated obs-websocket v5 server. OBS continues
to encode, record and write media. CrowdQuest adds no media engine, external admin
service, stream controls or AIG tool.

## Architecture and boundaries

React uses same-origin HTTP → a separate local Admin session → a narrow FastAPI
adapter → `obsws-python==1.8.0` → `ws://127.0.0.1:4455` → installed OBS.
The adapter is independent of Plans, Run/Action approval, runtime capabilities,
queue admission, worker delivery and overlay credentials. The sole AIG tool remains
`enqueue_overlay_challenge/1`, installed AIG 0.3.0 remains pinned to
`bb8e8fb1234128613a750bee17967b225072bb14`, and its default budget remains five seconds.
No new Twitch permission, event, candidate, Plan or execution is needed for Admin.

Exactly these OBS requests are permitted internally:

| Reads | Explicit mutations |
| --- | --- |
| GetVersion, GetSceneList, GetCurrentProgramScene | SetCurrentProgramScene |
| GetRecordStatus, GetStreamStatus | StartRecord, StopRecord |
| GetInputSettings, GetSceneItemList | PressInputPropertiesButton (`refreshnocache` only) |

`GetStreamStatus` is observation only. If streaming is active, mutations are blocked;
the operator must stop the stream themselves. No streaming/output-toggle, vendor,
hotkey, source creation, settings write, filesystem download or arbitrary RPC/shell
endpoint exists. OBS Admin cannot show a new challenge through AIG.

## Private setup

1. Open OBS yourself. In **Tools → WebSocket Server Settings**, enable the built-in
   server, choose port 4455, and **keep password authentication enabled**. Security
   settings/password entry are user actions, never automated by this feature.
2. From the repository in your private terminal, run:

   ```powershell
   uv run --locked python -m crowdquest.obs_setup
   ```

   Enter the existing OBS WebSocket password, then a **different** Admin passphrase
   (16–256 characters) twice. Inputs are hidden. Only these two new credentials are
   saved in a separate Windows Credential Manager service derived from
   `%LOCALAPPDATA%/CrowdQuestAI/obs-admin`. Twitch/AIG credentials are never accessed
   by this setup. Do not paste passwords into chat, command arguments or reports.
3. A newly started CrowdQuest process loads the configuration and serves the page.
   Do not restart a working service with pending work merely to load Admin. Use a
   separately authorized safe activation window for a running full application.

Supported startup-only environment overrides: `OBS_WS_HOST=127.0.0.1`,
`OBS_WS_PORT=4455`, `OBS_WS_PASSWORD`, `OBS_ADMIN_PASSWORD`. Only the exact numeric
IPv4 loopback host is accepted; remote hosts, DNS names and wildcard addresses are
rejected. There is no automatic `.env` loader or plaintext fallback. Empty or invalid
configuration disables Admin, without interrupting existing CrowdQuest features.
Non-default ports must match the server. Environment values override the vault;
remove empty overrides if you intend to use saved credentials.

For an isolated OBS-only process when port 8000 is unused:

```powershell
uv run --locked python -m crowdquest.obs_admin
```

This uses the same page, adapter and security routes, binds only `127.0.0.1`, and
does **not** open application SQLite stores, start EventSub, construct AIG or start
a worker. It serves `/obs-admin` only; the Dashboard/Overlay require the full app.
Do not mistake an OBS-only server for a recovered full CrowdQuest installation.
Use only one Admin/backend process for a given OBS instance.

## Security model

- Both launchers bind `127.0.0.1`, one worker, with proxy headers and access logs off.
  Each Admin route additionally checks the actual socket peer is loopback, exact
  `Host: localhost:<port>`, and rejects cross-site/same-site Fetch Metadata. Forwarded
  headers cannot confer loopback access. Do not expose this process via a tunnel.
- The login form uses a separate Admin passphrase, not the OBS password or Twitch
  session. A five-minute unauthenticated bootstrap cookie binds its CSRF token.
  Successful login rotates the cookie and CSRF; the authenticated session lasts one
  hour. Cookies are HttpOnly, SameSite=Strict and scoped to `/api/obs-admin`.
- All POSTs require the exact Origin, JSON, the session's CSRF token and bounded
  input. Duplicate JSON keys, extra fields, queries and invalid identifiers are denied.
  Login is limited to five failures/minute across the process; sessions are capped at
  sixteen. Tokens stay in memory and expire on restart. This is a local single-user
  tool, not a hostile-local-user or multi-tenant security boundary.
- The OBS password is used only by the backend. Credential fields have masked
  representations; SDK loggers (including its password-bearing INFO log and raw
  response/error logs) are disabled before connecting. Only fixed error codes and
  reviewed status fields cross HTTP. Raw input settings, unsafe URLs and exception
  comments never reach the page. Local output paths are visible only after login.
- Browser mutations consume a single-use process revision before dispatch, even if
  they fail. A global nonblocking adapter lock and synchronous frontend guard prevent
  duplicate/concurrent commands. A stale tab or replayed POST receives a conflict.
  Reloading a page never starts recording. Signing out/closing the server never
  implicitly starts or stops OBS recording; inspect OBS yourself if leaving it active.

## State, timeouts and recovery

The client uses a two-second connection/socket timeout, no event subscriptions and
one connection attempt per request. Failed connections are throttled for five seconds.
Status polling is read-only every five seconds; there is no background recording job,
mutation retry or reconnect replay. Each response failure discards that connection so
late replies cannot answer a new request.

Start/Stop first query actual OBS recording state and return `ALREADY_IN_STATE`
without dispatch when applicable. After dispatch, a new actual state query is
required before `VERIFIED`. If the reply is lost, the adapter reconnects at most once
for a read: `STATE_RECONCILED` reports the observed state, without claiming ownership
of an externally triggered change. It **never resends** StartRecord/StopRecord.
An unavailable or inconsistent reconciliation returns `OBS_OUTCOME_UNKNOWN`. Inspect
OBS and refresh state before considering any new explicit command. A refresh-button
ACK cannot prove browser navigation or OBS rendering; timeout returns uncertain.

StopRecord's documented `outputPath` is retained only in server memory. If its reply
was lost, recording can be confirmed stopped but the filename is unknown. No file is
guessed, downloaded, deleted or overwritten. Restart loses this convenience field.

## Usage from a browser / Desktop Work

1. Open `/obs-admin` and enter the **Admin** passphrase yourself. Never provide the
   OBS password to browser automation. Let the user complete authentication.
2. Wait for Connected, version/current scene and actual recording status.
3. Select an existing scene and click **Switch scene**; wait for confirmed current
   program scene before continuing. No scene/source is created automatically.
4. **Refresh CrowdQuest overlay** targets exactly the existing input named
   `CrowdQuest Overlay`, kind `browser_source`, exact local `/overlay` URL and no local
   file mode. Unsafe/credential-bearing URL settings are hidden and rejected. Enabled
   status describes direct instances in the current scene; groups/nested scenes are
   explicitly unknown rather than falsely claimed visible. Configuration is not edited.
5. Click **Start Recording** once; wait for actual Recording state. Click **Stop
   Recording** once; wait for Stopped. Read the returned path, then independently
   verify file existence and playback for real acceptance. No acceptance follows
   from HTTP 200 alone.

All busy/error/disconnected states disable stale controls. Recording time comes from
OBS `outputDuration`, refreshed every five seconds; it is not a fabricated local timer.
Typical errors: `OBS_UNAVAILABLE` → open OBS/check server/port;
`OBS_AUTH_FAILED` → privately correct password; `OBS_AUTH_REQUIRED` → personally
enable authentication; `OBS_STALE` → refresh status; `OBS_OUTCOME_UNKNOWN` → inspect
OBS without blindly repeating the operation. No authentication is disabled automatically.

## Qualification and rollback

See [acceptance](PHASE45-OBS-ADMIN-ACCEPTANCE.md) for measured results and live blockers.
Tests use temporary stores, synthetic OBS and real Chromium; wire tests exercise the
installed client's v5 handshake against a local fixture. They never prove real media.

Qualified assets can be built separately, preserving `frontend/dist`:

```powershell
$env:UV_PROJECT_ENVIRONMENT = "$PWD/.artifacts/phase45/venv"
uv sync --locked --python 3.13
.artifacts/phase45/venv/Scripts/python.exe -m pytest -q
npm --prefix frontend run test
# Run from frontend:
node node_modules/vite/bin/vite.js build --outDir ../.artifacts/phase45/frontend
# From repository root:
$env:CROWDQUEST_TEST_FRONTEND = "$PWD/.artifacts/phase45/frontend"
.artifacts/phase45/venv/Scripts/python.exe -m tests.obs_browser_e2e
```

Rollback: stop only this OBS-only process, or use a separately approved safe full-app
shutdown; return to the previous qualified source/environment/assets. No data migration
is introduced, so do not delete or restore real SQLite just to remove Admin. Leave
existing OBS scene/source/recordings and historical evidence untouched. Remove only
these optional Admin environment overrides or the two separately named Admin vault
entries if you explicitly want to retire access. Do not change Twitch/AIG credentials.

Protocol sources: [official OBS v5 protocol](https://github.com/obsproject/obs-websocket/blob/master/docs/generated/protocol.md),
[client documentation](https://github.com/aatikturk/obsws-python), and the installed
1.8.0 client source reviewed during implementation. These document the request/response
contracts; they are separate from our measured acceptance evidence.
