# src/ats/ax/test/langgraph_sample/agent_flow_prototype.py
"""
LangGraph를 사용한 Agent Flow 프로토타입 (GPT-4 버전)

⚠️ GPT-5 모델을 사용하려면 agent_flow_gpt5_direct.py를 사용하세요!

특징:
- OpenAI GPT-4o-mini 모델 사용 (안정적)
- 진행 상황 실시간 보고 (report_progress tool)
- 과거 대화 검색 및 문서 읽기 기능
- 상태 관리 및 도구 실행 추적
- LangChain 완전 통합

설치 필요 패키지:
pip install langgraph langchain-openai langchain-core python-dotenv

환경 변수:
OPENAI_API_KEY=your-api-key-here
"""

import operator
import os
from typing import TypedDict, Annotated, Sequence, List, Dict, Any, Union

# LangGraph 및 LangChain 관련 라이브러리 임포트
try:
    from langgraph.graph import StateGraph, END
    from langgraph.prebuilt import ToolNode
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage
    from langchain_core.tools import tool
    from dotenv import load_dotenv
except ImportError as e:
    print("❌ 필수 라이브러리가 설치되지 않았습니다.")
    print(f"오류: {e}")
    print("다음 명령어로 설치해주세요: pip install langgraph langchain-openai langchain-core python-dotenv")
    exit(1)

# 환경 변수 로드 (.env 파일에서 OPENAI_API_KEY 등을 로드)
load_dotenv()

# ==============================================================================
# 1. State 정의 (작업 진행 상황 포함)
# ==============================================================================
class AgentState(TypedDict):
    """
    Agent의 전체 상태를 관리하는 타입 정의입니다.
    messages: 대화 히스토리 (Human, AI, Tool 메시지 등)
    progress_log: 작업 진행 상황 로그 (report_progress 도구에 의해 기록됨)
    user_request: 사용자의 원본 요청 (진행 상황 메시지 생성 시 사용)
    """
    # operator.add는 리스트를 이어붙이는 리듀서 역할을 합니다.
    messages: Annotated[Sequence[BaseMessage], operator.add]
    progress_log: Annotated[List[Dict[str, Any]], operator.add]
    user_request: str

# ==============================================================================
# 2. Tools 정의
# ==============================================================================

# 정적 매핑 폴백 전략 (LLM 생성 실패 시 사용)
STATIC_PROGRESS_MAPPING = {
    "search_conversations": {
        "title": "과거 대화 검색 중",
        "description": "관련된 과거 대화 내역을 검색하고 있습니다."
    },
    "read_document": {
        "title": "문서 읽는 중",
        "description": "요청하신 문서를 읽고 있습니다."
    },
    "default": {
        "title": "작업 진행 중",
        "description": "요청하신 작업을 수행하고 있습니다."
    }
}

def _generate_progress_message(
    user_request: str,
    tool_name: str,
    tool_description: str,
    tool_params: Dict[str, Any]
) -> Dict[str, str]:
    """
    LLM을 사용하여 진행 상황 메시지(title, description)를 동적으로 생성합니다.
    생성 실패 시 정적 매핑을 사용합니다.
    
    Args:
        user_request: 사용자의 원본 요청
        tool_name: 호출된 툴 이름
        tool_description: 툴 설명
        tool_params: 툴 파라미터
    
    Returns:
        Dict[str, str]: title과 description을 포함한 딕셔너리
    """
    try:
        # LLM을 사용하여 동적 생성
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0
        )
        
        prompt = f"""## Role
사용자에게 현재 AI Agent의 작업 진행 상황을 설명하는 메시지를 생성합니다.

## Input
- 사용자 요청: {user_request}
- 호출 툴: {tool_name}
- 툴 설명: {tool_description}
- 툴 파라미터: {tool_params}

## Output Format
title: [작업 단계를 나타내는 명사형 제목, 15자 내외]
description: [현재 수행 중인 작업을 1~3문장으로 설명. tool_params의 구체적 값을 자연스럽게 포함]

## Guidelines
- title은 "~중", "~ 확인" 형태의 명사형
- description은 "~하고 있습니다" 형태
- tool_params에 있는 키워드, ID, 이름 등을 description에 자연스럽게 녹여서 구체성 확보
- 기술 용어는 사용자 친화적으로 변환 (예: "url_tracker" → "제공할 페이지 찾는 중")

다음 형식으로만 응답하세요:
title: [제목]
description: [설명]"""
        
        response = llm.invoke(prompt)
        content = response.content
        
        # 응답 파싱
        lines = content.strip().split('\n')
        title = ""
        description = ""
        
        for line in lines:
            if line.startswith('title:'):
                title = line.replace('title:', '').strip()
            elif line.startswith('description:'):
                description = line.replace('description:', '').strip()
        
        if title and description:
            return {
                "title": title,
                "description": description
            }
    except Exception as e:
        print(f"⚠️ LLM 진행 상황 메시지 생성 실패, 폴백 사용: {e}")
    
    # 폴백: 정적 매핑 사용
    mapping = STATIC_PROGRESS_MAPPING.get(tool_name, STATIC_PROGRESS_MAPPING["default"])
    return {
        "title": mapping["title"],
        "description": mapping["description"]
    }

