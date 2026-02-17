from __future__ import annotations

import json
from typing import Optional

from app.repositories.validation_runs import ValidationRunRepository


def _build_key(item) -> str:
    return f"{item.conversation_room_index}:{item.repeat_index}:{item.query_text_snapshot}"


def compare_validation_runs(repo: ValidationRunRepository, run_id: str, base_run_id: Optional[str] = None) -> dict:
    run = repo.get_run(run_id)
    if run is None:
        raise ValueError("Run not found")

    if base_run_id:
        base_run = repo.get_run(base_run_id)
    else:
        base_run = repo.latest_done_run_for_env(run.environment, exclude_run_id=run_id)

    if base_run is None:
        return {"baseRunId": None, "delta": {}, "changedRows": []}

    if base_run.environment != run.environment:
        raise PermissionError("Cross-environment comparison is not allowed")

    run_items = repo.list_items(run.id, limit=100000)
    base_items = repo.list_items(base_run.id, limit=100000)
    run_logic = repo.get_logic_eval_map([x.id for x in run_items])
    run_llm = repo.get_llm_eval_map([x.id for x in run_items])
    base_logic = repo.get_logic_eval_map([x.id for x in base_items])
    base_llm = repo.get_llm_eval_map([x.id for x in base_items])

    current_by_key = {_build_key(item): item for item in run_items}
    base_by_key = {_build_key(item): item for item in base_items}

    changed_rows: list[dict] = []
    for key, item in current_by_key.items():
        base_item = base_by_key.get(key)
        if base_item is None:
            changed_rows.append({"key": key, "type": "NEW"})
            continue

        logic_cur = run_logic.get(item.id)
        logic_base = base_logic.get(base_item.id)
        llm_cur = run_llm.get(item.id)
        llm_base = base_llm.get(base_item.id)
        current_logic = logic_cur.result if logic_cur else ""
        base_logic_result = logic_base.result if logic_base else ""
        current_llm_status = llm_cur.status if llm_cur else ""
        base_llm_status = llm_base.status if llm_base else ""
        current_llm_score = llm_cur.total_score if llm_cur else None
        base_llm_score = llm_base.total_score if llm_base else None
        current_error = item.error or ""
        base_error = base_item.error or ""

        if (
            current_logic != base_logic_result
            or current_llm_status != base_llm_status
            or current_llm_score != base_llm_score
            or current_error != base_error
        ):
            changed_rows.append(
                {
                    "key": key,
                    "queryText": item.query_text_snapshot,
                    "current": {
                        "logicResult": current_logic,
                        "llmStatus": current_llm_status,
                        "llmScore": current_llm_score,
                        "error": current_error,
                    },
                    "base": {
                        "logicResult": base_logic_result,
                        "llmStatus": base_llm_status,
                        "llmScore": base_llm_score,
                        "error": base_error,
                    },
                }
            )

    current_error_count = len([x for x in run_items if (x.error or "").strip()])
    base_error_count = len([x for x in base_items if (x.error or "").strip()])
    return {
        "baseRunId": base_run.id,
        "delta": {
            "errorCount": current_error_count - base_error_count,
            "totalItems": len(run_items) - len(base_items),
        },
        "changedRows": changed_rows,
    }


def parse_metric_scores(value: str) -> dict[str, float]:
    if not value:
        return {}
    try:
        raw = json.loads(value)
    except Exception:
        return {}
    if isinstance(raw, dict):
        out: dict[str, float] = {}
        for key, val in raw.items():
            if isinstance(val, (int, float)):
                out[str(key)] = float(val)
        return out
    return {}
