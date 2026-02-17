from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable


class InMemoryRunner:
    def __init__(self):
        self.jobs: dict[str, str] = {}

    def run(self, job_id: str, job_coro_factory: Callable[[], Awaitable[None]]) -> None:
        self.jobs[job_id] = "RUNNING"

        async def _wrap():
            try:
                await job_coro_factory()
                self.jobs[job_id] = "DONE"
            except Exception:
                self.jobs[job_id] = "FAILED"

        asyncio.create_task(_wrap())


runner = InMemoryRunner()
