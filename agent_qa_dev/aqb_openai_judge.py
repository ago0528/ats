from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def extract_usage_fields(resp_json: Dict[str, Any]) -> Dict[str, int]:
    usage = (resp_json or {}).get("usage") or {}
    if not isinstance(usage, dict):
        usage = {}

    input_tokens = usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0
    output_tokens = usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0
    total_tokens = usage.get("total_tokens", 0) or 0

    itd = usage.get("input_tokens_details", usage.get("prompt_tokens_details", {})) or {}
    if not isinstance(itd, dict):
        itd = {}
    cached_tokens = itd.get("cached_tokens", 0) or 0

    otd = usage.get("output_tokens_details", usage.get("completion_tokens_details", {})) or {}
    if not isinstance(otd, dict):
        otd = {}
    reasoning_tokens = otd.get("reasoning_tokens", 0) or 0

    def _to_int(x: Any) -> int:
        try:
            return int(x)
        except Exception:
            try:
                return int(float(x))
            except Exception:
                return 0

    return {
        "input_tokens": _to_int(input_tokens),
        "output_tokens": _to_int(output_tokens),
        "cached_tokens": _to_int(cached_tokens),
        "reasoning_tokens": _to_int(reasoning_tokens),
        "total_tokens": _to_int(total_tokens),
    }


def estimate_cost_usd(
    usage: Dict[str, int],
    price_input_per_1m: float,
    price_output_per_1m: float,
    price_cached_input_per_1m: float,
) -> float:
    if not usage:
        return 0.0
    inp = float(usage.get("input_tokens", 0) or 0)
    out = float(usage.get("output_tokens", 0) or 0)
    cached = float(usage.get("cached_tokens", 0) or 0)
    uncached = max(0.0, inp - cached)

    cost = 0.0
    if price_input_per_1m > 0:
        cost += (uncached / 1_000_000.0) * float(price_input_per_1m)
    if price_cached_input_per_1m > 0:
        cost += (cached / 1_000_000.0) * float(price_cached_input_per_1m)
    if price_output_per_1m > 0:
        cost += (out / 1_000_000.0) * float(price_output_per_1m)
    return float(cost)
def extract_openai_output_text(resp_json: Dict[str, Any]) -> str:
    """
    Responses API 응답에서 텍스트를 최대한 안전하게 추출.
    - SDK의 output_text와 달리 raw JSON에서는 output 배열을 파싱해야 할 수 있음.
    """
    if isinstance(resp_json, dict) and isinstance(resp_json.get("output_text"), str):
        return resp_json["output_text"]

    out = resp_json.get("output", [])
    texts: List[str] = []
    if isinstance(out, list):
        for item in out:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "message":
                content = item.get("content", [])
                if isinstance(content, list):
                    for c in content:
                        if not isinstance(c, dict):
                            continue
                        ctype = c.get("type")
                        if ctype in ("output_text", "text"):
                            t = c.get("text")
                            if isinstance(t, str):
                                texts.append(t)
            # 일부 응답은 output에 바로 text가 올 수도 있어 방어적으로 처리
            if isinstance(item.get("text"), str):
                texts.append(item["text"])
    return "\n".join(texts).strip()


def coerce_int_0_100(x: Any) -> int:
    try:
        v = int(float(x))
    except Exception:
        return 0
    return max(0, min(100, v))


def _looks_like_error_response(raw: str) -> bool:
    """응답 원문(raw)이 에러/사과 메시지인지 휴리스틱 판별."""
    if not raw or not isinstance(raw, str):
        return False
    s = raw.strip()
    if not s:
        return False
    # JSON이면 assistantMessage 내용만 검사
    try:
        parsed = json.loads(s)
        if isinstance(parsed, dict) and "assistantMessage" in parsed:
            s = str(parsed["assistantMessage"]) if parsed["assistantMessage"] else ""
    except Exception:
        pass
    s_lower = s.lower()
    error_markers = ("죄송해요", "문제가 발생", "에러", "error", "timeout", "오류")
    return any(m in s or m in s_lower for m in error_markers)


