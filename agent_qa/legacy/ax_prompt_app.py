"""
AX 프롬프트 관리 Streamlit 웹 애플리케이션

이 애플리케이션은 AX 프롬프트 API를 관리하고 테스트할 수 있는 웹 인터페이스를 제공합니다.
"""

import streamlit as st
from typing import Optional
from dotenv import load_dotenv

from curl_parsing import parse_curl_headers
from prompt_api import (
    AxPromptApiClient,
    PromptResponse,
    WorkerTestResponse,
    WORKER_TYPES,
    WORKER_DESCRIPTIONS,
    BASE_URL_DV,
    BASE_URL_QA,
    BASE_URL_ST,
    BASE_URL_PR,
    get_base_url,
    safe_len,
)

# 환경변수 로드
load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="AX 프롬프트 관리",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


def initialize_session_state():
    """세션 상태 초기화"""
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = None
    if "conversation_history" not in st.session_state:
        st.session_state.conversation_history = []
    if "selected_environment" not in st.session_state:
        st.session_state.selected_environment = "DV"
    if "retention_token" not in st.session_state:
        st.session_state.retention_token = ""
    if "cms_access_token" not in st.session_state:
        st.session_state.cms_access_token = ""
    if "mrs_session" not in st.session_state:
        st.session_state.mrs_session = ""
    if "selected_worker_for_prompt" not in st.session_state:
        st.session_state.selected_worker_for_prompt = WORKER_TYPES[0]
    if "selected_worker_for_test" not in st.session_state:
        st.session_state.selected_worker_for_test = WORKER_TYPES[0]
    if "editing_prompt" not in st.session_state:
        st.session_state.editing_prompt = False
    if "recruit_plan_id" not in st.session_state:
        st.session_state.recruit_plan_id = ""


def create_api_client(environment: str, retention_token: str, mrs_session: str, cms_access_token: str) -> Optional[AxPromptApiClient]:
    """API 클라이언트 생성"""
    base_url = get_base_url(environment)
    if not base_url:
        st.error(f"❌ {environment} 환경의 Base URL이 설정되지 않았습니다.")
        return None

    return AxPromptApiClient(
        base_url=base_url,
        environment=environment,
        retention_token=retention_token if retention_token else None,
        mrs_session=mrs_session if mrs_session else None,
        cms_access_token=cms_access_token if cms_access_token else None,
    )


def render_sidebar():
    """사이드바 렌더링 (LNB) - 환경 설정 및 토큰만 관리"""
    with st.sidebar:
        st.header("⚙️ 설정")

        # 환경 선택
        st.subheader("환경 선택")
        env_options = ["DV", "QA", "ST", "PR"]

        # 현재 선택된 환경의 인덱스 찾기 (없으면 기본값 0=DV)
        try:
            default_index = env_options.index(st.session_state.selected_environment)
        except ValueError:
            default_index = 0

        environment = st.radio(
            "배포 환경",
            env_options,
            index=default_index,
        )
        st.session_state.selected_environment = environment

        if environment == "PR" and BASE_URL_PR is None:
            st.warning("⚠️ PR 환경은 아직 준비되지 않았습니다.")

        st.markdown("---")

        # cURL 파싱 섹션
        st.subheader("cURL 파싱")
        curl_text = st.text_area(
            "cURL 붙여넣기",
            height=150,
            placeholder="브라우저에서 복사한 cURL 명령을 붙여넣으세요...",
            help="브라우저 개발자 도구에서 'Copy as cURL' 한 내용을 붙여넣으면 토큰이 자동으로 추출됩니다.",
            key="curl_input",
        )

        if st.button("🔍 토큰 추출", width='stretch', key="parse_curl"):
            if curl_text.strip():
                parsed = parse_curl_headers(curl_text)

                # authorization 헤더에서 Bearer 제거
                auth_value = parsed.get("authorization")
                if auth_value and auth_value.lower().startswith("bearer "):
                    auth_value = auth_value[7:]  # "Bearer " 제거

                # 파싱된 값으로 세션 상태 업데이트
                if auth_value:
                    st.session_state.retention_token = auth_value
                if parsed.get("cms-access-token"):
                    st.session_state.cms_access_token = parsed["cms-access-token"]
                if parsed.get("mrs-session"):
                    st.session_state.mrs_session = parsed["mrs-session"]

                # 결과 표시
                found_count = sum(1 for v in [auth_value, parsed.get("cms-access-token"), parsed.get("mrs-session")] if v)
                if found_count > 0:
                    st.success(f"✅ {found_count}개의 토큰이 추출되었습니다!")
                    st.rerun()
                else:
                    st.warning("⚠️ 토큰을 찾을 수 없습니다. cURL 형식을 확인해주세요.")
            else:
                st.warning("⚠️ cURL 내용을 붙여넣어주세요.")

        st.markdown("---")

        # 토큰 입력
        st.subheader("인증 토큰")
        
        retention_token = st.text_input(
            "Retention 토큰 (Bearer)",
            value=st.session_state.retention_token,
            type="password",
            help="Worker 테스트를 위해 필요한 Retention 토큰입니다.",
        )
        st.session_state.retention_token = retention_token
        
        cms_access_token = st.text_input(
            "CMS Access 토큰",
            value=st.session_state.cms_access_token,
            type="password",
            help="Worker 테스트를 위해 필요한 CMS Access 토큰입니다.",
        )
        st.session_state.cms_access_token = cms_access_token
        
        mrs_session = st.text_input(
            "Mrs 세션",
            value=st.session_state.mrs_session,
            type="password",
            help="Worker 테스트를 위해 필요한 Mrs 세션입니다.",
        )
        st.session_state.mrs_session = mrs_session
        
        return environment, retention_token, mrs_session, cms_access_token


