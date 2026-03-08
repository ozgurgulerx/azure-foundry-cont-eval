"""Verify that continuous evaluation runs exist and contain expected results.

This script:
1. Loads the rule verification artifact to get the eval object ID.
2. Lists recent eval runs via openai_client.evals.runs.list().
3. Queries Application Insights for evaluation traces.
4. Checks whether eval results exist for the traffic we sent.
5. Saves verification results to runs/eval-runs.json.

Usage:
    python scripts/verify_evaluation.py
    python scripts/verify_evaluation.py --eval-id <eval-object-id>
    python scripts/verify_evaluation.py --hours 4
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from src.observability import list_eval_runs, query_evaluation_traces
from src.utils import (
    PROJECT_ROOT,
    create_arg_parser,
    load_config,
    load_env,
    save_run_artifact,
    setup_logging,
    timestamp_iso,
)


def _load_eval_id_from_artifact() -> str | None:
    """Try to load the eval object ID from the rule verification artifact."""
    artifact_path = PROJECT_ROOT / "runs" / "rule-verification.json"
    if not artifact_path.exists():
        return None
    with open(artifact_path) as f:
        data = json.load(f)
    return data.get("eval_object", {}).get("id")


def _load_traffic_run_ids() -> list[str]:
    """Load run IDs from the traffic log artifact."""
    artifact_path = PROJECT_ROOT / "runs" / "traffic-log.json"
    if not artifact_path.exists():
        return []
    with open(artifact_path) as f:
        data = json.load(f)
    return [
        i["run_id"]
        for i in data.get("interactions", [])
        if i.get("run_id") and i["run_id"] != "dry-run-run-id"
    ]


def main() -> None:
    parser = create_arg_parser("Verify continuous evaluation runs.")
    parser.add_argument(
        "--eval-id",
        default=None,
        help="Eval object ID. If not provided, reads from runs/rule-verification.json.",
    )
    parser.add_argument(
        "--hours",
        type=int,
        default=24,
        help="Hours to look back for evaluation traces (default: 24).",
    )
    parser.add_argument(
        "--poll",
        action="store_true",
        default=False,
        help="Poll for results with backoff until found or timeout.",
    )
    parser.add_argument(
        "--poll-timeout",
        type=int,
        default=900,
        help="Max seconds to poll (default: 900 = 15 minutes).",
    )
    args = parser.parse_args()
    logger = setup_logging(args.log_level)
    load_env()

    dry_run = not args.execute
    mode = "DRY RUN" if dry_run else "EXECUTE"
    logger.info("=== verify_evaluation.py [%s] ===", mode)

    # Phase gate check.
    from src.utils import check_phase_gate
    check_phase_gate("verify_evaluation.py", execute=args.execute)

    # Resolve eval ID.
    eval_id = args.eval_id or _load_eval_id_from_artifact()
    if not eval_id:
        logger.warning("No eval ID provided and no rule-verification.json found.")
        logger.warning("Run setup_evaluation.py --execute first, or pass --eval-id.")
        if dry_run:
            eval_id = "dry-run-eval-id"
            logger.info("Using placeholder eval ID for dry run: %s", eval_id)
        else:
            sys.exit(1)

    traffic_run_ids = _load_traffic_run_ids()
    logger.info("Eval object ID: %s", eval_id)
    logger.info("Traffic run IDs found: %d", len(traffic_run_ids))
    logger.info("Look-back window: %d hours", args.hours)
    logger.info("")

    # Step 1: List eval runs.
    logger.info("--- Step 1: List Evaluation Runs ---")
    eval_runs_result = list_eval_runs(eval_id, limit=20, dry_run=dry_run)
    runs = eval_runs_result.get("runs", [])
    logger.info("Eval runs found: %d", len(runs))

    for run in runs[:5]:
        logger.info("  Run %s — status: %s, report: %s",
                     run.get("id", "?"), run.get("status", "?"),
                     run.get("report_url", "N/A"))

    # Step 2: Query AppInsights for eval traces.
    logger.info("")
    logger.info("--- Step 2: Query Evaluation Traces ---")
    traces_result = query_evaluation_traces(hours=args.hours, dry_run=dry_run)
    trace_rows = traces_result.get("rows", [])
    logger.info("Evaluation traces found: %d", len(trace_rows))

    # Step 3: Cross-reference with traffic.
    logger.info("")
    logger.info("--- Step 3: Cross-Reference with Traffic ---")
    matched_runs = set()
    unmatched_runs = set()

    if traffic_run_ids and trace_rows:
        traced_run_ids = {row.get("run_id") for row in trace_rows}
        for rid in traffic_run_ids:
            if rid in traced_run_ids:
                matched_runs.add(rid)
            else:
                unmatched_runs.add(rid)
        logger.info("Traffic runs with eval traces: %d/%d", len(matched_runs), len(traffic_run_ids))
        if unmatched_runs:
            logger.warning("Traffic runs WITHOUT eval traces: %s", unmatched_runs)
    elif dry_run:
        logger.info("[Dry run — no real cross-reference possible]")
    else:
        logger.info("No traffic runs or traces to cross-reference.")

    # Step 4: Summarise evaluator scores.
    logger.info("")
    logger.info("--- Step 4: Evaluator Score Summary ---")
    evaluator_scores: dict[str, list[float]] = {}
    for row in trace_rows:
        evaluator = row.get("evaluator", "unknown")
        score = row.get("score")
        if score is not None:
            evaluator_scores.setdefault(evaluator, []).append(float(score))

    if evaluator_scores:
        for evaluator, scores in sorted(evaluator_scores.items()):
            avg = sum(scores) / len(scores)
            logger.info("  %s — avg: %.2f, min: %.2f, max: %.2f, count: %d",
                         evaluator, avg, min(scores), max(scores), len(scores))
    elif dry_run:
        logger.info("[Dry run — no scores to summarise]")
    else:
        logger.info("No evaluator scores found.")

    # Save verification artifact.
    verification = {
        "timestamp": timestamp_iso(),
        "mode": mode.lower().replace(" ", "-"),
        "eval_id": eval_id,
        "hours": args.hours,
        "eval_runs": {
            "count": len(runs),
            "runs": runs[:20],
        },
        "eval_traces": {
            "count": len(trace_rows),
            "sample": trace_rows[:10],
        },
        "traffic_cross_reference": {
            "traffic_run_ids": traffic_run_ids,
            "matched": list(matched_runs),
            "unmatched": list(unmatched_runs),
        },
        "evaluator_summary": {
            evaluator: {
                "avg": sum(scores) / len(scores),
                "min": min(scores),
                "max": max(scores),
                "count": len(scores),
            }
            for evaluator, scores in evaluator_scores.items()
        },
        "verdict": _compute_verdict(runs, trace_rows, traffic_run_ids, matched_runs),
    }

    save_run_artifact("eval-runs.json", verification)

    # Final verdict.
    logger.info("")
    logger.info("=== Verdict ===")
    for k, v in verification["verdict"].items():
        logger.info("  %s: %s", k, v)
    logger.info("Artifact saved to: runs/eval-runs.json")


def _load_max_hourly_runs() -> int:
    """Load the configured max_hourly_runs from agent.yaml."""
    try:
        from src.utils import load_config
        config = load_config("agent.yaml")
        return config.get("evaluation", {}).get("max_hourly_runs", 100)
    except Exception:
        return 100  # Default per Azure docs.


def _compute_verdict(
    runs: list,
    trace_rows: list,
    traffic_run_ids: list,
    matched_runs: set,
) -> dict:
    """Compute a structured verdict from verification data."""
    has_runs = len(runs) > 0
    has_traces = len(trace_rows) > 0
    has_traffic = len(traffic_run_ids) > 0
    all_matched = has_traffic and len(matched_runs) == len(traffic_run_ids)

    max_hourly = _load_max_hourly_runs()
    hourly_limit_likely_hit = len(runs) >= max_hourly

    if not has_traffic:
        overall = "NO_TRAFFIC"
        detail = "No traffic run IDs found. Run generate_traffic.py --execute first."
    elif not has_runs and not has_traces:
        overall = "NO_EVAL_DATA"
        detail = "Traffic was sent but no evaluation runs or traces found. Wait and retry."
    elif has_runs and has_traces and all_matched:
        overall = "PASS"
        detail = "Evaluation runs found and all traffic runs have matching traces."
    elif has_runs or has_traces:
        overall = "PARTIAL"
        detail = (
            f"Some evaluation data found. Runs: {len(runs)}, "
            f"Traces: {len(trace_rows)}, Matched: {len(matched_runs)}/{len(traffic_run_ids)}."
        )
        if hourly_limit_likely_hit:
            detail += (
                f" WARNING: {len(runs)} runs found matches max_hourly_runs={max_hourly}. "
                "Hourly rate limit may have been reached. Consider increasing max_hourly_runs "
                "or waiting for the next hour."
            )
    else:
        overall = "UNKNOWN"
        detail = "Unexpected state."

    return {
        "overall": overall,
        "detail": detail,
        "eval_runs_found": has_runs,
        "eval_traces_found": has_traces,
        "traffic_sent": has_traffic,
        "all_traffic_matched": all_matched,
        "max_hourly_runs": max_hourly,
        "hourly_limit_likely_hit": hourly_limit_likely_hit,
    }


if __name__ == "__main__":
    main()
