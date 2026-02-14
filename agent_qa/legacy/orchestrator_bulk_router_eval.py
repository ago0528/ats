"""
bulk_router_eval.py

CSV 질의 파일을 읽어서 Gemini 2.5 Flash(gemini-2.5-flash)에 병렬(1~5)로 질의하고,
라우팅 정확도/속도/토큰 사용량을 기록한 뒤 Excel(.xlsx)로 저장하는 유틸리티.

- google-genai SDK 기반 (Gemini Developer API 또는 Vertex AI 지원)
- Structured Output(JSON Schema) 강제: response_mime_type='application/json', response_schema=Pydantic 모델

사용 예시 (CLI):
  export GEMINI_API_KEY="..."
  python bulk_router_eval.py --input_csv queries.csv --output_xlsx results.xlsx --concurrency 5 --thinking_budget 0

Streamlit 모듈 import용으로도 사용 가능:
  from bulk_router_eval import run_bulk_eval, build_excel_bytes
"""

from __future__ import annotations

import argparse
import asyncio
import json
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Literal, Optional, Tuple

import pandas as pd
from pydantic import BaseModel, Field

from google import genai
from google.genai import errors, types

from pathlib import Path
try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv가 없어도 실행 가능하게 처리
    load_dotenv = None

# bulk_router_eval.py 파일이 있는 폴더의 .env를 로드
ENV_PATH = Path(__file__).resolve().parent / ".env"
if load_dotenv is not None:
    load_dotenv(dotenv_path=ENV_PATH, override=False)  # override=False면 이미 설정된 OS env를 우선


# -----------------------------
# 1) Structured Output Schema
# -----------------------------

WorkerName = Literal[
    "RECRUIT_PLAN_CREATE_WORKER_V3",
    "RECRUIT_WIKI_WORKER_V3",
    "RESUME_WORKER_V3",
    "URL_WORKER_V3",
]


class SubWorkerTask(BaseModel):
    worker: WorkerName = Field(..., description="선정된 Sub Worker 이름")


class RouterResponse(BaseModel):
    subWorkerTask: SubWorkerTask


def _pydantic_validate(model_cls: type[BaseModel], data: Any) -> BaseModel:
    """Pydantic v1/v2 호환 검증."""
    if hasattr(model_cls, "model_validate"):
        return model_cls.model_validate(data)  # type: ignore[attr-defined]
    return model_cls.parse_obj(data)  # type: ignore[attr-defined]


# -----------------------------
# 2) Default System Prompt
#    (필요 시 --prompt_file로 교체 권장)
# -----------------------------

DEFAULT_SYSTEM_PROMPT = """
!! Output Type is only 'JSON', Do Not Markdown 'Fenced Code Block' like (```json)
## Role
'채용 에이전트'라는 제품의 사용을 돕기 위한 AI 에이전트이다.

## Instructions
유저의 질문과 대화이력을 참고하여 가장 적합한 답변을 제공할 수 있는 Sub Worker를 선별해라.
- 적절한 Sub Worker을 선별할 수 없다면, 제품 기능을 추천하기 위해 URL 이동을 추천해라.

@@ Variable
- conversationId:b0365495-bdb8-4cb0-86e6-f20fb0ab28d0
@@ Sub Worker(하위 AI 에이전트) Role
* RECRUIT_PLAN_CREATE_WORKER_V3(채용 플랜 생성 AI 에이전트)
- 채용(채용명·공고명·일정·프로세스)을 설계/생성
- 새로운 채용을 생성할 수 있는 URL 제공

* RECRUIT_WIKI_WORKER_V3(채용 위키 AI 에이전트)
- 채용 관련 질문, 솔루션 내 개념 설명, 사용 방법, 가이드 요청 또는 "채용위키/위키" 키워드 포함

* RESUME_WORKER_V3(지원자 관리 AI 에이전트)
- 지원자 수(검색 조건 적용)
- 지원자 비교/통계
- 검색 조건이 적용된 지원자 관리 화면으로 이동할 수 있는 URL 제공

* URL_WORKER_V3(URL AI 에이전트)
- URL 제공 : 화면 이동, 메뉴 접근, 채용/공고/전형 생성·수정·설정 요청
    - 제외 URL : 지원자 관리 URL, 채용 생성 URL


"""


