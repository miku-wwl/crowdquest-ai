# Phase 5 submission readiness

Reviewed 2026-10-30 against the [Official Rules](https://twitchcon-codex.devpost.com/rules)
and [Devpost FAQ/resources](https://twitchcon-codex.devpost.com/resources). The rules
set the deadline at **2026-11-02 14:00 Pacific = 2026-11-03 11:00 NZDT**. The FAQ says
YouTube Unlisted is acceptable; Private videos cannot be viewed by judges. Internal
target: 2026-11-02 18:00 NZDT. No upload or submission is authorized by this checklist.

## Engineering and product evidence

- [x] Phase 1 engineering and installed AIG integration are recorded in their dated reports.
- [x] Genuine Phase 3 single-Action session is recorded in [its acceptance report](PHASE3-REAL-ACCEPTANCE.md).
- [x] Phase 4 local voting/outcome/broadcast qualification and commit-specific CI are recorded in [Phase 4 acceptance](PHASE4-ACCEPTANCE.md); **overall Phase 4 remains PARTIAL**.
- [x] Phase 4.5.5 delivery/ACK implementation and CI qualification are recorded in [its report](PHASE455-STUDIO-DELIVERY-ACK-RELIABILITY.md).
- [ ] Accept a genuine native background-tab retest for Phase 4.5.5; the synthetic/two-tab workaround does not establish that gate.
- [x] Phase 4.5.6 Clear Demo History implementation is pushed and CI-qualified. A user-provided screenshot shows the clean view, and read-only database evidence confirms persistent watermarks with old rows retained. The owner's login/click was not independently observed. See [current feature note](PHASE456-DASHBOARD-HISTORY-CLEANUP.md).
- [ ] Complete a new real post-clear Twitch suggestion/vote-to-Broadcast-Studio E2E. It was **NOT_RUN** at this review. Do not infer it from EventSub readiness or synthetic browser tests.
- [ ] Rehearse fresh-machine Windows installation and judge access without exposing private credentials.

## Eligibility, ownership and disclosure

- [x] Distinguish new CrowdQuest Twitch/product work from the pre-existing MIT AIG runtime.
- [ ] Obtain written clarification about using the entrant's own pre-existing AIG runtime.
- [ ] Owner confirms age/majority, eligible legal residence and official section 3 exclusions/conflicts.
- [ ] Confirm Devpost registration/team representation, IP/media/privacy rights and absence of prohibited preferential support. Do not infer legal residence from timezone.

Prepared organizer question (NOT SENT):

> May I use my own previously published MIT-licensed general-purpose runtime, Agentic Intent Gate v0.3.0, as an unchanged pinned library, while building all Twitch-specific CrowdQuest application code, voting, UI, integrations and demo during this competition? I will disclose the runtime's prior development and MIT license. Is that permitted, and is any further disclosure required?

`ORIGINALITY_DISCLOSURE=PASS` means attribution is explicit; it is not an eligibility ruling. `ORGANIZER_CLARIFICATION=PENDING`, `PERSONAL_ELIGIBILITY=UNVERIFIED`, and `COMPETITION_ELIGIBILITY=UNVERIFIED`. The owner must authorize or personally send any question; no organizer was contacted here.

## Demo and submission materials

- [ ] English project description explains features, actual Codex use, local-model provenance, independent human gates and verified limits.
- [x] English **2:45** OBS-free [storyboard/runbook](PHASE5-DEMO-STORYBOARD.md) prepared; it remains a plan, not recorded evidence.
- [ ] Record an actual demo under 3 minutes showing Twitch functionality and how the project was built with Codex. Use Snipping Tool desktop-region recording for the real Twitch/Dashboard/Studio flow; Studio WebM is optional and Canvas-only. Label any synthetic shots.
- [ ] If a real Action is included, obtain separate fresh owner authorization and execute it at most once. Never replay historical `UNKNOWN` or `EXPIRED` Actions.
- [ ] Verify media, game footage and trademarks are owner-created, licensed or explicitly permitted. Redact unrelated account/private content.
- [ ] Separately authorize YouTube upload. The FAQ permits Unlisted, but Private videos are not viewable by judges. Verify the link while logged out.
- [ ] Verify the public repository URL, source/assets/setup instructions and all links as a judge.
- [ ] Use principal Codex thread ID `01a172e3-9804-73d1-87d8-4e01f1f75043`, unless the owner verifies another thread contains most of the project work.
- [ ] Owner reviews all Devpost fields, incorporated terms and media rights; obtain separate explicit final-submit consent.
- [ ] Observe the actual Devpost **Submitted** confirmation and timestamp before claiming submission PASS. A draft, push or video upload is not a submission.

`SUBMISSION_READINESS=PARTIAL`. Historical acceptance remains scoped; real post-clear Twitch-to-Studio evidence, native visibility retest, eligibility clarification and final submission materials remain open.
