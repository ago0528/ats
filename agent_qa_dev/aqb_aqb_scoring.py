from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import parse_qs, unquote, urlparse

import aiohttp
import pandas as pd

from aqb_openai_judge import openai_judge_with_retry

AQB_SCORE_COLUMNS: List[str] = [
    "run_id",
    "query_id",
    "query_text",
    "agent_type",
    "semantic_score",
    "consistency_score",
    "accuracy_score",
    "speed_score",
    "stability_score",
    "weighted_total",
    "flag_manual_review",
    "ttft_pass",
    "semantic_reason",
    "consistency_reason",
    "accuracy_reason",
    "speed_reason",
    "stability_reason",
    "semantic_calc_method",
    "consistency_calc_method",
    "accuracy_calc_method",
    "speed_calc_method",
    "stability_calc_method",
    "speed_single_score",
    "speed_multi_score",
    "response_time_avg_sec",
    "additional_tool_calls",
    "response_error_or_blank",
]

AQB_RULES_SUMMARY_MD = """
### AQB v1.2.0 규칙 요약
- 점수 범위: 모든 지표는 0~5점
- 산출 원칙: 문항별 점수 산출 후 평균, 필요 시 회차 평균 후 에이전트 최종 평균
- 지표: 의도 충족, 일관성, 정확성, 응답 속도, 안정성
- 종합 점수: `semantic*0.2 + consistency*0.1 + accuracy*0.3 + speed*0.2 + stability*0.2`
- 수기 확인 플래그: 아래 중 하나라도 충족 시 `true`
  - 의도 충족 <= 2
  - 정확성 <= 2
  - 안정성 <= 2
  - 종합 점수 <= 2.5
  - 응답 중 하나라도 에러/빈 응답
- TTFT: PASS/FAIL만 기록하고 종합 점수에는 반영하지 않음
"""

AQB_RUBRIC_MD = """
### 지표별 루브릭 (0~5)

#### 1) 의도 충족 (Semantic)
- 5: 의도한 조건(필터/datakey) 정확 + 응답 표현 적절
- 4: 조건은 정확하나 톤/표현 일부 부정확
- 3: 핵심 의도 파악했지만 조건 일부 누락/불필요 조건 추가
- 2: 의도 일부만 반영
- 1: 조건 매핑 실패지만 관련 응답
- 0: 전혀 다른 의도 또는 응답 실패

#### 2) 일관성 (Consistency, 기본 3회)
- 5: 3회 모두 숫자+결론 일치
- 4: 3회 결론 일치, 숫자 허용오차(기본 ±1%) 내
- 3: 3회 중 2회 숫자+결론 일치
- 2: 3회 중 2회 결론만 일치
- 1: 결론은 유사하나 숫자 매번 다름
- 0: 모두 상이 또는 평가 불가

#### 3) 정확성 (Accuracy)
- 실행/이동 에이전트(datakey):
  - 5: 기대 datakey 정확 사용
  - 3: 기대 datakey 포함 + 추가 datakey
  - 0: 기대 datakey 미포함
- 지원자 관리(필터 + Ground Truth):
  - 5: 필터 정확 + 수치 정확
  - 4: 필터 정확 + 수치 허용오차 내
  - 3: 필터 부정확하나 수치 정확/근접
  - 2: 필터 정확하나 수치 부정확
  - 1: 필터 부분 일치 + 수치 부정확
  - 0: 필터 불일치 + 수치 부정확

#### 4) 응답 속도 (Speed)
- 단일 도구 호출:
  - 5: <=5초, 4: 5~8초, 3: 8~10초, 2: 10~15초, 1: 15~20초, 0: >20초/타임아웃
- 복수 도구 호출:
  - 지원자 관리: 5<=20, 4:20~30, 3:30~40, 2:40~50, 1:50~60, 0:>60
  - 그 외 에이전트: 5<=10, 4:10~15, 3:15~20, 2:20~30, 1:30~45, 0:>45

#### 5) 안정성 (Stability)
- 5: 정상 응답
- 0: 에러/타임아웃/Null/빈 응답

#### 6) 종합 점수
- `semantic*0.2 + consistency*0.1 + accuracy*0.3 + speed*0.2 + stability*0.2`
- TTFT는 `ttft_pass`로만 표기, 종합 가중치에는 미반영
"""

_ERROR_MARKERS = (
    "error",
    "오류",
    "timeout",
    "타임아웃",
    "실패",
    "예외",
    "문제가 발생",
    "죄송",
    "http",
    "llm 평가 실패",
)

_ROUND_ALIASES = ["회차", "run_id", "run", "execution_round", "batch", "batch_id"]
_ORDINALS = ["1차", "2차", "3차", "4차"]
_RESPONSE_COLS = [f"{o} 답변" for o in _ORDINALS]
_RESPONSE_TIME_COLS = [f"{o} 답변 시간(초)" for o in _ORDINALS]
_RESPONSE_STATUS_COLS = [f"{o} 응답 상태" for o in _ORDINALS]


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    return out


def _pick_col(columns: Sequence[str], aliases: Sequence[str]) -> Optional[str]:
    for alias in aliases:
        target = alias.strip().lower()
        for c in columns:
            if str(c).strip().lower() == target:
                return str(c)
    return None


def _to_str(v: Any) -> str:
    if v is None:
        return ""
    s = str(v)
    if s.strip().lower() == "nan":
        return ""
    return s.strip()


def _is_blank(v: Any) -> bool:
    return _to_str(v) == ""


def _to_float(v: Any) -> Optional[float]:
    s = _to_str(v)
    if not s:
        return None
    try:
        return float(s)
    except Exception:
        try:
            return float(s.replace(",", ""))
        except Exception:
            return None


def _clamp_score(score: Any) -> int:
    try:
        s = int(round(float(score)))
    except Exception:
        return 0
    return max(0, min(5, s))


def _parse_tokens(raw: str) -> List[str]:
    s = _to_str(raw)
    if not s:
        return []
    s = s.replace(";", ",").replace("|", ",").replace("/", ",")

    out: List[str] = []
    for part in s.split(","):
        tok = part.strip()
        if tok:
            out.append(tok)

    uniq: List[str] = []
    seen = set()
    for t in out:
        low = t.lower()
        if low in seen:
            continue
        seen.add(low)
        uniq.append(t)
    return uniq


def _norm_set(tokens: Iterable[str]) -> set:
    return {str(t).strip().lower() for t in tokens if str(t).strip()}


def _extract_numbers(text: str) -> List[float]:
    s = _to_str(text)
    if not s:
        return []
    pattern = re.compile(r"[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?%?|[-+]?\d+(?:\.\d+)?%?")
    nums: List[float] = []
    for m in pattern.finditer(s):
        tok = m.group(0)
        if not tok:
            continue
        is_pct = tok.endswith("%")
        tok = tok[:-1] if is_pct else tok
        tok = tok.replace(",", "")
        try:
            nums.append(float(tok))
        except Exception:
            continue
    return nums


