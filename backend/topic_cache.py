import hashlib
import importlib
import json
import threading
import time
from typing import Optional

from settings import settings

try:
    redis = importlib.import_module("redis")
except Exception:  # pragma: no cover - optional dependency
    redis = None


class TopicContextCache:
    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self._memory_cache: dict[str, tuple[float, str]] = {}
        self._lock = threading.Lock()
        self._redis_client = None

        if settings.redis_url and redis is not None:
            try:
                self._redis_client = redis.Redis.from_url(
                    settings.redis_url,
                    decode_responses=True,
                )
                # Fail fast if URL is invalid/unreachable during startup.
                self._redis_client.ping()
            except Exception:
                self._redis_client = None

    @staticmethod
    def _topic_hash(topic: str) -> str:
        normalized = topic.strip().lower().encode("utf-8")
        return hashlib.sha256(normalized).hexdigest()

    def _cache_key(self, topic: str) -> str:
        return f"topic_context:{self._topic_hash(topic)}"

    def get(self, topic: str) -> Optional[str]:
        cache_key = self._cache_key(topic)

        if self._redis_client is not None:
            payload = self._redis_client.get(cache_key)
            if payload:
                try:
                    data = json.loads(payload)
                    return str(data.get("context", ""))
                except Exception:
                    return None

        now = time.time()
        with self._lock:
            cached = self._memory_cache.get(cache_key)
            if not cached:
                return None

            expires_at, context = cached
            if now >= expires_at:
                del self._memory_cache[cache_key]
                return None
            return context

    def set(self, topic: str, context: str) -> None:
        cache_key = self._cache_key(topic)

        if self._redis_client is not None:
            payload = json.dumps({"context": context}, ensure_ascii=True)
            self._redis_client.setex(cache_key, self.ttl_seconds, payload)
            return

        expires_at = time.time() + self.ttl_seconds
        with self._lock:
            self._memory_cache[cache_key] = (expires_at, context)


topic_context_cache = TopicContextCache(ttl_seconds=settings.tavily_cache_ttl_seconds)
