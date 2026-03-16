# AI Debate System ⚖️🤖

A multi-agent AI system where distinct language models debate a given topic from varying perspectives, fact-check claims using an embedded knowledge base and real-time web search, and finally produce a conclusive verdict. This project aims to synthesize a well-reasoned outcome by mirroring human panel discussions and court arguments.

## Architecture

*   **Backend:** FastAPI (Python), WebSockets
*   **Agent Flow:** LangGraph 
*   **AI Engine:** Local execution via Ollama (configured for `llama3.2`)
*   **Web Research:** Tavily Search API
*   **Knowledge Base:** ChromaDB + Ollama Embeddings
*   **Frontend:** React, Vite, TailwindCSS v4

## How it Works

The debate process runs autonomously through a compiled LangGraph state machine:

1.  **🎙️ Moderator Node:** Receives the topic, sets debate rules, and manages the rounds.
2.  **🕵️ Search / Research Node:** Calls the Tavily Search API to scan the web for recent news, context, and expert opinions on the given topic. This grounds the debate in reality.
3.  **👍 Pro Agent:** Constructs arguments in favor of the topic, utilizing the gathered background context.
4.  **👎 Opponent Agent:** Challenges the pro's assumptions and exposes weaknesses using the shared context.
5.  **🔍 Fact Checker Agent:** Automatically extracts claims and verifies them against both live web context and a local semantic knowledge base (ChromaDB).
6.  **⚖️ Verdict Agent:** Once the max rounds are exhausted, this agent summarizes the best arguments and produces a final definitive verdict on the topic.

Messages from the execution graph are streamed in real-time to the React frontend via WebSockets.

---

## 🛠️ Local Development & Setup

### Prerequisites
1.  Python 3.10+
2.  Node.js (npm or yarn)
3.  [Ollama](https://ollama.com/) installed and running locally.

### 1. Model Configuration
Ensure you pull the required model using Ollama before running the app.
```bash
ollama pull llama3.2
```

### 2. Backend Setup
Navigate to the `backend` folder and set up a virtual environment.
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt  # Or install individual packages listed below
```

**Required backend packages:**
```bash
pip install langgraph langchain langchain-ollama ollama fastapi chromadb uvicorn websockets pydantic tavily-python python-dotenv
```

**Environment Variables:**
Create a `.env` file in the `backend` directory and add your Tavily API Key.
```env
TAVILY_API_KEY=your_tavily_api_key_here
```

Start the FastAPI server:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Frontend Setup
Navigate to the `frontend` folder and install dependencies.
```bash
cd frontend
npm install
```

Start the Vite development server:
```bash
npm run dev
```

### 4. Run the App
Open your browser and navigate to `http://localhost:5173/`. Enter any topic into the input field (e.g., "Should AI replace Programmers?") and watch the agents go to work!

---
*Built with LangGraph, FastAPI, and React.*