@tool
def report_progress(
    user_request: str,
    tool_name: str,
    tool_description: str,
    tool_params: Dict[str, Any]
) -> str:
    """
    작업 진행 상황을 사용자에게 보고합니다.
    Agent는 중요한 단계마다 이 도구를 호출하여 사용자에게 피드백을 주어야 합니다.
    
    이 툴은 LLM을 사용하여 사용자 친화적인 진행 상황 메시지를 동적으로 생성합니다.

    Args:
        user_request: 사용자의 원본 요청
        tool_name: 현재 호출하려는 툴의 이름
        tool_description: 툴의 설명
        tool_params: 툴에 전달할 파라미터 (딕셔너리 형태)
    
    Returns:
        str: 보고 완료 메시지
    """
    # 진행 상황 메시지 생성 (LLM 동적 생성 또는 정적 매핑 폴백)
    progress_msg = _generate_progress_message(
        user_request=user_request,
        tool_name=tool_name,
        tool_description=tool_description,
        tool_params=tool_params
    )
    
    # 실제 환경에서는 여기서 WebSocket이나 DB로 상태를 전송할 수 있습니다.
    print(f"\n📊 {progress_msg['title']}")
    print(f"   💬 {progress_msg['description']}\n")

    return f"진행 상황이 사용자에게 보고되었습니다: {progress_msg['title']}"

@tool
def search_conversations(query: str) -> str:
    """
    과거 대화 내역이나 프로젝트 히스토리를 검색합니다.
    
    Args:
        query: 검색할 키워드나 질문
        
    Returns:
        str: 검색된 대화 요약
    """
    # TODO: 실제 Vector Store나 DB 검색 로직으로 교체 필요
    return f"'{query}' 관련 대화 3건 발견: 병원 상세 페이지 UX, 필터링 시스템, 프로필 설계"

@tool
def read_document(path: str) -> str:
    """
    지정된 경로의 문서를 읽어서 내용을 반환합니다.
    
    Args:
        path: 파일 경로
        
    Returns:
        str: 문서 내용
    """
    # TODO: 실제 파일 시스템 읽기 로직으로 교체 필요
    return f"{path} 문서 내용 로드 완료"

# ==============================================================================
# 3. Nodes 정의
# ==============================================================================

def agent_node(state: AgentState):
    """
    Agent 노드: LLM을 호출하여 다음 행동을 결정합니다.
    
    참고: GPT-5 사용 시 agent_flow_gpt5_direct.py를 사용하세요.
    이 파일은 안정적인 GPT-4 모델을 사용합니다.
    """
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️ OPENAI_API_KEY 환경변수가 설정되지 않았습니다. API 호출이 실패할 수 있습니다.")

    # GPT-4 모델 사용 (안정적이고 모든 파라미터 지원)
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0
    )

    # Agent가 사용할 도구 바인딩
    tools = [report_progress, search_conversations, read_document]
    llm_with_tools = llm.bind_tools(tools)

    # 현재 메시지 히스토리를 기반으로 LLM 호출
    response = llm_with_tools.invoke(state["messages"])

    # 새로운 메시지 반환 (기존 messages 리스트에 추가됨)
    return {
        "messages": [response]
    }

def tool_node(state: AgentState):
    """
    Tools 노드: Agent가 선택한 도구를 실행합니다.
    report_progress 도구가 호출된 경우, progress_log 상태도 업데이트합니다.
    """
    tools = [report_progress, search_conversations, read_document]
    tool_executor = ToolNode(tools)

    # 도구 실행 (ToolMessage 반환)
    result = tool_executor.invoke(state)

    # report_progress 호출 여부 확인 및 로그 기록
    # state["messages"][-1]은 Agent가 생성한 AIMessage (tool_calls 포함)
    last_message = state["messages"][-1]
    progress_entries = []
    
    if hasattr(last_message, 'tool_calls'):
        for tool_call in last_message.tool_calls:
            if tool_call['name'] == 'report_progress':
                # 진행 상황 메시지 생성
                user_request = tool_call['args'].get('user_request', state.get('user_request', ''))
                tool_name = tool_call['args'].get('tool_name', '')
                tool_description = tool_call['args'].get('tool_description', '')
                tool_params = tool_call['args'].get('tool_params', {})
                
                progress_msg = _generate_progress_message(
                    user_request=user_request,
                    tool_name=tool_name,
                    tool_description=tool_description,
                    tool_params=tool_params
                )
                
                progress_entry = {
                    'title': progress_msg['title'],
                    'description': progress_msg['description']
                }
                progress_entries.append(progress_entry)
    
    output = {
        "messages": result["messages"]
    }
    
    # 진행 로그가 있다면 상태에 추가
    if progress_entries:
        output["progress_log"] = progress_entries

    return output

