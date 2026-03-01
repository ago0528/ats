from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any


class InMemoryRunner:
    def __init__(self):
        self.jobs: dict[str, str] = {}
        self._tasks_by_job_id: dict[str, asyncio.Task[Any]] = {}
        self._job_ids_by_key: dict[str, set[str]] = {}

    def _normalize_key(self, job_key: str | None) -> str:
        return str(job_key or "").strip()

    def _prune_key(self, normalized_key: str) -> None:
        job_ids = self._job_ids_by_key.get(normalized_key)
        if not job_ids:
            self._job_ids_by_key.pop(normalized_key, None)
            return
        stale_job_ids = {
            job_id
            for job_id in list(job_ids)
            if (task := self._tasks_by_job_id.get(job_id)) is None or task.done()
        }
        job_ids.difference_update(stale_job_ids)
        if not job_ids:
            self._job_ids_by_key.pop(normalized_key, None)

    def run(
        self,
        job_id: str,
        job_coro_factory: Callable[[], Awaitable[None]],
        *,
        job_key: str | None = None,
    ) -> None:
        self.jobs[job_id] = "RUNNING"
        normalized_key = self._normalize_key(job_key)

        async def _wrap():
            try:
                await job_coro_factory()
                self.jobs[job_id] = "DONE"
            except asyncio.CancelledError:
                self.jobs[job_id] = "CANCELED"
                raise
            except Exception:
                self.jobs[job_id] = "FAILED"

        task = asyncio.create_task(_wrap())
        self._tasks_by_job_id[job_id] = task
        if normalized_key:
            self._job_ids_by_key.setdefault(normalized_key, set()).add(job_id)

        def _cleanup(done_task: asyncio.Task[Any]) -> None:
            self._tasks_by_job_id.pop(job_id, None)
            if normalized_key:
                self._prune_key(normalized_key)
            try:
                done_task.exception()
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

        task.add_done_callback(_cleanup)

    def has_active_job(self, job_key: str) -> bool:
        normalized_key = self._normalize_key(job_key)
        if not normalized_key:
            return False
        self._prune_key(normalized_key)
        job_ids = self._job_ids_by_key.get(normalized_key, set())
        for job_id in job_ids:
            task = self._tasks_by_job_id.get(job_id)
            if task is not None and not task.done():
                return True
        return False

    def cancel_by_key(self, job_key: str) -> bool:
        normalized_key = self._normalize_key(job_key)
        if not normalized_key:
            return False
        self._prune_key(normalized_key)
        job_ids = list(self._job_ids_by_key.get(normalized_key, set()))
        cancelled = False
        for job_id in job_ids:
            task = self._tasks_by_job_id.get(job_id)
            if task is None or task.done():
                continue
            task.cancel()
            cancelled = True
        return cancelled


runner = InMemoryRunner()
