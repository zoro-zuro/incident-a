# Incident Response Agent
## Architecture, Implementation Status, Demo, and Scaling Plan

## 1. Opening Statement

Our project is an event-driven incident-response simulation platform for SRE and on-call teams.

It receives an incident alert, collects evidence, searches historical incidents and runbooks, makes a structured decision, requests approval, applies a simulated remediation, verifies the result, generates a report, and stores the incident for future recall.

The important distinction is that the orchestration is real, while the infrastructure evidence and remediation are simulated for a safe hackathon demonstration.

## 2. Planned Architecture

```text
CLI Alert / FastAPI API
          |
          v
    Redis Pub/Sub
          |
          v
   Agent Listener
          |
          v
      LangGraph
          |
   +------+--------+----------------+
   |               |                |
   v               v                v
ChromaDB       Evidence         Runbooks
Memory         Collection       ChromaDB
   |               |
   |        +------+------+------+
   |        |      |      |      |
   |        v      v      v      v
   |      Logs  Metrics  Health Deployments
   |               |
   +---------------+
           |
           v
    Structured Decision Layer
       Mock Provider / Laya
           |
           v
      Human Approval
           |
           v
   Simulated Remediation
           |
           v
       Verification
           |
           v
    Incident Report
           |
           v
    ChromaDB Memory
```

## 3. Why Each Component Exists

### FastAPI

FastAPI provides the service API and Swagger UI.

Why we use it:

- Allows monitoring systems or users to submit alerts.
- Provides `/health`, `/stats`, and incident endpoints.
- Gives us a visible API interface at `/docs`.
- Separates alert ingestion from the worker process.

Current interface:

```text
http://localhost:8000/docs
```

### CLI Alert Publisher

`scripts/publish_alert.py` sends a test incident into the system.

Why we use it:

- Makes the demo repeatable.
- Allows P0, P1, and P2 sample scenarios.
- Proves that alerts enter through the same Redis queue used by the listener.

### Redis Pub/Sub

Redis is the event transport layer.

Why we use it:

- Decouples alert producers from the agent worker.
- Supports asynchronous event-driven processing.
- Allows multiple alert producers to publish to the same `alerts` channel.
- Keeps the original architecture simple for the MVP.

Redis is real in the local demo, normally running in Docker.

### Agent Listener

`agent.listener` subscribes to the Redis `alerts` channel.

Why we use it:

- Keeps the worker continuously waiting for alerts.
- Converts a Redis message into a LangGraph incident execution.
- Allows the API and CLI to use the same processing path.

### LangGraph

LangGraph is the workflow orchestrator.

Why we use it:

- Represents the incident process as explicit nodes and transitions.
- Maintains shared incident state.
- Supports branching based on confidence and decisions.
- Makes the workflow visible, testable, and extendable.

The current active workflow is:

```text
Ingest Alert
  -> Recall Incident Memory
  -> Collect Evidence
  -> Retrieve Runbook
  -> Make Structured Decision
  -> Human Approval
  -> Simulated Remediation
  -> Verification
  -> Generate Report
  -> Save Incident Memory
```

### Incident State

`agent.state.IncidentState` carries the shared state through LangGraph.

It contains:

- Original alert
- Logs
- Metrics
- Service health
- Deployment history
- Severity
- Affected services
- Similar incidents
- Runbook information
- Decision output
- Approval status
- Remediation result
- Verification result
- Final incident report

Why we use it:

- Keeps every workflow node working from the same evidence.
- Makes the decision auditable.
- Allows verification to compare state before and after remediation.

### ChromaDB Incident Memory

ChromaDB stores previous incident documents as embeddings.

Why we use it:

- Finds semantically similar incidents.
- Gives the decision layer historical context.
- Allows the system to learn from previous simulated resolutions.
- Persists incident memory locally between runs.

The current collection has been successfully queried in the Python 3.11 environment.

### ChromaDB Runbook Retrieval

Runbook Markdown files are embedded and stored in a separate ChromaDB collection.

Why we use it:

- Retrieves relevant operational guidance semantically.
- Avoids hard-coded runbook selection based only on keywords.
- Makes the workflow easy to extend by adding Markdown runbooks.

The system successfully retrieved the database connection pool runbook during validation.

### Evidence Collection

The MVP has deterministic simulated evidence tools:

- Application logs
- Service metrics
- Service health
- Deployment history