def _mean(values: Sequence[float]) -> Optional[float]:
    arr = [float(v) for v in values if v is not None]
    if not arr:
        return None
    return sum(arr) / len(arr)


def _relative_close(a: float, b: float, tolerance_pct: float) -> bool:
    base = max(abs(a), abs(b), 1e-9)
    return (abs(a - b) / base) <= (tolerance_pct / 100.0)


def _tokenize_text(text: str) -> List[str]:
    s = _to_str(text).lower()
    if not s:
        return []
    return [t for t in re.findall(r"[a-z0-9가-힣]+", s) if len(t) > 1]


def _text_similarity(a: str, b: str) -> float:
    ta = set(_tokenize_text(a))
    tb = set(_tokenize_text(b))
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return float(inter) / float(union) if union else 0.0


def _contains_error_text(text: str) -> bool:
    s = _to_str(text).lower()
    if not s:
        return False
    return any(marker in s for marker in _ERROR_MARKERS)


def _extract_datakeys_from_url(url: str) -> List[str]:
    u = _to_str(url)
    if not u:
        return []

    try:
        parsed = urlparse(u)
    except Exception:
        return []

    keys: List[str] = []
    qs = parse_qs(parsed.query)
    for name in ("dataKey", "datakey", "data_key"):
        for val in qs.get(name, []):
            tok = _to_str(unquote(str(val)))
            if tok:
                keys.append(tok)

    for tok in re.findall(r"(?:dataKey|datakey)=([A-Za-z0-9_\-.]+)", u):
        if tok:
            keys.append(tok)

    uniq: List[str] = []
    seen = set()
    for key in keys:
        low = key.lower()
        if low in seen:
            continue
        seen.add(low)
        uniq.append(key)
    return uniq


def _extract_datakeys_from_raw_json(raw_text: str) -> List[str]:
    s = _to_str(raw_text)
    if not s:
        return []
    try:
        obj = json.loads(s)
    except Exception:
        return []

    keys: List[str] = []

    def _walk(v: Any):
        if isinstance(v, dict):
            for k, vv in v.items():
                k_low = str(k).lower()
                if k_low in ("datakey", "data_key"):
                    tok = _to_str(vv)
                    if tok:
                        keys.append(tok)
                _walk(vv)
        elif isinstance(v, list):
            for item in v:
                _walk(item)

    _walk(obj)

    uniq: List[str] = []
    seen = set()
    for key in keys:
        low = key.lower()
        if low in seen:
            continue
        seen.add(low)
        uniq.append(key)
    return uniq


def _collect_run_id(row: pd.Series, columns: Sequence[str]) -> str:
    col = _pick_col(columns, _ROUND_ALIASES)
    if col:
        v = _to_str(row.get(col))
        if v:
            return v
    return "run-1"


def _collect_response_texts(row: pd.Series) -> List[str]:
    texts: List[str] = []
    for col in _RESPONSE_COLS:
        if col in row.index:
            s = _to_str(row.get(col))
            if s:
                texts.append(s)

    if not texts and "응답" in row.index:
        s = _to_str(row.get("응답"))
        if s:
            texts.append(s)
    return texts


def _collect_response_times(row: pd.Series) -> List[float]:
    times: List[float] = []
    for col in _RESPONSE_TIME_COLS:
        if col in row.index:
            v = _to_float(row.get(col))
            if v is not None:
                times.append(v)

    if not times and "응답 시간(초)" in row.index:
        v = _to_float(row.get("응답 시간(초)"))
        if v is not None:
            times.append(v)
    return times


def _collect_statuses(row: pd.Series) -> List[str]:
    statuses: List[str] = []
    for col in _RESPONSE_STATUS_COLS + ["1차 응답 상태", "2차 응답 상태"]:
        if col in row.index:
            s = _to_str(row.get(col))
            if s:
                statuses.append(s)
    return statuses


def _collect_expected_filters(row: pd.Series, columns: Sequence[str]) -> List[str]:
    col = _pick_col(columns, ["기대 필터/열", "expected_filters", "기대 필터"])
    if not col:
        return []
    return _parse_tokens(_to_str(row.get(col)))


def _collect_detected_filters(row: pd.Series, columns: Sequence[str]) -> List[str]:
    vals: List[str] = []
    for alias in ["감지된 필터", "1차 감지된 필터", "2차 감지된 필터", "detected_filters"]:
        col = _pick_col(columns, [alias])
        if col:
            vals.extend(_parse_tokens(_to_str(row.get(col))))

    uniq: List[str] = []
    seen = set()
    for v in vals:
        low = v.lower()
        if low in seen:
            continue
        seen.add(low)
        uniq.append(v)
    return uniq


def _collect_expected_datakeys(row: pd.Series, columns: Sequence[str]) -> List[str]:
    vals: List[str] = []
    for alias in ["기대 datakey", "기대 데이터키", "expected_datakey", "expected_datakeys"]:
        col = _pick_col(columns, [alias])
        if col:
            vals.extend(_parse_tokens(_to_str(row.get(col))))

    uniq: List[str] = []
    seen = set()
    for v in vals:
        low = v.lower()
        if low in seen:
            continue
        seen.add(low)
        uniq.append(v)
    return uniq


def _collect_detected_datakeys(row: pd.Series, columns: Sequence[str]) -> List[str]:
    vals: List[str] = []

    for alias in ["사용 datakey", "감지된 datakey", "detected_datakey", "detected_datakeys"]:
        col = _pick_col(columns, [alias])
        if col:
            vals.extend(_parse_tokens(_to_str(row.get(col))))

    for prefix in _ORDINALS:
        col = f"{prefix} buttonUrl"
        if col in row.index:
            vals.extend(_extract_datakeys_from_url(_to_str(row.get(col))))

    for raw_col in [f"{o} 답변 raw" for o in _ORDINALS] + ["raw"]:
        if raw_col in row.index:
            vals.extend(_extract_datakeys_from_raw_json(_to_str(row.get(raw_col))))

    uniq: List[str] = []
    seen = set()
    for v in vals:
        low = v.lower()
        if low in seen:
            continue
        seen.add(low)
        uniq.append(v)
    return uniq


def _collect_ground_truth_text(row: pd.Series, columns: Sequence[str]) -> str:
    col = _pick_col(
        columns,
        [
            "ground_truth",
            "ground truth",
            "검증 API 결과",
            "검증api 결과",
            "정답 수치",
            "검증 수치",
            "gt",
        ],
    )
    return _to_str(row.get(col)) if col else ""


