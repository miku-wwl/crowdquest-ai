"""Owned fixture-process startup identity and graceful shutdown acknowledgement."""

import json
import socket
import subprocess
import sys
import time
from urllib.request import urlopen

from filelock import FileLock


def start_fixture(directory, *, phase3=False):
    for name in ("stop", "stopped"):
        (directory / name).unlink(missing_ok=True)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    process = subprocess.Popen(
        [sys.executable, "-m", "tests.browser_server", str(directory), str(port)]
        + (["phase3"] if phase3 else []),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    origin = f"http://localhost:{port}"
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("Fixture process exited during startup")
        try:
            with urlopen(origin + "/_test/health", timeout=0.3) as response:
                if json.load(response) == {"fixture_id": directory.name}:
                    return process, origin
        except OSError:
            pass
        time.sleep(0.1)
    stop_fixture(process, directory)
    raise RuntimeError("Fixture identity not confirmed")


def stop_fixture(process, directory):
    (directory / "stop").touch()
    deadline = time.monotonic() + 15
    while not (directory / "stopped").exists():
        if time.monotonic() >= deadline:
            process.terminate()
            process.wait(timeout=5)
            raise RuntimeError("Fixture did not acknowledge graceful shutdown")
        time.sleep(0.05)
    # The Windows venv launcher can outlive the completed application. Verify
    # ownership was actually released before reaping that test-owned wrapper.
    with FileLock(directory / "phase1.lock").acquire(timeout=5):
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.terminate()
        process.wait(timeout=5)
