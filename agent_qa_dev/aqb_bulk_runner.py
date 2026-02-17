from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import aiohttp
import pandas as pd

from aqb_agent_client import AgentResponse, ApplicantAgentClient, parse_button_url
from aqb_openai_judge import (
    estimate_cost_usd,
    openai_judge_with_retry,
    postprocess_eval_json,
    derive_csv_fields_from_eval,
)
from aqb_prompt_template import safe_fill_template
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def get_col(df: pd.DataFrame, name: str) -> Optional[str]:
    for c in df.columns:
        if c.strip() == name:
            return c
    return None


def is_blank(x: Any) -> bool:
    if x is None:
        return True
    s = str(x)
    return not s.strip() or s.strip().lower() == "nan"


def truncate_text(s: str, max_chars: int) -> str:
    if not s:
        return ""
    s = str(s)
    if len(s) <= max_chars:
        return s
    return s[:max_chars] + f"\n...(truncated, {len(s)} chars total)"


def build_surrogate_response_payload(row: pd.Series, prefix: str) -> Optional[Dict[str, Any]]:
    """
    기존 CSV에 raw(assistant payload)가 없을 때를 대비한 fallback.
    - {prefix} 답변 / {prefix} buttonUrl 로 최소한의 Response 구조를 복원한다.
    - 프롬프트 평가 기준은 'Response에서 추론 가능한 정보'이므로,
      최소한 assistantMessage + buttonUrl만 있어도 LLM이 일정 수준 판정 가능.
    """
    msg = str(row.get(f"{prefix} 답변", "") or "").strip()
    btn = str(row.get(f"{prefix} buttonUrl", "") or "").strip()

    if not msg and not btn:
        return None

    data_ui_list = []
    if btn:
        data_ui_list = [
            {
                "uiDescription": "지원자 관리(추정)",
                "uiValue": {
                    "formType": "LINK",
                    "buttonUrl": btn,
                },
            }
        ]

    return {
        "assistantMessage": msg,
        "dataUIList": data_ui_list,
        "guideList": [],
    }


async def run_applicant_calls_async(
    df: pd.DataFrame,
    client: ApplicantAgentClient,
    progress_cb: Optional[Callable[[int, int, str, float, int], None]] = None,
    only_missing: bool = True,
    limit_rows: Optional[int] = None,
    n_calls: int = 2,
    context: Optional[Dict[str, Any]] = None,
    target_assistant: Optional[str] = None,
    independent_sessions: bool = False,
    auto_save_callback: Optional[Callable[[pd.DataFrame], None]] = None,
) -> pd.DataFrame:
    """
    CSV df를 받아, 지원자 에이전트를 N차로 호출해 df에 컬럼을 채움.
    (이 단계에서는 '평가'를 하지 않음)

    - n_calls: 호출 횟수 (1~4, 기본값 2)
    - context: API 호출 시 전달할 context 객체
    - target_assistant: 특정 어시스턴트 지정 (예: RECRUIT_PLAN_ASSISTANT)
    - independent_sessions: True면 호출마다 새 채팅방으로 실행(일관성 실험용)
    - auto_save_callback: 10개 완료 시마다 호출되는 자동 저장 콜백
    """
    df = df.copy()

    id_col = get_col(df, "ID") or "ID"
    query_col = get_col(df, "질의") or "질의"

    # 동적으로 출력 컬럼 확보 (n_calls에 따라)
    ordinals = ["1차", "2차", "3차", "4차"]
    for i in range(n_calls):
        prefix = ordinals[i]
        for suffix in ["답변", "답변 시간(초)", "답변 raw", "buttonUrl", "감지된 필터"]:
            col_name = f"{prefix} {suffix}"
            if col_name not in df.columns:
                df[col_name] = ""

    # 대상 row 인덱스 구성
    target_idxs: List[int] = []
    for i, r in df.iterrows():
        if limit_rows is not None and len(target_idxs) >= limit_rows:
            break
        if only_missing:
            # 첫 번째 호출 컬럼만 체크
            if not is_blank(r.get("1차 답변")):
                continue
        target_idxs.append(i)

    total = len(target_idxs)
    if total == 0:
        return df

    connector = aiohttp.TCPConnector(limit=50, ssl=False)
    timeout = aiohttp.ClientTimeout(total=120)

    done = 0
    start_time = time.time()
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = []

        async def _run_one(idx: int):
            async with client.semaphore:
                query = str(df.loc[idx, query_col])
                responses, err = await client.run_n_times(
                    session, query, n_calls=n_calls,
                    context=context,
                    target_assistant=target_assistant,
                    independent_sessions=independent_sessions,
                )

                out = {
                    "idx": idx,
                    "err": err,
                    "responses": responses,
                }
                return out

        for idx in target_idxs:
            tasks.append(asyncio.create_task(_run_one(idx)))

        for fut in asyncio.as_completed(tasks):
            res = await fut
            idx = res["idx"]
            err = res["err"]
            responses: List[Optional[AgentResponse]] = res["responses"]

            # 각 호출 결과를 동적 컬럼에 저장
            for i, resp in enumerate(responses):
                if resp is None:
                    continue
                prefix = ordinals[i]
                df.at[idx, f"{prefix} 답변"] = resp.assistant_message
                df.at[idx, f"{prefix} 답변 시간(초)"] = round(resp.response_time_sec, 2) if resp.response_time_sec is not None else ""
                df.at[idx, f"{prefix} 답변 raw"] = json.dumps(resp.assistant_payload, ensure_ascii=False)
                df.at[idx, f"{prefix} buttonUrl"] = resp.button_url
                parsed = parse_button_url(resp.button_url)
                df.at[idx, f"{prefix} 감지된 필터"] = ",".join(parsed["filter_types"])

            if err:
                if "특이사항" not in df.columns:
                    df["특이사항"] = ""
                df.at[idx, "특이사항"] = str(err)

            done += 1
            elapsed = time.time() - start_time
            if progress_cb:
                progress_cb(done, total, f"[{df.loc[idx, id_col]}] calls done (err={bool(err)})", elapsed, done)

            # 자동 저장: 10개 완료 시마다
            if auto_save_callback and done % 10 == 0:
                auto_save_callback(df)

    return df


