"""Create a continuous evaluation rule for the agent.

This script:
1. Loads evaluator config from configs/evaluators.yaml.
2. Loads eval rule config from configs/agent.yaml (evaluation section).
3. Creates an eval object via openai_client.evals.create() with testing_criteria.
4. Creates a continuous evaluation rule via evaluation_rules.create_or_update().
5. Saves rule metadata to runs/rule-verification.json.

Usage:
    python scripts/setup_evaluation.py              # Dry-run (default)
    python scripts/setup_evaluation.py --execute    # Create rule for real

Reference:
    https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/how-to-monitor-agents-dashboard
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure project root is on sys.path for imports.
_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from src.utils import (
    create_arg_parser,
    get_env,
    load_config,
    load_env,
    save_run_artifact,
    setup_logging,
    timestamp_iso,
)


def main() -> None:
    parser = create_arg_parser("Create continuous evaluation rule for the agent.")
    args = parser.parse_args()
    logger = setup_logging(args.log_level)
    load_env()

    dry_run = not args.execute
    mode = "DRY RUN" if dry_run else "EXECUTE"
    logger.info("=== setup_evaluation.py [%s] ===", mode)

    # Phase gate check.
    from src.utils import check_phase_gate
    check_phase_gate("setup_evaluation.py", execute=args.execute)

    # Load configs.
    agent_config = load_config("agent.yaml")
    eval_config = load_config("evaluators.yaml")

    eval_section = agent_config["evaluation"]
    agent_name = get_env("AZURE_AI_AGENT_NAME", agent_config["agent"]["name"])

    # Build testing criteria from evaluators.yaml.
    testing_criteria = eval_config.get("testing_criteria", [])

    # Build data source config.
    data_source = eval_section.get("data_source", {})
    data_source_config = {
        "type": data_source.get("type", "azure_ai_source"),
        "scenario": data_source.get("scenario", "responses"),
    }

    # Build rule definition.
    rule_def = {
        "rule_id": eval_section["rule_id"],
        "display_name": eval_section["rule_display_name"],
        "description": eval_section["rule_description"],
        "event_type": eval_section["event_type"],
        "enabled": eval_section.get("enabled", True),
        "max_hourly_runs": eval_section.get("max_hourly_runs", 100),
        "eval_name": eval_section.get("eval_name", "Continuous Evaluation"),
        "agent_name": agent_name,
        "data_source_config": data_source_config,
        "testing_criteria": testing_criteria,
    }

    if dry_run:
        logger.info("--- Step 1: Create Eval Object ---")
        logger.info("=== DRY RUN: Eval Object ===")
        logger.info("Name: %s", rule_def["eval_name"])
        logger.info("Data source: %s", json.dumps(data_source_config, indent=2))
        logger.info("Testing criteria (%d evaluators):", len(testing_criteria))
        for tc in testing_criteria:
            logger.info("  - %s (%s)", tc["name"], tc["evaluator_name"])
        logger.info("=== No Azure calls made ===")

        logger.info("")
        logger.info("--- Step 2: Create Evaluation Rule ---")
        logger.info("=== DRY RUN: Evaluation Rule ===")
        logger.info("Rule ID: %s", rule_def["rule_id"])
        logger.info("Display name: %s", rule_def["display_name"])
        logger.info("Event type: %s", rule_def["event_type"])
        logger.info("Agent filter: %s", agent_name)
        logger.info("Max hourly runs: %d", rule_def["max_hourly_runs"])
        logger.info("Enabled: %s", rule_def["enabled"])
        logger.info("=== No Azure calls made ===")

        artifact = {
            "timestamp": timestamp_iso(),
            "mode": "dry-run",
            "eval_object": {
                "id": "dry-run-eval-id",
                "name": rule_def["eval_name"],
                "testing_criteria": testing_criteria,
                "data_source_config": data_source_config,
            },
            "evaluation_rule": {
                "id": "dry-run-rule-id",
                **rule_def,
            },
        }

        save_run_artifact("rule-verification.json", artifact)

        logger.info("")
        logger.info("=== Summary ===")
        logger.info("Mode: DRY RUN")
        logger.info("Eval object: %s (%d evaluators)", rule_def["eval_name"], len(testing_criteria))
        logger.info("Rule: %s → %s on %s", rule_def["rule_id"], rule_def["display_name"], rule_def["event_type"])
        logger.info("Agent filter: %s", agent_name)
        logger.info("Artifact saved to: runs/rule-verification.json")
        logger.info("")
        logger.info("This was a dry run. To create the evaluation rule, run:")
        logger.info("  python scripts/setup_evaluation.py --execute")
        return

    # --- EXECUTE MODE ---
    from src.agent_client import get_project_client

    logger.info("--- Step 1: Create Eval Object ---")
    project_client = get_project_client()

    with project_client:
        openai_client = project_client.get_openai_client()

        # Create the eval object.
        eval_object = openai_client.evals.create(
            name=rule_def["eval_name"],
            data_source_config=data_source_config,  # type: ignore
            testing_criteria=testing_criteria,  # type: ignore
        )
        logger.info("Eval object created — id: %s, name: %s", eval_object.id, eval_object.name)

        # Create the continuous evaluation rule.
        logger.info("--- Step 2: Create Evaluation Rule ---")

        from azure.ai.projects.models import (
            ContinuousEvaluationRuleAction,
            EvaluationRule,
            EvaluationRuleEventType,
            EvaluationRuleFilter,
        )

        eval_rule = project_client.evaluation_rules.create_or_update(
            id=rule_def["rule_id"],
            evaluation_rule=EvaluationRule(
                display_name=rule_def["display_name"],
                description=rule_def["description"],
                action=ContinuousEvaluationRuleAction(
                    eval_id=eval_object.id,
                    max_hourly_runs=rule_def["max_hourly_runs"],
                ),
                event_type=EvaluationRuleEventType.RESPONSE_COMPLETED,
                filter=EvaluationRuleFilter(agent_name=agent_name),
                enabled=rule_def["enabled"],
            ),
        )
        logger.info("Evaluation rule created — id: %s, name: %s", eval_rule.id, eval_rule.display_name)

    # Save artifact.
    artifact = {
        "timestamp": timestamp_iso(),
        "mode": "execute",
        "eval_object": {
            "id": eval_object.id,
            "name": eval_object.name,
            "testing_criteria": testing_criteria,
            "data_source_config": data_source_config,
        },
        "evaluation_rule": {
            "id": eval_rule.id,
            "display_name": eval_rule.display_name,
            "event_type": rule_def["event_type"],
            "agent_name": agent_name,
            "max_hourly_runs": rule_def["max_hourly_runs"],
            "enabled": rule_def["enabled"],
        },
    }

    save_run_artifact("rule-verification.json", artifact)

    logger.info("")
    logger.info("=== Summary ===")
    logger.info("Mode: EXECUTE")
    logger.info("Eval object ID: %s", eval_object.id)
    logger.info("Rule ID: %s", eval_rule.id)
    logger.info("Agent filter: %s", agent_name)
    logger.info("Artifact saved to: runs/rule-verification.json")


if __name__ == "__main__":
    main()
