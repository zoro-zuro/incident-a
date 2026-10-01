# Incident Response Agent: Getting Started

This guide starts the project from a freshly opened workspace on Windows and explains which parts are real, mocked, optional, or not wired yet.

## 1. What This Application Is

This is an event-driven Python incident-response service with two interfaces:

- **REST API:** FastAPI at `http://localhost:8000/docs`
- **CLI worker:** a terminal listener that subscribes to Redis and prints the agent workflow

The normal local architecture is:

```text
CLI script or REST API
        |
        v
Redis pub/sub channel: alerts
        |
        v
agent.listener -> LangGraph workflow -> ChromaDB and configured integrations
```

The CLI is not the only interface. It is the easiest way to watch the workflow. The API exposes health, incident, statistics, and Swagger endpoints.

## 2. Prerequisites

For the recommended local setup on Windows:

- Windows 10/11
- Python 3.11 or newer (Python 3.13 works in the current setup)
- Docker Desktop, used here only to run Redis
- Internet access on the first run so Python packages and the local embedding model can download
- Approximately 1 GB or more of free disk space for dependencies and model caches

Optional:

- Ollama, only if you want a local LLM instead of the built-in demo model
- A LangSmith API key, only if you want hosted tracing
- Kubernetes, PagerDuty, Slack, Jira, Prometheus, and real log storage, only for production integrations

## 3. Fresh Windows Setup

Open PowerShell in the repository folder:

```powershell
cd D:\Incident-response-on-call-agent
```

### 3.1 Start Redis with Docker

Start Docker Desktop first, then run:

```powershell
docker run --name incident-redis -p 6379:6379 -d redis:7-alpine
```

If the container already exists, start it instead:

```powershell
docker start incident-redis
```

Verify Redis:

```powershell
docker exec incident-redis redis-cli ping
```

Expected output:

```text
PONG
```

### 3.2 Create the Python environment

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Use `python -m pip`, rather than plain `pip`, so packages are installed into the same interpreter that runs the project.

### 3.3 Configure environment variables

Create the local environment file:

```powershell
Copy-Item .env.example .env
```

For a quiet local demo with the mock decision provider:

```env
REDIS_URL=redis://localhost:6379
USE_MOCK_LLM=1
DECISION_PROVIDER=mock
APPROVAL_MODE=manual
LANGCHAIN_TRACING_V2=false
```

For the Groq cloud decision provider:

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

Obtain a free Groq API key at https://console.groq.com. The key begins with `gsk_`.

The remaining integration variables can stay empty for the demo.

### 3.4 Initialize local databases

Run these once after creating the environment:

```powershell
python -m agent.rag
python -m agent.memory
```

The first command downloads `all-MiniLM-L6-v2` if necessary and embeds the Markdown runbooks into local ChromaDB. The second command seeds the local incident-memory collection.

The generated local data is stored in `.chromadb` and `.chromadb_memory`.

## 4. Start the Application

Use three PowerShell terminals. Activate `.venv` in each terminal.

### Terminal 1: API

```powershell
cd D:\Incident-response-on-call-agent
.\.venv\Scripts\Activate.ps1
uvicorn api.main:app --reload --port 8000
```

### Terminal 2: Worker

```powershell
cd D:\Incident-response-on-call-agent
.\.venv\Scripts\Activate.ps1
python -m agent.listener
```

Wait for:

```text
[queue] Subscribed to 'alerts' channel. Waiting for alerts...
```

### Terminal 3: Send a test alert

```powershell
cd D:\Incident-response-on-call-agent
.\.venv\Scripts\Activate.ps1
python scripts/publish_alert.py --sev P1
```

The worker should print `Alert received` and then the numbered incident workflow.

You can also trigger the built-in API demo:

```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/incidents/test/P1
```

Open the API UI at:

```text
http://localhost:8000/docs
```

Useful checks:

```powershell
Invoke-RestMethod http://localhost:8000/health
Invoke-RestMethod http://localhost:8000/stats
```

## 5. Stop the Application

Press `Ctrl+C` in the API and worker terminals. Stop Redis when it is no longer needed:

```powershell
docker stop incident-redis
```

Start it again next time with:

```powershell
docker start incident-redis
```

## 6. What Happened During the Test?

The P1 test used a hard-coded sample alert from `scripts/publish_alert.py`:

- Service: `checkout-service`
- Metric: `error_rate`
- Value: `8.3%`
- Threshold: `1%`
- Severity: requested as P1

