# Acceptance criteria and evidence matrix

PASS means the stated check actually ran and met its condition. PARTIAL means only
part is evidenced; BLOCKED names a prerequisite failure; NOT_RUN means no execution.
Dependency checks never prove product or human behavior. Current evidence is linked
from [PHASE0_EVIDENCE.md](PHASE0_EVIDENCE.md) and [PHASE1_EVIDENCE.md](PHASE1_EVIDENCE.md).

| ID / phase | Acceptance condition | Required evidence | Current evidence |
| --- | --- | --- | --- |
| P0-01 | Existing fresh public target inspected; history preserved; MIT added | GitHub metadata, initial ancestor and final SHA | See Phase 0 evidence |
| P0-02 | Official rules/FAQ read; period and Pacific→NZ deadline verified | Source links/date, timezone conversion | PASS |
| P0-03 | Full authoritative consumer template preserved with traceable source | Prefix Git blob/SHA-256; separate project suffix | See baseline JSON |
| P0-04 | Tag peels to pin; installed v0.3.0 isolated; lock consistent | tag/ref, direct URL, installed path, uv checks | See baseline JSON |
| P0-05 | All required product/security/integration/phase/submission docs | Required-file baseline check and review | See baseline JSON |
| P0-06 | No secrets/private state staged; authorized commit/push verified | Diff/ignore/secret checks; matching remote main | See Phase 0 evidence |
| P0-07 | CI actually completes on pushed commit | Commit-specific workflow URL/conclusion | See remote Actions |
| P0-08 | Material eligibility questions resolved before submission | Entrant checks and organizer written answer | PARTIAL / reuse UNVERIFIED |
| P1-01 | Real authenticated channel.chat.message v1 received | Redacted live ID/channel/time and subscription | PASS; final-real-chain.json |
| P1-02 | `!quest` validation and duplicate suppression survive restart | Parser tests and persistent unique candidate | PASS; controlled SQLite duplicate/process tests plus preserved real rows after authorized start |
| P1-03 | Invalid channel/replay/overload does not create proposals | Negative intake tests and bounded queue | PASS; SYNTHETIC_TEST |
| P1-04 | Owner-selected escaped development content renders | Real browser and OBS observation; no AI/AIG claim | PASS; USER_OBSERVED_REAL_E2E and supplied visual evidence |
| P1-05 | Phase 0 regression, Phase 1 tests/locks and pushed CI pass | Commit-specific Actions result | See Phase 1 evidence and delivery report |
| P2-01 | Exact approved Plan produces one separately authorized action | Persistent Run/Approval/Action/claim/receipt | PASS; installed AIG/actual temporary SQLite, synthetic proposal/consent |
| P2-02 | No approval/Authorization or wrong identity denies effects | Negative tests and zero queue insert count | PASS; controlled core/consumer/HTTP denials |
| P2-03 | Duplicate/conflicting/concurrent requests stay safe | Real SQLite rows/receipts, race tests | PASS; receipt/conflict tests and eight actual SQLite contender threads |
| P2-04 | Crash/lost ack/late outcome becomes Unknown without replay | Restart tests; effect count unchanged | PASS; actual disposable process crash, lost ack, shortened deadline |
| P2-05 | Unknown/unconfirmed admission never releases worker job | Job quarantine and gateway-read tests | PASS; pending/Unknown job quarantine and separate worker denial tests |
| P3-01 | Real provider yields one bounded valid domain Plan | Redacted real-provider trace; strict validation | PASS; three actual local Ollama/AIG probes, no real Twitch/Action |
| P3-02 | Model injection cannot select identity/authority/extra actions | Adversarial schema/semantic and provider cases | PASS; host-owned scaffold, controlled negatives and real bounded probe; wording safety still needs human review |
| P3-03 | Real owner review is required, rejection has no effect | Authenticated browser actions; CSRF/owner tests | PASS; tests plus explicit user approval/authorization of the exact live Action; see PHASE3-REAL-ACCEPTANCE.md |
| P3-04 | Durable admission and rendering are separate, accurate states | Correlated AIG receipt/job/render ack | PASS; separate receipt/ACK and actual native OBS observation in the real session |
| P3-05 | Reload/disconnect cannot replay uncertain rendering | Fenced dispatch and browser recovery tests | PASS; controlled worker/process/clock/ack tests and actual Chromium |
| P3-06 | Complete flow works on genuine Twitch and OBS | Live IDs, human approval, receipt, actual OBS footage | PASS for one authorized Action; session-only image observations, no invented local archive |
| P4A | Voting is durable, bounded and cannot grant execution authority | Transaction, concurrency, restart and Chromium tests | Local PASS; live Phase 4 NOT_RUN; PHASE4-ACCEPTANCE.md |
| P4B | One immutable owner outcome displays without redispatch | Receipt/ACK linkage, duplicate/lost-ack/restart tests, Chromium | Local PASS; live Phase 4 NOT_RUN |
| P4C | Transparent readable broadcast states within 1280x720 | Actual Chromium maximum text, timers, reduced motion and screenshots | Local PASS; actual Phase 4 OBS NOT_RUN |
| P4D | Full existing regression, dependencies and integrity retained | 203 backend / 25 frontend, three browser suites, static/security checks | Local PASS; exact-commit CI recorded in PHASE4-ACCEPTANCE.md |
| P5-01 | Fresh setup and judge access work | Clean-machine run evidence; accessible source | NOT_RUN |
| P5-02 | Description, principal session ID and video meet requirements | English materials, public YouTube <3 min | PARTIAL; English storyboard/checklist prepared, recording/upload NOT_RUN |
| P5-03 | Final Devpost submission received within period | Submitted confirmation and timestamp | NOT_RUN |

Phase 1 engineering gates pass after the user's explicit post-start manual acceptance
and final regression. Original PNG archival remains PARTIAL; the user-approved visual
evidence alternative satisfies the OBS observation criterion without fabricated files.
Phase 2's conditional prerequisite is satisfied; its own quality gates remain separate.
Phase 2 remote delivery/CI at edcefa7 is PASS. The subsequent genuine Phase 3 session
passed the scoped human/OBS gates; see [real session record](PHASE3-REAL-ACCEPTANCE.md).
New Phase 4 live voting/outcome acceptance remains separate and NOT_RUN. Competition eligibility and
entrant-owned runtime reuse clarification still block submission readiness.
No acceptance row authorizes future work. Product release
or submission cannot be called PASS while its mandatory real evidence is missing.

## Current Phase 4.5 status — reviewed 2026-10-30

- **Phase 4.5.5:** delivery/ACK implementation and exact-commit CI are recorded in
  [the reliability report](PHASE455-STUDIO-DELIVERY-ACK-RELIABILITY.md). A genuine
  native background-tab retest remains pending; synthetic tests do not establish it.
- **Phase 4.5.6:** implementation and CI are recorded in
  [the dashboard history note](PHASE456-DASHBOARD-HISTORY-CLEANUP.md). A user-provided
  screenshot shows the clean view; read-only SQLite evidence confirms persistent
  watermarks and retained history. The owner's login/click was not independently
  observed. New real post-clear Twitch-to-Studio acceptance is NOT_RUN.
- Historical candidates, votes, Actions, receipts, render records and UNKNOWN outcomes
  remain preserved. This display reset grants no authority to replay historical work.
