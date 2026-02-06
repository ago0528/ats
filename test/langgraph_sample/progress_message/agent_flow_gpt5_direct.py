# src/ats/ax/test/langgraph_sample/agent_flow_gpt5_direct.py
"""
GPT-5 모델을 직접 OpenAI Client로 사용하는 버전
참고: https://community.openai.com/t/gpt-5-models-temperature/1337957

GPT-5는 reasoning 모델로 temperature 파라미터를 지원하지 않습니다.
LangChain의 ChatOpenAI가 자동으로 temperature를 추가하므로,
직접 OpenAI client를 사용합니다.
"""

import operator
import os
from typing import TypedDict, Annotated, Sequence, List, Dict, Any
from openai import OpenAI

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()

# OpenAI Client 초기화
client = OpenAI()

# ==============================================================================
# 1. State 정의
# ==============================================================================
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    progress_log: Annotated[List[Dict[str, Any]], operator.add]

# ==============================================================================
# 2. Tools 정의
# ==============================================================================
@tool
def report_progress(
    stage: str,
    action: str,
    progress: int,
    details: str
) -> str:
    """작업 진행 상황을 사용자에게 보고합니다."""
    print(f"\n📊 [{progress}%] {stage.upper()}: {action}")
    print(f"   💬 {details}\n")
    return f"진행 상황이 사용자에게 보고되었습니다: {action} ({progress}%)"

@tool
def search_conversations(query: str) -> str:
    """과거 대화 내역이나 프로젝트 히스토리를 검색합니다."""
    return f"'{query}' 관련 대화 3건 발견: 병원 상세 페이지 UX, 필터링 시스템, 프로필 설계"

@tool
def read_document(path: str) -> str:
    """지정된 경로의 문서를 읽어서 내용을 반환합니다."""
    return f"{path} 문서 내용 로드 완료"

# Tool 스키마 생성
def get_tool_schemas():
    """LangChain tools를 OpenAI function calling 형식으로 변환"""
    tools = [report_progress, search_conversations, read_document]
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        arg_name: {
                            "type": "string",
                            "description": f"{arg_name} parameter"
                        }
                        for arg_name in t.args
                    },
                    "required": list(t.args.keys())
                }
            }
        }
        for t in tools
    ]

# ==============================================================================
# 3. Nodes 정의
# ==============================================================================
def agent_node(state: AgentState):
    """Agent 노드: GPT-5를 직접 호출하여 다음 행동을 결정합니다."""
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️ OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")

    # LangChain 메시지를 OpenAI 형식으로 변환
    messages = []
    for msg in state["messages"]:
        if isinstance(msg, HumanMessage):
            messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                # Tool calls가 있는 경우
                tool_calls = [
                    {
                        "id": tc['id'],
                        "type": "function",
                        "function": {
                            "name": tc['name'],
                            "arguments": str(tc['args'])
                        }
                    }
                    for tc in msg.tool_calls
                ]
                messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": tool_calls
                })
            else:
                messages.append({"role": "assistant", "content": msg.content})
        elif isinstance(msg, ToolMessage):
            messages.append({
                "role": "tool",
                "tool_call_id": msg.tool_call_id,
                "content": msg.content
            })

    # GPT-5 API 호출 (temperature 파라미터 제외)
    # 참고: https://community.openai.com/t/gpt-5-models-temperature/1337957
    try:
        completion = client.chat.completions.create(
            model="gpt-5-nano",
            messages=messages,
            tools=get_tool_schemas()
            # temperature 파라미터를 명시하지 않음 (GPT-5 요구사항)
        )
        
        response_message = completion.choices[0].message
        
        # OpenAI 응답을 LangChain AIMessage로 변환
        if response_message.tool_calls:
            tool_calls = [
                {
                    'name': tc.function.name,
                    'args': eval(tc.function.arguments),  # JSON string to dict
                    'id': tc.id,
                    'type': 'tool_call'
                }
                for tc in response_message.tool_calls
            ]
            ai_msg = AIMessage(
                content=response_message.content or "",
                tool_calls=tool_calls
            )
        else:
            ai_msg = AIMessage(content=response_message.content)
        
        return {"messages": [ai_msg]}
        
    except Exception as e:
        print(f"❌ GPT-5 API 호출 오류: {e}")
        raise