def _infer_stability_from_responses(
    response_1_raw: Optional[str], response_2_raw: Optional[str]
) -> Dict[str, Any]:
    """1차/2차 응답 원문으로 안정성(stability) 객체를 추론."""
    err1 = _looks_like_error_response(response_1_raw or "")
    err2 = _looks_like_error_response(response_2_raw or "")
    status_1 = "에러" if err1 else "정상"
    status_2 = "에러" if err2 else "정상"
    if err1 and err2:
        score = 0
        note = "응답 내용 기반 추론: 양쪽 모두 에러 메시지"
    elif err1 or err2:
        score = 3
        note = "응답 내용 기반 추론: 한쪽 에러"
    else:
        score = 5
        note = ""
    return {
        "score": score,
        "response_1_status": status_1,
        "response_2_status": status_2,
        "note": note,
    }


def robust_json_loads(s: str) -> Optional[Dict[str, Any]]:
    """
    1) 그대로 json.loads
    2) 실패 시: 첫 '{'부터 마지막 '}'까지 잘라서 재시도
    """
    if not s:
        return None
    s = s.strip()
    try:
        obj = json.loads(s)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass

    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            obj = json.loads(s[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None
    return None


async def openai_judge_once(
    session: aiohttp.ClientSession,
    api_key: str,
    model: str,
    prompt_text: str,
    timeout_sec: int = 90,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, int], str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": "You are a QA evaluator. Output MUST be a valid JSON object and nothing else. JSON only.",
            },
            {"role": "user", "content": prompt_text},
        ],
        "text": {"format": {"type": "json_object"}},
        "temperature": 0,
    }

    try:
        async with session.post(OPENAI_RESPONSES_URL, headers=headers, json=payload, timeout=timeout_sec) as resp:
            text = await resp.text()
            if resp.status != 200:
                return None, {}, f"OpenAI HTTP {resp.status}: {text[:250]}"
            data = json.loads(text)

            usage = extract_usage_fields(data)

            out_text = extract_openai_output_text(data)
            parsed = robust_json_loads(out_text)
            if parsed is None:
                return None, usage, f"OpenAI output is not JSON. raw={out_text[:200]}"
            return parsed, usage, ""
    except asyncio.TimeoutError:
        return None, {}, f"OpenAI timeout({timeout_sec}s)"
    except Exception as e:
        return None, {}, f"OpenAI error: {type(e).__name__}: {str(e)[:200]}"

async def openai_judge_with_retry(
    session: aiohttp.ClientSession,
    api_key: str,
    model: str,
    prompt_text: str,
    max_retries: int = 2,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, int], str]:
    wait = 2.0
    last_err = ""
    last_usage: Dict[str, int] = {}

    for _attempt in range(max_retries + 1):
        result, usage, err = await openai_judge_once(session, api_key, model, prompt_text)
        if usage:
            last_usage = usage
        if result is not None and not err:
            return result, last_usage, ""
        last_err = err or "unknown"
        await asyncio.sleep(wait)
        wait *= 2

    return None, last_usage, last_err


