# Migration Handoff

Date: 2026-10-01
Repository: `D:\Incident-response-on-call-agent`

## Objective

Migrate the existing incident-response prototype into the hackathon MVP architecture while preserving:

```text
FastAPI / CLI
  -> Redis Pub/Sub
  -> Agent Listener
  -> LangGraph
  -> ChromaDB memory and runbooks
  -> Evidence collection
  -> Decision Provider
  -> Human approval
  -> Stateful simulated remediation
  -> Verification
  -> Incident report
```

Laya must be a structured decision provider, not the workflow engine or report generator.

## Changes Already Made

Added:

- `agent/decision_provider.py`
  - `DecisionProvider`
  - `MockDecisionProvider`
  - `LayaDecisionProvider`
  - Laya checkpoint: `convaiinnovations/laya-typed-decisions`
- `agent/simulated_env.py`
  - deterministic service state
  - simulated logs, metrics, service health, deployment history
  - stateful rollback/restart/scale operations
  - verification helpers
- `agent/approval.py`
  - manual, auto, deny, and pending approval modes
- `agent/embeddings.py`
  - one cached Sentence Transformers embedding function per process
- `requirements-laya.txt`
  - optional `laya` dependency
- `GETTING_STARTED.md`
  - local startup and architecture documentation

Modified:

- `agent/graph.py`
  - active flow now includes evidence, runbook, structured decision, approval, simulated remediation, verification, report, and memory
  - PagerDuty, Slack, and Jira nodes are no longer active
- `agent/state.py`
  - added service health, deployment history, decision, approval, and verification fields
- `agent/tools.py`
  - active logs come from simulated state
- `agent/metrics.py`
  - active metrics come from simulated state
- `agent/remediation.py`
  - no runtime `kubectl`, shell, Docker, or external Redis actions
  - remediation mutates simulated state only
- `agent/rag.py` and `agent/memory.py`
  - use the shared cached embedding provider
- `.env.example`
  - added `DECISION_PROVIDER=mock`
  - added `APPROVAL_MODE=manual`
  - disabled LangSmith tracing by default
- `requirements.txt`
  - pinned the scientific stack for Python 3.11:

```text
numpy==1.26.4
scipy==1.14.1
scikit-learn==1.5.2
sentence-transformers==3.3.1
transformers==4.48.3
tokenizers==0.21.4
```

## Current Environments

Original working demo environment:

```text
.venv
```

Fresh Laya validation environment:

```text
.venv-laya311
Python 3.11.14
```

Use `.venv-laya311` for the next validation. Do not delete `.venv`.

## Confirmed Tests

### Existing local demo

Previously confirmed working:

- Docker Redis responds with `PONG`
- CLI alert publishes to Redis
- Agent listener receives Redis alert
- LangGraph executes
- Mock evidence is collected
- ChromaDB memory and runbook retrieval work in the original environment
- Simulated rollback changes state
- Verification reads the changed simulated state

### Laya

In `.venv-laya311`:

```text
LAYA_IMPORT=OK
LAYA_LOAD=OK
LAYA_PREDICT=OK
```

Successful Laya prediction returned typed results including:

```text
severity: P1
recommended_action: rollback
sufficient_evidence: True
rollback probability: 0.3249
```

Laya warnings:

- Hugging Face unauthenticated warning: non-blocking
- Windows symlink warning: non-blocking
- Invalid checkpoint temperature warning: non-blocking, but confidence is uncalibrated

The Laya provider had to be corrected using the installed package documentation:

- questions must be a dictionary keyed by question ID
- every question needs `instructions`
- `choice` questions use `criteria`, not `options`
- `predict()` returns a list containing an `answers` dictionary
- the provider now unwraps and normalizes typed answers

Relevant provider file:

```text
agent/decision_provider.py
```

### ChromaDB

Real ChromaDB validation succeeded independently in `.venv-laya311` using cached embeddings and offline mode:

```powershell
$env:HF_HUB_OFFLINE="1"
$env:HF_DATASETS_OFFLINE="1"
$env:TRANSFORMERS_OFFLINE="1"
```

