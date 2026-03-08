# Project Charter

## Project Name
Azure AI Foundry Continuous Evaluation for Agents — Test Repository

## Problem Statement
Azure AI Foundry offers continuous evaluation for Agents as a preview feature. Before relying on it for production monitoring, we need to verify:
1. Can it be configured reliably?
2. Does it produce observable, queryable results?
3. Are the built-in evaluators meaningful for our use case?
4. What are the practical limitations?

## Objective
Build a reproducible test harness that exercises continuous evaluation end-to-end and produces a structured report of findings.

## Success Criteria
See SPEC.md Section 11 — Acceptance Criteria Per Phase.

## Stakeholders
- Engineering team evaluating Azure AI Foundry for agent monitoring.

## Timeline
Phases 0–7, executed sequentially with gate checks between phases.

## Constraints
- Preview feature — API surface may change.
- Hourly evaluation cadence limits iteration speed.
- Single-agent, single-model scope.

## References
- [SPEC.md](../SPEC.md) — Governing specification.
- [Decision Log](decision-log.md) — All recorded decisions.
