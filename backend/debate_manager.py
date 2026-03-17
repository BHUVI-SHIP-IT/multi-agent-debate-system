import asyncio
import uuid
from typing import Any

from settings import settings


NODE_ROLE_MAP = {
    "moderator": "moderator",
    "researcher": "researcher",
    "pro_agent": "pro",
    "opponent_agent": "opponent",
    "fact_checker": "fact_checker",
    "verdict_agent": "verdict",
}

APPEND_FIELDS = {"conversation", "fact_checking_results", "search_queries"}


def _merge_state(current_state: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    merged = dict(current_state)
    for key, value in update.items():
        if key in APPEND_FIELDS and isinstance(value, list):
            previous = merged.get(key, [])
            if not isinstance(previous, list):
                previous = []
            merged[key] = previous + value
            continue
        merged[key] = value
    return merged


class DebateJobManager:
    def __init__(self, graph, state_store, event_bus) -> None:
        self.graph = graph
        self.state_store = state_store
        self.event_bus = event_bus
        self._tasks: dict[str, asyncio.Task] = {}
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_debates)

    @staticmethod
    def channel_for(debate_id: str) -> str:
        return f"debate:{debate_id}"

    async def startup(self) -> None:
        await self.state_store.startup()

    async def shutdown(self) -> None:
        for task in self._tasks.values():
            task.cancel()
        for task in self._tasks.values():
            try:
                await task
            except asyncio.CancelledError:
                pass
        await self.state_store.close()
        await self.event_bus.close()

    async def start_debate(self, topic: str, max_rounds: int = 2) -> str:
        debate_id = str(uuid.uuid4())
        initial_state = {
            "debate_id": debate_id,
            "topic": topic,
            "current_round": 0,
            "max_rounds": max_rounds,
            "conversation": [],
            "fact_checking_results": [],
            "search_queries": [],
            "background_context": "",
            "rules": "",
            "verdict": "",
            "verdict_data": {},
        }

        await self.state_store.create_debate(debate_id, topic, initial_state)

        task = asyncio.create_task(self._run_debate(debate_id, initial_state))
        self._tasks[debate_id] = task

        return debate_id

    async def get_debate(self, debate_id: str):
        return await self.state_store.get_debate(debate_id)

    async def resume_debate(self, debate_id: str) -> bool:
        existing_task = self._tasks.get(debate_id)
        if existing_task and not existing_task.done():
            return True

        debate = await self.state_store.get_debate(debate_id)
        if not debate:
            return False

        state = debate.get("state")
        if not isinstance(state, dict):
            return False

        status = str(debate.get("status", "")).lower()
        if status not in {"queued", "running"}:
            return False

        task = asyncio.create_task(self._run_debate(debate_id, state))
        self._tasks[debate_id] = task
        return True

    def subscribe(self, debate_id: str):
        return self.event_bus.subscribe(self.channel_for(debate_id))

    async def _publish_conversation_event(self, debate_id: str, node_name: str, state_update: dict[str, Any]) -> None:
        if "conversation" not in state_update:
            return

        conversation = state_update.get("conversation") or []
        if not conversation:
            return

        last_msg = conversation[-1]
        role = NODE_ROLE_MAP.get(node_name, last_msg.get("role", node_name))

        # The final verdict is published as a dedicated payload.
        if role == "verdict" and state_update.get("verdict"):
            return

        await self.event_bus.publish(
            self.channel_for(debate_id),
            {
                "type": "agent_message",
                "debate_id": debate_id,
                "agent": node_name,
                "role": role,
                "content": last_msg.get("content", ""),
            },
        )

    async def _publish_verdict_event(self, debate_id: str, state_update: dict[str, Any]) -> None:
        verdict = state_update.get("verdict")
        if not verdict:
            return

        await self.event_bus.publish(
            self.channel_for(debate_id),
            {
                "type": "verdict",
                "debate_id": debate_id,
                "content": verdict,
                "verdict_data": state_update.get("verdict_data", {}),
            },
        )

    async def _run_debate(self, debate_id: str, initial_state: dict[str, Any]) -> None:
        state = dict(initial_state)

        try:
            async with self._semaphore:
                await self.state_store.update_status(debate_id, "running")

                config = {"configurable": {"thread_id": debate_id}}
                async for event in self.graph.astream(initial_state, config=config, stream_mode="updates"):
                    for node_name, state_update in event.items():
                        if not isinstance(state_update, dict):
                            continue

                        state = _merge_state(state, state_update)
                        await self.state_store.save_state(debate_id, node_name, state)

                        await self._publish_conversation_event(debate_id, node_name, state_update)
                        await self._publish_verdict_event(debate_id, state_update)

                    if settings.stream_dispatch_delay_seconds > 0:
                        await asyncio.sleep(settings.stream_dispatch_delay_seconds)

                await self.state_store.update_status(debate_id, "completed")
                await self.event_bus.publish(
                    self.channel_for(debate_id),
                    {
                        "type": "completed",
                        "debate_id": debate_id,
                    },
                )
        except Exception as exc:
            await self.state_store.update_status(debate_id, "failed", error=str(exc))
            await self.event_bus.publish(
                self.channel_for(debate_id),
                {
                    "type": "error",
                    "debate_id": debate_id,
                    "message": str(exc),
                },
            )
        finally:
            self._tasks.pop(debate_id, None)
