"""
AX Navigation Pipeline (Orchestrator -> URL Agent -> (optional) WIKI Agent)
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

try:
    import requests  # type: ignore
except ImportError:  # pragma: no cover
    requests = None

from openai import OpenAI


# =============================================================================
# 경로 상수
# =============================================================================

_CURRENT_DIR = Path(__file__).parent
URL_REFERENCE_FILE_PATH = _CURRENT_DIR / "url_reference.md"

# 프롬프트는 ax_url_agent 디렉토리 밖에 존재한다.
_PROMPT_DIR = _CURRENT_DIR.parent / "prompt" / "nmrs_v14.1.0"
ORCHESTRATOR_PROMPT_FILE_PATH = _PROMPT_DIR / "prompt_orchestrator_worker.md"
URL_WORKER_PROMPT_FILE_PATH = _PROMPT_DIR / "prompt_url_worker.md"
WIKI_QUERY_ANALYZER_PROMPT_FILE_PATH = _PROMPT_DIR / "prompt_wiki_worker_query_analyzer.md"
WIKI_SYNTHESIZER_PROMPT_FILE_PATH = _PROMPT_DIR / "prompt_wiki_worker_synthesizer.md"

WIKI_SEARCH_API_URL = "https://track.hdot.kr-dv-jainwon.com/api/v1/kb/search"


# =============================================================================
# 공통 유틸
# =============================================================================

def _ensure_json_word_in_prompt(prompt: str) -> str:
    """
    OpenAI API에서 `response_format={"type":"json_object"}`를 사용할 때,
    프롬프트에 'json' 문자열이 없으면 오류가 날 수 있어 방어적으로 추가한다.
    """
    if "json" in prompt.lower():
        return prompt
    return f"{prompt}\n\n중요: 반드시 JSON 형식으로만 출력한다."


def _parse_first_json_object(raw: str) -> tuple[dict[str, Any], Optional[str]]:
    """
    모델 출력이 JSON object 뒤에 추가 텍스트를 덧붙이는 경우가 있어도,
    첫 JSON object만 안전하게 파싱한다.
    """
    decoder = json.JSONDecoder()
    obj, end_idx = decoder.raw_decode(raw.strip())
    if not isinstance(obj, dict):
        raise ValueError(f"JSON object 형태가 아니다. type={type(obj)} raw={raw}")
    remainder = raw.strip()[end_idx:].strip()
    warning = None
    if remainder:
        warning = f"모델 출력에서 JSON 외 텍스트를 무시했다: {remainder[:120]}"
    return obj, warning


def _read_text_utf8(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"프롬프트 파일을 찾을 수 없음: {path}")
    return path.read_text(encoding="utf-8")


# =============================================================================
# 응답 데이터 구조
# =============================================================================

@dataclass
class OrchestratorResponse:
    query: str
    resume_worker: bool
    url_worker: bool
    recruit_wiki_worker: bool
    reason: str
    selected_agent_id: str
    error: Optional[str] = None
    latency: float = 0.0


@dataclass
class URLAgentResponse:
    """URL Agent 응답 데이터 클래스"""

    query: str
    url: str
    reason: str
    matched_name: str
    plan_id_required: bool
    plan_id: Optional[str] = None
    error: Optional[str] = None
    latency: float = 0.0


@dataclass
class WikiAgentResponse:
    """Wiki Agent 응답 데이터 클래스"""

    query: str
    analyzed_query: str
    analyzed_tag: Optional[str]
    search_api_request_url: Optional[str]
    search_api_request_params: Optional[dict[str, Any]]
    search_api_response_raw: Optional[dict[str, Any]]
    documents: list[dict[str, Any]]
    search_results_count: int
    total_from_hubspot: Optional[int] = None
    total_after_filter: Optional[int] = None
    answer: str = ""
    error: Optional[str] = None
    latency: float = 0.0
    query_analyzer_latency: float = 0.0
    search_api_latency: float = 0.0
    synthesizer_latency: float = 0.0


@dataclass
class NavigationPipelineResponse:
    query: str
    selected_agent_id: str
    orchestrator_reason: str
    url: str
    url_reason: str
    matched_name: str
    plan_id_required: bool
    plan_id: Optional[str] = None

    wiki_analyzed_query: Optional[str] = None
    wiki_analyzed_tag: Optional[str] = None
    wiki_search_api_request_url: Optional[str] = None
    wiki_search_api_request_params: Optional[dict[str, Any]] = None
    wiki_search_api_response_raw: Optional[dict[str, Any]] = None
    wiki_documents: Optional[list[dict[str, Any]]] = None
    wiki_search_results_count: Optional[int] = None
    wiki_total_from_hubspot: Optional[int] = None
    wiki_total_after_filter: Optional[int] = None
    wiki_answer: Optional[str] = None
    wiki_query_analyzer_latency: float = 0.0
    wiki_search_api_latency: float = 0.0
    wiki_synthesizer_latency: float = 0.0
    wiki_agent_latency: float = 0.0

    error: Optional[str] = None
    total_latency: float = 0.0
    orchestrator_latency: float = 0.0
    url_agent_latency: float = 0.0


# =============================================================================
# Orchestrator Agent
# =============================================================================

class AXOrchestratorAgent:
    _PRIORITY_ORDER = ["RESUME_WORKER", "URL_WORKER", "RECRUIT_WIKI_WORKER"]

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-5.2",
        prompt_file: Optional[Path] = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
        self.prompt_file = prompt_file or ORCHESTRATOR_PROMPT_FILE_PATH
        self._prompt_cache: Optional[str] = None

    def reload_prompt(self) -> None:
        self._prompt_cache = None

    def _load_prompt(self) -> str:
        if self._prompt_cache is not None:
            return self._prompt_cache
        self._prompt_cache = _read_text_utf8(self.prompt_file)
        return self._prompt_cache

    @classmethod
    def _resolve_selected_agent_id(cls, resume: bool, url: bool, wiki: bool) -> str:
        mapping = {"RESUME_WORKER": resume, "URL_WORKER": url, "RECRUIT_WIKI_WORKER": wiki}
        selected = [k for k, v in mapping.items() if v]
        if len(selected) == 1:
            return selected[0]
        if len(selected) == 0:
            return "NONE"
        for agent_id in cls._PRIORITY_ORDER:
            if mapping.get(agent_id) is True:
                return agent_id
        return "NONE"

    def route(self, query: str, conversation_history: Optional[str] = None) -> OrchestratorResponse:
        start = time.perf_counter()
        if not self.client:
            return OrchestratorResponse(
                query=query,
                resume_worker=False,
                url_worker=False,
                recruit_wiki_worker=False,
                reason="",
                selected_agent_id="NONE",
                error="OPENAI_API_KEY가 설정되지 않았다.",
                latency=0.0,
            )

        try:
            system_prompt = self._load_prompt()
            history_text = (conversation_history or "").strip()
            user_content = (
                "대화 히스토리:\n"
                f"{history_text if history_text else '(없음)'}\n\n"
                "사용자 요청:\n"
                f"{query}"
            )
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _ensure_json_word_in_prompt(system_prompt)},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content or ""
            parsed, warning = _parse_first_json_object(content)

            resume_worker = bool(parsed.get("RESUME_WORKER", False))
            url_worker = bool(parsed.get("URL_WORKER", False))
            recruit_wiki_worker = bool(parsed.get("RECRUIT_WIKI_WORKER", False))
            reason = str(parsed.get("reason", "")).strip()

            selected_agent_id = self._resolve_selected_agent_id(resume_worker, url_worker, recruit_wiki_worker)
            return OrchestratorResponse(
                query=query,
                resume_worker=resume_worker,
                url_worker=url_worker,
                recruit_wiki_worker=recruit_wiki_worker,
                reason=reason,
                selected_agent_id=selected_agent_id,
                error=warning,
                latency=time.perf_counter() - start,
            )
        except Exception as e:
            return OrchestratorResponse(
                query=query,
                resume_worker=False,
                url_worker=False,
                recruit_wiki_worker=False,
                reason="",
                selected_agent_id="NONE",
                error=str(e),
                latency=time.perf_counter() - start,
            )


# =============================================================================
# URL Navigation Agent
# =============================================================================

class AXURLAgent:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-5.2",
        prompt_file: Optional[Path] = None,
        url_reference_file: Optional[Path] = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
        self.prompt_file = prompt_file or URL_WORKER_PROMPT_FILE_PATH
        self.url_reference_file = url_reference_file or URL_REFERENCE_FILE_PATH
        self._prompt_cache: Optional[str] = None
        self._url_reference_cache: Optional[str] = None

    def reload_prompt(self) -> None:
        self._prompt_cache = None
        self._url_reference_cache = None

    def _load_prompt_template(self) -> str:
        if self._prompt_cache is not None:
            return self._prompt_cache
        self._prompt_cache = _read_text_utf8(self.prompt_file)
        return self._prompt_cache

    def _load_url_reference_markdown(self) -> str:
        if self._url_reference_cache is not None:
            return self._url_reference_cache
        self._url_reference_cache = _read_text_utf8(self.url_reference_file)
        return self._url_reference_cache

    def _build_system_prompt(self) -> str:
        template = self._load_prompt_template()
        url_ref = self._load_url_reference_markdown()
        return template.replace("{url_reference}", url_ref)

    def analyze_query(self, query: str, plan_id: Optional[str] = None) -> URLAgentResponse:
        start = time.perf_counter()
        if not self.client:
            return URLAgentResponse(
                query=query,
                url="",
                reason="",
                matched_name="",
                plan_id_required=False,
                error="OPENAI_API_KEY가 설정되지 않았다.",
                latency=0.0,
            )

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _ensure_json_word_in_prompt(self._build_system_prompt())},
                    {"role": "user", "content": query},
                ],
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content or ""
            result, warning = _parse_first_json_object(content)

            url = str(result.get("url", "") or "")
            reason = str(result.get("reason", "") or "")
            matched_name = str(result.get("matched_name", "") or "")
            plan_id_required = bool(result.get("plan_id_required", False))

            extracted_plan_id = result.get("plan_id")
            final_plan_id = str(extracted_plan_id) if extracted_plan_id is not None else plan_id
            if plan_id_required and final_plan_id:
                url = url.replace("{planId}", str(final_plan_id))

            return URLAgentResponse(
                query=query,
                url=url,
                reason=reason,
                matched_name=matched_name,
                plan_id_required=plan_id_required,
                plan_id=str(extracted_plan_id) if extracted_plan_id is not None else None,
                error=warning,
                latency=time.perf_counter() - start,
            )
        except Exception as e:
            return URLAgentResponse(
                query=query,
                url="",
                reason="",
                matched_name="",
                plan_id_required=False,
                error=str(e),
                latency=time.perf_counter() - start,
            )


# =============================================================================
# Recruit Wiki Agent
# =============================================================================

class AXWikiAgent:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-5.2",
        query_analyzer_prompt_file: Optional[Path] = None,
        synthesizer_prompt_file: Optional[Path] = None,
        search_api_url: Optional[str] = None,
        fetch_limit: int = 99,
        limit: int = 5,
        body: bool = True,
        request_timeout_s: float = 12.0,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
        self.query_analyzer_prompt_file = query_analyzer_prompt_file or WIKI_QUERY_ANALYZER_PROMPT_FILE_PATH
        self.synthesizer_prompt_file = synthesizer_prompt_file or WIKI_SYNTHESIZER_PROMPT_FILE_PATH
        self.search_api_url = search_api_url or WIKI_SEARCH_API_URL
        self.fetch_limit = fetch_limit
        self.limit = limit
        self.body = body
        self.request_timeout_s = request_timeout_s
        self._query_analyzer_prompt_cache: Optional[str] = None
        self._synthesizer_prompt_cache: Optional[str] = None

    def reload_prompt(self) -> None:
        self._query_analyzer_prompt_cache = None
        self._synthesizer_prompt_cache = None

    def _load_query_analyzer_prompt(self) -> str:
        if self._query_analyzer_prompt_cache is not None:
            return self._query_analyzer_prompt_cache
        self._query_analyzer_prompt_cache = _read_text_utf8(self.query_analyzer_prompt_file)
        return self._query_analyzer_prompt_cache

    def _load_synthesizer_prompt(self) -> str:
        if self._synthesizer_prompt_cache is not None:
            return self._synthesizer_prompt_cache
        self._synthesizer_prompt_cache = _read_text_utf8(self.synthesizer_prompt_file)
        return self._synthesizer_prompt_cache

    @staticmethod
    def _normalize_tag(tag_value: Any) -> tuple[Optional[str], Optional[str]]:
        if tag_value is None:
            return None, None
        if isinstance(tag_value, list):
            cleaned = [str(x).strip() for x in tag_value if str(x).strip()]
            if not cleaned:
                return None, None
            return cleaned[0], ", ".join(cleaned)
        tag_str = str(tag_value).strip()
        if not tag_str or tag_str.lower() == "null":
            return None, None
        if "," in tag_str:
            parts = [p.strip() for p in tag_str.split(",") if p.strip()]
            if not parts:
                return None, tag_str
            return parts[0], tag_str
        return tag_str, tag_str

    def _analyze_query(self, query: str) -> tuple[str, Optional[str], Optional[str], float]:
        start = time.perf_counter()
        if not self.client:
            raise RuntimeError("OPENAI_API_KEY가 설정되지 않았다.")
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": _ensure_json_word_in_prompt(self._load_query_analyzer_prompt())},
                {"role": "user", "content": query},
            ],
            response_format={"type": "json_object"},
        )
        content = resp.choices[0].message.content or ""
        result, _warning = _parse_first_json_object(content)
        q_val = result.get("q")
        if not isinstance(q_val, str) or not q_val.strip():
            raise ValueError(f"Wiki Query Analyzer 출력에서 q가 유효하지 않다: {result}")
        tag_for_search, tag_display = self._normalize_tag(result.get("tag"))
        return q_val.strip(), tag_for_search, tag_display, time.perf_counter() - start

    def _search_documents(
        self, q: str, tag_for_search: Optional[str]
    ) -> tuple[dict[str, Any], float, Optional[str], dict[str, Any]]:
        if requests is None:
            raise RuntimeError("requests 라이브러리가 없어 Wiki Search API를 호출할 수 없다.")
        start = time.perf_counter()
        params: dict[str, Any] = {
            "q": q,
            "fetch_limit": self.fetch_limit,
            "limit": self.limit,
            "body": "true" if self.body else "false",
        }
        if tag_for_search is not None:
            params["tag"] = tag_for_search
        resp = requests.get(self.search_api_url, params=params, timeout=self.request_timeout_s)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise ValueError("Wiki Search API 응답이 JSON object가 아니다.")
        return data, time.perf_counter() - start, getattr(resp, "url", None), params

    def _synthesize_answer(self, user_query: str, documents: list[dict[str, Any]]) -> tuple[str, float]:
        start = time.perf_counter()
        if not self.client:
            raise RuntimeError("OPENAI_API_KEY가 설정되지 않았다.")
        user_content = (
            "사용자 질문:\n"
            f"{user_query}\n\n"
            "검색된 문서:\n"
            f"{json.dumps(documents, ensure_ascii=False)}"
        )
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._load_synthesizer_prompt()},
                {"role": "user", "content": user_content},
            ],
        )
        answer = (resp.choices[0].message.content or "").strip()
        return answer, time.perf_counter() - start

    def process(self, query: str) -> WikiAgentResponse:
        overall_start = time.perf_counter()
        try:
            analyzed_q, tag_for_search, tag_display, qa_latency = self._analyze_query(query=query)
            search_json, search_latency, request_url, request_params = self._search_documents(
                q=analyzed_q,
                tag_for_search=tag_for_search,
            )
            results = search_json.get("results", [])
            if not isinstance(results, list):
                raise ValueError("Wiki Search API 응답에서 results가 list가 아니다.")
            answer, synth_latency = self._synthesize_answer(user_query=query, documents=results)
            total_latency = time.perf_counter() - overall_start
            total_from_hubspot = search_json.get("total_from_hubspot")
            total_after_filter = search_json.get("total_after_filter")
            return WikiAgentResponse(
                query=query,
                analyzed_query=analyzed_q,
                analyzed_tag=tag_display,
                search_api_request_url=request_url,
                search_api_request_params=request_params,
                search_api_response_raw=search_json,
                documents=results,
                search_results_count=len(results),
                total_from_hubspot=total_from_hubspot if isinstance(total_from_hubspot, int) else None,
                total_after_filter=total_after_filter if isinstance(total_after_filter, int) else None,
                answer=answer,
                error=None,
                latency=total_latency,
                query_analyzer_latency=qa_latency,
                search_api_latency=search_latency,
                synthesizer_latency=synth_latency,
            )
        except Exception as e:
            total_latency = time.perf_counter() - overall_start
            return WikiAgentResponse(
                query=query,
                analyzed_query="",
                analyzed_tag=None,
                search_api_request_url=None,
                search_api_request_params=None,
                search_api_response_raw=None,
                documents=[],
                search_results_count=0,
                answer="",
                error=str(e),
                latency=total_latency,
            )


# =============================================================================
# Orchestrator -> URL Agent 파이프라인
# =============================================================================

class AXNavigationPipeline:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-5.2",
        url_prompt_file: Optional[Path] = None,
        url_reference_file: Optional[Path] = None,
        orchestrator_prompt_file: Optional[Path] = None,
        wiki_query_analyzer_prompt_file: Optional[Path] = None,
        wiki_synthesizer_prompt_file: Optional[Path] = None,
        wiki_search_api_url: Optional[str] = None,
    ) -> None:
        self.orchestrator = AXOrchestratorAgent(
            api_key=api_key,
            model=model,
            prompt_file=orchestrator_prompt_file,
        )
        self.url_agent = AXURLAgent(
            api_key=api_key,
            model=model,
            prompt_file=url_prompt_file,
            url_reference_file=url_reference_file,
        )
        self.wiki_agent = AXWikiAgent(
            api_key=api_key,
            model=model,
            query_analyzer_prompt_file=wiki_query_analyzer_prompt_file,
            synthesizer_prompt_file=wiki_synthesizer_prompt_file,
            search_api_url=wiki_search_api_url,
        )

    def reload_prompt(self) -> None:
        self.orchestrator.reload_prompt()
        self.url_agent.reload_prompt()
        self.wiki_agent.reload_prompt()

    def recommend(
        self,
        query: str,
        plan_id: Optional[str] = None,
        conversation_history: Optional[str] = None,
        direct_url_agent: bool = False,
    ) -> NavigationPipelineResponse:
        start = time.perf_counter()

        if direct_url_agent:
            url_res = self.url_agent.analyze_query(query=query, plan_id=plan_id)
            total_latency = time.perf_counter() - start
            if url_res.error:
                return NavigationPipelineResponse(
                    query=query,
                    selected_agent_id="URL_WORKER",
                    orchestrator_reason="(직접 실행: Orchestrator 생략)",
                    url="",
                    url_reason="",
                    matched_name="",
                    plan_id_required=False,
                    plan_id=None,
                    error=url_res.error,
                    total_latency=total_latency,
                    orchestrator_latency=0.0,
                    url_agent_latency=url_res.latency,
                )
            return NavigationPipelineResponse(
                query=query,
                selected_agent_id="URL_WORKER",
                orchestrator_reason="(직접 실행: Orchestrator 생략)",
                url=url_res.url,
                url_reason=url_res.reason,
                matched_name=url_res.matched_name,
                plan_id_required=url_res.plan_id_required,
                plan_id=url_res.plan_id,
                error=None,
                total_latency=total_latency,
                orchestrator_latency=0.0,
                url_agent_latency=url_res.latency,
            )

        orch = self.orchestrator.route(query=query, conversation_history=conversation_history)
        selected_agent_id = orch.selected_agent_id
        orchestrator_reason = orch.reason

        # Wiki Agent
        if selected_agent_id == "RECRUIT_WIKI_WORKER":
            wiki_res = self.wiki_agent.process(query=query)
            total_latency = time.perf_counter() - start
            if wiki_res.error:
                return NavigationPipelineResponse(
                    query=query,
                    selected_agent_id=selected_agent_id,
                    orchestrator_reason=orchestrator_reason,
                    url="",
                    url_reason="",
                    matched_name="",
                    plan_id_required=False,
                    plan_id=None,
                    wiki_analyzed_query=wiki_res.analyzed_query,
                    wiki_analyzed_tag=wiki_res.analyzed_tag,
                    wiki_search_api_request_url=wiki_res.search_api_request_url,
                    wiki_search_api_request_params=wiki_res.search_api_request_params,
                    wiki_search_api_response_raw=wiki_res.search_api_response_raw,
                    wiki_documents=wiki_res.documents,
                    wiki_search_results_count=wiki_res.search_results_count,
                    wiki_total_from_hubspot=wiki_res.total_from_hubspot,
                    wiki_total_after_filter=wiki_res.total_after_filter,
                    wiki_answer=wiki_res.answer,
                    wiki_query_analyzer_latency=wiki_res.query_analyzer_latency,
                    wiki_search_api_latency=wiki_res.search_api_latency,
                    wiki_synthesizer_latency=wiki_res.synthesizer_latency,
                    wiki_agent_latency=wiki_res.latency,
                    error=wiki_res.error,
                    total_latency=total_latency,
                    orchestrator_latency=orch.latency,
                    url_agent_latency=0.0,
                )
            return NavigationPipelineResponse(
                query=query,
                selected_agent_id=selected_agent_id,
                orchestrator_reason=orchestrator_reason,
                url="",
                url_reason="",
                matched_name="",
                plan_id_required=False,
                plan_id=None,
                wiki_analyzed_query=wiki_res.analyzed_query,
                wiki_analyzed_tag=wiki_res.analyzed_tag,
                wiki_search_api_request_url=wiki_res.search_api_request_url,
                wiki_search_api_request_params=wiki_res.search_api_request_params,
                wiki_search_api_response_raw=wiki_res.search_api_response_raw,
                wiki_documents=wiki_res.documents,
                wiki_search_results_count=wiki_res.search_results_count,
                wiki_total_from_hubspot=wiki_res.total_from_hubspot,
                wiki_total_after_filter=wiki_res.total_after_filter,
                wiki_answer=wiki_res.answer,
                wiki_query_analyzer_latency=wiki_res.query_analyzer_latency,
                wiki_search_api_latency=wiki_res.search_api_latency,
                wiki_synthesizer_latency=wiki_res.synthesizer_latency,
                wiki_agent_latency=wiki_res.latency,
                error=None,
                total_latency=total_latency,
                orchestrator_latency=orch.latency,
                url_agent_latency=0.0,
            )

        # URL_WORKER가 아니면 URL 추천은 생략한다.
        if selected_agent_id != "URL_WORKER":
            total_latency = time.perf_counter() - start
            return NavigationPipelineResponse(
                query=query,
                selected_agent_id=selected_agent_id,
                orchestrator_reason=orchestrator_reason,
                url="",
                url_reason="",
                matched_name="",
                plan_id_required=False,
                plan_id=None,
                error=orch.error,
                total_latency=total_latency,
                orchestrator_latency=orch.latency,
                url_agent_latency=0.0,
            )

        url_res = self.url_agent.analyze_query(query=query, plan_id=plan_id)
        total_latency = time.perf_counter() - start
        if url_res.error:
            return NavigationPipelineResponse(
                query=query,
                selected_agent_id=selected_agent_id,
                orchestrator_reason=orchestrator_reason,
                url="",
                url_reason="",
                matched_name="",
                plan_id_required=False,
                plan_id=None,
                error=url_res.error,
                total_latency=total_latency,
                orchestrator_latency=orch.latency,
                url_agent_latency=url_res.latency,
            )

        return NavigationPipelineResponse(
            query=query,
            selected_agent_id=selected_agent_id,
            orchestrator_reason=orchestrator_reason,
            url=url_res.url,
            url_reason=url_res.reason,
            matched_name=url_res.matched_name,
            plan_id_required=url_res.plan_id_required,
            plan_id=url_res.plan_id,
            error=None,
            total_latency=total_latency,
            orchestrator_latency=orch.latency,
            url_agent_latency=url_res.latency,
        )



