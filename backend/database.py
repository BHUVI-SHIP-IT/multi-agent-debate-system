import chromadb
from chromadb.utils import embedding_functions

# Initialize ChromaDB client (local persistent storage)
client = chromadb.PersistentClient(path="./chroma_db")

# Use Ollama for embeddings to avoid HuggingFace downloads and timeouts
ollama_ef = embedding_functions.OllamaEmbeddingFunction(
    url="http://localhost:11434/api/embeddings",
    model_name="llama3.2",
)

# Create or get the debate knowledge base collection
collection = client.get_or_create_collection(name="debate_kb", embedding_function=ollama_ef)

def clear_knowledge_base():
    """Clears all documents from the knowledge base."""
    results = collection.get()
    if results and "ids" in results and results["ids"]:
        collection.delete(ids=results["ids"])

def add_to_knowledge_base(documents: list):
    """Adds a list of text snippets to the vector database."""
    if not documents:
        return
    ids = [f"doc_{i}" for i in range(len(documents))]
    collection.add(documents=documents, ids=ids)

def query_knowledge_base(query: str) -> str:
    """Queries the ChromaDB knowledge base and returns the most relevant results."""
    results = collection.query(
        query_texts=[query],
        n_results=2
    )
    if results and results["documents"] and results["documents"][0]:
        return "\\n".join(results["documents"][0])
    return "No relevant facts found."