def tool_node(state: AgentState):
    """Tools 노드: Agent가 선택한 도구를 실행합니다."""
    tools = [report_progress, search_conversations, read_document]
    tool_executor = ToolNode(tools)
    result = tool_executor.invoke(state)

    last_message = state["messages"][-1]
    progress_entries = []
    
    if hasattr(last_message, 'tool_calls'):
        for tool_call in last_message.tool_calls:
            if tool_call['name'] == 'report_progress':
                progress_entry = {
                    'stage': tool_call['args'].get('stage'),
                    'action': tool_call['args'].get('action'),
                    'progress': tool_call['args'].get('progress'),
                    'details': tool_call['args'].get('details')
                }
                progress_entries.append(progress_entry)
    
    output = {"messages": result["messages"]}
    if progress_entries:
        output["progress_log"] = progress_entries

    return output

# ==============================================================================
# 4. Graph 구성
# ==============================================================================
def should_continue(state: AgentState):
    """조건부 엣지: 도구 호출이 있으면 Tools 노드로, 없으면 종료."""
    last_message = state["messages"][-1]
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tools"
    return END

def create_agent_graph():
    """LangGraph 워크플로우를 생성하고 컴파일합니다."""
    workflow = StateGraph(AgentState)

    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    workflow.set_entry_point("agent")
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {"tools": "tools", END: END}
    )
    workflow.add_edge("tools", "agent")

    return workflow.compile()

# ==============================================================================
# 5. 실행 로직
# ==============================================================================
def run_agent_with_progress(user_query: str):
    """Agent를 실행하고 결과를 출력합니다."""
    system_prompt = """
당신은 메디컬잡다 프로덕트 매니저의 업무를 돕는 AI 어시스턴트입니다.

**중요**: 작업을 수행할 때마다 report_progress 도구를 사용하여
사용자에게 진행 상황을 알려주세요.

보고 시점:
1. 새로운 단계 시작 시
2. 중요한 도구 호출 전후
3. 의미있는 결과 도출 시

예시:
- report_progress(stage="planning", action="작업 계획 수립", progress=10, details="PRD 작성 5단계 계획 수립 중")
- report_progress(stage="executing", action="과거 대화 검색", progress=30, details="병원 상세 페이지 관련 대화 검색 중")
"""

    graph = create_agent_graph()
    initial_state = {
        "messages": [
            HumanMessage(content=system_prompt),
            HumanMessage(content=user_query)
        ],
        "progress_log": []
    }

    print("=" * 60)
    print("🚀 Agent Flow 시작 (GPT-5-mini via Direct OpenAI Client)")
    print("=" * 60)

    try:
        for event in graph.stream(initial_state):
            print(f"\n📦 Event: {list(event.keys())}")
            
        print("\n🔄 최종 결과 집계 중...")
        final_state = graph.invoke(initial_state)

        print("\n" + "=" * 60)
        print("✅ Agent Flow 완료")
        print("=" * 60)

        print("\n📋 진행 상황 요약:")
        if "progress_log" in final_state:
            for i, log in enumerate(final_state["progress_log"], 1):
                print(f"{i}. [{log['progress']}%] {log['action']}: {log['details']}")

        print("\n💡 최종 답변:")
        if final_state["messages"]:
            print(final_state["messages"][-1].content)

        return final_state

    except Exception as e:
        print(f"\n❌ 실행 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("\n⚠️  OPENAI_API_KEY가 설정되지 않았습니다.")
        print("PowerShell에서 다음과 같이 설정해주세요:")
        print('$env:OPENAI_API_KEY="your-api-key-here"')
        exit(1)
    
    print("\n🤖 사용 모델: GPT-5-mini-2025-08-07 (Direct OpenAI Client)")
    print("📚 참고: https://community.openai.com/t/gpt-5-models-temperature/1337957\n")
    
    run_agent_with_progress(
        "병원 상세 페이지의 간호등급 정보 표시 방법에 대한 PRD를 작성해줘"
    )