# -----------------------------
# 3) IO / Column handling
# -----------------------------

# CSV 헤더가 한국어/영어 혼재해도 동작하도록 alias 지원
COL_ALIASES: Dict[str, List[str]] = {
    "id": ["ID", "id", "질의번호", "질의번호: ID", "query_id", "qid"],
    "expected_agent": ["기대 에이전트", "expected_agent", "expected", "expectedWorker", "expected_worker"],
    "query": ["질의", "query", "question", "user_query", "message"],
    # 아래는 입력에 없어도 됨(없으면 생성/덮어씀)
    "response_value": ["응답값", "response_value", "predicted_agent", "response"],
    "pass_fail": ["성공 여부", "pass_fail", "result"],
    "latency_s": ["응답속도(초)", "latency_s", "response_time_s", "time_s"],
    "input_tokens": ["인풋 토큰", "input_tokens", "prompt_tokens"],
    "output_tokens": ["아웃풋 토큰", "output_tokens", "completion_tokens"],
    # 옵션 입력
    "hint": ["hint", "힌트"],
    "recruitPlanId": ["recruitPlanId", "recruit_plan_id", "채용플랜ID"],
    "context_json": ["context", "context_json"],
}


def _first_existing_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    cols = set(df.columns)
    for c in candidates:
        if c in cols:
            return c
    return None


