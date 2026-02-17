from __future__ import annotations

import json
from typing import Optional

from app.models.generic_run_row import GenericRunRow
from app.repositories.generic_runs import GenericRunRepository


def compare_runs(repo: GenericRunRepository, run_id: str, base_run_id: Optional[str] = None):
    run = repo.get_run(run_id)
    if run is None:
        raise ValueError("Run not found")

    if base_run_id is None:
        base = repo.latest_done_run_for_env(run.environment, exclude_run_id=run_id)
    else:
        base = repo.get_run(base_run_id)

    if base is None:
        return {"baseRunId": None, "delta": {}, "changedRows": []}

    if base.environment != run.environment:
        raise PermissionError("Cross-environment comparison is not allowed")

    db = repo.db
    current_rows = list(db.query(GenericRunRow).filter(GenericRunRow.run_id == run_id).all())
    base_rows = list(db.query(GenericRunRow).filter(GenericRunRow.run_id == base.id).all())
    by_qid = {r.query_id: r for r in base_rows}

    changed = []
    cur_err = 0
    base_err = 0
    for row in current_rows:
        if row.error:
            cur_err += 1
        b = by_qid.get(row.query_id)
        if b and b.error:
            base_err += 1
        if b is None:
            changed.append({"queryId": row.query_id, "type": "NEW"})
            continue
        if (row.logic_result != b.logic_result) or (row.llm_eval_json != b.llm_eval_json):
            changed.append(
                {
                    "queryId": row.query_id,
                    "current": {"logic": row.logic_result, "llm": row.llm_eval_json},
                    "base": {"logic": b.logic_result, "llm": b.llm_eval_json},
                }
            )

    return {
        "baseRunId": base.id,
        "delta": {
            "errorCount": cur_err - base_err,
            "totalRows": len(current_rows) - len(base_rows),
        },
        "changedRows": changed,
    }
