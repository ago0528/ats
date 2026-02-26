from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from typing import Any, Optional


AQB_SCHEMA_VERSION = "aqb.v1"
AQB_RUBRIC_VERSION = "2026-02-24.v1"
LEGACY_ACCURACY_FALLBACK_TAG = "[LEGACY_ACCURACY_FALLBACK]"
ACCURACY_LLM_EXTRACT_FALLBACK_TAG = "[ACCURACY_LLM_EXTRACT_FALLBACK]"

DEFAULT_INTENT_RUBRIC = {
    "scale": "0-5",
    "policy": "intent_only",
}

_PATH_TOKEN_PATTERN = re.compile(r"([^[.\]]+)|\[(\*|\d+)\]")
_CHECK_LINE_PATTERN = re.compile(r"@check\s+(.+?)(?=(?:\s+@check\s+)|$)", re.IGNORECASE)
_LATENCY_CLASS_ALLOWED = {"SINGLE", "MULTI"}


def _parse_json_like(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def _normalize_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if value == 1:
            return True
        if value == 0:
            return False
        return None
    text = str(value or "").strip().lower()
    if not text:
        return None
    if text in {"true", "1", "y", "yes"}:
        return True
    if text in {"false", "0", "n", "no"}:
        return False
    return None


def _normalize_number(value: Any) -> Optional[float]:
    if not isinstance(value, (int, float)):
        return None
    out = float(value)
    if not math.isfinite(out):
        return None
    return out


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_latency_class(value: Any) -> Optional[str]:
    text = _safe_text(value).upper()
    if not text:
        return None
    if text not in _LATENCY_CLASS_ALLOWED:
        return None
    return text


def _build_named_accuracy_check(field_name: str, raw_value: Any) -> Optional[dict[str, Any]]:
    key = _safe_text(field_name)
    if not key:
        return None
    key_norm = key.lower()
    text_value = _safe_text(raw_value)

    if key_norm == "formtype" and text_value:
        return {"path": "dataUIList[*].uiValue.formType", "op": "eq", "value": text_value, "weight": 1}
    if key_norm == "actiontype" and text_value:
        return {"path": "dataUIList[*].uiValue.actionType", "op": "eq", "value": text_value, "weight": 1}
    if key_norm == "datakey" and text_value:
        return {"path": "dataUIList[*].uiValue.value.dataKey", "op": "eq", "value": text_value, "weight": 1}
    if key_norm == "buttonkey" and text_value:
        return {"path": "dataUIList[*].uiValue.value.buttonKey", "op": "eq", "value": text_value, "weight": 1}
    if key_norm == "buttonurlcontains" and text_value:
        return {"path": "dataUIList[*].uiValue.buttonUrl", "op": "contains", "value": text_value, "weight": 1}
    if key_norm == "assistantmessagecontains" and text_value:
        return {"path": "assistantMessage", "op": "contains", "value": text_value, "weight": 1}
    if key_norm == "multiselectallowyn":
        normalized = _normalize_bool(raw_value)
        if normalized is not None:
            return {"path": "dataUIList[*].uiValue.multiSelectAllowYn", "op": "eq", "value": normalized, "weight": 1}
    return None


def _build_helper_accuracy_checks(
    *,
    form_type: str = "",
    action_type: str = "",
    data_key: str = "",
    button_key: str = "",
    button_url_contains: str = "",
    multi_select_allow_yn: str = "",
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for key, value in (
        ("formType", form_type),
        ("actionType", action_type),
        ("dataKey", data_key),
        ("buttonKey", button_key),
        ("buttonUrlContains", button_url_contains),
        ("multiSelectAllowYn", multi_select_allow_yn),
    ):
        built = _build_named_accuracy_check(key, value)
        if built is not None:
            checks.append(built)
    return checks


def build_aqb_v1_criteria(
    criteria_input: Any,
    *,
    form_type: str = "",
    action_type: str = "",
    data_key: str = "",
    button_key: str = "",
    button_url_contains: str = "",
    multi_select_allow_yn: str = "",
    intent_rubric_json: str = "",
    accuracy_checks_json: str = "",
) -> dict[str, Any]:
    parsed_existing = _parse_json_like(criteria_input)
    if isinstance(parsed_existing, dict) and parsed_existing.get("schemaVersion") == AQB_SCHEMA_VERSION:
        payload = dict(parsed_existing)
        if not isinstance(payload.get("intentRubric"), dict):
            payload["intentRubric"] = dict(DEFAULT_INTENT_RUBRIC)
        if not isinstance(payload.get("accuracyChecks"), list):
            payload["accuracyChecks"] = []
        if not isinstance(payload.get("meta"), dict):
            payload["meta"] = {}
        payload["meta"].setdefault("source", "template_json")
        payload["meta"].setdefault("rubricVersion", AQB_RUBRIC_VERSION)
        return payload

    parsed_intent_rubric = _parse_json_like(intent_rubric_json)
    parsed_accuracy_checks = _parse_json_like(accuracy_checks_json)
    helper_checks = _build_helper_accuracy_checks(
        form_type=form_type,
        action_type=action_type,
        data_key=data_key,
        button_key=button_key,
        button_url_contains=button_url_contains,
        multi_select_allow_yn=multi_select_allow_yn,
    )

    merged_checks: list[Any] = []
    if isinstance(parsed_accuracy_checks, list):
        merged_checks.extend(parsed_accuracy_checks)
    merged_checks.extend(helper_checks)

    has_helper_inputs = (
        bool(helper_checks)
        or isinstance(parsed_intent_rubric, dict)
        or isinstance(parsed_accuracy_checks, list)
    )

    payload: dict[str, Any] = {
        "schemaVersion": AQB_SCHEMA_VERSION,
        "intentRubric": parsed_intent_rubric if isinstance(parsed_intent_rubric, dict) else dict(DEFAULT_INTENT_RUBRIC),
        "accuracyChecks": merged_checks,
        "meta": {
            "source": "template_helper" if has_helper_inputs else "legacy",
            "rubricVersion": AQB_RUBRIC_VERSION,
        },
    }
    if not has_helper_inputs and parsed_existing is not None:
        payload["meta"]["legacyCriteria"] = parsed_existing
    elif not has_helper_inputs:
        raw_text = _safe_text(criteria_input)
        if raw_text:
            payload["meta"]["legacyCriteria"] = raw_text
    return payload


def parse_applied_criteria(criteria_text: Any) -> tuple[dict[str, Any], bool]:
    payload = build_aqb_v1_criteria(criteria_text)
    source = _safe_text((payload.get("meta") or {}).get("source"))
    is_legacy = source == "legacy" or len(payload.get("accuracyChecks") or []) == 0
    return payload, is_legacy


def apply_latency_class_to_criteria(criteria_payload: dict[str, Any], latency_class: Any) -> dict[str, Any]:
    normalized = normalize_latency_class(latency_class)
    if normalized is None:
        return criteria_payload
    next_payload = dict(criteria_payload or {})
    meta = dict(next_payload.get("meta") or {})
    meta["latencyClass"] = normalized
    next_payload["meta"] = meta
    return next_payload


def extract_latency_class(criteria_input: Any) -> Optional[str]:
    parsed = _parse_json_like(criteria_input)
    if not isinstance(parsed, dict):
        return None
    meta = parsed.get("meta")
    if not isinstance(meta, dict):
        return None
    return normalize_latency_class(meta.get("latencyClass"))


def parse_expected_result_accuracy_checks(expected_result: str) -> list[dict[str, Any]]:
    text = str(expected_result or "")
    checks: list[dict[str, Any]] = []
    for match in _CHECK_LINE_PATTERN.finditer(text):
        body = _safe_text(match.group(1))
        if not body:
            continue
        segments = [segment.strip() for segment in body.split(";") if segment.strip()]
        for segment in segments:
            if segment.lower().startswith("@check "):
                segment = segment[7:].strip()
            if "=" not in segment:
                continue
            field_name, raw_value = segment.split("=", 1)
            built = _build_named_accuracy_check(field_name, raw_value)
            if built is not None:
                checks.append(built)
    return checks


def merge_accuracy_checks(primary_checks: list[Any], secondary_checks: list[Any]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen_signatures: set[tuple[str, str]] = set()

    def _append(source_checks: list[Any]) -> None:
        for check in source_checks:
            if not isinstance(check, dict):
                continue
            path = _safe_text(check.get("path"))
            op = _safe_text(check.get("op")).lower()
            if not path or not op:
                continue
            signature = (path, op)
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            merged.append(dict(check))

    _append(primary_checks)
    _append(secondary_checks)
    return merged


def parse_raw_payload(raw_json: str) -> tuple[dict[str, Any], bool]:
    text = _safe_text(raw_json)
    if not text:
        return {}, False
    try:
        payload = json.loads(text)
    except Exception:
        return {}, False
    if not isinstance(payload, dict):
        return {}, False
    return payload, True


def has_response_content(raw_payload: dict[str, Any]) -> bool:
    assistant_message = _safe_text(raw_payload.get("assistantMessage"))
    if assistant_message:
        return True
    data_ui_list = raw_payload.get("dataUIList")
    return isinstance(data_ui_list, list) and len(data_ui_list) > 0


def score_stability(*, error_text: str, raw_payload: dict[str, Any], raw_parse_ok: bool) -> float:
    if _safe_text(error_text):
        return 0.0
    if not raw_parse_ok:
        return 0.0
    if not has_response_content(raw_payload):
        return 0.0
    return 5.0


def classify_tool_mode(raw_payload: dict[str, Any]) -> str:
    execution_processes = raw_payload.get("executionProcesses")
    workers = raw_payload.get("worker")
    execution_count = len(execution_processes) if isinstance(execution_processes, list) else 0
    worker_count = len(workers) if isinstance(workers, list) else 0
    if execution_count >= 2 or worker_count >= 2:
        return "multi"
    return "single"


def extract_response_time_sec(raw_payload: dict[str, Any], latency_ms: Optional[int] = None) -> Optional[float]:
    direct = _normalize_number(raw_payload.get("responseTimeSec"))
    if direct is not None:
        return direct
    if latency_ms is None:
        return None
    parsed_latency = _normalize_number(latency_ms)
    if parsed_latency is None:
        return None
    return parsed_latency / 1000.0


def score_latency(response_time_sec: Optional[float], mode: str) -> Optional[float]:
    if response_time_sec is None:
        return None
    sec = float(response_time_sec)
    if mode == "multi":
        if sec <= 20:
            return 5.0
        if sec <= 30:
            return 4.0
        if sec <= 40:
            return 3.0
        if sec <= 50:
            return 2.0
        if sec <= 60:
            return 1.0
        return 0.0

    if sec <= 5:
        return 5.0
    if sec <= 8:
        return 4.0
    if sec <= 10:
        return 3.0
    if sec <= 15:
        return 2.0
    if sec <= 20:
        return 1.0
    return 0.0


def ratio_to_score(ratio: float) -> float:
    normalized = max(0.0, min(1.0, float(ratio)))
    if normalized == 1.0:
        return 5.0
    if normalized >= 0.75:
        return 4.0
    if normalized >= 0.5:
        return 3.0
    if normalized >= 0.25:
        return 2.0
    if normalized > 0.0:
        return 1.0
    return 0.0


def _path_tokens(path: str) -> list[str]:
    tokens: list[str] = []
    for segment in str(path or "").split("."):
        for match in _PATH_TOKEN_PATTERN.finditer(segment):
            token = match.group(1) if match.group(1) is not None else match.group(2)
            if token is None:
                continue
            tokens.append(token)
    return tokens


def extract_path_values(payload: Any, path: str) -> list[Any]:
    tokens = _path_tokens(path)
    if not tokens:
        return []
    current: list[Any] = [payload]
    for token in tokens:
        next_values: list[Any] = []
        if token == "*":
            for value in current:
                if isinstance(value, list):
                    next_values.extend(value)
            current = next_values
            continue

        if token.isdigit():
            index = int(token)
            for value in current:
                if isinstance(value, list) and 0 <= index < len(value):
                    next_values.append(value[index])
            current = next_values
            continue

        for value in current:
            if isinstance(value, dict) and token in value:
                next_values.append(value[token])
        current = next_values
    return current


def _equals(actual: Any, expected: Any) -> bool:
    actual_number = _normalize_number(actual)
    expected_number = _normalize_number(expected)
    if actual_number is not None and expected_number is not None:
        return abs(actual_number - expected_number) < 1e-9

    actual_bool = _normalize_bool(actual)
    expected_bool = _normalize_bool(expected)
    if actual_bool is not None and expected_bool is not None:
        return actual_bool == expected_bool

    return _safe_text(actual) == _safe_text(expected)


def _contains(actual: Any, expected: Any) -> bool:
    expected_text = _safe_text(expected)
    if not expected_text:
        return False
    if isinstance(actual, list):
        return any(_equals(item, expected) for item in actual)
    return expected_text in _safe_text(actual)


def _in(actual: Any, expected: Any) -> bool:
    if not isinstance(expected, list):
        return False
    return any(_equals(actual, item) for item in expected)


def _regex(actual: Any, expected: Any) -> bool:
    pattern = _safe_text(expected)
    if not pattern:
        return False
    try:
        return re.search(pattern, _safe_text(actual)) is not None
    except re.error:
        return False


def evaluate_accuracy_checks(raw_payload: dict[str, Any], checks: list[Any]) -> dict[str, Any]:
    valid_checks: list[dict[str, Any]] = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        path = _safe_text(check.get("path"))
        op = _safe_text(check.get("op")).lower()
        if not path or not op:
            continue
        weight = _normalize_number(check.get("weight"))
        valid_checks.append(
            {
                "path": path,
                "op": op,
                "value": check.get("value"),
                "weight": weight if weight is not None and weight > 0 else 1.0,
            }
        )

    if not valid_checks:
        return {
            "hasChecks": False,
            "score": None,
            "passRatio": None,
            "passedWeight": 0.0,
            "totalWeight": 0.0,
            "failedChecks": [],
        }

    passed_weight = 0.0
    total_weight = 0.0
    failed_checks: list[dict[str, Any]] = []

    for check in valid_checks:
        path = check["path"]
        op = check["op"]
        expected_value = check.get("value")
        weight = float(check["weight"])
        values = extract_path_values(raw_payload, path)
        total_weight += weight

        passed = False
        if op == "exists":
            passed = any(value is not None and (_safe_text(value) != "" or isinstance(value, (dict, list))) for value in values)
        elif op == "eq":
            passed = any(_equals(value, expected_value) for value in values)
        elif op == "contains":
            passed = any(_contains(value, expected_value) for value in values)
        elif op == "in":
            passed = any(_in(value, expected_value) for value in values)
        elif op == "regex":
            passed = any(_regex(value, expected_value) for value in values)

        if passed:
            passed_weight += weight
        else:
            failed_checks.append(
                {
                    "path": path,
                    "op": op,
                    "value": expected_value,
                }
            )

    ratio = (passed_weight / total_weight) if total_weight > 0 else 0.0
    return {
        "hasChecks": True,
        "score": ratio_to_score(ratio),
        "passRatio": ratio,
        "passedWeight": passed_weight,
        "totalWeight": total_weight,
        "failedChecks": failed_checks,
    }


def metric_value(metric_scores: dict[str, Any], metric_name: str) -> Optional[float]:
    if not isinstance(metric_scores, dict):
        return None
    parsed = _normalize_number(metric_scores.get(metric_name))
    if parsed is None:
        return None
    return parsed


def quantile(values: list[float], q: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * max(0.0, min(1.0, q))))
    return float(ordered[index])


def average(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return float(sum(values) / len(values))


def score_bucket(score: Optional[float]) -> Optional[str]:
    if score is None:
        return None
    return str(int(max(0, min(5, round(score)))))


def build_consistency_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        query_key = _safe_text(record.get("queryKey"))
        if not query_key:
            continue
        grouped[query_key].append(record)

    eligible_count = 0
    consistent_count = 0
    for query_key in grouped:
        rows = grouped[query_key]
        if len(rows) < 2:
            continue
        eligible_count += 1
        pass_flags: list[bool] = []
        for row in rows:
            intent = _normalize_number(row.get("intentScore")) or 0.0
            accuracy = _normalize_number(row.get("accuracyScore")) or 0.0
            stability = _normalize_number(row.get("stabilityScore")) or 0.0
            pass_flags.append(intent >= 3.0 and accuracy >= 3.0 and stability >= 5.0)
        if all(pass_flags) or not any(pass_flags):
            consistent_count += 1

    if eligible_count == 0:
        return {
            "status": "PENDING",
            "score": None,
            "eligibleQueryCount": 0,
            "consistentQueryCount": 0,
        }

    score = 5.0 * (consistent_count / eligible_count)
    return {
        "status": "READY",
        "score": round(score, 4),
        "eligibleQueryCount": eligible_count,
        "consistentQueryCount": consistent_count,
    }
