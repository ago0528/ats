from __future__ import annotations

import asyncio
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import aiohttp

from app.adapters.openai_judge_adapter import OpenAIJudgeAdapter
from app.core.db import SessionLocal
from app.core.enums import EvalStatus
from app.repositories.validation_runs import ValidationRunRepository
from app.services.logic_check import run_logic_check
from app.services.validation_scoring import average, extract_response_time_sec, parse_raw_payload, score_stability

PROMPT_VERSION = "single-prompt-v2.0.0"
METRIC_KEYS = ("intent", "accuracy", "consistency", "latencySingle", "latencyMulti", "stability")
CONSISTENCY_KEY = "consistency"

_DOCS_ROOT = Path(__file__).resolve().parents[4] / "docs" / "evaluating"
_PROMPT_PATH = _DOCS_ROOT / "prompt_for_scoring.txt"
_SCHEMA_PATH = _DOCS_ROOT / "prompt_for_scoring_output_schema.json"


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _clamp_score(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except Exception:
        return None
    if parsed < 0:
        return 0.0
    if parsed > 5:
        return 5.0
    return parsed


def _parse_metric_scores(metric_scores_json: str) -> dict[str, float]:
    if not metric_scores_json:
        return {}
    try:
        payload = json.loads(metric_scores_json)
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}

    out: dict[str, float] = {}
    for key, value in payload.items():
        parsed = _clamp_score(value)
        if parsed is not None:
            out[str(key)] = parsed
    return out


def _normalize_prompt_text(text: str) -> str:
    normalized = str(text or "").replace("\r\n", "\n").strip()
    if not normalized:
        raise ValueError("prompt_for_scoring.txt is empty")
    return normalized


def _load_prompt_and_schema() -> tuple[str, dict[str, Any], str, bool]:
    prompt_text = _normalize_prompt_text(_PROMPT_PATH.read_text(encoding="utf-8"))
    schema_payload = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    schema = schema_payload.get("schema")
    if not isinstance(schema, dict):
        raise ValueError("prompt_for_scoring_output_schema.json must contain object field `schema`")
    schema_name = str(schema_payload.get("name") or "score_eval")
    strict = bool(schema_payload.get("strict", True))
    return prompt_text, schema, schema_name, strict


def _canonicalize_json_value(value: Any, *, max_text: int) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _canonicalize_json_value(value[key], max_text=max_text)
            for key in sorted(value.keys())
        }
    if isinstance(value, list):
        return [_canonicalize_json_value(item, max_text=max_text) for item in value[:20]]
    if isinstance(value, str):
        return value[:max_text]
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)[:max_text]


def _build_row_raw_payload(raw_payload: dict[str, Any], *, max_text: int) -> dict[str, Any]:
    return {
        "assistantMessage": _safe_text(raw_payload.get("assistantMessage"))[:max_text],
        "dataUIList": _canonicalize_json_value(raw_payload.get("dataUIList"), max_text=max_text),
        "setting": _canonicalize_json_value(raw_payload.get("setting"), max_text=max_text),
        "filterType": _canonicalize_json_value(raw_payload.get("filterType"), max_text=max_text),
        "raw": _canonicalize_json_value(raw_payload, max_text=max_text),
    }


@dataclass
class ItemEvalDraft:
    item_id: str
    query_id: str
    metric_scores: dict[str, Any]
    llm_comment: str
    status: str
    llm_output_json: str
    prompt_version: str
    input_hash: str


def _build_total_score(metric_scores: dict[str, Any]) -> float | None:
    intent = _clamp_score(metric_scores.get("intent"))
    accuracy = _clamp_score(metric_scores.get("accuracy"))
    stability = _clamp_score(metric_scores.get("stability"))
    consistency = _clamp_score(metric_scores.get("consistency"))
    if intent is None or accuracy is None or stability is None:
        return None
    values = [intent, accuracy, stability]
    if consistency is not None:
        values.append(consistency)
    total = average(values)
    if total is None:
        return None
    return round(float(total), 4)