def postprocess_eval_json(
    obj: Dict[str, Any],
    response_1_raw: Optional[str] = None,
    response_2_raw: Optional[str] = None,
) -> Dict[str, Any]:
    """
    - score 필드 정수화/클램프
    - total_score 재계산(안전)
    - 누락 키 방어적으로 채움
    - accuracy 비어 있으면 filter_accuracy에서 fallback
    - stability 비어 있고 response_1_raw/response_2_raw가 있으면 응답 내용으로 추론
    """
    out = obj.copy()
    fa = out.get("filter_accuracy") if isinstance(out.get("filter_accuracy"), dict) else {}

    # stability (안정성)
    stab = out.get("stability") if isinstance(out.get("stability"), dict) else {}
    stab_score = coerce_int_0_100(stab.get("score"))
    stab["score"] = stab_score
    stab["response_1_status"] = str(stab.get("response_1_status") or "")
    stab["response_2_status"] = str(stab.get("response_2_status") or "")
    stab["note"] = str(stab.get("note") or "")
    # stability 비어 있으면 1차/2차 응답 원문으로 추론
    stability_empty = (
        stab_score == 0
        and not stab.get("response_1_status")
        and not stab.get("response_2_status")
    )
    if stability_empty and response_1_raw and response_2_raw:
        inferred = _infer_stability_from_responses(response_1_raw, response_2_raw)
        stab = {**stab, **inferred}
        stab_score = coerce_int_0_100(stab["score"])
    out["stability"] = stab

    # accuracy (정확도) - 비어 있으면 filter_accuracy에서 fallback
    acc = out.get("accuracy") if isinstance(out.get("accuracy"), dict) else {}
    acc_score = coerce_int_0_100(acc.get("score"))
    acc["score"] = acc_score
    acc["expected"] = acc.get("expected") if isinstance(acc.get("expected"), list) else []
    acc["detected"] = acc.get("detected") if isinstance(acc.get("detected"), list) else []
    acc["note"] = str(acc.get("note") or "")
    accuracy_empty = (
        acc_score == 0 and not acc.get("expected") and not acc.get("detected")
    )
    if accuracy_empty and fa:
        acc["score"] = coerce_int_0_100(fa.get("score"))
        acc["expected"] = fa.get("expected") if isinstance(fa.get("expected"), list) else []
        acc["detected"] = fa.get("detected") if isinstance(fa.get("detected"), list) else []
        acc["note"] = str(fa.get("note") or "")
    acc_score = coerce_int_0_100(acc["score"])
    out["accuracy"] = acc

    # consistency (일관성)
    con = out.get("consistency") if isinstance(out.get("consistency"), dict) else {}
    con_score = coerce_int_0_100(con.get("score"))
    con["score"] = con_score
    con["matched"] = con.get("matched") if isinstance(con.get("matched"), list) else []
    con["diff"] = con.get("diff") if isinstance(con.get("diff"), list) else []
    con["note"] = str(con.get("note") or "")
    out["consistency"] = con

    # total_score: (stability + accuracy + consistency) / 3
    out["total_score"] = round((stab_score + acc_score + con_score) / 3, 2)
    out["remarks"] = str(out.get("remarks") or "")

    return out


def derive_csv_fields_from_eval(eval_json: Dict[str, Any]) -> Dict[str, str]:
    """
    CSV 템플릿 컬럼(열/필터 일치 여부, 답변 일관성, 차이 유형, 특이사항)을
    LLM 평가 결과(JSON)에서 도출.
    """
    stab = eval_json.get("stability", {}) or {}
    acc = eval_json.get("accuracy", {}) or {}
    con = eval_json.get("consistency", {}) or {}

    stab_score = int(stab.get("score", 0))
    acc_score = int(acc.get("score", 0))
    con_score = int(con.get("score", 0))

    # 안정성이 0이면 전체 실패로 처리
    if stab_score == 0:
        filter_pass = "FAIL"
        consistency = "평가 불가"
        diff_type = "응답 실패"
    else:
        # 기준: 프롬프트 정의 그대로(4 이상은 기대필터 사용 + 추가필터)
        filter_pass = "PASS" if acc_score >= 4 else "FAIL"

        # 안정성이 3점이면 일관성 평가 불가
        if stab_score == 3:
            consistency = "평가 불가"
        else:
            consistency = "일치" if con_score >= 4 else "차이 발생"

        # 차이 유형 (검증 규칙 문서의 분류를 LLM 평가 결과로 매핑)
        diff_type = ""
        if acc_score < 4:
            diff_type = "열/필터 변경"
        else:
            if con_score < 4:
                diff_type = "통계값만 변경"
            elif con_score < 5:
                diff_type = "표현만 변경"
            else:
                diff_type = ""

    note_parts = []
    stab_note = str(stab.get("note") or "").strip()
    acc_note = str(acc.get("note") or "").strip()
    con_note = str(con.get("note") or "").strip()
    remarks = str(eval_json.get("remarks") or "").strip()

    for s in [stab_note, acc_note, con_note, remarks]:
        if s and s not in note_parts:
            note_parts.append(s)

    return {
        "열/필터 일치 여부": filter_pass,
        "답변 일관성": consistency,
        "차이 유형": diff_type,
        "특이사항": " / ".join(note_parts),
    }