def standardize_columns(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """
    df의 컬럼명을 표준 키로 매핑한다.
    반환: (df, mapping) where mapping[standard_key] = original_col_name
    """
    mapping: Dict[str, str] = {}
    for std_key, aliases in COL_ALIASES.items():
        found = _first_existing_col(df, aliases)
        if found:
            mapping[std_key] = found

    # 필수 컬럼 체크
    missing_required = [k for k in ("id", "expected_agent", "query") if k not in mapping]
    if missing_required:
        required_human = {
            "id": "ID/질의번호",
            "expected_agent": "기대 에이전트",
            "query": "질의",
        }
        missing_labels = [required_human[k] for k in missing_required]
        raise ValueError(
            f"CSV에 필수 컬럼이 없습니다: {missing_labels}. "
            f"현재 컬럼: {list(df.columns)}"
        )
    return df, mapping


def read_csv_safely(path: str) -> pd.DataFrame:
    """한국어 CSV에서 흔한 인코딩(utf-8-sig/cp949)을 순차 시도."""
    last_err: Optional[Exception] = None
    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise last_err or RuntimeError("CSV 읽기 실패")


# -----------------------------
# 4) Evaluation config + helpers
# -----------------------------

# # 추론 X 실행용
# @dataclass(frozen=True)
# class EvalConfig:
#     model: str = "gemini-2.5-flash"
#     concurrency: int = 5
#     temperature: float = 0.0
#     top_p: float = 1.0
#     top_k: int = 1
#     max_output_tokens: int = 1024
#     seed: Optional[int] = 42

#     # Gemini 2.5 Flash는 thinking_budget으로 thinking을 제어 가능
#     # 0: thinking off, -1: dynamic thinking
#     thinking_budget: Optional[int] = 0

#     # Retry
#     max_retries: int = 2
#     retry_backoff_s: float = 0.8

#     # System prompt
#     system_prompt: str = DEFAULT_SYSTEM_PROMPT

# Default
@dataclass(frozen=True)
class EvalConfig:
    model: str = "gemini-2.5-flash"
    concurrency: int = 5
    temperature: float = 0.0
    top_p: float = 0.95
    top_k: int = 64
    max_output_tokens: int = None
    seed: Optional[int] = None

    # Gemini 2.5 Flash는 thinking_budget으로 thinking을 제어 가능
    # 0: thinking off, -1: dynamic thinking
    thinking_budget: Optional[int] = 0

    # Retry
    max_retries: int = 2
    retry_backoff_s: float = 0.8

    # System prompt
    system_prompt: str = DEFAULT_SYSTEM_PROMPT


def _build_input_payload(row: pd.Series, mapping: Dict[str, str]) -> Dict[str, Any]:
    """
    CSV row -> input_data(JSON) 생성.
    기본 형태:
      {"message": <질의>, "hint": <hint or None>, "context": {"recruitPlanId": <id or None>, ...}}
    """
    query = str(row[mapping["query"]]).strip()

    hint = None
    if "hint" in mapping and pd.notna(row[mapping["hint"]]):
        hint = row[mapping["hint"]]

    # context 기본
    context: Dict[str, Any] = {"recruitPlanId": None}

    if "recruitPlanId" in mapping and pd.notna(row[mapping["recruitPlanId"]]):
        context["recruitPlanId"] = row[mapping["recruitPlanId"]]

    # context_json 컬럼이 있다면 JSON으로 merge
    if "context_json" in mapping and pd.notna(row[mapping["context_json"]]):
        try:
            extra_ctx = row[mapping["context_json"]]
            if isinstance(extra_ctx, str):
                extra_ctx_obj = json.loads(extra_ctx)
            elif isinstance(extra_ctx, dict):
                extra_ctx_obj = extra_ctx
            else:
                extra_ctx_obj = None
            if isinstance(extra_ctx_obj, dict):
                context.update(extra_ctx_obj)
        except Exception:
            # context 파싱 실패는 무시(테스트 계속 진행)
            pass

    return {"message": query, "hint": hint, "context": context}


def _make_generate_config(cfg: EvalConfig) -> types.GenerateContentConfig:
    thinking_cfg = None
    if cfg.thinking_budget is not None:
        thinking_cfg = types.ThinkingConfig(thinking_budget=cfg.thinking_budget)

    return types.GenerateContentConfig(
        system_instruction=cfg.system_prompt,
        temperature=cfg.temperature,
        top_p=cfg.top_p,
        top_k=cfg.top_k,
        max_output_tokens=cfg.max_output_tokens,
        seed=cfg.seed,
        thinking_config=thinking_cfg,
        response_mime_type="application/json",
        response_schema=RouterResponse,
    )


def _is_retryable_api_error(e: errors.APIError) -> bool:
    # 429 Too Many Requests, 500/503 transient, 504 gateway timeout 등
    return e.code in {408, 429, 500, 502, 503, 504}


# -----------------------------
# 5) Core async execution
# -----------------------------

async def _call_once(
    aclient: genai.Client,  # actually async client object
    cfg: EvalConfig,
    gen_cfg: types.GenerateContentConfig,
    input_payload: Dict[str, Any],
) -> Tuple[Optional[RouterResponse], str, Optional[types.GenerateContentResponseUsageMetadata]]:
    """
    단일 호출. 반환:
      (parsed_router_response, raw_text, usage_metadata)
    """
    contents = json.dumps(input_payload, ensure_ascii=False, separators=(",", ":"))
    resp = await aclient.models.generate_content(
        model=cfg.model,
        contents=contents,
        config=gen_cfg,
    )

    raw_text = resp.text or ""
    parsed: Optional[RouterResponse] = None

    # SDK가 schema 기반으로 파싱해준 결과가 있으면 우선 사용
    if getattr(resp, "parsed", None) is not None:
        try:
            parsed = resp.parsed  # type: ignore[assignment]
        except Exception:
            parsed = None

    if parsed is None:
        # fallback: text -> json -> pydantic validate
        try:
            obj = json.loads(raw_text)
            parsed = _pydantic_validate(RouterResponse, obj)  # type: ignore[assignment]
        except Exception:
            parsed = None

    usage = getattr(resp, "usage_metadata", None)
    return parsed, raw_text, usage


async def _call_with_retries(
    aclient: genai.Client,
    cfg: EvalConfig,
    gen_cfg: types.GenerateContentConfig,
    input_payload: Dict[str, Any],
) -> Tuple[Optional[RouterResponse], str, Optional[types.GenerateContentResponseUsageMetadata], int, Optional[str]]:
    """
    재시도 포함 호출.
    반환: (parsed, raw_text, usage, attempts, error_message)
    """
    attempts = 0
    last_err: Optional[str] = None
    raw_text = ""
    usage = None
    parsed = None

    while attempts < (cfg.max_retries + 1):
        attempts += 1
        try:
            parsed, raw_text, usage = await _call_once(aclient, cfg, gen_cfg, input_payload)
            return parsed, raw_text, usage, attempts, None
        except errors.APIError as e:
            last_err = f"APIError {e.code}: {e.message}"
            if attempts <= cfg.max_retries and _is_retryable_api_error(e):
                await asyncio.sleep(cfg.retry_backoff_s * (2 ** (attempts - 1)))
                continue
            return None, raw_text, usage, attempts, last_err
        except Exception as e:  # noqa: BLE001
            last_err = f"UnexpectedError: {type(e).__name__}: {e}"
            # 일반 예외는 재시도 가치가 애매하므로 1회만 재시도
            if attempts <= cfg.max_retries:
                await asyncio.sleep(cfg.retry_backoff_s * (2 ** (attempts - 1)))
                continue
            return None, raw_text, usage, attempts, last_err

    return None, raw_text, usage, attempts, last_err or "UnknownError"


async def evaluate_dataframe_async(
    df: pd.DataFrame,
    cfg: EvalConfig,
    *,
    api_key: Optional[str] = None,
    use_vertexai: bool = False,
    project: Optional[str] = None,
    location: Optional[str] = None,
) -> pd.DataFrame:
    """
    DataFrame 전체를 병렬 평가.
    반환: 결과가 채워진 DataFrame(표준 컬럼 + 추가 컬럼 포함)
    """
    if not (1 <= cfg.concurrency <= 5):
        raise ValueError("concurrency는 1~5 범위여야 합니다.")

    df, mapping = standardize_columns(df)

    # Client 생성 (Gemini Developer API or Vertex AI)
    client_kwargs: Dict[str, Any] = {}
    if use_vertexai:
        if not project or not location:
            raise ValueError("Vertex AI 모드에서는 project/location이 필요합니다.")
        client_kwargs.update({"vertexai": True, "project": project, "location": location})
    else:
        # GEMINI_API_KEY or GOOGLE_API_KEY environment variable도 자동 인식
        if api_key:
            client_kwargs["api_key"] = api_key

    gen_cfg = _make_generate_config(cfg)

    results: List[Dict[str, Any]] = [None] * len(df)  # type: ignore[list-item]

    sem = asyncio.Semaphore(cfg.concurrency)

    async def _run_one(i: int, row: pd.Series) -> None:
        async with sem:
            input_payload = _build_input_payload(row, mapping)

            t0 = time.perf_counter()
            parsed, raw_text, usage, attempts, err = await _call_with_retries(
                aclient,
                cfg,
                gen_cfg,
                input_payload,
            )
            latency = time.perf_counter() - t0

            predicted_worker: Optional[str] = None

            if parsed is not None:
                predicted_worker = parsed.subWorkerTask.worker

            expected = str(row[mapping["expected_agent"]]).strip()

            pass_fail = "PASS" if predicted_worker == expected else "FAIL"

            # 토큰
            prompt_tokens = getattr(usage, "prompt_token_count", None) if usage else None
            output_tokens = None
            if usage:
                # 대부분 candidates_token_count가 output에 해당
                output_tokens = getattr(usage, "candidates_token_count", None)
                if output_tokens is None:
                    output_tokens = getattr(usage, "response_token_count", None)
            thoughts_tokens = getattr(usage, "thoughts_token_count", None) if usage else None
            total_tokens = getattr(usage, "total_token_count", None) if usage else None

            # 결과 row
            out: Dict[str, Any] = {
                "ID": row[mapping["id"]],
                "기대 에이전트": expected,
                "질의": row[mapping["query"]],
                "응답값": predicted_worker,
                "성공 여부": pass_fail,
                "응답속도(초)": round(latency, 4),
                "인풋 토큰": prompt_tokens,
                "아웃풋 토큰": output_tokens,
                "raw_json": raw_text,
                "thoughts_token": thoughts_tokens,
                "total_token": total_tokens,
                "attempts": attempts,
                "error": err,
            }
            results[i] = out

    # Async client context manager로 close 보장
    async with genai.Client(**client_kwargs).aio as aclient:
        await asyncio.gather(*[_run_one(i, df.iloc[i]) for i in range(len(df))])

    out_df = pd.DataFrame(results)
    return out_df


# -----------------------------
# 6) Sync wrappers (Streamlit-friendly)
# -----------------------------

def run_bulk_eval(
    input_csv: str,
    *,
    cfg: Optional[EvalConfig] = None,
    api_key: Optional[str] = None,
    use_vertexai: bool = False,
    project: Optional[str] = None,
    location: Optional[str] = None,
) -> pd.DataFrame:
    """
    CSV 경로를 받아 결과 DataFrame 반환 (동기 래퍼).
    Streamlit에서도 바로 호출 가능.
    """
    cfg = cfg or EvalConfig()
    df = read_csv_safely(input_csv)
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        result_box: Dict[str, Any] = {}
        error_box: Dict[str, BaseException] = {}

        def _runner() -> None:
            try:
                result_box["df"] = asyncio.run(
                    evaluate_dataframe_async(
                        df,
                        cfg,
                        api_key=api_key,
                        use_vertexai=use_vertexai,
                        project=project,
                        location=location,
                    )
                )
            except BaseException as exc:  # noqa: BLE001
                error_box["exc"] = exc

        t = threading.Thread(target=_runner, daemon=True)
        t.start()
        t.join()
        if "exc" in error_box:
            raise error_box["exc"]
        return result_box["df"]

    return asyncio.run(
        evaluate_dataframe_async(
            df,
            cfg,
            api_key=api_key,
            use_vertexai=use_vertexai,
            project=project,
            location=location,
        )
    )


def compute_summary(results_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """summary sheet + confusion matrix 생성."""
    df = results_df.copy()

    # latency가 숫자인 것만
    latency = pd.to_numeric(df["응답속도(초)"], errors="coerce")
    tokens_in = pd.to_numeric(df["인풋 토큰"], errors="coerce")
    tokens_out = pd.to_numeric(df["아웃풋 토큰"], errors="coerce")

    total = len(df)
    pass_cnt = int((df["성공 여부"] == "PASS").sum())
    fail_cnt = total - pass_cnt
    acc = (pass_cnt / total) if total else 0.0

    def q(series: pd.Series, quantile: float) -> Optional[float]:
        s = series.dropna()
        if s.empty:
            return None
        return float(s.quantile(quantile))

    summary = pd.DataFrame(
        [
            {"metric": "total", "value": total},
            {"metric": "pass", "value": pass_cnt},
            {"metric": "fail", "value": fail_cnt},
            {"metric": "accuracy", "value": round(acc, 6)},
            {"metric": "latency_avg_s", "value": float(latency.mean()) if not latency.dropna().empty else None},
            {"metric": "latency_p50_s", "value": q(latency, 0.50)},
            {"metric": "latency_p95_s", "value": q(latency, 0.95)},
            {"metric": "latency_max_s", "value": float(latency.max()) if not latency.dropna().empty else None},
            {"metric": "input_tokens_avg", "value": float(tokens_in.mean()) if not tokens_in.dropna().empty else None},
            {"metric": "output_tokens_avg", "value": float(tokens_out.mean()) if not tokens_out.dropna().empty else None},
            {"metric": "input_tokens_sum", "value": float(tokens_in.sum()) if not tokens_in.dropna().empty else None},
            {"metric": "output_tokens_sum", "value": float(tokens_out.sum()) if not tokens_out.dropna().empty else None},
        ]
    )

    conf = pd.pivot_table(
        df,
        index="기대 에이전트",
        columns="응답값",
        values="ID",
        aggfunc="count",
        fill_value=0,
        dropna=False,
    )

    conf = conf.reset_index()
    return summary, conf


def build_excel_bytes(results_df: pd.DataFrame, *, cfg: Optional[EvalConfig] = None) -> bytes:
    """
    Streamlit download_button에 바로 넣을 수 있는 xlsx bytes 생성.
    """
    import io

    cfg = cfg or EvalConfig()
    summary_df, conf_df = compute_summary(results_df)

    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        results_df.to_excel(writer, sheet_name="results", index=False)
        summary_df.to_excel(writer, sheet_name="summary", index=False)
        conf_df.to_excel(writer, sheet_name="confusion_matrix", index=False)
        # config sheet
        pd.DataFrame([asdict(cfg)]).to_excel(writer, sheet_name="run_config", index=False)

    buf.seek(0)
    return buf.read()


def save_excel(results_df: pd.DataFrame, output_xlsx: str, *, cfg: Optional[EvalConfig] = None) -> str:
    """xlsx로 저장 후 경로 반환."""
    xlsx_bytes = build_excel_bytes(results_df, cfg=cfg)
    with open(output_xlsx, "wb") as f:
        f.write(xlsx_bytes)
    return output_xlsx


# -----------------------------
# 7) CLI entrypoint
# -----------------------------

def _load_prompt_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main() -> None:
    p = argparse.ArgumentParser(description="Bulk router eval with Gemini 2.5 Flash + Structured Output")
    p.add_argument("--input_csv", required=True, help="입력 CSV 파일 경로")
    p.add_argument("--output_xlsx", required=True, help="출력 Excel(.xlsx) 파일 경로")
    p.add_argument("--model", default="gemini-2.5-flash", help="모델 코드 (기본: gemini-2.5-flash)")
    p.add_argument("--concurrency", type=int, default=5, help="동시 요청 수 (1~5)")
    p.add_argument("--thinking_budget", type=int, default=0, help="thinkingBudget (0=OFF, -1=dynamic)")
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--max_output_tokens", type=int, default=512)
    p.add_argument("--seed", type=int, default=42)

    p.add_argument("--max_retries", type=int, default=2)
    p.add_argument("--retry_backoff_s", type=float, default=0.8)

    p.add_argument("--prompt_file", default=None, help="system prompt 텍스트 파일 경로(선택)")

    p.add_argument("--api_key", default=None, help="Gemini Developer API key(없으면 환경변수 사용)")
    p.add_argument("--vertexai", action="store_true", help="Vertex AI 사용")
    p.add_argument("--project", default=None, help="Vertex AI project id")
    p.add_argument("--location", default=None, help="Vertex AI location (예: us-central1)")

    args = p.parse_args()

    system_prompt = DEFAULT_SYSTEM_PROMPT
    if args.prompt_file:
        system_prompt = _load_prompt_file(args.prompt_file)

    cfg = EvalConfig(
        model=args.model,
        concurrency=args.concurrency,
        temperature=args.temperature,
        max_output_tokens=args.max_output_tokens,
        seed=args.seed,
        thinking_budget=args.thinking_budget,
        max_retries=args.max_retries,
        retry_backoff_s=args.retry_backoff_s,
        system_prompt=system_prompt,
    )

    # Run
    df = read_csv_safely(args.input_csv)
    results_df = asyncio.run(
        evaluate_dataframe_async(
            df,
            cfg,
            api_key=args.api_key,
            use_vertexai=args.vertexai,
            project=args.project,
            location=args.location,
        )
    )
    save_excel(results_df, args.output_xlsx, cfg=cfg)
    summary_df, _ = compute_summary(results_df)
    summary = dict(zip(summary_df["metric"], summary_df["value"]))
    print(
        f"rows={int(summary.get('total', 0))}, "
        f"accuracy={float(summary.get('accuracy', 0.0)):.4f}, "
        f"latency_avg_s={float(summary.get('latency_avg_s', 0.0)):.4f}"
    )
    print(f"Saved: {args.output_xlsx}")


if __name__ == "__main__":
    main()
