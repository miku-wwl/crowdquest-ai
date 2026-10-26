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
| P1-02 | `!quest` validation and duplicate suppression survive restart | Parser tests and persistent unique candidate | PASS_SYNTHETIC; SQLite rows and fresh process |
| P1-03 | Invalid channel/replay/overload does not create proposals | Negative intake tests and bounded queue | PASS_SYNTHETIC |
| P1-04 | Owner-selected escaped development content renders | Real browser and OBS observation; no AI/AIG claim | PASS; USER_OBSERVED_REAL_E2E and supplied visual evidence |
| P1-05 | Phase 0 regression, Phase 1 tests/locks and pushed CI pass | Commit-specific Actions result | See Phase 1 evidence and delivery report |
| P2-01 | Exact approved Plan produces one separately authorized action | Persistent Run/Approval/Action/claim/receipt | NOT_RUN |
| P2-02 | No approval/Authorization or wrong identity denies effects | Negative tests and zero queue insert count | NOT_RUN |
| P2-03 | Duplicate/conflicting/concurrent requests stay safe | Real SQLite rows/receipts, race tests | NOT_RUN |
| P2-04 | Crash/lost ack/late outcome becomes Unknown without replay | Restart tests; effect count unchanged | NOT_RUN |
| P2-05 | Unknown/unconfirmed admission never releases worker job | Job quarantine and gateway-read tests | NOT_RUN |
| P3-01 | Real provider yields one bounded valid domain Plan | Redacted real-provider trace; strict validation | NOT_RUN |
| P3-02 | Model injection cannot select identity/authority/extra actions | Adversarial schema/semantic and provider cases | NOT_RUN |
| P3-03 | Real owner review is required, rejection has no effect | Authenticated browser actions; CSRF/owner tests | NOT_RUN |
| P3-04 | Durable admission and rendering are separate, accurate states | Correlated AIG receipt/job/render ack | NOT_RUN |
| P3-05 | Reload/disconnect cannot replay uncertain rendering | Fenced dispatch and browser recovery tests | NOT_RUN |
| P3-06 | Complete flow works on genuine Twitch and OBS | Live IDs, human approval, receipt, actual OBS footage | NOT_RUN |
| P4-01 | Fresh setup and judge access work | Clean-machine run evidence; accessible source | NOT_RUN |
| P4-02 | Description, principal session ID and video meet requirements | English materials, public/unlisted YouTube <3 min | NOT_RUN |
| P4-03 | Final Devpost submission received within period | Submitted confirmation and timestamp | NOT_RUN |

Phase 1 remains PARTIAL for final security activation and archival; real display passed.
Phase 2 is conditionally authorized but blocked until mandatory Phase 1 gates pass.
No acceptance row authorizes future work. Product release
or submission cannot be called PASS while its mandatory real evidence is missing.
