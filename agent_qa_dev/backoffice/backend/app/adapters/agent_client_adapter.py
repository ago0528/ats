from __future__ import annotations

from typing import Optional

from aqb_agent_client import ApplicantAgentClient


class AgentClientAdapter:
    def __init__(self, base_url: str, bearer: str, cms: str, mrs: str, origin: str, referer: str, max_parallel: int = 3):
        self.client = ApplicantAgentClient(
            base_url=base_url,
            bearer_token=bearer,
            cms_token=cms,
            mrs_session=mrs,
            origin=origin,
            referer=referer,
            max_parallel=max_parallel,
        )

    async def test_orchestrator_sync(
        self,
        session,
        query: str,
        conversation_id: Optional[str] = None,
        context: Optional[dict] = None,
        target_assistant: Optional[str] = None,
    ):
        return await self.client.test_orchestrator_sync(
            session,
            query,
            conversation_id=conversation_id,
            context=context,
            target_assistant=target_assistant,
        )
