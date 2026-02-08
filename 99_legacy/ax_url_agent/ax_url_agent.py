"""
AX Navigation Pipeline (Orchestrator -> URL Agent)

?ъ슜??吏덉쓽 ?낅젰 -> Orchestrator(?뚯빱 ?좏깮) -> URL Agent(URL 異붿쿇) ?먮쫫??濡쒖뺄?먯꽌 ?ы쁽?섍린 ?꾪븳 ?ㅽ겕由쏀듃?대떎.
?ㅼ젣 ?댁쁺 ?섍꼍?먯꽌???좏깮??Worker???곕씪 ?꾧뎄 ?몄텧/?붾㈃ ?뚮뜑留곸씠 ?댁뼱吏�吏�留?
???ㅽ겕由쏀듃??URL 異붿쿇 ?뚰듃留?吏곸젒 ?ㅽ뻾?섎ŉ, 洹???Worker???좏깮 寃곌낵留?異쒕젰?쒕떎.
"""

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
# 寃쎈줈 ?곸닔
# =============================================================================

# ?꾩옱 ?뚯씪 湲곗? ?붾젆?좊━ 寃쎈줈
_CURRENT_DIR = Path(__file__).parent
URL_REFERENCE_FILE_PATH = _CURRENT_DIR / "url_reference.md"

# ?꾨＼?꾪듃??ax_url_agent ?붾젆?좊━ 諛뽰뿉 議댁옱?쒕떎.
_PROMPT_DIR = _CURRENT_DIR.parent / "prompt" / "nmrs_v14.1.0"
ORCHESTRATOR_PROMPT_FILE_PATH = _PROMPT_DIR / "prompt_orchestrator_worker.md"
WIKI_QUERY_ANALYZER_PROMPT_FILE_PATH = _PROMPT_DIR / "prompt_wiki_worker_query_analyzer.md"
WIKI_SYNTHESIZER_PROMPT_FILE_PATH = _PROMPT_DIR / "prompt_wiki_worker_synthesizer.md"
URL_WORKER_PROMPT_FILE_PATH = _PROMPT_DIR / "prompt_url_worker.md"

# URL Worker ?꾨＼?꾪듃??prompt ?붾젆?좊━???뺣낯 ?뚯씪??湲곕낯?쇰줈 ?ъ슜?쒕떎.
# (ax_url_agent/prompt.md??怨쇨굅 ?명솚?⑹쑝濡쒕쭔 痍④툒?쒕떎.)
PROMPT_FILE_PATH = URL_WORKER_PROMPT_FILE_PATH

WIKI_SEARCH_API_URL = "https://track.hdot.kr-dv-jainwon.com/api/v1/kb/search"


# =============================================================================
# 怨듯넻 ?좏떥
# =============================================================================

def _ensure_json_word_in_prompt(prompt: str) -> str:
    """
    OpenAI API??`response_format={"type":"json_object"}` ?ъ슜 ??
    messages ?댁슜??'json'?대씪???⑥뼱媛� ?ы븿?섏뼱???쒕떎???쒖빟???고쉶?섍린 ?꾪븳 ?덉쟾?μ튂?대떎.

    - ?꾨＼?꾪듃 ?먯껜???대? JSON 洹쒖튃???덈떎硫??곹뼢??嫄곗쓽 ?녿떎.
    - ?녿뜑?쇰룄, 異쒕젰 ?щ㎎??JSON?쇰줈 怨좎젙?섎뒗 吏�?쒕? 異붽??쒕떎.
    """
    if "json" in prompt.lower():
        return prompt
    return f"{prompt}\n\n以묒슂: 諛섎뱶??JSON ?뺤떇?쇰줈留?異쒕젰?쒕떎."


def _parse_first_json_object(raw: str) -> tuple[dict[str, Any], Optional[str]]:
    """
    紐⑤뜽??JSON object ?ㅼ뿉 異붽? ?띿뒪?몃? ?㏓텤?대뒗 寃쎌슦媛� ?덉뼱??
    泥?踰덉㎏ JSON object留??덉쟾?섍쾶 ?뚯떛?섍린 ?꾪븳 ?좏떥?대떎.

    Returns:
        - parsed: 泥?JSON object
        - warning: JSON ?ㅼ뿉 ?섎? ?덈뒗 ?붿뿬 ?띿뒪?멸? ?덉뿀?쇰㈃ 寃쎄퀬 臾몄옄?? ?꾨땲硫?None
    """
    decoder = json.JSONDecoder()
    try:
        obj, end_idx = decoder.raw_decode(raw.strip())
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"{e.msg} / raw={raw}", e.doc, e.pos) from e

    if not isinstance(obj, dict):
        raise ValueError(f"JSON object ?뺥깭媛� ?꾨땲?? type={type(obj)} raw={raw}")

    remainder = raw.strip()[end_idx:].strip()
    if remainder:
        return obj, f"紐⑤뜽 異쒕젰??JSON ??異붽? ?띿뒪?멸? ?덉뼱 臾댁떆?덈떎: {remainder[:120]}"

    return obj, None


def _normalize_orchestrator_result(result: dict[str, Any]) -> dict[str, Any]:
    """
    Orchestrator ?꾨＼?꾪듃??'toolAssistantExecutionProcess' 媛숈? ???몄텧 ?щ㎎???ы븿?섏뼱 ?덉쑝硫?
    ?ㅼ젣 紐⑤뜽 異쒕젰???꾨옒 ?뺥깭濡?媛먯떥???섏삤??寃쎌슦媛� ?덈떎.

    - {"toolAssistantExecutionProcess": {"RESUME_WORKER": false, ...}}

    濡쒖뺄 ?ㅽ겕由쏀듃???ㅼ젣 ?댁쓣 ?ㅽ뻾?섏? ?딆쑝誘�濡? ???섑띁瑜?踰쀪꺼??湲곗〈 濡쒖쭅??湲곕??섎뒗
    理쒖긽????RESUME_WORKER, URL_WORKER, RECRUIT_WIKI_WORKER, reason)瑜??삳뒗??
    """
    wrapped = result.get("toolAssistantExecutionProcess")
    if isinstance(wrapped, dict):
        return wrapped
    return result