def _sync_consistency_by_query_id(drafts: list[ItemEvalDraft]) -> None:
    grouped: dict[str, list[ItemEvalDraft]] = defaultdict(list)
    for draft in drafts:
        if draft.query_id:
            grouped[draft.query_id].append(draft)

    for query_id, rows in grouped.items():
        if not query_id:
            continue
        if len(rows) < 2:
            for draft in rows:
                draft.metric_scores[CONSISTENCY_KEY] = None
            continue

        shared_value: float | None = None
        for draft in rows:
            parsed = _clamp_score(draft.metric_scores.get(CONSISTENCY_KEY))
            if parsed is not None:
                shared_value = parsed
                break
        for draft in rows:
            draft.metric_scores[CONSISTENCY_KEY] = shared_value


def _build_score_snapshots(repo: ValidationRunRepository, run_id: str, run_items: list[Any]) -> None:
    run = repo.get_run(run_id)
    if run is None:
        return

    item_ids = [item.id for item in run_items]
    logic_map = repo.get_logic_eval_map(item_ids)
    llm_map = repo.get_llm_eval_map(item_ids)
    query_ids = [item.query_id for item in run_items if item.query_id]
    query_to_group = repo.list_query_group_ids_by_query_ids(query_ids)

    aggregates: dict[Optional[str], dict[str, Any]] = defaultdict(
        lambda: {
            "totalItems": 0,
            "executedItems": 0,
            "errorItems": 0,
            "logicPassItems": 0,
            "llmDoneItems": 0,
            "metricSums": defaultdict(float),
            "metricCounts": defaultdict(int),
            "totalScoreSum": 0.0,
            "totalScoreCount": 0,
        }
    )

    for item in run_items:
        group_id = query_to_group.get(item.query_id) if item.query_id else None
        target_groups = [None]
        if group_id:
            target_groups.append(group_id)

        for target_group in target_groups:
            agg = aggregates[target_group]
            agg["totalItems"] += 1
            has_execution = bool(item.executed_at) or bool((item.error or "").strip())
            if has_execution:
                agg["executedItems"] += 1
            if (item.error or "").strip():
                agg["errorItems"] += 1

            logic = logic_map.get(item.id)
            if logic and logic.result == "PASS":
                agg["logicPassItems"] += 1

            llm = llm_map.get(item.id)
            if llm and str(llm.status or "").upper().startswith("DONE"):
                agg["llmDoneItems"] += 1
                if isinstance(llm.total_score, (int, float)):
                    agg["totalScoreSum"] += float(llm.total_score)
                    agg["totalScoreCount"] += 1
                for metric_name, metric_score in _parse_metric_scores(llm.metric_scores_json).items():
                    agg["metricSums"][metric_name] += metric_score
                    agg["metricCounts"][metric_name] += 1

    repo.clear_score_snapshots_for_run(run_id)
    for group_id, agg in aggregates.items():
        metric_avg = {
            metric_name: round(agg["metricSums"][metric_name] / agg["metricCounts"][metric_name], 4)
            for metric_name in agg["metricSums"]
            if agg["metricCounts"][metric_name] > 0
        }
        score_avg = (
            round(agg["totalScoreSum"] / agg["totalScoreCount"], 4)
            if agg["totalScoreCount"] > 0
            else None
        )
        repo.upsert_score_snapshot(
            run_id=run_id,
            test_set_id=run.test_set_id,
            query_group_id=group_id,
            total_items=agg["totalItems"],
            executed_items=agg["executedItems"],
            error_items=agg["errorItems"],
            logic_pass_items=agg["logicPassItems"],
            llm_done_items=agg["llmDoneItems"],
            llm_metric_averages=metric_avg,
            llm_total_score_avg=score_avg,
        )


