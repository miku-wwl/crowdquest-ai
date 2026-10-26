# Phase 4 engineering acceptance

Date: 2026-10-27, Pacific/Auckland. Project: CrowdQuest AI.
Git baseline: `369ec862465705225f8781dd867ecd23fdf90028`, clean before work.
**Local Phase 4A/4B/4C/4D qualification PASS; complete Phase 4 status PARTIAL pending
separately authorized genuine Twitch/voting/outcome/OBS acceptance.** Remote CI receipt
is added after the exact implementation commit is delivered; no old CI proves new code.

## Implemented and measured gates

| Gate | Local result and evidence |
| --- | --- |
| Audience voting | PASS: exactly two valid frozen candidates, owner-only Draft/Open/Closed/Cancelled, one unfinished round/channel, server expiry/explicit close, equal totals require owner choice. |
| EventSub accounting | PASS: existing source/session/type/channel/time validation, exact !vote 1/2 parsing; one transaction binds delivery/message dedup and a vote. Duplicate voter/delivery/conflict/late commands cannot inflate totals. |
| Privacy and isolation | PASS: HMAC-SHA256 voter pseudonyms scoped to channel/round; separate retained private key; missing/replaced key rejects startup. No raw voter IDs in vote records or overlay data; channel-scoped audit and identity checks. |
| Concurrency/recovery | PASS: 40 concurrent distinct voters, duplicate-viewer race, close CAS race, write contention, real child-process exit before/after COMMIT, restart tally/deadline preservation and clock rollback handling. |
| Winner binding | PASS: persisted winner/candidate text snapshot, changed binding denied; model Run provenance records trusted round; no votes call AIG consent/execution. |
| AIG safety | PASS: unchanged installed v0.3.0 pin, 45 source files match distribution RECORD; same four-field schema, sole enqueue_overlay_challenge/1 and five-second default. Existing missing/stale/wrong-identity/Unknown/race/restart tests retained. |
| Outcomes | PASS: one Completed/Failed/Skipped owner report per successful acknowledged challenge, exact job/payload/receipt match, duplicate/lost-commit-ACK safety, restart and eight-second presentation expiry/no replay. AIG Succeeded remains unchanged. |
| Broadcast UX | PASS: actual Chromium 1280x720; both 280-character CJK suggestions fit; 80/240-character Plan fields pass original browser regression; native vote meters, server-anchored timer, HTML/body transparency, reduced-motion rule and no clipped text/viewport overflow. |
| Complete synthetic flow | PASS: real Chromium + installed AIG + real temporary SQLite + distinct authenticated worker. Synthetic chat/model/consent; 2:1 votes, winning Plan, four distinct operations, exactly one executed Action/job/render, two overlays, owner result and reload suppression. |

Voting bounds: 15/30/60-second owner-selected durations, 60 accepted votes/round/second,
120 globally/second, six created rounds/channel/minute, 500 rounds, inherited 10,000
delivery dedup cap and 20,000 vote cap. Caps reject work; they never silently delete
history. These are reviewed local demo limits, not an unlimited production claim.

## Commands, counts and exit codes

Baseline before features: 163 backend tests, 16 frontend tests (exit 0).
Final locked qualification uses a separate `.artifacts/phase4/venv` so the running
service's original `.venv` is preserved. Set `$env:UV_PROJECT_ENVIRONMENT` to that
absolute directory before `uv sync --locked --python 3.13`; alternatively use its
Python directly, as in the actual recorded runs below.

| Check | Actual result |
| --- | --- |
| isolated Python `-m pytest -q` | 203 passed, exit 0, 98.93 seconds; one existing Starlette/HTTPX deprecation warning |
| `npm --prefix frontend run test` | 25 passed across 3 files, exit 0 |
| `npm --prefix frontend run typecheck` | exit 0 |
| `npm --prefix frontend run lint` | exit 0; TypeScript unused/fallthrough semantic checks |
| `npm --prefix frontend run format:check` | exit 0; Prettier 3.9.10 |
| `npm --prefix frontend run build:test` | exit 0; TypeScript and Vite build into isolated assets, not live frontend/dist |
| isolated Python `-m ruff check crowdquest tests scripts` | exit 0 |
| isolated Python `-m ruff format --check crowdquest tests scripts` | exit 0; 53 files |
| `uv lock --check --offline` | exit 0; exact immutable AIG Git source retained |
| `uv pip check --python` isolated Python | exit 0; 43 installed distributions compatible |
| isolated Python `-I scripts/verify_baseline.py --environment .artifacts/phase4/venv` | exit 0; package/version/source/public API/template and 45 installed AIG source hashes verified |
| isolated Python `-m tests.browser_e2e` | exit 0; actual Chromium with synthetic OAuth/chat, legacy Phase 1 retained |
| isolated Python `-m tests.phase3_browser_e2e` | exit 0; actual Chromium + separate worker; observed expiry EXPIRED, two deliberately distinct fixture jobs |
| isolated Python `-m tests.phase4_browser_e2e --output-dir docs/evidence/phase4` | exit 0; actual Chromium, transparent/reduced-motion/max Unicode, one intended fixture execution |
| npm dependency audit | exit 0; zero reported advisories |
| isolated Python dependency audit | exit 0; zero known vulnerabilities among auditable packages. AIG is skipped by PyPI audit because it is Git-only; immutable-source integrity is separately verified, not a CVE certification. |
| Source/diff/secret review | recorded before staging/delivery in local qualification JSON |