# ==============================================================================
# 4. Graph 구성
# ==============================================================================

def should_continue(state: AgentState):
    """
    조건부 엣지: 도구 호출이 있으면 Tools 노드로, 없으면 종료.
    """
    last_message = state["messages"][-1]

    # Tool call이 포함되어 있다면 tools 노드로 이동
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"

    # 도구 호출이 없다면(최종 답변 생성) 종료
    return END

def create_agent_graph():
    """
    LangGraph 워크플로우를 생성하고 컴파일합니다.
    """
    workflow = StateGraph(AgentState)

    # 노드 추가
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)

    # 시작점 설정
    workflow.set_entry_point("agent")

    # 엣지 추가
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            END: END
        }
    )

    # 도구 실행 후에는 다시 Agent가 결과를 확인하고 다음 행동을 결정하도록 순환
    workflow.add_edge("tools", "agent")

    return workflow.compile()

# ==============================================================================
# 5. 실행 로직
# ==============================================================================

def run_agent_with_progress(user_query: str):
    """
    Agent를 실행하고 결과를 출력합니다.
    """

    # System Prompt: Agent의 역할과 보고 의무를 명시
    system_prompt = """
당신은 사용자의 요청을 처리하는 AI 어시스턴트입니다.

**중요**: 작업을 수행할 때마다 report_progress 도구를 사용하여
사용자에게 진행 상황을 알려주세요.

## Tool Guideline
작업 시작 시 report_progress 툴을 호출하여 사용자에게 알려주세요.

보고 시점:
1. 새로운 단계 시작 시
2. 중요한 도구 호출 전후
3. 의미있는 결과 도출 시

report_progress 사용 예시:
- 요청 분석 시작: report_progress(user_request="사용자 요청", tool_name="search_conversations", tool_description="과거 대화 검색", tool_params={"query": "키워드"})
- 문서 읽기 시작: report_progress(user_request="사용자 요청", tool_name="read_document", tool_description="문서 읽기", tool_params={"path": "/path/to/doc"})

report_progress는 다른 도구를 호출하기 전에 호출하여 사용자에게 현재 작업 상황을 알려주세요.
"""

    graph = create_agent_graph()

    initial_state = {
        "messages": [
            HumanMessage(content=system_prompt),
            HumanMessage(content=user_query)
        ],
        "progress_log": [],
        "user_request": user_query
    }

    print("=" * 60)
    print("🚀 Agent Flow 시작")
    print("=" * 60)

    try:
        # 스트리밍 실행: 각 단계별 이벤트 확인
        # (실제 서비스에서는 invoke만 사용해도 됩니다)
        for event in graph.stream(initial_state):
            print(f"\n📦 Event: {list(event.keys())}")
            
        # 최종 결과 조회
        # graph.stream 완료 후 상태를 확실히 얻기 위해 invoke를 사용 (중복 실행 가능성 있음)
        # 효율성을 위해서는 stream의 마지막 state를 캡처하는 것이 좋음
        print("\n🔄 최종 결과 집계 중...")
        final_state = graph.invoke(initial_state)

        print("\n" + "=" * 60)
        print("✅ Agent Flow 완료")
        print("=" * 60)

        # 진행 로그 요약
        print("\n📋 진행 상황 요약:")
        if "progress_log" in final_state:
            for i, log in enumerate(final_state["progress_log"], 1):
                print(f"{i}. {log.get('title', '작업 진행 중')}")
                print(f"   {log.get('description', '')}")

        # 최종 답변
        print("\n💡 최종 답변:")
        if final_state["messages"]:
            print(final_state["messages"][-1].content)

        return final_state

    except Exception as e:
        print(f"\n❌ 실행 중 오류 발생: {e}")
        return None

if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("\n⚠️  OPENAI_API_KEY가 설정되지 않았습니다.")
        print("PowerShell에서 다음과 같이 설정해주세요:")
        print('$env:OPENAI_API_KEY="your-api-key-here"')
        exit(1)
    
    print("\n" + "=" * 60)
    print("🤖 사용 모델: GPT-4o-mini (안정 버전)")
    print("📝 GPT-5를 사용하려면: python agent_flow_gpt5_direct.py")
    print("=" * 60 + "\n")
    
    # 정책 문서 기반 테스트 시나리오
    test_scenarios = [
        "기존 채용을 불러오고 싶어",  # 기존 채용 불러오기
        # "공채 채용을 생성하고 싶어",  # 공채 채용 생성
        # "수상시 채용을 생성하고 싶어",  # 수상시 채용 생성
    ]
    
    # 첫 번째 시나리오 실행
    run_agent_with_progress(test_scenarios[0])
    
    # 여러 시나리오를 순차적으로 테스트하려면 아래 주석을 해제하세요
    # for scenario in test_scenarios:
    #     print("\n" + "=" * 60)
    #     print(f"📋 시나리오 테스트: {scenario}")
    #     print("=" * 60 + "\n")
    #     run_agent_with_progress(scenario)

