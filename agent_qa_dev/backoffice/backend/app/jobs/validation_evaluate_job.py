from __future__ import annotations

import asyncio
import hashlib
import json
import re
from collections import defaultdict
from typing import Any, Optional

import aiohttp

from app.adapters.openai_judge_adapter import OpenAIJudgeAdapter
from app.core.db import SessionLocal
from app.core.enums import EvalStatus
from app.repositories.validation_runs import ValidationRunRepository
from app.services.logic_check import run_logic_check
from app.services.validation_scoring import (
    ACCURACY_LLM_EXTRACT_FALLBACK_TAG,
    LEGACY_ACCURACY_FALLBACK_TAG,
    average,
    evaluate_accuracy_checks,
    merge_accuracy_checks,
    parse_applied_criteria,
    parse_expected_result_accuracy_checks,
    parse_raw_payload,
    score_stability,
)

INTENT_PROMPT_VERSION = "intent-v2.0.0"
INTENT_VERDICT_SCORE_MAP: dict[str, float] = {
    "PERFECT": 5.0,
    "GOOD": 4.0,
    "PARTIAL": 3.0,
    "WEAK": 2.0,
    "RELATED_BUT_WRONG": 1.0,
    "FAILED": 0.0,
}
ACCURACY_SOURCE_TAG_PREFIX = "[ACCURACY_SOURCE:"
ACCURACY_FAILED_PATHS_TAG_PREFIX = "[ACCURACY_FAILED_PATHS:"


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
        if isinstance(value, (int, float)):
            out[str(key)] = float(value)
    return out


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _canonicalize_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonicalize_json_value(value[key]) for key in sorted(value.keys())}
    if isinstance(value, list):
        return [_canonicalize_json_value(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _build_intent_input_payload(item: Any, raw_payload: dict[str, Any], max_chars: int) -> dict[str, Any]:
    data_ui = raw_payload.get("dataUIList")
    if not isinstance(data_ui, list):
        data_ui = []
    payload = {
        "query": _normalize_text(item.query_text_snapshot)[:max_chars],
        "expectedResult": _normalize_text(item.expected_result_snapshot)[:max_chars],
        "assistantMessage": _normalize_text(raw_payload.get("assistantMessage"))[:max_chars],
        "dataUIList": _canonicalize_json_value(data_ui[:3]),
    }
    return payload


def _extract_intent_verdict(result: Any) -> tuple[float | None, str, list[str]]:
    if not isinstance(result, dict):
        return None, "", []
    verdict = str(result.get("intent_verdict") or "").strip().upper()
    score = INTENT_VERDICT_SCORE_MAP.get(verdict)
    comment = _normalize_text(result.get("comment"))
    evidence_raw = result.get("evidence")
    evidence: list[str] = []
    if isinstance(evidence_raw, list):
        for entry in evidence_raw[:3]:
            text = _normalize_text(entry)
            if text:
                evidence.append(text)
    return score, comment, evidence


def _extract_accuracy_checks_from_llm_result(result: Any) -> list[dict[str, Any]]:
    if not isinstance(result, dict):
        return []
    supported_keys = (
        "formType",
        "actionType",
        "dataKey",
        "buttonKey",
        "buttonUrlContains",
        "multiSelectAllowYn",
        "assistantMessageContains",
    )
    lines: list[str] = []
    for key in supported_keys:
        value = result.get(key)
        if value is None:
            continue
        if isinstance(value, bool):
            value_text = "true" if value else "false"
        else:
            value_text = str(value).strip()
        if not value_text:
            continue
        lines.append(f"@check {key}={value_text}")
    if not lines:
        return []
    return parse_expected_result_accuracy_checks("\n".join(lines))


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
):
    db = SessionLocal()
    repo = ValidationRunRepository(db)
    repo.set_eval_status(run_id, EvalStatus.RUNNING)
    db.commit()

    try:
        run_items = repo.list_items(run_id, limit=100000)
        if not run_items:
            repo.set_eval_status(run_id, EvalStatus.DONE)
            db.commit()
            return
        missing_expected = [
            item for item in run_items if not str(item.expected_result_snapshot or "").strip()
        ]
        if missing_expected:
            sample_query_ids = [
                str(item.query_id or item.id or "")
                for item in missing_expected[:5]
                if str(item.query_id or item.id or "").strip()
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

        adapter = OpenAIJudgeAdapter()
        sem = asyncio.Semaphore(max(1, int(max_parallel or 1)))
        timeout = aiohttp.ClientTimeout(total=120)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async def _evaluate_item(item) -> None:
                raw_payload, raw_parse_ok = parse_raw_payload(item.raw_json or "")
                criteria_payload, legacy_fallback = parse_applied_criteria(item.applied_criteria_json or "")
                criteria_meta = criteria_payload.get("meta") if isinstance(criteria_payload, dict) else {}
                criteria_source = str((criteria_meta or {}).get("source") or "").strip() or "legacy"

                stability_score = score_stability(
                    error_text=item.error or "",
                    raw_payload=raw_payload,
                    raw_parse_ok=raw_parse_ok,
                )

                base_accuracy_checks = (
                    criteria_payload.get("accuracyChecks")
                    if isinstance(criteria_payload, dict)
                    and isinstance(criteria_payload.get("accuracyChecks"), list)
                    else []
                )
                expected_result_checks = parse_expected_result_accuracy_checks(item.expected_result_snapshot or "")
                merged_accuracy_checks = merge_accuracy_checks(base_accuracy_checks, expected_result_checks)
                accuracy_eval = evaluate_accuracy_checks(raw_payload, merged_accuracy_checks)

                llm_error_message = ""
                intent_comment = ""
                intent_evidence: list[str] = []
                intent_score = 0.0
                intent_payload = _build_intent_input_payload(item, raw_payload, max_chars)
                intent_payload_text = json.dumps(
                    intent_payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                )
                intent_input_hash = hashlib.sha256(intent_payload_text.encode("utf-8")).hexdigest()[:12]

                if (item.error or "").strip():
                    llm_error_message = "Execution failed. Intent evaluation skipped."
                elif not openai_key:
                    llm_error_message = "OpenAI API key is missing."
                else:
                    intent_rubric = criteria_payload.get("intentRubric") if isinstance(criteria_payload, dict) else {}
                    prompt = (
                        "다음 입력 JSON을 기준으로 의도 충족을 채점하세요.\n"
                        "반드시 JSON 객체만 출력하세요.\n"
                        "키는 intent_verdict, evidence, comment만 허용합니다.\n"
                        "intent_verdict 허용값: PERFECT, GOOD, PARTIAL, WEAK, RELATED_BUT_WRONG, FAILED\n"
                        "evidence는 최대 3개의 짧은 문자열만 허용합니다.\n"
                        "정확성(formType/dataKey/buttonUrl 등 구조값)은 별도 규칙엔진이 평가하므로 여기서는 의도만 판단하세요.\n\n"
                        f"의도 루브릭(JSON): {json.dumps(intent_rubric if isinstance(intent_rubric, dict) else {}, ensure_ascii=False)}\n\n"
                        f"입력 JSON: {intent_payload_text}\n\n"
                        '{"intent_verdict":"PERFECT|GOOD|PARTIAL|WEAK|RELATED_BUT_WRONG|FAILED","evidence":["근거1"],"comment":"판단 근거"}'
                    )
                    try:
                        async with sem:
                            result, _usage, err = await adapter.judge(session, openai_key, openai_model, prompt)
                        if result is None:
                            llm_error_message = err or "Intent evaluation failed."
                        else:
                            parsed_intent, parsed_comment, parsed_evidence = _extract_intent_verdict(result)
                            if parsed_intent is not None:
                                intent_score = parsed_intent
                            else:
                                llm_error_message = "Intent verdict parse failed."
                            intent_comment = parsed_comment
                            intent_evidence = parsed_evidence
                    except Exception as exc:
                        llm_error_message = str(exc)

                accuracy_extract_error = False
                accuracy_extract_used = False
                accuracy_extract_message = ""
                if not accuracy_eval.get("hasChecks"):
                    if (item.error or "").strip():
                        accuracy_extract_error = True
                        accuracy_extract_message = "Execution failed. Accuracy extractor skipped."
                    elif not openai_key:
                        accuracy_extract_error = True
                        accuracy_extract_message = "OpenAI API key is missing for accuracy extractor."
                    else:
                        extractor_prompt = (
                            "기대결과 텍스트를 읽고 정확성 검증용 키 후보를 추출하세요.\n"
                            "반드시 JSON 객체만 출력하고, 아래 키만 사용하세요.\n"
                            "허용 키: formType, actionType, dataKey, buttonKey, buttonUrlContains, multiSelectAllowYn, assistantMessageContains\n"
                            "값을 알 수 없으면 null 또는 빈 문자열을 사용하세요.\n\n"
                            f"질의: {_normalize_text(item.query_text_snapshot)[:max_chars]}\n\n"
                            f"기대결과: {_normalize_text(item.expected_result_snapshot)[:max_chars]}\n\n"
                            '{"formType":null,"actionType":null,"dataKey":null,"buttonKey":null,"buttonUrlContains":null,"multiSelectAllowYn":null,"assistantMessageContains":null}'
                        )
                        try:
                            async with sem:
                                extract_result, _usage, extract_err = await adapter.judge(
                                    session, openai_key, openai_model, extractor_prompt
                                )
                            if extract_result is None:
                                accuracy_extract_error = True
                                accuracy_extract_message = extract_err or "Accuracy extractor failed."
                            else:
                                extracted_checks = _extract_accuracy_checks_from_llm_result(extract_result)
                                merged_accuracy_checks = merge_accuracy_checks(merged_accuracy_checks, extracted_checks)
                                accuracy_eval = evaluate_accuracy_checks(raw_payload, merged_accuracy_checks)
                                if accuracy_eval.get("hasChecks"):
                                    accuracy_extract_used = True
                                else:
                                    accuracy_extract_error = True
                                    accuracy_extract_message = "Accuracy extractor returned empty checks."
                        except Exception as exc:
                            accuracy_extract_error = True
                            accuracy_extract_message = str(exc)

                accuracy_score = accuracy_eval.get("score")
                if not isinstance(accuracy_score, (int, float)):
                    accuracy_score = 0.0
                accuracy_score = max(0.0, min(5.0, float(accuracy_score)))
                if accuracy_extract_error:
                    accuracy_score = 0.0

                metric_scores = {
                    "의도충족": max(0.0, min(5.0, float(intent_score))),
                    "정확성": accuracy_score,
                    "안정성": max(0.0, min(5.0, float(stability_score))),
                }
                total_score = average(
                    [
                        metric_scores["의도충족"],
                        metric_scores["정확성"],
                        metric_scores["안정성"],
                    ]
                )

                failed_checks = accuracy_eval.get("failedChecks") or []
                failed_check_text = ""
                failed_paths_for_tag: list[str] = []
                if isinstance(failed_checks, list) and failed_checks:
                    failed_paths_for_tag = [
                        str(check.get("path") or "").strip()
                        for check in failed_checks
                        if isinstance(check, dict)
                    ]
                    failed_paths_for_tag = [path for path in failed_paths_for_tag if path]
                    if failed_paths_for_tag:
                        failed_check_text = f"Accuracy failed checks: {', '.join(failed_paths_for_tag[:6])}"

                accuracy_source_parts: list[str] = []
                if criteria_source == "template_json":
                    accuracy_source_parts.append("aqb")
                elif criteria_source == "template_helper":
                    accuracy_source_parts.append("helper")
                elif criteria_source == "legacy":
                    accuracy_source_parts.append("legacy")
                if expected_result_checks:
                    accuracy_source_parts.append("@check")
                if accuracy_extract_used:
                    accuracy_source_parts.append("llm_extract")
                if not accuracy_source_parts:
                    accuracy_source_parts.append("none")
                accuracy_source_text = "+".join(dict.fromkeys(accuracy_source_parts))

                comment_parts: list[str] = []
                comment_parts.append(f"[PROMPT_VERSION:{INTENT_PROMPT_VERSION}]")
                comment_parts.append(f"[INPUT_HASH:{intent_input_hash}]")
                comment_parts.append(f"{ACCURACY_SOURCE_TAG_PREFIX}{accuracy_source_text}]")
                if failed_paths_for_tag:
                    comment_parts.append(f"{ACCURACY_FAILED_PATHS_TAG_PREFIX}{','.join(failed_paths_for_tag[:20])}]")
                if intent_evidence:
                    comment_parts.append(f"Intent evidence: {'; '.join(intent_evidence)}")
                if intent_comment:
                    comment_parts.append(intent_comment)
                if failed_check_text:
                    comment_parts.append(failed_check_text)
                if legacy_fallback:
                    comment_parts.append(LEGACY_ACCURACY_FALLBACK_TAG)
                if accuracy_extract_used:
                    comment_parts.append(ACCURACY_LLM_EXTRACT_FALLBACK_TAG)
                if accuracy_extract_error:
                    comment_parts.append(f"Accuracy extractor fallback: {accuracy_extract_message or 'failed'}")
                if llm_error_message:
                    comment_parts.append(f"Intent judge fallback: {llm_error_message}")
                if not comment_parts:
                    comment_parts.append("OK")
                llm_comment = " | ".join(comment_parts)

                status = "DONE"
                if (item.error or "").strip():
                    status = "DONE_WITH_EXEC_ERROR"
                elif accuracy_extract_error:
                    status = "DONE_WITH_ACCURACY_EXTRACT_ERROR"
                elif llm_error_message:
                    status = "DONE_WITH_LLM_ERROR"
                elif legacy_fallback or accuracy_extract_used:
                    status = "DONE_LEGACY"

                repo.upsert_llm_eval(
                    item.id,
                    eval_model=openai_model,
                    metric_scores=metric_scores,
                    total_score=round(float(total_score), 4) if isinstance(total_score, (int, float)) else None,
                    llm_comment=llm_comment,
                    status=status,
                )

            await asyncio.gather(*[_evaluate_item(item) for item in run_items])
            db.commit()

        _build_score_snapshots(repo, run_id, run_items)
        db.commit()

        repo.set_eval_status(run_id, EvalStatus.DONE)
        db.commit()
    except Exception:
        repo.set_eval_status(run_id, EvalStatus.FAILED)
        db.commit()
        raise
    finally:
        db.close()
