# SPEC: Azure AI Foundry Continuous Evaluation for Agents — Test Repository

**Version:** 0.2.0
**Status:** Phase 2 — Agent Scenario & Observability Defined
**Created:** 2026-03-08
**Author:** Project scaffolding agent

---

## 1. Project Objective

Build a reproducible repository that configures, exercises, and verifies Azure AI Foundry continuous evaluation for Agents (preview). The goal is to prove whether continuous evaluation is correctly configured, produces observable results, and is practically useful for monitoring an Azure AI Foundry agent in near real time.

This project tests **the evaluation feature itself**, not the underlying model's quality.

## 2. Non-Goals

- Model fine-tuning or training.
- Large-scale benchmark suites.
- Production deployment hardening.
- UI or dashboard development.
- Broad multi-agent orchestration.
- Comparing models against each other.
- Offline batch evaluation (unless explicitly required to contrast with continuous evaluation).
- Integration with Azure services not required for continuous evaluation.

## 3. Scope Boundaries

### In Scope

| Area | Details |
|------|---------|
| Agent scenario | Minimal single-agent with a grounded, traceable task (Q&A over a small knowledge base). |
| Continuous evaluation config | Create and manage evaluation rules via Azure AI Foundry SDK (EvaluationRule + ContinuousEvaluationRuleAction). |
| Observability | Application Insights connection, trace collection, telemetry verification. |
| Evaluators | Built-in evaluators (groundedness, relevance, coherence, fluency, similarity) and custom deterministic evaluators. |
| Traffic generation | Scripted, controlled prompts with known-good expected outputs. |
| Verification | Programmatic inspection of evaluation runs + portal-visible evidence capture. |
| Reporting | Structured final report with findings, gaps, and recommendations. |

### Out of Scope

| Area | Reason |
|------|--------|
| Multi-turn conversation evaluation | Narrowing to single-turn for determinism. |
| Streaming responses | Adds complexity without testing the evaluation feature. |
| Custom model deployments beyond a single GPT-4o deployment | One model is sufficient. |
| Azure DevOps / GitHub Actions CI pipelines | Manual execution is sufficient for Phase 0–7. |

## 4. Prerequisites

### Azure Resources Required

| Resource | Purpose | SKU / Tier |
|----------|---------|------------|
| Azure AI Foundry project | Host the agent and evaluation (must be Foundry project, NOT hub-based) | Standard |
| Azure AI Services (multi-service) | Model deployment (GPT-4o) | S0 or pay-as-you-go |
| Application Insights | Telemetry collection for continuous evaluation | Standard |
| Log Analytics Workspace | Kusto queries for verification | Associated with AppInsights |
| Azure Blob Storage | Agent file storage (knowledge base) | Standard LRS (managed by Foundry) |

### Local Tooling

| Tool | Version | Purpose |
|------|---------|---------|
| Python | >= 3.9 | Scripts and SDK usage |
| azure-ai-projects SDK | >= 2.0.0b2 | Agent creation, evaluation rule management, OpenAI evals client |
| azure-identity | latest | Authentication (DefaultAzureCredential) |
| azure-monitor-query | >= 1.4.0 | Log Analytics / Kusto queries for verification |
| Azure CLI | >= 2.60 | Resource provisioning and RBAC setup |

### Accounts & Permissions

- Azure subscription with Contributor access to a resource group.
- Ability to create AI Foundry projects (Foundry type, not hub-based) and deploy models.
- Ability to create and manage Application Insights resources.
- Ability to assign RBAC roles (Azure AI User on project managed identity; Log Analytics Reader for verification).

## 5. Assumptions

All assumptions are recorded here and in `/docs/decision-log.md`.

