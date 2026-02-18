from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.db import Base, _ENGINE, assert_safe_db_reset, get_db_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reset backoffice DB (test DB only).")
    parser.add_argument(
        "--allow-db-reset",
        action="store_true",
        help="Required. Explicitly allow destructive reset.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if not args.allow_db_reset:
        raise SystemExit("Reset blocked: pass --allow-db-reset to continue.")

    os.environ["BACKOFFICE_ALLOW_DB_RESET"] = "1"
    assert_safe_db_reset()
    Base.metadata.drop_all(_ENGINE)
    Base.metadata.create_all(_ENGINE)
    print(f"Reset complete: {get_db_path()}")


if __name__ == "__main__":
    main()
