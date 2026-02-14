"""
채용 에이전트 검증 백오피스 / 업데이트일자: 260212
- 목적:
  1) CSV(질의/기대필터)를 업로드해서 지원자 관리 에이전트를 1차/2차(동일 세션)로 호출
  2) "지원자 관리 에이전트 평가 프롬프트" 프레임워크에 맞춰 ChatGPT(OpenAI API)로 자동 평가(JSON)
  3) 결과를 표로 확인하고 Excel로 다운로드
  4) 필요 시 'URL Agent(이동/버튼URL)' 벌크 테스트도 같은 화면에서 실행
  5) AQB v1.2.0 점수 계산(별도 탭/시트)

실행:
streamlit run aqb_v1.2.0.py

.env (이 파일과 같은 폴더 권장):
  # ATS(채용솔루션) 토큰
  ATS_BEARER_TOKEN=...
  ATS_CMS_TOKEN=...
  ATS_MRS_SESSION=...

  # OpenAI (ChatGPT 평가)
  OPENAI_API_KEY=...
  OPENAI_MODEL=gpt-5.2

주의:
- 토큰/키는 절대 깃에 커밋하지 마세요.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, Optional

import aiohttp
import pandas as pd
import streamlit as st

# 상위 폴더(ax)의 모듈을 import하기 위해 경로 추가
_AX_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _AX_DIR not in sys.path:
    sys.path.insert(0, _AX_DIR)

from curl_parsing import parse_curl_headers
from prompt_api import AxPromptApiClient, WORKER_DESCRIPTIONS, WORKER_TYPES, safe_len

from aqb_agent_client import ApplicantAgentClient
from aqb_bulk_runner import normalize_columns, run_applicant_calls_async, run_openai_judge_async
from aqb_common_utils import (
    build_applicant_csv_template,
    build_generic_csv_template,
    build_url_csv_template,
    load_dotenv,
    make_arrow_safe,
    run_logic_check,
)
from aqb_openai_judge import openai_judge_with_retry
from aqb_prompt_template import ENV_PRESETS, read_prompt_template
from aqb_runtime_utils import dataframe_to_excel_bytes, dataframes_to_excel_bytes, run_async
from aqb_url_tester import UrlAgentTester, run_url_tests_async
from aqb_aqb_scoring import (
    AQB_RULES_SUMMARY_MD,
    AQB_RUBRIC_MD,
    build_aqb_agent_summary,
    build_aqb_precheck_report,
    build_aqb_round_summary,
    run_aqb_scoring_async,
)

def main():
    st.set_page_config(page_title="채용 에이전트 검증 백오피스", page_icon="🧪", layout="wide")

    script_dir = os.path.dirname(os.path.abspath(__file__))

    # .env 자동 로드
    loaded_env = load_dotenv(os.path.join(script_dir, ".env"))

    st.title("🧪 채용 에이전트 검증 백오피스")

    with st.sidebar:
        st.header("설정")
        st.caption("토큰/키는 .env 또는 아래 입력으로 주입하세요. (커밋 금지)")

        # ENV 선택
        env = st.selectbox("환경 (DV/QA/ST/PR)", ["PR", "ST", "QA", "DV"], index=0)
        preset = ENV_PRESETS.get(env, {})

        base_url = st.text_input("ATS base_url", value=preset.get("base_url", ""), placeholder="https://api-llm....")
        origin = st.text_input("origin", value=preset.get("origin", ""), placeholder="https://...cms...")
        referer = st.text_input("referer", value=preset.get("referer", ""), placeholder="https://.../")

        st.divider()
        st.subheader("ATS 토큰")

        # cURL 붙여넣기 기능
        with st.expander("📋 cURL로 토큰 자동 입력", expanded=False):
            curl_text = st.text_area(
                "cURL 명령어 붙여넣기",
                placeholder="curl 'https://...' -H 'authorization: Bearer ...' -H 'cms-access-token: ...' ...",
                height=100,
                key="curl_input"
            )
            if st.button("🔑 인증 정보 파싱", key="parse_curl"):
                if curl_text.strip():
                    parsed = parse_curl_headers(curl_text)
                    # Bearer 접두사 제거
                    auth_val = parsed.get("authorization") or ""
                    if auth_val.lower().startswith("bearer "):
                        auth_val = auth_val[7:]
                    st.session_state["parsed_bearer"] = auth_val
                    st.session_state["parsed_cms"] = parsed.get("cms-access-token") or ""
                    st.session_state["parsed_mrs"] = parsed.get("mrs-session") or ""

                    # 파싱 결과 표시
                    if auth_val or parsed.get("cms-access-token") or parsed.get("mrs-session"):
                        st.success("✅ 토큰 파싱 완료! 아래 입력 필드에 자동 적용됩니다.")
                    else:
                        st.warning("⚠️ cURL에서 토큰을 찾지 못했습니다.")
                else:
                    st.warning("cURL 명령어를 입력하세요.")

        # 파싱된 토큰이 있으면 기본값으로 사용
        default_bearer = st.session_state.get("parsed_bearer") or os.getenv("ATS_BEARER_TOKEN", "")
        default_cms = st.session_state.get("parsed_cms") or os.getenv("ATS_CMS_TOKEN", "")
        default_mrs = st.session_state.get("parsed_mrs") or os.getenv("ATS_MRS_SESSION", "")

        bearer = st.text_input("ATS_BEARER_TOKEN", value=default_bearer, type="password")
        cms = st.text_input("ATS_CMS_TOKEN", value=default_cms, type="password")
        mrs = st.text_input("ATS_MRS_SESSION", value=default_mrs, type="password")

        # 세션 확인 버튼
        if st.button("🔍 세션 확인", key="check_session"):
            if base_url and bearer and cms and mrs:
                async def check_session():
                    connector = aiohttp.TCPConnector(ssl=False)
                    timeout = aiohttp.ClientTimeout(total=30)
                    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
                        url = f"{base_url.rstrip('/')}/api/v2/ai/orchestrator/query"
                        headers = {
                            "authorization": f"Bearer {bearer}",
                            "cms-access-token": cms,
                            "mrs-session": mrs,
                            "origin": origin,
                            "referer": referer,
                            "accept": "application/json, text/plain, */*",
                            "content-type": "application/json",
                        }
                        payload = {"conversationId": None, "userMessage": "테스트"}
                        try:
                            async with session.post(url, headers=headers, json=payload) as resp:
                                return resp.status == 200, resp.status
                        except Exception as e:
                            return False, str(e)

                ok, status = run_async(check_session())
                if ok:
                    st.success(f"✅ 세션 유효 (HTTP 200)")
                else:
                    st.error(f"❌ 세션 무효 또는 오류: {status}")

        st.divider()
        st.subheader("OpenAI (ChatGPT 평가)")

        # 주요 설정 (항상 표시)
        judge_parallel = st.slider("LLM 병렬수", min_value=1, max_value=10, value=3, step=1)
        max_chars = st.slider("응답 최대 길이(평가 입력)", min_value=2000, max_value=30000, value=15000, step=1000)

        # 고급 설정 (접기)
        with st.expander("⚙️ 고급 설정", expanded=False):
            openai_key = st.text_input("OPENAI_API_KEY", value=os.getenv("OPENAI_API_KEY", ""), type="password")
            openai_model = st.text_input("OPENAI_MODEL", value=os.getenv("OPENAI_MODEL", "gpt-5.2"))

            # 비용 계산용(선택): 1M 토큰당 USD
            st.caption("비용 계산용 (선택사항)")
            try:
                default_in = float(os.getenv("OPENAI_PRICE_INPUT_PER_1M", "0") or 0)
            except Exception:
                default_in = 0.0
            try:
                default_out = float(os.getenv("OPENAI_PRICE_OUTPUT_PER_1M", "0") or 0)
            except Exception:
                default_out = 0.0
            try:
                default_cached = float(os.getenv("OPENAI_PRICE_CACHED_INPUT_PER_1M", "0") or 0)
            except Exception:
                default_cached = 0.0

            price_input_per_1m = st.number_input("Input $/1M tokens", min_value=0.0, value=default_in, step=0.1, format="%.4f")
            price_output_per_1m = st.number_input("Output $/1M tokens", min_value=0.0, value=default_out, step=0.1, format="%.4f")
            price_cached_input_per_1m = st.number_input("Cached input $/1M tokens", min_value=0.0, value=default_cached, step=0.1, format="%.4f")

        st.divider()
        st.subheader("실행 옵션")
        agent_parallel = st.slider("ATS 호출 병렬수", min_value=1, max_value=10, value=3, step=1)
        n_calls = st.slider(
            "채팅 호출 횟수",
            min_value=1, max_value=4, value=1, step=1,
            help="동일 conversationId에서 같은 질문을 N번 반복 (일관성 테스트용). 1이면 일관성 평가 제외."
        )
        independent_sessions = st.checkbox(
            "일관성용 독립 세션 호출",
            value=True,
            help="ON이면 n회 호출을 각각 독립 채팅방에서 실행합니다. (일관성 정식 기준 권장)",
        )
        only_missing = st.checkbox("이미 채워진 row는 스킵", value=True)
        limit_rows = st.number_input("상위 N개만 실행 (0=전체)", min_value=0, value=0, step=1)
        limit_rows = None if int(limit_rows) == 0 else int(limit_rows)

        st.caption("✅ .env 로드됨" if loaded_env else "⚠️ .env 미로드(없거나 비어있음)")

    tab_generic, tab_applicant, tab_url, tab_quality, tab_prompt = st.tabs(
        ["범용 테스트", "지원자 에이전트 검증", "이동 에이전트 검증", "품질 점수 계산", "프롬프트 관리"]
    )

    # --------------------------------------------
    # Tab 2: 지원자 에이전트 검증
    # --------------------------------------------
    with tab_applicant:
        st.subheader("1) CSV 업로드")

        # 업로드용 CSV 템플릿 다운로드
        st.download_button(
            "⬇️ 업로드용 CSV 양식 다운로드",
            data=build_applicant_csv_template(),
            file_name="지원자_관리_질의_템플릿.csv",
            mime="text/csv",
        )

        uploaded = st.file_uploader("지원자 관리 질의 CSV", type=["csv"])

        # 프롬프트 템플릿 로드 + 편집
        st.subheader("2) 평가 프롬프트")
        prompt_default = read_prompt_template(script_dir)
        prompt_text = st.text_area("평가 프롬프트(수정 가능)", value=prompt_default, height=320)

        if uploaded is None:
            st.info("CSV를 업로드하면 실행할 수 있어요.")
        else:
            try:
                df_in = pd.read_csv(uploaded, encoding="utf-8")
            except Exception:
                df_in = pd.read_csv(uploaded, encoding="utf-8-sig")
            df_in = normalize_columns(df_in)

            st.write("미리보기", df_in.head(10))

            # Context 및 targetAssistant 설정
            st.subheader("3) API 설정 (선택)")
            col_ctx, col_target = st.columns(2)

            with col_ctx:
                use_context = st.checkbox("Context 사용", value=False, help="API 호출 시 context 객체를 함께 전송")
                context_obj: Optional[Dict[str, Any]] = None
                if use_context:
                    context_input = st.text_area(
                        "Context (JSON 형식)",
                        value='{"recruitPlanId": 123}',
                        height=80,
                        help='예: {"recruitPlanId": 123, "채용명": "2026년 공채"}'
                    )
                    try:
                        context_obj = json.loads(context_input)
                        st.success("✅ JSON 파싱 성공")
                    except json.JSONDecodeError as e:
                        st.error(f"❌ JSON 파싱 오류: {e}")
                        context_obj = None

            with col_target:
                use_target_assistant = st.checkbox("targetAssistant 지정", value=False, help="특정 어시스턴트를 지정하여 호출")
                target_assistant: Optional[str] = None
                if use_target_assistant:
                    target_assistant = st.text_input(
                        "targetAssistant",
                        value="RECRUIT_PLAN_ASSISTANT",
                        help='예: RECRUIT_PLAN_ASSISTANT, RECRUIT_PLAN_CREATE_ASSISTANT'
                    )

            # 실행 버튼
            st.subheader("4) 실행")
            colA, colB, colC = st.columns(3)
            run_calls = colA.button("① ATS 호출만 실행", key="tab2_run_calls")
            run_judge = colB.button("② LLM 평가만 실행", key="tab2_run_judge")
            run_all = colC.button("③ 전체 실행(호출+평가)", key="tab2_run_all")

            # 진행률 표시 영역 (개선: 업데이트 형태)
            progress = st.progress(0)
            progress_placeholder = st.empty()

            # 임시 저장 경로
            temp_save_path = os.path.join(script_dir, f"_autosave_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")

            def auto_save_callback(df_partial: pd.DataFrame):
                try:
                    df_partial.to_csv(temp_save_path, index=False, encoding="utf-8-sig")
                    st.toast(f"💾 자동 저장 완료 ({temp_save_path})")
                except Exception as e:
                    st.toast(f"⚠️ 자동 저장 실패: {e}")

            def progress_cb(done: int, total: int, msg: str, elapsed: float = 0.0, completed: int = 0):
                if total > 0:
                    progress.progress(min(1.0, done / total))
                # 진행률 업데이트 (하나의 placeholder에서 갱신)
                if done > 0 and elapsed > 0:
                    avg_time = elapsed / done
                    remaining = (total - done) * avg_time
                    progress_placeholder.markdown(
                        f"**진행** {done}/{total} | **총 경과 시간** {elapsed:.1f}초 (약 {remaining:.0f}초 남음)"
                    )
                else:
                    progress_placeholder.markdown(f"**진행** {done}/{total} | **총 경과 시간** {elapsed:.1f}초")

            # 상태 df는 session_state에 보관
            if "applicant_df" not in st.session_state:
                st.session_state["applicant_df"] = df_in

            # 버튼을 누르면 session_state를 기준으로 실행
            if run_calls or run_all:
                if not (base_url and origin and referer and bearer and cms and mrs):
                    st.error("ATS 설정(base_url/origin/referer)과 토큰 3종을 입력하세요.")
                else:
                    client = ApplicantAgentClient(
                        base_url=base_url,
                        bearer_token=bearer,
                        cms_token=cms,
                        mrs_session=mrs,
                        origin=origin,
                        referer=referer,
                        max_parallel=agent_parallel,
                    )
                    st.session_state["applicant_df"] = run_async(
                        run_applicant_calls_async(
                            st.session_state["applicant_df"],
                            client,
                            progress_cb=progress_cb,
                            only_missing=only_missing,
                            limit_rows=limit_rows,
                            n_calls=n_calls,
                            context=context_obj,
                            target_assistant=target_assistant,
                            independent_sessions=independent_sessions,
                            auto_save_callback=auto_save_callback,
                        )
                    )
                    st.success("ATS 호출 완료")

            if run_judge or run_all:
                if not openai_key:
                    st.error("OPENAI_API_KEY를 입력하세요.")
                else:
                    df_result, eval_count = run_async(
                        run_openai_judge_async(
                            st.session_state["applicant_df"],
                            prompt_template=prompt_text,
                            api_key=openai_key,
                            model=openai_model,
                            progress_cb=progress_cb,
                            only_missing=only_missing,
                            limit_rows=limit_rows,
                            max_chars_per_response=max_chars,
                            max_parallel=judge_parallel,
                            price_input_per_1m=price_input_per_1m,
                            price_output_per_1m=price_output_per_1m,
                            price_cached_input_per_1m=price_cached_input_per_1m,
                        )
                    )
                    st.session_state["applicant_df"] = df_result
                    if eval_count == 0:
                        st.warning("LLM 평가 대상이 없습니다. (1차/2차 raw 데이터가 없거나 이미 평가 완료됨)")
                    else:
                        st.success(f"LLM 평가 완료 ({eval_count}건)")

            df_out = st.session_state["applicant_df"]

            st.subheader("5) 결과 요약")
            # 기본 요약
            total_rows = len(df_out)
            err_rows = df_out["특이사항"].astype(str).str.contains("fail|timeout|HTTP|LLM 평가 실패", case=False, na=False).sum() if "특이사항" in df_out.columns else 0

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("총 Row", total_rows)
            c2.metric("에러/특이", int(err_rows))

            if "총점" in df_out.columns:
                try:
                    avg_total = float(pd.to_numeric(df_out["총점"], errors="coerce").dropna().mean())
                except Exception:
                    avg_total = 0.0
                c3.metric("평균 총점", f"{avg_total:.1f}")
            else:
                c3.metric("평균 총점", "-")

            if "LLM 비용(USD)" in df_out.columns:
                try:
                    total_cost = float(pd.to_numeric(df_out["LLM 비용(USD)"], errors="coerce").fillna(0).sum())
                except Exception:
                    total_cost = 0.0
                c4.metric("LLM 비용(USD)", f"${total_cost:,.4f}")
            else:
                c4.metric("LLM 비용(USD)", "-")

            st.subheader("6) 결과 테이블")
            st.dataframe(make_arrow_safe(df_out), use_container_width=True, height=420)

            st.subheader("7) 다운로드")
            xlsx_bytes = dataframe_to_excel_bytes(df_out, sheet_name="applicant_results")
            st.download_button(
                "📥 결과 Excel 다운로드",
                data=xlsx_bytes,
                file_name=f"applicant_agent_results_{env}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    # --------------------------------------------
    # Tab 품질 점수 계산
    # --------------------------------------------
    with tab_quality:
        st.subheader("품질 점수 계산")
        st.caption("정확성(Accuracy)과 사용성(Usability)을 우선으로, 실행 전 프리체크 후 점수를 계산합니다.")

        with st.expander("점수화 기준(루브릭) 보기", expanded=False):
            st.markdown(AQB_RUBRIC_MD)
        with st.expander("평가 규칙 요약 보기", expanded=False):
            st.markdown(AQB_RULES_SUMMARY_MD)

        source_candidates = []
        if "generic_df" in st.session_state:
            source_candidates.append(("범용 테스트 결과", "generic_df", "generic_results"))
        if "applicant_df" in st.session_state:
            source_candidates.append(("지원자 에이전트 검증 결과", "applicant_df", "applicant_results"))
        if "url_df" in st.session_state:
            source_candidates.append(("이동 에이전트 검증 결과", "url_df", "url_results"))

        if not source_candidates:
            st.info("사용 가능한 데이터 소스가 없습니다. 먼저 테스트 탭에서 결과를 생성하세요.")
        else:
            source_label_to_meta = {label: (key, sheet_name) for label, key, sheet_name in source_candidates}
            source_labels = list(source_label_to_meta.keys())
            default_idx = 0
            for i, lbl in enumerate(source_labels):
                if "범용 테스트 결과" in lbl:
                    default_idx = i
                    break

            selected_source_label = st.selectbox(
                "데이터 소스 선택",
                source_labels,
                index=default_idx,
                help="점수 계산에 사용할 결과 데이터셋을 선택하세요.",
            )
            source_key, source_sheet_name = source_label_to_meta[selected_source_label]
            source_df = st.session_state[source_key].copy()
            st.caption(f"선택 소스: `{selected_source_label}` (`{source_key}`)")
            st.write("입력 데이터 미리보기", source_df.head(10))

            mode = st.radio("설정 모드", ["간편 모드 (추천)", "고급 모드"], horizontal=True)
            is_advanced = mode == "고급 모드"

            tolerance_pct = 1.0
            consistency_min_runs = 3
            allow_two_run_proxy = True
            consistency_under_min_policy = "two_run_proxy"
            use_semantic_llm = True
            use_consistency_llm = True
            allow_force_run = False

            st.subheader("계산 옵션")
            if is_advanced:
                opt1, opt2, opt3 = st.columns(3)
                with opt1:
                    tolerance_pct = st.number_input(
                        "수치 허용 오차(%)",
                        min_value=0.0,
                        max_value=20.0,
                        value=1.0,
                        step=0.1,
                        format="%.1f",
                        help="정확성/일관성 수치 비교 허용 오차입니다.",
                    )
                with opt2:
                    consistency_min_runs = st.number_input(
                        "일관성 최소 응답 수",
                        min_value=2,
                        max_value=4,
                        value=3,
                        step=1,
                        help="요구사항 권장값은 3회입니다.",
                    )
                with opt3:
                    allow_two_run_proxy = st.checkbox(
                        "일관성 미달 시 임시 2회 평가 허용",
                        value=True,
                        help="ON: 3회 미달 시 2회 기준 임시 평가 / OFF: 0점",
                    )
                consistency_under_min_policy = "two_run_proxy" if allow_two_run_proxy else "zero"

                llm_col1, llm_col2, llm_col3 = st.columns(3)
                with llm_col1:
                    use_semantic_llm = st.checkbox("의도 충족 LLM 평가", value=True)
                with llm_col2:
                    use_consistency_llm = st.checkbox("일관성 LLM 평가", value=True)
                with llm_col3:
                    allow_force_run = st.checkbox(
                        "프리체크 차단 경고 무시하고 실행",
                        value=False,
                        help="차단 FAIL이 있어도 강제로 점수를 계산합니다.",
                    )
            else:
                use_llm_boost = st.checkbox(
                    "의도/일관성 LLM 보강 평가 사용",
                    value=True,
                    help="OFF면 해당 지표를 규칙 기반으로만 계산합니다.",
                )
                use_semantic_llm = use_llm_boost
                use_consistency_llm = use_llm_boost
                allow_two_run_proxy = st.checkbox(
                    "일관성 미달 시 임시 2회 평가 허용",
                    value=True,
                    help="기본 ON 권장",
                )
                consistency_under_min_policy = "two_run_proxy" if allow_two_run_proxy else "zero"
                st.info(
                    "간편 모드 기본값: 허용오차 ±1.0%, 일관성 최소 3회, "
                    "TTFT는 PASS/FAIL만 표기(종합점수 미반영)."
                )

            precheck_summary, precheck_df = build_aqb_precheck_report(
                source_df,
                consistency_min_runs=int(consistency_min_runs),
            )

            st.subheader("실행 전 적합성 진단 (프리체크)")
            pc1, pc2, pc3, pc4 = st.columns(4)
            pc1.metric("문항 수", precheck_summary.get("total_rows", 0))
            pc2.metric("응답 커버리지", f"{precheck_summary.get('response_coverage_pct', 0.0):.2f}%")
            pc3.metric("일관성 준비도", f"{precheck_summary.get('consistency_ready_pct', 0.0):.2f}%")
            pc4.metric("WARN / FAIL", f"{precheck_summary.get('warn_count', 0)} / {precheck_summary.get('fail_count', 0)}")

            if precheck_summary.get("hard_fail"):
                st.error("차단 FAIL이 있습니다. 데이터/컬럼을 보완하거나 고급 모드에서 강행 실행을 선택하세요.")
            elif precheck_summary.get("warn_count", 0) > 0:
                st.warning("WARN 항목이 있습니다. 점수 정확도에 영향을 줄 수 있으니 상세를 확인하세요.")
            else:
                st.success("프리체크 통과: 현재 설정으로 점수 계산 적합도가 높습니다.")
            st.dataframe(make_arrow_safe(precheck_df), use_container_width=True, height=240)

            run_aqb_score = st.button("품질 점수 계산 실행", key="run_quality_score")
            if run_aqb_score:
                if precheck_summary.get("hard_fail") and not allow_force_run:
                    st.error("차단 FAIL이 있어 실행을 중단했습니다. (고급 모드에서 강행 실행 가능)")
                elif (use_semantic_llm or use_consistency_llm) and not openai_key:
                    st.error("OPENAI_API_KEY를 입력해야 LLM 평가를 사용할 수 있습니다.")
                else:
                    with st.spinner("품질 점수 계산 중..."):
                        score_df = run_async(
                            run_aqb_scoring_async(
                                source_df,
                                api_key=openai_key if (use_semantic_llm or use_consistency_llm) else "",
                                model=openai_model,
                                max_parallel=judge_parallel,
                                tolerance_pct=float(tolerance_pct),
                                use_semantic_llm=bool(use_semantic_llm),
                                use_consistency_llm=bool(use_consistency_llm),
                                consistency_min_runs=int(consistency_min_runs),
                                consistency_under_min_policy=consistency_under_min_policy,
                            )
                        )
                    round_df = build_aqb_round_summary(score_df)
                    agent_df = build_aqb_agent_summary(score_df)

                    if "aqb_score_store" not in st.session_state:
                        st.session_state["aqb_score_store"] = {}
                    st.session_state["aqb_score_store"][source_key] = {
                        "score_df": score_df,
                        "round_df": round_df,
                        "agent_df": agent_df,
                        "precheck_df": precheck_df,
                    }
                    st.success(f"품질 점수 계산 완료 ({len(score_df)}건)")

            score_store = st.session_state.get("aqb_score_store", {})
            if source_key in score_store:
                stored = score_store[source_key]
                df_score = stored.get("score_df", pd.DataFrame()).copy()
                df_round = stored.get("round_df", pd.DataFrame()).copy()
                df_agent = stored.get("agent_df", pd.DataFrame()).copy()
                df_precheck = stored.get("precheck_df", pd.DataFrame()).copy()

                st.subheader("결과 요약")
                total_rows = len(df_score)
                manual_cnt = (
                    int(df_score["flag_manual_review"].astype(bool).sum())
                    if "flag_manual_review" in df_score.columns
                    else 0
                )

                avg_total = 0.0
                if not df_agent.empty and "weighted_total_avg" in df_agent.columns:
                    try:
                        avg_total = float(pd.to_numeric(df_agent["weighted_total_avg"], errors="coerce").dropna().mean())
                    except Exception:
                        avg_total = 0.0

                avg_accuracy = 0.0
                if not df_agent.empty and "accuracy_avg" in df_agent.columns:
                    try:
                        avg_accuracy = float(pd.to_numeric(df_agent["accuracy_avg"], errors="coerce").dropna().mean())
                    except Exception:
                        avg_accuracy = 0.0

                avg_stability = 0.0
                if not df_agent.empty and "stability_avg" in df_agent.columns:
                    try:
                        avg_stability = float(pd.to_numeric(df_agent["stability_avg"], errors="coerce").dropna().mean())
                    except Exception:
                        avg_stability = 0.0

                sm1, sm2, sm3, sm4 = st.columns(4)
                sm1.metric("문항 수", total_rows)
                sm2.metric("에이전트 평균 종합점수", f"{avg_total:.2f}")
                sm3.metric("평균 정확성 / 안정성", f"{avg_accuracy:.2f} / {avg_stability:.2f}")
                sm4.metric("수기 확인 필요", manual_cnt)

                st.subheader("문항별 점수")
                st.caption("`*_calc_method` 컬럼으로 각 지표 점수 산출 방식(LLM/규칙)을 확인할 수 있습니다.")
                st.dataframe(make_arrow_safe(df_score), use_container_width=True, height=360)

                st.subheader("회차별 평균 점수")
                if df_round.empty:
                    st.info("회차 요약 데이터가 없습니다.")
                else:
                    st.dataframe(make_arrow_safe(df_round), use_container_width=True, height=220)

                st.subheader("에이전트별 최종 점수")
                if df_agent.empty:
                    st.info("에이전트 요약 데이터가 없습니다.")
                else:
                    st.dataframe(make_arrow_safe(df_agent), use_container_width=True, height=220)

                st.subheader("다운로드")
                score_xlsx = dataframes_to_excel_bytes(
                    {
                        source_sheet_name: source_df,
                        "aqb_scores_v1_2": df_score,
                        "aqb_round_summary": df_round,
                        "aqb_agent_summary": df_agent,
                        "aqb_precheck": df_precheck,
                    }
                )
                st.download_button(
                    "📥 품질 점수 Excel 다운로드 (원본+점수/요약/프리체크 시트)",
                    data=score_xlsx,
                    file_name=f"aqb_quality_scores_{env}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_quality_score",
                )

    # --------------------------------------------
    # Tab 1: 범용 테스트
    # --------------------------------------------
    with tab_generic:
        st.subheader("범용 테스트")
        st.caption("범용 에이전트 테스트. 필수 컬럼: `질의`. 선택 컬럼: `LLM 평가기준`, `검증 필드`, `기대값`")

        # CSV 템플릿 다운로드
        st.download_button(
            "⬇️ 범용 테스트 CSV 양식 다운로드",
            data=build_generic_csv_template(),
            file_name="범용_테스트_템플릿.csv",
            mime="text/csv",
            key="download_generic_template"
        )

        # 입력 방식 선택
        input_mode = st.radio("입력 방식", ["CSV 업로드", "직접 입력"], horizontal=True)

        generic_df: Optional[pd.DataFrame] = None

        if input_mode == "CSV 업로드":
            up_generic = st.file_uploader("범용 테스트 CSV", type=["csv"], key="generic_csv")
            if up_generic is not None:
                try:
                    generic_df = pd.read_csv(up_generic, encoding="utf-8")
                except Exception:
                    generic_df = pd.read_csv(up_generic, encoding="utf-8-sig")
                generic_df = normalize_columns(generic_df)
        else:
            # 직접 입력 (4개 필드)
            st.markdown("**질의 입력**")
            direct_query = st.text_area("질의", placeholder="에이전트에게 보낼 질의를 입력하세요", height=100)
            direct_criteria = st.text_area("LLM 평가기준", placeholder="평가 기준을 입력하세요 (예: 정확한 수치 포함 여부, 응답 형식 등)", height=100)
            col_field, col_expect = st.columns(2)
            with col_field:
                direct_field = st.text_input("검증 필드", placeholder="예: assistantMessage, dataUIList[0].uiValue.buttonUrl")
            with col_expect:
                direct_expected = st.text_input("기대값", placeholder="응답에 포함되어야 할 문자열")

            if direct_query.strip():
                generic_df = pd.DataFrame([{
                    "질의": direct_query.strip(),
                    "LLM 평가기준": direct_criteria.strip(),
                    "검증 필드": direct_field.strip(),
                    "기대값": direct_expected.strip(),
                }])

        if generic_df is not None:
            # ID 자동 생성 (CSV에 ID 컬럼 없으면)
            if "ID" not in generic_df.columns:
                generic_df.insert(0, "ID", [f"Q-{i+1}" for i in range(len(generic_df))])

            # 선택 컬럼 기본값 보장
            for _col_name in ("LLM 평가기준", "검증 필드", "기대값"):
                if _col_name not in generic_df.columns:
                    generic_df[_col_name] = ""
            generic_df = generic_df.fillna("")

            st.session_state["generic_input_df"] = generic_df.copy()
            st.write("미리보기", generic_df.head(10))

            # API 설정 (범용 테스트용)
            st.subheader("API 설정 (선택)")
            col_ctx_g, col_target_g = st.columns(2)

            with col_ctx_g:
                use_generic_context = st.checkbox("Context 사용", value=False, key="generic_context_check")
                generic_context_obj: Optional[Dict[str, Any]] = None
                if use_generic_context:
                    generic_context_input = st.text_area(
                        "Context (JSON 형식)",
                        value='{"recruitPlanId": 123}',
                        height=80,
                        key="generic_context_input"
                    )
                    try:
                        generic_context_obj = json.loads(generic_context_input)
                        st.success("✅ JSON 파싱 성공")
                    except json.JSONDecodeError:
                        st.error("JSON 파싱 오류")
                        generic_context_obj = None

            with col_target_g:
                use_generic_target = st.checkbox("targetAssistant 지정", value=False, key="generic_target_check")
                generic_target_assistant: Optional[str] = None
                if use_generic_target:
                    generic_target_assistant = st.text_input(
                        "targetAssistant",
                        value="RECRUIT_PLAN_ASSISTANT",
                        key="generic_target_input",
                        help='예: RECRUIT_PLAN_ASSISTANT, RECRUIT_PLAN_CREATE_ASSISTANT'
                    )

            # ── 버튼 2개: 1단계 / 2단계 ──
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                run_step1 = st.button("1단계: 질의 보내기", key="run_generic_step1")
            with col_btn2:
                run_step2 = st.button("2단계: 평가하기", key="run_generic_step2")

            progress_generic = st.progress(0)
            progress_generic_text = st.empty()

            # ── Step 1: 질의 보내기 (병렬) ──
            if run_step1:
                if not (base_url and bearer and cms and mrs):
                    st.error("ATS 설정과 토큰을 입력하세요.")
                else:
                    async def run_generic_queries():
                        nonlocal progress_generic, progress_generic_text
                        client = ApplicantAgentClient(
                            base_url=base_url,
                            bearer_token=bearer,
                            cms_token=cms,
                            mrs_session=mrs,
                            origin=origin,
                            referer=referer,
                            max_parallel=agent_parallel,
                        )
                        connector = aiohttp.TCPConnector(limit=50, ssl=False)
                        _timeout = aiohttp.ClientTimeout(total=120)

                        input_df = st.session_state["generic_input_df"]
                        total = len(input_df)
                        done_count = 0
                        start_time = time.time()

                        # 결과 DataFrame 준비 (입력 컬럼 + 출력 컬럼)
                        res_df = input_df.copy()
                        for _c in ("응답", "응답 시간(초)", "실행 프로세스", "오류", "raw"):
                            res_df[_c] = ""

                        async with aiohttp.ClientSession(connector=connector, timeout=_timeout) as session:
                            async def _run_one(idx: int):
                                async with client.semaphore:
                                    query = str(res_df.loc[idx, "질의"])
                                    sync_result = await client.test_orchestrator_sync(
                                        session,
                                        query,
                                        conversation_id=None,
                                        context=generic_context_obj,
                                        target_assistant=generic_target_assistant,
                                    )
                                    if sync_result.get("error"):
                                        return {"idx": idx, "err": str(sync_result.get("error")), "sse": None}
                                    return {"idx": idx, "err": "", "sse": sync_result}

                            tasks = []
                            for i in range(total):
                                tasks.append(asyncio.create_task(_run_one(i)))

                            for fut in asyncio.as_completed(tasks):
                                result = await fut
                                idx = result["idx"]
                                err = result["err"]
                                sse = result["sse"]

                                if sse is None:
                                    # 동기식 테스트 API 호출 실패
                                    res_df.at[idx, "오류"] = err
                                else:
                                    # 실행 프로세스 요약
                                    exec_summary = ""
                                    for ep in sse.get("execution_processes", []):
                                        msg_summary = ep.get("messageSummary", "")
                                        if msg_summary:
                                            step_ms = ep.get("ms")
                                            try:
                                                step_ms_float = float(step_ms)
                                            except Exception:
                                                step_ms_float = None
                                            if step_ms_float is not None:
                                                exec_summary += f"[{msg_summary} ({step_ms_float:.1f}ms)] "
                                            else:
                                                exec_summary += f"[{msg_summary}] "

                                    res_df.at[idx, "응답"] = sse.get("assistant_message", "")
                                    rt = sse.get("response_time_sec")
                                    res_df.at[idx, "응답 시간(초)"] = round(rt, 2) if rt else ""
                                    res_df.at[idx, "실행 프로세스"] = exec_summary.strip()
                                    res_df.at[idx, "오류"] = sse.get("error", "")
                                    # LLM/로직 평가에서 "원본 응답"을 사용할 수 있도록
                                    # 축약 payload + worker 원본/요약을 함께 저장
                                    res_df.at[idx, "raw"] = json.dumps(
                                        {
                                            "assistantMessage": sse.get("assistant_message"),
                                            "dataUIList": sse.get("data_ui_list"),
                                            "guideList": sse.get("guide_list"),
                                            "execution_processes": sse.get("execution_processes", []),
                                            "worker": sse.get("workers", []),
                                            "workerMsMap": sse.get("worker_ms_map", {}),
                                            "conversation_id": sse.get("conversation_id"),
                                            "response_time_sec": sse.get("response_time_sec"),
                                            "error": sse.get("error", ""),
                                        },
                                        ensure_ascii=False,
                                        default=str,
                                    )

                                done_count += 1
                                elapsed = time.time() - start_time
                                progress_generic.progress(min(1.0, done_count / total))
                                if done_count > 0 and elapsed > 0:
                                    remaining = (total - done_count) * (elapsed / done_count)
                                    progress_generic_text.markdown(
                                        f"**진행** {done_count}/{total} | "
                                        f"**총 경과 시간** {elapsed:.1f}초 (약 {remaining:.0f}초 남음)"
                                    )

                        return res_df

                    result_df = run_async(run_generic_queries())
                    st.session_state["generic_results_df"] = result_df
                    st.session_state["generic_df"] = result_df.copy()
                    st.success("1단계 완료: 질의 응답 수집 완료")

            # ── Step 2: 평가하기 ──
            if run_step2:
                if "generic_results_df" not in st.session_state:
                    st.error("먼저 1단계(질의 보내기)를 실행하세요.")
                else:
                    eval_df = st.session_state["generic_results_df"].copy()

                    # (A) 로직 평가 (동기, 즉시)
                    if "로직 검증결과" not in eval_df.columns:
                        eval_df["로직 검증결과"] = ""
                    for idx in range(len(eval_df)):
                        field_path = str(eval_df.at[idx, "검증 필드"]).strip()
                        expected = str(eval_df.at[idx, "기대값"]).strip()
                        if field_path and expected and field_path.lower() != "nan" and expected.lower() != "nan":
                            raw_str = str(eval_df.at[idx, "raw"])
                            eval_df.at[idx, "로직 검증결과"] = run_logic_check(raw_str, field_path, expected)

                    # (B) LLM 평가 (비동기, 병렬)
                    if "LLM 평가결과" not in eval_df.columns:
                        eval_df["LLM 평가결과"] = ""

                    # LLM 평가 대상 인덱스 수집
                    llm_targets = []
                    for idx in range(len(eval_df)):
                        criteria = str(eval_df.at[idx, "LLM 평가기준"]).strip()
                        if criteria and criteria.lower() != "nan":
                            llm_targets.append(idx)

                    if llm_targets and openai_key:
                        async def run_generic_llm_eval():
                            sem = asyncio.Semaphore(judge_parallel)
                            _timeout = aiohttp.ClientTimeout(total=120)

                            async with aiohttp.ClientSession(timeout=_timeout) as session:
                                async def eval_one(idx: int):
                                    async with sem:
                                        row_err = str(eval_df.at[idx, "오류"]).strip()
                                        if row_err and row_err.lower() != "nan":
                                            return idx, "평가 불가 (호출 오류)"

                                        criteria = str(eval_df.at[idx, "LLM 평가기준"])
                                        response_raw = str(eval_df.at[idx, "raw"])
                                        query = str(eval_df.at[idx, "질의"])

                                        eval_prompt = f"""다음 질의에 대한 에이전트 응답을 평가하세요.

