from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import aiohttp
import pandas as pd
class UrlAgentTester:
    def __init__(self, base_url: str, bearer_token: str, cms_token: str, mrs_session: str, origin: str, referer: str, max_parallel: int = 1):
        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token.strip()
        self.cms_token = cms_token.strip()
        self.mrs_session = mrs_session.strip()
        self.origin = origin.strip()
        self.referer = referer.strip()
        self.semaphore = asyncio.Semaphore(max_parallel)

    def get_headers(self, for_sse: bool = False) -> dict:
        headers = {
            "authorization": f"Bearer {self.bearer_token}",
            "cms-access-token": self.cms_token,
            "mrs-session": self.mrs_session,
            "origin": self.origin,
            "referer": self.referer,
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }
        if for_sse:
            headers["accept"] = "text/event-stream"
        else:
            headers["accept"] = "application/json, text/plain, */*"
            headers["content-type"] = "application/json"
        return headers

    async def send_query(self, session: aiohttp.ClientSession, message: str) -> tuple[Optional[str], str]:
        url = f"{self.base_url}/api/v2/ai/orchestrator/query"
        payload = {"conversationId": None, "userMessage": message}
        try:
            async with session.post(url, headers=self.get_headers(), json=payload, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("conversationId"), ""
                else:
                    error_text = await response.text()
                    return None, f"HTTP {response.status}: {error_text[:200]}"
        except asyncio.TimeoutError:
            return None, "timeout(30s)"
        except Exception as e:
            return None, f"{type(e).__name__}: {str(e)[:120]}"

    async def subscribe_sse_get_buttonurl(self, session: aiohttp.ClientSession, conversation_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/api/v1/ai/orchestrator/chat-room/sse/subscribe"
        params = {"conversationId": conversation_id}

        connect_time: Optional[datetime] = None
        chat_time: Optional[datetime] = None
        button_url: str = ""
        error_msg: str = ""

        buffer = ""
        current_event = None
        last_heartbeat = datetime.now()

        try:
            timeout = aiohttp.ClientTimeout(total=60)
            async with session.get(url, headers=self.get_headers(for_sse=True), params=params, timeout=timeout) as response:
                async for chunk in response.content.iter_any():
                    buffer += chunk.decode("utf-8", errors="ignore")

                    if (datetime.now() - last_heartbeat).total_seconds() > 30:
                        error_msg = "heartbeat timeout(30s)"
                        break

                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        line = line.strip()

                        if line.startswith("event:"):
                            current_event = line.replace("event:", "").strip()
                            if current_event == "CONNECT":
                                connect_time = datetime.now()
                            elif current_event == "HEARTBEAT":
                                last_heartbeat = datetime.now()

                        elif line.startswith("data:"):
                            data_str = line.replace("data:", "", 1).strip()
                            if current_event == "CHAT" and data_str.startswith("{"):
                                try:
                                    data = json.loads(data_str)
                                except Exception:
                                    continue
                                if data.get("messageType") == "ASSISTANT":
                                    chat_time = datetime.now()
                                    assistant = data.get("assistant", {}) or {}
                                    for ui in assistant.get("dataUIList", []) or []:
                                        ui_value = (ui or {}).get("uiValue", {}) or {}
                                        if "buttonUrl" in ui_value:
                                            button_url = str(ui_value["buttonUrl"])
                                            break
                                    rt = "-"
                                    if connect_time and chat_time:
                                        rt = f"{(chat_time - connect_time).total_seconds():.2f}"
                                    return {
                                        "응답시간(초)": rt,
                                        "실제URL": button_url or "-",
                                        "실패사유": "" if button_url else "URL 미반환",
                                    }
        except asyncio.TimeoutError:
            error_msg = "sse timeout(60s)"
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)[:4]}"

        return {"응답시간(초)": "-", "실제URL": "-", "실패사유": error_msg or "알 수 없는 오류"}

    async def run_one(self, session: aiohttp.ClientSession, row: Dict[str, str]) -> Dict[str, Any]:
        async with self.semaphore:
            qid = row.get("ID", "")
            query = row.get("질의", "")
            expected_url = row.get("기대URL", "")

            conv_id, err = await self.send_query(session, query)
            if not conv_id:
                return {
                    "ID": qid,
                    "질의": query,
                    "기대URL": expected_url,
                    "성공여부": "FAIL",
                    "실패사유": err,
                    "실제URL": "-",
                    "응답시간(초)": "-",
                }

            r = await self.subscribe_sse_get_buttonurl(session, conv_id)
            actual = r.get("실제URL", "-")
            success = "PASS"
            fail_reason = ""
            if expected_url:
                # 단순 포함/정규식 둘 다 지원 (정규식: /.../ 형태)
                if expected_url.startswith("/") and expected_url.endswith("/") and len(expected_url) > 2:
                    pat = expected_url[1:-1]
                    try:
                        if not re.search(pat, actual):
                            success = "FAIL"
                            fail_reason = "정규식 불일치"
                    except re.error:
                        success = "FAIL"
                        fail_reason = "정규식 오류"
                else:
                    if expected_url not in actual:
                        success = "FAIL"
                        fail_reason = "URL 불일치"
            if r.get("실패사유"):
                success = "FAIL"
                fail_reason = r.get("실패사유")

            return {
                "ID": qid,
                "질의": query,
                "기대URL": expected_url,
                "성공여부": success,
                "실패사유": fail_reason,
                "실제URL": actual,
                "응답시간(초)": r.get("응답시간(초)", "-"),
            }


async def run_url_tests_async(
    rows: List[Dict[str, str]],
    tester: UrlAgentTester,
    progress_cb: Optional[Callable[[int, int, str], None]] = None,
) -> pd.DataFrame:
    connector = aiohttp.TCPConnector(limit=50, ssl=False)
    timeout = aiohttp.ClientTimeout(total=120)
    results: List[Dict[str, Any]] = []

    total = len(rows)
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        tasks = [asyncio.create_task(tester.run_one(session, r)) for r in rows]
        done = 0
        for fut in asyncio.as_completed(tasks):
            res = await fut
            results.append(res)
            done += 1
            if progress_cb:
                progress_cb(done, total, f"[{res.get('ID')}] url test done ({res.get('성공여부')})")
    return pd.DataFrame(results)