| ID | Assumption | Impact if Wrong |
|----|-----------|-----------------|
| A1 | Continuous evaluation for Agents is available in preview in the target subscription and region. | Blocker — must verify in Phase 2. |
| A2 | GPT-4o is available for deployment in the chosen region. | Must pick a region where GPT-4o is available. |
| A3 | Continuous evaluation triggers on `RESPONSE_COMPLETED` events via `EvaluationRule`. | **Confirmed** — docs show `EvaluationRuleEventType.RESPONSE_COMPLETED`. |
| A4 | Evaluation runs are event-driven (per response), rate-limited by `max_hourly_runs` (default 100, max 1000). | **Corrected** — not hourly cadence but event-driven with hourly rate cap. |
| A5 | Application Insights is the required telemetry sink for continuous evaluation. | **Confirmed** — docs require AppInsights connection. |
| A6 | Built-in evaluators (violence, groundedness, relevance, coherence, fluency) are available as `builtin.*` evaluator names. | **Confirmed** — docs show `builtin.violence` pattern. |
| A7 | Evaluation results are queryable via `openai_client.evals.runs.list()` and via Kusto queries on Application Insights. | **Confirmed** — docs show both methods. |
| A8 | `max_hourly_runs` controls how many evaluation runs can execute per hour per rule (default 100, system limit 1000). | **Corrected** — not one-per-hour; rate-limited per hour. |
| A9 | Skipped runs occur when hourly run limit is reached. | **Corrected** — skips due to rate limit, not absence of data. |
| A10 | A single Azure AI Foundry project is sufficient; no cross-project evaluation is needed. | Simplifies setup. |

## 6. Repository Structure

```
azure-foundry-cont-eval/
├── SPEC.md                          # This file — governing specification
├── README.md                        # Project overview and quickstart
├── .env.template                    # Environment variable template
├── .gitignore
├── requirements.txt
├── docs/
│   ├── project-charter.md           # Why this project exists
│   ├── architecture.md              # System architecture and data flow
│   ├── observability-setup.md       # Application Insights + tracing setup
│   ├── evaluator-strategy.md        # Evaluator selection and design rationale
│   ├── verification-plan.md         # How we verify evaluation is working
│   └── decision-log.md              # All decisions and assumptions
├── configs/
│   ├── project.yaml                 # Project-level settings
│   ├── agent.yaml                   # Agent configuration
│   ├── evaluators.yaml              # Evaluator definitions and pass criteria
│   ├── traffic.yaml                 # Traffic generation parameters
│   └── azure.yaml                   # Azure resource identifiers (no secrets)
├── scripts/
│   ├── setup_agent.py               # Create or retrieve the agent
│   ├── setup_evaluation.py          # Create continuous evaluation schedule
│   ├── generate_traffic.py          # Send controlled prompts to the agent
│   ├── verify_evaluation.py         # Check that evaluation runs exist
│   └── collect_results.py           # Export evaluation results for reporting
├── src/
│   ├── __init__.py
│   ├── agent_client.py              # Agent interaction utilities
│   ├── evaluators/
│   │   ├── __init__.py
│   │   └── deterministic.py         # Custom deterministic evaluators
│   ├── observability.py             # Telemetry helpers
│   └── utils.py                     # Shared utilities
├── data/
│   └── knowledge_base.md            # Small knowledge base for the agent
├── runs/                            # Captured run metadata (gitignored except .gitkeep)
│   └── .gitkeep
└── results/                         # Reports, summaries, exported metrics
    └── .gitkeep
```

## 7. Evaluator Philosophy

### Principles

1. **Deterministic first.** If a check can be expressed as a code rule (e.g., response contains required citation, response length within bounds, response latency within threshold), implement it as a deterministic custom evaluator — not a prompt-based evaluator.
2. **Built-in second.** Use Azure AI Foundry built-in evaluators (groundedness, relevance, coherence, fluency) for subjective quality dimensions that cannot be checked deterministically.
3. **Minimal set.** Start with the smallest set of evaluators that covers distinct dimensions. Add more only if gaps are found.
4. **Clear pass criteria.** Every evaluator must have a documented pass threshold before traffic generation begins.
5. **Verifiable.** Every evaluator result must be inspectable — either via SDK query or portal screenshot.

### Planned Evaluators

| Evaluator | Type | Source | Pass Criterion | Deterministic? |
|-----------|------|--------|----------------|----------------|
| Groundedness | Built-in | Azure AI Foundry | Score >= 3 (1–5 scale) | No |
| Relevance | Built-in | Azure AI Foundry | Score >= 3 (1–5 scale) | No |
| Coherence | Built-in | Azure AI Foundry | Score >= 3 (1–5 scale) | No |
| Fluency | Built-in | Azure AI Foundry | Score >= 3 (1–5 scale) | No |
| Response contains citation | Custom | Code-based | Citation marker present | Yes |
| Response within length bounds | Custom | Code-based | 50–500 tokens | Yes |

### Evaluator Design Constraints

- Custom evaluators must be pure functions: input → score + reason.
- Custom evaluators must not call external APIs.
- Custom evaluator tests must be included in the repo.

## 8. Deterministic Guardrails

