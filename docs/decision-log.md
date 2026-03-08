# Decision Log

All project decisions and assumptions are recorded here. Each entry is immutable once written; corrections are appended as new entries referencing the original.

---

## Format

| Field | Description |
|-------|-------------|
| ID | Sequential identifier (D-NNN) |
| Date | Date of decision |
| Phase | Phase in which the decision was made |
| Decision | What was decided |
| Rationale | Why this choice was made |
| Alternatives Considered | What else was evaluated |
| Status | Active / Superseded by D-NNN / Revoked |

---

## Decisions

### D-001: Single-agent, single-turn Q&A scenario
- **Date:** 2026-03-08
- **Phase:** 0
- **Decision:** Use a single agent with single-turn Q&A over a small knowledge base as the test scenario.
- **Rationale:** Minimizes variables. Continuous evaluation is the system under test, not the agent's conversational ability. Single-turn interactions are easier to trace and verify deterministically.
- **Alternatives Considered:** Multi-turn conversation, multi-agent routing, RAG pipeline. All rejected as adding complexity without testing the evaluation feature.
- **Status:** Active

### D-002: GPT-4o as the sole model
- **Date:** 2026-03-08
- **Phase:** 0
- **Decision:** Deploy GPT-4o as the agent's underlying model.
- **Rationale:** Widely available, well-understood behavior, good balance of quality and cost for testing. One model avoids confounding variables.
- **Alternatives Considered:** GPT-4o-mini (cheaper but less capable), GPT-4.1 (newer but less tested in Foundry agents).
- **Status:** Active

### D-003: Deterministic evaluators for rule-based checks
- **Date:** 2026-03-08
- **Phase:** 0
- **Decision:** Implement citation-presence and response-length checks as deterministic code-based evaluators, not prompt-based evaluators.
- **Rationale:** Deterministic checks are reproducible, fast, and free of LLM variability. Prompt-based evaluators should only be used for subjective quality dimensions.
- **Alternatives Considered:** Using built-in evaluators for everything. Rejected because it would conflate the evaluation feature test with LLM judge variability.
- **Status:** Active

### D-004: Hourly cadence assumed as the minimum evaluation frequency
- **Date:** 2026-03-08
- **Phase:** 0
- **Decision:** Design all timing around a 1-hour evaluation cadence.
- **Rationale:** Azure AI Foundry documentation indicates hourly as the evaluation cadence for continuous evaluation. Test design must account for this delay.
- **Alternatives Considered:** Sub-hourly cadence (not supported in preview as of spec date).
- **Status:** Superseded by D-010

### D-005: Dry-run default for all state-changing scripts
- **Date:** 2026-03-08
- **Phase:** 0
- **Decision:** All scripts that create or modify Azure resources default to dry-run mode and require an explicit `--execute` flag.
- **Rationale:** Prevents accidental resource creation or cost. Supports auditability — user sees what will happen before it happens.
- **Alternatives Considered:** Interactive confirmation prompts. Rejected because `--execute` flag is more script-friendly and auditable.
- **Status:** Active

### D-006: Application Insights as the sole telemetry sink
- **Date:** 2026-03-08
- **Phase:** 0
- **Decision:** Assume Application Insights is the required and sole telemetry sink for continuous evaluation.
- **Rationale:** All current Azure AI Foundry documentation points to Application Insights. If other sinks are supported, this decision will be updated.
- **Alternatives Considered:** Azure Monitor Logs, custom telemetry. Deferred unless Application Insights proves insufficient.
- **Status:** Active

### D-007: Target New Foundry portal API (not Classic)
- **Date:** 2026-03-08
- **Phase:** 2
- **Decision:** Use the New Foundry portal API pattern (`EvaluationRule` + `ContinuousEvaluationRuleAction`) instead of the Classic pattern (`AgentEvaluationRequest`).
- **Rationale:** The New Foundry API is the current recommended approach. Classic docs redirect to it. The New API uses `evaluation_rules.create_or_update()` and `openai_client.evals.create()`.
- **Alternatives Considered:** Classic `AgentEvaluationRequest` pattern. Rejected because it is the legacy approach.
- **Status:** Active

### D-008: Contoso Solar as the fictional knowledge base domain
- **Date:** 2026-03-08
- **Phase:** 2
- **Decision:** Use a fictional "Contoso Solar" renewable energy company as the knowledge base domain.
- **Rationale:** Provides structured, factual content across 6 sections (company, products, installation, warranty, financing, service areas). All facts are verifiable against the knowledge base, enabling groundedness evaluation. Uses the familiar "Contoso" naming convention from Azure samples.
- **Alternatives Considered:** Generic FAQ, random facts. Rejected because a coherent domain makes citation verification more meaningful.
- **Status:** Active

### D-009: SDK version pinned to azure-ai-projects >= 2.0.0b2
- **Date:** 2026-03-08
- **Phase:** 2
- **Decision:** Use `azure-ai-projects>=2.0.0b2` (not 1.0.0b*). Remove `azure-ai-evaluation` as a direct dependency — evaluator definitions are handled via the `testing_criteria` in the evals API.
- **Rationale:** The 2.0.0b2 SDK includes `evaluation_rules`, `PromptAgentDefinition`, and the OpenAI evals integration needed for continuous evaluation.
- **Alternatives Considered:** 1.0.0b7 (does not include new Foundry APIs).
- **Status:** Active

