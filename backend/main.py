from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
from graph import build_debate_graph
from debate_manager import DebateJobManager
from event_bus import build_event_bus
from state_store import build_state_store
from checkpointer import checkpointer_context
from settings import settings

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "AI Debate Backend is running."}

debate_manager: DebateJobManager | None = None
_checkpointer_cm = None


@app.on_event("startup")
async def startup_event() -> None:
    global debate_manager
    global _checkpointer_cm

    _checkpointer_cm = checkpointer_context()
    checkpointer = await _checkpointer_cm.__aenter__()

    debate_graph = build_debate_graph(checkpointer=checkpointer)
    state_store = build_state_store()
    event_bus = build_event_bus()
    debate_manager = DebateJobManager(debate_graph, state_store, event_bus)
    await debate_manager.startup()


@app.on_event("shutdown")
async def shutdown_event() -> None:
    global _checkpointer_cm

    if debate_manager is not None:
        await debate_manager.shutdown()

    if _checkpointer_cm is not None:
        await _checkpointer_cm.__aexit__(None, None, None)
        _checkpointer_cm = None

@app.websocket("/ws/debate")
async def debate_endpoint(websocket: WebSocket):
    manager = debate_manager
    if manager is None:
        await websocket.accept()
        await websocket.send_json({"type": "error", "message": "Debate manager is not initialized yet."})
        await websocket.close()
        return

    await websocket.accept()
    print("WebSocket connected.")
    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            debate_id = payload.get("debate_id")

            if debate_id:
                debate = await manager.get_debate(debate_id)
                if debate is None:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": f"Unknown debate_id: {debate_id}",
                        }
                    )
                    continue
                await websocket.send_json(
                    {
                        "type": "debate_started",
                        "debate_id": debate_id,
                        "topic": debate.get("topic", ""),
                    }
                )

                await manager.resume_debate(debate_id)
            else:
                topic = payload.get("topic", "AI Replacing Programmers")
                max_rounds = int(payload.get("max_rounds", 2))
                debate_id = await manager.start_debate(topic=topic, max_rounds=max_rounds)

                await websocket.send_json(
                    {
                        "type": "debate_started",
                        "debate_id": debate_id,
                        "topic": topic,
                    }
                )

            async with manager.subscribe(debate_id) as queue:
                while True:
                    event = await queue.get()
                    await websocket.send_json(event)

                    if event.get("type") in {"completed", "error"}:
                        break

    except WebSocketDisconnect:
        print("WebSocket disconnected.")
        
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