def _collect_ttft(row: pd.Series, columns: Sequence[str]) -> Optional[float]:
    col = _pick_col(columns, ["ttft", "ttft_sec", "ttft(초)", "첫 응답 시간(초)", "초기 반응 시간(초)"])
    if not col:
        return None
    return _to_float(row.get(col))


def build_aqb_precheck_report(
    df: pd.DataFrame,
    consistency_min_runs: int = 3,
) -> Tuple[Dict[str, Any], pd.DataFrame]:
    """
    점수 계산 실행 전 데이터 적합성 점검.
    반환:
    - summary: 주요 커버리지/차단 여부
    - detail_df: 항목별 PASS/WARN/FAIL 상세
    """
    src = normalize_columns(df) if df is not None else pd.DataFrame()
    columns = list(src.columns)
    total = int(len(src))

    checks: List[Dict[str, Any]] = []

    def _add(check: str, status: str, detail: str, impact: str):
        checks.append(
            {
                "check": check,
                "status": status,  # PASS / WARN / FAIL
                "detail": detail,
                "impact": impact,  # blocking / quality / info
            }
        )

    if total <= 0:
        _add("입력 데이터", "FAIL", "행이 0건입니다.", "blocking")
        detail_df = pd.DataFrame(checks)
        return {
            "total_rows": 0,
            "response_coverage_pct": 0.0,
            "consistency_ready_pct": 0.0,
            "hard_fail": True,
        }, detail_df

    query_col = _pick_col(columns, ["ID", "query_id", "질의ID"])
    if query_col:
        _add("문항 ID 컬럼", "PASS", f"`{query_col}` 컬럼 사용", "info")
    else:
        _add("문항 ID 컬럼", "WARN", "ID 컬럼이 없어 row 기반으로 자동 생성합니다.", "quality")

    text_col = _pick_col(columns, ["질의", "query", "query_text"])
    if text_col:
        _add("질의 컬럼", "PASS", f"`{text_col}` 컬럼 사용", "info")
    else:
        _add("질의 컬럼", "FAIL", "질의(query) 컬럼이 없어 점수 계산이 불가능합니다.", "blocking")

    has_response_shape = any(c in columns for c in _RESPONSE_COLS) or ("응답" in columns)
    if has_response_shape:
        _add("응답 컬럼", "PASS", "응답 텍스트 컬럼이 확인되었습니다.", "info")
    else:
        _add("응답 컬럼", "FAIL", "응답 컬럼(응답 또는 n차 답변)이 없습니다.", "blocking")

    response_ready = 0
    consistency_ready = 0
    speed_ready = 0
    condition_ready = 0
    gt_ready = 0
    ttft_ready = 0

    for _, row in src.iterrows():
        responses = _collect_response_texts(row)
        if responses:
            response_ready += 1
        if len(responses) >= consistency_min_runs:
            consistency_ready += 1
        if _collect_response_times(row):
            speed_ready += 1
        if _collect_expected_filters(row, columns) or _collect_expected_datakeys(row, columns):
            condition_ready += 1
        if _collect_ground_truth_text(row, columns):
            gt_ready += 1
        if _collect_ttft(row, columns) is not None:
            ttft_ready += 1

    def _pct(v: int) -> float:
        return round((float(v) / float(total)) * 100.0, 2) if total > 0 else 0.0

    response_pct = _pct(response_ready)
    consistency_pct = _pct(consistency_ready)
    speed_pct = _pct(speed_ready)
    condition_pct = _pct(condition_ready)
    gt_pct = _pct(gt_ready)
    ttft_pct = _pct(ttft_ready)

    if response_pct >= 95:
        _add("응답 커버리지", "PASS", f"{response_ready}/{total} ({response_pct}%)", "quality")
    elif response_pct >= 70:
        _add("응답 커버리지", "WARN", f"{response_ready}/{total} ({response_pct}%)", "quality")
    else:
        _add("응답 커버리지", "FAIL", f"{response_ready}/{total} ({response_pct}%)", "blocking")

    if consistency_pct >= 80:
        _add(
            "일관성 평가 준비도",
            "PASS",
            f"{consistency_ready}/{total} ({consistency_pct}%)가 {consistency_min_runs}회 이상 응답 보유",
            "quality",
        )
    elif consistency_pct >= 30:
        _add(
            "일관성 평가 준비도",
            "WARN",
            f"{consistency_ready}/{total} ({consistency_pct}%)가 {consistency_min_runs}회 이상 응답 보유",
            "quality",
        )
    else:
        _add(
            "일관성 평가 준비도",
            "WARN",
            f"{consistency_ready}/{total} ({consistency_pct}%)만 {consistency_min_runs}회 이상 응답 보유",
            "quality",
        )

    if speed_pct >= 80:
        _add("속도 평가 준비도", "PASS", f"{speed_ready}/{total} ({speed_pct}%)에 응답시간 존재", "quality")
    elif speed_pct > 0:
        _add("속도 평가 준비도", "WARN", f"{speed_ready}/{total} ({speed_pct}%)에 응답시간 존재", "quality")
    else:
        _add("속도 평가 준비도", "WARN", "응답시간 컬럼이 없어 속도 점수 신뢰도가 낮습니다.", "quality")

    if condition_pct >= 80:
        _add("조건(필터/datakey) 준비도", "PASS", f"{condition_ready}/{total} ({condition_pct}%)", "quality")
    elif condition_pct > 0:
        _add(
            "조건(필터/datakey) 준비도",
            "WARN",
            f"{condition_ready}/{total} ({condition_pct}%)만 기대조건 존재",
            "quality",
        )
    else:
        _add(
            "조건(필터/datakey) 준비도",
            "WARN",
            "기대 조건 컬럼이 없어 의도/정확성 점수의 정확도가 낮아질 수 있습니다.",
            "quality",
        )

    if gt_pct >= 80:
        _add("Ground Truth 준비도", "PASS", f"{gt_ready}/{total} ({gt_pct}%)", "quality")
    elif gt_pct > 0:
        _add("Ground Truth 준비도", "WARN", f"{gt_ready}/{total} ({gt_pct}%)만 GT 존재", "quality")
    else:
        _add("Ground Truth 준비도", "WARN", "Ground Truth 컬럼이 없어 정확성은 보수 평가됩니다.", "quality")

    if ttft_pct > 0:
        _add("TTFT 측정", "PASS", f"{ttft_ready}/{total} ({ttft_pct}%)", "info")
    else:
        _add("TTFT 측정", "WARN", "TTFT 컬럼이 없어 ttft_pass는 N/A가 많을 수 있습니다.", "info")

    detail_df = pd.DataFrame(checks)
    hard_fail = bool(((detail_df["status"] == "FAIL") & (detail_df["impact"] == "blocking")).any())
    summary = {
        "total_rows": total,
        "response_coverage_pct": response_pct,
        "consistency_ready_pct": consistency_pct,
        "hard_fail": hard_fail,
        "warn_count": int((detail_df["status"] == "WARN").sum()),
        "fail_count": int((detail_df["status"] == "FAIL").sum()),
    }
    return summary, detail_df


