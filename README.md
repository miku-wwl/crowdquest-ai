# CrowdQuest AI

**Crowd-powered challenges. Streamer-approved execution.**

AI-powered Twitch audience challenges with streamer approval, safe execution, and reliable Agent runtime.

## Current status

**Phase 0: repository, dependency baseline and architecture only. No application is implemented.**
Twitch connectivity, AI generation, human approval, AIG execution, browser/OBS rendering,
video and Devpost submission are `NOT_RUN`. Plans below describe intended behavior.

The public repository already existed with one README-only initial commit
(`639eabc8b6947a44048b220faea5fea4990587d1`, created 2026-10-25 UTC).
Phase 0 preserves that history; it does not fork or import another project's source.

Planned flow: Twitch `!quest` → validated candidate → AI Plan → streamer preview and
explicit approval → independent AIG Authorization → durable overlay-job admission →
separate worker → OBS Browser Source. Admission and rendering have separate outcomes.

## Verify the Phase 0 baseline

Install Python 3.13 and [uv](https://docs.astral.sh/uv/), then from this repository:

```powershell
uv sync --locked --python 3.13
uv lock --check --offline
uv pip check
uv run --locked python -I scripts/verify_baseline.py
git diff --check
```

There is no server start command yet. `.env.example` documents planned configuration;
no credentials or service accounts are needed for the checks above. AIG is installed
from Git at full commit `bb8e8fb1234128613a750bee17967b225072bb14`, version `0.3.0`.
`uv.lock` fixes transitive versions. The root project is intentionally not packaged.
React/TypeScript frontend tooling and WebSocket client dependencies will be selected
and locked in Phase 1; no empty application scaffold or Node installation is included.

## Competition and reuse

[Official rules](https://twitchcon-codex.devpost.com/rules) and
[FAQ/resources](https://twitchcon-codex.devpost.com/resources) were checked on
2026-10-26. Submissions are open. The rules' Pacific deadline converts to
**2026-11-03 11:00 NZDT** (2026-11-02 22:00 UTC).

AIG is a pre-existing MIT runtime, transparently reused as a dependency. Its eligibility
as the entrant's own pre-existing library is **UNVERIFIED**. Personal eligibility and
Devpost registration are also unconfirmed. See [originality and reuse](docs/ORIGINALITY_AND_REUSE.md)
and the [submission checklist](docs/SUBMISSION_CHECKLIST.md); this is not a claim of
fully verified competition eligibility. No organizer has been contacted.

## Project documents

- [Product requirements](docs/PRD.md)
- [Architecture and lifecycle](docs/ARCHITECTURE.md)
- [Security and threat model](docs/SECURITY_AND_THREAT_MODEL.md)
- [AIG integration contract](docs/AIG_INTEGRATION.md)
- [Twitch integration plan](docs/TWITCH_INTEGRATION.md)
- [Phases and gates](docs/PHASE_PLAN.md)
- [Acceptance criteria](docs/ACCEPTANCE_CRITERIA.md)
- [Decisions](docs/DECISIONS.md)
- [Phase 0 evidence](docs/PHASE0_EVIDENCE.md)

Read [AGENTS.md](AGENTS.md) before development. It preserves the entire authoritative
AIG consumer template and appends CrowdQuest constraints. No AIG core changes are allowed.

License: [MIT](LICENSE). The pre-existing dependency's original notice is retained in
[third-party notices](docs/THIRD_PARTY_NOTICES.md).
