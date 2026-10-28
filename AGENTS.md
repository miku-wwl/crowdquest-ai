# Hackathon Agent Instructions — Reuse Agentic Intent Gate

## Purpose

This repository is a **Hackathon application that consumes an existing Python Agent Runtime**. Build the competition-specific product, **not another agent execution framework**.

**Shared runtime:** [Agentic Intent Gate](https://github.com/miku-wwl/agentic-intent-gate)<br>
**Python distribution:** `agentic-intent-gate`<br>
**Public integration module:** `agentic_intent_gate.runtime`<br>
**Qualified release:** `v0.3.0` (verified annotated Git tag; Python 3.13; MIT)<br>
**Pinned release commit:** `bb8e8fb1234128613a750bee17967b225072bb14`

The annotated tag `v0.3.0` peels to the pinned commit above. This is a **Git release, not a PyPI publication**. Use the immutable full commit SHA, **not** a moving `main` branch. When upgrading in the future, verify the tag, peeled commit, installed version, and lockfile. Never embed private Git credentials or external-service secrets in URLs, code, screenshots, or logs.

**Template use:** Copy this document into a **new consumer repository** as its root `AGENTS.md`. Add the competition's own scope, security rules, environment constraints, and human-approval requirements. If that repository already has `AGENTS.md`, **merge** the instructions instead of overwriting its product-specific rules. Do not copy the core repository's developer-only root `AGENTS.md` into a consumer project.

## Dependency Setup

Declare this exact dependency in the consumer's existing `pyproject.toml` and update its lockfile:

```toml
[project]
dependencies = [
  "agentic-intent-gate @ git+https://github.com/miku-wwl/agentic-intent-gate.git@bb8e8fb1234128613a750bee17967b225072bb14",
]
```

**Merge the dependency entry**; do not replace an existing `[project]` section or other dependencies blindly. Verify the installed distribution reports `agentic-intent-gate==0.3.0`, resolves to the pinned source commit, and is imported from the installed environment, **not an adjacent source checkout**. Use the [v0.3.0 consumer handoff](https://github.com/miku-wwl/agentic-intent-gate/blob/main/docs/V0.3.0-CONSUMER-HANDOFF.md) and [adapter guide](https://github.com/miku-wwl/agentic-intent-gate/blob/v0.3.0/docs/ADAPTER_GUIDE.md) as the detailed integration references.

## Reuse the Core

Within its supported scope, Agentic Intent Gate already provides:

- Strict structured Plan validation and trusted, bounded tool schemas.
- Persistent Runs and exact Plan-to-Approval binding.
- Independent Action execution Authorization, separate from Plan Approval.
- Explicit trusted single-tool `ToolExecutor` registration.
- Single-step `SIDE_EFFECT` Action lifecycle.
- SQLite-backed durable Action state, claim, audit events and receipt references.
- CAS/concurrency controls, stable effect keys, binding identity and idempotent command handling.
- Fail-closed recovery and terminal ambiguous/`Unknown` outcomes (no blind retry).
- Trusted configurable adapter execution budgets: default **5 seconds**, explicit maximum **15 seconds**.

**Do not copy, fork, reimplement, monkeypatch, or bypass these core mechanisms in the consumer.** Use the published public API and a fixed dependency revision.

## Public Integration Entry Point

Inspect the **installed v0.3.0 API** and the core repository's `examples/consumer/app.py` before implementing integration. Supported imports include:

```python
from agentic_intent_gate.runtime import (
    ToolBinding,
    ToolCapability,
    ExecutableRegistry,
    CapabilityVerifier,
    BoundCapabilityAuthorization,
    execution_budget_binding,
    open_runtime,
)
```

Check the actual constructor/function signatures; do not invent methods. Register trusted executors at startup with exact tool/version/target/adapter identity, reviewed binding revision, canonical execution scope, strict argument schema and appropriate independent authorization. Model output and untrusted HTTP input cannot register code or select trusted identities.

### Trusted Execution Budget (v0.3.0)

- `open_runtime(..., execution_timeout_seconds=5)` is the **backward-compatible default**. Finite built-in `int`/`float` values in `(0, 15]` are supported. Booleans, invalid types, NaN, infinity, non-positive values and values over 15 are rejected.
- For values **above 5**, trusted host code must explicitly opt in, use a **fresh reviewed base `ToolBinding` revision**, and apply `execution_budget_binding(base_binding, 15)` to produce a canonical binding revision ending in `.exec-15s`. The complete revision must fit the 64-character limit.
- Pass `execution_timeout_seconds=15` to `open_runtime` **only after the complete reviewed binding, capability, registry, verifier, policy and consumer effect/receipt identity are consistently configured**. Do not let model output, tool arguments, browser parameters, or API clients choose or increase this value.
- Keep the extended profile's binding revision, scope and persisted consumer configuration **stable across restarts**. Use a fresh UUIDv4 scope and **separate private gate/ledger/receipt-store identity** for a new extended profile.
- **Do not silently elevate old Actions or grants.** Never migrate, relabel, replay, or reuse legacy Approval, Authorization, effect keys or receipt identities under a longer budget. Create a new Plan/Run, obtain fresh human Approval, admit a new Action and obtain separate Authorization. Existing default-profile Actions retain their original identities; previously Failed/Unknown terminal Actions must not be reset or replayed.
- Extended Actions use `action-compiler-v3` / `action-spec-v3` and bind the reviewed budget profile into their identity. Old v1/v2 Actions cannot gain a longer budget merely by changing host configuration or using a similar binding name. Keep prior ledgers available for historical audit; v0.1.0 software cannot interpret v3 extended Actions.
- The configured adapter deadline starts **after durable Gateway claim**. The Gateway's synchronous claim and finish work are outside the adapter timer. A caller-supplied validated **monotonic** deadline may only **shorten**, never extend, this budget. Late outcomes, cancellation, lost acknowledgment and uncertain writes can still become `Unknown`.
- Provider requests, independent effect verification and adapter-side durable receipt persistence must fit within the adapter budget. External effects cannot necessarily be cancelled after dispatch. Avoid detached background execution, automatic retries, and recovery replay; **15 seconds is not a guaranteed completion time or exactly-once remote-effect guarantee**.
- The bundled Runtime Action HTTP routes retain a **10-second parent deadline**. If the consumer needs a full 15-second adapter allowance, use a supported public Gateway invocation within an appropriately budgeted **consumer-owned request envelope**; do not use private Runtime internals or assume the bundled HTTP endpoint grants 15 seconds.
- Consumer-specific constraints, including Sandbox-only execution, allowed targets, spend limits, HTTP timeouts, durable dispatch fencing and payment-provider policies, belong **in the consumer application**, not in the shared Runtime.

**Default rule:** Unless a reviewed use case needs an extended budget, omit the new argument and retain **5 seconds**.

## Competition-Specific Responsibilities

Implement **only** the product-specific requirements:

1. Product concept, competition integrations, frontend and demo experience.
2. Trusted consumer tools, bounded argument schemas, concrete executors and receipt stores.
3. External service/API/MCP clients, where genuinely needed.
4. Consumer authentication, authorization, credentials and environment controls.
5. A suitable consumer `ModelProvider` when model-driven Plan generation is required.
6. Product tests, evaluation, deployment, documentation and submission.

**Demo boundaries:** The core's bundled local LLM prompt is tailored to `service-demo/service_id`, and its UI Action-admission controls remain Demo-specific. A non-Demo consumer must provide suitable planning and its own UI or use supported API admission paths; the bundled Demo UI does **not** automatically support arbitrary tools. The reference consumer's scripted approval is test/example consent, not proof of authenticated human approval.

## Supported Scope and Non-Goals

v0.3.0 supports **one explicitly registered trusted `SIDE_EFFECT` tool per Runtime composition and single-step execution**. It is **not** a general-purpose multi-agent engine. Do not assume general `READ_ONLY` tool execution, multi-tool/multi-step workflow orchestration, dynamic plugin discovery, arbitrary MCP execution, production multi-user authentication, distributed HA, malicious-Python isolation, or guaranteed exactly-once remote side effects.

If the competition requires unsupported functionality, identify the gap before building. Prefer a thin product-owned layer where safe. Request a separately reviewed core extension only when unavoidable; never silently bypass the core's safety gates.

## Mandatory Safety Boundaries

- Model output proposes a Plan; it **never** chooses trusted credentials, executors, scopes, execution budgets or grant decisions.
- Verify exact tool identity, schema, target, binding revision, execution scope and trusted profile before compilation and execution.
- **Human Approval and execution Authorization are separate gates**. Approval alone never dispatches an effect; do not fabricate or inherit consent from earlier Actions.
- Never substitute a different Plan's Approval, skip durable claiming, or weaken owner fencing and authorization checks.
- Treat ambiguous post-dispatch effects as `Unknown`; **no automatic retry, unsafe reconciliation, duplicate POST or recovery replay**. Distinguish proven pre-dispatch no-effect failures from uncertain remote effects.
- Respect the provider's documented idempotency semantics; a provider request ID is **not** a universal exactly-once guarantee.
- Keep secrets, capability tokens, private Git credentials, personal data and private state outside source, docs, screenshots and CI logs.
- Do not initiate real money movements, financial API mutations or other irreversible third-party effects without fresh, explicit, operation-specific human authorization.

## Acceptance Criteria

An external consumer using the exact pinned, **installed** package, **without modifying core source**, must demonstrate:

**Validated Plan → Persistent Run → Exact Human Approval → Admission → Independent Authorization → Durable Action Claim → Consumer Executor → Verified Effect → Durable Receipt**

Tests should cover successful execution and persistence; unknown tool, wrong target/binding/scope, missing authorization, stale approval, duplicate/concurrent/conflicting effects, and ambiguous outcome. For extended profiles, additionally test default/15-second configuration, invalid budgets, wrong-profile denial, old-Action non-escalation, shortening caller deadlines, pre-dispatch expiry, lost acknowledgments, late receipts and process restart/recovery **without a second effect**. Verify actual durable state rather than only printed success. Synthetic planning is acceptable for offline tests; genuine external side effects need separate permission.

## Agent Work Protocol

Before changing code:

1. Read this `AGENTS.md`, other local instructions and actual competition requirements.
2. Verify the exact pinned dependency, installed public API, package version and lockfile.
3. Read the shared Runtime's `examples/consumer/app.py`, v0.3.0 handoff and adapter guide.
4. Propose the smallest **consumer-specific** implementation and targeted tests.
5. Flag missing capabilities rather than inventing public APIs or modifying the shared Runtime.

During development, preserve existing project state and security constraints. Keep changes scoped; use safe synthetic tests by default. **Do not commit, push, tag, release, deploy or run real external effects unless separately instructed.**

**Guiding rule: Build the Hackathon application; reuse the pinned Agentic Intent Gate Runtime.**


---

# CrowdQuest AI — Competition-Specific Instructions

## Authority, provenance, and current phase

The complete upstream consumer template above is preserved verbatim. Its safety
requirements take precedence over any weaker project suggestion. Source:
https://github.com/miku-wwl/agentic-intent-gate/blob/7f635adf13f105cf4ed8408766c47e612048773c/docs/AGENTS-dependence.md
Source commit: `7f635adf13f105cf4ed8408766c47e612048773c`.
Source Git blob: `f14307dcc124a0eaefc24dbc3cb64643f35b1fa9`.
See `docs/aig-upstream.json` for byte length and digest verification.
The AIG developer-only root instructions were not substituted.

Current authorization is Phase 0 only: documentation, dependency installation,
non-destructive baseline validation, and one Phase 0 commit/push to
`miku-wwl/crowdquest-ai` main. Preserve the existing README-only initial history.
This explicit user authorization satisfies the upstream separate-instruction rule
for that commit/push only. Do not begin Phase 1, modify AIG or another repository,
force-push, tag, release, deploy, contact organizers, or submit to Devpost.

## Twitch input and approval

- Use authenticated Twitch EventSub WebSocket sessions and narrow OAuth scopes;
  validate token identity, channel, subscription type/version/status, event shape,
  and message timestamp/IDs. Do not confuse WebSocket authentication with webhook
  HMAC verification. If webhook transport is introduced, review its HMAC separately.
- Treat every viewer message, display name and model response as untrusted data.
  Bound input sizes; render text only; never interpret chat as instructions, HTML,
  executable code, tool definitions, credentials, authorization or prompt policy.
- Deduplicate delivery IDs and chat message IDs durably before creating a candidate.
  Apply per-viewer, per-channel and global rate/queue limits; fail closed on loss of
  deduplication or ownership state. Reconnect does not grant permission to replay.
- Validate one bounded challenge against application-owned schemas and AIG's flat,
  closed scalar ToolCapability contract. Model output cannot choose trusted tool
  identity, target, scope, credentials, execution budget, binding or grant decision.
- Only an authenticated owner of the configured channel may explicitly approve or
  reject the exact current Plan. Bind approval to that Run/version and preview;
  edits and stale approvals require fresh review. Protect sessions, origin and CSRF.
- Human Approval never authorizes execution. A separate trusted policy must issue
  independent Authorization for the exact admitted Action and frozen binding.
  No viewer or browser receives a runtime capability token.

## Effect and overlay boundaries

- Register exactly one reviewed SIDE_EFFECT tool: `enqueue_overlay_challenge`,
  version `1`, for a fixed operator-configured channel target, persisted UUIDv4
  scope, adapter and binding revision. Register only through public startup APIs.
- Retain the default five-second adapter budget. No extended profile is approved.
  One approved Plan has one action step. No dynamic tools, arbitrary shell calls,
  game modification, arbitrary OBS control or multi-agent orchestration.
- The trusted executor performs only short durable queue admission into a separate
  consumer-owned SQLite effect/job/receipt store. Atomically bind the effect key,
  full payload digest, all binding fields, job and unique admission receipt.
- A separate worker performs longer overlay delivery. Restrict OBS Browser Source
  to escaped bounded display text/countdowns using a read-only per-channel overlay
  credential. It cannot approve, authorize, execute tools or change OBS scenes.
- Report AIG Action/admission state and worker/browser rendering state separately.
  A queue receipt proves admission only. Browser delivery is not rendering proof;
  an actual overlay acknowledgement is required for a rendering claim.
- Preserve durable receipts, owner fencing and audit correlation without exposing
  secrets, private state, full chat history or source code to the overlay/model.
- Ambiguous post-dispatch effects are terminal Unknown. Never reset, automatically
  retry, reconcile into success, or create replacement Actions to replay an Unknown
  effect. Also quarantine an admitted job whose AIG outcome is Unknown or unconfirmed;
  the worker must not render it. Lost rendering acknowledgements are separately
  ambiguous; do not replay them. Preserve history for operator inspection.
- Keep Twitch OAuth, provider credentials, runtime capability, dashboard session
  and overlay credential separate. Give executors no approval or control-plane
  credentials. Private persistent state is outside the public repository.

## Competition evidence and publication

- Follow the official rules/FAQ and `docs/SUBMISSION_CHECKLIST.md`. CrowdQuest is
  new competition-specific work; AIG is a disclosed pre-existing MIT dependency.
  Whether the entrant's own pre-existing runtime is permitted remains UNVERIFIED.
  Never claim complete eligibility while this or personal eligibility is unresolved.
- Record Codex Session IDs and dated development evidence without publishing raw
  session logs, prompts, source secrets, credentials or personal information.
- Label PASS, PARTIAL, BLOCKED and NOT_RUN truthfully. Dependency checks are not
  runtime integration, human approval, real Twitch, provider, OBS or browser proof.
- Do not contact an organizer without separate authorization. A saved Devpost draft
  is not a submission. Future video/upload/submission work requires Phase 4 authority.
- After Phase 0 verification, commit/push and report, STOP for the user's next phase.

## Phase 1 authorization update — 2026-10-26

The user's subsequent Phase 1 instruction supersedes the historical Phase 0-only
authorization above. Implement and test OAuth, read-only EventSub chat intake,
durable deduplication and authenticated manual development previews; commit/push
normal scoped changes to this repository's main and verify CI. Preserve the entire
upstream template and the AIG pin. No AI Plans, Runtime construction/execution,
production Approval/Authorization, SIDE_EFFECT or Phase 2/3 work is authorized.
Live testing needs user OAuth consent and confirmation of the owned test channel.
No chat writes, moderation, organizer contact, deployment, video upload or submission.
All previews visibly say DEVELOPMENT PREVIEW — NOT APPROVED / NOT EXECUTED.
Keep live Twitch, synthetic browser tests and actual OBS evidence distinct. Stop
after Phase 1; unresolved competition eligibility stays PARTIAL/UNVERIFIED.

## Final acceptance authorization update — 2026-10-26

The user's latest request authorizes Phase 1 final engineering/security acceptance
and conditional automatic Phase 2 progression only after all mandatory Phase 1
quality gates pass. Preserve existing uncommitted diagnostic fixes and real private
data. Two final user-provided screenshots are visual evidence; do not invent local
image files or require the two historical screenshots that were explicitly excluded.
Do not redo real OAuth/pairing, start streaming, mutate credentials, send Twitch chat,
or interrupt the working live instance to force a test pass. Use temporary databases
and fixture services for destructive/fault tests. Stop on a mandatory unresolved gate
or any need for new authorization. Existing Phase 1 normal main delivery authority
continues; no core AIG changes, paid calls, deployment, release or submission.

## Controlled restart authorization update — 2026-10-26

The user explicitly authorized one controlled CrowdQuest local-service restart to
load the tested backend security fixes. Verify and back up real SQLite first;
preserve its records and existing credential values. Affect no other project.
The prior prohibition on this restart/login/pairing is superseded for this operation.
If owner login or OBS pairing is needed, provide exact steps and wait for the user
to perform them. Retain only user:read:chat, never send Twitch chat or start a stream.
Verify real recovery and distinguish controlled deduplication tests from genuine
Twitch delivery. Phase 2 remains conditional on all mandatory Phase 1 gates passing.

## Phase 2 gate update — 2026-10-26

The user completed post-start real OAuth, OBS pairing, Inbox selection, OBS rendering
and approximately 65-second preview expiry. Read-only live evidence and final Phase 1
regression corroborate the engineering gates. Original PNG archival stays PARTIAL,
using the user's explicitly accepted visual-evidence alternative. The existing
conditional Phase 2 authorization now applies to the documented local single-action
AIG integration and its tests. Preserve the working Phase 1 process; do not infer
another live restart, a real Action's Approval/Authorization, paid calls, Phase 3,
deployment or submission authority from test consent.

## Phase 3A–3D authorization update — 2026-10-26

The latest user attachment explicitly authorizes Phase 2 delivery reconciliation,
Phase 3A local real-model planning, 3B authenticated review UI, 3C fenced worker and
production overlay, and 3D local/browser/fault qualification. Normal scoped main
commits, non-force pushes and commit-specific CI verification are authorized after
local gates pass. Preserve the installed AIG pin, complete upstream prefix, fixed
tool/binding and default five-second execution budget. Use existing local Ollama
without paid requests or large downloads. Preserve real candidates and the healthy
Phase 1 process. Live restart, new OAuth/pairing, real Action consent, paid providers,
organizer contact, publication/submission and Phase 4 still need separate approval.
Complete independent local work before asking for that live activation approval.

## Phase 4 championship upgrade authorization — 2026-10-27

The user explicitly authorizes local implementation, isolated synthetic qualification,
documentation, scoped commits/non-force pushes to the verified CrowdQuest main, and
exact-commit CI for audience voting, owner-reported outcomes and broadcast design.
Their prior session completed the genuine Phase 3 single-Action E2E; record it as
session evidence without rewriting historical test reports or inventing image files.
Preserve the installed AIG pin, single tool, independent human gates and five-second
budget. New product state belongs in the consumer. All tests use temporary fixtures;
build frontend assets separately so the running service's frontend/dist is preserved.
Do not restart the real service, change real stores/credentials, repeat OAuth/pairing,
send Twitch messages or execute another real Action. Phase 4 live acceptance needs
separate permission. Prepare the demo/script and submission checklist, but do not
record/upload video, contact organizers, deploy, or submit the project.

## Phase 4.5 local OBS Admin authorization — 2026-10-28

The user authorizes a lightweight loopback-only, session/CSRF-protected OBS v5 Admin
page; isolated tests; documentation; and, after all required gates pass, scoped normal
main commit/push and exact-commit CI. The bounded real acceptance includes existing
scene switching, existing CrowdQuest source refresh and one short local recording,
stop and playable-file verification. No streaming, new Twitch events, new/replayed
AIG Actions or edits to previous acceptance evidence. Keep OBS control outside the
AIG tool registry. Do not automatically restart an active service with pending work.
OBS security-setting changes and password entry must be performed by the user; stop
at that specific setup step. Never weaken OBS authentication or expose credentials.

## Phase 4.5 OBS-free replacement authorization — 2026-10-28

The latest user attachment supersedes the OBS-required acceptance path: implement
the browser Broadcast Studio with one Canvas for presentation and native local
recording/export. Preserve in-progress OBS Admin work as optional compatibility;
do not request OBS setup. Computer Use and all native desktop automation are
FORBIDDEN for this task. Use only coding/terminal, IAB and supported browser tests.
No new real Twitch events, AIG Actions, historical replay, streaming or publication.
Safe local startup and fixture recordings are authorized; do not restart an active
service with pending Actions or overwrite real SQLite/evidence. Scoped normal
main delivery and exact-commit CI are authorized after applicable qualification.
Keep Phase 4 historical overall PARTIAL and label synthetic/IAB footage distinctly.

## Phase 4.5.1 recovery and acceptance authorization — 2026-10-28

Preserve the interrupted EventSub changes and all historical stores/evidence. The
latest user request authorizes completing the documented reconnect URL/security and
continuous-handover fix, isolated regression, scoped normal main delivery and exact
CI. A safe restart of the verified CrowdQuest services requires intact, verified
database backups and no pending Action or active voting round. Keep the existing
private identity, AIG pin/default five-second budget and user:read:chat scope.
Use terminal and IAB only; no native desktop/OBS automation, tunnels or substitute
live browser driver. Distinguish user-reported IAB rendering from agent automation.
Before any fresh live events, finish readiness checks and obtain the user's explicit
GO. Then at most two genuine suggestions, one round, one account vote, one real Plan
and one Action may be used. Show the exact Plan/version and wait for explicit human
approval; retain independent Approval, Admission, Authorization and Execute gates.
Ask for the factual owner outcome when not observed; never fabricate completion.
No historical replay, second uncertain Execute, extra scopes, streaming, upload,
deployment, competition submission or automatic Phase 5 work is authorized.