def _infer_agent_type(
    row: pd.Series,
    columns: Sequence[str],
    expected_filters: Sequence[str],
    expected_datakeys: Sequence[str],
) -> str:
    explicit_col = _pick_col(columns, ["agent_type", "agent type", "에이전트 유형", "에이전트 타입"])
    if explicit_col:
        raw = _to_str(row.get(explicit_col)).lower()
        if raw:
            if "applicant" in raw or "지원자" in raw:
                return "applicant_management"
            if "move" in raw or "이동" in raw or "url" in raw:
                return "navigation"
            if "execute" in raw or "실행" in raw:
                return "execution"
            return raw

    if expected_datakeys:
        return "execution_or_navigation"
    if expected_filters:
        return "applicant_management"

    has_btn = any(_to_str(row.get(f"{o} buttonUrl")) for o in _ORDINALS)
    if has_btn:
        return "execution_or_navigation"
    return "applicant_management"


def _is_period_like_filter(token: str) -> bool:
    s = token.lower()
    keywords = ["기간", "최근", "개월", "month", "year", "date", "from", "to", "일", "주"]
    return any(k in s for k in keywords)


def _infer_additional_tool_calls(
    row: pd.Series,
    columns: Sequence[str],
    expected_filters: Sequence[str],
    expected_datakeys: Sequence[str],
) -> int:
    direct_col = _pick_col(columns, ["추가 도구 호출 수", "additional_tool_calls"])
    if direct_col:
        v = _to_float(row.get(direct_col))
        if v is not None:
            return max(0, int(round(v)))

    total_col = _pick_col(columns, ["도구 호출 수", "tool_calls", "tools_called"])
    if total_col:
        v = _to_float(row.get(total_col))
        if v is not None:
            return max(0, int(round(v)) - 1)

    if expected_datakeys:
        return max(0, len(_norm_set(expected_datakeys)) - 1)

    non_period = [f for f in expected_filters if not _is_period_like_filter(f)]
    if non_period:
        return max(0, len(_norm_set(non_period)) - 1)
    return 0


def _inferred_expected_calls(row: pd.Series, columns: Sequence[str], responses: Sequence[str]) -> int:
    col = _pick_col(columns, ["호출 횟수", "n_calls", "call_count"])
    if col:
        v = _to_float(row.get(col))
        if v is not None and v > 0:
            return int(round(v))

    # 호출 횟수 컬럼이 없으면 응답이 채워진 최대 차수를 사용
    max_idx = 0
    for i, col_name in enumerate(_RESPONSE_COLS, start=1):
        if col_name in row.index and _to_str(row.get(col_name)):
            max_idx = i
    if max_idx > 0:
        return max_idx

    return max(1, len(responses))


def _detect_error_or_blank(
    row: pd.Series,
    columns: Sequence[str],
    responses: Sequence[str],
    expected_calls: int,
) -> bool:
    issue_col = _pick_col(columns, ["특이사항", "error", "오류"])
    if issue_col and _contains_error_text(_to_str(row.get(issue_col))):
        return True

    if not responses:
        return True

    statuses = _collect_statuses(row)
    if statuses:
        for status in statuses:
            low = status.lower()
            if any(k in low for k in ("에러", "실패", "timeout", "오류", "fail")):
                return True

    for i in range(min(expected_calls, len(_RESPONSE_COLS))):
        col = _RESPONSE_COLS[i]
        if col in row.index:
            val = _to_str(row.get(col))
            if not val:
                return True
            if _contains_error_text(val):
                return True

    for txt in responses:
        if _contains_error_text(txt):
            return True

    return False


def _filter_match_grade(expected: Sequence[str], detected: Sequence[str]) -> Tuple[str, str]:
    exp = _norm_set(expected)
    det = _norm_set(detected)

    if not exp:
        return "unknown", "기대 필터 정보 없음"

    matched = exp & det
    extras = det - exp

    if matched == exp and not extras:
        return "exact", "기대 필터 정확 일치"
    if matched == exp and extras:
        return "full_with_extra", f"기대 필터 포함 + 추가 필터({', '.join(sorted(extras))})"
    if matched:
        miss = exp - matched
        return "partial", f"일부 일치(일치: {', '.join(sorted(matched))}, 누락: {', '.join(sorted(miss))})"
    return "none", "기대 필터와 불일치"


def _datakey_grade(expected: Sequence[str], detected: Sequence[str]) -> Tuple[str, str]:
    exp = _norm_set(expected)
    det = _norm_set(detected)

    if not exp:
        return "unknown", "기대 datakey 정보 없음"

    if exp.issubset(det):
        extras = det - exp
        if extras:
            return "partial", f"기대 datakey 포함 + 추가 datakey({', '.join(sorted(extras))})"
        return "pass", "기대 datakey 정확히 사용"

    miss = exp - det
    return "fail", f"기대 datakey 미포함({', '.join(sorted(miss))})"


def _compute_numeric_match(
    responses: Sequence[str],
    ground_truth_text: str,
    tolerance_pct: float,
) -> Tuple[str, str]:
    gt_nums = _extract_numbers(ground_truth_text)
    if not gt_nums:
        return "unknown", "Ground Truth 수치가 없어 수치 비교는 제한됨"

    if not responses:
        return "missing", "응답이 없어 수치 비교 불가"

    resp_nums = _extract_numbers("\n".join(responses))
    if not resp_nums:
        return "missing", "응답에서 수치 추출 실패"

    n = min(len(gt_nums), len(resp_nums))
    if n <= 0:
        return "missing", "비교 가능한 수치 쌍 없음"

    exact_all = True
    tol_all = True
    for i in range(n):
        g = gt_nums[i]
        r = resp_nums[i]
        if r != g:
            exact_all = False
        if not _relative_close(r, g, tolerance_pct=tolerance_pct):
            tol_all = False

    if exact_all:
        return "exact", "Ground Truth 수치와 일치"
    if tol_all:
        return "within_tol", f"Ground Truth 대비 허용오차(±{tolerance_pct:.1f}%) 이내"
    return "mismatch", "Ground Truth 수치 불일치"


