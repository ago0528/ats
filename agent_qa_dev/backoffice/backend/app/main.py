from __future__ import annotations

import logging
import os
import ipaddress
import socket
from pathlib import Path

logger = logging.getLogger(__name__)


def _load_dotenv_file() -> None:
    base_dir = Path(__file__).resolve().parents[1]
    candidates = [
        base_dir / ".env",
        Path.cwd() / ".env",
    ]
    env_path: Path | None = None
    for candidate in candidates:
        if candidate.exists():
            env_path = candidate
            break

    if env_path is None:
        logger.warning(
            "No .env file found. Tried: %s, %s",
            base_dir / ".env",
            Path.cwd() / ".env",
        )
        return

    logger.info("Loading environment variables from %s", env_path)

    loaded_keys: list[str] = []
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if key.startswith("export "):
            key = key.removeprefix("export ").strip()
        if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value
            loaded_keys.append(key)

    if loaded_keys:
        logger.debug("Loaded %d variables from %s: %s", len(loaded_keys), env_path, ", ".join(sorted(loaded_keys)))
    else:
        logger.debug("No new variables were loaded from %s", env_path)


def _log_openai_key_status() -> None:
    openai_key = os.getenv("BACKOFFICE_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    if openai_key:
        if os.getenv("BACKOFFICE_OPENAI_API_KEY"):
            logger.info("Resolved OpenAI key from BACKOFFICE_OPENAI_API_KEY.")
        else:
            logger.info("Resolved OpenAI key from OPENAI_API_KEY.")
        return

    logger.warning(
        "OpenAI API key is not configured. Set BACKOFFICE_OPENAI_API_KEY or OPENAI_API_KEY in environment/.env.",
    )


_load_dotenv_file()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes.auth import router as auth_router
from app.api.routes.generic_runs import router as generic_runs_router
from app.api.routes.prompts import router as prompts_router
from app.api.routes.queries import router as queries_router
from app.api.routes.query_groups import router as query_groups_router
from app.api.routes.utils import router as utils_router
from app.api.routes.validation_agents import router as validation_agents_router
from app.api.routes.validation_run_activity import router as validation_run_activity_router
from app.api.routes.validation_runs import router as validation_runs_router
from app.api.routes.validation_settings import router as validation_settings_router
from app.api.routes.validation_test_sets import router as validation_test_sets_router
from app.core.db import Base, _ENGINE, get_db_path

app = FastAPI(title="AQB Backoffice API", version="0.2.0")
APP_VERSION = os.getenv("BACKOFFICE_VERSION", "0.2.0")


def _resolve_allowed_origins() -> list[str]:
    defaults = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ]

    discovered_private_origins: set[str] = set()
    discovered_hosts: set[str] = set()
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as outbound_socket:
            outbound_socket.connect(("8.8.8.8", 80))
            discovered_hosts.add(outbound_socket.getsockname()[0])
    except OSError:
        pass

    try:
        host_name = socket.gethostname()
        for entry in socket.getaddrinfo(host_name, None, family=socket.AF_INET):
            discovered_hosts.add(str(entry[4][0]))
    except OSError:
        pass

    for host in discovered_hosts:
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            continue
        if not (ip.is_private or ip.is_loopback):
            continue
        discovered_private_origins.add(f"http://{ip}:5173")
        discovered_private_origins.add(f"http://{ip}:4173")

    raw_value = str(os.getenv("BACKOFFICE_ALLOWED_ORIGINS", "")).strip()
    if not raw_value:
        return sorted(set(defaults) | discovered_private_origins)
    values = [item.strip() for item in raw_value.split(",") if item.strip()]
    filtered = [value for value in values if value != "*"]
    return filtered or sorted(set(defaults) | discovered_private_origins)

_ALLOWED_ORIGINS = _resolve_allowed_origins()
logger.info("Resolved CORS allowed origins: %s", ", ".join(_ALLOWED_ORIGINS))
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ensure_sqlite_column(table_name: str, column_name: str, column_definition: str) -> None:
    with _ENGINE.begin() as connection:
        existing_columns = {
            str(row[1])
            for row in connection.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        }
        if column_name in existing_columns:
            return
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_definition}"))


@app.on_event("startup")
def startup() -> None:
    logger.info("Resolved BACKOFFICE_DB_PATH=%s", get_db_path())
    _log_openai_key_status()
    Base.metadata.create_all(_ENGINE)
    _ensure_sqlite_column("validation_queries", "context_json", "context_json TEXT NOT NULL DEFAULT ''")
    _ensure_sqlite_column("validation_queries", "target_assistant", "target_assistant TEXT NOT NULL DEFAULT ''")
    _ensure_sqlite_column(
        "validation_query_groups",
        "default_target_assistant",
        "default_target_assistant TEXT NOT NULL DEFAULT ''",
    )
    _ensure_sqlite_column(
        "validation_query_groups",
        "llm_eval_criteria_default_json",
        "llm_eval_criteria_default_json TEXT NOT NULL DEFAULT '[]'",
    )
    _ensure_sqlite_column("validation_run_items", "context_json_snapshot", "context_json_snapshot TEXT NOT NULL DEFAULT ''")
    _ensure_sqlite_column("validation_run_items", "target_assistant_snapshot", "target_assistant_snapshot TEXT NOT NULL DEFAULT ''")
    _ensure_sqlite_column("validation_runs", "test_set_id", "test_set_id TEXT")
    _ensure_sqlite_column("validation_runs", "name", "name TEXT NOT NULL DEFAULT ''")
    _ensure_sqlite_column("validation_runs", "eval_status", "eval_status TEXT NOT NULL DEFAULT 'PENDING'")
    _ensure_sqlite_column("validation_runs", "eval_started_at", "eval_started_at DATETIME")
    _ensure_sqlite_column("validation_runs", "eval_finished_at", "eval_finished_at DATETIME")
    _ensure_sqlite_column(
        "validation_llm_evaluations",
        "llm_output_json",
        "llm_output_json TEXT NOT NULL DEFAULT ''",
    )
    _ensure_sqlite_column(
        "validation_llm_evaluations",
        "prompt_version",
        "prompt_version TEXT NOT NULL DEFAULT ''",
    )
    _ensure_sqlite_column(
        "validation_llm_evaluations",
        "input_hash",
        "input_hash TEXT NOT NULL DEFAULT ''",
    )
    _ensure_sqlite_column(
        "validation_settings",
        "pagination_page_size_limit_default",
        "pagination_page_size_limit_default INTEGER NOT NULL DEFAULT 100",
    )


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.get("/api/v1/version")
def version():
    return {"version": APP_VERSION}


app.include_router(utils_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(generic_runs_router, prefix="/api/v1")
app.include_router(prompts_router, prefix="/api/v1")
app.include_router(query_groups_router, prefix="/api/v1")
app.include_router(queries_router, prefix="/api/v1")
app.include_router(validation_settings_router, prefix="/api/v1")
app.include_router(validation_runs_router, prefix="/api/v1")
app.include_router(validation_run_activity_router, prefix="/api/v1")
app.include_router(validation_test_sets_router, prefix="/api/v1")
app.include_router(validation_agents_router, prefix="/api/v1")
