"""Export evaluation results and run custom evaluators for reporting.

This script:
1. Loads traffic log from runs/traffic-log.json.
2. Loads eval run data from runs/eval-runs.json.
3. Runs custom deterministic evaluators against collected responses.
4. Produces a combined results summary in results/.
5. Generates a pass/fail report against all evaluator thresholds.

Usage:
    python scripts/collect_results.py
    python scripts/collect_results.py --execute
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from src.evaluators.deterministic import (
    evaluate_citation_present,
    evaluate_no_competitor_mention,
    evaluate_refusal_on_out_of_scope,
    evaluate_response_length,
)
from src.utils import (
    PROJECT_ROOT,
    create_arg_parser,
    load_config,
    load_env,
    save_result_artifact,
    setup_logging,
    timestamp_iso,
)


def _load_json_artifact(subdir: str, filename: str) -> dict | None:
    """Load a JSON artifact if it exists."""
    path = PROJECT_ROOT / subdir / filename
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def main() -> None:
    parser = create_arg_parser("Export evaluation results and run custom evaluators.")
    args = parser.parse_args()

    from src.utils import check_phase_gate
    logger = setup_logging(args.log_level)
    load_env()

    dry_run = not args.execute
    mode = "DRY RUN" if dry_run else "EXECUTE"
    logger.info("=== collect_results.py [%s] ===", mode)

    # Phase gate check.
    check_phase_gate("collect_results.py", execute=args.execute)

    # Load evaluator config for pass criteria.
    eval_config = load_config("evaluators.yaml")

    # Load traffic log.
    traffic_log = _load_json_artifact("runs", "traffic-log.json")
    if not traffic_log:
        logger.warning("No traffic log found at runs/traffic-log.json.")
        logger.warning("Run generate_traffic.py first.")
        traffic_log = {"interactions": [], "mode": "missing"}

    # Load eval runs verification.
    eval_runs = _load_json_artifact("runs", "eval-runs.json")
    if not eval_runs:
        logger.warning("No eval runs found at runs/eval-runs.json.")
        logger.warning("Run verify_evaluation.py first.")
        eval_runs = {"evaluator_summary": {}, "verdict": {"overall": "MISSING"}}

    interactions = traffic_log.get("interactions", [])
    logger.info("Interactions loaded: %d", len(interactions))
    logger.info("")

    # --- Run custom deterministic evaluators ---
    logger.info("--- Custom Evaluator Results ---")
    custom_results = []

    for interaction in interactions:
        response = interaction.get("response", "")
        is_oos = interaction.get("is_out_of_scope", False)
        prompt_id = interaction.get("prompt_id", "?")

        # Skip dry-run placeholders.
        if response == "[dry-run: no response]" and dry_run:
            response = ""

        results = {
            "prompt_id": prompt_id,
            "is_out_of_scope": is_oos,
            "response_preview": response[:100] if response else "[empty]",
            "evaluators": {},
        }

        # Run each custom evaluator.
        citation = evaluate_citation_present(response)
        results["evaluators"]["citation_present"] = citation

        length = evaluate_response_length(response)
        results["evaluators"]["response_length"] = length

        refusal = evaluate_refusal_on_out_of_scope(response, is_oos)
        results["evaluators"]["refusal_on_out_of_scope"] = refusal

        competitor = evaluate_no_competitor_mention(response)
        results["evaluators"]["no_competitor_mention"] = competitor

        custom_results.append(results)

        logger.info("  [%s] citation=%d, length=%d, refusal=%d, competitor=%d",
                     prompt_id,
                     citation["score"], length["score"],
                     refusal["score"], competitor["score"])

    # --- Aggregate custom evaluator results ---
    logger.info("")
    logger.info("--- Custom Evaluator Aggregates ---")
    custom_aggregates = {}
    evaluator_names = ["citation_present", "response_length",
                       "refusal_on_out_of_scope", "no_competitor_mention"]

    for name in evaluator_names:
        scores = [
            r["evaluators"][name]["score"]
            for r in custom_results
            if name in r["evaluators"]
        ]
        if scores:
            custom_aggregates[name] = {
                "total": len(scores),
                "passed": sum(scores),
                "failed": len(scores) - sum(scores),
                "pass_rate": sum(scores) / len(scores),
            }
            logger.info("  %s — %d/%d passed (%.0f%%)",
                         name, sum(scores), len(scores),
                         100 * sum(scores) / len(scores))

    # --- Built-in evaluator summary (from verification) ---
    logger.info("")
    logger.info("--- Built-in Evaluator Summary ---")
    builtin_summary = eval_runs.get("evaluator_summary", {})
    if builtin_summary:
        for name, stats in sorted(builtin_summary.items()):
            logger.info("  %s — avg: %.2f, min: %.2f, max: %.2f, count: %d",
                         name, stats["avg"], stats["min"], stats["max"], stats["count"])
    else:
        logger.info("  [No built-in evaluator data available]")

    # --- Pass/Fail determination ---
    logger.info("")
    logger.info("--- Pass/Fail Report ---")
    pass_fail = {}

    # Custom evaluators: all must have 100% pass rate.
    for name, agg in custom_aggregates.items():
        passed = agg["pass_rate"] == 1.0
        pass_fail[name] = {
            "type": "custom",
            "passed": passed,
            "pass_rate": agg["pass_rate"],
            "detail": f"{agg['passed']}/{agg['total']} passed",
        }
        status = "PASS" if passed else "FAIL"
        logger.info("  [%s] %s — %s", status, name, pass_fail[name]["detail"])

    # Built-in evaluators: avg score >= threshold.
    builtin_thresholds = {}
    for ev in eval_config.get("builtin_evaluators", []):
        pc = ev.get("pass_criterion", {})
        builtin_thresholds[ev["name"]] = {
            "operator": pc.get("operator", ">="),
            "threshold": pc.get("threshold", 3),
        }

    for name, stats in builtin_summary.items():
        threshold_info = builtin_thresholds.get(name, {"operator": ">=", "threshold": 3})
        threshold = threshold_info["threshold"]
        if isinstance(threshold, (int, float)):
            passed = stats["avg"] >= threshold
        else:
            passed = True  # Non-numeric thresholds (e.g., severity labels) — manual check needed
        pass_fail[name] = {
            "type": "builtin",
            "passed": passed,
            "avg_score": stats["avg"],
            "threshold": threshold,
            "detail": f"avg={stats['avg']:.2f} (threshold: {threshold})",
        }
        status = "PASS" if passed else "FAIL"
        logger.info("  [%s] %s — %s", status, name, pass_fail[name]["detail"])

    # --- Overall verdict ---
    all_passed = all(pf["passed"] for pf in pass_fail.values()) if pass_fail else False
    overall = "PASS" if all_passed else ("FAIL" if pass_fail else "NO_DATA")

    # --- Save results ---
    results_data = {
        "timestamp": timestamp_iso(),
        "mode": mode.lower().replace(" ", "-"),
        "custom_evaluator_results": custom_results,
        "custom_evaluator_aggregates": custom_aggregates,
        "builtin_evaluator_summary": builtin_summary,
        "pass_fail_report": pass_fail,
        "overall_verdict": overall,
        "verification_verdict": eval_runs.get("verdict", {}),
    }

    save_result_artifact("eval-results.json", results_data)
    save_result_artifact("score-summary.json", {
        "timestamp": timestamp_iso(),
        "custom": custom_aggregates,
        "builtin": builtin_summary,
        "pass_fail": pass_fail,
        "overall": overall,
    })

    logger.info("")
    logger.info("=== Overall Verdict: %s ===", overall)
    logger.info("Results saved to: results/eval-results.json")
    logger.info("Score summary saved to: results/score-summary.json")


if __name__ == "__main__":
    main()