# =============================================================================
# Orchestrator / URL Agent / Pipeline ?묐떟 ?곗씠??援ъ“
# =============================================================================

@dataclass
class OrchestratorResponse:
    """Orchestrator ?묐떟 ?곗씠???대옒??(遺덈━??留ㅽ븨)"""
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
    """URL Agent ?묐떟 ?곗씠???대옒??""
    query: str                      # ?먮낯 ?ъ슜??吏덉쓽
    url: str                        # 留ㅼ묶??URL
    reason: str                     # 留ㅼ묶 ?댁쑀
    matched_name: str               # 留ㅼ묶??湲곕뒫紐?
    plan_id_required: bool          # planId ?꾩슂 ?щ?
    plan_id: Optional[str] = None   # 異붿텧??planId (?녿뒗 寃쎌슦 None)
    error: Optional[str] = None     # ?먮윭 硫붿떆吏� (?덈뒗 寃쎌슦)
    latency: float = 0.0


@dataclass
class WikiAgentResponse:
    """Wiki Agent ?묐떟 ?곗씠???대옒??""
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
    """Orchestrator -> URL Agent ?뚯씠?꾨씪??寃곌낵"""
    query: str
    selected_agent_id: str
    orchestrator_reason: str
    url: str
    url_reason: str
    matched_name: str
    plan_id_required: bool
    plan_id: Optional[str] = None

    # WIKI Agent 寃곌낵 (RECRUIT_WIKI_WORKER ?좏깮 ??
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
    """
    Orchestrator Agent

    ?ъ슜??吏덉쓽(諛??�???덉뒪?좊━)瑜?湲곕컲?쇰줈 Worker瑜?1媛??좏깮?쒕떎.
    異쒕젰?� 遺덈━??留ㅽ븨(JSON)?쇰줈 怨좎젙?쒕떎.
    """

    _PRIORITY_ORDER = ["RESUME_WORKER", "URL_WORKER", "RECRUIT_WIKI_WORKER"]

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-5.2",
        prompt_file: Optional[Path] = None,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None

        self.prompt_file = prompt_file or ORCHESTRATOR_PROMPT_FILE_PATH
        self._prompt_cache: Optional[str] = None

    def reload_prompt(self) -> None:
        """?꾨＼?꾪듃 罹먯떆瑜?臾댄슚?뷀븯怨??ㅼ떆 濡쒕뱶?섎룄濡??ㅼ젙"""
        self._prompt_cache = None

    def _load_prompt(self) -> str:
        if self._prompt_cache is not None:
            return self._prompt_cache

        if not self.prompt_file.exists():
            raise FileNotFoundError(f"Orchestrator ?꾨＼?꾪듃 ?뚯씪??李얠쓣 ???놁쓬: {self.prompt_file}")

        self._prompt_cache = self.prompt_file.read_text(encoding="utf-8")
        return self._prompt_cache

    def get_system_prompt(self) -> str:
        """?꾩옱 Orchestrator ?꾨＼?꾪듃瑜?諛섑솚 (?붾쾭源??뺤씤??"""
        return self._load_prompt()

    @classmethod
    def _resolve_selected_agent_id(cls, resume: bool, url: bool, wiki: bool) -> str:
        mapping = {
            "RESUME_WORKER": resume,
            "URL_WORKER": url,
            "RECRUIT_WIKI_WORKER": wiki,
        }

        selected = [k for k, v in mapping.items() if v]
        if len(selected) == 1:
            return selected[0]
        if len(selected) == 0:
            return "NONE"

        # 鍮꾩젙??蹂듭닔 true)??寃쎌슦 ?곗꽑?쒖쐞濡?蹂댁젙?쒕떎.
        for agent_id in cls._PRIORITY_ORDER:
            if mapping.get(agent_id) is True:
                return agent_id
        return "NONE"

    def route(self, query: str, conversation_history: Optional[str] = None) -> OrchestratorResponse:
        start_time = time.perf_counter()
        if not self.client:
            return OrchestratorResponse(
                query=query,
                resume_worker=False,
                url_worker=False,
                recruit_wiki_worker=False,
                reason="",
                selected_agent_id="NONE",
                error="OpenAI API ?ㅺ? ?ㅼ젙?섏? ?딆쓬. OPENAI_API_KEY ?섍꼍蹂�?섎? ?ㅼ젙?섍굅??api_key ?뚮씪誘명꽣瑜??꾨떖?섏꽭??",
                latency=0.0,
            )

        try:
            system_prompt = self._load_prompt()
            history_text = conversation_history.strip() if conversation_history else ""
            user_content = (
                "?�???덉뒪?좊━:\n"
                f"{history_text if history_text else '(?놁쓬)'}\n\n"
                "?ъ슜???붿껌:\n"
                f"{query}"
            )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _ensure_json_word_in_prompt(system_prompt)},
                    {"role": "user", "content": user_content},
                ],
                response_format={"type": "json_object"},
            )
            
            # API ?몄텧 ?꾨즺 ?쒓컙 痢≪젙
            end_time = time.perf_counter()
            latency = end_time - start_time

            content = response.choices[0].message.content or ""
            parsed, warning = _parse_first_json_object(content)
            result = _normalize_orchestrator_result(parsed)

            resume_worker = bool(result.get("RESUME_WORKER", False))
            url_worker = bool(result.get("URL_WORKER", False))
            recruit_wiki_worker = bool(result.get("RECRUIT_WIKI_WORKER", False))
            reason = str(result.get("reason", "")).strip()

            selected_agent_id = self._resolve_selected_agent_id(
                resume=resume_worker,
                url=url_worker,
                wiki=recruit_wiki_worker,
            )

            # toolAssistantExecutionProcess ?섑띁媛� JSON ?ㅼ뿉 異붽?濡?遺숇뒗 耳�?댁뒪媛� ?덉뼱 warning??諛쒖깮?????덈떎.
            # ??寃쎌슦 湲곕뒫??臾몄젣???꾨땲誘�濡? ?붾쾭源낆뿉留??꾩????섎룄濡?warning ?띿뒪?몃? 遺�?쒕읇寃??좎??쒕떎.
            error = warning
            if sum([resume_worker, url_worker, recruit_wiki_worker]) > 1:
                multi_true_msg = "Orchestrator 異쒕젰???щ윭 Agent瑜?true濡??ㅼ젙?섏뿬 ?곗꽑?쒖쐞濡?蹂댁젙?덈떎."
                error = f"{error} / {multi_true_msg}" if error else multi_true_msg

            return OrchestratorResponse(
                query=query,
                resume_worker=resume_worker,
                url_worker=url_worker,
                recruit_wiki_worker=recruit_wiki_worker,
                reason=reason,
                selected_agent_id=selected_agent_id,
                error=error,
                latency=latency,
            )

        except json.JSONDecodeError as e:
            return OrchestratorResponse(
                query=query,
                resume_worker=False,
                url_worker=False,
                recruit_wiki_worker=False,
                reason="",
                selected_agent_id="NONE",
                error=f"Orchestrator JSON ?뚯떛 ?ㅻ쪟: {str(e)}",
                latency=time.perf_counter() - start_time,
            )
        except FileNotFoundError as e:
            return OrchestratorResponse(
                query=query,
                resume_worker=False,
                url_worker=False,
                recruit_wiki_worker=False,
                reason="",
                selected_agent_id="NONE",
                error=str(e),
                latency=time.perf_counter() - start_time,
            )
        except Exception as e:
            return OrchestratorResponse(
                query=query,
                resume_worker=False,
                url_worker=False,
                recruit_wiki_worker=False,
                reason="",
                selected_agent_id="NONE",
                error=f"Orchestrator API ?몄텧 ?ㅻ쪟: {str(e)}",
                latency=time.perf_counter() - start_time,
            )