The three browser suites cannot prove real Twitch, real-model inference, genuine human
consent or actual OBS. Those operations were not repeated. No new real Action was run.

## Security finding and remediation

Initial pip-audit found three filelock 3.32.7 advisories:
[CVE-2026-112940](https://github.com/tox-dev/filelock/security/advisories/GHSA-v4x8-3wr5-3wq8),
[CVE-2026-112913](https://github.com/tox-dev/filelock/security/advisories/GHSA-9vhv-jxww-xfm5),
[CVE-2026-112907](https://github.com/tox-dev/filelock/security/advisories/GHSA-567q-5qvw-pf92).
They concern SQLite reader/writer locks and soft-lock paths. The current Windows
FileLock resolves to WindowsFileLock; the application does not select those other
types. Nevertheless the consumer requirement was raised to >=4.2.1,<5 and lockfile
resolved 4.2.4. AIG has no filelock dependency constraint and its immutable source/pin
was preserved. Full regression and all browser suites were repeated against the new
isolated environment. The live environment was deliberately not changed.

## Genuine synthetic screenshots

Captured from actual Chromium execution; no generated imagery or reconstructed UI:

- [Director studio](evidence/phase4/synthetic-director-studio.png)
- [Vote totals/instructions](evidence/phase4/synthetic-voting.png)
- [Audience-selected challenge](evidence/phase4/synthetic-chat-selected-challenge.png)
- [Owner-reported outcome](evidence/phase4/synthetic-owner-outcome.png)
- [Two maximum-length CJK candidates](evidence/phase4/synthetic-voting-max-unicode.png)

Images were visually reviewed. Alpha backgrounds are intentional for OBS composition.
Synthetic evidence labels and fixture filenames must be retained when sharing them.

## Failure history and honest limits

- The first browser attempt completed the main flow, then exposed an ambiguous label:
  Voting time matched both a selector and timer. Explicit label/selector association
  and an exact locator fixed this accessibility/test issue.
- Visual inspection exposed an opaque HTML root despite a transparent body. Root
  transparency was fixed and both HTML/body now have browser assertions.
- Maximum CJK voting text initially produced a 733px document in a 720px viewport.
  Card spacing was reduced while retaining 18px long-text size. The strict overflow
  assertion was preserved and passed; a failed diagnostic is excluded from public images.
- An initial npm argument-forwarding build command was rejected by the local npm CLI.
  The explicit build:test script succeeds and protects live frontend/dist.
- An initial audit invocation used an incompatible flag. The corrected audit revealed
  real advisories; the fixed dependency was audited and requalified. No findings ignored.

No penetration test, independent content-safety guarantee or gameplay recognition is
claimed. A trusted single-host operator remains assumed. The earlier Phase 3 real
session PASS is preserved in PHASE3-REAL-ACCEPTANCE.md; original live PNG archival is
session-only. Phase 4 live acceptance, clean-machine judging rehearsal and final video
are NOT_RUN. Organizer clarification and personal eligibility remain unverified.

The original backend PID was still present at read-only inspection. No real database,
credential or running assets were modified by development tests. A current localhost
worker process was not found at final inspection; this was not repaired because live
restart/start authority is excluded. The separate live runbook must verify/start the
worker during a specifically authorized controlled activation. No current real-instance
health or Phase 4 actual OBS PASS is inferred from the historical session.

## Delivery and next action

Commit only reviewed source/docs/synthetic images after local gates; push only the
verified HTTPS CrowdQuest main, without force. Record actual implementation-commit CI
and verify any documentation receipt commit separately. Never substitute baseline CI.
Next operational step: separately authorize controlled activation and the exact bounded
session in PHASE4-LIVE-RUNBOOK.md. No live work, organizer contact, video capture/upload,
deployment or Devpost submission was performed in Phase 4 development.
