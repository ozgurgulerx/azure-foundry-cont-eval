# Final Report: Azure AI Foundry Continuous Evaluation for Agents

**Date:** 2026-03-08
**Project:** azure-foundry-cont-eval
**Spec version:** 0.2.0
**Phases completed:** 0–7

---

## 1. Executive Summary

This repository provides a complete, reproducible test harness for Azure AI Foundry's continuous evaluation for Agents (preview). It configures a grounded Q&A agent, attaches continuous evaluation with 5 built-in and 4 custom evaluators, generates controlled traffic, and verifies that evaluation results appear both programmatically and in the Foundry portal.

All scripts, configs, and evaluators are implemented and verified in dry-run mode. The project is ready for execution against a live Azure AI Foundry environment.

## 2. What Was Configured

### Agent
| Setting | Value |
|---------|-------|
| Name | `cont-eval-test-agent` |
| Model | GPT-4o |
| Temperature | 0.0 (deterministic) |
| Tool | File search (knowledge base) |
| Knowledge base | 6-section Contoso Solar company facts |
| Instructions | Grounded Q&A with citation requirement |

### Continuous Evaluation Rule
| Setting | Value |
|---------|-------|
| Rule ID | `cont-eval-rule` |
| Event type | `RESPONSE_COMPLETED` |
| Max hourly runs | 100 |
| Agent filter | `cont-eval-test-agent` |
| Data source | `azure_ai_source` / `responses` |

### Built-in Evaluators (5)
| Evaluator | Pass Criterion |
|-----------|----------------|
| `builtin.violence` | Severity == "Very low" |
| `builtin.groundedness` | Score >= 3 (1–5) |
| `builtin.relevance` | Score >= 3 (1–5) |
| `builtin.coherence` | Score >= 3 (1–5) |
| `builtin.fluency` | Score >= 3 (1–5) |

### Custom Deterministic Evaluators (4)
| Evaluator | What It Checks |
|-----------|----------------|
| `citation_present` | Response references a KB section |
| `response_length` | 10–200 words |
| `refusal_on_out_of_scope` | Out-of-scope questions get refusal |
| `no_competitor_mention` | No real competitor names |

### Test Traffic
- 10 prompts total: 8 in-scope (covering all 6 KB sections), 2 out-of-scope
- Each prompt has expected response properties for verification
- 2-second delay between prompts

## 3. Signals Expected

When executed against a live environment, the following signals should appear:

### Application Insights
- Traces with `message == "gen_ai.evaluation.result"`
- Custom dimensions: `gen_ai.thread.run.id`, `gen_ai.evaluation.evaluator_name`, `gen_ai.evaluation.score`
- Queryable via Kusto in Log Analytics

### OpenAI Evals API
- `openai_client.evals.runs.list()` returns completed runs
- Each run has a `report_url` for detailed results

### Foundry Portal
- Agent Monitor tab shows evaluation score charts
- Continuous evaluation results visible in the selected time range

## 4. What Failed (Pre-Execution)

No Azure execution has been performed yet. The following are known dry-run limitations:

| Issue | Reason | Resolution |
|-------|--------|------------|
| Custom evaluators show 0% pass in dry-run | Empty responses fail citation and length checks | Expected — will pass with real agent responses |
| No eval runs or traces | No Azure calls made | Expected — run with `--execute` against live environment |
| Assumptions A1, A2, A10 unverified | Require live environment | Verify during first execution |

## 5. Practical Utility of Continuous Evaluation

Based on documentation research and implementation experience:

### What It's Good For
1. **Automated quality monitoring** — evaluators run on every response without manual intervention.
2. **Safety checks at scale** — violence detection and content safety evaluators catch harmful outputs automatically.
3. **Trend detection** — the Foundry Monitor dashboard shows score trends over time, making quality degradation visible.
4. **Debugging** — evaluation results are connected to traces, enabling root-cause analysis of low-scoring responses.
5. **Low-effort setup** — once configured, continuous evaluation runs without additional code changes.

### What It's Less Good For
1. **Deterministic verification** — built-in evaluators use LLM judgment, producing variable scores. Code-based checks must be supplemented locally.
2. **Real-time alerting** — there is a minutes-long delay between response and evaluation result visibility.
3. **Custom evaluator integration** — the `testing_criteria` format only supports `azure_ai_evaluator` types. Custom code-based evaluators cannot run inside the continuous eval rule and must be run separately.
4. **Rapid iteration** — `max_hourly_runs` caps throughput; high-volume testing requires patience or increased limits.

## 6. Gaps and Limitations

### Feature Gaps
| Gap | Impact | Workaround |
|-----|--------|------------|
| Custom code evaluators not supported in eval rules | Must run deterministic checks separately | `collect_results.py` runs them locally |
| No webhook/callback on eval completion | Must poll for results | `verify_evaluation.py` polls with backoff |
| Sampling is per-rule, not per-evaluator | Cannot evaluate safety at 100% and quality at 10% | Create multiple rules with different configs |
| Preview API instability | SDK classes may change between versions | Pin `azure-ai-projects>=2.0.0b2` |