def _score_accuracy_applicant(
    expected_filters: Sequence[str],
    detected_filters: Sequence[str],
    responses: Sequence[str],
    ground_truth_text: str,
    tolerance_pct: float,
) -> Tuple[int, str]:
    filter_grade, filter_note = _filter_match_grade(expected_filters, detected_filters)
    num_status, num_note = _compute_numeric_match(responses, ground_truth_text, tolerance_pct)

    if num_status == "unknown":
        if filter_grade == "exact":
            return 4, f"필터 정확. {num_note}"
        if filter_grade == "full_with_extra":
            return 3, f"추가 필터 존재. {num_note}"
        if filter_grade == "partial":
            return 1, f"필터 부분 일치. {num_note}"
        return 0, f"필터 불일치. {num_note}"

    if filter_grade in ("exact", "full_with_extra") and num_status == "exact":
        return 5, f"{filter_note}; {num_note}"
    if filter_grade in ("exact", "full_with_extra") and num_status == "within_tol":
        return 4, f"{filter_note}; {num_note}"
    if filter_grade in ("partial", "none") and num_status in ("exact", "within_tol"):
        return 3, f"필터 불완전하지만 수치는 정확/근접. {filter_note}; {num_note}"
    if filter_grade in ("exact", "full_with_extra") and num_status == "mismatch":
        return 2, f"필터는 맞지만 수치 불일치. {num_note}"
    if filter_grade == "partial" and num_status == "mismatch":
        return 1, f"필터 부분 일치 + 수치 불일치. {filter_note}; {num_note}"
    return 0, f"필터 불일치 + 수치 불일치. {filter_note}; {num_note}"


def _score_accuracy_execute(expected_datakeys: Sequence[str], detected_datakeys: Sequence[str]) -> Tuple[int, str]:
    grade, note = _datakey_grade(expected_datakeys, detected_datakeys)
    if grade == "pass":
        return 5, note
    if grade == "partial":
        return 3, note
    if grade == "unknown":
        return 0, note
    return 0, note


def _score_semantic_rule(
    mapping_grade: str,
    response_text: str,
    has_error_or_blank: bool,
    agent_type: str,
) -> Tuple[int, str]:
    if has_error_or_blank or _is_blank(response_text):
        return 0, "응답 실패 또는 빈 응답"

    # 이동 에이전트는 매핑 중심으로 판단
    if agent_type in ("navigation",):
        if mapping_grade == "exact":
            return 5, "조건 매핑 정확 + 응답 정상"
        if mapping_grade in ("full_with_extra", "partial"):
            return 3, "조건 부분 매핑"
        if mapping_grade == "none":
            return 1, "조건 매핑 실패"
        return 2, "조건 매핑 정보 부족"

    if mapping_grade == "exact":
        return 5, "조건 매핑 정확 + 응답 정상"
    if mapping_grade in ("full_with_extra", "partial"):
        return 3, "핵심 의도는 파악했으나 조건이 불완전"
    if mapping_grade == "none":
        return 1, "조건 매핑 실패"
    return 2, "조건 매핑 정보 부족"


def _score_speed_single(avg_sec: Optional[float], has_error: bool) -> Tuple[int, str]:
    if has_error:
        return 0, "에러/타임아웃/빈 응답"
    if avg_sec is None:
        return 0, "응답 시간 측정값 없음"

    if avg_sec <= 5:
        return 5, f"{avg_sec:.2f}초 (<=5초)"
    if avg_sec <= 8:
        return 4, f"{avg_sec:.2f}초 (5~8초)"
    if avg_sec <= 10:
        return 3, f"{avg_sec:.2f}초 (8~10초)"
    if avg_sec <= 15:
        return 2, f"{avg_sec:.2f}초 (10~15초)"
    if avg_sec <= 20:
        return 1, f"{avg_sec:.2f}초 (15~20초)"
    return 0, f"{avg_sec:.2f}초 (20초 초과)"


def _score_speed_multi(avg_sec: Optional[float], has_error: bool, agent_type: str) -> Tuple[int, str]:
    if has_error:
        return 0, "에러/타임아웃/빈 응답"
    if avg_sec is None:
        return 0, "응답 시간 측정값 없음"

    if agent_type == "applicant_management":
        # 지원자 관리 에이전트: 30초 기준선
        if avg_sec <= 20:
            return 5, f"{avg_sec:.2f}초 (<=20초)"
        if avg_sec <= 30:
            return 4, f"{avg_sec:.2f}초 (20~30초)"
        if avg_sec <= 40:
            return 3, f"{avg_sec:.2f}초 (30~40초)"
        if avg_sec <= 50:
            return 2, f"{avg_sec:.2f}초 (40~50초)"
        if avg_sec <= 60:
            return 1, f"{avg_sec:.2f}초 (50~60초)"
        return 0, f"{avg_sec:.2f}초 (60초 초과)"

    # 그 외 에이전트: 10초 기준선
    if avg_sec <= 10:
        return 5, f"{avg_sec:.2f}초 (<=10초)"
    if avg_sec <= 15:
        return 4, f"{avg_sec:.2f}초 (10~15초)"
    if avg_sec <= 20:
        return 3, f"{avg_sec:.2f}초 (15~20초)"
    if avg_sec <= 30:
        return 2, f"{avg_sec:.2f}초 (20~30초)"
    if avg_sec <= 45:
        return 1, f"{avg_sec:.2f}초 (30~45초)"
    return 0, f"{avg_sec:.2f}초 (45초 초과)"


def _score_stability(has_error_or_blank: bool) -> Tuple[int, str]:
    if has_error_or_blank:
        return 0, "에러/타임아웃/Null 응답"
    return 5, "정상 응답"


def _pair_numeric_state(a: str, b: str, tolerance_pct: float) -> str:
    nums_a = _extract_numbers(a)
    nums_b = _extract_numbers(b)

    if not nums_a and not nums_b:
        return "no_numbers"
    if not nums_a or not nums_b:
        return "mismatch"

    n = min(len(nums_a), len(nums_b))
    if n <= 0:
        return "mismatch"

    exact = True
    tol = True
    for i in range(n):
        va = nums_a[i]
        vb = nums_b[i]
        if va != vb:
            exact = False
        if not _relative_close(va, vb, tolerance_pct=tolerance_pct):
            tol = False

    if exact:
        return "exact"
    if tol:
        return "within_tol"
    return "mismatch"