def render_prompt_management_tab(environment: str, retention_token: str, mrs_session: str, cms_access_token: str):
    """프롬프트 관리 탭 렌더링"""
    # 프롬프트 관리용 Worker 선택 (최상단)
    st.markdown("### Worker 타입 선택")
    selected_worker = st.selectbox(
        "프롬프트를 관리할 Worker 타입",
        WORKER_TYPES,
        index=WORKER_TYPES.index(st.session_state.selected_worker_for_prompt) if st.session_state.selected_worker_for_prompt in WORKER_TYPES else 0,
        format_func=lambda x: f"{x} - {WORKER_DESCRIPTIONS.get(x, '')}",
        key="prompt_worker_select",
    )
    
    # Worker 선택이 변경되면 이전 결과 초기화
    if st.session_state.selected_worker_for_prompt != selected_worker:
        if "prompt_result" in st.session_state:
            del st.session_state.prompt_result
        st.session_state.selected_worker_for_prompt = selected_worker
        st.session_state.editing_prompt = False
    
    # 프롬프트 조회 및 초기화 버튼
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("🔍 프롬프트 조회", width='stretch'):
            with st.spinner("프롬프트 조회 중..."):
                try:
                    client = create_api_client(environment, retention_token, mrs_session, cms_access_token)
                    if client:
                        result = client.get_prompt(selected_worker)
                        
                        # 결과를 세션 상태에 저장
                        st.session_state.prompt_result = result
                        st.session_state.selected_worker_for_prompt = selected_worker
                        st.session_state.editing_prompt = False
                        
                        st.success("✅ 프롬프트 조회 완료!")
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ 오류 발생: {str(e)}")
    
    with col_btn2:
        if st.button("🔄 프롬프트 초기화", width='stretch'):
            with st.spinner("프롬프트 초기화 중..."):
                try:
                    client = create_api_client(environment, retention_token, mrs_session, cms_access_token)
                    if client:
                        result = client.reset_prompt(selected_worker)
                        before_len = safe_len(result.before)
                        after_len = safe_len(result.after)
                        st.success("✅ 프롬프트 초기화 완료!")
                        st.info(f"변경 전: {before_len}자 → 변경 후: {after_len}자")
                        
                        # 결과를 세션 상태에 저장
                        st.session_state.prompt_result = result
                        st.session_state.selected_worker_for_prompt = selected_worker
                        st.session_state.editing_prompt = False
                        st.rerun()
                except Exception as e:
                    st.error(f"❌ 오류 발생: {str(e)}")
    
    st.markdown("---")
    
    # 프롬프트 조회 결과 표시
    if "prompt_result" in st.session_state:
        result = st.session_state.prompt_result
        worker = st.session_state.get("selected_worker_for_prompt", "Unknown")
        
        # 현재 선택된 Worker와 결과의 Worker가 일치하는지 확인
        if worker != selected_worker:
            st.info("👆 위에서 Worker 타입을 선택하고 '프롬프트 조회' 버튼을 클릭하세요.")
        else:
            before_text = result.before if result.before is not None else ""
            after_text = result.after if result.after is not None else ""
            
            # 변경 전/현재 프롬프트를 2열로 표시
            st.markdown("### 프롬프트 비교")
            col_before, col_after = st.columns(2)
            
            with col_before:
                st.markdown("#### 📄 변경 전 프롬프트")
                st.text_area(
                    "변경 전 프롬프트",
                    value=before_text,
                    height=400,
                    disabled=True,
                    key="before_prompt",
                )
                st.caption(f"길이: {safe_len(before_text)}자")
            
            with col_after:
                st.markdown("#### 📄 현재 프롬프트")
                st.text_area(
                    "현재 프롬프트",
                    value=after_text,
                    height=400,
                    disabled=True,
                    key="after_prompt",
                )
                st.caption(f"길이: {safe_len(after_text)}자")
            
            st.markdown("---")
            
            # 프롬프트 수정 섹션
            st.markdown("### 프롬프트 수정")
            
            # 수정 모드 토글 버튼
            if not st.session_state.editing_prompt:
                if st.button("✏️ 프롬프트 수정 시작", width='stretch', key="start_edit"):
                    st.session_state.editing_prompt = True
                    st.rerun()
            else:
                # 수정 영역
                st.info("💡 현재 프롬프트를 기반으로 수정하세요. 변경 사항은 저장 시 적용됩니다.")
                
                new_prompt = st.text_area(
                    "새로운 프롬프트 입력",
                    value=after_text,
                    height=400,
                    help="프롬프트를 수정한 후 '프롬프트 업데이트' 버튼을 클릭하세요.",
                    key="new_prompt_input",
                )
                
                # 변경 사항 요약
                if new_prompt != after_text:
                    diff_len = len(new_prompt) - len(after_text)
                    diff_sign = "+" if diff_len > 0 else ""
                    st.info(f"📊 변경 사항: {len(after_text)}자 → {len(new_prompt)}자 ({diff_sign}{diff_len}자)")
                
                # 버튼 영역
                col_save, col_cancel = st.columns(2)
                with col_save:
                    if st.button("💾 프롬프트 업데이트", width='stretch', key="update_prompt"):
                        with st.spinner("프롬프트 업데이트 중..."):
                            try:
                                client = create_api_client(environment, retention_token, mrs_session, cms_access_token)
                                if client:
                                    update_result = client.update_prompt(worker, new_prompt)
                                    before_len = safe_len(update_result.before)
                                    after_len = safe_len(update_result.after)
                                    st.success("✅ 프롬프트 업데이트 완료!")
                                    st.info(f"변경 전: {before_len}자 → 변경 후: {after_len}자")
                                    
                                    # 세션 상태 업데이트
                                    st.session_state.prompt_result = update_result
                                    st.session_state.editing_prompt = False
                                    st.rerun()
                            except Exception as e:
                                st.error(f"❌ 오류 발생: {str(e)}")
                
                with col_cancel:
                    if st.button("❌ 수정 취소", width='stretch', key="cancel_edit"):
                        st.session_state.editing_prompt = False
                        st.rerun()
    else:
        st.info("👆 위에서 Worker 타입을 선택하고 '프롬프트 조회' 버튼을 클릭하세요.")


