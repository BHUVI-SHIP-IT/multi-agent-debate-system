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

# We can insert some mock documents into our knowledge base for fact-checking
mock_documents = [
    {"id": "doc1", "text": "AI can automate code generation and optimization, but still requires human oversight to ensure complex architectural choices are sound."},
    {"id": "doc2", "text": "Programmers spend less time typing code and more time debugging, designing, and understanding user requirements, which AI struggles to do autonomously."},
    {"id": "doc3", "text": "Devin and other autonomous coding agents can solve many Github issues automatically but fail on novel or highly complex tasks requiring deep context."}
]

# For simplicity, we just add them if it's empty
if collection.count() == 0:
    collection.add(
        documents=[doc["text"] for doc in mock_documents],
        ids=[doc["id"] for doc in mock_documents]
    )

def query_knowledge_base(query: str) -> str:
    """Queries the ChromaDB knowledge base and returns the most relevant results."""
    results = collection.query(
        query_texts=[query],
        n_results=2
    )
    if results and results["documents"] and results["documents"][0]:
        return "\\n".join(results["documents"][0])
    return "No relevant facts found."
