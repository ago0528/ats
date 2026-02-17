from __future__ import annotations

from typing import Optional

from app.adapters.prompt_api_client import AxPromptApiClient, WORKER_DESCRIPTIONS, WORKER_TYPES


class PromptApiAdapter:
    @staticmethod
    def workers() -> list[dict]:
        return [{"workerType": w, "description": WORKER_DESCRIPTIONS.get(w, "")} for w in WORKER_TYPES]

    def __init__(self, base_url: str, ats_env: str, bearer: Optional[str], cms: Optional[str], mrs: Optional[str]):
        self.client = AxPromptApiClient(
            base_url=base_url,
            environment=ats_env,
            retention_token=bearer,
            cms_access_token=cms,
            mrs_session=mrs,
        )

    def get_prompt(self, worker_type: str):
        return self.client.get_prompt(worker_type)

    def update_prompt(self, worker_type: str, prompt: str):
        return self.client.update_prompt(worker_type, prompt)

    def reset_prompt(self, worker_type: str):
        return self.client.reset_prompt(worker_type)