### Documentation Gaps
| Gap | Impact |
|-----|--------|
| Exact scoring scale for each built-in evaluator is not always documented | Pass thresholds are best-guess; may need adjustment |
| Sampling behavior under `max_hourly_runs` is unclear (per-response or batched?) | Test with small traffic first |
| Interaction between multiple eval rules on same agent is undocumented | Stick to one rule per agent for testing |

### Architectural Constraints
| Constraint | Impact |
|-----------|--------|
| Must be Foundry project (not hub-based) | May require project migration |
| Project managed identity needs Azure AI User role | Additional RBAC setup step |
| Application Insights required | Cannot use alternative telemetry sinks |

## 7. Recommendations

### For Testing
1. Start with `--execute` on `setup_agent.py`, then `setup_evaluation.py`.
2. Send traffic with `generate_traffic.py --execute`.
3. Wait 5 minutes, then run `verify_evaluation.py --execute`.
4. Run `collect_results.py --execute` for the full pass/fail report.
5. Take a manual screenshot of the Foundry Monitor tab.

### For Production Use
1. Reduce `max_hourly_runs` to match expected traffic volume.
2. Add alerting rules in the Foundry portal for score drops.
3. Consider separate eval rules for safety (always-on) and quality (sampled).
4. Monitor SDK version compatibility — pin and upgrade deliberately.
5. Run custom deterministic evaluators as a scheduled job against Application Insights data.

### For Future Work
1. Explore scheduled evaluations (non-continuous) for periodic benchmark runs.
2. Investigate red team scans feature for adversarial testing.
3. Build a CI pipeline that runs traffic + verification as an integration test.
4. Evaluate whether custom `azure_ai_evaluator` types can be registered for use in eval rules.

## 8. Repository Artifacts

### Documentation
| File | Content |
|------|---------|
| `SPEC.md` | Governing specification |
| `docs/project-charter.md` | Project purpose and constraints |
| `docs/architecture.md` | System architecture, data flow, SDK patterns |
| `docs/observability-setup.md` | AppInsights setup, Kusto queries, RBAC |
| `docs/evaluator-strategy.md` | Evaluator selection, design, pass criteria |
| `docs/verification-plan.md` | Verification checks, timing, failure modes |
| `docs/decision-log.md` | 17 decisions, 12 assumptions |

### Configuration
| File | Content |
|------|---------|
| `configs/project.yaml` | Project-level settings |
| `configs/agent.yaml` | Agent + eval rule configuration |
| `configs/evaluators.yaml` | 5 built-in + 4 custom evaluator definitions |
| `configs/traffic.yaml` | 10 test prompts with expected properties |
| `configs/azure.yaml` | Azure resource topology |

### Scripts
| Script | Purpose | Dry-run verified |
|--------|---------|-----------------|
| `setup_agent.py` | Create agent + upload KB | Yes |
| `setup_evaluation.py` | Create eval object + rule | Yes |
| `generate_traffic.py` | Send 10 controlled prompts | Yes |
| `verify_evaluation.py` | Check eval runs + traces | Yes |
| `collect_results.py` | Custom evaluators + pass/fail | Yes |

### Source
| File | Purpose |
|------|---------|
| `src/utils.py` | Shared utilities (env, config, logging, artifacts) |
| `src/agent_client.py` | Agent CRUD and messaging |
| `src/observability.py` | AppInsights verification, Kusto queries, eval runs |
| `src/evaluators/deterministic.py` | 4 custom evaluators |

### Tests
| File | Tests | Status |
|------|-------|--------|
| `tests/test_deterministic_evaluators.py` | 33 | All passing |

## 9. Decision Summary

| ID | Decision | Phase |
|----|----------|-------|
| D-001 | Single-agent, single-turn Q&A | 0 |
| D-002 | GPT-4o as sole model | 0 |
| D-003 | Deterministic evaluators for rule-based checks | 0 |
| D-004 | ~~Hourly cadence~~ → Superseded by D-010 | 0 |
| D-005 | Dry-run default for all scripts | 0 |
| D-006 | Application Insights as sole telemetry sink | 0 |
| D-007 | Target New Foundry API (not Classic) | 2 |
| D-008 | Contoso Solar as fictional KB domain | 2 |
| D-009 | SDK pinned to azure-ai-projects >= 2.0.0b2 | 2 |
| D-010 | Event-driven evaluation model | 2 |
| D-011 | Foundry project required (not hub-based) | 2 |
| D-012 | Agent via create_version + PromptAgentDefinition | 2 |
| D-013 | 9 evaluators: 5 built-in + 4 custom | 3 |
| D-014 | Custom evaluators run locally | 3 |
| D-015 | Violence as primary safety evaluator | 3 |
| D-016 | Two-client SDK pattern | 4 |
| D-017 | Lazy Azure SDK imports | 4 |

---

**End of Report**
