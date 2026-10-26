# Phase 3 operator runbook

The original controlled activation and one genuine Phase 3 Action session completed
PASS; see [session record](PHASE3-REAL-ACCEPTANCE.md). The procedure below remains the
reference for a separately authorized future activation. Existing credentials, stores
and identities must be retained. Do not repeat activation/OAuth/pairing as a development
test. Phase 4 uses its [new live runbook](PHASE4-LIVE-RUNBOOK.md).

## Before a controlled activation

1. Record Git HEAD, verify a clean checkout and the pushed-commit CI receipt. Preserve
   the installed AIG pin, fixed binding and five-second adapter budget.
2. Recheck localhost:8000, the listener PID, executable/command line and private
   EventSub status PID. They must identify this checkout or its recorded CrowdQuest
   verified bootstrap. Never terminate an unverified listener or another project.
3. Read-only SQLite integrity checks and the online backup API must pass. Back up
   real intake and any existing gate/product/admission/render stores privately; retain
   scope, identity, credentials and history. Never clear, replace or replay real rows.
4. Confirm configured owner miku_wwl and existing token scope exactly user:read:chat
   through Twitch validation. Reuse Windows Credential Manager; never paste credentials
   into chat, command arguments, screenshots or project files. Normal provider-issued
   token refresh is not manual credential reset; extra OAuth scopes are prohibited.
5. Confirm existing local phi4-mini:latest and its qualified digest. No download,
   cloud-backed Ollama model, paid provider or large installation is part of this plan.

Example private intake backup, before shutdown (no chat contents printed):

```powershell
@'
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from crowdquest.config import Settings
s = Settings.load()
directory = s.state_dir.parent / "backups" / datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
directory.mkdir(parents=True, mode=0o700)
with closing(sqlite3.connect((s.state_dir / "intake.sqlite3").as_uri()+"?mode=ro", uri=True)) as source:
    assert source.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
    with closing(sqlite3.connect(directory / "intake.sqlite3")) as backup:
        source.backup(backup)
        assert backup.execute("PRAGMA integrity_check").fetchall() == [("ok",)]
print("PRIVATE_SQLITE_BACKUP_AND_INTEGRITY=PASS")
'@ | uv run python -
```

Keep the original service and all business data intact until the owner approves this
specific restart. Prefer its own terminal's graceful shutdown. If unavailable, only
the freshly verified CrowdQuest PID may be stopped after backup; confirm port and
owner lock release. Do not reuse a stale PID from this document or prior evidence.

## Private provisioning and startup, after approval

The following read-only lookup captures the validated numeric owner ID in a local
variable. It prints no token or secret; do not echo that variable into public logs.

```powershell
$cqOwnerId = @'
import json, sys, httpx
from crowdquest.config import Settings
from crowdquest.secrets import WindowsVault
try:
    s = Settings.load()
    saved = json.loads(WindowsVault(s.state_dir).get("tokens"))
    with httpx.Client(timeout=10, trust_env=False) as client:
        response = client.get("https://id.twitch.tv/oauth2/validate",
            headers={"Authorization": "OAuth " + saved["access_token"]})
    assert response.status_code == 200
    owner = response.json()
    assert owner["login"] == s.owner_login and owner["client_id"] == s.client_id
    assert owner["scopes"] == ["user:read:chat"]
    print(owner["user_id"])
except Exception:
    print("OWNER_VALIDATION_FAILED")
    sys.exit(1)
'@ | uv run python -
if ($LASTEXITCODE -ne 0) { throw 'Owner validation failed; stop activation' }
$cqProfile = Join-Path $env:LOCALAPPDATA 'CrowdQuestAI\phase3'
uv run python -m crowdquest.phase3 $cqProfile --owner-id $cqOwnerId
```

Provision only a new private directory. Existing directories, including empty ones,
are rejected. Do not delete an existing profile to bypass this guard: inspect and
retain its binding, scope, receipts and Unknown history. The UUIDv4 scope is created
once; the runtime capability, worker token and browser credential roles are separate.
No Plan/Approval/Action is created by provisioning.