async def evaluate_validation_run(
    run_id: str,
    openai_key: Optional[str],
    openai_model: str,
    max_chars: int,
    max_parallel: int,
    item_ids: Optional[list[str]] = None,
):
    db = SessionLocal()
    repo = ValidationRunRepository(db)
    repo.set_eval_status(run_id, EvalStatus.RUNNING)
    db.commit()

    try:
        all_run_items = repo.list_items(run_id, limit=100000)
        if not all_run_items:
            repo.set_eval_status(run_id, EvalStatus.DONE)
            db.commit()
            return

        target_item_ids = list(dict.fromkeys([str(item_id).strip() for item_id in (item_ids or []) if str(item_id).strip()]))
        run_items = (
            repo.list_items_by_ids(run_id, target_item_ids)
            if target_item_ids
            else all_run_items
        )
        if not run_items:
            repo.set_eval_status(run_id, EvalStatus.DONE)
            db.commit()
            return

        missing_expected = [item for item in run_items if not _safe_text(item.expected_result_snapshot)]
        if missing_expected:
            sample_query_ids = [
                str(item.query_id or item.id or "")
                for item in missing_expected[:5]
                if _safe_text(item.query_id or item.id)
            ]
            sample_text = ",".join(sample_query_ids) if sample_query_ids else "-"
            raise ValueError(
                f"expected_result_missing|missingCount={len(missing_expected)}|sampleQueryIds={sample_text}"
            )

        for item in run_items:
            if item.logic_field_path_snapshot and item.logic_expected_value_snapshot:
                logic_raw_result = run_logic_check(
                    item.raw_json or "",
                    item.logic_field_path_snapshot,
                    item.logic_expected_value_snapshot,
                )
            else:
                logic_raw_result = "SKIPPED_NO_CRITERIA"

            logic_upper = str(logic_raw_result).upper()
            if logic_upper.startswith("PASS"):
                logic_result = "PASS"
                fail_reason = ""
            elif logic_upper.startswith("FAIL"):
                logic_result = "FAIL"
                fail_reason = str(logic_raw_result)
            else:
                logic_result = "SKIPPED"
                fail_reason = ""

            repo.upsert_logic_eval(
                item.id,
                eval_items={
                    "fieldPath": item.logic_field_path_snapshot,
                    "expectedValue": item.logic_expected_value_snapshot,
                },
                result=logic_result,
                fail_reason=fail_reason,
            )
        db.commit()

        prompt_template, response_schema, schema_name, strict_schema = _load_prompt_and_schema()

        parsed_raw_map: dict[str, tuple[dict[str, Any], bool]] = {}
        response_sec_map: dict[str, float | None] = {}
        query_group_map: dict[str, list[Any]] = defaultdict(list)

        for item in run_items:
            raw_payload, raw_parse_ok = parse_raw_payload(item.raw_json or "")
            parsed_raw_map[item.id] = (raw_payload, raw_parse_ok)
            response_sec_map[item.id] = extract_response_time_sec(raw_payload, item.latency_ms)
            if item.query_id:
                query_group_map[str(item.query_id)].append(item)

        adapter = OpenAIJudgeAdapter()
        sem = asyncio.Semaphore(max(1, int(max_parallel or 1)))
        timeout = aiohttp.ClientTimeout(total=120)
        eval_drafts: list[ItemEvalDraft] = []

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async def _evaluate_item(item) -> None:
                raw_payload, raw_parse_ok = parsed_raw_map[item.id]
                response_time_sec = response_sec_map.get(item.id)
                stability_fallback = score_stability(
                    error_text=item.error or "",
                    raw_payload=raw_payload,
                    raw_parse_ok=raw_parse_ok,
                )

                peer_rows: list[dict[str, Any]] = []
                if item.query_id:
                    for peer in query_group_map.get(str(item.query_id), []):
                        peer_payload, _ = parsed_raw_map[peer.id]
                        peer_rows.append(
                            {
                                "itemId": peer.id,
                                "repeatIndex": int(peer.repeat_index or 1),
                                "conversationRoomIndex": int(peer.conversation_room_index or 1),
                                "responseTimeSec": response_sec_map.get(peer.id),
                                "error": _safe_text(peer.error),
                                "assistantMessage": _safe_text(peer_payload.get("assistantMessage"))[: max_chars // 4],
                                "dataUIList": _canonicalize_json_value(peer_payload.get("dataUIList"), max_text=1000),
                            }
                        )

                evaluation_input = {
                    "runId": run_id,
                    "itemId": item.id,
                    "queryId": str(item.query_id or ""),
                    "queryText": _safe_text(item.query_text_snapshot)[:max_chars],
                    "expectedResult": _safe_text(item.expected_result_snapshot)[:max_chars],
                    "error": _safe_text(item.error),
                    "responseTimeSec": response_time_sec,
                    "rawPayload": _build_row_raw_payload(raw_payload, max_text=max(500, max_chars // 4)),
                    "peerExecutions": peer_rows,
                }

                input_json_text = json.dumps(
                    evaluation_input,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                )
                if len(input_json_text) > max_chars:
                    input_json_text = input_json_text[:max_chars]

                prompt = (
                    f"{prompt_template}\n\n"
                    "<evaluation_input_json>\n"
                    f"{input_json_text}\n"
                    "</evaluation_input_json>\n"
                )
                input_hash = hashlib.sha256(input_json_text.encode("utf-8")).hexdigest()

                result_payload: dict[str, Any] | None = None
                llm_error = ""
                if not openai_key:
                    llm_error = "OpenAI API key is missing."
                else:
                    try:
                        async with sem:
                            result_payload, _usage, llm_error = await adapter.judge(
                                session,
                                openai_key,
                                openai_model,
                                prompt,
                                response_schema=response_schema,
                                schema_name=schema_name,
                                strict_schema=strict_schema,
                            )
                    except Exception as exc:
                        llm_error = str(exc)

                metric_scores: dict[str, Any] = {
                    "intent": 0.0,
                    "accuracy": 0.0,
                    "consistency": None,
                    "latencySingle": None,
                    "latencyMulti": None,
                    "stability": float(stability_fallback),
                }
                llm_comment = ""
                llm_output_json = ""
                status = "DONE_WITH_LLM_ERROR"

                if result_payload is not None and not llm_error:
                    for key in METRIC_KEYS:
                        if key == CONSISTENCY_KEY:
                            metric_scores[key] = _clamp_score(result_payload.get(key))
                        else:
                            metric_scores[key] = _clamp_score(result_payload.get(key))
                    if metric_scores.get("intent") is None:
                        metric_scores["intent"] = 0.0
                    if metric_scores.get("accuracy") is None:
                        metric_scores["accuracy"] = 0.0
                    if metric_scores.get("stability") is None:
                        metric_scores["stability"] = float(stability_fallback)

                    llm_comment = _safe_text(result_payload.get("reasoning")) or "OK"
                    llm_output_json = json.dumps(result_payload, ensure_ascii=False)
                    status = "DONE_WITH_EXEC_ERROR" if _safe_text(item.error) else "DONE"
                else:
                    llm_comment = f"LLM_ERROR: {llm_error or 'unknown'}"
                    llm_output_json = json.dumps({"error": llm_error or "unknown"}, ensure_ascii=False)
                    status = "DONE_WITH_LLM_ERROR"

                eval_drafts.append(
                    ItemEvalDraft(
                        item_id=item.id,
                        query_id=str(item.query_id or ""),
                        metric_scores=metric_scores,
                        llm_comment=llm_comment,
                        status=status,
                        llm_output_json=llm_output_json,
                        prompt_version=PROMPT_VERSION,
                        input_hash=input_hash,
                    )
                )

            await asyncio.gather(*[_evaluate_item(item) for item in run_items])

        _sync_consistency_by_query_id(eval_drafts)

        for draft in eval_drafts:
            total_score = _build_total_score(draft.metric_scores)
            repo.upsert_llm_eval(
                draft.item_id,
                eval_model=openai_model,
                metric_scores=draft.metric_scores,
                total_score=total_score,
                llm_comment=draft.llm_comment,
                status=draft.status,
                llm_output=draft.llm_output_json,
                prompt_version=draft.prompt_version,
                input_hash=draft.input_hash,
            )
        db.commit()

        _build_score_snapshots(repo, run_id, all_run_items)
        db.commit()

        repo.set_eval_status(run_id, EvalStatus.DONE)
        db.commit()
    except Exception:
        repo.set_eval_status(run_id, EvalStatus.FAILED)
        db.commit()
        raise
    finally:
        db.close()
