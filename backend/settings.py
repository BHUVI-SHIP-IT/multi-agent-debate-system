import os
from dataclasses import dataclass


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _get_csv(name: str, default: str) -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    model_name: str
    ollama_base_url: str
    ollama_embedding_url: str
    max_concurrent_debates: int
    node_executor_workers: int
    stream_dispatch_delay_seconds: float
    tavily_cache_ttl_seconds: int
    cors_origins: list[str]
    redis_url: str
    state_store: str
    state_store_path: str
    checkpointer_backend: str
    checkpointer_dsn: str


settings = Settings(
    model_name=os.getenv("OLLAMA_MODEL", "llama3.2"),
    ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip().rstrip("/"),
    ollama_embedding_url=os.getenv("OLLAMA_EMBEDDING_URL", "http://localhost:11434/api/embeddings").strip(),
    max_concurrent_debates=max(1, _get_int("MAX_CONCURRENT_DEBATES", 64)),
    node_executor_workers=max(4, _get_int("NODE_EXECUTOR_WORKERS", 32)),
    stream_dispatch_delay_seconds=max(0.0, _get_float("STREAM_DISPATCH_DELAY_SECONDS", 0.0)),
    tavily_cache_ttl_seconds=max(30, _get_int("TAVILY_CACHE_TTL_SECONDS", 900)),
    cors_origins=_get_csv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"),
    redis_url=os.getenv("REDIS_URL", "").strip(),
    state_store=os.getenv("STATE_STORE", "sqlite").strip().lower(),
    state_store_path=os.getenv("STATE_STORE_PATH", "./debate_state.sqlite3").strip(),
    checkpointer_backend=os.getenv("CHECKPOINTER_BACKEND", "memory").strip().lower(),
    checkpointer_dsn=os.getenv("CHECKPOINTER_DSN", "").strip(),
)
