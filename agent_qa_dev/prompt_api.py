"""Backward compatibility shim for legacy `prompt_api` imports.

The canonical module now lives at:
`backoffice/backend/app/adapters/prompt_api_client.py`
"""

from __future__ import annotations

import sys
from pathlib import Path

_BACKEND_APP_PATH = Path(__file__).resolve().parent / "backoffice" / "backend"
if str(_BACKEND_APP_PATH) not in sys.path:
    sys.path.append(str(_BACKEND_APP_PATH))

from app.adapters.prompt_api_client import *  # noqa: F401,F403
