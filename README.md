# Incident Response On-Call Agent

An event-driven incident response system that listens for alerts, searches historical incidents and runbooks, evaluates likely root causes, and coordinates a human-approved remediation path. The project combines a Python LangGraph workflow, a FastAPI backend, a Redis event bus, and a small React dashboard for incident tracking.

## What the project does

The app is designed for the first phase of incident handling, where the agent:

- ingests an alert from Redis or an HTTP request
- classifies the severity and affected services
- recalls similar incidents from ChromaDB memory
- gathers logs, metrics, service health, and deployment metadata
- retrieves the most relevant runbook via semantic search
- asks a configured decision provider for a recommended action
- waits for human approval before performing a remediation
- stores the resulting incident state and report for future recall

This is not a full production SRE platform; it is a practical local prototype for evaluating agent-driven incident triage and response.

## Architecture

```text
Alert source / REST API / CLI
        |
        v
Redis pub/sub channel: alerts
        |
        v
agent.listener
        |
        v
LangGraph workflow in agent.graph
        |-- recall_memory -> ChromaDB historical incidents
        |-- fetch_evidence -> simulated logs/metrics/service data
        |-- fetch_runbook -> ChromaDB runbook RAG
        |-- make_decision -> Groq, mock, or Laya provider
        |-- human approval -> approval workflow
        |-- auto_remediate -> simulated remediation
        |-- generate_report -> stored incident state
        |
        v
FastAPI API + incident state cache + Redis persistence
        |
        v
React frontend dashboard
```

The system is intentionally modular: the decision provider, remediation behavior, queue, and storage are isolated behind simple interfaces.

## Core technologies

- Python 3.11+
- LangGraph for orchestration
- FastAPI for the API layer
- Redis for event-driven alert delivery
- ChromaDB + sentence-transformers for memory and runbook retrieval
- Groq cloud LLM support, plus a deterministic mock provider for local demos
- React + Vite for the frontend dashboard
- Docker for Redis and optional containerized deployment

## Decision providers

The app supports multiple provider modes through the environment variable `DECISION_PROVIDER`:

- `mock`: deterministic local demo logic for offline testing
- `groq`: structured decision-making with a Groq API key
- `laya`: optional typed-decision model via the Laya package

The default environment file includes `mock` and `groq` examples, while the rest of the graph depends on a consistent decision interface rather than a single model.

## Runbook and memory workflow

The repository includes markdown runbooks under `runbooks/` and a memory store in ChromaDB. The workflow behaves like this:

1. A service alert arrives.
2. The agent searches historical incidents for similar failures.
3. It collects evidence and retrieves the most relevant runbook.
4. It asks the decision provider whether the issue is likely a deployment regression, infra fault, or another cause.
5. It recommends an action and waits for approval before changing the system state.

## Project structure

```text
Incident-response-on-call-agent/
├── agent/
│   ├── approval.py              # human approval flow
│   ├── decision_provider.py     # mock / groq / laya provider abstraction
│   ├── embeddings.py            # embedding helpers
│   ├── graph.py                 # LangGraph workflow and stages
│   ├── incident_runner.py       # execution + state tracking + Redis sync
│   ├── listener.py              # Redis subscription entrypoint
│   ├── llm.py                   # LLM integration
│   ├── memory.py                # ChromaDB incident memory logic
│   ├── metrics.py               # metrics/query helpers
│   ├── rag.py                   # runbook ingestion and retrieval
│   ├── reasoner.py              # confidence and retry logic
│   ├── redis_queue.py           # Redis pub/sub helpers
│   ├── remediation.py           # remediation planning and execution
│   ├── simulated_env.py         # simulated infra evidence
│   ├── state.py                 # typed workflow state
│   └── tools.py                 # external integrations and helper calls
├── api/
│   └── main.py                  # FastAPI API and endpoints
├── frontend/
│   ├── package.json             # React/Vite app setup
│   ├── src/
│   └── public/
├── infra/
│   ├── docker-compose.yml
│   ├── Dockerfile
│   └── redis.conf
├── runbooks/
│   ├── db_connection_pool.md
│   ├── elasticsearch_rebalancing.md
│   ├── high_error_rate.md
│   ├── memory_leak.md
│   └── redis_connection_failure.md
├── scripts/
│   └── publish_alert.py         # publish sample alerts to Redis
├── tests/
│   └── test_decision_provider.py
├── .env.example
├── .gitignore
├── GETTING_STARTED.md
├── Procfile
├── README.md
├── requirements.txt
├── requirements-laya.txt
├── architecture.png
└── JULES_REPORT.md
```