# =============================================================================
# URL Navigation Agent
# =============================================================================

class AXURLAgent:
    """
    AX URL Navigation Agent
    
    ?ъ슜??吏덉쓽瑜?遺꾩꽍?섏뿬 ?곹빀??URL??諛섑솚?섎뒗 ?먯씠?꾪듃.
    OpenAI API瑜??ъ슜?섏뿬 ?먯뿰???댄빐 諛?URL 留ㅼ묶???섑뻾?쒕떎.
    """
    
    def __init__(
        self, 
        api_key: Optional[str] = None, 
        model: str = "gpt-5.2",
        prompt_file: Optional[Path] = None,
        url_reference_file: Optional[Path] = None
    ):
        """
        Args:
            api_key: OpenAI API ??(None?대㈃ ?섍꼍蹂�?섏뿉??媛�?몄샂)
            model: ?ъ슜??OpenAI 紐⑤뜽紐?
            prompt_file: ?꾨＼?꾪듃 ?뚯씪 寃쎈줈 (None?대㈃ 湲곕낯 寃쎈줈 ?ъ슜)
            url_reference_file: URL Reference ?뚯씪 寃쎈줈 (None?대㈃ 湲곕낯 寃쎈줈 ?ъ슜)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None
        
        # ?꾨＼?꾪듃 諛?URL Reference ?뚯씪 寃쎈줈 ?ㅼ젙
        self.prompt_file = prompt_file or PROMPT_FILE_PATH
        self.url_reference_file = url_reference_file or URL_REFERENCE_FILE_PATH
        
        # ?꾨＼?꾪듃 罹먯떆 (理쒖큹 ?몄텧 ??濡쒕뱶)
        self._prompt_cache: Optional[str] = None
        self._url_reference_cache: Optional[str] = None
    
    def _load_prompt_template(self) -> str:
        """
        prompt.md ?뚯씪?먯꽌 ?꾨＼?꾪듃 ?쒗뵆由우쓣 濡쒕뱶
        
        Returns:
            str: ?꾨＼?꾪듃 ?쒗뵆由?臾몄옄??
        
        Raises:
            FileNotFoundError: ?꾨＼?꾪듃 ?뚯씪??議댁옱?섏? ?딅뒗 寃쎌슦
        """
        if self._prompt_cache is not None:
            return self._prompt_cache
        
        if not self.prompt_file.exists():
            # ?명솚?? 怨쇨굅 寃쎈줈(prompt.md)瑜?吏�?뺥뻽嫄곕굹, ?섍꼍???곕씪 ?뚯씪???꾨씫?????덈떎.
            # 媛�?ν븳 寃쎌슦 ?뺣낯 ?꾨＼?꾪듃(prompt_url_worker.md)濡??먮룞 ?대갚?쒕떎.
            fallback = URL_WORKER_PROMPT_FILE_PATH
            if fallback.exists():
                self.prompt_file = fallback
            else:
                raise FileNotFoundError(f"?꾨＼?꾪듃 ?뚯씪??李얠쓣 ???놁쓬: {self.prompt_file}")
        
        self._prompt_cache = self.prompt_file.read_text(encoding="utf-8")
        return self._prompt_cache
    
    def _load_url_reference_markdown(self) -> str:
        """
        url_reference.md ?뚯씪?먯꽌 URL Reference瑜?濡쒕뱶
        
        Returns:
            str: URL Reference 留덊겕?ㅼ슫 臾몄옄??
        
        Raises:
            FileNotFoundError: URL Reference ?뚯씪??議댁옱?섏? ?딅뒗 寃쎌슦
        """
        if self._url_reference_cache is not None:
            return self._url_reference_cache
        
        if not self.url_reference_file.exists():
            raise FileNotFoundError(f"URL Reference ?뚯씪??李얠쓣 ???놁쓬: {self.url_reference_file}")
        
        self._url_reference_cache = self.url_reference_file.read_text(encoding="utf-8")
        return self._url_reference_cache
    
    def _build_system_prompt(self) -> str:
        """
        ?쒖뒪???꾨＼?꾪듃 ?앹꽦
        
        prompt.md ?뚯씪??濡쒕뱶?섍퀬, {url_reference} ?뚮젅?댁뒪?�?붾?
        ?ㅼ젣 URL Reference ?댁슜?쇰줈 移섑솚
        """
        try:
            # prompt.md ?뚯씪 濡쒕뱶
            prompt_template = self._load_prompt_template()
            
            # URL Reference 濡쒕뱶
            url_ref_text = self._load_url_reference_markdown()
            
            # ?뚮젅?댁뒪?�??移섑솚
            system_prompt = prompt_template.replace("{url_reference}", url_ref_text)
            
            return system_prompt
            
        except FileNotFoundError as e:
            # ?뚯씪???녿뒗 寃쎌슦 ?먮윭 諛쒖깮
            raise FileNotFoundError(
                f"{e}\n\n"
                "prompt.md?� url_reference.md ?뚯씪???꾩슂?⑸땲??\n"
                "?뚯씪 寃쎈줈瑜??뺤씤?섍굅??prompt_file, url_reference_file ?뚮씪誘명꽣瑜?吏�?뺥븯?몄슂."
            )
    
    def reload_prompt(self) -> None:
        """?꾨＼?꾪듃 罹먯떆瑜?臾댄슚?뷀븯怨??ㅼ떆 濡쒕뱶?섎룄濡??ㅼ젙"""
        self._prompt_cache = None
        self._url_reference_cache = None
    
    def get_system_prompt(self) -> str:
        """?꾩옱 ?쒖뒪???꾨＼?꾪듃瑜?諛섑솚 (?붾쾭源??뺤씤??"""
        return self._build_system_prompt()
    
    def analyze_query(self, query: str, plan_id: Optional[str] = None) -> URLAgentResponse:
        """
        ?ъ슜??吏덉쓽瑜?遺꾩꽍?섏뿬 ?곹빀??URL??諛섑솚
        
        Args:
            query: ?ъ슜??吏덉쓽
            plan_id: ?꾩옱 ?좏깮??梨꾩슜(?뚮줈?? ID (?좏깮 ?ы빆)
        
        Returns:
            URLAgentResponse: URL 留ㅼ묶 寃곌낵
        """
        start_time = time.perf_counter()
        if not self.client:
            return URLAgentResponse(
                query=query,
                url="",
                reason="",
                matched_name="",
                plan_id_required=False,
                error="OpenAI API ?ㅺ? ?ㅼ젙?섏? ?딆쓬. OPENAI_API_KEY ?섍꼍蹂�?섎? ?ㅼ젙?섍굅??api_key ?뚮씪誘명꽣瑜??꾨떖?섏꽭??",
                latency=0.0
            )
        
        try:
            # OpenAI API ?몄텧 (GPT-5 ?명솚)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _ensure_json_word_in_prompt(self._build_system_prompt())},
                    {"role": "user", "content": query}
                ],
                response_format={"type": "json_object"}
            )
            
            end_time = time.perf_counter()
            latency = end_time - start_time
            
            # ?묐떟 ?뚯떛
            content = response.choices[0].message.content or ""
            result, warning = _parse_first_json_object(content)
            
            url = result.get("url", "")
            reason = result.get("reason", "")
            matched_name = result.get("matched_name", "")
            plan_id_required = result.get("plan_id_required", False)
            extracted_plan_id = result.get("plan_id")
            
            # planId 移섑솚 (?꾩슂??寃쎌슦)
            # 1. ?꾨＼?꾪듃媛� 異붿텧??plan_id媛� ?덉쑝硫?洹멸쾬???곗꽑 ?ъ슜
            # 2. ?놁쑝硫??몄옄濡??꾨떖??plan_id ?ъ슜
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
                latency=latency
            )
            
        except json.JSONDecodeError as e:
            return URLAgentResponse(
                query=query,
                url="",
                reason="",
                matched_name="",
                plan_id_required=False,
                error=f"JSON ?뚯떛 ?ㅻ쪟: {str(e)}",
                latency=time.perf_counter() - start_time
            )
        except FileNotFoundError as e:
            return URLAgentResponse(
                query=query,
                url="",
                reason="",
                matched_name="",
                plan_id_required=False,
                error=str(e),
                latency=time.perf_counter() - start_time
            )
        except Exception as e:
            return URLAgentResponse(
                query=query,
                url="",
                reason="",
                matched_name="",
                plan_id_required=False,
                error=f"API ?몄텧 ?ㅻ쪟: {str(e)}",
                latency=time.perf_counter() - start_time
            )
    
    def bulk_analyze(
        self, 
        queries: list[str], 
        plan_id: Optional[str] = None,
        verbose: bool = True
    ) -> list[URLAgentResponse]:
        """
        ?щ윭 吏덉쓽瑜?踰뚰겕濡?遺꾩꽍
        
        Args:
            queries: ?ъ슜??吏덉쓽 由ъ뒪??
            plan_id: ?꾩옱 ?좏깮??梨꾩슜(?뚮줈?? ID
            verbose: 吏꾪뻾 ?곹솴 異쒕젰 ?щ?
        
        Returns:
            list[URLAgentResponse]: URL 留ㅼ묶 寃곌낵 由ъ뒪??
        """
        results = []
        total = len(queries)
        
        for idx, query in enumerate(queries, 1):
            if verbose:
                print(f"[{idx}/{total}] 遺꾩꽍 以? {query[:50]}...")
            
            result = self.analyze_query(query, plan_id)
            results.append(result)
        
        return results


# =============================================================================
# Recruit Wiki Agent
# =============================================================================

class AXWikiAgent:
    """
    AX Recruit Wiki Agent

    Orchestrator媛� RECRUIT_WIKI_WORKER濡??쇱슦?낇뻽?????숈옉?쒕떎.

    泥섎━ ?먮쫫:
    1) Query Analyzer(OpenAI): ?ъ슜??吏덉쓽 -> 寃�?됱뼱(q), ?쒓렇(tag) 異붿텧 (JSON)
    2) Search API(requests): q/tag濡?Knowledge Base 臾몄꽌 寃�??
    3) Synthesizer(OpenAI): 寃�??臾몄꽌瑜?洹쇨굅濡?理쒖쥌 ?듬? ?앹꽦
    """

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
    ):
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
        """?꾨＼?꾪듃 罹먯떆瑜?臾댄슚?뷀븯怨??ㅼ떆 濡쒕뱶?섎룄濡??ㅼ젙"""
        self._query_analyzer_prompt_cache = None
        self._synthesizer_prompt_cache = None

    def _load_query_analyzer_prompt(self) -> str:
        if self._query_analyzer_prompt_cache is not None:
            return self._query_analyzer_prompt_cache
        if not self.query_analyzer_prompt_file.exists():
            raise FileNotFoundError(f"Wiki Query Analyzer ?꾨＼?꾪듃 ?뚯씪??李얠쓣 ???놁쓬: {self.query_analyzer_prompt_file}")
        self._query_analyzer_prompt_cache = self.query_analyzer_prompt_file.read_text(encoding="utf-8")
        return self._query_analyzer_prompt_cache

    def _load_synthesizer_prompt(self) -> str:
        if self._synthesizer_prompt_cache is not None:
            return self._synthesizer_prompt_cache
        if not self.synthesizer_prompt_file.exists():
            raise FileNotFoundError(f"Wiki Synthesizer ?꾨＼?꾪듃 ?뚯씪??李얠쓣 ???놁쓬: {self.synthesizer_prompt_file}")
        self._synthesizer_prompt_cache = self.synthesizer_prompt_file.read_text(encoding="utf-8")
        return self._synthesizer_prompt_cache

    @staticmethod
    def _normalize_tag(tag_value: Any) -> tuple[Optional[str], Optional[str]]:
        """
        Query Analyzer 異쒕젰??tag???꾨＼?꾪듃 ??臾몄옄?댁쓣 湲곕??섏?留?
        ?덉쇅?곸쑝濡?list ?먮뒗 肄ㅻ쭏 援щ텇 臾몄옄?댁씠 ?ㅼ뼱?????덈떎.

        Returns:
            - tag_for_search: Search API???꾨떖???쒓렇(媛�?ν븯硫?1媛?
            - tag_display: ?먮낯 ?섎?瑜?理쒕???蹂댁〈???쒖떆???쒓렇
        """
        if tag_value is None:
            return None, None

        # list ?뺥깭: 泥???ぉ??寃�???쒓렇濡??ъ슜?섍퀬, ?쒖떆?⑹? 蹂묓빀?쒕떎.
        if isinstance(tag_value, list):
            cleaned = [str(x).strip() for x in tag_value if str(x).strip()]
            if not cleaned:
                return None, None
            return cleaned[0], ", ".join(cleaned)

        # 臾몄옄???뺥깭
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
        """
        Query Analyzer瑜??몄텧?섏뿬 寃�?됱뼱(q)?� ?쒓렇(tag)瑜?異붿텧?쒕떎.

        Returns:
            (q, tag_for_search, tag_display, latency_s)
        """
        start_time = time.perf_counter()
        if not self.client:
            raise RuntimeError(
                "OpenAI API ?ㅺ? ?ㅼ젙?섏? ?딆쓬. OPENAI_API_KEY ?섍꼍蹂�?섎? ?ㅼ젙?섍굅??api_key ?뚮씪誘명꽣瑜??꾨떖?섏꽭??"
            )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": _ensure_json_word_in_prompt(self._load_query_analyzer_prompt())},
                {"role": "user", "content": query},
            ],
            response_format={"type": "json_object"},
        )
        latency = time.perf_counter() - start_time

        content = response.choices[0].message.content or ""
        try:
            result, _warning = _parse_first_json_object(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Wiki Query Analyzer JSON ?뚯떛 ?ㅻ쪟: {str(e)}") from e

        q_val = result.get("q")
        if not isinstance(q_val, str) or not q_val.strip():
            raise ValueError(f"Wiki Query Analyzer 異쒕젰??q媛� ?녾굅??鍮꾩젙?곸씠?? {result}")

        tag_for_search, tag_display = self._normalize_tag(result.get("tag"))
        return q_val.strip(), tag_for_search, tag_display, latency

    def _search_documents(self, q: str, tag_for_search: Optional[str]) -> tuple[dict[str, Any], float]:
        """
        Search API瑜??몄텧?쒕떎.

        Returns:
            (response_json, latency_s, request_url, request_params)
        """
        if requests is None:
            raise RuntimeError("requests ?쇱씠釉뚮윭由щ? 李얠쓣 ???놁뒿?덈떎. Wiki Search API ?몄텧???꾪빐 requests ?ㅼ튂媛� ?꾩슂?⑸땲??")

        start_time = time.perf_counter()

        params: dict[str, Any] = {
            "q": q,
            "fetch_limit": self.fetch_limit,
            "limit": self.limit,
            "body": "true" if self.body else "false",
        }
        # tag媛� None?대㈃ ?꾪꽣留곸쓣 嫄대꼫?곕룄濡??뚮씪誘명꽣瑜??앸왂?쒕떎.
        if tag_for_search is not None:
            params["tag"] = tag_for_search

        try:
            resp = requests.get(self.search_api_url, params=params, timeout=self.request_timeout_s)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            # ?ㅽ듃?뚰겕/HTTP/JSON ?뚯떛 ?ㅻ쪟瑜??듯빀 硫붿떆吏�濡??꾨떖?쒕떎.
            raise RuntimeError(f"Wiki Search API ?몄텧 ?ㅻ쪟: {str(e)}") from e

        latency = time.perf_counter() - start_time
        if not isinstance(data, dict):
            raise ValueError("Wiki Search API ?묐떟??JSON object ?뺥깭媛� ?꾨땲??")

        return data, latency, getattr(resp, "url", None), params

    def _synthesize_answer(self, user_query: str, documents: list[dict[str, Any]]) -> tuple[str, float]:
        """
        Synthesizer瑜??몄텧?섏뿬 理쒖쥌 ?듬????앹꽦?쒕떎.

        臾몄꽌 湲곕컲 ?듬? ?먯튃?� ?꾨＼?꾪듃???섑빐 媛뺤젣?섎?濡? ?ш린?쒕뒗 臾몄꽌 results 諛곗뿴留??꾨떖?쒕떎.
        """
        start_time = time.perf_counter()
        if not self.client:
            raise RuntimeError(
                "OpenAI API ?ㅺ? ?ㅼ젙?섏? ?딆쓬. OPENAI_API_KEY ?섍꼍蹂�?섎? ?ㅼ젙?섍굅??api_key ?뚮씪誘명꽣瑜??꾨떖?섏꽭??"
            )

        # Synthesizer ?꾨＼?꾪듃???쒗뵆由??뺥깭吏�留? ?덉쟾?섍쾶 user 硫붿떆吏�?먯꽌 ?낅젰???꾨떖?쒕떎.
        user_content = (
            "?ъ슜??吏덈Ц:\n"
            f"{user_query}\n\n"
            "寃�?됰맂 臾몄꽌:\n"
            f"{json.dumps(documents, ensure_ascii=False)}"
        )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self._load_synthesizer_prompt()},
                {"role": "user", "content": user_content},
            ],
        )
        latency = time.perf_counter() - start_time

        answer = (response.choices[0].message.content or "").strip()
        return answer, latency

    def process(self, query: str) -> WikiAgentResponse:
        """
        Wiki ?뚯씠?꾨씪?몄쓣 ?ㅽ뻾?쒕떎.

        Returns:
            WikiAgentResponse
        """
        overall_start = time.perf_counter()

        try:
            analyzed_q, tag_for_search, tag_display, qa_latency = self._analyze_query(query=query)
            search_json, search_latency, request_url, request_params = self._search_documents(
                q=analyzed_q,
                tag_for_search=tag_for_search,
            )

            results = search_json.get("results", [])
            if not isinstance(results, list):
                raise ValueError("Wiki Search API ?묐떟??results媛� 諛곗뿴 ?뺥깭媛� ?꾨땲??")

            # 臾몄꽌 寃곌낵??Synthesizer??洹몃?濡??꾨떖?쒕떎. (body ?ы븿)
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
            # ?먮윭 ?곹솴?먯꽌??媛�?ν븳 ??吏꾨떒???꾩????섎뒗 ?뺣낫瑜?諛섑솚?쒕떎.
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
# Orchestrator -> URL Agent ?뚯씠?꾨씪??
# =============================================================================

class AXNavigationPipeline:
    """Orchestrator -> URL Agent ?뚯씠?꾨씪?몄쓣 臾띠뼱???ㅽ뻾?쒕떎."""

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
    ):
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
        """
        ?ъ슜??吏덉쓽???�??Orchestrator瑜??듯빐 Worker瑜??좏깮?섍퀬,
        URL_WORKER???뚮쭔 URL Agent瑜??몄텧??URL??異붿쿇?쒕떎.
        """
        start_time = time.perf_counter()
        
        if direct_url_agent:
            url_res = self.url_agent.analyze_query(query=query, plan_id=plan_id)
            total_latency = time.perf_counter() - start_time
            
            if url_res.error:
                return NavigationPipelineResponse(
                    query=query,
                    selected_agent_id="URL_WORKER",
                    orchestrator_reason="(吏곸젒 ?ㅽ뻾: Orchestrator ?앸왂)",
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
                orchestrator_reason="(吏곸젒 ?ㅽ뻾: Orchestrator ?앸왂)",
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
        if orch.error and orch.selected_agent_id == "NONE":
            total_latency = time.perf_counter() - start_time
            return NavigationPipelineResponse(
                query=query,
                selected_agent_id="NONE",
                orchestrator_reason=orch.reason,
                url="",
                url_reason="",
                matched_name="",
                plan_id_required=False,
                error=orch.error,
                total_latency=total_latency,
                orchestrator_latency=orch.latency,
                url_agent_latency=0.0,
            )

        selected_agent_id = orch.selected_agent_id
        orchestrator_reason = orch.reason

        # Wiki Agent
        if selected_agent_id == "RECRUIT_WIKI_WORKER":
            wiki_res = self.wiki_agent.process(query=query)
            total_latency = time.perf_counter() - start_time

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

        # URL_WORKER媛� ?꾨땲硫?URL 異붿쿇?� ?ㅽ뻾?섏? ?딅뒗??
        if selected_agent_id != "URL_WORKER":
            total_latency = time.perf_counter() - start_time
            return NavigationPipelineResponse(
                query=query,
                selected_agent_id=selected_agent_id,
                orchestrator_reason=orchestrator_reason,
                url="",
                url_reason="",
                matched_name="",
                plan_id_required=False,
                error=None,
                total_latency=total_latency,
                orchestrator_latency=orch.latency,
                url_agent_latency=0.0,
            )

        url_res = self.url_agent.analyze_query(query=query, plan_id=plan_id)
        total_latency = time.perf_counter() - start_time
        
        if url_res.error:
            return NavigationPipelineResponse(
                query=query,
                selected_agent_id=selected_agent_id,
                orchestrator_reason=orchestrator_reason,
                url="",
                url_reason="",
                matched_name="",
                plan_id_required=False,
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

    def bulk_recommend(
        self,
        queries: list[str],
        plan_id: Optional[str] = None,
        conversation_history: Optional[str] = None,
        verbose: bool = True,
        direct_url_agent: bool = False,
    ) -> list[NavigationPipelineResponse]:
        results: list[NavigationPipelineResponse] = []
        total = len(queries)

        for idx, query in enumerate(queries, 1):
            if verbose:
                print(f"[{idx}/{total}] 遺꾩꽍 以? {query[:50]}...")
            results.append(
                self.recommend(
                    query=query,
                    plan_id=plan_id,
                    conversation_history=conversation_history,
                    direct_url_agent=direct_url_agent,
                )
            )
        return results


# =============================================================================
# 寃곌낵 異쒕젰 ?좏떥由ы떚
# =============================================================================

def print_results(results: list[NavigationPipelineResponse], format: str = "table") -> None:
    """
    遺꾩꽍 寃곌낵瑜?異쒕젰
    
    Args:
        results: NavigationPipelineResponse 由ъ뒪??
        format: 異쒕젰 ?뺤떇 ("table", "detail", "json")
    """
    if format == "json":
        output = []
        for r in results:
            output.append({
                "query": r.query,
                "selected_agent_id": r.selected_agent_id,
                "orchestrator_reason": r.orchestrator_reason,
                "url": r.url,
                "url_reason": r.url_reason,
                "matched_name": r.matched_name,
                "plan_id_required": r.plan_id_required,
                "plan_id": r.plan_id,
                "error": r.error,
                "total_latency": r.total_latency,
                "orchestrator_latency": r.orchestrator_latency,
                "url_agent_latency": r.url_agent_latency,
            })
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return
    
    if format == "detail":
        for idx, r in enumerate(results, 1):
            print(f"\n{'='*60}")
            print(f"[{idx}] 吏덉쓽: {r.query}")
            print(f"{'='*60}")
            if r.error:
                print(f"?ㅻ쪟: {r.error}")
            print(f"?좏깮 Agent: {r.selected_agent_id}")
            if r.orchestrator_reason:
                print(f"Orchestrator ?댁쑀: {r.orchestrator_reason}")
            if r.selected_agent_id == "URL_WORKER" and not r.error:
                print(f"留ㅼ묶 湲곕뒫: {r.matched_name}")
                print(f"URL: {r.url}")
                print(f"URL ?댁쑀: {r.url_reason}")
                if r.plan_id_required:
                    plan_msg = f"(planId: {r.plan_id})" if r.plan_id else "(planId ?꾩슂)"
                    print(plan_msg)
            elif r.selected_agent_id == "RECRUIT_WIKI_WORKER" and not r.error:
                analyzed_q = r.wiki_analyzed_query or "-"
                analyzed_tag = r.wiki_analyzed_tag or "-"
                print(f"遺꾩꽍 寃�?됱뼱(q): {analyzed_q}")
                print(f"?쒓렇(tag): {analyzed_tag}")
                if r.wiki_search_results_count is not None:
                    print(f"寃�??寃곌낵 ?? {r.wiki_search_results_count}")
                if r.wiki_answer:
                    print("?듬?:")
                    print(r.wiki_answer)
            elif r.selected_agent_id != "URL_WORKER":
                print("URL 異붿쿇?� ?ㅽ뻾?섏? ?딆븯?? (?좏깮 Agent媛� URL_WORKER媛� ?꾨떂)")
        return
    
    # 湲곕낯: table ?뺤떇
    print("\n" + "="*140)
    print(f"{'No.':<4} {'吏덉쓽':<30} {'?좏깮 Agent':<16} {'URL':<45} {'planId':<10} {'Latency(s)':<10}")
    print("="*140)
    
    for idx, r in enumerate(results, 1):
        query_display = r.query[:28] + ".." if len(r.query) > 30 else r.query
        url_value = r.url if r.url else "-"
        url_display = url_value[:43] + ".." if len(url_value) > 45 else url_value
        
        # planId ?쒖떆 濡쒖쭅 ?섏젙
        plan_id_display = "-"
        if r.plan_id_required:
            plan_id_display = str(r.plan_id) if r.plan_id else "?꾩슂(誘몄엯??"
            
        agent_display = r.selected_agent_id[:14] if r.selected_agent_id else "NONE"
        latency_display = f"{r.total_latency:.2f}"
        
        if r.error:
            print(f"{idx:<4} {query_display:<30} {agent_display:<16} {'[?ㅻ쪟] ' + r.error[:35]:<45} {'':<10} {latency_display:<10}")
        else:
            print(f"{idx:<4} {query_display:<30} {agent_display:<16} {url_display:<45} {plan_id_display:<10} {latency_display:<10}")
    
    print("="*140)
    
    # ?곸꽭 ?댁쑀 異쒕젰
    print("\n[?댁쑀]")
    for idx, r in enumerate(results, 1):
        if r.error:
            continue
        if r.selected_agent_id == "URL_WORKER":
            print(f"{idx}. [ORCH] {r.orchestrator_reason} / [URL] {r.url_reason}")
        elif r.selected_agent_id == "RECRUIT_WIKI_WORKER":
            print(f"{idx}. [ORCH] {r.orchestrator_reason}")
        else:
            print(f"{idx}. [ORCH] {r.orchestrator_reason}")


# =============================================================================
# ?뚯뒪?몄슜 ?덉떆 吏덉쓽
# =============================================================================

SAMPLE_QUERIES = [
    "채용 만들고 싶어",
    "지원자 보여줘",
    "지원서 템플릿이 뭐야?",
    "공고명 바꾸고 싶어",
    "메시지 템플릿 관리",
    "면접 일정 조율하고 싶어",
    "역량검사 설정 변경",
    "채용 목록 조회",
    "블라인드 채용 설정",
    "접수 기간 수정",
    "스크리닝이 뭐야?",
    "전형 안내 메일에서 참석여부 회신 결과는 어디서 봐요?",
    "채용 플로우가 무슨 말이야?",
]


# =============================================================================
# 硫붿씤 ?ㅽ뻾
# =============================================================================

def main():
    """硫붿씤 ?ㅽ뻾 ?⑥닔"""
    import argparse
    
    parser = argparse.ArgumentParser(description="AX Navigation Pipeline (Orchestrator -> URL Agent)")
    parser.add_argument(
        "-q", "--query", 
        type=str, 
        help="?⑥씪 吏덉쓽 遺꾩꽍"
    )
    parser.add_argument(
        "-f", "--file", 
        type=str, 
        help="吏덉쓽 紐⑸줉???닿릿 ?뚯씪 寃쎈줈 (??以꾩뿉 ?섎굹??"
    )
    parser.add_argument(
        "-p", "--plan-id", 
        type=str, 
        default=None,
        help="?꾩옱 ?좏깮??梨꾩슜(?뚮줈?? ID"
    )
    parser.add_argument(
        "--format", 
        type=str, 
        choices=["table", "detail", "json"],
        default="table",
        help="異쒕젰 ?뺤떇 (湲곕낯: table)"
    )
    parser.add_argument(
        "--sample", 
        action="store_true",
        help="?섑뵆 吏덉쓽濡??뚯뒪???ㅽ뻾"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-5.2",
        help="?ъ슜??OpenAI 紐⑤뜽 (湲곕낯: gpt-5.2)"
    )
    parser.add_argument(
        "--show-prompt",
        action="store_true",
        help="(?명솚) URL Agent ?쒖뒪???꾨＼?꾪듃瑜?異쒕젰?섍퀬 醫낅즺"
    )
    parser.add_argument(
        "--show-url-prompt",
        action="store_true",
        help="URL Agent ?쒖뒪???꾨＼?꾪듃瑜?異쒕젰?섍퀬 醫낅즺"
    )
    parser.add_argument(
        "--show-orchestrator-prompt",
        action="store_true",
        help="Orchestrator ?꾨＼?꾪듃瑜?異쒕젰?섍퀬 醫낅즺"
    )
    parser.add_argument(
        "--reload-prompt",
        action="store_true",
        help="?꾨＼?꾪듃 罹먯떆瑜?臾댁떆?섍퀬 ?뚯씪?먯꽌 ?ㅼ떆 濡쒕뱶"
    )
    parser.add_argument(
        "--direct-url-agent",
        action="store_true",
        help="Orchestrator瑜??앸왂?섍퀬 URL Agent留?吏곸젒 ?ㅽ뻾"
    )
    
    args = parser.parse_args()
    
    # --show-prompt ??--show-url-prompt???명솚 alias濡?泥섎━?쒕떎.
    if args.show_prompt:
        args.show_url_prompt = True

    pipeline = AXNavigationPipeline(model=args.model)

    # ?꾨＼?꾪듃 由щ줈???듭뀡
    if args.reload_prompt:
        pipeline.reload_prompt()

    # ?꾨＼?꾪듃 異쒕젰 ?듭뀡
    if args.show_orchestrator_prompt:
        try:
            print("=" * 60)
            print("Orchestrator ?꾨＼?꾪듃")
            print("=" * 60)
            print(pipeline.orchestrator.get_system_prompt())
            print("=" * 60)
        except FileNotFoundError as e:
            print(f"[?ㅻ쪟] {e}")
        return

    if args.show_url_prompt:
        try:
            print("=" * 60)
            print("URL Agent ?쒖뒪???꾨＼?꾪듃")
            print("=" * 60)
            print(pipeline.url_agent.get_system_prompt())
            print("=" * 60)
        except FileNotFoundError as e:
            print(f"[?ㅻ쪟] {e}")
        return
    
    # 吏덉쓽 紐⑸줉 寃곗젙
    queries = []
    
    if args.query:
        queries = [args.query]
    elif args.file:
        with open(args.file, "r", encoding="utf-8") as f:
            queries = [line.strip() for line in f if line.strip()]
    elif args.sample:
        queries = SAMPLE_QUERIES
    else:
        print("?ъ슜踰?")
        print("  ?⑥씪 吏덉쓽: python ax_url_agent.py -q '梨꾩슜 留뚮뱾怨??띠뼱'")
        print("  ?뚯씪 ?낅젰: python ax_url_agent.py -f queries.txt")
        print("  ?섑뵆 ?뚯뒪?? python ax_url_agent.py --sample")
        print("\n?듭뀡:")
        print("  -p, --plan-id: ?뚮줈??ID 吏�??(?? -p 123)")
        print("  --format: 異쒕젰 ?뺤떇 (table, detail, json)")
        print("  --model: OpenAI 紐⑤뜽 吏�??(湲곕낯: gpt-5.1)")
        print("  --show-orchestrator-prompt: Orchestrator ?꾨＼?꾪듃 異쒕젰")
        print("  --show-url-prompt: URL Agent ?쒖뒪???꾨＼?꾪듃 異쒕젰")
        print("  --show-prompt: (?명솚) URL Agent ?쒖뒪???꾨＼?꾪듃 異쒕젰")
        print("  --reload-prompt: ?꾨＼?꾪듃 罹먯떆 臾댁떆?섍퀬 ?뚯씪?먯꽌 ?ㅼ떆 濡쒕뱶")
        print("  --direct-url-agent: Orchestrator ?앸왂?섍퀬 URL Agent留??ㅽ뻾")
        return
    
    # 遺꾩꽍 ?ㅽ뻾
    print(f"\n珥?{len(queries)}媛쒖쓽 吏덉쓽瑜?遺꾩꽍?⑸땲??..\n")
    results = pipeline.bulk_recommend(
        queries=queries,
        plan_id=args.plan_id,
        verbose=True,
        direct_url_agent=args.direct_url_agent
    )
    
    # 寃곌낵 異쒕젰
    print_results(results, format=args.format)


if __name__ == "__main__":
    main()