Why we use simulated evidence:

- No production monitoring credentials are needed.
- The demo is deterministic and safe.
- We can demonstrate state transitions without a Kubernetes cluster.
- The interfaces can later be replaced with Datadog, Prometheus, Loki, or CloudWatch adapters.

The tools are structured as if they were real operational data sources.

### Decision Provider

The decision layer is separated behind a provider interface:

```text
DecisionProvider
    |
    +-- MockDecisionProvider
    +-- LayaDecisionProvider
```

Why we use this boundary:

- Keeps LangGraph independent from a specific model.
- Allows guaranteed local mock operation.
- Allows Laya to return structured choices and probabilities.
- Prevents a free-form language model from directly controlling workflow execution.

The mock provider is reliable for the hackathon demo. Laya has been installed, loaded, and independently executed successfully, but the complete combined Laya plus Chroma graph has not yet completed reliably on Windows.

### Human Approval

The approval node sits between the decision and remediation.

Why we use it:

- Prevents blind automated actions.
- Makes the decision auditable.
- Creates a clear future point for a web approval interface.
- Allows manual, automatic-demo, denied, and pending modes.

For the non-interactive hackathon demo, `APPROVAL_MODE=auto` can be used. In a real workflow, approval should come from a user or incident commander.

### Simulated Remediation

The simulated environment stores service state such as:

```text
Version: v1.8
Status: degraded
Error rate: 38.2%
```

A rollback changes the state to:

```text
Version: v1.7
Status: healthy
Error rate: 0.3%
```

Why we use stateful simulation:

- Proves remediation changes something real in the demo process.
- Allows verification to inspect the new state.
- Avoids dangerous Kubernetes or shell execution.
- Makes the before/decision/action/after story visible.

No real `kubectl`, production cluster, Slack, Jira, or PagerDuty action is performed.

### Verification

Verification reads the simulated service state after remediation.

Why we use it:

- Demonstrates that the action had an observable effect.
- Prevents a fake success message from being the only result.
- Creates the foundation for real post-remediation health checks later.

### Incident Report

The report is generated from the final state.

Why we use it:

- Provides a human-readable incident summary.
- Includes the cause, evidence, decision, approval, remediation, and verification.
- Can later be generated by Ollama or another text-generation model.

## 4. What Happens During the Demo

The main demo alert is a P1 checkout-service error-rate incident.

### Initial simulated state

```text
Service: checkout-service
Version: v2.4.1
Status: degraded
Error rate: 8.3%
Threshold: 1%
Recent deployment: v2.4.1
```

### Workflow

1. The CLI publishes the alert to Redis.
2. The listener receives the Redis event.
3. LangGraph creates the incident state.
4. ChromaDB recalls similar checkout incidents.
5. Evidence tools return connection-pool logs and anomalous metrics.
6. ChromaDB retrieves the database connection pool runbook.
7. The decision provider recommends rollback.
8. Approval is requested.
9. Simulated rollback changes `v2.4.1` to `v2.4.0`.
10. Service health changes from degraded to healthy.
11. Error rate changes to a healthy simulated value.
12. Verification confirms the changed state.
13. A report is generated.
14. The incident is saved to ChromaDB memory.

## 5. Current Implementation Coverage

The percentages below measure implementation against the planned hackathon architecture, not production readiness.

| Area | Status | Approx. coverage |
|---|---|---:|
| FastAPI and Swagger | Implemented | 90% |
| CLI alert publisher | Implemented | 90% |
| Redis Pub/Sub | Implemented and tested | 95% |
| Agent listener | Implemented and tested | 90% |
| LangGraph orchestration | Implemented | 85% |
| Incident state | Implemented | 85% |
| ChromaDB incident memory | Implemented and independently tested | 85% |
| ChromaDB runbook retrieval | Implemented and independently tested | 85% |
| Simulated evidence | Implemented | 90% |
| Mock structured decision provider | Implemented | 90% |
| Laya provider | Implemented and independently predicted successfully | 70% |
| Human approval gate | Implemented | 75% |
| Stateful simulated remediation | Implemented and tested | 85% |
| Verification | Implemented and tested | 80% |
| Incident report | Implemented | 80% |
| Production integrations | Intentionally not implemented | 0% |
| Custom web dashboard | Not implemented | 0% |

### Overall Estimate

The hackathon MVP architecture is approximately **80% implemented**.

