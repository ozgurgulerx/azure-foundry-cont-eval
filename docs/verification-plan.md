# Verification Plan

> **Status:** Complete — Phase 6.

## Overview

Verification confirms that continuous evaluation is functioning by cross-referencing traffic with evaluation results. Two scripts handle this:

- `scripts/verify_evaluation.py` — checks for eval runs and traces
- `scripts/collect_results.py` — runs custom evaluators and produces pass/fail reports

## Verification Checks

| # | Check | Script | Method | Evidence File |
|---|-------|--------|--------|---------------|
| 1 | Agent created and responds | `setup_agent.py` | Script output | `runs/agent-verification.json` |
| 2 | AppInsights receives traces | `verify_evaluation.py` | Kusto query | `runs/eval-runs.json` |
| 3 | Eval rule exists and is enabled | `setup_evaluation.py` | SDK create_or_update | `runs/rule-verification.json` |
| 4 | Eval runs are triggered | `verify_evaluation.py` | `evals.runs.list()` | `runs/eval-runs.json` |
| 5 | Eval results contain expected evaluators | `verify_evaluation.py` | Trace analysis | `runs/eval-runs.json` |
| 6 | Built-in evaluator scores within range | `collect_results.py` | Threshold comparison | `results/score-summary.json` |
| 7 | Custom evaluator scores correct | `collect_results.py` | Deterministic evaluation | `results/eval-results.json` |
| 8 | Portal shows evaluation in Monitor tab | Manual | Screenshot | `results/portal-screenshot.png` |

## Timing Strategy

1. Run `setup_agent.py --execute` — creates agent.
2. Run `setup_evaluation.py --execute` — creates eval rule.
3. Run `generate_traffic.py --execute` — sends 10 prompts.
4. Wait 2–5 minutes for Application Insights ingestion.
5. Run `verify_evaluation.py --execute` — checks for eval runs/traces.
6. Run `collect_results.py --execute` — produces pass/fail report.

If eval data is not yet available, use `--poll` flag on `verify_evaluation.py` to poll with backoff.

## Evidence Collection

All evidence is saved as JSON artifacts:

| Directory | File | Content |
|-----------|------|---------|
| `runs/` | `agent-verification.json` | Agent creation metadata |
| `runs/` | `rule-verification.json` | Eval object + rule metadata |
| `runs/` | `traffic-log.json` | All prompts, responses, thread/run IDs |
| `runs/` | `eval-runs.json` | Eval run list, traces, cross-reference, verdict |
| `results/` | `eval-results.json` | Custom evaluator results per interaction |
| `results/` | `score-summary.json` | Aggregate scores and pass/fail report |
| `results/` | `portal-screenshot.png` | Manual screenshot of Foundry Monitor tab |

## Failure Modes

| Scenario | Expected Behaviour | Resolution |
|----------|-------------------|------------|
| No eval runs after traffic | Verdict: `NO_EVAL_DATA` | Check rule is enabled; check RBAC; wait and retry |
| Some runs missing | Verdict: `PARTIAL` | Check `max_hourly_runs` limit; expand time window |
| Hourly limit exhausted | Runs skipped | Increase `max_hourly_runs` or wait for next hour |
| AppInsights ingestion delay | Empty trace query | Wait 5+ minutes; use `--poll` flag |
| Custom evaluator failures | Low pass rate | Investigate agent responses in traffic log |
| Built-in scores below threshold | `FAIL` in pass/fail | Check response quality; may indicate agent config issue |

## Verdicts

The verification script produces a structured verdict:

| Verdict | Meaning |
|---------|---------|
| `PASS` | Eval runs found, traces present, all traffic matched |
| `PARTIAL` | Some eval data found but not all traffic matched |
| `NO_EVAL_DATA` | Traffic sent but no eval runs or traces found |
| `NO_TRAFFIC` | No traffic log found — run generate_traffic.py first |
| `MISSING` | Prerequisite artifacts not found |
