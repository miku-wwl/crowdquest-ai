"""Actual installed AIG + temporary SQLite; all proposals/decisions are SYNTHETIC_TEST."""

import asyncio
import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing, contextmanager
from dataclasses import replace
from uuid import uuid4

import pytest
from agentic_intent_gate.runtime import (
    AdmissionCommand,
    ApprovalChoice,
    ApprovalDecisionRequest,
    AttemptContext,
    CapabilityVerifier,
    ExecutableRegistry,
    ExecutionSpec,
    Outcome,
    ToolBinding,
)

from crowdquest.admission import AdmissionExecutor
from crowdquest.challenges import Challenge, OfflineChallengeProvider
from crowdquest.phase2 import challenge_runtime, provision

CHALLENGE = {
    "title": "Survive 60 seconds",
    "description": "No healing during this challenge",
    "duration_seconds": 60,
    "difficulty": "Medium",
}


@contextmanager
def core_denial(expected_code):
    try:
        yield
    except Exception as error:  # noqa: BLE001 -- assert exact denial without private AIG imports
        assert getattr(error, "code", None) == expected_code
    else:
        pytest.fail("Expected a specific public-runtime denial")


@pytest.fixture
def directory(tmp_path):
    directory = tmp_path / "phase2"
    provision(directory, "123")
    return directory


def opened(directory, **kwargs):
    return challenge_runtime(directory, "123", predecessor_stopped=True, **kwargs)


async def approved(service):
    run = await service.create(CHALLENGE)
    assert run.state.value == "AwaitingApproval"
    return service.decide(run.run_id, run.version, "APPROVE", reviewer_id="123")


async def admitted(service, authorize=True):
    run = await approved(service)
    action = service.admit(run.run_id, run.version, str(uuid4()))
    if authorize:
        action = service.authorize(action.action_id, action.version, str(uuid4()))
    return action


def count(store):
    with closing(store.connect()) as db:
        return db.execute("SELECT count(*) FROM jobs").fetchone()[0]


async def test_exact_lifecycle_receipt_and_separate_authorization(directory):
    with opened(directory) as service:
        assert service.runtime.gateway.tool_timeout_seconds == 5
        action = await admitted(service, authorize=False)
        assert action.state.value == "Pending" and count(service.store) == 0
        with core_denial("ACTION_NOT_EXECUTABLE"):
            await service.execute(action.action_id, action.version, str(uuid4()))
        assert count(service.store) == 0
        action = service.authorize(action.action_id, action.version, str(uuid4()))
        result = await service.execute(action.action_id, action.version, str(uuid4()))
        assert result.state.value == "Succeeded"
        job = service.store.job(result.effect_key)
        assert job["state"] == "ELIGIBLE"
        assert job["receipt"] == result.result["receipt_reference"]
        assert job["payload_digest"] == ExecutionSpec.from_compiled(result.spec).payload_digest()
        assert json.loads(job["binding"]) == vars(service.binding)
        assert json.loads(job["arguments"]) == CHALLENGE
        assert service.snapshot(result)["rendering"] == "NOT_RUN"
        assert count(service.store) == 1


async def test_stale_wrong_owner_reject_and_core_only_approval_denied(directory):
    with opened(directory) as service:
        run = await service.create(CHALLENGE)
        with pytest.raises(ValueError, match="OWNER_REQUIRED"):
            service.decide(run.run_id, run.version, "APPROVE", reviewer_id="999")
        with core_denial("STALE_RUN_VERSION"):
            service.decide(run.run_id, run.version - 1, "APPROVE", reviewer_id="123")
        with pytest.raises(ValueError, match="EXACT_OWNER_REVIEW_REQUIRED"):
            service.admit(run.run_id, run.version, str(uuid4()))
        rejected = service.decide(run.run_id, run.version, "REJECT", reviewer_id="123")
        assert rejected.state.value == "Rejected"
        with pytest.raises(ValueError):
            service.admit(run.run_id, rejected.version, str(uuid4()))
        second = await service.create(CHALLENGE)
        core_approved = service.runtime.run_service.decide(
            second.run_id, ApprovalDecisionRequest(ApprovalChoice.APPROVE, second.version)
        )
        with pytest.raises(ValueError, match="EXACT_OWNER_REVIEW_REQUIRED"):
            service.admit(core_approved.run_id, core_approved.version, str(uuid4()))
        assert count(service.store) == 0


