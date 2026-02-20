from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional, Tuple

import aiohttp

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


def extract_usage_fields(resp_json: Dict[str, Any]) -> Dict[str, int]:
    usage = (resp_json or {}).get("usage") or {}
    if not isinstance(usage, dict):
        usage = {}

    input_tokens = usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0
    output_tokens = usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0
    total_tokens = usage.get("total_tokens", 0) or 0
    input_details = usage.get("input_tokens_details", usage.get("prompt_tokens_details", {})) or {}
    output_details = usage.get("output_tokens_details", usage.get("completion_tokens_details", {})) or {}
    cached_tokens = input_details.get("cached_tokens", 0) if isinstance(input_details, dict) else 0
    reasoning_tokens = output_details.get("reasoning_tokens", 0) if isinstance(output_details, dict) else 0

    def _to_int(value: Any) -> int:
        try:
            return int(value)
        except Exception:
            try:
                return int(float(value))
            except Exception:
                return 0

    return {
        "input_tokens": _to_int(input_tokens),
        "output_tokens": _to_int(output_tokens),
        "cached_tokens": _to_int(cached_tokens),
        "reasoning_tokens": _to_int(reasoning_tokens),
        "total_tokens": _to_int(total_tokens),
    }


def extract_openai_output_text(resp_json: Dict[str, Any]) -> str:
    if isinstance(resp_json, dict) and isinstance(resp_json.get("output_text"), str):
        return resp_json["output_text"]

    output = resp_json.get("output", [])
    chunks: list[str] = []
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "message":
                content = item.get("content", [])
                if isinstance(content, list):
                    for node in content:
                        if not isinstance(node, dict):
                            continue
                        if node.get("type") in ("output_text", "text") and isinstance(node.get("text"), str):
                            chunks.append(node["text"])
            if isinstance(item.get("text"), str):
                chunks.append(item["text"])
    return "\n".join(chunks).strip()


def robust_json_loads(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    raw = text.strip()
    try:
        payload = json.loads(raw)
        return payload if isinstance(payload, dict) else None
    except Exception:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            payload = json.loads(raw[start:end + 1])
            return payload if isinstance(payload, dict) else None
        except Exception:
            return None
    return None


async def openai_judge_once(
    session: aiohttp.ClientSession,
    api_key: str,
    model: str,
    prompt_text: str,
    timeout_sec: int = 90,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, int], str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": "You are a QA evaluator. Output MUST be a valid JSON object and nothing else.",
            },
            {"role": "user", "content": prompt_text},
        ],
        "text": {"format": {"type": "json_object"}},
        "temperature": 0,
    }
    try:
        async with session.post(OPENAI_RESPONSES_URL, headers=headers, json=payload, timeout=timeout_sec) as resp:
            body = await resp.text()
            if resp.status != 200:
                return None, {}, f"OpenAI HTTP {resp.status}: {body[:250]}"
            parsed = json.loads(body)
            usage = extract_usage_fields(parsed)
            text = extract_openai_output_text(parsed)
            result = robust_json_loads(text)
            if result is None:
                return None, usage, f"OpenAI output is not JSON. raw={text[:200]}"
            return result, usage, ""
    except asyncio.TimeoutError:
        return None, {}, f"OpenAI timeout({timeout_sec}s)"
    except Exception as exc:
        return None, {}, f"OpenAI error: {type(exc).__name__}: {str(exc)[:200]}"


async def openai_judge_with_retry(
    session: aiohttp.ClientSession,
    api_key: str,
    model: str,
    prompt_text: str,
    max_retries: int = 2,
) -> Tuple[Optional[Dict[str, Any]], Dict[str, int], str]:
    wait = 2.0
    last_err = ""
    last_usage: Dict[str, int] = {}

    for _ in range(max_retries + 1):
        result, usage, err = await openai_judge_once(session, api_key, model, prompt_text)
        if usage:
            last_usage = usage
        if result is not None and not err:
            return result, last_usage, ""
        last_err = err or "unknown"
        await asyncio.sleep(wait)
        wait *= 2

    return None, last_usage, last_err