Results:

```text
Runbook collection: 35 chunks
Incident memory: 3 similar incidents returned
Runbook match: db_connection_pool.md
Example similarity: 65%
```

`pip check` passed after pinning the scientific stack.

## Current Blocker

The complete combined process has not finished successfully:

```text
Real ChromaDB memory/runbook initialization
  -> LangGraph
  -> Laya decision
  -> approval
  -> remediation
  -> verification
  -> report
```

The latest full-graph run reaches:

```text
Node 1: ingest alert
recall memory
fetch evidence
fetch runbook
[decision] Evaluating structured incident decisions...
```

It then exits or is interrupted before producing the final graph result. No reliable traceback was captured from the terminal wrapper.

The blocker appears to be combined-process model initialization/inference cost on Windows, not a missing Laya model or Chroma collection:

- Chroma works independently.
- Laya prediction works independently.
- The combined graph stalls at the decision boundary after Chroma.

Do not claim the full migration is runtime-verified until this completes.

## Important Current Behavior

Laya returned rollback with confidence `0.3249`. The graph remediation threshold is `0.92`, so the current policy will not remediate this Laya result. That is expected safety behavior, but it means a successful Laya graph may produce a report without remediation unless the decision confidence is high enough.

The current CLI sample still normalizes to `checkout-service` because `MockLLM` alert ingestion returns hard-coded checkout services. The target presentation scenario is `payment-service`; this was not fully migrated yet.

## Recommended Starting Point

1. Use the existing `.venv-laya311` environment.
2. Confirm versions:

```powershell
.\.venv-laya311\Scripts\python.exe -m pip list | Select-String 'numpy|scipy|scikit-learn|sentence-transformers|transformers|tokenizers|laya'
```

Expected important versions:

```text
numpy 1.26.4
scipy 1.14.1
scikit-learn 1.5.2
sentence-transformers 3.3.1
transformers 4.48.3
tokenizers 0.21.4
```

3. Test the embedding initialization alone:

```powershell
$env:HF_HUB_OFFLINE="1"
$env:HF_DATASETS_OFFLINE="1"
$env:TRANSFORMERS_OFFLINE="1"
.\.venv-laya311\Scripts\python.exe -u -c "from agent.memory import _get_collection; print('START'); _get_collection(); print('EMBED_OK')"
```

4. Test Laya prediction alone using the previously successful command in the conversation. Do not change the provider schema again unless a new Laya traceback proves it is necessary.

5. If both isolated tests pass, run the full graph with:

```powershell
$env:HF_HUB_OFFLINE="1"
$env:HF_DATASETS_OFFLINE="1"
$env:TRANSFORMERS_OFFLINE="1"
$env:DECISION_PROVIDER="laya"
$env:APPROVAL_MODE="auto"
$env:USE_MOCK_LLM="1"
$env:LANGCHAIN_TRACING_V2="false"
.\.venv-laya311\Scripts\python.exe -m agent.graph
```

6. Capture output using native Command Prompt if the VS Code PowerShell wrapper truncates output.

## Do Not Do Yet

Do not:

- rewrite the graph
- remove Redis
- replace LangGraph
- replace ChromaDB
- add PagerDuty, Slack, Jira, Datadog, or Prometheus
- enable real Kubernetes remediation
- loosen the `0.92` remediation threshold without an explicit safety decision
- delete `.venv`
- delete `.chromadb` or `.chromadb_memory`
- claim full end-to-end completion based only on isolated Laya and Chroma tests

## Final Acceptance Criteria

The migration is complete only when one clean process demonstrates:

```text
Alert
  -> Redis
  -> Listener
  -> LangGraph
  -> Chroma memory recall
  -> Evidence
  -> Chroma runbook retrieval
  -> Laya typed decision
  -> Human approval
  -> Simulated state mutation
  -> Verification
  -> Report
  -> Chroma memory write
```

The next agent should report the exact stage reached and exact traceback if the combined process still stops.