The core local simulation is approximately **90% complete**.

The remaining approximately 20% is mainly:

- Reliable combined Laya plus Chroma execution on the current Windows environment.
- A dedicated payment-service demo scenario.
- API approval/resume handling.
- Duplicate API execution prevention.
- A custom web dashboard.
- Production adapter implementations, which are intentionally outside the MVP.

These percentages should be presented as engineering estimates, not formal test coverage percentages.

## 6. Current Known Problems

### 1. Full Laya plus Chroma process is not consistently completing

Laya prediction works independently.

Chroma memory and runbook retrieval work independently.

The combined process has stalled during heavy model initialization or decision execution on Windows. This is the main remaining runtime-validation issue.

The mock provider remains the reliable presentation mode.

### 2. The current CLI sample is checkout-service

The target story mentions payment-service, but the current `scripts/publish_alert.py` P1 sample is checkout-service. The existing demo should be presented as checkout-service unless the sample is changed.

### 3. The API can duplicate work

The current POST incident path both schedules direct background processing and publishes to Redis. A production version should use one path, preferably:

```text
FastAPI -> Redis -> Listener -> LangGraph
```

### 4. External integrations are not real

PagerDuty, Slack, Jira, Datadog, Prometheus, Kubernetes, and production logs are not connected.

### 5. No custom website exists

The current visible interfaces are:

- FastAPI Swagger UI: `/docs`
- CLI listener output

There is no React dashboard or custom frontend yet.

## 7. How to Present the Current Project Honestly

Use this statement:

> We built a working event-driven incident-response simulation. The orchestration, Redis event flow, LangGraph workflow, ChromaDB memory, runbook retrieval, approval gate, stateful remediation, verification, and reporting are implemented. The operational data sources and infrastructure actions are simulated so the system can run safely without production credentials. Laya is integrated as an optional structured decision provider and works independently, while the stable demo mode uses a deterministic mock provider.

Do not say:

- We rolled back a real Kubernetes deployment.
- We paged a real PagerDuty team.
- We posted to a real Slack channel.
- We created a real Jira incident.
- We queried real production logs or Prometheus.

## 8. Future Scaling Plan

### Stage 1: Reliable MVP demonstration

- Keep Redis, LangGraph, ChromaDB, mock evidence, mock decision provider, approval, and simulated remediation.
- Add a clean payment-service demo alert.
- Fix the duplicate API execution path.
- Add an approval/resume API endpoint.
- Ensure all warnings are disabled in demo mode.

### Stage 2: Pluggable real evidence

Replace simulated evidence adapters one at a time:

```text
get_application_logs()
get_service_metrics()
get_service_health()
get_deployment_history()
```

Possible implementations:

- Loki, Datadog, or CloudWatch logs
- Prometheus metrics
- Kubernetes service health
- Kubernetes deployment history

The LangGraph workflow should remain unchanged.

### Stage 3: Safe real actions

Add production action adapters behind a policy layer:

```text
Decision
  -> Policy validation
  -> Human approval
  -> Authorized action adapter
  -> Verification
```

Actions should include:

- Idempotency keys
- Dry-run mode
- Audit logs
- Allowlisted services
- Timeout and rollback handling
- Least-privilege credentials
- Explicit approval for destructive actions

### Stage 4: Distributed scale

For multiple agent workers:

- Use Redis Streams or a durable queue instead of only pub/sub.
- Add alert IDs and idempotency keys.
- Store incident state in a shared database.
- Move ChromaDB to a shared service or managed vector store only if scale requires it.
- Separate ingestion, investigation, approval, and reporting workers.
- Add distributed locks so one incident is not processed twice.

### Stage 5: Web dashboard

Add a frontend that shows:

- Active incidents
- Evidence timeline
- Similar incidents
- Runbook match
- Laya/mock decision probabilities
- Approval controls
- Before/after simulated state
- Final report

The frontend should call FastAPI; it should not bypass Redis or LangGraph.

## 9. Closing Statement

This project is not a production SRE automation platform yet. It is a credible, safe hackathon MVP that demonstrates the complete control-plane workflow using simulated infrastructure.

The strongest demo claim is:

```text
Real event-driven orchestration
+ real vector memory and runbook retrieval
+ structured decisions
+ stateful simulated remediation
+ post-action verification
```

The strongest future claim is:

```text
Replace each simulated adapter with a real adapter without rewriting LangGraph.
```
