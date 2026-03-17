import asyncio
import websockets
import json

async def test_ws():
    uri = "ws://localhost:8000/ws/debate"
    print("Connecting to ws...")
    async with websockets.connect(uri) as websocket:
        print("Connected.")
        req = json.dumps({"topic": "AI replacing programmers"})
        print("Sending topic:", req)
        await websocket.send(req)
        
        while True:
            response = await websocket.recv()
            print("Received from server:", response)

if __name__ == "__main__":
    asyncio.run(test_ws())
