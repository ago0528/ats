from __future__ import annotations

import os
from dataclasses import dataclass

from app.lib.aqb_prompt_template import ENV_PRESETS

from .enums import Environment


@dataclass(frozen=True)
class EnvConfig:
    ui_code: Environment
    ats_code: str
    base_url: str
    origin: str
    referer: str
    cms_base_url: str


_ENV_MAP = {
    Environment.DEV: "DV",
    Environment.ST2: "QA",
    Environment.ST: "ST",
    Environment.PR: "PR",
}

_CMS_BASE_URL_PRESETS = {
    Environment.DEV: "https://demo01-cms-recruiter-co-kr.kr-dv-midasitwebsol.com",
    Environment.ST2: "https://qa-jobda02-cms-recruiter-co-kr.midasweb.net",
    Environment.ST: "https://st-jobda07-cms-recruiter-co-kr.midasweb.net",
    Environment.PR: "https://pr-jobda02-cms.recruiter.co.kr",
}


def _normalize_url(value: str) -> str:
    return str(value or "").strip().rstrip("/")


def get_cms_base_url(env: Environment) -> str:
    override_key = f"BACKOFFICE_CMS_BASE_URL_{env.name}"
    override_value = _normalize_url(os.getenv(override_key, ""))
    if override_value:
        return override_value
    return _normalize_url(_CMS_BASE_URL_PRESETS[env])


def to_ats_environment(env: Environment) -> str:
    return _ENV_MAP[env]


def get_env_config(env: Environment) -> EnvConfig:
    ats = to_ats_environment(env)
    preset = ENV_PRESETS[ats]
    return EnvConfig(
        ui_code=env,
        ats_code=ats,
        base_url=str(preset.get("base_url", "")),
        origin=str(preset.get("origin", "")),
        referer=str(preset.get("referer", "")),
        cms_base_url=get_cms_base_url(env),
    )
