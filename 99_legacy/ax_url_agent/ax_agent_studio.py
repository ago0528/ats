import streamlit as st
import pandas as pd
import time
import os
import json
from dataclasses import asdict
from pathlib import Path
import re

# ax_url_agent.py가 같은 디렉토리에 있다고 가정하고 임포트
# 실제 운영 시에는 패키지 구조에 맞춰 조정 필요
try:
    # 기존 `ax_url_agent.py`가 인코딩/문자 손상으로 SyntaxError를 유발할 수 있어,
    # Studio에서는 "정상 UTF-8" 모듈인 `ax_url_agent_clean.py`를 기본으로 사용한다.
    from ax_url_agent_clean import AXNavigationPipeline, NavigationPipelineResponse
except ImportError:
    st.error("ax_url_agent.py 파일을 찾을 수 없습니다. 같은 디렉토리에 위치시켜 주세요.")
    st.stop()

# 채팅 UX 보조 모듈 (같은 디렉토리에 위치)
try:
    from chat_storage_jsonl import JSONLChatStore, ChatMessageRecord, ChatSummaryRecord
    from chat_memory_langchain import build_conversation_history_text, build_orchestrator_history_text, dataclass_to_dict
    from chat_llm_utils import condense_to_standalone_query, summarize_conversation_memory
except ImportError:
    JSONLChatStore = None  # type: ignore[assignment]
    ChatMessageRecord = None  # type: ignore[assignment]
    ChatSummaryRecord = None  # type: ignore[assignment]
    build_conversation_history_text = None  # type: ignore[assignment]
    build_orchestrator_history_text = None  # type: ignore[assignment]
    dataclass_to_dict = None  # type: ignore[assignment]
    condense_to_standalone_query = None  # type: ignore[assignment]
    summarize_conversation_memory = None  # type: ignore[assignment]

