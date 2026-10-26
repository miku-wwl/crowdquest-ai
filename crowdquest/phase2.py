"""Opt-in single-action composition using only the installed public AIG API."""

import json
import re
from contextlib import closing, contextmanager
from pathlib import Path
from uuid import uuid4

from agentic_intent_gate.runtime import (
    ActionCommand,
    AdmissionCommand,
    ApprovalChoice,
    ApprovalDecisionRequest,
    BoundCapabilityAuthorization,
    CapabilityVerifier,
    ExecutableRegistry,
    ExecutionSpec,
    Intent,
    ToolBinding,
    ToolCapability,
    open_runtime,
    provision_capability,
)

from .admission import AdmissionExecutor, AdmissionStore, uuid4_string
from .challenges import ARGUMENT_SCHEMA, Challenge, OfflineChallengeProvider, challenge_semantics
from .config import ROOT


def binding_for(owner_id, scope):
    if not re.fullmatch(r"[1-9][0-9]{0,24}", owner_id) or not uuid4_string(scope):
        raise ValueError("PHASE2_IDENTITY")
    return ToolBinding(
        "enqueue_overlay_challenge",
        "1",
        "crowdquest-overlay",
        "overlay-admission-v1",
        "twitch-channel-" + owner_id,
        scope,
    )


def private_directory(directory):
    directory = Path(directory).resolve()
    if directory.is_relative_to(ROOT):
        raise ValueError("PHASE2_STATE_MUST_BE_PRIVATE")
    return directory


def provision(directory, owner_id):
    """Operator-only, exclusive provisioning; never called by HTTP or an executor."""
    directory = private_directory(directory)
    binding = binding_for(owner_id, str(uuid4()))
    try:
        # Python 3.13 applies a user/admin-only DACL for 0o700 on Windows.
        # Reject even empty existing directories: mkdir's privacy mode would be ignored.
        directory.mkdir(parents=True, exist_ok=False, mode=0o700)
    except FileExistsError:
        raise ValueError("PHASE2_DIRECTORY_NOT_EMPTY") from None
    provision_capability(directory / "capability")
    (directory / "identity.json").write_text(json.dumps(vars(binding)), encoding="utf-8")
    AdmissionStore.provision(directory / "overlay.sqlite3", binding)


class ChallengeService:
    def __init__(self, runtime, store, binding, owner_id, principal):
        self.runtime, self.store, self.binding = runtime, store, binding
        self.owner_id, self._principal = owner_id, principal

    async def create(self, challenge):
        challenge = Challenge.model_validate(challenge)
        return await self.runtime.run_service.create(Intent(challenge.model_dump_json()))

    def run(self, run_id):
        return self.runtime.run_service.get(run_id)

    def decide(self, run_id, expected_version, decision, *, reviewer_id):
        if reviewer_id != self.owner_id:
            raise ValueError("OWNER_REQUIRED")
        run = self.runtime.run_service.decide(
            run_id,
            ApprovalDecisionRequest(
                ApprovalChoice(decision),
                expected_version,
            ),
        )
        # If this audit write fails, admission remains denied even if AIG approval committed.
        self.store.record_review(run, reviewer_id, decision)
        return run

    def admit(self, run_id, expected_version, key):
        self.store.require_review(self.run(run_id), self.owner_id)
        action = self.runtime.gateway.admit(
            AdmissionCommand(
                run_id,
                expected_version,
                self._principal.subject_id,
                key,
            ),
            self._principal,
        ).action
        self.store.link(action, ExecutionSpec.from_compiled(action.spec))
        return action

    def authorize(self, action_id, expected_version, key):
        action = self.runtime.gateway.get(action_id, self._principal)
        self.store.require_review(self.run(action.spec.run_id), self.owner_id)
        return self.runtime.gateway.authorize(
            ActionCommand(
                action_id,
                expected_version,
                key,
            ),
            self._principal,
        ).action

    def refresh(self, action_id):
        action = self.runtime.gateway.get(action_id, self._principal)
        self.store.confirm(action, ExecutionSpec.from_compiled(action.spec))
        return action

    async def execute(self, action_id, expected_version, key, *, deadline=None):
        action = self.runtime.gateway.get(action_id, self._principal)
        self.store.require_review(self.run(action.spec.run_id), self.owner_id)
        self.store.link(action, ExecutionSpec.from_compiled(action.spec))
        try:
            await self.runtime.gateway.execute(
                ActionCommand(
                    action_id,
                    expected_version,
                    key,
                ),
                self._principal,
                deadline=deadline,
            )
        finally:
            # A public durable read is the only source of success; uncertainty quarantines.
            action = self.refresh(action_id)
        return action

    def snapshot(self, action):
        job = self.store.job(action.effect_key)
        return {
            "action": action.snapshot(),
            "admission": None
            if job is None
            else {
                "job_id": job["job_id"],
                "receipt": job["receipt"],
                "state": job["state"],
            },
            "rendering": "NOT_RUN",
        }


@contextmanager
def challenge_runtime(
    directory,
    owner_id,
    *,
    predecessor_stopped=False,
    provider=None,
    executor_factory=AdmissionExecutor,
):
    directory = private_directory(directory)
    saved = json.loads((directory / "identity.json").read_text("utf-8"))
    binding = binding_for(owner_id, saved["execution_scope"])
    if saved != vars(binding):
        raise ValueError("PHASE2_IDENTITY_MISMATCH")
    store = AdmissionStore(directory / "overlay.sqlite3", binding)
    with closing(store.connect()) as db:
        store.check_identity(db)
    token = (directory / "capability").read_text("ascii")
    verifier = CapabilityVerifier(
        token,
        subject_id="twitch-owner-" + owner_id,
        binding=binding,
        operations=("read", "admit", "authorize", "execute"),
    )
    policy = BoundCapabilityAuthorization(verifier, policy_revision="crowdquest-owner-policy-v1")
    with open_runtime(
        gate_path=directory / "gate.sqlite3",
        provider=provider if provider is not None else OfflineChallengeProvider(binding),
        capability=ToolCapability(
            binding,
            "Admit one reviewed display challenge",
            ARGUMENT_SCHEMA,
            semantic_rule=challenge_semantics,
        ),
        registry=ExecutableRegistry(executor_factory(store), binding=binding),
        verifier=verifier,
        policy=policy,
        predecessor_stopped=predecessor_stopped,
    ) as runtime:
        service = ChallengeService(
            runtime, store, binding, owner_id, verifier.verify("Bearer " + token)
        )
        for action_id in store.action_ids():
            service.refresh(action_id)  # Read-only gate confirmation, never execute/retry.
        yield service


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Provision fresh private Phase 2 state only")
    parser.add_argument("directory", type=Path)
    parser.add_argument("--owner-id", required=True)
    args = parser.parse_args()
    provision(args.directory, args.owner_id)
    print("PHASE2_PROVISIONED=YES; no Run, Approval, Authorization or effect was created")
