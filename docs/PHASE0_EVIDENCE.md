# Phase 0 evidence

Evidence date: 2026-10-26, Pacific/Auckland. This is the pre-commit engineering snapshot;
the final delivery report supplies the post-push SHA and observed CI conclusion.
Overall competition compliance is **PARTIAL** while entrant checks and own-runtime
eligibility remain unresolved. Engineering checks below do not establish eligibility.

## Repository preflight

- Connected GitHub login and local GitHub CLI account: `miku-wwl`, user ID `38804125`.
- Target `miku-wwl/crowdquest-ai`: PUBLIC, main default, ADMIN access, not a fork.
- Created `2026-10-25T11:22:47Z`; only README existed at initial inspection.
- Initial local/tracking/remote main: `639eabc8b6947a44048b220faea5fea4990587d1`.
- Initial working tree clean. HTTPS origin is the requested target. No repository
  recreation, history replacement, AIG modification or unrelated-repository mutation.
- MIT notice added locally. GitHub license detection is verified after push separately.

## Official sources and time

[Rules](https://twitchcon-codex.devpost.com/rules),
[resources/FAQ](https://twitchcon-codex.devpost.com/resources) and
[overview](https://twitchcon-codex.devpost.com/) were read on the evidence date.
Submission period is active on the client's 2026-10-26 date.

Windows TimeZoneInfo `Pacific Standard Time` and `New Zealand Standard Time`
conversion confirmed both endpoints:

| Endpoint | Pacific | UTC | Auckland |
| --- | --- | --- | --- |
| Open | Oct 23 10:00 PDT | Oct 23 17:00 | Oct 24 06:00 NZDT |
| Deadline | Nov 2 14:00 PST | Nov 2 22:00 | Nov 3 11:00 NZDT |

FAQ UTC example discrepancy, personal eligibility and organizer clarification are
recorded in [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md) and
[ORIGINALITY_AND_REUSE.md](ORIGINALITY_AND_REUSE.md). No contact or entry was made.

## Dependency and instruction evidence

`git ls-remote https://github.com/miku-wwl/agentic-intent-gate.git refs/tags/v0.3.0 'refs/tags/v0.3.0^{}'`
returned tag object `28af5eccf287f70b63f20386010e5747e1511e9b` and peeled commit
`bb8e8fb1234128613a750bee17967b225072bb14`. GitHub Release is published and not draft
or prerelease. The tag is unsigned; no signing claim is made.

The complete consumer instruction source, pinned handoff, adapter guide, example,
runtime public module, package metadata and MIT notice were fetched/read from public
upstream. Reference copies are local Git metadata only, excluded from published source.
Upstream source and the example were not executed or modified.

| Check actually run | Result |
| --- | --- |
| `uv lock --python 3.13` | PASS; 25 lock records including root, 24 installed dependencies |
| `uv sync --locked --python 3.13` | PASS; isolated `.venv`, CPython 3.13.9 |
| `uv lock --check --offline` | PASS |
| `uv pip check` | PASS; 24 compatible installed packages |
| `uv run --locked python -I scripts/verify_baseline.py --output docs/evidence/phase0-baseline.json` | PASS |
| Installed distribution | `agentic-intent-gate==0.3.0` |
| Installed module | `.venv/Lib/site-packages/agentic_intent_gate/runtime.py` |
| Installed direct_url commit | `bb8e8fb1234128613a750bee17967b225072bb14` |
| Root upstream prefix | PASS; 12,127 unchanged bytes; Git blob `f14307dcc124a0eaefc24dbc3cb64643f35b1fa9` |
| Upstream prefix SHA-256 | `499f7c64b551dbfd48d640606da0b4ebb9e67c39e9544ed7eb120f08d732d10e` |
| Public API inspection | PASS; installed constructors and gateway/Run methods inspected; default budget 5 |
| Required file inventory | PASS; all 17 mandatory baseline files including lock |

Full machine-readable signatures/provenance: [phase0-baseline.json](evidence/phase0-baseline.json).
Local uv version: `0.11.16`. Hardlink fallback copied packages successfully between
drives; it did not change installed provenance. No test-count claim is made: these
are configuration/package/document checks, not CrowdQuest behavior tests.

## Development evidence and remaining checks

Codex Session ID: `01a172e3-9804-73c2-b597-8c5df928a56c`, read from this process's
`CODEX_THREAD_ID`. It identifies this Phase 0 thread; use the principal implementation
thread at final submission if later work occurs elsewhere. No raw session log is published.

Pre-commit review completed: 25 candidate files; secret/key/credential-URL pattern
checks found no matches; local Markdown targets and Python syntax passed; no application
scaffold exists. Ignore checks passed for `.env`, `.env.local`, `.venv`, node_modules,
private state and SQLite sidecars. Only the 25 explicit Phase 0 paths were staged;
`git diff --cached --check` passed. This is a bounded pattern/design review, not an
exhaustive secret detector, dependency vulnerability audit or penetration test.

CI is configured in [.github/workflows/phase0.yml](../.github/workflows/phase0.yml) with
read-only repository permission and immutable action commits. It checks locked install,
package compatibility, installed public API, template/document provenance and committed
whitespace. At this evidence snapshot, remote CI/push is **NOT_RUN**; consult the final
delivery report and commit-specific [Actions](https://github.com/miku-wwl/crowdquest-ai/actions)
for the observed post-push result.

Application scaffold, runtime construction/execution, synthetic consent workflows,
Twitch/OAuth/EventSub, model inference, authenticated human approval, browser/OBS,
video and Devpost submission: **NOT_RUN / NOT_IMPLEMENTED in Phase 0**.
No release, deployment, organizer contact or other-repository push is authorized.
