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
- **Status:** Active

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

---

## Assumptions

Assumptions are also listed in SPEC.md Section 5. This log tracks any updates.

| ID | Assumption | Recorded | Status |
|----|-----------|----------|--------|
| A1 | Continuous evaluation preview available in target subscription/region | 2026-03-08 | Unverified |
| A2 | GPT-4o available in chosen region | 2026-03-08 | Unverified |
| A3 | Evaluation triggers on agent thread/run completions | 2026-03-08 | Unverified |
| A4 | Hourly evaluation cadence | 2026-03-08 | Unverified |
| A5 | Application Insights is the required telemetry sink | 2026-03-08 | Unverified |
| A6 | Built-in evaluators available for continuous evaluation | 2026-03-08 | Unverified |
| A7 | Evaluation results queryable via SDK/REST | 2026-03-08 | Unverified |
| A8 | At most one evaluation run per hour per schedule | 2026-03-08 | Unverified |
| A9 | Skipped runs when no new data | 2026-03-08 | Unverified |
| A10 | Single project sufficient | 2026-03-08 | Unverified |
