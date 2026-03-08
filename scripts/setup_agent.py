"""Create or retrieve the Azure AI Foundry agent.

This script:
1. Loads agent configuration from configs/agent.yaml.
2. Uploads the knowledge base file for file search.
3. Creates a new agent version via PromptAgentDefinition.
4. Verifies Application Insights connectivity.
5. Saves agent metadata to runs/agent-verification.json.

Usage:
    python scripts/setup_agent.py              # Dry-run (default)
    python scripts/setup_agent.py --execute    # Create agent for real

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

from src.agent_client import create_or_get_agent, upload_knowledge_base
from src.observability import verify_appinsights_connection
from src.utils import (
    create_arg_parser,
    load_env,
    save_run_artifact,
    setup_logging,
    timestamp_iso,
)


def main() -> None:
    parser = create_arg_parser("Create or retrieve the Azure AI Foundry agent.")
    args = parser.parse_args()
    logger = setup_logging(args.log_level)
    load_env()

    dry_run = not args.execute
    mode = "DRY RUN" if dry_run else "EXECUTE"
    logger.info("=== setup_agent.py [%s] ===", mode)

    # Step 1: Upload knowledge base.
    logger.info("--- Step 1: Upload Knowledge Base ---")
    kb_result = upload_knowledge_base(dry_run=dry_run)

    if kb_result.get("error"):
        logger.error("Knowledge base upload failed: %s", kb_result["error"])
        sys.exit(1)

    # Step 2: Create agent.
    logger.info("--- Step 2: Create Agent ---")
    agent_result = create_or_get_agent(dry_run=dry_run)

    # Step 3: Verify Application Insights.
    logger.info("--- Step 3: Verify Application Insights ---")
    appinsights_result = verify_appinsights_connection(dry_run=dry_run)

    # Step 4: Save verification artifact.
    artifact = {
        "timestamp": timestamp_iso(),
        "mode": mode.lower().replace(" ", "-"),
        "knowledge_base": kb_result,
        "agent": agent_result,
        "appinsights": appinsights_result,
    }

    save_run_artifact("agent-verification.json", artifact)

    # Summary
    logger.info("=== Summary ===")
    logger.info("Mode: %s", mode)
    logger.info("Agent name: %s", agent_result.get("agent_name", "N/A"))
    logger.info("Agent ID: %s", agent_result.get("id", "N/A"))
    logger.info("KB file ID: %s", kb_result.get("file_id", "N/A"))
    logger.info("AppInsights connected: %s", appinsights_result.get("connected", "N/A"))
    logger.info("Artifact saved to: runs/agent-verification.json")

    if dry_run:
        logger.info("")
        logger.info("This was a dry run. To create the agent, run:")
        logger.info("  python scripts/setup_agent.py --execute")


if __name__ == "__main__":
    main()
