"""Entry point: ``python -m agent_clicker``."""

from __future__ import annotations

import asyncio

from agent_clicker.main import run


def cli() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    cli()