After verified shutdown of all prior owners of this profile, start the backend:

```powershell
uv run python -m crowdquest --phase3-directory $cqProfile --phase3-owner-id $cqOwnerId --predecessor-stopped
```

Keep it running. In a second terminal, with the same private profile path:

```powershell
$cqProfile = Join-Path $env:LOCALAPPDATA 'CrowdQuestAI\phase3'
uv run python -m crowdquest.worker --origin http://localhost:8000 --token-file (Join-Path $cqProfile 'worker-token')
```

The predecessor flag is an operator attestation, not a lock bypass or process-killing
command. A worker HTTP failure stops the worker; there is no restart/retry loop.
If launched by an agent with Start-Process, keep helper windows hidden.

## Required manual owner operations

1. Open http://localhost:8000 and Connect Twitch as miku_wwl. Memory sessions from
   Phase 1 expire at restart; accept user:read:chat only. Stop if extra scopes appear.
2. In OBS retain CrowdQuest Demo / CrowdQuest Overlay, URL
   http://localhost:8000/overlay and 1280×720. Refresh it. Match its pairing code in
   the owner Dashboard and wait for Ready. Never send the code or credentials to chat.
3. Check genuine EventSub welcome, matching enabled subscription and fresh keepalives;
   Dashboard Connected/Ready alone is not EventSub or rendering proof.
4. The owner sends one fresh real `!quest Survive 60 seconds without healing` message.
   The agent does not send Twitch chat. Verify the new persisted candidate separately.
5. Select it and Generate proposed Plan once. Require REAL_MODEL, review all four exact
   fields and current version. If rejected/invalid, do not pretend a manual draft is
   real inference. A deliberate manual draft is labelled OFFLINE_MANUAL and needs fresh
   review; it cannot complete the genuine real-model acceptance gate.
6. The owner explicitly clicks Approve this Plan, then Admit approved Action, then
   separately Authorize this Action, then Execute authorized Action. No agent/script
   may substitute fixture consent. Approval does not dispatch a job.
7. Verify durable AIG Succeeded plus matching admission receipt, then separate render
   state and browser acknowledgement. The owner visually confirms the exact challenge
   and decreasing countdown in actual OBS. Browser acknowledgement alone is insufficient.
8. For a generated 60-second Plan, observe roughly 60–65 seconds until text clears and
   Expired/Waiting appears. Do not click Execute/Preview again to force success. Refresh
   the source to verify no replay; confirm no second Action/effect/dispatch record.

Record correlated redacted chat/delivery IDs, candidate/Run/Action IDs, receipt hash,
render ID, browser acknowledgement and dated user OBS observation. Export no raw chat
history, cookies, token, pairing code, private database or private state path. A new
screenshot is user visual evidence; never fabricate a local original image or hash.

## Recovery decisions

| Observed condition | Required response |
| --- | --- |
| Missing owner/channel auth | Deny control and publication; owner handles reauthentication |
| Model rejection/refusal/timeout | No Action; no automatic inference retry; explicit labelled manual draft only |
| AIG Pending/Authorized/Executing | No render until exact durable success/receipt is verified |
| AIG Unknown or unconfirmed outcome | Quarantine; never reset, retry or create a replacement Action |
| Worker fenced or uncertain HTTP response | Stop worker; inspect durable state, do not resend |
| Claimed but no dispatch marker | Conservative Render Failed; preserve record, no automatic requeue |
| Dispatch/ack uncertainty, worker loss, server restart | Terminal rendering Unknown; no replay or success reconciliation |
| Browser reload/reconnect | Issued challenge is not replayed and countdown cannot restart |
| Confirmed expiry | Preserve receipt/history; only a separately approved new candidate can progress |

The OS/operator is trusted; no distributed HA, malicious-Python isolation or universal
exactly-once remote display guarantee is claimed. Do not upload/stream/submit or contact
the organizer. Competition eligibility and own-runtime reuse clarification remain
separate blockers for submission.
Use one deployment/profile for the configured channel. Do not start parallel profiles
for the same channel; ownership/active-render fencing is local to the configured deployment.