## Quick start

### 1. Create the environment

On Windows PowerShell:

```powershell
cd D:\Incident-response-on-call-agent
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

The sample environment file includes the core variables for Redis, Groq, and approval mode. For a quick local demo, the simplest configuration is:

```env
REDIS_URL=redis://localhost:6379
USE_MOCK_LLM=1
DECISION_PROVIDER=mock
APPROVAL_MODE=manual
LANGCHAIN_TRACING_V2=false
```

For Groq-backed reasoning instead:

```env
REDIS_URL=redis://localhost:6379
USE_MOCK_LLM=1
DECISION_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_TIMEOUT_SECONDS=20
APPROVAL_MODE=manual
LANGCHAIN_TRACING_V2=false
```

### 2. Start Redis

Using Docker:

```powershell
docker run --name incident-redis -p 6379:6379 -d redis:7-alpine
```

Verify it is up:

```powershell
docker exec incident-redis redis-cli ping
```

Expected output:

```text
PONG
```

### 3. Initialize local memory and runbooks

```powershell
python -m agent.rag
python -m agent.memory
```

These commands build the local ChromaDB collections used for semantic retrieval and incident recall.

### 4. Start the API

```powershell
uvicorn api.main:app --reload --port 8000
```

Then open:

```text
http://localhost:8000/docs
```

### 5. Start the worker

In a second terminal:

```powershell
python -m agent.listener
```

The listener subscribes to the `alerts` Redis channel and executes the incident workflow when messages arrive.

### 6. Trigger a sample incident

In a third terminal:

```powershell
python scripts/publish_alert.py --sev P1
```

You can also trigger a test incident through the API:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/incidents/test/P1
```

## API overview

The backend exposes the following major endpoints:

- `GET /health` — health check for Redis, memory, Groq, and agent status
- `GET /stats` — system statistics
- `POST /incidents` — create an incident from an alert payload
- `GET /incidents` — list incidents
- `GET /incidents/{id}` — fetch incident details and timeline
- `POST /incidents/{id}/approve` — approve the recommended action
- `POST /incidents/{id}/reject` — reject the recommendation
- `GET /incidents/{id}/report` — fetch the generated incident report
- `GET /runbooks` and `GET /runbooks/{name}` — list and inspect runbooks
- `GET /memory` — query history in the memory store

The app also supports `/api/...` aliases for the same API surfaces.

## Frontend

The frontend lives in `frontend/` and uses React + Vite. It provides a lightweight dashboard for incident overview, details, runbooks, and memory views. To run it locally:

```powershell
cd frontend
npm install
npm run dev
```

## Notes and current status

- The project is designed around local-first investigation and a controlled approval loop.
- `APPROVAL_MODE=manual` is the default safe mode; the agent will not blindly execute a remediation without operator approval.
- Some integrations such as PagerDuty, Slack, Jira, and real observability backends are represented as optional or simulated layers rather than fully connected production integrations.
- For a more hands-on Windows setup guide, see [GETTING_STARTED.md](GETTING_STARTED.md).

## Recommended next steps

- add real log/metrics adapters for your environment
- connect PagerDuty, Slack, and Jira webhooks
- replace the simulated remediation logic with actual infrastructure actions
- wire the frontend to the live incident state and SSE/refresh workflow
- expand the runbook library and historical memory coverage

This repo is best treated as a prototype for building a practical, reviewable AI incident-response assistant with transparent decision-making and a human approval gate.

---

## Known limitations

- All integrations are mocked by default - real Datadog, PagerDuty, 
  and Slack need API keys wired into `.env`
- Confidence threshold (0.92) is tuned for MockLLM - needs calibration 
  when running real Ollama against production logs
- Incident memory is local ChromaDB not shared across multiple agent instances yet
- kubectl remediation calls need a real cluster pointed at `~/.kube/config`

## What's next

- [ ] Wire real Datadog log queries
- [ ] Add Slack slash command to manually trigger investigation
- [ ] Calibrate confidence scoring against real Ollama responses
- [ ] Kubernetes integration tests against a local kind cluster
- [ ] Multi-agent parallelism - separate agents per service

