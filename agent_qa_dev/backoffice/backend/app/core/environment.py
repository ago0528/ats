from __future__ import annotations

from dataclasses import dataclass

from aqb_prompt_template import ENV_PRESETS

from .enums import Environment


@dataclass(frozen=True)
class EnvConfig:
    ui_code: Environment
    ats_code: str
    base_url: str
    origin: str
    referer: str


_ENV_MAP = {
    Environment.DEV: "DV",
    Environment.ST2: "QA",
    Environment.ST: "ST",
    Environment.PR: "PR",
}


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
    )
