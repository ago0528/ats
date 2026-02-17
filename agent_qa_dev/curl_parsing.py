"""붙여넣은 cURL에서 authorization, cms-access-token, mrs-session 헤더를 파싱하는 스크립트."""

import json
import re
import sys
from typing import Dict, Optional

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

TARGET_HEADERS = ("authorization", "cms-access-token", "mrs-session")


def parse_curl_headers(curl_text: str) -> Dict[str, Optional[str]]:
    """
    cURL 문자열에서 -H 로 전달된 헤더를 추출한다.
    Windows(^", ^ 줄넘김) 및 Unix(\\, \") 형식을 모두 허용한다.
    """
    # 줄 연속 문자 제거 후 한 줄로 정규화
    normalized = re.sub(r"\s*[\^\\]\s*\n\s*", " ", curl_text)

    # -H "..." 또는 -H ^"..."^" 형태의 헤더 블록 추출
    # (헤더 값 안에 따옴표가 없는다고 가정)
    pattern = r"-H\s+(?:\^)?[\"']([^\"']+)[\"'](?:\^)?"
    matches = re.findall(pattern, normalized, re.IGNORECASE)

    result: Dict[str, Optional[str]] = {h: None for h in TARGET_HEADERS}
    for block in matches:
        if ":" not in block:
            continue
        name, _, value = block.partition(":")
        name = name.strip().lower()
        value = value.strip().rstrip("^")
        if name in result:
            result[name] = value

    return result


def main() -> None:
    if sys.stdin.isatty():
        print("cURL 명령을 붙여넣은 뒤 Ctrl+Z (Enter) 또는 Ctrl+D 로 입력을 끝내세요.\n")
    raw = sys.stdin.read()
    parsed = parse_curl_headers(raw)
    print(json.dumps(parsed, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