async def test_owner_review_audit_write_failure_cannot_authorize_admission(directory, monkeypatch):
    with opened(directory) as service:
        run = await service.create(CHALLENGE)

        def unavailable(*args):
            raise sqlite3.OperationalError("Test-owned consumer audit write failure")

        # Only the consumer audit writer is injected; AIG source/APIs stay unchanged.
        monkeypatch.setattr(service.store, "record_review", unavailable)
        with pytest.raises(sqlite3.OperationalError):
            service.decide(run.run_id, run.version, "APPROVE", reviewer_id="123")
        assert service.run(run.run_id).state.value == "Approved"
        with pytest.raises(ValueError, match="EXACT_OWNER_REVIEW_REQUIRED"):
            service.admit(run.run_id, service.run(run.run_id).version, str(uuid4()))
        assert count(service.store) == 0


async def test_job_is_not_eligible_before_durable_aig_finish(directory):
    pending = []

    class ObservedExecutor(AdmissionExecutor):
        async def execute(self, spec, key, context):
            outcome = await super().execute(spec, key, context)
            pending.append(self.store.job(key)["state"])
            return outcome

    with opened(directory, executor_factory=ObservedExecutor) as service:
        action = await admitted(service)
        result = await service.execute(action.action_id, action.version, str(uuid4()))
        assert pending == ["PENDING_CONFIRMATION"]
        assert result.state.value == "Succeeded"
        assert service.store.job(action.effect_key)["state"] == "ELIGIBLE"


async def test_polling_inflight_admission_never_releases_or_poison_quarantines(directory):
    committed, release = asyncio.Event(), asyncio.Event()

    class BarrierExecutor(AdmissionExecutor):
        async def execute(self, spec, key, context):
            result = await super().execute(spec, key, context)
            committed.set()
            await release.wait()
            return result

    with opened(directory, executor_factory=BarrierExecutor) as service:
        action = await admitted(service)
        task = asyncio.create_task(service.execute(action.action_id, action.version, str(uuid4())))
        try:
            await asyncio.wait_for(committed.wait(), 2)
            assert service.refresh(action.action_id).state.value == "Executing"
            assert service.store.job(action.effect_key)["state"] == "PENDING_CONFIRMATION"
        finally:
            release.set()
        assert (await task).state.value == "Succeeded"
        assert service.store.job(action.effect_key)["state"] == "ELIGIBLE"


async def test_wrong_store_identity_cannot_admit_an_effect(directory):
    with opened(directory) as service:
        action = await admitted(service)
        with closing(service.store.connect()) as db:
            db.execute("UPDATE identity SET binding=?", ("{}",))
            db.commit()
        context = AttemptContext(
            str(uuid4()), asyncio.get_running_loop().time() + 1, asyncio.Event()
        )
        outcome = await AdmissionExecutor(service.store).execute(
            ExecutionSpec.from_compiled(action.spec), action.effect_key, context
        )
        assert outcome.category == Outcome.CONFIRMED_FAILURE
        assert outcome.no_effect_reason == "STORE_IDENTITY_MISMATCH"
        assert count(service.store) == 0


@pytest.mark.parametrize(
    "change",
    [
        {"target": "twitch-channel-999"},
        {"risk_class": "READ_ONLY"},
        {"tool_name": "run_shell"},
        {"tool_version": "2"},
        {"arguments": CHALLENGE | {"execution_scope": str(uuid4())}},
        {"arguments": CHALLENGE | {"duration_seconds": True}},
        {"arguments": CHALLENGE | {"description": "hello\u200bworld"}},
        {"extra_step": True},
    ],
)
async def test_untrusted_plan_cannot_select_identity_or_expand_schema(directory, change):
    class BadProvider:
        async def generate_plan(self, intent, **kwargs):
            good = json.loads(await OfflineChallengeProvider(binding).generate_plan(intent))
            for key, value in change.items():
                if key in ("target", "risk_class"):
                    good[key] = value
                elif key == "extra_step":
                    good["steps"].append(good["steps"][0])
                else:
                    good["steps"][0][key] = value
            return json.dumps(good)

    with opened(directory, provider=BadProvider()) as service:
        binding = service.binding
        run = await service.create(CHALLENGE)
        assert run.state.value == "PlanRejected"
        assert count(service.store) == 0