### D-010: Event-driven evaluation model (corrects D-004)
- **Date:** 2026-03-08
- **Phase:** 2
- **Decision:** Continuous evaluation is event-driven (triggers per `RESPONSE_COMPLETED`), rate-limited by `max_hourly_runs`. This supersedes D-004 which assumed hourly cadence.
- **Rationale:** Confirmed from official docs — evaluation rules fire on events, not on a timer. `max_hourly_runs` (default 100, system max 1000) controls throughput.
- **Alternatives Considered:** N/A — this is a factual correction.
- **Status:** Active (supersedes D-004)

### D-011: Foundry project required (not hub-based)
- **Date:** 2026-03-08
- **Phase:** 2
- **Decision:** The Azure AI Foundry project must be a "Foundry project" type, not a "hub-based project". Hub-based projects do not support continuous evaluation.
- **Rationale:** Explicitly stated in the official documentation prerequisites.
- **Alternatives Considered:** N/A — this is a hard requirement.
- **Status:** Active

### D-012: Agent created via create_version with PromptAgentDefinition
- **Date:** 2026-03-08
- **Phase:** 2
- **Decision:** Use `project_client.agents.create_version()` with `PromptAgentDefinition` to create the agent. This is the new Foundry SDK pattern.
- **Rationale:** Confirmed from the new Foundry docs. The older `agents.create_agent()` pattern is for classic Foundry.
- **Alternatives Considered:** Classic `create_agent()` pattern. Not compatible with new Foundry evaluation rules.
- **Status:** Active

### D-013: Nine evaluators — 5 built-in + 4 custom
- **Date:** 2026-03-08
- **Phase:** 3
- **Decision:** Use 5 built-in evaluators (violence, groundedness, relevance, coherence, fluency) and 4 custom deterministic evaluators (citation_present, response_length, refusal_on_out_of_scope, no_competitor_mention).
- **Rationale:** Built-in evaluators cover safety and subjective quality dimensions. Custom evaluators cover rule-based behavioural requirements (citation compliance, length bounds, refusal behaviour, brand safety) that can be verified deterministically.
- **Alternatives Considered:** More built-in evaluators (similarity, etc.). Rejected to keep the set minimal and avoid redundancy. Custom evaluators for latency — deferred as operational metric, not response quality.
- **Status:** Active

### D-014: Custom evaluators run locally, not in the continuous eval rule
- **Date:** 2026-03-08
- **Phase:** 3
- **Decision:** Custom evaluators run in `scripts/collect_results.py` against responses retrieved from Application Insights, not inside the continuous evaluation rule.
- **Rationale:** The continuous eval rule's `testing_criteria` accepts `azure_ai_evaluator` types (builtin.*). Custom code-based evaluators are not supported in the rule. Running locally also ensures full control and testability.
- **Alternatives Considered:** Wrapping custom evaluators as Azure AI evaluators. Adds complexity without testing the continuous eval feature — deferred.
- **Status:** Active

### D-015: Violence evaluator as primary safety evaluator
- **Date:** 2026-03-08
- **Phase:** 3
- **Decision:** Use `builtin.violence` as the safety evaluator. It is the canonical example from Azure docs and validates the safety evaluation pipeline.
- **Rationale:** The Contoso Solar scenario is unlikely to trigger violence, making it a good baseline — any detection would indicate a real problem.
- **Alternatives Considered:** builtin.hate, builtin.self_harm. Could be added but would be redundant for this test scenario.
- **Status:** Active

---

## Assumptions

Assumptions are also listed in SPEC.md Section 5. This log tracks any updates.

| ID | Assumption | Recorded | Updated | Status |
|----|-----------|----------|---------|--------|
| A1 | Continuous evaluation preview available in target subscription/region | 2026-03-08 | — | Unverified |
| A2 | GPT-4o available in chosen region | 2026-03-08 | — | Unverified |
| A3 | Evaluation triggers on RESPONSE_COMPLETED events | 2026-03-08 | 2026-03-08 | **Confirmed** (docs) |
| A4 | Event-driven eval, rate-limited by max_hourly_runs (default 100) | 2026-03-08 | 2026-03-08 | **Corrected** (was: hourly cadence) |
| A5 | Application Insights is the required telemetry sink | 2026-03-08 | 2026-03-08 | **Confirmed** (docs) |
| A6 | Built-in evaluators available as builtin.* names | 2026-03-08 | 2026-03-08 | **Confirmed** (docs) |
| A7 | Evaluation results queryable via openai_client.evals.runs.list() and Kusto | 2026-03-08 | 2026-03-08 | **Confirmed** (docs) |
| A8 | max_hourly_runs controls rate limit (default 100, max 1000) | 2026-03-08 | 2026-03-08 | **Corrected** (was: one run/hr) |
| A9 | Skipped runs when hourly limit exhausted | 2026-03-08 | 2026-03-08 | **Corrected** (was: no new data) |
| A10 | Single project sufficient | 2026-03-08 | — | Unverified |
| A11 | Must be Foundry project type (not hub-based) | 2026-03-08 | — | **Confirmed** (docs) |
| A12 | Project managed identity needs Azure AI User role | 2026-03-08 | — | **Confirmed** (docs) |
