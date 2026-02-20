from __future__ import annotations

import re
from typing import Dict, Optional

TARGET_HEADERS = ("authorization", "cms-access-token", "mrs-session")


def parse_curl_headers(curl_text: str) -> Dict[str, Optional[str]]:
    normalized = re.sub(r"\s*[\^\\]\s*\n\s*", " ", curl_text)
    pattern = r"-H\s+(?:\^)?[\"']([^\"']+)[\"'](?:\^)?"
    matches = re.findall(pattern, normalized, re.IGNORECASE)

    result: Dict[str, Optional[str]] = {h: None for h in TARGET_HEADERS}
    for block in matches:
        if ":" not in block:
            continue
        name, _, value = block.partition(":")
        header_name = name.strip().lower()
        header_value = value.strip().rstrip("^")
        if header_name in result:
            result[header_name] = header_value

    return result