# 페이지 기본 설정
st.set_page_config(
    page_title="AX Agent Eval Studio",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 스타일 커스터마이징
st.markdown("""
<style>
    .stProgress .st-bo {
        background-color: #00c0f2;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        text-align: center;
    }
    .status-ok { color: green; font-weight: bold; }
    .status-error { color: red; font-weight: bold; }
    .status-warning { color: orange; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# 사이드바 설정 (LNB)
with st.sidebar:
    st.title("🧪 AX Agent Studio")
    st.caption("v1.0.0 | Orchestrator & URL/WIKI Agent")
    
    st.divider()
    
    # 1. 모델 및 환경 설정
    st.subheader("⚙️ 환경 설정")
    
    # API Key 설정 (환경변수 없으면 입력받기)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        api_key = st.text_input("OpenAI API Key", type="password")
        if not api_key:
            st.warning("API Key가 필요합니다.")
            st.stop()
    
    model_name = st.selectbox(
        "사용 모델",
        ["gpt-5.2", "gpt-5.1", "gpt-5.1-mini"],
        index=0
    )
    
    plan_id = st.text_input("Plan ID (Test용)", value="12345")
    
    st.divider()
    
    # 2. 실행 옵션
    st.subheader("🚀 실행 옵션")
    direct_url_agent = st.checkbox("Orchestrator 생략 (URL Agent 직접 호출)", value=False)
    verbose_mode = st.checkbox("상세 로그 표시", value=True)

    st.divider()
    st.info("💡 팁: '프롬프트' 탭에서 실시간으로 프롬프트를 수정하고 테스트할 수 있습니다.")

# 메인 타이틀
st.title("AX Agent Evaluation Studio")
st.markdown("Orchestrator 및 URL/WIKI Agent의 **응답 품질**과 **Latency**를 추적하고 분석합니다.")

# 탭 구성
tab_exec, tab_analytics, tab_prompt, tab_chat = st.tabs(["📊 실행 및 결과", "📈 성능 분석", "📝 프롬프트 튜닝", "💬 채팅"])

# -----------------------------------------------------------------------------
# 1. 실행 및 결과 탭
# -----------------------------------------------------------------------------
with tab_exec:
    col_input, col_result = st.columns([1, 1.5])
    
    # [Left] 입력 및 설정
    with col_input:
        st.subheader("1. 질의 입력")
        
        input_method = st.radio("입력 방식", ["직접 입력", "파일 업로드 (.txt, .md)"])
        
        queries = []
        
        if input_method == "직접 입력":
            user_input = st.text_area("테스트할 질의 입력 (한 줄에 하나씩)", height=200, 
                                    placeholder="채용 만들고 싶어\n지원자 보여줘\n...")
            if user_input:
                queries = [line.strip() for line in user_input.split('\n') if line.strip()]
                
        else: # 파일 업로드
            uploaded_file = st.file_uploader("테스트 파일 업로드", type=["txt", "md"])
            if uploaded_file:
                content = uploaded_file.read().decode("utf-8")
                
                if uploaded_file.name.endswith(".md"):
                    # MD 파일 파싱 (표 형태 가정)
                    for line in content.splitlines():
                        if re.match(r'^\| \d+ \|', line):
                            parts = line.split('|')
                            if len(parts) > 3:
                                queries.append(parts[3].strip())
                    st.success(f"Markdown 표에서 {len(queries)}개의 질의를 추출했습니다.")
                else:
                    # TXT 파일 파싱
                    queries = [line.strip() for line in content.splitlines() if line.strip()]
                    st.success(f"텍스트 파일에서 {len(queries)}개의 질의를 추출했습니다.")
        
        st.divider()
        
        # 실행 버튼
        run_btn = st.button("테스트 실행", type="primary", disabled=len(queries) == 0, width='stretch')
    
    # [Right] 실행 결과 실시간 표시
    with col_result:
        st.subheader("2. 실행 결과")
        
        if "results" not in st.session_state:
            st.session_state.results = []
            
        result_container = st.container()
        
        if run_btn:
            st.session_state.results = [] # 초기화
            pipeline = AXNavigationPipeline(api_key=api_key, model=model_name)
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            total_queries = len(queries)
            
            for i, query in enumerate(queries):
                status_text.text(f"[{i+1}/{total_queries}] 분석 중: {query[:30]}...")
                
                # 에이전트 호출
                try:
                    res = pipeline.recommend(
                        query=query,
                        plan_id=plan_id,
                        direct_url_agent=direct_url_agent
                    )
                    st.session_state.results.append(res)
                except Exception as e:
                    st.error(f"Error processing '{query}': {str(e)}")
                
                # 진행률 업데이트
                progress_bar.progress((i + 1) / total_queries)
                
            status_text.text("분석 완료!")
            st.success(f"총 {total_queries}개 질의 분석 완료")
        
        # 결과 렌더링 (데이터프레임 변환)
        if st.session_state.results:
            data = []
            for r in st.session_state.results:
                
                # planId 표시 로직 (ax_url_agent.py와 동기화)
                plan_id_display = "-"
                # 기존 requires_plan_id 대신 plan_id_required 사용
                # NavigationPipelineResponse 객체가 최신 상태인지 확인 필요
                # 만약 객체 속성명이 아직 업데이트 안 된 구버전 패키지를 쓰고 있다면 에러 날 수 있음
                # 하지만 로컬 파일 import이므로 괜찮음.
                
                # 안전하게 속성 존재 여부 체크 (호환성)
                is_required = getattr(r, 'plan_id_required', getattr(r, 'requires_plan_id', False))
                pid_val = getattr(r, 'plan_id', None)
                
                if is_required:
                    plan_id_display = str(pid_val) if pid_val else "필요(미입력)"
                
                # WIKI Agent 필드 (호환성 고려: getattr 사용)
                wiki_analyzed_q = getattr(r, "wiki_analyzed_query", None)
                wiki_analyzed_tag = getattr(r, "wiki_analyzed_tag", None)
                wiki_results_count = getattr(r, "wiki_search_results_count", None)
                wiki_answer = getattr(r, "wiki_answer", None) or ""
                wiki_answer_short = wiki_answer[:100] + "..." if len(wiki_answer) > 100 else (wiki_answer or "-")

                wiki_qa_latency = float(getattr(r, "wiki_query_analyzer_latency", 0.0) or 0.0)
                wiki_search_latency = float(getattr(r, "wiki_search_api_latency", 0.0) or 0.0)
                wiki_synth_latency = float(getattr(r, "wiki_synthesizer_latency", 0.0) or 0.0)
                wiki_total_latency = float(getattr(r, "wiki_agent_latency", 0.0) or 0.0)

                data.append({
                    "Query": r.query,
                    "Agent": r.selected_agent_id,
                    "URL": r.url,
                    "PlanID": plan_id_display,
                    "Latency (Total)": f"{r.total_latency:.2f}s",
                    "Orch Latency": f"{r.orchestrator_latency:.2f}s",
                    "URL Latency": f"{r.url_agent_latency:.2f}s",
                    "WIKI Latency": f"{wiki_total_latency:.2f}s" if r.selected_agent_id == "RECRUIT_WIKI_WORKER" else "-",
                    "WIKI QA Latency": f"{wiki_qa_latency:.2f}s" if r.selected_agent_id == "RECRUIT_WIKI_WORKER" else "-",
                    "WIKI Search Latency": f"{wiki_search_latency:.2f}s" if r.selected_agent_id == "RECRUIT_WIKI_WORKER" else "-",
                    "WIKI Synth Latency": f"{wiki_synth_latency:.2f}s" if r.selected_agent_id == "RECRUIT_WIKI_WORKER" else "-",
                    "WIKI q": wiki_analyzed_q if wiki_analyzed_q else ("-" if r.selected_agent_id != "RECRUIT_WIKI_WORKER" else ""),
                    "WIKI tag": wiki_analyzed_tag if wiki_analyzed_tag else ("-" if r.selected_agent_id != "RECRUIT_WIKI_WORKER" else ""),
                    "WIKI results": str(wiki_results_count) if wiki_results_count is not None else ("-" if r.selected_agent_id != "RECRUIT_WIKI_WORKER" else ""),
                    "WIKI answer": wiki_answer_short if r.selected_agent_id == "RECRUIT_WIKI_WORKER" else "-",
                    "Reason": f"{r.orchestrator_reason} / {r.url_reason}" if r.selected_agent_id == "URL_WORKER" else r.orchestrator_reason,
                    "Error": r.error if r.error else "-"
                })
            
            df = pd.DataFrame(data)
            
            # 요약 메트릭 표시
            m1, m2, m3 = st.columns(3)
            # 문자열 "0.12s" 에서 "s" 제거 후 float 변환
            avg_latency = 0.0
            if not df.empty:
                avg_latency = df["Latency (Total)"].str.replace("s", "").astype(float).mean()
            
            error_count = df[df["Error"] != "-"].shape[0]
            
            m1.metric("평균 응답 시간", f"{avg_latency:.2f}s")
            m2.metric("총 실행 수", len(df))
            m3.metric("에러 발생", error_count, delta_color="inverse")
            
            # 상세 테이블
            st.dataframe(df, width='stretch', height=500)

            # 상세 결과 (선택 사항)
            if verbose_mode:
                st.divider()
                st.subheader("3. 상세 결과")
                for idx, r in enumerate(st.session_state.results, 1):
                    header = f"[{idx}] {r.selected_agent_id} | {r.query}"
                    with st.expander(header, expanded=False):
                        if r.error:
                            st.error(r.error)
                            continue

                        st.caption(f"Orchestrator Reason: {r.orchestrator_reason}")

                        if r.selected_agent_id == "URL_WORKER":
                            st.write(f"Matched Name: {r.matched_name}")
                            st.write(f"URL: {r.url}")
                            st.write(f"URL Reason: {r.url_reason}")

                        if r.selected_agent_id == "RECRUIT_WIKI_WORKER":
                            wiki_docs = getattr(r, "wiki_documents", None) or []
                            wiki_answer_full = (getattr(r, "wiki_answer", None) or "").replace("/n", "\n")
                            wiki_req_url = getattr(r, "wiki_search_api_request_url", None)
                            wiki_req_params = getattr(r, "wiki_search_api_request_params", None)
                            wiki_raw = getattr(r, "wiki_search_api_response_raw", None)

                            st.write(f"Analyzed q: {getattr(r, 'wiki_analyzed_query', '')}")
                            st.write(f"Analyzed tag: {getattr(r, 'wiki_analyzed_tag', '')}")

                            st.subheader("Search API 추적")
                            if wiki_req_url:
                                st.write(f"Request URL: {wiki_req_url}")
                            if isinstance(wiki_req_params, dict):
                                st.write("Request Params:")
                                st.json(wiki_req_params)

                            show_raw = st.checkbox(
                                "Search API 원본 Response(JSON) 표시(용량 큼)",
                                value=False,
                                key=f"show_wiki_raw_{idx}",
                            )
                            if show_raw:
                                if isinstance(wiki_raw, dict):
                                    st.json(wiki_raw)
                                else:
                                    st.info("원본 Response를 찾을 수 없습니다.")

                            st.subheader("답변")
                            st.text(wiki_answer_full if wiki_answer_full else "(답변 없음)")

                            st.subheader("검색 문서")
                            if wiki_docs:
                                docs_rows = []
                                for d in wiki_docs:
                                    docs_rows.append({
                                        "title": d.get("title"),
                                        "score": d.get("score"),
                                        "url": d.get("url"),
                                        "tags": ", ".join(d.get("tags", [])) if isinstance(d.get("tags"), list) else d.get("tags"),
                                    })
                                st.dataframe(pd.DataFrame(docs_rows), width='stretch', height=240)
                            else:
                                st.info("검색된 문서가 없습니다.")
            
            # 다운로드 버튼
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                "결과 CSV 다운로드",
                csv,
                "ax_agent_results.csv",
                "text/csv",
                key='download-csv'
            )

# -----------------------------------------------------------------------------
# 2. 성능 분석 탭
# -----------------------------------------------------------------------------
with tab_analytics:
    st.header("📈 성능 및 품질 분석")
    
    if not st.session_state.results:
        st.info("먼저 '실행 및 결과' 탭에서 테스트를 실행해주세요.")
    else:
        df = pd.DataFrame([
            {
                "Agent": r.selected_agent_id, 
                "Latency": r.total_latency,
                "HasError": bool(r.error)
            } for r in st.session_state.results
        ])
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("에이전트 선택 분포")
            if not df.empty:
                agent_counts = df["Agent"].value_counts()
                st.bar_chart(agent_counts)
            
        with col2:
            st.subheader("응답 시간 분포 (Histogram)")
            if not df.empty:
                st.bar_chart(df["Latency"])

        st.divider()
        st.subheader("Slow Queries (Top 5)")
        
        if not df.empty:
            # 느린 순서대로 정렬
            slow_queries = pd.DataFrame([
                {"Query": r.query, "Latency": r.total_latency, "Agent": r.selected_agent_id}
                for r in st.session_state.results
            ]).sort_values("Latency", ascending=False).head(5)
            
            st.table(slow_queries)

# -----------------------------------------------------------------------------
# 3. 프롬프트 튜닝 탭
# -----------------------------------------------------------------------------
with tab_prompt:
    st.header("📝 프롬프트 엔지니어링 샌드박스")
    
    current_dir = Path(__file__).parent
    prompt_root_dir = current_dir.parent / "prompt" / "nmrs_v14.1.0"

    prompt_orch_path = prompt_root_dir / "prompt_orchestrator_worker.md"
    prompt_url_path = prompt_root_dir / "prompt_url_worker.md"
    prompt_wiki_analyzer_path = prompt_root_dir / "prompt_wiki_worker_query_analyzer.md"
    prompt_wiki_synth_path = prompt_root_dir / "prompt_wiki_worker_synthesizer.md"

    col_p1, col_p2 = st.columns(2)
    
    with col_p1:
        st.subheader("Orchestrator Prompt")
        if prompt_orch_path.exists():
            orch_content = prompt_orch_path.read_text(encoding="utf-8")
            new_orch_content = st.text_area("편집", orch_content, height=400, key="orch_edit")
            if st.button("Orchestrator 저장", key="save_orch"):
                prompt_orch_path.write_text(new_orch_content, encoding="utf-8")
                st.success("저장되었습니다!")
        else:
            st.error("prompt_orchestrator_worker.md 파일을 찾을 수 없습니다.")

    with col_p2:
        st.subheader("URL Agent Prompt")
        if prompt_url_path.exists():
            url_content = prompt_url_path.read_text(encoding="utf-8")
            new_url_content = st.text_area("편집", url_content, height=400, key="url_edit")
            if st.button("URL Agent 저장", key="save_url"):
                prompt_url_path.write_text(new_url_content, encoding="utf-8")
                st.success("저장되었습니다!")
        else:
            st.error("prompt_url_worker.md 파일을 찾을 수 없습니다.")

    st.divider()
    col_p3, col_p4 = st.columns(2)

    with col_p3:
        st.subheader("WIKI Query Analyzer Prompt")
        if prompt_wiki_analyzer_path.exists():
            analyzer_content = prompt_wiki_analyzer_path.read_text(encoding="utf-8")
            new_analyzer_content = st.text_area("편집", analyzer_content, height=400, key="wiki_analyzer_edit")
            if st.button("WIKI Query Analyzer 저장", key="save_wiki_analyzer"):
                prompt_wiki_analyzer_path.write_text(new_analyzer_content, encoding="utf-8")
                st.success("저장되었습니다!")
        else:
            st.error("prompt_wiki_worker_query_analyzer.md 파일을 찾을 수 없습니다.")

    with col_p4:
        st.subheader("WIKI Synthesizer Prompt")
        if prompt_wiki_synth_path.exists():
            synth_content = prompt_wiki_synth_path.read_text(encoding="utf-8")
            new_synth_content = st.text_area("편집", synth_content, height=400, key="wiki_synth_edit")
            if st.button("WIKI Synthesizer 저장", key="save_wiki_synth"):
                prompt_wiki_synth_path.write_text(new_synth_content, encoding="utf-8")
                st.success("저장되었습니다!")
        else:
            st.error("prompt_wiki_worker_synthesizer.md 파일을 찾을 수 없습니다.")

# -----------------------------------------------------------------------------
# 4. 채팅 탭 (사용자 관점 UX 테스트)
# -----------------------------------------------------------------------------
with tab_chat:
    st.header("💬 채팅 UX 테스트")
    st.caption("대화 맥락(메모리)을 유지하며 AX Agent를 사용자 관점에서 테스트합니다.")

    if JSONLChatStore is None:
        st.error("채팅 모듈을 불러올 수 없습니다. chat_storage_jsonl.py 등이 같은 디렉토리에 있는지 확인해주세요.")
        st.stop()

    current_dir = Path(__file__).parent
    chat_root_dir = current_dir / ".chat_history"
    store = JSONLChatStore(chat_root_dir)

    # -----------------------------
    # 세션 상태 초기화
    # -----------------------------
    if "chat_conversation_id" not in st.session_state:
        existing = store.list_conversations()
        st.session_state.chat_conversation_id = existing[0] if existing else store.new_conversation_id()

    if "chat_messages" not in st.session_state:
        st.session_state.chat_messages = []

    if "chat_summary" not in st.session_state:
        st.session_state.chat_summary = None

    # -----------------------------
    # 대화방 컨트롤 + 설정
    # -----------------------------
    col_ctrl, col_chat = st.columns([1, 1.6])

    with col_ctrl:
        st.subheader("대화방")

        conversations = store.list_conversations()
        # 아직 저장된 대화가 하나도 없는 경우에도 선택 UI가 동작해야 한다.
        if st.session_state.chat_conversation_id not in conversations:
            conversations = [st.session_state.chat_conversation_id] + conversations

        selected = st.selectbox(
            "선택",
            options=conversations,
            index=conversations.index(st.session_state.chat_conversation_id) if st.session_state.chat_conversation_id in conversations else 0,
            key="chat_conversation_select",
        )

        def _load_conversation(conversation_id: str) -> None:
            msgs, summ = store.load_messages(conversation_id)
            st.session_state.chat_conversation_id = conversation_id
            st.session_state.chat_messages = msgs
            st.session_state.chat_summary = summ

        if selected != st.session_state.chat_conversation_id:
            _load_conversation(selected)

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("새 대화", width='stretch'):
                new_id = store.new_conversation_id()
                _load_conversation(new_id)
                st.rerun()

        with col_btn2:
            confirm_delete = st.checkbox("삭제 확인", value=False, key="chat_confirm_delete")
            if st.button("삭제", width='stretch', disabled=not confirm_delete):
                store.delete_conversation(st.session_state.chat_conversation_id)
                # 삭제 후에는 가장 최신 대화로 이동
                remaining = store.list_conversations()
                fallback = remaining[0] if remaining else store.new_conversation_id()
                _load_conversation(fallback)
                st.rerun()

        st.divider()

        st.subheader("메모리/디버그")
        debug_mode = st.checkbox("디버그 표시", value=True, key="chat_debug_mode")
        max_history_messages = st.slider("히스토리 메시지 수", min_value=4, max_value=40, value=12, step=2)
        auto_summary = st.checkbox("자동 요약(메모리) 업데이트", value=False, key="chat_auto_summary")
        summary_trigger_messages = st.slider("요약 트리거(메시지 수)", min_value=10, max_value=80, value=24, step=2)

        if st.session_state.chat_summary and st.session_state.chat_summary.content:
            st.text_area("현재 요약", st.session_state.chat_summary.content, height=160, key="chat_summary_view", disabled=True)
        else:
            st.caption("요약이 없다. 자동 요약을 켜거나 대화를 충분히 진행하면 생성할 수 있다.")

        # JSONL 다운로드
        conv_path = store.get_conversation_file_path(st.session_state.chat_conversation_id)
        if conv_path.exists():
            st.download_button(
                "대화 JSONL 다운로드",
                data=conv_path.read_bytes(),
                file_name=f"{st.session_state.chat_conversation_id}.jsonl",
                mime="application/jsonl",
                width='stretch',
            )

    # -----------------------------
    # 채팅 UI
    # -----------------------------
    with col_chat:
        st.subheader("채팅")

        # 메시지 렌더링
        for m in st.session_state.chat_messages:
            role = (m.role or "assistant").strip().lower()
            if role not in ["user", "assistant"]:
                # system 등은 채팅 로그에서 숨긴다(혼란 방지). 필요하면 디버그에서 확인한다.
                continue

            with st.chat_message(role):
                st.markdown(m.content)
                if debug_mode and role == "assistant":
                    meta = getattr(m, "meta", None) or {}
                    if isinstance(meta, dict) and meta:
                        with st.expander("디버그", expanded=False):
                            st.json(meta)

        # 입력
        user_input = st.chat_input("메시지를 입력하세요")
        if user_input:
            pipeline = AXNavigationPipeline(api_key=api_key, model=model_name)

            # 현재 대화의 히스토리를 구성한다.
            history_text = build_conversation_history_text(
                messages=st.session_state.chat_messages,
                summary=st.session_state.chat_summary,
                max_messages=max_history_messages,
                include_system=False,
            )

            # Orchestrator에는 '라우팅 친화' 히스토리를 전달한다.
            orchestrator_history_text = build_orchestrator_history_text(
                messages=st.session_state.chat_messages,
                summary=st.session_state.chat_summary,
                max_messages=max(max_history_messages, 12),
                include_system=False,
            )

            # 단독 질의 재구성
            condense_res = condense_to_standalone_query(
                api_key=api_key,
                model=model_name,
                history_text=history_text,
                user_input=user_input,
            )
            standalone_query = condense_res.text

            # 사용자 메시지 저장(원본)
            user_record = ChatMessageRecord(
                conversation_id=st.session_state.chat_conversation_id,
                role="user",
                content=user_input,
                ts=time.time(),
                meta={
                    "standalone_query": standalone_query,
                    "condense_latency_s": condense_res.latency_s,
                    "condense_error": condense_res.error,
                },
            )
            store.append_message(user_record)
            st.session_state.chat_messages.append(user_record)

            # 파이프라인 호출 (recommend는 query를 별도로 받으므로 conversation_history에는 직전 히스토리만 전달한다)
            try:
                res = pipeline.recommend(
                    query=standalone_query,
                    plan_id=plan_id,
                    conversation_history=orchestrator_history_text,
                    direct_url_agent=direct_url_agent,
                )
            except Exception as e:
                # 예외는 사용자 친화적으로 표시하고, 대화는 이어지도록 한다.
                res = NavigationPipelineResponse(
                    query=standalone_query,
                    selected_agent_id="NONE",
                    orchestrator_reason="",
                    url="",
                    url_reason="",
                    matched_name="",
                    plan_id_required=False,
                    plan_id=None,
                    error=f"Pipeline 호출 오류: {str(e)}",
                    total_latency=0.0,
                    orchestrator_latency=0.0,
                    url_agent_latency=0.0,
                )

            # 사용자 관점 답변 텍스트 구성
            if getattr(res, "error", None):
                assistant_text = f"요청 처리 중 오류가 발생했다.\n\n- 오류: {res.error}"
            elif res.selected_agent_id == "URL_WORKER":
                pid_hint = ""
                if getattr(res, "plan_id_required", False):
                    pid_hint = f"\n\n- planId: {res.plan_id if res.plan_id else '필요(미입력)'}"
                assistant_text = (
                    "이동할 페이지를 찾았다.\n\n"
                    f"- URL: {res.url}\n"
                    f"- 기능: {res.matched_name}\n"
                    f"- 이유: {res.url_reason}{pid_hint}"
                )
            elif res.selected_agent_id == "RECRUIT_WIKI_WORKER":
                answer = getattr(res, "wiki_answer", None) or ""
                assistant_text = answer.strip() if answer.strip() else "관련 문서를 찾았지만 답변을 생성하지 못했다."
            else:
                # URL 추천이 아닌 경우에도 사용자가 다음 행동을 알 수 있어야 한다.
                assistant_text = (
                    "요청을 처리할 워커를 선택했다.\n\n"
                    f"- 선택: {res.selected_agent_id}\n"
                    f"- 이유: {res.orchestrator_reason if res.orchestrator_reason else '(없음)'}\n\n"
                    "현재 스튜디오에서는 URL/WIKI 응답만 직접 실행한다."
                )

            assistant_meta = {
                "selected_agent_id": res.selected_agent_id,
                "standalone_query": standalone_query,
                "history_text_sent_to_orchestrator": orchestrator_history_text,
                "latency_s": {
                    "total": getattr(res, "total_latency", 0.0),
                    "orchestrator": getattr(res, "orchestrator_latency", 0.0),
                    "url_agent": getattr(res, "url_agent_latency", 0.0),
                    "wiki_agent": getattr(res, "wiki_agent_latency", 0.0),
                },
                "reason": {
                    "orchestrator": getattr(res, "orchestrator_reason", ""),
                    "url": getattr(res, "url_reason", ""),
                },
                "url": getattr(res, "url", ""),
                "matched_name": getattr(res, "matched_name", ""),
                "plan_id_required": getattr(res, "plan_id_required", False),
                "plan_id": getattr(res, "plan_id", None),
                "raw_response": dataclass_to_dict(res),
            }

            assistant_record = ChatMessageRecord(
                conversation_id=st.session_state.chat_conversation_id,
                role="assistant",
                content=assistant_text,
                ts=time.time(),
                meta=assistant_meta,
            )
            store.append_message(assistant_record)
            st.session_state.chat_messages.append(assistant_record)

            # 자동 요약 업데이트(선택)
            if auto_summary and len(st.session_state.chat_messages) >= summary_trigger_messages:
                # 요약은 긴 히스토리를 압축하기 위한 목적이므로, 전체 히스토리를 기반으로 갱신한다.
                full_history_text = build_conversation_history_text(
                    messages=st.session_state.chat_messages,
                    summary=None,
                    max_messages=9999,
                    include_system=False,
                )
                existing_summary = st.session_state.chat_summary.content if st.session_state.chat_summary else ""
                summ_res = summarize_conversation_memory(
                    api_key=api_key,
                    model=model_name,
                    existing_summary=existing_summary,
                    history_text=full_history_text,
                )
                summary_record = ChatSummaryRecord(
                    conversation_id=st.session_state.chat_conversation_id,
                    content=summ_res.text,
                    ts=time.time(),
                    meta={
                        "summary_latency_s": summ_res.latency_s,
                        "summary_error": summ_res.error,
                    },
                )
                store.upsert_summary(summary_record)
                st.session_state.chat_summary = summary_record

            st.rerun()
