from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes.generic_runs import router as generic_runs_router
from app.api.routes.prompts import router as prompts_router
from app.api.routes.queries import router as queries_router
from app.api.routes.query_groups import router as query_groups_router
from app.api.routes.utils import router as utils_router
from app.api.routes.validation_runs import router as validation_runs_router
from app.api.routes.validation_settings import router as validation_settings_router
from app.api.routes.validation_test_sets import router as validation_test_sets_router
from app.core.db import Base, _ENGINE

app = FastAPI(title="AQB Backoffice API", version="0.1.0")
APP_VERSION = os.getenv("BACKOFFICE_VERSION", "0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
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
    Base.metadata.create_all(_ENGINE)
    _ensure_sqlite_column("validation_query_groups", "default_target_assistant", "default_target_assistant TEXT NOT NULL DEFAULT ''")
    _ensure_sqlite_column("validation_queries", "context_json", "context_json TEXT NOT NULL DEFAULT ''")
    _ensure_sqlite_column("validation_queries", "target_assistant", "target_assistant TEXT NOT NULL DEFAULT ''")
    _ensure_sqlite_column("validation_run_items", "context_json_snapshot", "context_json_snapshot TEXT NOT NULL DEFAULT ''")
    _ensure_sqlite_column("validation_run_items", "target_assistant_snapshot", "target_assistant_snapshot TEXT NOT NULL DEFAULT ''")
    _ensure_sqlite_column("validation_runs", "test_set_id", "test_set_id TEXT")
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
app.include_router(generic_runs_router, prefix="/api/v1")
app.include_router(prompts_router, prefix="/api/v1")
app.include_router(query_groups_router, prefix="/api/v1")
app.include_router(queries_router, prefix="/api/v1")
app.include_router(validation_settings_router, prefix="/api/v1")
app.include_router(validation_runs_router, prefix="/api/v1")
app.include_router(validation_test_sets_router, prefix="/api/v1")
