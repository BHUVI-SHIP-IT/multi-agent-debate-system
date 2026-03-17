import asyncio
import sys
import os

# Ensure backend modules can be imported
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from graph import debate_graph

async def main():
    state = {
        "topic": "AI Replacing Programmers",
        "current_round": 0,
        "max_rounds": 2,
        "conversation": [],
        "fact_checking_results": [],
        "search_queries": [],
        "background_context": "",
        "rules": "",
        "verdict": "",
        "verdict_data": {}
    }
    print("Starting graph execution...")
    async for event in debate_graph.astream(state, stream_mode="updates"):
        print("Received event:", event)
        import sys
        sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(main())
