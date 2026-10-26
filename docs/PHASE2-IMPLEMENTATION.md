# Phase 2 single-action integration

Date: 2026-10-26, Pacific/Auckland. **Local engineering integration: PASS.**
Phase 1 engineering acceptance passed; original screenshot bytes remain separately
PARTIAL. Phase 2 live activation, actual human Action approval, real AI and worker/OBS
delivery are NOT_RUN. The working Phase 1 service was not restarted a second time.

Delivery reconciliation: commit `edcefa7c6d286e6f4dde98d01700dd2d636020cb` is on remote
main. [CI 40278101916](https://github.com/miku-wwl/crowdquest-ai/actions/runs/40278101916)
was rechecked against that exact SHA: SUCCESS, 125 backend tests, 9 frontend tests,
lint/build/provenance and actual Chromium synthetic E2E passed. Remote push and
commit-specific CI are PASS; live activation and real human Action approval stay NOT_RUN.

The delivered vertical slice follows the existing roadmap: a fixed
enqueue_overlay_challenge/1 binding, default five-second installed AIG runtime,
strict flat challenge arguments, persistent Run and exact version-bound Approval,
separate admission/Authorization/execution, and a consumer-owned transactional SQLite
job/receipt store. Unknown or unconfirmed outcomes stay quarantined without retries.

Only the installed v0.3.0 public API is imported. The pinned
[consumer example](https://github.com/miku-wwl/agentic-intent-gate/blob/bb8e8fb1234128613a750bee17967b225072bb14/examples/consumer/app.py),
[handoff](https://github.com/miku-wwl/agentic-intent-gate/blob/bb8e8fb1234128613a750bee17967b225072bb14/docs/V0.3.0-CONSUMER-HANDOFF.md)
and [adapter guide](https://github.com/miku-wwl/agentic-intent-gate/blob/bb8e8fb1234128613a750bee17967b225072bb14/docs/ADAPTER_GUIDE.md)
were reread before implementation; dependency/provenance checks passed.
Offline/manual planning is explicit and makes no LLM/provider request. Owner routes
must retain the existing authentication, CSRF and Origin controls. An optional trusted
startup composition isolates Phase 2 from the running Phase 1 instance.

## Implemented boundaries

- `crowdquest/challenges.py`: strict title 1–80, description 1–240, duration integer
  15–120 and Easy/Medium/Hard; control characters and extra authority fields rejected.
  Markup stays untrusted text. OFFLINE_MANUAL is a deterministic proposal scaffold,
  with no external inference or paid call.
- `crowdquest/phase2.py`: exclusive private provisioning, persisted UUIDv4 scope,
  exact configured owner/target, binding overlay-admission-v1 and frozen policy.
  One public registry and the default five-second runtime; no configurable budget.
  Existing identity/state is never silently reprovisioned or migrated.
- `crowdquest/admission.py`: one transaction binds full identity, payload digest,
  effect key, challenge, unique job and receipt. It independently reads back committed
  data inside the adapter deadline. Same payload returns the original receipt;
  conflicts do not overwrite it. Executor receives no control-plane credential.
- `crowdquest/phase2_routes.py`: owner/CSRF/Origin-protected review, decision, admission,
  independent Authorization and execution. Exact approved Plan/version and durable
  authenticated-owner review are checked before admission; a missing consumer review
  audit fails closed even if AIG approval committed. The browser never receives the
  runtime capability. Error responses contain fixed codes only.
- Job state is PENDING_CONFIRMATION until a public durable gateway read establishes
  Succeeded and an exact matching receipt. Normal Executing polls leave it ineligible;
  Unknown, failed/mismatched evidence or interrupted recovery quarantines it. Terminal
  quarantine is never automatically released. Startup confirms state without executing,
  resetting, replacing or retrying Actions. ELIGIBLE is admission readiness, not rendering.

The permission mode uses Python 3.13's documented
[Windows 0o700 directory ACL handling](https://docs.python.org/3.13/library/os.html#os.mkdir).
Even existing empty directories are rejected so their earlier permissions cannot
silently bypass private creation. Capability provisioning uses the public AIG helper.

## Consumer API

Phase 2 is absent from the default app. A trusted startup factory enables these routes:

| Method/path | Request / behavior |
| --- | --- |
| POST /api/phase2/runs | Four bounded challenge fields; returns the exact proposed Plan and OFFLINE_MANUAL |
| GET /api/phase2/runs/{run_id} | Owner reviews persistent state, Plan and current version |
| POST /api/phase2/runs/{run_id}/decision | decision APPROVE/REJECT and expected_version; never dispatches |
| POST /api/phase2/runs/{run_id}/admit | expected_version and UUID idempotency_key; creates an unexecuted Action |
| POST /api/phase2/actions/{action_id}/authorize | Separate explicit command for exact Action/version |
| POST /api/phase2/actions/{action_id}/execute | Separate explicit command; AIG claim precedes executor |
| GET /api/phase2/actions/{action_id} | Durable Action plus separately stated admission/rendering state |

Versions come from current responses, not hard-coded example numbers. Browser/model
inputs cannot set trusted identity, target, scope, policy, executor or timeout.
The complete review UI, real ModelProvider and overlay worker remain Phase 3.

Operator provisioning is explicit, outside the checkout, with the configured numeric
broadcaster ID. For a separately authorized future activation:

```powershell
uv run python -m crowdquest.phase2 <new-private-directory> --owner-id <broadcaster-id>
uv run python -m crowdquest --phase2-directory <existing-private-directory> --phase2-owner-id <broadcaster-id> --predecessor-stopped
```

These are syntax templates, not commands executed against the live instance.
`--predecessor-stopped` is an operator attestation after verifying shutdown, not a
process-termination command. Existing state retains the same identity on restart.

## Actual verification

The full local suite returned **125 backend tests passed**, including **46 Phase 2
cases**, with one existing Starlette/HTTPX deprecation warning. Frontend: **9 passed**.
Actual Chromium synthetic E2E exited 0; lint, format, TypeScript/Vite build, installed
pin/public API/upstream-template verification, lock and dependency checks passed.
All 45 installed AIG Python source hashes match distribution RECORD entries.
The final full backend run took 46.28 seconds. The actual Windows private directory
ACL check is included and passes; POSIX uses the actual 0700 permission check.

Tests inspect real temporary SQLite effects/receipts and public AIG state. They cover
strict schema/identity denials, wrong channel/subject/operation, stale and rejected
approval, missing owner-review audit, absent Authorization, stable idempotency,
payload conflicts, eight actual concurrent threads/SQLite claim contenders, in-flight
polling, store identity, lost acknowledgement, expired/shortened deadlines, wrong
receipt, restart and an actual test-owned subprocess exit after effect COMMIT. Recovery
leaves one effect and terminal Unknown/quarantine; no second dispatch occurs.
Scripted fixture decisions are SYNTHETIC_TEST, not authenticated human evidence.

Failure history: the first late-ack probe used a 50 ms caller envelope, which could
expire before claim/dispatch; it correctly became Unknown without a job. Its assertion
failed (32 passed, 1 failed). Separate pre-dispatch and post-commit deadline cases now
test both outcomes, retaining the runtime's unchanged five-second budget. Review also
found and fixed premature permanent quarantine during normal in-flight polling.

The Windows ACL probe initially failed because Windows PowerShell could not autoload
Get-Acl in the fixture environment, and then because the expected-principal list
omitted OWNER RIGHTS. Direct .NET ACL inspection and the pinned
[CPython 3.13.9 implementation](https://github.com/python/cpython/blob/v3.13.9/Modules/posixmodule.c)
confirmed the protected owner/SYSTEM/Administrators ACL. The corrected check validates
the directory's actual owner as well as every allowed principal and passes. Existing
directories are still rejected; no production permissions or credentials were changed.

[local qualification receipt](evidence/phase2/local-qualification.json) records source
hashes, commands, results and evidence classes. No real database, token or capability
is archived. Phase 2 GitHub delivery/CI and live activation are reported separately
from local qualification; a previous Phase 1 CI run is not Phase 2 code evidence.

At Phase 2 qualification no Phase 3 work, paid inference, Twitch writes, OBS control,
deployment, release or submission was performed. Subsequent separately authorized
Phase 3 work is recorded in [PHASE3-IMPLEMENTATION.md](PHASE3-IMPLEMENTATION.md).
Competition eligibility remains UNVERIFIED.
