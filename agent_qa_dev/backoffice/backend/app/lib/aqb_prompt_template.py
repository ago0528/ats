from __future__ import annotations

from typing import Dict

ENV_PRESETS: Dict[str, Dict[str, str]] = {
    "PR": {
        "base_url": "https://api-llm.ats.kr-pr-midasin.com",
        "origin": "https://pr-jobda02-cms.recruiter.co.kr",
        "referer": "https://pr-jobda02-cms.recruiter.co.kr/",
    },
    "ST": {
        "base_url": "https://api-llm.ats.kr-st-midasin.com",
        "origin": "https://st-jobda02-cms.recruiter.co.kr",
        "referer": "https://st-jobda02-cms.recruiter.co.kr/",
    },
    "DV": {
        "base_url": "https://api-llm.ats.kr-dv-midasin.com",
        "origin": "https://dv-jobda02-cms.recruiter.co.kr",
        "referer": "https://dv-jobda02-cms.recruiter.co.kr/",
    },
    "QA": {
        "base_url": "https://api-llm.ats.kr-st2-midasin.com",
        "origin": "https://st-jobda02-cms.recruiter.co.kr",
        "referer": "https://st-jobda02-cms.recruiter.co.kr/",
    },
}

