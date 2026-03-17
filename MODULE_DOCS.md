# AI Debate System - Module Documentation

This document explains each of the major modules, files, and functions found within the AI Debate System, covering both the backend (FastAPI, LangGraph) and the frontend (React).

## 1. Backend Modules (`/backend`)

The backend is responsible for managing the AI debate process, utilizing local LLMs through Ollama, managing states across different AI agents, searching the web, and providing memory through ChromaDB. 

### `main.py`
This is the entry point for the FastAPI server. It exposes the application endpoints and connects the LangGraph pipeline with the frontend application.
- **`app = FastAPI()`**: Initializes the API with necessary CORS configurations to support connections from the React frontend.
- **`debate_endpoint(websocket: WebSocket)`**: A WebSocket endpoint (`/ws/debate`) that the frontend connects to. Once triggered, it reads a user-provided topic, sets up an `initial_state` dictionary starting at round 0, and runs an asynchronous loop on `debate_graph`. As the debate simulation progresses over various agents, the function listens for any new conversation entries or a final verdict and streams these updates in real-time as JSON payloads back to the client UI.

### `agents.py`
This module defines the specific logic and instructions for every unique AI agent participating in the system. It uses `ChatOllama` for generating outputs.
- **`run_moderator(state)`**: Defines the debate structure, announces the debate rules at the initial round (Round 0), and signals the start. Afterward, remains quiet to allow the actual debate agents to speak.
- **`run_researcher(state)`**: Before the core debate starts, clears the existing knowledge base, then performs an internet search on the `topic` using the Tavily API (`tavily_client.search`). It dynamically injects the fetched web snippets directly into the ChromaDB vector database on the fly, while also returning a formatted context string for the `pro` and `opponent` agents.
- **`run_pro_agent(state)`**: Uses the gathered web context to formulate a concise 2-3 sentence argument supporting the debate topic.
- **`run_opponent_agent(state)`**: Identifies weaknesses or logically counter-argues the Pro argument in 2-3 sentences based on prior exchange and background context.
- **`run_fact_checker(state)`**: Extracts the **last claim** from the conversation and evaluates its factual accuracy by querying the local ChromaDB database and the web search context. The response evaluates to 'True', 'False', or 'Partially True', supported by a one-sentence reasoning.
- **`run_verdict_agent(state)`**: Executed at the very end of the debate, this agent analyzes all historical dialogue to synthesize a final verdict out of the best points made.

### `graph.py`
Leverages **LangGraph** to model the debate flow. Think of this file as creating a state machine where nodes represent agents and edges manage sequence execution.
- **`DebateState`**: An annotated `TypedDict` defining the global debate state format tracking fields like `topic`, `current_round`, `max_rounds`, `search_queries`, `fact_checking_results`, and `conversation` appends.
- **`route_from_moderator(state)`**: A conditional routing function. It dictates what happens after the moderator speaks: starts the initial `researcher` phase if early, pushes to the `verdict_agent` to conclude the debate if rounds are topped, or loops into the normal `pro_agent` logic otherwise.
- **`increment_round(state)`**: Simply bumps up `current_round` by 1.
- **Graph Assembly (`builder`)**: Attaches all agent functions as "Nodes" (e.g. `builder.add_node("moderator", run_moderator)`). Connects the required workflow using normal edges and conditional edges. The flow moves: Moderator -> Researcher -> Pro -> Opponent -> Fact Checker -> Increment Round -> Moderator -> Verdict -> END. Finally, compiles this logic into an exportable `debate_graph`.

### `database.py`
Handles information storage mapping claims to dynamically fetched logical facts using **ChromaDB**. 
- **Initialization**: Connects a persistent Chroma Database (`./chroma_db`) and registers an `OllamaEmbeddingFunction` targeting the local Llama3 embedding API so vectorization stays on-device.
- **`clear_knowledge_base()`**: Empties the `debate_kb` collection so that facts from previous debates don't leak into new ones. Called dynamically by the Researcher agent.
- **`add_to_knowledge_base(documents)`**: Dynamically injects new document strings (like recent web snippets) into the vector collection.
- **`query_knowledge_base(query)`**: A helper function primarily utilized by the Fact Checker agent. It runs a vector similarity search on the local collection targeting the queried text, pulling the most relevant 2 documents and concatenating them.

---

## 2. Frontend Modules (`/frontend/src/`)

The frontend visualizes the debate as an ongoing chat sequence. Built in React, Vite, and TailwindCSS.

### `App.tsx`
This single file encompasses the core components, styling logic, and state management rendering the entire browser experience.
- **Component States**: Maintains reactive variables such as `topic`, `messages[]` (holding agent messages including their type and ID element), `isDebating`, and active `ws` WebSocket connections.
- **`useEffect` (WebSocket Hook)**: Auto-connects to the backend websocket on mount. Registers an `onmessage` event listener to inject new parsed JSON messages streamed from the backend directly into the component's `messages` state (categorizing them safely via `type === 'agent_message'` or `'verdict'`).
- **`scrollToBottom`**: An automated ref hook triggering a smooth downward scroll effect every time the `messages` array changes footprint so users always see the latest inputs.
- **`handleStart(e)`**: Intercepts the form submission payload, prevents standard browser refresh strings up and pushes the JSON encoded `topic` string through the WebSocket pipeline to kick off the backend script execution.
- **UI & Helper Functions**: 
  - `getAgentIcon`, `getAgentColor`, `getAgentName`: Functions that provide varying semantic Lucide icons, Tailwind background borders, and Human text labels based strictly on the received user strings (e.g. distinguishing a 'moderator' color from a 'pro' color!).
  - **Render Payload**: Contains the application HTML layout using responsive CSS classes alongside simple mapping arrays displaying the chat messages sequentially.