async def test_idempotent_admission_commands_and_execution_conflict(directory):
    with opened(directory) as service:
        run = await approved(service)
        key = str(uuid4())
        first = service.admit(run.run_id, run.version, key)
        second = service.admit(run.run_id, run.version, key)
        assert first.action_id == second.action_id
        grant_key = str(uuid4())
        authorized = service.authorize(first.action_id, first.version, grant_key)
        assert service.authorize(first.action_id, first.version, grant_key) == authorized
        execute_key = str(uuid4())
        result = await service.execute(authorized.action_id, authorized.version, execute_key)
        assert (
            await service.execute(authorized.action_id, authorized.version, execute_key) == result
        )
        with core_denial("IDEMPOTENCY_CONFLICT"):
            await service.execute(authorized.action_id, result.version, execute_key)
        assert count(service.store) == 1


async def test_concurrent_execution_has_one_durable_effect(directory):
    with opened(directory) as service:
        action = await admitted(service)

        def competing_request():
            return asyncio.run(service.execute(action.action_id, action.version, str(uuid4())))

        # Separate threads/loops actually contend for SQLite writes; async-only calls
        # with a synchronous adapter would otherwise run serially.
        results = await asyncio.gather(
            *[asyncio.to_thread(competing_request) for _ in range(8)], return_exceptions=True
        )
        assert sum(not isinstance(value, Exception) for value in results) == 1
        assert count(service.store) == 1
        assert service.refresh(action.action_id).state.value == "Succeeded"
        assert service.store.job(action.effect_key)["state"] == "ELIGIBLE"


async def test_other_verifier_subject_scope_and_missing_operation_denied(directory):
    with opened(directory) as service:
        run = await approved(service)
        for subject, scope, operations in [
            ("other-owner", service.binding.execution_scope, ("read", "admit")),
            ("twitch-owner-123", str(uuid4()), ("read", "admit")),
            ("twitch-owner-123", service.binding.execution_scope, ("read",)),
        ]:
            altered = ToolBinding(**(vars(service.binding) | {"execution_scope": scope}))
            verifier = CapabilityVerifier(
                "f" * 64, subject_id=subject, binding=altered, operations=operations
            )
            principal = verifier.verify("Bearer " + "f" * 64)
            with core_denial("ACTION_NOT_AUTHORIZED"):
                service.runtime.gateway.admit(
                    AdmissionCommand(run.run_id, run.version, subject, str(uuid4())), principal
                )
        assert count(service.store) == 0


async def test_expired_caller_deadline_has_no_effect(directory):
    with opened(directory) as service:
        action = await admitted(service)
        result = await service.execute(
            action.action_id,
            action.version,
            str(uuid4()),
            deadline=asyncio.get_running_loop().time() - 1,
        )
        assert result.state.value == "Unknown" and count(service.store) == 0


async def test_actual_queue_write_lock_is_unknown_without_retry(directory):
    class BusyExecutor(AdmissionExecutor):
        async def execute(self, *args):
            with closing(self.store.connect()) as blocker:
                blocker.execute("BEGIN IMMEDIATE")
                return await super().execute(*args)

    with opened(directory, executor_factory=BusyExecutor) as service:
        action = await admitted(service)
        result = await service.execute(action.action_id, action.version, str(uuid4()))
        assert result.state.value == "Unknown" and count(service.store) == 0


