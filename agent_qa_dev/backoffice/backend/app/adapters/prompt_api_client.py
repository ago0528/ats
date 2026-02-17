"""
AX 프롬프트 API 클라이언트 모듈

프롬프트 조회, 수정, 초기화 기능을 제공합니다.
"""

import os
import time
from typing import Optional, Literal
from dataclasses import dataclass
import httpx


# Worker 타입 정의
WorkerType = Literal[
    # # 구버전 (v14.2.0)
    # "ORCHESTRATOR_WORKER",
    # "RESUME_WORKER",
    # "RESUME_WORKER_V2",
    # "RESUME_ANALYSIS_CODE_CREATE_WORKER",
    # "RECRUIT_PLAN_CREATE_WORKER",
    # "RECRUIT_PLAN_WORKER",
    # "RECRUIT_WIKI_WORKER",
    # "RECRUIT_WIKI_QUERY_ANALYZER_WORKER",
    # "RECRUIT_WIKI_SYNTHESIZER_WORKER",
    # "URL_WORKER",

    # 현재 버전 (v14.3.0)
    "ORCHESTRATOR_WORKER_V3",
    "URL_WORKER_V3",
    "RESUME_WORKER_V3",
    "RESUME_ANALYSIS_CODE_CREATE_WORKER_V3",
    "RESUME_COMMON_DATA_SEARCH_WORKER_V3",
    "RECRUIT_PLAN_CREATE_WORKER_V3",
    "RECRUIT_PLAN_WORKER_V3",
    "RECRUIT_WIKI_WORKER_V3",
    "APPLICANT_EVALUATION_WORKER",
    "ANSWER_SYNTHESIZER_WORKER_V3",
]

# Worker 타입 목록
WORKER_TYPES: list[str] = [
    # 구버전 (v14.2.0)
    # "ORCHESTRATOR_WORKER",
    # "RESUME_WORKER",
    # "RESUME_WORKER_V2",
    # "RESUME_ANALYSIS_CODE_CREATE_WORKER",
    # "RECRUIT_PLAN_CREATE_WORKER",
    # "RECRUIT_PLAN_WORKER",
    # "RECRUIT_WIKI_WORKER",
    # "RECRUIT_WIKI_QUERY_ANALYZER_WORKER",
    # "RECRUIT_WIKI_SYNTHESIZER_WORKER",
    # "URL_WORKER",

    # 현재 버전 (v14.3.0)
    "ORCHESTRATOR_WORKER_V3",
    "RESUME_WORKER_V3",
    "RESUME_ANALYSIS_CODE_CREATE_WORKER_V3",
    "RESUME_COMMON_DATA_SEARCH_WORKER_V3",
    "URL_WORKER_V3",
    "RECRUIT_WIKI_WORKER_V3",
    "ANSWER_SYNTHESIZER_WORKER_V3",
    "RECRUIT_PLAN_CREATE_WORKER_V3",
    "RECRUIT_PLAN_WORKER_V3",
    "APPLICANT_EVALUATION_WORKER"
]

# Worker 타입 설명
WORKER_DESCRIPTIONS = {
    # # 구버전 (v14.2.0)
    # "ORCHESTRATOR_WORKER": "하위 에이전트 실행 판단 AI 에이전트",
    # "RESUME_WORKER": "지원자 관리 AI 에이전트",
    # "RESUME_WORKER_V2": "지원자 관리 AI 에이전트",
    # "RESUME_ANALYSIS_CODE_CREATE_WORKER": "지원자 통계/분석 코드 생성 AI 에이전트",
    # "RECRUIT_PLAN_CREATE_WORKER": "채용 플랜 생성 AI 에이전트",
    # "RECRUIT_PLAN_WORKER": "채용 플랜 AI 에이전트",
    # "RECRUIT_WIKI_WORKER": "채용 위키 AI 에이전트",
    # "RECRUIT_WIKI_QUERY_ANALYZER_WORKER": "채용 위키 질문 분석 AI 에이전트",
    # "RECRUIT_WIKI_SYNTHESIZER_WORKER": "채용 위키 답변 합성 AI 에이전트",
    # "URL_WORKER": "URL AI 에이전트",

    # 현재 버전 (v14.3.0)
    "ORCHESTRATOR_WORKER_V3": "하위 에이전트 실행 판단 AI 에이전트",
    "RESUME_WORKER_V3": "지원자 관리 AI 에이전트",
    "RESUME_ANALYSIS_CODE_CREATE_WORKER_V3": "지원자 통계/분석 코드 생성 AI 에이전트",
    "RESUME_COMMON_DATA_SEARCH_WORKER_V3": "지원서 공통 데이터 검색 AI 에이전트",
    "URL_WORKER_V3": "URL AI 에이전트",
    "RECRUIT_WIKI_WORKER_V3": "채용 위키 AI 에이전트",
    "ANSWER_SYNTHESIZER_WORKER_V3": "답변 병합 AI 에이전트",
    "RECRUIT_PLAN_CREATE_WORKER_V3": "채용 플랜 생성 AI 에이전트",
    "RECRUIT_PLAN_WORKER_V3": "채용 플랜 AI 에이전트",
    "APPLICANT_EVALUATION_WORKER": "지원자 평가 AI 에이전트"
}

