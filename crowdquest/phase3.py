"""Explicit Phase 3 provisioning/composition; live activation is a separate owner gate."""

import json
from contextlib import contextmanager
from pathlib import Path

from agentic_intent_gate.runtime import provision_capability

from .admission import AdmissionExecutor
from .phase2 import binding_for, challenge_runtime, private_directory
from .phase2 import provision as provision_phase2
from .product import ProductService, ProductStore
from .providers import DomainProvider
from .rendering import RenderCoordinator, RenderStore


def provision(directory, owner_id, *, model="phi4-mini:latest"):
    directory = private_directory(directory)
    DomainProvider(None, model=model)  # Validate config before any state is created.
    provision_phase2(directory, owner_id)
    binding = binding_for(
        owner_id, json.loads((directory / "identity.json").read_text("utf-8"))["execution_scope"]
    )
    ProductStore.provision(directory / "product.sqlite3")
    RenderStore.provision(directory / "render.sqlite3", binding)
    provision_capability(directory / "worker-token")
    (directory / "provider.json").write_text(
        json.dumps({"provider": "ollama_local", "model": model}), encoding="utf-8"
    )


@contextmanager
def production_runtime(
    directory,
    owner_id,
    *,
    predecessor_stopped=False,
    provider_factory=None,
    monotonic=None,
    clock=None,
    executor_factory=AdmissionExecutor,
):
    directory = private_directory(directory)
    identity = json.loads((directory / "identity.json").read_text("utf-8"))
    binding = binding_for(owner_id, identity["execution_scope"])
    config = json.loads((directory / "provider.json").read_text("utf-8"))
    if set(config) != {"provider", "model"} or config["provider"] != "ollama_local":
        raise ValueError("PROVIDER_CONFIGURATION")
    provider = (
        provider_factory(binding)
        if provider_factory
        else DomainProvider(binding, model=config["model"])
    )
    with challenge_runtime(
        directory,
        owner_id,
        provider=provider,
        predecessor_stopped=predecessor_stopped,
        executor_factory=executor_factory,
    ) as base:
        proposals = ProductStore(directory / "product.sqlite3")
        proposals.recover()
        clocks = {}
        if monotonic is not None:
            clocks["monotonic"] = monotonic
        if clock is not None:
            clocks["clock"] = clock
        rendering = RenderStore(directory / "render.sqlite3", binding, **clocks)
        coordinator = RenderCoordinator(
            base, rendering, (directory / "worker-token").read_text("ascii")
        )
        service = ProductService(base, proposals, coordinator)
        service.provider_name = config["model"]
        yield service


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Provision a new private Phase 3 profile, no activation"
    )
    parser.add_argument("directory", type=Path)
    parser.add_argument("--owner-id", required=True)
    parser.add_argument("--model", default="phi4-mini:latest")
    args = parser.parse_args()
    provision(args.directory, args.owner_id, model=args.model)
    print("PHASE3_PROVISIONED=YES; no Plan, approval, Action or rendering was created")