@pytest.mark.parametrize(
    "field,value",
    [
        ("tool_name", "run_shell"),
        ("target", "twitch-channel-999"),
        ("execution_scope", str(uuid4())),
        ("binding_revision", "other-v1"),
        ("adapter_id", "other"),
        ("tool_version", "2"),
    ],
)
async def test_registry_and_executor_exact_identity_denials(directory, field, value):
    with opened(directory) as service:
        action = await admitted(service)
        spec = replace(ExecutionSpec.from_compiled(action.spec), **{field: value})
        executor = AdmissionExecutor(service.store)
        registry = ExecutableRegistry(executor, binding=service.binding)
        with core_denial("TOOL_NOT_BOUND"):
            registry.resolve(spec)
        context = AttemptContext(
            str(uuid4()), asyncio.get_running_loop().time() + 1, asyncio.Event()
        )
        result = await executor.execute(spec, str(uuid4()), context)
        assert result.category == Outcome.CONFIRMED_FAILURE
        assert result.no_effect_reason == "INPUT_REJECTED"
        assert count(service.store) == 0


async def test_adapter_same_payload_receipt_and_payload_conflict(directory):
    with opened(directory) as service:
        action = await admitted(service)
        done = await service.execute(action.action_id, action.version, str(uuid4()))
        spec = ExecutionSpec.from_compiled(done.spec)
        context = AttemptContext(
            str(uuid4()), asyncio.get_running_loop().time() + 2, asyncio.Event()
        )
        executor = AdmissionExecutor(service.store)
        same = await executor.execute(spec, done.effect_key, context)
        assert same.receipt_reference == done.result["receipt_reference"]
        changed = replace(spec, arguments=CHALLENGE | {"title": "Different payload"})
        conflict = await executor.execute(changed, done.effect_key, context)
        assert conflict.no_effect_reason == "PAYLOAD_CONFLICT"
        assert count(service.store) == 1


class LostAckExecutor(AdmissionExecutor):
    async def execute(self, *args):
        result = await super().execute(*args)
        if result.category == Outcome.SUCCESS:
            raise sqlite3.OperationalError("Synthetic lost acknowledgement after actual COMMIT")
        return result


async def test_lost_ack_is_unknown_quarantined_and_cannot_replay(directory):
    with opened(directory, executor_factory=LostAckExecutor) as service:
        action = await admitted(service)
        result = await service.execute(action.action_id, action.version, str(uuid4()))
        assert result.state.value == "Unknown"
        assert service.store.job(action.effect_key)["state"] == "QUARANTINED"
        with core_denial("EXECUTION_ALREADY_STARTED"):
            await service.execute(action.action_id, result.version, str(uuid4()))
        assert count(service.store) == 1
    with opened(directory) as restarted:
        assert restarted.refresh(action.action_id).state.value == "Unknown"
        assert restarted.store.job(action.effect_key)["state"] == "QUARANTINED"
        assert count(restarted.store) == 1


async def test_shortened_deadline_late_ack_never_releases_job(directory):
    class LateExecutor(AdmissionExecutor):
        async def execute(self, *args):
            result = await super().execute(*args)
            await asyncio.sleep(3)
            return result

    with opened(directory, executor_factory=LateExecutor) as service:
        action = await admitted(service)
        result = await service.execute(
            action.action_id,
            action.version,
            str(uuid4()),
            deadline=asyncio.get_running_loop().time() + 2,
        )
        assert result.state.value == "Unknown"
        assert service.store.job(action.effect_key)["state"] == "QUARANTINED"
        assert count(service.store) == 1


async def test_success_survives_restart_without_another_effect(directory):
    with opened(directory) as service:
        action = await admitted(service)
        result = await service.execute(action.action_id, action.version, str(uuid4()))
        saved_job = service.store.job(action.effect_key)
        binding = service.binding
    with opened(directory) as restarted:
        assert restarted.binding == binding
        assert restarted.refresh(action.action_id) == result
        assert restarted.store.job(action.effect_key) == saved_job
        assert count(restarted.store) == 1


