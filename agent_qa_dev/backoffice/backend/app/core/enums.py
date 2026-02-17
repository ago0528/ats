from __future__ import annotations

from enum import Enum


class Environment(str, Enum):
    DEV = "dev"
    ST2 = "st2"
    ST = "st"
    PR = "pr"


class RunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"