def _score_consistency_three(responses: Sequence[str], tolerance_pct: float) -> Tuple[int, str]:
    if len(responses) < 3:
        return 0, "3회 응답이 없어 일관성 평가 불가"

    r = list(responses[:3])
    pairs = [(0, 1), (0, 2), (1, 2)]

    concl_true = 0
    exact_true = 0
    tol_true = 0
    mismatch_with_conclusion = 0

    for i, j in pairs:
        sim = _text_similarity(r[i], r[j])
        same_conclusion = sim >= 0.45
        if same_conclusion:
            concl_true += 1

        num_state = _pair_numeric_state(r[i], r[j], tolerance_pct)
        if same_conclusion and num_state == "exact":
            exact_true += 1
        if same_conclusion and num_state in ("exact", "within_tol", "no_numbers"):
            tol_true += 1
        if same_conclusion and num_state == "mismatch":
            mismatch_with_conclusion += 1

    # 5: 3회 모두 숫자 일치 + 결론 일치
    if concl_true == 3 and exact_true == 3:
        return 5, "3회 모두 숫자/결론 일치"

    # 4: 3회 모두 결론 일치, 숫자 허용 오차 내
    if concl_true == 3 and tol_true == 3:
        return 4, f"3회 결론 일치 + 숫자 허용오차(±{tolerance_pct:.1f}%) 이내"

    # 3: 3회 중 2회 일치(숫자+결론)
    if exact_true >= 1:
        return 3, "3회 중 2회는 숫자+결론 일치"

    # 2: 3회 중 2회 결론만 일치, 숫자 불일치
    if mismatch_with_conclusion >= 1:
        return 2, "3회 중 2회 결론은 유사하나 숫자 불일치"

    # 1: 3회 모두 결론 유사하나 숫자 매번 다름
    if concl_true == 3 and exact_true == 0 and tol_true == 0:
        return 1, "3회 결론은 유사하나 숫자가 매번 다름"

    return 0, "3회 응답이 상이"


def _score_consistency_under_min(
    responses: Sequence[str],
    tolerance_pct: float,
    policy: str,
    min_runs: int,
) -> Tuple[int, str]:
    if policy == "two_run_proxy" and len(responses) >= 2:
        a, b = responses[0], responses[1]
        sim = _text_similarity(a, b) >= 0.45
        num_state = _pair_numeric_state(a, b, tolerance_pct)

        if sim and num_state == "exact":
            return 3, f"임시 2회 평가: 숫자+결론 일치 (정식 기준 {min_runs}회 미충족)"
        if sim and num_state in ("within_tol", "no_numbers"):
            return 2, f"임시 2회 평가: 결론 일치, 숫자 근접 (정식 기준 {min_runs}회 미충족)"
        if sim:
            return 1, f"임시 2회 평가: 결론만 유사 (정식 기준 {min_runs}회 미충족)"
        return 0, f"임시 2회 평가: 응답 불일치 (정식 기준 {min_runs}회 미충족)"

    return 0, f"응답 {min_runs}회 미만으로 일관성 0점 처리"


def _semantic_prompt(
    query: str,
    expected_conditions: Sequence[str],
    detected_conditions: Sequence[str],
    response_text: str,
    agent_type: str,
) -> str:
    expected_str = ", ".join(expected_conditions) if expected_conditions else "(없음)"
    detected_str = ", ".join(detected_conditions) if detected_conditions else "(없음)"

    return f"""당신은 에이전트 QA 평가자입니다.
아래 문항의 의도 충족 점수(0~5)를 평가하세요.
의도 충족은 조건 매핑 정확도 + 응답 표현 품질(톤앤매너/가독성) 종합 평가입니다.

[점수 기준]
5: 의도 조건 정확 + 응답 표현 적절(톤앤매너 준수)
4: 조건은 맞지만 톤앤매너 미준수 또는 표현 일부 부정확
3: 핵심 의도 파악했지만 조건 일부 누락 또는 불필요 조건 추가
2: 의도 일부만 반영, 결과가 기대와 다름
1: 조건 완전 실패이나 관련 영역 응답 제공
0: 완전히 다른 의도 또는 응답 실패

[입력]
에이전트 유형: {agent_type}
질의: {query}
기대 조건: {expected_str}
감지 조건: {detected_str}
응답: {response_text}

반드시 JSON 객체만 출력하세요.
{{"score": 0-5 정수, "reason": "한국어 한 문장 근거"}}
"""


def _consistency_prompt(query: str, responses: Sequence[str], tolerance_pct: float) -> str:
    lines = []
    for i, r in enumerate(responses[:3], start=1):
        lines.append(f"응답{i}: {r}")
    body = "\n".join(lines)

    return f"""당신은 에이전트 QA 평가자입니다.
아래 질의의 3회 응답 일관성을 0~5로 평가하세요.
핵심은 숫자 일치와 결론(의미) 일치입니다. 숫자 허용오차는 ±{tolerance_pct:.1f}%입니다.

[점수 기준]
5: 3회 모두 숫자 일치 + 결론 일치
4: 3회 모두 결론 일치 + 숫자 허용오차 내
3: 3회 중 2회 숫자+결론 일치
2: 3회 중 2회 결론만 일치
1: 3회 모두 결론 유사하나 숫자는 매번 다름
0: 3회 응답이 모두 상이

[입력]
질의: {query}
{body}

반드시 JSON 객체만 출력하세요.
{{"score": 0-5 정수, "reason": "한국어 한 문장 근거"}}
"""


async def _run_llm_scoring(
    tasks: Sequence[Tuple[str, int, str]],
    api_key: str,
    model: str,
    max_parallel: int,
) -> Dict[Tuple[int, str], Tuple[Optional[int], str]]:
    if not tasks:
        return {}

    sem = asyncio.Semaphore(max(1, max_parallel))
    timeout = aiohttp.ClientTimeout(total=120)
    out: Dict[Tuple[int, str], Tuple[Optional[int], str]] = {}

    async with aiohttp.ClientSession(timeout=timeout) as session:

        async def _run_one(kind: str, idx: int, prompt: str):
            async with sem:
                result, _usage, err = await openai_judge_with_retry(
                    session=session,
                    api_key=api_key,
                    model=model,
                    prompt_text=prompt,
                )
                if result is None:
                    return kind, idx, None, f"LLM 평가 실패: {err}"
                score = _clamp_score((result or {}).get("score"))
                reason = _to_str((result or {}).get("reason")) or "LLM 근거 미제공"
                return kind, idx, score, reason

        futures = [asyncio.create_task(_run_one(kind, idx, prompt)) for kind, idx, prompt in tasks]
        for fut in asyncio.as_completed(futures):
            kind, idx, score, reason = await fut
            out[(idx, kind)] = (score, reason)

    return out