The script published that JSON message to the real Redis container. The worker received it through the real Redis pub/sub channel and executed the real LangGraph control flow.

The workflow really did:

1. Parse and classify the alert.
2. Search the local ChromaDB incident-memory collection.
3. Retrieve local evidence.
4. Ask the configured reasoning implementation for a root cause.
5. Search the local ChromaDB runbook collection.
6. Produce a structured decision and request approval.
7. Apply a stateful simulated remediation only after approval.
8. Verify the changed simulated state.
9. Produce a report and save the incident to local memory.

However, the evidence and external actions in the default demo are simulated. The test did not inspect real checkout-service logs, Prometheus metrics, Kubernetes, PagerDuty, Slack, or Jira.

## 7. Real Versus Mocked Behavior

| Component | Default local behavior | Real behavior status |
|---|---|---|
| Redis queue | Real Redis in Docker | Real local infrastructure |
| LangGraph workflow | Real graph execution | Real |
| Runbook retrieval | Real ChromaDB + local embeddings over `runbooks/` | Real local data |
| Incident memory | Real ChromaDB + local embeddings over stored incidents | Real local data, seeded with demo incidents |
| Incident decision | `GroqDecisionProvider` (cloud) or `MockDecisionProvider` (offline) | Groq = real cloud LLM call; Mock = deterministic; Laya = local model |
| LLM alert normalization | `MockLLM` with hard-coded responses | No external call in mock mode |
| Logs | Generated by `agent.simulated_env` deterministic state | Simulated — no real log store |
| Metrics | Generated by `agent.simulated_env` deterministic state | Simulated — no real Prometheus |
| PagerDuty / Slack / Jira | Not in the active MVP workflow | Deactivated for the hackathon |
| Remediation | Stateful in-memory simulated service state | No external commands are allowed |
| LangSmith | Optional hosted tracing | Requires a valid API key and is disabled in the guide |

The printed ticket, Slack URL, PagerDuty ID, rollback result, logs, and metrics from the demo are therefore representative fake data, not actions against external systems.

## 8. Which Model Is Used?

There are two different kinds of models in this project.

### Reasoning and report model

With the recommended setting:

```env
USE_MOCK_LLM=1
```

the workflow uses `MockLLM` only for the initial alert normalization. Structured incident decisions come from `MockDecisionProvider`, and the report is generated deterministically. There is no LLM root-cause decision call in this mode.

If `USE_MOCK_LLM` is empty or removed, the project uses Ollama through `ChatOllama`:

```env
OLLAMA_MODEL=mistral
USE_MOCK_LLM=
```

Then install Ollama, download the model, and start Ollama:

```powershell
ollama pull mistral
ollama serve
```

Ollama runs the model locally. No OpenAI key is required. You can change `OLLAMA_MODEL` to another model installed in Ollama, such as `llama3.1`.

### Embedding model

ChromaDB uses the local Sentence Transformers model:

```text
all-MiniLM-L6-v2
```

This model creates vectors for runbooks and incident memory. It is not the root-cause reasoning model and does not replace Ollama.

## 9. How Does the Agent Get Input?

There are three local input paths:

### Fixed demo CLI input

```powershell
python scripts/publish_alert.py --sev P1
```

This sends one of the hard-coded P0, P1, or P2 sample payloads to Redis. It is fake input intended for demonstration.

### Fixed demo API input

```text
POST /incidents/test/P1
```

This creates another hard-coded sample payload in `api/main.py`.

### Custom API input

```text
POST /incidents
```

The request accepts an alert containing fields such as:

```json
{
  "title": "High error rate on checkout-service",
  "service": "checkout-service",
  "metric": "error_rate",
  "value": "8.3%",
  "threshold": "1%",
  "environment": "production",
  "tags": ["team:payments"]
}
```

This endpoint accepts custom alert input for the hackathon demo. External alert integrations are intentionally outside the active MVP path.

## 10. Decision Provider and Approval

The project supports three decision providers, selected via `DECISION_PROVIDER`:

### `groq` — Real Cloud Decision (Recommended)

```env
DECISION_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
GROQ_TIMEOUT_SECONDS=20
```

Groq receives the full structured incident context (logs, metrics, deployment history,
runbook excerpt, similar incidents) and returns a typed JSON decision. It is used
**only for the decision step** and cannot execute tools, run shell commands, modify
files, or bypass human approval.

Decision flow with Groq:

```
Evidence + ChromaDB Runbook + ChromaDB Memory
  -> DecisionProvider.evaluate_incident()
  -> Groq llama-3.3-70b-versatile (json_object mode)
  -> Structured decision: severity, hypothesis, recommended_action, confidence
  -> Human approval gate (APPROVAL_MODE)
  -> Existing simulated remediation
  -> Verification
  -> Incident report + ChromaDB memory write
```

Get a free key: https://console.groq.com

Quick connectivity test (before running the full workflow):

```powershell
$env:GROQ_API_KEY="gsk_your_key_here"
.\.venv\Scripts\python.exe -c "
import os; from groq import Groq
c = Groq(api_key=os.environ['GROQ_API_KEY'])
r = c.chat.completions.create(
  model='llama-3.3-70b-versatile',
  messages=[{'role':'user','content':'Reply: GROQ_OK'}],
  max_tokens=5
)
print(r.choices[0].message.content)
"
```

Full demo run with Groq:

```powershell
$env:DECISION_PROVIDER="groq"
$env:GROQ_API_KEY="gsk_your_key_here"
$env:APPROVAL_MODE="auto"
$env:USE_MOCK_LLM="1"
$env:LANGCHAIN_TRACING_V2="false"
$env:HF_HUB_OFFLINE="1"
.\.venv\Scripts\python.exe -m agent.graph
```

### `mock` — Offline / Testing

```env
DECISION_PROVIDER=mock
```

Deterministic decisions, no API key required. For local development, CI, and demos.

### `laya` — Local Laya Model

```env
DECISION_PROVIDER=laya
```

Loads `convaiinnovations/laya-typed-decisions` locally. Requires `pip install laya`
and high RAM. See `MIGRATION_HANDOFF.md` for setup details.

### Approval Modes

| `APPROVAL_MODE` | Behavior |
|---|---|
| `manual` (default) | Prompts for approval in the terminal. Non-interactive runs stay pending. |
| `auto` | Approved automatically — for demos and unit tests only. |
| `deny` | Always denied — for safety testing. |

Regardless of what Groq returns for `requires_approval`, the approval gate in
`agent/approval.py` is always authoritative. Groq cannot bypass it.

Ollama remains optional for alert normalization only. It is not required for the
structured decision layer, evidence, remediation, or report.

LangSmith is not required. Keep `LANGCHAIN_TRACING_V2=false` unless a valid key is set.

PagerDuty, Slack, Jira, Datadog, Prometheus, and real Kubernetes remediation are
intentionally deactivated from this MVP.

## 10a. Running the Test Suite

All tests use mocked Groq responses — no real API key is needed:

```powershell
.\.venv\Scripts\python.exe -m unittest tests/test_decision_provider.py -v
```

| Test | What it verifies |
|---|---|
| `test_mock_provider` | MockDecisionProvider returns valid schema |
| `test_laya_provider_interface` | LayaDecisionProvider interface preserved |
| `test_groq_provider_valid_schema` | Groq response validated and normalized correctly |
| `test_groq_invalid_json_rejected` | Malformed JSON raises clear RuntimeError |
| `test_groq_unauthorized_action_rejected` | Illegal action (kubectl etc.) is rejected |
| `test_groq_missing_fields_rejected` | Incomplete response raises schema error |
| `test_groq_missing_api_key` | Missing key raises clear RuntimeError |
| `test_no_silent_fallback_on_api_error` | Network failure raises error, no silent Mock fallback |
| `test_provider_selection_dispatch` | Unknown provider raises ValueError |
| `test_full_langgraph_workflow_with_groq` | Full LangGraph pipeline: Evidence->Groq->Approval->Remediation->Verification |



## 11. Common Troubleshooting

### The worker says Redis connection refused

Check Docker and Redis:

```powershell
docker start incident-redis
docker exec incident-redis redis-cli ping
Get-Content .env | Select-String REDIS_URL
```

For the Docker-only setup, `REDIS_URL` must be:

```env
REDIS_URL=redis://localhost:6379
```

Restart the worker after changing `.env`.

### The worker says LangSmith authentication failed

Set:

```env
LANGCHAIN_TRACING_V2=false
```

Then restart the worker and API.

### The first RAG or memory command downloads files

That is expected. The embedding model is downloaded once and then cached locally. A Hugging Face token is not required for this small public model.

### The alert publishes but no worker receives it

Start the worker before publishing the alert. Redis pub/sub does not retain messages for subscribers that were offline.

### `datetime.utcnow()` deprecation warnings appear

These are non-blocking warnings from the current code and do not indicate a failed incident.
