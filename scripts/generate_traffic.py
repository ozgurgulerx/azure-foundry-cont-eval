"""Send controlled prompts to the agent for continuous evaluation testing.

This script:
1. Loads prompts from configs/traffic.yaml.
2. Sends each prompt to the agent via the Responses API.
3. Logs thread/run IDs for traceability.
4. Saves all interactions to runs/traffic-log.json.

Usage:
    python scripts/generate_traffic.py              # Dry-run (default)
    python scripts/generate_traffic.py --execute    # Send prompts to agent

Reference:
    configs/traffic.yaml for prompt definitions.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_project_root))

from src.agent_client import send_message
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
    parser = create_arg_parser("Send controlled prompts to the agent.")
    args = parser.parse_args()
    logger = setup_logging(args.log_level)
    load_env()

    dry_run = not args.execute
    mode = "DRY RUN" if dry_run else "EXECUTE"
    logger.info("=== generate_traffic.py [%s] ===", mode)

    # Load configs.
    traffic_config = load_config("traffic.yaml")
    agent_config = load_config("agent.yaml")

    prompts = traffic_config["traffic"]["prompts"]
    volume = traffic_config["traffic"]["volume"]
    delay = volume.get("delay_between_prompts_seconds", 2)
    agent_name = get_env("AZURE_AI_AGENT_NAME", agent_config["agent"]["name"])

    logger.info("Agent: %s", agent_name)
    logger.info("Prompts: %d", len(prompts))
    logger.info("Delay between prompts: %ds", delay)
    logger.info("")

    interactions = []

    for i, prompt in enumerate(prompts, 1):
        logger.info("--- Prompt %d/%d [%s] ---", i, len(prompts), prompt["id"])
        logger.info("Text: %s", prompt["text"])
        logger.info("Out of scope: %s", prompt["is_out_of_scope"])

        result = send_message(agent_name, prompt["text"], dry_run=dry_run)

        interaction = {
            "prompt_id": prompt["id"],
            "prompt_text": prompt["text"],
            "is_out_of_scope": prompt["is_out_of_scope"],
            "expected_section": prompt.get("expected_section"),
            "expected_properties": prompt.get("expected_properties", {}),
            "thread_id": result.get("thread_id"),
            "run_id": result.get("run_id"),
            "run_status": result.get("run_status", "dry-run"),
            "response": result.get("response", ""),
            "error": result.get("error"),
            "timestamp": result.get("timestamp"),
        }
        interactions.append(interaction)

        if result.get("error"):
            logger.error("  Error: %s", result["error"])
        else:
            response_preview = (result.get("response") or "")[:120]
            logger.info("  Response: %s", response_preview)

        # Delay between prompts (skip after last).
        if i < len(prompts) and not dry_run:
            logger.info("  Waiting %ds...", delay)
            time.sleep(delay)

    # Save traffic log.
    traffic_log = {
        "timestamp": timestamp_iso(),
        "mode": mode.lower().replace(" ", "-"),
        "agent_name": agent_name,
        "total_prompts": len(prompts),
        "successful": sum(1 for i in interactions if not i.get("error")),
        "failed": sum(1 for i in interactions if i.get("error")),
        "interactions": interactions,
    }

    save_run_artifact("traffic-log.json", traffic_log)

    # Summary.
    logger.info("")
    logger.info("=== Summary ===")
    logger.info("Mode: %s", mode)
    logger.info("Total prompts: %d", len(prompts))
    logger.info("Successful: %d", traffic_log["successful"])
    logger.info("Failed: %d", traffic_log["failed"])
    logger.info("In-scope: %d", sum(1 for p in prompts if not p["is_out_of_scope"]))
    logger.info("Out-of-scope: %d", sum(1 for p in prompts if p["is_out_of_scope"]))
    logger.info("Artifact saved to: runs/traffic-log.json")

    if dry_run:
        logger.info("")
        logger.info("This was a dry run. To send prompts to the agent, run:")
        logger.info("  python scripts/generate_traffic.py --execute")


if __name__ == "__main__":
    main()
