"""Verify Phase 0 dependency/provenance facts without creating a runtime or effects."""

import argparse
import base64
import hashlib
import importlib
import inspect
import json
import sys
import tomllib
from importlib.metadata import distribution
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PIN = "bb8e8fb1234128613a750bee17967b225072bb14"
REPOSITORY = "https://github.com/miku-wwl/agentic-intent-gate"
DEPENDENCY = f"agentic-intent-gate @ git+{REPOSITORY}.git@{PIN}"
REQUIRED = (
    "README.md",
    "AGENTS.md",
    "LICENSE",
    ".gitignore",
    ".env.example",
    "pyproject.toml",
    "uv.lock",
    "docs/PRD.md",
    "docs/ARCHITECTURE.md",
    "docs/ORIGINALITY_AND_REUSE.md",
    "docs/SECURITY_AND_THREAT_MODEL.md",
    "docs/AIG_INTEGRATION.md",
    "docs/TWITCH_INTEGRATION.md",
    "docs/PHASE_PLAN.md",
    "docs/ACCEPTANCE_CRITERIA.md",
    "docs/SUBMISSION_CHECKLIST.md",
    "docs/DECISIONS.md",
)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def verify(expected_environment=None):
    require(sys.version_info[:2] == (3, 13), "Python 3.13 is required")
    for name in REQUIRED:
        require((ROOT / name).is_file(), f"Missing {name}")
        require((ROOT / name).stat().st_size > 0, f"Empty {name}")
    metadata = json.loads((ROOT / "docs/aig-upstream.json").read_text("utf-8"))
    agents = (ROOT / "AGENTS.md").read_bytes()
    prefix = agents[: metadata["source_bytes"]]
    blob = hashlib.sha1(b"blob " + str(len(prefix)).encode() + b"\0" + prefix).hexdigest()
    require(blob == metadata["source_blob_sha"], "Upstream Git blob was changed")
    require(hashlib.sha256(prefix).hexdigest() == metadata["source_sha256"], "Template changed")
    require(metadata["source_path"] == "docs/AGENTS-dependence.md", "Wrong template path")
    require(metadata["release_commit"] == PIN, "Wrong upstream release identity")
    require(
        "CrowdQuest AI — Competition-Specific Instructions"
        in agents[metadata["source_bytes"] :].decode("utf-8"),
        "Missing appended consumer instructions",
    )
    project = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    require(DEPENDENCY in project["project"]["dependencies"], "Dependency is not immutable")
    require(project["project"]["requires-python"] == ">=3.13,<3.14", "Wrong Python range")
    lock = tomllib.loads((ROOT / "uv.lock").read_text("utf-8"))
    locked = [p for p in lock["package"] if p["name"] == "agentic-intent-gate"]
    require(len(locked) == 1 and locked[0]["version"] == "0.3.0", "Wrong locked AIG version")
    require(
        locked[0]["source"].get("git", "").endswith(f"#{PIN}"),
        "Lockfile does not resolve to the pinned commit",
    )
    dist = distribution("agentic-intent-gate")
    require(dist.version == "0.3.0", "Wrong installed version")
    direct = json.loads(dist.read_text("direct_url.json") or "{}")
    require(direct.get("url", "").removesuffix(".git") == REPOSITORY, "Unexpected installed source")
    require(direct.get("vcs_info", {}).get("commit_id") == PIN, "Wrong installed commit")
    require(not direct.get("dir_info", {}).get("editable", False), "Editable AIG is forbidden")
    runtime = importlib.import_module("agentic_intent_gate.runtime")

    module = Path(runtime.__file__).resolve()
    environment = Path(sys.prefix).resolve()
    expected_environment = (
        Path(expected_environment).resolve() if expected_environment else (ROOT / ".venv").resolve()
    )
    require(environment == expected_environment, "Use the explicitly selected isolated environment")
    require(module.is_relative_to(environment), "AIG imports from outside the environment")
    require("site-packages" in module.parts, "AIG is not loaded from installed site-packages")
    source_files = [
        item
        for item in dist.files
        if str(item).replace("\\", "/").startswith("agentic_intent_gate/") and item.suffix == ".py"
    ]
    require(bool(source_files), "Installed AIG source inventory is missing")
    for item in source_files:
        require(item.hash is not None and item.hash.mode == "sha256", "Missing AIG RECORD hash")
        actual = (
            base64.urlsafe_b64encode(
                hashlib.sha256(Path(dist.locate_file(item)).read_bytes()).digest()
            )
            .decode()
            .rstrip("=")
        )
        require(
            actual == item.hash.value, "Installed AIG source differs from its distribution RECORD"
        )
    names = (
        "ToolBinding",
        "ToolCapability",
        "ExecutableRegistry",
        "CapabilityVerifier",
        "BoundCapabilityAuthorization",
        "execution_budget_binding",
        "open_runtime",
        "AdmissionCommand",
        "ActionCommand",
        "ApprovalDecisionRequest",
        "ToolOutcome",
        "ModelProvider",
        "ToolExecutor",
    )
    signatures = {name: str(inspect.signature(getattr(runtime, name))) for name in names}
    require(
        inspect.signature(runtime.open_runtime).parameters["execution_timeout_seconds"].default
        == 5,
        "Unexpected default execution budget",
    )
    return {
        "status": "PASS",
        "scope": "Phase 0 installed dependency, public API and document provenance only",
        "python": ".".join(map(str, sys.version_info[:3])),
        "aig_version": dist.version,
        "aig_commit": PIN,
        "installed_aig_source_files_verified": len(source_files),
        "module_relative_to_venv": module.relative_to(environment).as_posix(),
        "upstream_source_commit": metadata["source_commit"],
        "upstream_blob_sha": blob,
        "upstream_preserved_bytes": len(prefix),
        "required_files": len(REQUIRED),
        "public_api_signatures": signatures,
        "not_run": [
            "runtime workflow",
            "human approval",
            "Twitch",
            "AI inference",
            "OBS",
            "browser E2E",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--environment",
        type=Path,
        help="Explicit isolated qualification environment; default .venv",
    )
    args = parser.parse_args()
    result = verify(args.environment)
    rendered = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
