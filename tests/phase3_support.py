"""Synthetic provider/consent helpers; real installed AIG and temporary SQLite."""

import json
from contextlib import contextmanager
from uuid import uuid4

from crowdquest.challenges import Challenge
from crowdquest.phase3 import production_runtime, provision
from crowdquest.providers import TRACE, plan_for
from tests.test_phase2 import CHALLENGE


class SyntheticProvider:
    def __init__(self, binding):
        self.binding = binding
        self.calls = 0

    async def generate_plan(self, intent, **kwargs):
        self.calls += 1
        self.last_intent = intent.text
        data = json.loads(intent.text)
        trace = TRACE.get()
        if trace is not None:
            trace.update(
                source="SYNTHETIC_TEST", provider="fixture", attempts=1, reason="FIXTURE_VALIDATED"
            )
        challenge = Challenge.model_validate(data.get("manual", CHALLENGE))
        return plan_for(self.binding, challenge)


@contextmanager
def product(directory, *, time_values=None, provider_factory=SyntheticProvider, **kwargs):
    if not directory.exists():
        provision(directory, "123")
    clocks = (
        {}
        if time_values is None
        else {"monotonic": lambda: time_values[0], "clock": lambda: time_values[1]}
    )
    with production_runtime(
        directory,
        "123",
        predecessor_stopped=True,
        provider_factory=provider_factory,
        **clocks,
        **kwargs,
    ) as service:
        yield service


async def succeeded(service, *, challenge=None):
    candidate = {"id": str(uuid4()), "suggestion": "Synthetic viewer suggestion"}
    proposal = await (
        service.generate(candidate)
        if challenge is None
        else service.manual(candidate["id"], challenge, 0)
    )
    run = proposal["run"]
    reviewed = service.decide(run["run_id"], run["version"], "APPROVE", "123")
    action = service.admit(reviewed.run_id, reviewed.version, str(uuid4()))
    action = service.authorize(action.action_id, action.version, str(uuid4()))
    action = await service.execute(action.action_id, action.version, str(uuid4()))
    return candidate, action


def tick(service, worker=None):
    worker = worker or str(uuid4())
    service.renderer.tick(worker, service.renderer.boot)
    return worker