async def run_aqb_scoring_async(
    df: pd.DataFrame,
    api_key: str,
    model: str,
    max_parallel: int = 3,
    tolerance_pct: float = 1.0,
    use_semantic_llm: bool = True,
    use_consistency_llm: bool = True,
    consistency_min_runs: int = 3,
    consistency_under_min_policy: str = "two_run_proxy",  # zero | two_run_proxy
) -> pd.DataFrame:
    """
    AQB v1.2.0 문항 점수 계산.
    - 문항 단위 지표 점수 산출
    - TTFT는 PASS/FAIL 컬럼만 산출 (종합 점수 미반영)
    """
    src = normalize_columns(df)
    columns = list(src.columns)

    id_col = _pick_col(columns, ["ID", "query_id", "질의ID"]) or "ID"
    query_col = _pick_col(columns, ["질의", "query", "query_text"]) or "질의"

    row_infos: List[Dict[str, Any]] = []
    llm_tasks: List[Tuple[str, int, str]] = []

    for idx, row in src.iterrows():
        run_id = _collect_run_id(row, columns)
        query_id = _to_str(row.get(id_col)) or f"row-{idx + 1}"
        query_text = _to_str(row.get(query_col))

        responses = _collect_response_texts(row)
        response_times = _collect_response_times(row)
        avg_response_time = _mean(response_times)

        expected_filters = _collect_expected_filters(row, columns)
        detected_filters = _collect_detected_filters(row, columns)
        expected_datakeys = _collect_expected_datakeys(row, columns)
        detected_datakeys = _collect_detected_datakeys(row, columns)
        ground_truth_text = _collect_ground_truth_text(row, columns)

        agent_type = _infer_agent_type(row, columns, expected_filters, expected_datakeys)

        expected_calls = _inferred_expected_calls(row, columns, responses)
        has_error_or_blank = _detect_error_or_blank(
            row=row,
            columns=columns,
            responses=responses,
            expected_calls=expected_calls,
        )

        # Accuracy
        if agent_type in ("execution", "navigation", "execution_or_navigation"):
            accuracy_score, accuracy_reason = _score_accuracy_execute(expected_datakeys, detected_datakeys)
            mapping_grade, _mapping_note = _datakey_grade(expected_datakeys, detected_datakeys)
            expected_conditions = expected_datakeys
            detected_conditions = detected_datakeys
        else:
            accuracy_score, accuracy_reason = _score_accuracy_applicant(
                expected_filters=expected_filters,
                detected_filters=detected_filters,
                responses=responses,
                ground_truth_text=ground_truth_text,
                tolerance_pct=tolerance_pct,
            )
            mapping_grade, _mapping_note = _filter_match_grade(expected_filters, detected_filters)
            expected_conditions = expected_filters
            detected_conditions = detected_filters

        # Semantic (rule baseline)
        semantic_score, semantic_reason = _score_semantic_rule(
            mapping_grade=mapping_grade,
            response_text=responses[0] if responses else "",
            has_error_or_blank=has_error_or_blank,
            agent_type=agent_type,
        )

        # Consistency (rule)
        if len(responses) >= consistency_min_runs:
            consistency_score, consistency_reason = _score_consistency_three(
                responses=responses,
                tolerance_pct=tolerance_pct,
            )
        else:
            consistency_score, consistency_reason = _score_consistency_under_min(
                responses=responses,
                tolerance_pct=tolerance_pct,
                policy=consistency_under_min_policy,
                min_runs=consistency_min_runs,
            )

        # Speed
        additional_tool_calls = _infer_additional_tool_calls(
            row=row,
            columns=columns,
            expected_filters=expected_filters,
            expected_datakeys=expected_datakeys,
        )
        single_score, single_reason = _score_speed_single(avg_response_time, has_error_or_blank)
        multi_score, multi_reason = _score_speed_multi(avg_response_time, has_error_or_blank, agent_type)

        if additional_tool_calls > 0:
            speed_score = float(multi_score)
            speed_reason = f"복수 도구 기준: {multi_reason}"
        else:
            speed_score = float(single_score)
            speed_reason = f"단일 도구 기준: {single_reason}"

        # Stability
        stability_score, stability_reason = _score_stability(has_error_or_blank)

        # TTFT (pass/fail only)
        ttft = _collect_ttft(row, columns)
        if ttft is None:
            ttft_pass = "N/A"
        else:
            ttft_pass = "PASS" if ttft <= 1.0 else "FAIL"

        row_info: Dict[str, Any] = {
            "row_idx": int(idx),
            "run_id": run_id,
            "query_id": query_id,
            "query_text": query_text,
            "agent_type": agent_type,
            "semantic_score": int(semantic_score),
            "semantic_reason": semantic_reason,
            "semantic_calc_method": "rule_based",
            "consistency_score": int(consistency_score),
            "consistency_reason": consistency_reason,
            "consistency_calc_method": "rule_based",
            "accuracy_score": int(accuracy_score),
            "accuracy_reason": accuracy_reason,
            "accuracy_calc_method": "rule_based",
            "speed_score": float(speed_score),
            "speed_reason": speed_reason,
            "speed_calc_method": "rule_based",
            "stability_score": int(stability_score),
            "stability_reason": stability_reason,
            "stability_calc_method": "rule_based",
            "speed_single_score": int(single_score),
            "speed_multi_score": int(multi_score),
            "response_time_avg_sec": round(float(avg_response_time), 3) if avg_response_time is not None else "",
            "additional_tool_calls": int(additional_tool_calls),
            "ttft_pass": ttft_pass,
            "response_error_or_blank": bool(has_error_or_blank),
            "semantic_mapping_grade": mapping_grade,
            "expected_conditions": expected_conditions,
            "detected_conditions": detected_conditions,
            "responses": responses,
        }

        if use_semantic_llm and api_key and responses and not has_error_or_blank:
            llm_tasks.append(
                (
                    "semantic",
                    int(idx),
                    _semantic_prompt(
                        query=query_text,
                        expected_conditions=expected_conditions,
                        detected_conditions=detected_conditions,
                        response_text=responses[0],
                        agent_type=agent_type,
                    ),
                )
            )

        if use_consistency_llm and api_key and len(responses) >= consistency_min_runs:
            llm_tasks.append(
                (
                    "consistency",
                    int(idx),
                    _consistency_prompt(query=query_text, responses=responses, tolerance_pct=tolerance_pct),
                )
            )

        row_infos.append(row_info)

    llm_results: Dict[Tuple[int, str], Tuple[Optional[int], str]] = {}
    if llm_tasks and api_key:
        llm_results = await _run_llm_scoring(
            tasks=llm_tasks,
            api_key=api_key,
            model=model,
            max_parallel=max_parallel,
        )

    records: List[Dict[str, Any]] = []
    for info in row_infos:
        idx = int(info["row_idx"])

        # semantic LLM 결과 반영 (매핑 실패 시 상한 적용)
        sem_key = (idx, "semantic")
        if sem_key in llm_results and llm_results[sem_key][0] is not None:
            llm_score = int(llm_results[sem_key][0])
            llm_reason = llm_results[sem_key][1]

            mapping_grade = info.get("semantic_mapping_grade")
            if mapping_grade == "none":
                llm_score = min(llm_score, 1)
            elif mapping_grade in ("partial", "full_with_extra"):
                llm_score = min(llm_score, 3)

            info["semantic_score"] = llm_score
            info["semantic_reason"] = f"LLM 평가: {llm_reason}"
            info["semantic_calc_method"] = "llm_with_rule_guard"
        elif sem_key in llm_results:
            info["semantic_reason"] = f"규칙 기반 fallback: {info['semantic_reason']} / {llm_results[sem_key][1]}"
            info["semantic_calc_method"] = "rule_fallback_from_llm"

        # consistency LLM 결과 반영
        con_key = (idx, "consistency")
        if con_key in llm_results and llm_results[con_key][0] is not None:
            info["consistency_score"] = int(llm_results[con_key][0])
            info["consistency_reason"] = f"LLM 평가: {llm_results[con_key][1]}"
            info["consistency_calc_method"] = "llm_based"
        elif con_key in llm_results:
            info["consistency_reason"] = f"규칙 기반 fallback: {info['consistency_reason']} / {llm_results[con_key][1]}"
            info["consistency_calc_method"] = "rule_fallback_from_llm"

        semantic = float(info["semantic_score"])
        consistency = float(info["consistency_score"])
        accuracy = float(info["accuracy_score"])
        speed = float(info["speed_score"])
        stability = float(info["stability_score"])

        # TTFT는 가중치 반영하지 않음
        weighted_total = round(
            (semantic * 0.2)
            + (consistency * 0.1)
            + (accuracy * 0.3)
            + (speed * 0.2)
            + (stability * 0.2),
            2,
        )

        flag_manual = (
            semantic <= 2
            or accuracy <= 2
            or stability <= 2
            or weighted_total <= 2.5
            or bool(info["response_error_or_blank"])
        )

        record = {
            "run_id": info["run_id"],
            "query_id": info["query_id"],
            "query_text": info["query_text"],
            "agent_type": info["agent_type"],
            "semantic_score": _clamp_score(info["semantic_score"]),
            "consistency_score": _clamp_score(info["consistency_score"]),
            "accuracy_score": _clamp_score(info["accuracy_score"]),
            "speed_score": round(float(info["speed_score"]), 2),
            "stability_score": _clamp_score(info["stability_score"]),
            "weighted_total": weighted_total,
            "flag_manual_review": bool(flag_manual),
            "ttft_pass": info["ttft_pass"],
            "semantic_reason": _to_str(info["semantic_reason"]),
            "consistency_reason": _to_str(info["consistency_reason"]),
            "accuracy_reason": _to_str(info["accuracy_reason"]),
            "speed_reason": _to_str(info["speed_reason"]),
            "stability_reason": _to_str(info["stability_reason"]),
            "semantic_calc_method": _to_str(info["semantic_calc_method"]),
            "consistency_calc_method": _to_str(info["consistency_calc_method"]),
            "accuracy_calc_method": _to_str(info["accuracy_calc_method"]),
            "speed_calc_method": _to_str(info["speed_calc_method"]),
            "stability_calc_method": _to_str(info["stability_calc_method"]),
            "speed_single_score": _clamp_score(info["speed_single_score"]),
            "speed_multi_score": _clamp_score(info["speed_multi_score"]),
            "response_time_avg_sec": info["response_time_avg_sec"],
            "additional_tool_calls": int(info["additional_tool_calls"]),
            "response_error_or_blank": bool(info["response_error_or_blank"]),
        }
        records.append(record)

    out_df = pd.DataFrame(records)
    for col in AQB_SCORE_COLUMNS:
        if col not in out_df.columns:
            out_df[col] = ""
    return out_df[AQB_SCORE_COLUMNS]


