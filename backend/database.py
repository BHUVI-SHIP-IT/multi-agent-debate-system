import chromadb
from chromadb.utils import embedding_functions
import re
import uuid
from settings import settings

# Initialize ChromaDB client (local persistent storage)
client = chromadb.PersistentClient(path="./chroma_db")

# Use Ollama for embeddings to avoid HuggingFace downloads and timeouts
ollama_ef = embedding_functions.OllamaEmbeddingFunction(
    url=settings.ollama_embedding_url,
    model_name=settings.model_name,
)

def _normalize_debate_id(debate_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", (debate_id or "default"))
    return safe[:48] or "default"


def _collection_name_for(debate_id: str) -> str:
    return f"debate_kb_{_normalize_debate_id(debate_id)}"


def _get_collection(debate_id: str):
    return client.get_or_create_collection(
        name=_collection_name_for(debate_id),
        embedding_function=ollama_ef,
    )

def clear_knowledge_base(debate_id: str = "default"):
    """Clears all documents from the knowledge base."""
    collection = _get_collection(debate_id)
    results = collection.get()
    if results and "ids" in results and results["ids"]:
        collection.delete(ids=results["ids"])

def add_to_knowledge_base(documents: list, debate_id: str = "default"):
    """Adds a list of text snippets to the vector database."""
    if not documents:
        return
    collection = _get_collection(debate_id)
    ids = [f"{_normalize_debate_id(debate_id)}_{uuid.uuid4().hex}_{i}" for i in range(len(documents))]
    collection.add(documents=documents, ids=ids)

def query_knowledge_base(query: str, debate_id: str = "default") -> str:
    """Queries the ChromaDB knowledge base and returns the most relevant results."""
    collection = _get_collection(debate_id)
    results = collection.query(
        query_texts=[query],
        n_results=2
    )
    if results and results["documents"] and results["documents"][0]:
        return "\\n".join(results["documents"][0])
    return "No relevant facts found."
