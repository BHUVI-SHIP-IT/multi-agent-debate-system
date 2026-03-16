from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
import asyncio
from graph import debate_graph

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "AI Debate Backend is running."}

@app.websocket("/ws/debate")
async def debate_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("WebSocket connected.")
    try:
        while True:
            # Wait for user topic
            data = await websocket.receive_text()
            payload = json.loads(data)
            topic = payload.get("topic", "AI Replacing Programmers")
            
            # Initialize State
            initial_state = {
                "topic": topic,
                "current_round": 0,
                "max_rounds": 2,
                "conversation": [],
                "fact_checking_results": [],
                "rules": "",
                "verdict": ""
            }

            print(f"Starting debate on topic: {topic}")
            
            # Stream events from LangGraph
            async for event in debate_graph.astream(initial_state, stream_mode="updates"):
                for node_name, state_update in event.items():
                    # We send the updates to the frontend
                    
                    if isinstance(state_update, dict):
                        if "conversation" in state_update and state_update["conversation"] is not None and len(state_update["conversation"]) > 0:
                            # Send the latest message 
                            last_msg = state_update["conversation"][-1]
                            
                            await websocket.send_json({
                                "type": "agent_message",
                                "agent": node_name,
                                "role": last_msg["role"],
                                "content": last_msg["content"]
                            })
                        
                        if "verdict" in state_update and state_update.get("verdict"):
                            # Final verdict reached
                            await websocket.send_json({
                                "type": "verdict",
                                "content": state_update["verdict"]
                            })

                    # Small delay to simulate human typing/reading on front end
                    await asyncio.sleep(1)

    except WebSocketDisconnect:
        print("WebSocket disconnected.")
        
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
