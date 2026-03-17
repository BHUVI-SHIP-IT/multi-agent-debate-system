import os
from dotenv import load_dotenv
from tavily import TavilyClient
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from database import clear_knowledge_base, add_to_knowledge_base

load_dotenv()

def test_researcher_steps():
    print("Testing Tavily Search...")
    tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY", ""))
    search_result = tavily_client.search(query="AI replacing programmers", search_depth="basic", max_results=2)
    print("Tavily Success:", search_result.keys())

    print("Testing ChromaDB clear...")
    clear_knowledge_base()
    print("ChromaDB Clear Success")

    print("Testing ChromaDB add (Ollama embeddings)...")
    add_to_knowledge_base(["This is a test document to embed."])
    print("ChromaDB Add Success")

test_researcher_steps()