# API Base URL
BASE_URL_DV = "https://api-llm.ats.kr-dv-midasin.com"
BASE_URL_QA = "https://api-llm.ats.kr-st2-midasin.com"
BASE_URL_ST = "https://api-llm.ats.kr-st-midasin.com"
BASE_URL_PR = "https://api-llm.ats.kr-pr-midasin.com"


@dataclass
class PromptResponse:
    """프롬프트 API 응답 데이터 클래스"""
    before: str
    after: str


@dataclass
class WorkerTestResponse:
    """Worker 테스트 API 응답 데이터 클래스"""
    conversation_id: str
    answer: str
    response_time: float  # API 호출 시간 (초)


def get_base_url(environment: str) -> Optional[str]:
    """환경에 따른 Base URL 반환"""
    urls = {
        "DV": BASE_URL_DV,
        "QA": BASE_URL_QA,
        "ST": BASE_URL_ST,
        "PR": BASE_URL_PR,
    }
    return urls.get(environment)


class AxPromptApiClient:
    """AX 프롬프트 API 클라이언트"""

    def __init__(
        self,
        base_url: str = BASE_URL_DV,
        environment: Optional[str] = None,
        retention_token: Optional[str] = None,
        mrs_session: Optional[str] = None,
        cms_access_token: Optional[str] = None,
    ):
        """
        클라이언트 초기화

        Args:
            base_url: API 베이스 URL (기본값: DV 환경)
            environment: 환경 이름 (DV, QA, ST, PR)
            retention_token: Retention 토큰 (Worker 테스트 시 필요)
            mrs_session: Mrs 세션 (Worker 테스트 시 필요)
            cms_access_token: CMS Access 토큰 (Worker 테스트 시 필요)
        """
        self.base_url = base_url.rstrip("/")
        self.environment = environment
        self.retention_token = retention_token or os.getenv("RETENTION_TOKEN")
        self.mrs_session = mrs_session or os.getenv("MRS_SESSION")
        self.cms_access_token = cms_access_token or os.getenv("CMS_ACCESS_TOKEN")

    def _get_auth_headers_if_needed(self) -> Optional[dict]:
        """
        ATS 호출에 필요한 인증 헤더를 반환합니다.

        인증 토큰을 입력한 환경에서는 환경 구분 없이 공통으로 헤더를 전달합니다.
        토큰이 하나도 없는 경우에는 요청 헤더를 붙이지 않습니다.

        Returns:
            인증 헤더 딕셔너리 또는 None
        """
        if not any([self.retention_token, self.mrs_session, self.cms_access_token]):
            return None

        # 토큰이 있으면 값으로 사용, 없으면 빈 문자열로 전달
        auth_token = (self.retention_token or "").strip()
        if auth_token.lower().startswith("bearer "):
            auth_token = auth_token[7:].strip()
        mrs_session = (self.mrs_session or "").strip()
        cms_token = (self.cms_access_token or "").strip()

        return {
            "Authorization": f"Bearer {auth_token}",
            "Mrs-Session": mrs_session,
            "Cms-Access-Token": cms_token,
            "Content-Type": "application/json",
        }

    def get_prompt(
        self,
        worker_type: str,
    ) -> PromptResponse:
        """
        프롬프트 조회

        Args:
            worker_type: 조회할 Worker 타입

        Returns:
            PromptResponse: 프롬프트 정보 (before, after)

        Raises:
            httpx.HTTPStatusError: API 호출 실패 시

        Note:
            API 동작 방식:
            - prompt: null -> 현재 프롬프트 조회
            - prompt: "값" -> 프롬프트 수정
            - 초기화는 별도 엔드포인트 PUT /api/v1/ai/prompt/reset 사용
        """
        url = f"{self.base_url}/api/v1/ai/prompt"

        # prompt를 null로 설정하여 조회 모드로 동작
        # JSON 직렬화 시 "prompt": null이 됨
        payload = {
            "workerType": worker_type,
            "prompt": None,
        }

        headers = self._get_auth_headers_if_needed()

        try:
            response = httpx.put(url, json=payload, headers=headers, timeout=30.0)
            response.raise_for_status()

            data = response.json()
            return PromptResponse(
                before=data.get("before", ""),
                after=data.get("after", ""),
            )
        except httpx.HTTPStatusError as e:
            print(f"API 호출 실패: {e.response.status_code}")
            print(f"응답 내용: {e.response.text}")
            raise
        except Exception as e:
            print(f"오류 발생: {str(e)}")
            raise

    def update_prompt(
        self,
        worker_type: str,
        prompt: str,
    ) -> PromptResponse:
        """
        프롬프트 수정

        Args:
            worker_type: 수정할 Worker 타입
            prompt: 새로운 프롬프트 내용

        Returns:
            PromptResponse: 변경 전후 프롬프트 정보

        Raises:
            httpx.HTTPStatusError: API 호출 실패 시
        """
        url = f"{self.base_url}/api/v1/ai/prompt"

        payload = {
            "workerType": worker_type,
            "prompt": prompt,
        }

        headers = self._get_auth_headers_if_needed()

        try:
            response = httpx.put(url, json=payload, headers=headers, timeout=30.0)
            response.raise_for_status()

            data = response.json()
            return PromptResponse(
                before=data.get("before", ""),
                after=data.get("after", ""),
            )
        except httpx.HTTPStatusError as e:
            print(f"API 호출 실패: {e.response.status_code}")
            print(f"응답 내용: {e.response.text}")
            raise
        except Exception as e:
            print(f"오류 발생: {str(e)}")
            raise

    def reset_prompt(
        self,
        worker_type: str,
    ) -> PromptResponse:
        """
        프롬프트 초기화 (코드에 남겨둔 System Prompt로 초기화)

        Args:
            worker_type: 초기화할 Worker 타입

        Returns:
            PromptResponse: 변경 전후 프롬프트 정보

        Raises:
            httpx.HTTPStatusError: API 호출 실패 시
        """
        url = f"{self.base_url}/api/v1/ai/prompt/reset"

        # workerType만 전달하여 코드에 저장된 기본 프롬프트로 복원
        payload = {
            "workerType": worker_type,
        }

        headers = self._get_auth_headers_if_needed()

        try:
            response = httpx.put(url, json=payload, headers=headers, timeout=30.0)
            response.raise_for_status()

            data = response.json()
            return PromptResponse(
                before=data.get("before", ""),
                after=data.get("after", ""),
            )
        except httpx.HTTPStatusError as e:
            print(f"API 호출 실패: {e.response.status_code}")
            print(f"응답 내용: {e.response.text}")
            raise
        except Exception as e:
            print(f"오류 발생: {str(e)}")
            raise

    def test_worker(
        self,
        worker_type: str,
        user_message: str,
        conversation_id: Optional[str] = None,
        recruit_plan_id: Optional[str] = None,
    ) -> WorkerTestResponse:
        """
        Worker 테스트 (프롬프트 테스트)

        Args:
            worker_type: 테스트할 Worker 타입
            user_message: 사용자 메시지 (질문)
            conversation_id: 대화 맥락 유지를 위한 ID (처음 대화 시작 시 None)
            recruit_plan_id: 채용 플랜 ID (선택적, 테스트 시에만 사용)

        Returns:
            WorkerTestResponse: Worker 응답 정보 (response_time 포함)

        Raises:
            httpx.HTTPStatusError: API 호출 실패 시
            ValueError: 토큰이 설정되지 않은 경우
        """
        if not self.retention_token or not self.mrs_session or not self.cms_access_token:
            raise ValueError(
                "Worker 테스트를 위해서는 RETENTION_TOKEN, MRS_SESSION, CMS_ACCESS_TOKEN이 필요합니다.\n"
                ".env 파일에 토큰을 설정하거나 클라이언트 초기화 시 전달해주세요."
            )

        url = f"{self.base_url}/api/v1/ai/prompt/worker/test"

        headers = {
            "Authorization": f"Bearer {self.retention_token}",
            "Mrs-Session": self.mrs_session,
            "Cms-Access-Token": self.cms_access_token,
            "Content-Type": "application/json",
        }

        payload = {
            "workerType": worker_type,
            "userMessage": user_message,
        }

        # conversation_id가 있으면 추가
        if conversation_id:
            payload["conversationId"] = conversation_id

        # Context 객체 생성 (recruitPlanId가 있으면 추가)
        context = {}
        if recruit_plan_id:
            context["recruitPlanId"] = recruit_plan_id

        # Context가 비어있지 않으면 payload에 추가
        if context:
            payload["context"] = context

        try:
            # API 호출 시간 측정
            start_time = time.time()
            response = httpx.post(url, json=payload, headers=headers, timeout=60.0)
            response.raise_for_status()
            end_time = time.time()
            response_time = end_time - start_time

            data = response.json()
            return WorkerTestResponse(
                conversation_id=data.get("conversationId", ""),
                answer=data.get("answer", ""),
                response_time=response_time,
            )
        except httpx.HTTPStatusError as e:
            print(f"API 호출 실패: {e.response.status_code}")
            print(f"응답 내용: {e.response.text}")
            raise
        except Exception as e:
            print(f"오류 발생: {str(e)}")
            raise


def safe_len(value: Optional[str]) -> int:
    """None-safe 길이 계산"""
    return len(value) if value is not None else 0
