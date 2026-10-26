"""Disposable synthetic process: terminate after a real rendering dispatch COMMIT."""

import asyncio
import os
import sys
from pathlib import Path

from tests.phase3_support import product, succeeded, tick


async def crash(directory):
    with product(directory) as service:
        await succeeded(service)
        tick(service)
        os._exit(74)


if __name__ == "__main__":
    asyncio.run(crash(Path(sys.argv[1])))
