from contextlib import asynccontextmanager

from langgraph.checkpoint.memory import InMemorySaver

from settings import settings

try:
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
except Exception:  # pragma: no cover - optional dependency
    AsyncPostgresSaver = None


def _resolve_dsn() -> str:
    if settings.checkpointer_dsn:
        return settings.checkpointer_dsn

    if settings.state_store == "postgres" and settings.state_store_path:
        return settings.state_store_path

    return ""


@asynccontextmanager
async def checkpointer_context():
    backend = settings.checkpointer_backend

    if backend == "postgres" and AsyncPostgresSaver is not None:
        dsn = _resolve_dsn()
        if dsn:
            async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
                await saver.setup()
                yield saver
                return

    # Fallback for local development and environments without postgres support.
    yield InMemorySaver()
