# AIG integration contract

Status: Phase 2 local integration and exact-commit remote CI PASS; see
[implementation and evidence](PHASE2-IMPLEMENTATION.md). Phase 3 adds real local-model
Plan probes and controlled worker/browser qualification; see
[Phase 3 evidence](PHASE3-IMPLEMENTATION.md). The subsequent genuine single-Action human/Twitch/model/OBS session passed; see
[real session evidence](PHASE3-REAL-ACCEPTANCE.md). Phase 4 has a separate pending live gate.

## Immutable release and instructions

```toml
"agentic-intent-gate @ git+https://github.com/miku-wwl/agentic-intent-gate.git@bb8e8fb1234128613a750bee17967b225072bb14"
```

- Distribution `agentic-intent-gate==0.3.0`; Python `>=3.13,<3.14`; Git release, not PyPI.
- Annotated tag object `28af5eccf287f70b63f20386010e5747e1511e9b` peels to the pin above.
  The tag is unsigned; identity checks do not claim cryptographic publisher signing.
- Template comes from upstream main commit `7f635adf13f105cf4ed8408766c47e612048773c`,
  consumer path `docs/AGENTS-dependence.md`, Git blob `f14307dcc124a0eaefc24dbc3cb64643f35b1fa9`.
  All 12,127 source bytes are the unchanged prefix of root `AGENTS.md`.
  Instruction provenance and runtime dependency commits intentionally differ.
- [Pinned consumer example](https://github.com/miku-wwl/agentic-intent-gate/blob/bb8e8fb1234128613a750bee17967b225072bb14/examples/consumer/app.py),
  [handoff](https://github.com/miku-wwl/agentic-intent-gate/blob/bb8e8fb1234128613a750bee17967b225072bb14/docs/V0.3.0-CONSUMER-HANDOFF.md),
  [adapter guide](https://github.com/miku-wwl/agentic-intent-gate/blob/bb8e8fb1234128613a750bee17967b225072bb14/docs/ADAPTER_GUIDE.md)
  and [public module](https://github.com/miku-wwl/agentic-intent-gate/blob/bb8e8fb1234128613a750bee17967b225072bb14/src/agentic_intent_gate/runtime.py)
  were read without changing upstream. Example workflow was not run.

`uv.lock` resolves that full Git commit. `scripts/verify_baseline.py` checks the lock,
installed distribution/direct-URL commit, non-editable import from this `.venv`, public
signatures, Python version and preserved template digest. It never opens a runtime.
Machine-readable installed signatures are in [baseline evidence](evidence/phase0-baseline.json).

## Public API and intended use

Import exclusively from `agentic_intent_gate.runtime`:

| Entry | Verified signature / intended role |
| --- | --- |
| `ToolBinding` | `(tool_name, tool_version, adapter_id, binding_revision, target, execution_scope)` |
| `ToolCapability` | Trusted binding, description, bounded flat input schema; optional target argument and semantic rule |
| `ExecutableRegistry` | One executor with explicit keyword `binding`; frozen startup registration |
| `CapabilityVerifier` | Private token plus trusted subject, binding and allowed operations |
| `BoundCapabilityAuthorization` | Verifier plus reviewed policy revision; independent Action policy |
| `open_runtime` | Keyword gate_path/provider/capability/registry/verifier/policy; predecessor_stopped=False; execution_timeout_seconds=5 |
| `ModelProvider.generate_plan` | Consumer planning port; domain-specific provider must be supplied |
| `ToolExecutor.execute` | `(self, spec, effect_key, context)`; bounded correlated `ToolOutcome` |
| `runtime.run_service` | `create`, `get`, `decide` for validated persistent Runs and decisions |
| `runtime.gateway` | `admit`, `authorize`, `execute`, `get`, `list_for_run`, `require` |

Use public `Intent`, `ApprovalChoice`, `ApprovalDecisionRequest`, `AdmissionCommand`,
`ActionCommand`, `ExecutionSpec`, `AttemptContext`, `Outcome` and `ToolOutcome` values.
Versions are read from current state; do not hard-code the reference example's version
numbers into a dashboard. AIG demo prompts and UI are service-demo specific and will
not be reused as a generic Twitch planner or authentication boundary.

## Frozen trusted composition (qualified locally and in one genuine Phase 3 session)

| Field | Design value |
| --- | --- |
| tool / version | `enqueue_overlay_challenge` / `1` |
| adapter / binding revision | `crowdquest-overlay` / `overlay-admission-v1` |
| target | Operator-configured `twitch-channel-<broadcaster_id>` |
| execution scope | Fresh canonical UUIDv4, generated once during explicit provisioning |
| adapter budget | Default 5 seconds; no extended budget approved |
| effect | Durable local job admission only; no browser or Twitch call in executor |

All six identity fields must match in capability, registry, verifier, policy, effect
store and receipt validation. Model/browser inputs cannot select them. Persist identity
across restarts; never silently generate a new scope on existing state. Keep the AIG
owner context open for the backend lifetime. `predecessor_stopped` is a verified operator
attestation, not a command that terminates another process.

Proposed arguments are four required bounded scalars: title string 1–80, description
string 1–240, duration_seconds integer 15–120, difficulty bounded string matching
`^(Easy|Medium|Hard)$`. No optional, nested or additional fields. Respect the API's
4 KiB schema/canonical-argument bound. Deterministic semantics enforce safe display text.
The host fixes risk `SIDE_EFFECT`, one step, tool/version and target. No new Plan
schema implementation replaces AIG's validator.

## Lifecycle, authorization and receipts

Validated Plan → persistent Run → exact authenticated human Approval → Action admission
→ independent Authorization → durable claim → consumer executor → verified admission
effect → durable receipt. A successful executor does not render anything.

The application authenticates the streamer separately; the backend holds a private
runtime capability. A reviewed policy checks exact Action authority and deny-by-default
channel conditions. Approval, Authorization and execution remain separate operations.
No browser token is used as a runtime capability and no executor obtains approval rights.

The executor atomically stores binding, effect_key, payload digest, job and UUID receipt
in the consumer SQLite store. Same key/payload yields the original receipt without
another insert; different payload is confirmed `PAYLOAD_CONFLICT`. Proven identity/input
rejection can be a confirmed failure. Evidence must correlate scope, target, full payload,
effect key and receipt; uncertainty is `Outcome.UNKNOWN_OUTCOME`.

Interrupted or lost-ack effects stay terminal `Unknown`; never reset, replay, issue
replacement Actions, or infer no effect from an exception. The worker cannot act on
an unconfirmed/Unknown admission. Read public gateway state and compare the receipt
before enabling a job; see [architecture](ARCHITECTURE.md). Keep rendering outcome
separate from AIG `Succeeded`. No generic reconciliation API or remote exactly-once
guarantee exists. All DB paths, tokens and private receipt state remain outside source.

## Phase 2 verification gate

Use the exact installed dependency without modifying AIG. Test real SQLite state and
receipt persistence, absent Authorization, stale approval, tool/target/binding/scope
denials, duplicate commands, same-effect conflicts, concurrent claims, crash/restart,
lost commit acknowledgements, timeouts and quarantined jobs. Synthetic providers and
scripted approvals must be labeled test consent. They cannot prove human approval,
real model inference or Twitch/OBS functionality.

## Phase 4 invariant

Voting and owner-reported outcomes are application state, not new AIG tools. Winner
provenance and the audience badge live outside the unchanged challenge arguments.
Every new Action still needs its own exact Plan Approval, admission, independent
Authorization and explicit Execute request. Outcome presentation never calls Execute,
rewrites a grant/result, extends a deadline or creates a replacement Unknown Action.