async def run_openai_judge_async(
    df: pd.DataFrame,
    prompt_template: str,
    api_key: str,
    model: str,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
    only_missing: bool = True,
    limit_rows: Optional[int] = None,
    max_chars_per_response: int = 15000,
    max_parallel: int = 3,
    price_input_per_1m: float = 0.0,
    price_output_per_1m: float = 0.0,
    price_cached_input_per_1m: float = 0.0,
) -> Tuple[pd.DataFrame, int]:
    """
    df에 있는 1차/2차 raw를 바탕으로 OpenAI 평가를 수행하고, 결과 컬럼을 채움.
    """
    df = df.copy()
    df = normalize_columns(df)

    id_col = get_col(df, "ID") or "ID"
    query_col = get_col(df, "질의") or "질의"
    expected_col = get_col(df, "기대 필터/열") or "기대 필터/열"

    # 평가 결과 컬럼 확보
    out_cols = [
        "안정성 점수",
        "1차 응답 상태",
        "2차 응답 상태",
        "안정성 비고",
        "정확도 점수",
        "기대 필터",
        "감지된 필터",
        "정확도 비고",
        "일관성 점수",
        "일치 항목",
        "불일치 항목",
        "일관성 비고",
        "총점",
        "종합 코멘트",
        "LLM 모델",
        "입력 토큰 수",
        "출력 토큰 수",
        "캐시 토큰 수",
        "추론 토큰 수",
        "전체 토큰 수",
        "LLM 비용(USD)",
        "LLM 평가 원본(JSON)"
    ]
    for c in out_cols:
        if c not in df.columns:
            df[c] = ""

    # 템플릿 컬럼들(있으면 채움)
    for c in ["열/필터 일치 여부", "답변 일관성", "차이 유형", "특이사항"]:
        if c not in df.columns:
            df[c] = ""

    # 대상 row 인덱스 구성
    target_idxs: List[int] = []
    for i, r in df.iterrows():
        if limit_rows is not None and len(target_idxs) >= limit_rows:
            break

        # 평가 입력 준비: raw가 없으면 assistantMessage/buttonUrl에서 surrogate 구성
        if is_blank(r.get("1차 답변 raw")):
            surrogate1 = build_surrogate_response_payload(r, "1차")
            if surrogate1 is not None:
                df.at[i, "1차 답변 raw"] = json.dumps(surrogate1, ensure_ascii=False)

        if is_blank(r.get("2차 답변 raw")):
            surrogate2 = build_surrogate_response_payload(r, "2차")
            if surrogate2 is not None:
                df.at[i, "2차 답변 raw"] = json.dumps(surrogate2, ensure_ascii=False)

        if is_blank(r.get("1차 답변 raw")) or is_blank(r.get("2차 답변 raw")):
            continue  # 호출 결과가 없으면 평가 불가

        if only_missing and (not is_blank(r.get("LLM 평가 원본(JSON)"))):
            continue

        # 기존 에러가 있으면 스킵(원하면 UI에서 override 가능하게 만들 수 있음)
        if isinstance(r.get("특이사항"), str) and "send_query" in r.get("특이사항"):
            continue

        target_idxs.append(i)

    total = len(target_idxs)
    if total == 0:
        return df, 0

    sem = asyncio.Semaphore(max_parallel)

    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:

        async def _judge_one(idx: int) -> Dict[str, Any]:
            async with sem:
                qid = str(df.loc[idx, id_col])
                query = str(df.loc[idx, query_col])
                expected = str(df.loc[idx, expected_col])

                r1_raw = truncate_text(str(df.loc[idx, "1차 답변 raw"]), max_chars_per_response)
                r2_raw = truncate_text(str(df.loc[idx, "2차 답변 raw"]), max_chars_per_response)

                prompt_text = safe_fill_template(
                    prompt_template,
                    {
                        "query_id": qid,
                        "query": query,
                        "expected_filters": expected,
                        "response_1": r1_raw,
                        "response_2": r2_raw,
                    },
                )

                eval_obj, usage, err = await openai_judge_with_retry(session, api_key, model, prompt_text)
                return {"idx": idx, "qid": qid, "eval": eval_obj, "usage": usage, "err": err}

        tasks = [asyncio.create_task(_judge_one(idx)) for idx in target_idxs]

        done = 0
        for fut in asyncio.as_completed(tasks):
            res = await fut
            idx = res["idx"]
            qid = res["qid"]
            err = res["err"]
            eval_obj = res["eval"]
            usage = res.get("usage") or {}

            if eval_obj is None:
                df.at[idx, "특이사항"] = f"LLM 평가 실패: {err}"
            else:
                r1_raw = str(df.loc[idx, "1차 답변 raw"]) if "1차 답변 raw" in df.columns else ""
                r2_raw = str(df.loc[idx, "2차 답변 raw"]) if "2차 답변 raw" in df.columns else ""
                eval_obj = postprocess_eval_json(eval_obj, response_1_raw=r1_raw, response_2_raw=r2_raw)

                # LLM 토큰/비용 기록
                df.at[idx, "LLM 모델"] = model
                if usage:
                    df.at[idx, "입력 토큰 수"] = usage.get("input_tokens", 0)
                    df.at[idx, "출력 토큰 수"] = usage.get("output_tokens", 0)
                    df.at[idx, "캐시 토큰 수"] = usage.get("cached_tokens", 0)
                    df.at[idx, "추론 토큰 수"] = usage.get("reasoning_tokens", 0)
                    df.at[idx, "전체 토큰 수"] = usage.get("total_tokens", 0)
                    df.at[idx, "LLM 비용(USD)"] = estimate_cost_usd(
                        usage,
                        price_input_per_1m=price_input_per_1m,
                        price_output_per_1m=price_output_per_1m,
                        price_cached_input_per_1m=price_cached_input_per_1m,
                    )
                df.at[idx, "LLM 평가 원본(JSON)"] = json.dumps(eval_obj, ensure_ascii=False)

                # 안정성(Stability)
                df.at[idx, "안정성 점수"] = eval_obj["stability"]["score"]
                df.at[idx, "1차 응답 상태"] = eval_obj["stability"]["response_1_status"]
                df.at[idx, "2차 응답 상태"] = eval_obj["stability"]["response_2_status"]
                df.at[idx, "안정성 비고"] = eval_obj["stability"]["note"]

                # 정확도(Accuracy)
                df.at[idx, "정확도 점수"] = eval_obj["accuracy"]["score"]
                df.at[idx, "기대 필터"] = ",".join(eval_obj["accuracy"]["expected"])
                df.at[idx, "감지된 필터"] = ",".join(eval_obj["accuracy"]["detected"])
                df.at[idx, "정확도 비고"] = eval_obj["accuracy"]["note"]

                # 일관성(Consistency)
                df.at[idx, "일관성 점수"] = eval_obj["consistency"]["score"]
                df.at[idx, "일치 항목"] = ",".join(eval_obj["consistency"]["matched"])
                df.at[idx, "불일치 항목"] = ",".join(eval_obj["consistency"]["diff"])
                df.at[idx, "일관성 비고"] = eval_obj["consistency"]["note"]

                df.at[idx, "총점"] = eval_obj["total_score"]
                df.at[idx, "종합 코멘트"] = eval_obj["remarks"]

                # CSV 템플릿 컬럼 채움
                derived = derive_csv_fields_from_eval(eval_obj)
                for k, v in derived.items():
                    if k in df.columns:
                        df.at[idx, k] = v

            done += 1
            if progress_cb:
                progress_cb(done, total, f"[{qid}] judge done (err={bool(err)})")

    return df, done