질의: {query}

응답(raw JSON): {response_raw[:max_chars]}

평가 기준: {criteria}

평가 결과를 JSON으로 출력하세요:
{{"score": 0-5, "passed": true/false, "reason": "평가 사유"}}
"""
                                        result, _usage, err = await openai_judge_with_retry(
                                            session, openai_key, openai_model, eval_prompt
                                        )
                                        if result:
                                            return idx, json.dumps(result, ensure_ascii=False)
                                        return idx, f"평가 실패: {err}"

                                eval_tasks = [asyncio.create_task(eval_one(i)) for i in llm_targets]
                                for fut in asyncio.as_completed(eval_tasks):
                                    idx, eval_result = await fut
                                    eval_df.at[idx, "LLM 평가결과"] = eval_result

                        run_async(run_generic_llm_eval())
                    elif llm_targets and not openai_key:
                        st.warning("LLM 평가 대상이 있으나 OpenAI API 키가 설정되지 않았습니다.")

                    st.session_state["generic_df"] = eval_df
                    st.success("2단계 완료: 평가 완료")

            # ── 결과 표시 ──
            if "generic_df" in st.session_state:
                df_generic_out = st.session_state["generic_df"]
                st.subheader("결과 테이블")

                # 요약 메트릭
                total_q = len(df_generic_out)
                logic_col = df_generic_out.get("로직 검증결과")
                logic_pass = 0
                logic_fail = 0
                if logic_col is not None:
                    logic_pass = int(logic_col.astype(str).str.startswith("PASS").sum())
                    logic_fail = int(logic_col.astype(str).str.startswith("FAIL").sum())
                llm_col = df_generic_out.get("LLM 평가결과")
                llm_done = 0
                if llm_col is not None:
                    llm_done = int((llm_col.astype(str).str.strip() != "").sum())
                err_col = df_generic_out.get("오류")
                err_count = 0
                if err_col is not None:
                    err_count = int((err_col.astype(str).str.strip() != "").sum()
                                    - (err_col.astype(str).str.strip().str.lower() == "nan").sum())

                mc1, mc2, mc3, mc4 = st.columns(4)
                mc1.metric("총 질의 수", total_q)
                mc2.metric("로직 PASS / FAIL", f"{logic_pass} / {logic_fail}")
                mc3.metric("LLM 평가 완료", llm_done)
                mc4.metric("오류 건수", max(0, err_count))

                st.dataframe(make_arrow_safe(df_generic_out), use_container_width=True, height=420)

                xlsx_bytes = dataframe_to_excel_bytes(df_generic_out, sheet_name="generic_results")
                st.download_button(
                    "📥 범용 테스트 결과 Excel 다운로드",
                    data=xlsx_bytes,
                    file_name=f"generic_test_results_{env}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key="download_generic"
                )
        else:
            st.info("CSV를 업로드하거나 직접 입력하세요.")

    # --------------------------------------------
    # Tab 3: 이동 에이전트 검증
    # --------------------------------------------
    with tab_url:
        st.subheader("이동 에이전트 검증")
        st.caption("CSV 컬럼 예시: ID, 질의, 기대URL (기대URL은 부분문자열 또는 /정규식/ 형태 지원)")

        # CSV 템플릿 다운로드
        st.download_button(
            "⬇️ 이동 에이전트 검증 CSV 양식 다운로드",
            data=build_url_csv_template(),
            file_name="이동_에이전트_검증_템플릿.csv",
            mime="text/csv",
            key="download_url_template"
        )

        up3 = st.file_uploader("URL 테스트 CSV", type=["csv"], key="urlcsv")

        if up3 is None:
            st.info("URL 테스트용 CSV를 업로드하세요.")
        else:
            try:
                df3 = pd.read_csv(up3, encoding="utf-8")
            except Exception:
                df3 = pd.read_csv(up3, encoding="utf-8-sig")
            df3 = normalize_columns(df3)

            st.write("미리보기", df3.head(10))

            if not (base_url and origin and referer and bearer and cms and mrs):
                st.warning("좌측 설정에서 ATS 환경/토큰을 입력하세요.")
            else:
                tester = UrlAgentTester(
                    base_url=base_url,
                    bearer_token=bearer,
                    cms_token=cms,
                    mrs_session=mrs,
                    origin=origin,
                    referer=referer,
                    max_parallel=agent_parallel,
                )

                rows = []
                for _, r in df3.iterrows():
                    rows.append(
                        {
                            "ID": str(r.get("ID", "")),
                            "질의": str(r.get("질의", "")),
                            "기대URL": str(r.get("기대URL", "")),
                        }
                    )

                run_url = st.button("URL 테스트 실행")
                progress3 = st.progress(0)
                log3 = st.empty()

                def progress_cb3(done: int, total: int, msg: str):
                    if total > 0:
                        progress3.progress(min(1.0, done / total))
                    log3.write(msg)

                if run_url:
                    df_url_out = run_async(run_url_tests_async(rows, tester, progress_cb=progress_cb3))
                    st.session_state["url_df"] = df_url_out
                    st.success("URL 테스트 완료")

                if "url_df" in st.session_state:
                    df_url_out = st.session_state["url_df"]
                    st.dataframe(make_arrow_safe(df_url_out), use_container_width=True, height=420)

                    xlsx_bytes = dataframe_to_excel_bytes(df_url_out, sheet_name="url_results")
                    st.download_button(
                        "📥 URL 결과 Excel 다운로드",
                        data=xlsx_bytes,
                        file_name=f"url_agent_results_{env}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

    # --------------------------------------------
    # Tab 4: 프롬프트 관리
    # --------------------------------------------
    with tab_prompt:
        st.subheader("Worker 프롬프트 관리")
        st.caption("Worker별 시스템 프롬프트를 조회, 수정, 초기화할 수 있습니다.")

        # 세션 상태 초기화
        if "prompt_result" not in st.session_state:
            st.session_state["prompt_result"] = None
        if "prompt_worker" not in st.session_state:
            st.session_state["prompt_worker"] = WORKER_TYPES[0]
        if "prompt_editing" not in st.session_state:
            st.session_state["prompt_editing"] = False

        # Worker 타입 선택
        selected_worker = st.selectbox(
            "Worker 타입 선택",
            WORKER_TYPES,
            index=WORKER_TYPES.index(st.session_state["prompt_worker"]) if st.session_state["prompt_worker"] in WORKER_TYPES else 0,
            format_func=lambda x: f"{x} - {WORKER_DESCRIPTIONS.get(x, '')}",
            key="prompt_worker_select",
        )

        # Worker 선택이 변경되면 이전 결과 초기화
        if st.session_state["prompt_worker"] != selected_worker:
            st.session_state["prompt_result"] = None
            st.session_state["prompt_worker"] = selected_worker
            st.session_state["prompt_editing"] = False

        # 프롬프트 조회 및 초기화 버튼
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🔍 프롬프트 조회", key="prompt_get"):
                if not base_url:
                    st.error("사이드바에서 환경을 선택하세요.")
                else:
                    with st.spinner("프롬프트 조회 중..."):
                        try:
                            client = AxPromptApiClient(
                                base_url=base_url,
                                environment=env,
                                retention_token=bearer if bearer else None,
                                mrs_session=mrs if mrs else None,
                                cms_access_token=cms if cms else None,
                            )
                            result = client.get_prompt(selected_worker)
                            st.session_state["prompt_result"] = result
                            st.session_state["prompt_worker"] = selected_worker
                            st.session_state["prompt_editing"] = False
                            st.success("프롬프트 조회 완료!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"오류 발생: {str(e)}")

        with col_btn2:
            if st.button("🔄 프롬프트 초기화", key="prompt_reset"):
                if not base_url:
                    st.error("사이드바에서 환경을 선택하세요.")
                else:
                    with st.spinner("프롬프트 초기화 중..."):
                        try:
                            client = AxPromptApiClient(
                                base_url=base_url,
                                environment=env,
                                retention_token=bearer if bearer else None,
                                mrs_session=mrs if mrs else None,
                                cms_access_token=cms if cms else None,
                            )
                            result = client.reset_prompt(selected_worker)
                            before_len = safe_len(result.before)
                            after_len = safe_len(result.after)
                            st.success("프롬프트 초기화 완료!")
                            st.info(f"변경 전: {before_len}자 -> 변경 후: {after_len}자")
                            st.session_state["prompt_result"] = result
                            st.session_state["prompt_worker"] = selected_worker
                            st.session_state["prompt_editing"] = False
                            st.rerun()
                        except Exception as e:
                            st.error(f"오류 발생: {str(e)}")

        st.divider()

        # 프롬프트 조회 결과 표시
        if st.session_state["prompt_result"] is not None:
            result = st.session_state["prompt_result"]
            worker = st.session_state.get("prompt_worker", "Unknown")

            # 현재 선택된 Worker와 결과의 Worker가 일치하는지 확인
            if worker != selected_worker:
                st.info("Worker 타입을 선택하고 '프롬프트 조회' 버튼을 클릭하세요.")
            else:
                before_text = result.before if result.before is not None else ""
                after_text = result.after if result.after is not None else ""

                # 변경 전/현재 프롬프트를 2열로 표시
                st.markdown("### 프롬프트 비교")
                col_before, col_after = st.columns(2)

                with col_before:
                    st.markdown("#### 변경 전 프롬프트")
                    st.text_area(
                        "변경 전",
                        value=before_text,
                        height=400,
                        disabled=True,
                        key="prompt_before",
                    )
                    st.caption(f"길이: {safe_len(before_text)}자")

                with col_after:
                    st.markdown("#### 현재 프롬프트")
                    st.text_area(
                        "현재",
                        value=after_text,
                        height=400,
                        disabled=True,
                        key="prompt_after",
                    )
                    st.caption(f"길이: {safe_len(after_text)}자")

                st.divider()

                # 프롬프트 수정 섹션
                st.markdown("### 프롬프트 수정")

                # 수정 모드 토글 버튼
                if not st.session_state["prompt_editing"]:
                    if st.button("✏️ 프롬프트 수정 시작", key="prompt_edit_start"):
                        st.session_state["prompt_editing"] = True
                        st.rerun()
                else:
                    # 수정 영역
                    st.info("현재 프롬프트를 기반으로 수정하세요. 변경 사항은 저장 시 적용됩니다.")

                    new_prompt = st.text_area(
                        "새로운 프롬프트 입력",
                        value=after_text,
                        height=400,
                        help="프롬프트를 수정한 후 '프롬프트 업데이트' 버튼을 클릭하세요.",
                        key="prompt_new_input",
                    )

                    # 변경 사항 요약
                    if new_prompt != after_text:
                        diff_len = len(new_prompt) - len(after_text)
                        diff_sign = "+" if diff_len > 0 else ""
                        st.info(f"변경 사항: {len(after_text)}자 -> {len(new_prompt)}자 ({diff_sign}{diff_len}자)")

                    # 버튼 영역
                    col_save, col_cancel = st.columns(2)
                    with col_save:
                        if st.button("💾 프롬프트 업데이트", key="prompt_update"):
                            with st.spinner("프롬프트 업데이트 중..."):
                                try:
                                    client = AxPromptApiClient(
                                        base_url=base_url,
                                        environment=env,
                                        retention_token=bearer if bearer else None,
                                        mrs_session=mrs if mrs else None,
                                        cms_access_token=cms if cms else None,
                                    )
                                    update_result = client.update_prompt(worker, new_prompt)
                                    before_len = safe_len(update_result.before)
                                    after_len = safe_len(update_result.after)
                                    st.success("프롬프트 업데이트 완료!")
                                    st.info(f"변경 전: {before_len}자 -> 변경 후: {after_len}자")
                                    st.session_state["prompt_result"] = update_result
                                    st.session_state["prompt_editing"] = False
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"오류 발생: {str(e)}")

                    with col_cancel:
                        if st.button("❌ 수정 취소", key="prompt_cancel"):
                            st.session_state["prompt_editing"] = False
                            st.rerun()
        else:
            st.info("Worker 타입을 선택하고 '프롬프트 조회' 버튼을 클릭하세요.")


if __name__ == "__main__":
    main()