| Guardrail | Enforcement |
|-----------|-------------|
| No files outside project root | All scripts use relative paths from project root. |
| No unsupported Azure capabilities | Every Azure API call is documented with a reference URL. |
| No automatic phase advancement | Each phase ends with a gate check; agent must stop. |
| All assumptions in files | Assumptions logged in `docs/decision-log.md` and `SPEC.md`. |
| No undocumented scripts | Every script has a docstring and is listed in README. |
| No prompt-based evaluators for deterministic checks | Evaluator strategy enforces this split. |
| No state-changing Azure ops before config review | Scripts require explicit `--execute` flag; default is dry-run. |
| No mixing offline and online evaluation | Only continuous (online) evaluation unless spec is amended. |

## 9. Verification Strategy

### What We Verify

| Check | Method | Evidence |
|-------|--------|----------|
| Agent is created and responds | Script output + thread/run IDs | `runs/agent-verification.json` |
| Application Insights receives traces | Kusto query on AppInsights | Query result export |
| Continuous evaluation rule exists and is enabled | SDK get evaluation rule | `runs/rule-verification.json` |
| Evaluation run is triggered | SDK list evaluation runs | `runs/eval-runs.json` |
| Evaluation results contain expected evaluators | SDK get evaluation results | `results/eval-results.json` |
| Built-in evaluator scores are within expected range | Programmatic threshold check | `results/score-summary.json` |
| Custom evaluator scores are correct | Programmatic exact-match check | `results/custom-eval-results.json` |
| Portal shows evaluation in monitoring tab | Manual screenshot | `results/portal-screenshot.png` |

### Verification Timing

- Evaluation is event-driven: each response can trigger an eval run.
- Allow 2–5 minutes for Application Insights ingestion after traffic.
- Verification script polls with backoff, up to a configurable timeout (default 15 minutes).
- Eval run results are also queryable via `openai_client.evals.runs.list()` with `report_url`.

### Skipped-Run Handling

- If a run is skipped, it is likely due to `max_hourly_runs` being exhausted.
- The verification script checks hourly run count and logs whether the limit was reached.
- If runs are skipped despite being under the limit, this is flagged for investigation.

## 10. Phase Gates

| Phase | Gate Criteria | Artifacts |
|-------|--------------|-----------|
| 0 | SPEC.md reviewed and approved. | `SPEC.md`, `docs/decision-log.md` |
| 1 | Repo scaffolded, all placeholder files exist, structure matches spec. | All files in repo structure. |
| 2 | Agent scenario defined, agent config written, observability prerequisites documented. | `configs/agent.yaml`, `docs/observability-setup.md`, `docs/architecture.md` |
| 3 | Evaluators defined with pass criteria, custom evaluator code written and tested. | `configs/evaluators.yaml`, `src/evaluators/deterministic.py`, evaluator unit tests. |
| 4 | Setup scripts created, dry-run succeeds, `.env.template` complete. | `scripts/setup_agent.py`, `scripts/setup_evaluation.py`, `.env.template` |
| 5 | Traffic generation script created, test prompts defined, dry-run succeeds. | `scripts/generate_traffic.py`, `configs/traffic.yaml` |
| 6 | Verification script created, can query for runs (even if none exist yet). | `scripts/verify_evaluation.py`, `scripts/collect_results.py` |
| 7 | Final report produced with all sections filled. | `results/final-report.md` |

## 11. Acceptance Criteria Per Phase

### Phase 0
- [x] SPEC.md exists and covers all required sections.
- [x] Decision log initialized.
- [ ] Spec reviewed by user.