def render_worker_test_tab(environment: str, retention_token: str, mrs_session: str, cms_access_token: str):
    """Worker 테스트 탭 렌더링"""
    # Worker 테스트용 Worker 선택 (최상단)
    st.markdown("### Worker 타입 선택")
    test_worker_type = st.selectbox(
        "테스트할 Worker 타입",
        WORKER_TYPES,
        index=WORKER_TYPES.index(st.session_state.selected_worker_for_test) if st.session_state.selected_worker_for_test in WORKER_TYPES else 0,
        format_func=lambda x: f"{x} - {WORKER_DESCRIPTIONS.get(x, '')}",
        key="test_worker_select",
    )
    st.session_state.selected_worker_for_test = test_worker_type
    
    # 대화 초기화 버튼
    if st.button("🔄 대화 초기화", width='stretch', key="reset_conversation"):
        st.session_state.conversation_id = None
        st.session_state.conversation_history = []
        st.success("✅ 대화가 초기화되었습니다.")
        st.rerun()
    
    st.markdown("---")
    
    # Recruit Plan ID 입력 (테스트 시에만 사용)
    st.markdown("### 테스트 옵션 (선택사항)")
    recruit_plan_id = st.text_input(
        "Recruit Plan ID",
        value=st.session_state.recruit_plan_id,
        placeholder="채용 플랜 ID를 입력하세요 (선택사항)",
        help="테스트 시 특정 채용 플랜 ID를 지정하려면 입력하세요.",
        key="recruit_plan_id_input",
    )
    st.session_state.recruit_plan_id = recruit_plan_id
    
    st.markdown("---")
    
    # 대화 히스토리 표시
    if st.session_state.conversation_history:
        st.markdown("### 대화 히스토리")
        for i, (role, message) in enumerate(st.session_state.conversation_history):
            if role == "user":
                with st.chat_message("user"):
                    st.write(message)
            else:
                with st.chat_message("assistant"):
                    st.write(message)
        st.markdown("---")
    
    # 질문 입력
    user_question = st.text_area(
        "질문 입력",
        height=200,
        placeholder="Worker에게 질문할 내용을 입력하세요...",
        key="user_question_input",
    )
    
    # 질문 전송 버튼
    if st.button("📤 질문 전송", width='stretch', key="send_question"):
        if not user_question.strip():
            st.warning("⚠️ 질문을 입력해주세요.")
        elif not retention_token or not mrs_session or not cms_access_token:
            st.warning("⚠️ Worker 테스트를 위해서는 Retention 토큰, Mrs 세션, CMS Access 토큰이 필요합니다.")
        else:
            with st.spinner("Worker가 답변을 생성하는 중..."):
                try:
                    client = create_api_client(environment, retention_token, mrs_session, cms_access_token)
                    if client:
                        # Worker 테스트 API 호출
                        response = client.test_worker(
                            worker_type=test_worker_type,
                            user_message=user_question,
                            conversation_id=st.session_state.conversation_id,
                            recruit_plan_id=recruit_plan_id if recruit_plan_id.strip() else None,
                        )
                        
                        # 대화 히스토리에 추가
                        st.session_state.conversation_history.append(("user", user_question))
                        st.session_state.conversation_history.append(("assistant", response.answer))
                        
                        # Conversation ID 업데이트
                        st.session_state.conversation_id = response.conversation_id
                        
                        st.success("✅ 답변을 받았습니다!")
                        
                        # 결과 표시
                        st.markdown("### 최신 답변")
                        st.markdown("---")
                        
                        with st.container():
                            st.markdown(f"**Worker 타입:** `{test_worker_type}`")
                            st.markdown(f"**Conversation ID:** `{response.conversation_id}`")
                            st.markdown(f"**응답 시간:** `{response.response_time:.2f}초`")
                            st.markdown("---")
                            
                            st.markdown("**답변:**")
                            st.info(response.answer)
                        
                        # 페이지 새로고침하여 히스토리 업데이트
                        st.rerun()
                except ValueError as e:
                    st.error(f"❌ 토큰 오류: {str(e)}")
                except Exception as e:
                    st.error(f"❌ 오류 발생: {str(e)}")
    
    # 대화 히스토리 삭제 버튼
    if st.session_state.conversation_history:
        if st.button("🗑️ 대화 히스토리 삭제", width='stretch', key="clear_history"):
            st.session_state.conversation_id = None
            st.session_state.conversation_history = []
            st.success("✅ 대화 히스토리가 삭제되었습니다.")
            st.rerun()


def main():
    """메인 애플리케이션"""
    initialize_session_state()
    
    # 제목
    st.title("🤖 AX 프롬프트 관리 시스템")
    st.markdown("---")
    
    # 사이드바 렌더링 (환경 설정 및 토큰만)
    environment, retention_token, mrs_session, cms_access_token = render_sidebar()
    
    # 탭으로 구분
    tab1, tab2 = st.tabs(["📝 프롬프트 관리", "💬 Worker 테스트"])
    
    with tab1:
        render_prompt_management_tab(environment, retention_token, mrs_session, cms_access_token)
    
    with tab2:
        render_worker_test_tab(environment, retention_token, mrs_session, cms_access_token)


if __name__ == "__main__":
    main()
