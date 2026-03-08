# Architecture

> **Status:** Complete — Phase 2.

## Overview

This project deploys a single Azure AI Foundry Agent that answers factual questions about a fictional company (Contoso Solar) using a small, structured knowledge base. Continuous evaluation is configured as an event-driven rule that fires on every `RESPONSE_COMPLETED` event, evaluating sampled agent responses against built-in and custom evaluators. Results flow to Application Insights and are visible in the Foundry Observability dashboard.

## Agent Scenario

**Task:** Grounded Q&A over a small knowledge base about Contoso Solar (fictional renewable energy company).

**Why this scenario:**
- Single-turn Q&A is the simplest traceable interaction pattern.
- A small, controlled knowledge base makes groundedness verifiable.
- Factual questions have deterministic expected answers, enabling custom evaluator validation.
- The scenario exercises the agent's file search tool, which is a common production pattern.

**Agent behavior:**
1. Receives a user question about Contoso Solar.
2. Searches the attached knowledge base using file search.
3. Returns a grounded answer with citation references.

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        Test Harness (scripts/)                         │
│                                                                        │
│  generate_traffic.py                                                   │
│       │                                                                │
│       │  Creates thread + message + run                                │
│       ▼                                                                │
│  ┌──────────────────────────────────────────────┐                      │
│  │       Azure AI Foundry Project                │                     │
│  │                                               │                     │
│  │  ┌─────────────┐    ┌──────────────────────┐  │                     │
│  │  │   Agent      │    │  File Search Tool    │  │                     │
│  │  │  (GPT-4o)    │───▶│  (knowledge_base.md) │  │                     │
│  │  │              │◀───│                      │  │                     │
│  │  └──────┬───────┘    └──────────────────────┘  │                     │
│  │         │                                      │                     │
│  │         │ RESPONSE_COMPLETED event             │                     │
│  │         ▼                                      │                     │
│  │  ┌──────────────────────────────────────────┐  │                     │
│  │  │  Continuous Evaluation Rule               │  │                     │
│  │  │  ─ Triggers on RESPONSE_COMPLETED         │  │                     │
│  │  │  ─ Runs configured evaluators             │  │                     │
│  │  │  ─ Sampling: 100% (test), max 100/hr      │  │                     │
│  │  └──────┬───────────────────────────────────┘  │                     │
│  │         │                                      │                     │
│  │         ▼                                      │                     │
│  │  ┌──────────────────────────────────────────┐  │                     │
│  │  │  Evaluators                               │  │                     │
│  │  │  ─ builtin.violence (safety)              │  │                     │
│  │  │  ─ builtin.groundedness (quality)         │  │                     │
│  │  │  ─ builtin.relevance (quality)            │  │                     │
│  │  │  ─ builtin.coherence (quality)            │  │                     │
│  │  │  ─ builtin.fluency (quality)              │  │                     │
│  │  └──────┬───────────────────────────────────┘  │                     │
│  │         │                                      │                     │
│  └─────────┼──────────────────────────────────────┘                     │
│            │                                                            │
│            ▼                                                            │
│  ┌──────────────────────────────────────────────┐                      │
│  │  Application Insights                         │                     │
│  │  ─ Traces: gen_ai.evaluation.result           │                     │
│  │  ─ Custom dimensions: scores, evaluator IDs   │                     │
│  │  ─ Queryable via Log Analytics / Kusto         │                     │
│  └──────┬───────────────────────────────────────┘                      │
│         │                                                              │
│         ▼                                                              │
│  ┌──────────────────────────────────────────────┐                      │
│  │  Verification (scripts/)                      │                     │
│  │  ─ verify_evaluation.py: list eval runs       │                     │
│  │  ─ collect_results.py: export to results/     │                     │
│  │  ─ Portal: Foundry Monitor tab screenshot     │                     │
│  └──────────────────────────────────────────────┘                      │
│                                                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

## Components

| Component | Implementation | Purpose |
|-----------|---------------|---------|
| **Agent** | Azure AI Foundry Agent (GPT-4o) with file search tool | Answers questions using knowledge base |
| **Knowledge Base** | `data/knowledge_base.md` uploaded as agent file | Provides grounded facts for agent responses |
| **Evaluation Object** | Created via `openai_client.evals.create()` | Defines evaluators and data source config |
| **Evaluation Rule** | `EvaluationRule` with `ContinuousEvaluationRuleAction` | Triggers evaluation on each response completion |
| **Application Insights** | Connected to Foundry project | Stores traces, evaluation results, operational metrics |
| **Traffic Generator** | `scripts/generate_traffic.py` | Sends controlled prompts via Responses API |
| **Verifier** | `scripts/verify_evaluation.py` | Queries eval runs via OpenAI evals API |

## Azure Resources

```
Resource Group
├── Azure AI Foundry Project (Foundry project, NOT hub-based)
│   ├── Agent: cont-eval-test-agent
│   │   ├── Model: GPT-4o deployment
│   │   └── Tool: File Search (knowledge_base.md)
│   ├── Evaluation Object (continuous eval config)
│   └── Evaluation Rule (RESPONSE_COMPLETED trigger)
├── Application Insights
│   └── Log Analytics Workspace
└── Storage Account (managed by Foundry)
```

## SDK Architecture

The new Foundry SDK uses two client patterns:

1. **`AIProjectClient`** — for agent management, evaluation rules, telemetry config
   - `project_client.agents.create_version()` — create/version agents
   - `project_client.evaluation_rules.create_or_update()` — manage eval rules
   - `project_client.telemetry.get_application_insights_connection_string()` — get AppInsights config

2. **OpenAI client** (obtained via `project_client.get_openai_client()`) — for eval objects and runs
   - `openai_client.evals.create()` — create evaluation definitions
   - `openai_client.evals.runs.list()` — list evaluation run results

3. **`LogsQueryClient`** (from `azure-monitor-query`) — for querying Application Insights
   - Kusto queries against the `traces` table
   - Filter on `message == "gen_ai.evaluation.result"`

## Key API Models

| Model | Package | Purpose |
|-------|---------|---------|
| `PromptAgentDefinition` | azure-ai-projects | Agent definition with model and instructions |
| `EvaluationRule` | azure-ai-projects | Rule that triggers evaluation on events |
| `ContinuousEvaluationRuleAction` | azure-ai-projects | Action config with eval_id and max_hourly_runs |
| `EvaluationRuleFilter` | azure-ai-projects | Filter by agent_name |
| `EvaluationRuleEventType` | azure-ai-projects | Event types (RESPONSE_COMPLETED) |

## Authentication

All scripts use `DefaultAzureCredential` from `azure-identity`. This supports:
- Azure CLI login (`az login`) — recommended for local development
- Managed identity — for automated environments
- Environment variables — fallback

Additionally, the **Foundry project's managed identity** must have the **Azure AI User** role assigned on the project resource for evaluation rules to function.