### Phase 1
- [ ] All files and directories from Section 6 exist.
- [ ] README.md has quickstart instructions.
- [ ] .gitignore covers .env, runs/*, results/* (except .gitkeep).
- [ ] requirements.txt lists all dependencies.

### Phase 2
- [ ] Agent scenario is described in `docs/architecture.md`.
- [ ] `configs/agent.yaml` defines agent name, model, instructions, and knowledge base reference.
- [ ] `docs/observability-setup.md` has step-by-step Application Insights setup.
- [ ] `configs/azure.yaml` has placeholder resource identifiers.

### Phase 3
- [ ] `configs/evaluators.yaml` lists all evaluators with pass criteria.
- [ ] `src/evaluators/deterministic.py` implements custom evaluators.
- [ ] Unit tests for custom evaluators pass.
- [ ] `docs/evaluator-strategy.md` is complete.

### Phase 4
- [ ] `scripts/setup_agent.py` can create or retrieve an agent in dry-run mode.
- [ ] `scripts/setup_evaluation.py` can create a continuous evaluation schedule in dry-run mode.
- [ ] `.env.template` lists all required environment variables.
- [ ] `configs/azure.yaml` is complete with placeholder values.

### Phase 5
- [ ] `configs/traffic.yaml` defines prompts and expected response properties.
- [ ] `scripts/generate_traffic.py` sends prompts and logs thread/run IDs.
- [ ] Dry-run mode prints what would be sent without calling Azure.

### Phase 6
- [ ] `scripts/verify_evaluation.py` queries for evaluation runs.
- [ ] `scripts/collect_results.py` exports results to `results/`.
- [ ] Verification handles skipped-run scenarios.
- [ ] Pass/fail summary is generated.

### Phase 7
- [ ] `results/final-report.md` exists with all sections.
- [ ] Report covers: configuration, signals observed, failures, practical utility, gaps, and limitations.
- [ ] All evidence files are referenced.

## 12. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Continuous evaluation preview not available in target region | Medium | Blocker | Check region availability before Phase 2; have fallback region list. |
| Evaluation runs take longer than 1 hour to appear | Medium | Delays verification | Build polling with configurable timeout (up to 4 hours). |
| SDK for continuous evaluation changes during preview | High | Script breakage | Pin SDK version; document API versions used. |
| Built-in evaluators not available for continuous eval | Low | Must use only custom evaluators | Custom evaluator fallback is already designed. |
| Application Insights data ingestion delay | Medium | False negatives in verification | Add delay tolerance to verification scripts. |
| Hourly evaluation limit prevents rapid iteration | High | Slows testing | Design traffic generation to be efficient; batch prompts before the window. |
| Evaluation results not queryable via SDK | Low | Must rely on portal screenshots | Verification plan includes manual screenshot step as fallback. |

## 13. Continuous Evaluation Specifics

### How Continuous Evaluation Works (Verified from Docs — March 2026)

1. A **Foundry project** (not hub-based) is created with an agent.
2. Application Insights is connected to the project for telemetry/tracing.
3. An **evaluation object** is created via `openai_client.evals.create()` specifying:
   - `data_source_config`: `{"type": "azure_ai_source", "scenario": "responses"}`
   - `testing_criteria`: list of `{"type": "azure_ai_evaluator", "evaluator_name": "builtin.*"}` entries
4. A **continuous evaluation rule** is created via `project_client.evaluation_rules.create_or_update()`:
   - `ContinuousEvaluationRuleAction(eval_id=..., max_hourly_runs=100)`
   - `EvaluationRuleEventType.RESPONSE_COMPLETED`
   - `EvaluationRuleFilter(agent_name=...)`
5. When the agent produces a response, the rule fires and runs the configured evaluators.
6. Results appear in Application Insights as `gen_ai.evaluation.result` traces and in the Foundry Monitor dashboard.
7. Results are queryable via `openai_client.evals.runs.list()` (includes `report_url`).

### Key Constraints

- **Event-driven**: Evaluations trigger per response, not on a schedule.
- **Rate limit**: `max_hourly_runs` caps evaluations per hour (default 100, system max 1000).
- **Skipped runs**: Occur when hourly rate limit is exhausted. Increase `max_hourly_runs` or wait.
- **Project type**: Must be a Foundry project, not hub-based.
- **RBAC**: Project managed identity needs Azure AI User role.
- **Preview limitations**: API surface may change; features may be incomplete.

### Test Design Implications

- Each agent response can trigger an evaluation (event-driven, not batched).
- With `max_hourly_runs=100` and 10 test prompts, all should be evaluated.
- Verification can begin shortly after traffic (minutes, not hours).
- Allow for Application Insights ingestion delay (typically 2-5 minutes).
- Test prompts should be distinct enough to identify in evaluation results.

## 14. Reference Documentation

- Azure AI Foundry continuous evaluation: Azure AI Foundry documentation (preview)
- Azure AI Evaluation SDK: `azure-ai-evaluation` package documentation
- Azure AI Projects SDK: `azure-ai-projects` package documentation
- Application Insights setup for AI Foundry: Azure Monitor documentation

---

**End of Spec — Phase 0 Complete**

**Next action:** User reviews this spec. Upon approval, proceed to Phase 1 (repository scaffolding).
