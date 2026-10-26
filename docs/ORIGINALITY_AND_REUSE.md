# Originality and reuse disclosure

Reviewed 2026-10-26. Overall status: **PARTIAL; own pre-existing runtime eligibility UNVERIFIED**.

## Work ledger

| Category | Provenance and treatment |
| --- | --- |
| Pre-existing runtime | Agentic Intent Gate v0.3.0, MIT, commit `bb8e8fb1234128613a750bee17967b225072bb14`; released before CrowdQuest. Installed dependency only; never claimed as new competition work. |
| Consumer instructions | Complete upstream `docs/AGENTS-dependence.md` preserved in root AGENTS; source commit/blob and digests in [aig-upstream.json](aig-upstream.json). |
| New CrowdQuest work | Phase 0 requirements/baseline; Phase 1 OAuth/EventSub/intake/development preview; Phase 2 thin installed-AIG integration and consumer admission store; Phase 3 domain ModelProvider, review UI, fenced worker, rendering ledger/acknowledgement and tests. No pre-existing Twitch application code or core execution state machine was imported. Genuine Phase 3 single-Action live acceptance is PASS in the subsequent session record. Phase 4 adds new consumer voting/outcomes/broadcast UI; its live gate remains NOT_RUN. |
| Standard dependencies | Python, uv, FastAPI, Uvicorn, Pydantic, HTTPX, websockets, keyring, filelock, React, TypeScript, Vite and locked test/transitive dependencies. Respect each license; no third-party game/media assets have been added. Synthetic screenshots depict only the new app. |
| Codex assistance | This phase was authored and verified with Codex under the entrant's product direction. Session ID and commands are recorded in [PHASE0_EVIDENCE.md](PHASE0_EVIDENCE.md). |

The existing local Ollama/phi4-mini model is a pre-existing third-party inference
dependency, not entrant-authored model training. Model weights were not downloaded,
modified or committed in this work. Its bounded local inference evidence is separate
from CrowdQuest originality and competition eligibility.

The remote was created on `2026-10-25T11:22:47Z`, after submissions opened. At inspection
it contained only the initial README commit `639eabc8b6947a44048b220faea5fea4990587d1`.
The repository is not a fork (verified via GitHub metadata). That history is preserved.
No pre-existing Twitch application code or AIG source tree was imported. This audit
supports repository provenance, not independent verification of all entrant activity.

## Interpretation and unresolved questions

The [official rules](https://twitchcon-codex.devpost.com/rules), sections 4 and 11,
permit standard libraries/open-source building blocks and require new submitted work.
They do not explicitly decide whether an entrant's own pre-existing runtime qualifies
as a reusable library. MIT permission is established; competition permission remains
**UNVERIFIED**. Do not present AIG's safety framework as newly invented for this entry.

Prepared organizer question (not sent):

> May an entrant use their own previously published MIT-licensed general-purpose
> runtime, AIG v0.3.0, strictly as an immutable library dependency, while building all
> Twitch-specific application code, UI, integrations and demo during the submission
> period and clearly disclosing that runtime's prior development? Is any additional
> disclosure or restriction required?

Section 11.6 requires written clarification of perceived ambiguities before the
deadline. **Clarification is outstanding and no organizer contact is authorized.**
The entrant must separately authorize contact or submit the question themselves;
record the answer and re-evaluate eligibility before competition submission.

Personal eligibility (age/majority, legal residence, exclusions/conflicts and any team
representation), registration, ownership attestations and preferential support have
not been independently verified. Timezone alone does not prove legal residence.
The application must build upon the runtime with new audience interaction; a renamed
runtime demo does not satisfy that originality goal.

## Evidence discipline

Keep dated commits and new-versus-reused attribution through later phases. Record the
principal Codex development thread at submission time if it differs from Phase 0.
Keep raw session transcripts, tokens, personal data and private stores out of Git.
Originality, installation and live runtime behavior are separate claims.

## 2026-10-27 disclosure update

ORIGINALITY_DISCLOSURE=PASS for explicit new-versus-reused attribution. This is not an
eligibility ruling. ORGANIZER_CLARIFICATION=PENDING and PERSONAL_ELIGIBILITY=UNVERIFIED.
The new audience-voting product, outcome workflow, design and competition demo plan
are CrowdQuest consumer work; no AIG core source was modified or represented as newly
built for this event. Prepared clarification wording and submission gates are in
[Phase 5 checklist](PHASE5-SUBMISSION-CHECKLIST.md); no message has been sent.