def build_aqb_round_summary(score_df: pd.DataFrame) -> pd.DataFrame:
    """
    문항별 점수 -> 회차별/에이전트별 평균.
    (요구사항 1.3의 2단계)
    """
    if score_df is None or score_df.empty:
        return pd.DataFrame(
            columns=[
                "run_id",
                "agent_type",
                "query_count",
                "semantic_avg",
                "consistency_avg",
                "accuracy_avg",
                "speed_avg",
                "stability_avg",
                "weighted_total_avg",
                "manual_review_rate",
            ]
        )

    df = score_df.copy()
    for c in [
        "semantic_score",
        "consistency_score",
        "accuracy_score",
        "speed_score",
        "stability_score",
        "weighted_total",
    ]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    if "flag_manual_review" in df.columns:
        df["flag_manual_review"] = df["flag_manual_review"].astype(bool)
    else:
        df["flag_manual_review"] = False

    out = (
        df.groupby(["run_id", "agent_type"], dropna=False)
        .agg(
            query_count=("query_id", "count"),
            semantic_avg=("semantic_score", "mean"),
            consistency_avg=("consistency_score", "mean"),
            accuracy_avg=("accuracy_score", "mean"),
            speed_avg=("speed_score", "mean"),
            stability_avg=("stability_score", "mean"),
            weighted_total_avg=("weighted_total", "mean"),
            manual_review_rate=("flag_manual_review", "mean"),
        )
        .reset_index()
    )

    for c in [
        "semantic_avg",
        "consistency_avg",
        "accuracy_avg",
        "speed_avg",
        "stability_avg",
        "weighted_total_avg",
        "manual_review_rate",
    ]:
        out[c] = out[c].round(4)

    return out.sort_values(["run_id", "agent_type"]).reset_index(drop=True)


def build_aqb_agent_summary(score_df: pd.DataFrame) -> pd.DataFrame:
    """
    회차별 평균 -> 에이전트 최종 평균.
    (요구사항 1.3의 3단계)
    """
    round_df = build_aqb_round_summary(score_df)
    if round_df.empty:
        return pd.DataFrame(
            columns=[
                "agent_type",
                "round_count",
                "total_query_count",
                "semantic_avg",
                "consistency_avg",
                "accuracy_avg",
                "speed_avg",
                "stability_avg",
                "weighted_total_avg",
                "manual_review_rate",
            ]
        )

    out = (
        round_df.groupby(["agent_type"], dropna=False)
        .agg(
            round_count=("run_id", "nunique"),
            total_query_count=("query_count", "sum"),
            semantic_avg=("semantic_avg", "mean"),
            consistency_avg=("consistency_avg", "mean"),
            accuracy_avg=("accuracy_avg", "mean"),
            speed_avg=("speed_avg", "mean"),
            stability_avg=("stability_avg", "mean"),
            weighted_total_avg=("weighted_total_avg", "mean"),
            manual_review_rate=("manual_review_rate", "mean"),
        )
        .reset_index()
    )

    for c in [
        "semantic_avg",
        "consistency_avg",
        "accuracy_avg",
        "speed_avg",
        "stability_avg",
        "weighted_total_avg",
        "manual_review_rate",
    ]:
        out[c] = out[c].round(4)

    return out.sort_values(["agent_type"]).reset_index(drop=True)
