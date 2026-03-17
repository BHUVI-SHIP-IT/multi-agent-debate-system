import asyncio
import contextlib
import importlib
import json
from contextlib import asynccontextmanager
from typing import AsyncIterator

from settings import settings

try:
    redis_async = importlib.import_module("redis.asyncio")
except Exception:  # pragma: no cover - optional dependency
    redis_async = None


class InMemoryEventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def publish(self, channel: str, event: dict) -> None:
        async with self._lock:
            queues = list(self._subscribers.get(channel, set()))

        for queue in queues:
            await queue.put(event)

    @asynccontextmanager
    async def subscribe(self, channel: str) -> AsyncIterator[asyncio.Queue]:
        queue: asyncio.Queue = asyncio.Queue()
        async with self._lock:
            self._subscribers.setdefault(channel, set()).add(queue)

        try:
            yield queue
        finally:
            async with self._lock:
                channel_subscribers = self._subscribers.get(channel)
                if channel_subscribers and queue in channel_subscribers:
                    channel_subscribers.remove(queue)
                if channel_subscribers and not channel_subscribers:
                    del self._subscribers[channel]

    async def close(self) -> None:
        return


class RedisEventBus:
    def __init__(self, redis_url: str) -> None:
        self._redis = redis_async.from_url(redis_url, decode_responses=True)

    async def publish(self, channel: str, event: dict) -> None:
        payload = json.dumps(event, ensure_ascii=True)
        await self._redis.publish(channel, payload)

    @asynccontextmanager
    async def subscribe(self, channel: str) -> AsyncIterator[asyncio.Queue]:
        pubsub = self._redis.pubsub()
        await pubsub.subscribe(channel)
        queue: asyncio.Queue = asyncio.Queue()

        async def _forward_messages() -> None:
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if not msg:
                    await asyncio.sleep(0.05)
                    continue
                data = msg.get("data")
                if not isinstance(data, str):
                    continue
                try:
                    await queue.put(json.loads(data))
                except Exception:
                    continue

        forward_task = asyncio.create_task(_forward_messages())
        try:
            yield queue
        finally:
            forward_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await forward_task
            await pubsub.unsubscribe(channel)
            await pubsub.close()

    async def close(self) -> None:
        await self._redis.aclose()


def build_event_bus():
    if settings.redis_url and redis_async is not None:
        try:
            return RedisEventBus(settings.redis_url)
        except Exception:
            return InMemoryEventBus()
    return InMemoryEventBus()