async def test_wrong_receipt_quarantined_permanently(directory):
    with opened(directory) as service:
        action = await admitted(service)
        result = await service.execute(action.action_id, action.version, str(uuid4()))
        with closing(service.store.connect()) as db:
            db.execute("UPDATE jobs SET receipt=?", (str(uuid4()),))
            db.commit()
        service.refresh(action.action_id)
        assert service.store.job(action.effect_key)["state"] == "QUARANTINED"
        with closing(service.store.connect()) as db:
            db.execute("UPDATE jobs SET receipt=?", (result.result["receipt_reference"],))
            db.commit()
        service.refresh(action.action_id)
        assert service.store.job(action.effect_key)["state"] == "QUARANTINED"


def test_provisioning_scope_owner_and_exclusive_runtime_fencing(directory):
    with pytest.raises(ValueError, match="DIRECTORY_NOT_EMPTY"):
        provision(directory, "123")
    with (
        pytest.raises(ValueError, match="IDENTITY_MISMATCH"),
        challenge_runtime(directory, "999", predecessor_stopped=True),
    ):
        pytest.fail("wrong owner opened")
    with core_denial("ACTION_NOT_AUTHORIZED"), challenge_runtime(directory, "123"):
        pytest.fail("predecessor shutdown was not attested")
    with opened(directory), core_denial("DATABASE_UNAVAILABLE"), opened(directory):
        pytest.fail("second runtime owner opened")


def test_existing_empty_directory_cannot_silently_bypass_private_provisioning(tmp_path):
    directory = tmp_path / "already-created"
    directory.mkdir()
    with pytest.raises(ValueError, match="DIRECTORY_NOT_EMPTY"):
        provision(directory, "123")
    assert list(directory.iterdir()) == []


def test_provisioned_directory_has_actual_private_permissions(directory):
    if os.name != "nt":
        assert directory.stat().st_mode & 0o777 == 0o700
        return
    script = """
        $currentSid = [Security.Principal.WindowsIdentity]::GetCurrent().User.Value
        $owners = @($currentSid, 'S-1-5-32-544', 'S-1-5-18')
        $allowed = $owners + @('S-1-3-4')
        $acl = [IO.Directory]::GetAccessControl($env:CQ_PHASE2_ACL_PATH)
        $owner = $acl.GetOwner([Security.Principal.SecurityIdentifier]).Value
        $unexpected = @($acl.Access | Where-Object {
            $_.AccessControlType -eq 'Allow' -and
            $_.IdentityReference.Translate([Security.Principal.SecurityIdentifier]).Value -notin $allowed
        })
        if (-not $acl.AreAccessRulesProtected -or $unexpected.Count -gt 0 -or
            $owner -notin $owners) { exit 1 }
    """
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        env=os.environ | {"CQ_PHASE2_ACL_PATH": str(directory)},
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0


def test_actual_process_crash_after_commit_recovers_unknown_without_second_effect(directory):
    completed = subprocess.run(
        [sys.executable, "-m", "tests.phase2_crash", str(directory)],
        capture_output=True,
        check=False,
        timeout=20,
    )
    assert completed.returncode == 73
    with opened(directory) as service:
        ids = service.store.action_ids()
        assert len(ids) == 1
        action = service.refresh(ids[0])
        assert action.state.value == "Unknown"
        assert service.store.job(action.effect_key)["state"] == "QUARANTINED"
        assert count(service.store) == 1
        with core_denial("EXECUTION_ALREADY_STARTED"):
            asyncio.run(service.execute(action.action_id, action.version, str(uuid4())))
        assert count(service.store) == 1


@pytest.mark.parametrize(
    "change",
    [
        {"duration_seconds": True},
        {"duration_seconds": 121},
        {"title": " "},
        {"description": "x" * 241},
        {"title": "x\nY"},
        {"difficulty": "Extreme"},
        {"credentials": "untrusted"},
    ],
)
def test_closed_display_schema(change):
    with pytest.raises(ValueError):
        Challenge.model_validate(CHALLENGE | change)


def test_schema_keeps_html_as_literal_untrusted_text():
    value = Challenge.model_validate(CHALLENGE | {"title": "<img src=x onerror=alert(1)>"})
    assert value.title.startswith("<img")  # Storage does not execute or interpret markup.
