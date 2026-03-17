# AI Debate System ⚖️🤖

A multi-agent AI system where distinct language models debate a given topic from varying perspectives, fact-check claims using an embedded knowledge base and real-time web search, and finally produce a conclusive verdict. This project aims to synthesize a well-reasoned outcome by mirroring human panel discussions and court arguments.

## Architecture

*   **Backend:** FastAPI (Python), WebSockets
*   **Agent Flow:** LangGraph 
*   **AI Engine:** Local execution via Ollama (configured for `llama3.2`)
*   **Web Research:** Tavily Search API
*   **Knowledge Base:** ChromaDB + Ollama Embeddings
*   **Scalable Runtime:** Redis (pub/sub + topic cache) + Postgres (state store + optional LangGraph checkpointer)
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
pip install -r requirements.txt
```

**Environment Variables:**
Create a `.env` file in the `backend` directory. You can copy from `.env.example`.

```env
TAVILY_API_KEY=your_tavily_api_key_here

# Model/runtime tuning
OLLAMA_MODEL=llama3.2
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_URL=http://localhost:11434/api/embeddings
MAX_CONCURRENT_DEBATES=64
NODE_EXECUTOR_WORKERS=32
STREAM_DISPATCH_DELAY_SECONDS=0
TAVILY_CACHE_TTL_SECONDS=900

# CORS for browser clients
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

# Redis pub/sub + cache
REDIS_URL=redis://localhost:6380/0

# Debate state store (memory|sqlite|postgres)
STATE_STORE=postgres
STATE_STORE_PATH=postgresql://debate:debate@localhost:5433/debate_db

# LangGraph checkpointer (memory|postgres)
CHECKPOINTER_BACKEND=postgres
CHECKPOINTER_DSN=postgresql://debate:debate@localhost:5433/debate_db
```

### 3. Start Redis + Postgres (Full Mode)
From the project root:

```bash
docker compose -f docker-compose.fullmode.yml up -d
```

This starts:
- Redis on `localhost:6380`
- Postgres on `localhost:5433` with database `debate_db`, user `debate`, password `debate`

Start the FastAPI server:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Frontend Setup
Navigate to the `frontend` folder and install dependencies.
```bash
cd frontend
npm install
```

Start the Vite development server:
```bash
npm run dev
```

### 5. Run the App
Open your browser and navigate to `http://localhost:5173/`. Enter any topic into the input field (e.g., "Should AI replace Programmers?") and watch the agents go to work!

### 6. Verify Full Mode Is Active
You should see these behaviors:
- Debate events continue to stream via pub/sub even when multiple debates run in parallel.
- Debate state is written to Postgres table `debates`.
- Topic research calls are cached via Redis.
- LangGraph checkpoints are persisted in Postgres (when `CHECKPOINTER_BACKEND=postgres`).

## Deploy Entire System (Single Stack)

This project now includes containerized deployment assets for **frontend + backend + Redis + Postgres + Ollama**.

### Files Used
- `docker-compose.deploy.yml`
- `.env.deploy.example`
- `backend/Dockerfile`
- `frontend/Dockerfile`
- `frontend/nginx.conf`

### 1. Prepare Deploy Env
From project root:

```bash
cp .env.deploy.example .env.deploy
```

Edit `.env.deploy` and set at least:

```env
TAVILY_API_KEY=your_real_tavily_key
```

Optional overrides:
- `OLLAMA_MODEL` (default `llama3.2`)
- `CORS_ORIGINS` (set your domain, e.g. `https://debate.example.com`)
- `FRONTEND_PORT` (default `80`)
- `VITE_WS_URL` (leave blank for same-origin proxy via nginx)

### 2. Build and Start Full Deployment

```bash
docker compose --env-file .env.deploy -f docker-compose.deploy.yml up -d --build
```

### 3. Pull the Ollama Model in Container

```bash
docker compose --env-file .env.deploy -f docker-compose.deploy.yml exec ollama ollama pull llama3.2
```

If you changed `OLLAMA_MODEL` in `.env.deploy`, pull that model instead.

### 4. Check Service Status

```bash
docker compose --env-file .env.deploy -f docker-compose.deploy.yml ps
```

### 5. Access App
- Frontend: `http://<server-ip-or-domain>:<FRONTEND_PORT>`
- WebSocket route is proxied by nginx at `/ws/debate`

### 6. Update Deployment

```bash
docker compose --env-file .env.deploy -f docker-compose.deploy.yml up -d --build
```

### 7. Stop Deployment

```bash
docker compose --env-file .env.deploy -f docker-compose.deploy.yml down
```

## Cloud Deployment (Public HTTPS For Real Users)

Use this path when you want other users on the internet to access the app through your domain.

### Files Used
- `docker-compose.cloud.yml`
- `.env.cloud.example`
- `deploy/caddy/Caddyfile`

### 1. Provision a Cloud VM
Recommended baseline:
- Ubuntu 22.04+
- 4 vCPU / 8 GB RAM minimum
- 80+ GB disk (Ollama models are large)

### 2. Point DNS To Your VM
Create an `A` record:
- Host: your domain (example `debate.example.com`)
- Value: your VM public IPv4

### 3. Open Firewall Ports
Allow inbound:
- `22` (SSH)
- `80` (HTTP, used for ACME challenge)
- `443` (HTTPS)

### 4. Install Docker + Compose Plugin On VM

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
	"deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
	$(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### 5. Clone Project And Prepare Env

```bash
git clone <your-repo-url>
cd "debate agent"
cp .env.cloud.example .env.cloud
```

Edit `.env.cloud` and set at least:

```env
PUBLIC_DOMAIN=debate.example.com
LETSENCRYPT_EMAIL=ops@example.com
TAVILY_API_KEY=your_real_tavily_key
POSTGRES_PASSWORD=use_a_strong_password_here
CORS_ORIGINS=https://debate.example.com
```

### 6. Start Cloud Stack

```bash
docker compose --env-file .env.cloud -f docker-compose.cloud.yml up -d --build
```

### 7. Pull Ollama Model In Container

```bash
docker compose --env-file .env.cloud -f docker-compose.cloud.yml exec ollama ollama pull llama3.2
```

If you changed `OLLAMA_MODEL`, pull that model instead.

### 8. Verify Public Availability

```bash
docker compose --env-file .env.cloud -f docker-compose.cloud.yml ps
docker compose --env-file .env.cloud -f docker-compose.cloud.yml logs caddy --tail=100
```

Open:
- `https://<PUBLIC_DOMAIN>`

### 9. Day-2 Operations

Update:
```bash
docker compose --env-file .env.cloud -f docker-compose.cloud.yml up -d --build
```

Stop:
```bash
docker compose --env-file .env.cloud -f docker-compose.cloud.yml down
```

### Notes
- TLS certificates are issued and renewed automatically by Caddy.
- Only Caddy is exposed publicly; backend/database/redis stay on the private Docker network.
- For production, keep `.env.cloud` out of git and rotate any leaked keys immediately.

## GCP Guide

The full GCP-only, step-by-step deployment guide now lives in:

- `README_GCP.md`

---
*Built with LangGraph, FastAPI, and React.*
