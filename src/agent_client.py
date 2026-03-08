"""Agent interaction utilities for Azure AI Foundry.

Provides functions to:
- Create an AIProjectClient
- Create or retrieve an agent via create_version / PromptAgentDefinition
- Upload the knowledge base file for file search
- Send a message and get a response (for traffic generation)

All functions that perform Azure operations accept a `dry_run` parameter.
When dry_run=True, they log what would happen without making API calls.

Reference:
  https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/how-to-monitor-agents-dashboard
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from src.utils import get_env, load_config, require_env, timestamp_iso

logger = logging.getLogger("cont-eval.agent")


def get_project_client():
    """Create and return an AIProjectClient using DefaultAzureCredential.

    Returns:
        AIProjectClient instance.
    """
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    endpoint = require_env("AZURE_AI_PROJECT_ENDPOINT")
    credential = DefaultAzureCredential()
    return AIProjectClient(endpoint=endpoint, credential=credential)


def create_or_get_agent(dry_run: bool = True) -> dict:
    """Create a new agent version or describe what would be created.

    Uses configs/agent.yaml for agent configuration.
    Uses PromptAgentDefinition with create_version (new Foundry API).

    Args:
        dry_run: If True, log the config without calling Azure.

    Returns:
        Dict with agent metadata (id, name, version, model, instructions).
    """
    config = load_config("agent.yaml")
    agent_cfg = config["agent"]
    agent_name = get_env("AZURE_AI_AGENT_NAME", agent_cfg["name"])
    model = get_env("AZURE_MODEL_DEPLOYMENT_NAME", agent_cfg["model"])

    agent_info = {
        "timestamp": timestamp_iso(),
        "agent_name": agent_name,
        "model": model,
        "temperature": agent_cfg.get("temperature", 0.0),
        "instructions": agent_cfg["instructions"].strip(),
        "tools": agent_cfg.get("tools", []),
        "knowledge_base_file": agent_cfg.get("knowledge_base", {}).get("file", ""),
        "dry_run": dry_run,
    }

    if dry_run:
        logger.info("=== DRY RUN: Agent Creation ===")
        logger.info("Agent name: %s", agent_name)
        logger.info("Model: %s", model)
        logger.info("Temperature: %s", agent_cfg.get("temperature", 0.0))
        logger.info("Instructions: %s...", agent_cfg["instructions"][:100].strip())
        logger.info("Tools: %s", [t["type"] for t in agent_cfg.get("tools", [])])
        logger.info("Knowledge base: %s", agent_info["knowledge_base_file"])
        logger.info("=== No Azure calls made ===")
        agent_info["id"] = "dry-run-agent-id"
        agent_info["version"] = "dry-run"
        return agent_info

    # --- EXECUTE MODE ---
    from azure.ai.projects.models import PromptAgentDefinition

    project_client = get_project_client()

    with project_client:
        # Create the agent version.
        agent = project_client.agents.create_version(
            agent_name=agent_name,
            definition=PromptAgentDefinition(
                model=model,
                instructions=agent_cfg["instructions"].strip(),
                temperature=agent_cfg.get("temperature", 0.0),
                top_p=agent_cfg.get("top_p", 1.0),
            ),
        )

        agent_info["id"] = agent.id
        agent_info["name"] = agent.name
        agent_info["version"] = agent.version
        agent_info["dry_run"] = False

        logger.info("Agent created — id: %s, name: %s, version: %s", agent.id, agent.name, agent.version)

    return agent_info


def upload_knowledge_base(dry_run: bool = True) -> dict:
    """Upload the knowledge base file for the agent's file search tool.

    Args:
        dry_run: If True, log what would be uploaded without calling Azure.

    Returns:
        Dict with file metadata.
    """
    config = load_config("agent.yaml")
    kb_path_str = config["agent"].get("knowledge_base", {}).get("file", "")

    from src.utils import PROJECT_ROOT
    kb_path = PROJECT_ROOT / kb_path_str

    file_info = {
        "timestamp": timestamp_iso(),
        "source_path": str(kb_path),
        "exists": kb_path.exists(),
        "size_bytes": kb_path.stat().st_size if kb_path.exists() else 0,
        "dry_run": dry_run,
    }

    if not kb_path.exists():
        logger.error("Knowledge base file not found: %s", kb_path)
        file_info["error"] = "File not found"
        return file_info

    if dry_run:
        logger.info("=== DRY RUN: Knowledge Base Upload ===")
        logger.info("File: %s", kb_path)
        logger.info("Size: %d bytes", file_info["size_bytes"])
        logger.info("=== No Azure calls made ===")
        file_info["file_id"] = "dry-run-file-id"
        return file_info

    # --- EXECUTE MODE ---
    project_client = get_project_client()

    with project_client:
        with open(kb_path, "rb") as f:
            uploaded = project_client.agents.files.upload(
                file=f,
                purpose="assistants",
            )
        file_info["file_id"] = uploaded.id
        file_info["dry_run"] = False
        logger.info("Knowledge base uploaded — file_id: %s", uploaded.id)

    return file_info


def send_message(
    agent_name: str,
    message: str,
    *,
    dry_run: bool = True,
) -> dict:
    """Send a single message to the agent and return the response.

    Creates a new thread, sends the message, and waits for the response.
    This is the Responses API pattern for the new Foundry SDK.

    Args:
        agent_name: The agent name to interact with.
        message: The user message to send.
        dry_run: If True, log what would be sent without calling Azure.

    Returns:
        Dict with thread_id, run_id, response text, and metadata.
    """
    result = {
        "timestamp": timestamp_iso(),
        "agent_name": agent_name,
        "user_message": message,
        "dry_run": dry_run,
    }

    if dry_run:
        logger.info("=== DRY RUN: Send Message ===")
        logger.info("Agent: %s", agent_name)
        logger.info("Message: %s", message[:100])
        logger.info("=== No Azure calls made ===")
        result["response"] = "[dry-run: no response]"
        result["thread_id"] = "dry-run-thread-id"
        result["run_id"] = "dry-run-run-id"
        return result

    # --- EXECUTE MODE ---
    project_client = get_project_client()

    with project_client:
        # Create thread, send message, process run.
        thread = project_client.agents.threads.create()
        project_client.agents.messages.create(
            thread_id=thread.id,
            role="user",
            content=message,
        )
        run = project_client.agents.runs.create_and_process(
            thread_id=thread.id,
            agent_id=agent_name,
        )

        result["thread_id"] = thread.id
        result["run_id"] = run.id
        result["run_status"] = run.status

        if run.status == "failed":
            result["error"] = str(run.last_error)
            logger.error("Run failed: %s", run.last_error)
        else:
            messages = project_client.agents.messages.list(thread_id=thread.id)
            response_texts = [m.text for m in messages.text_messages if m.role == "assistant"]
            result["response"] = response_texts[0] if response_texts else ""
            logger.info("Response received — thread: %s, run: %s", thread.id, run.id)

        result["dry_run"] = False

    return result
