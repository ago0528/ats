from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]


def _resolve_db_path(raw_path: str | None) -> str:
    configured = (raw_path or "").strip() or str(ROOT_DIR / "backoffice.db")
    candidate = configured.removeprefix("sqlite:///")
    path_only = candidate.split("?", 1)[0]
    if path_only == ":memory:":
        return ":memory:"

    db_path = Path(path_only).expanduser()
    if not db_path.is_absolute():
        cwd_path = (Path.cwd() / db_path).resolve()
        if cwd_path.exists():
            db_path = cwd_path
        else:
            db_path = (ROOT_DIR / db_path).resolve()
    return str(db_path)


def _has_mode_column(connection: sqlite3.Connection) -> bool:
    cursor = connection.execute("PRAGMA table_info(validation_runs)")
    return any(row[1] == "mode" for row in cursor.fetchall())


def _create_backup(db_path: str) -> str:
    backup_path = f"{db_path}.mode_backup"
    shutil.copy2(db_path, backup_path)
    return backup_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Drop legacy validation_runs.mode column.")
    parser.add_argument(
        "--db-path",
        default=os.getenv("BACKOFFICE_DB_PATH", str(ROOT_DIR / "backoffice.db")),
        help="Path to sqlite DB (same format as BACKOFFICE_DB_PATH).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply migration to remove mode column. Without this flag, runs in dry-run mode.",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Create a timestamp-free backup file before migration.",
    )
    return parser.parse_args()


def _run_dry_run(connection: sqlite3.Connection, db_path: str) -> None:
    if _has_mode_column(connection):
        print(f"[dry-run] mode column exists in validation_runs ({db_path}).")
        print("Re-run with --execute to remove it.")
    else:
        print(f"[dry-run] mode column not found in validation_runs ({db_path}).")


def _run_migration(connection: sqlite3.Connection, db_path: str, with_backup: bool) -> None:
    if not _has_mode_column(connection):
        print("No legacy mode column found. Nothing to do.")
        return

    if with_backup:
        backup_path = _create_backup(db_path)
        print(f"Backup created: {backup_path}")

    connection.execute("ALTER TABLE validation_runs DROP COLUMN mode")
    connection.commit()
    print("Removed validation_runs.mode column successfully.")


def main() -> None:
    args = _parse_args()
    db_path = _resolve_db_path(args.db_path)

    if db_path == ":memory:":
        raise RuntimeError("BACKOFFICE_DB_PATH cannot be in-memory for this migration.")

    connection = sqlite3.connect(db_path)
    try:
        if args.execute:
            _run_migration(connection, db_path, args.backup)
        else:
            _run_dry_run(connection, db_path)
    finally:
        connection.close()


if __name__ == "__main__":
    main()
