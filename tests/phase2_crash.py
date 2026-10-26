"""Test-owned process: crash after real local queue COMMIT, before AIG finish."""

import asyncio
import os
import sys
from pathlib import Path
from uuid import uuid4

from agentic_intent_gate.runtime import Outcome

from crowdquest.admission import AdmissionExecutor
from crowdquest.phase2 import challenge_runtime
from tests.test_phase2 import CHALLENGE


class CrashExecutor(AdmissionExecutor):
    async def execute(self, *args):
        result = await super().execute(*args)
        if result.category == Outcome.SUCCESS:
            os._exit(73)  # Only this disposable fixture process; no real Twitch service.
        return result


async def crash(directory):
    with challenge_runtime(
        directory, "123", predecessor_stopped=True, executor_factory=CrashExecutor
    ) as service:
        run = await service.create(CHALLENGE)
        run = service.decide(run.run_id, run.version, "APPROVE", reviewer_id="123")
        action = service.admit(run.run_id, run.version, str(uuid4()))
        action = service.authorize(action.action_id, action.version, str(uuid4()))
        await service.execute(action.action_id, action.version, str(uuid4()))


if __name__ == "__main__":
    asyncio.run(crash(Path(sys.argv[1])))
