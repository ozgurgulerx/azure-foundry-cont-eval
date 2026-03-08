"""Telemetry and observability helpers.

Provides functions to:
- Verify Application Insights connectivity via the project client
- Query evaluation results from Log Analytics (Kusto)
- List evaluation runs via the OpenAI evals API

Reference:
  https://learn.microsoft.com/en-us/azure/foundry/observability/how-to/how-to-monitor-agents-dashboard
"""

from __future__ import annotations

import logging
import os
from datetime import timedelta

from src.utils import require_env, timestamp_iso

logger = logging.getLogger("cont-eval.observability")


def verify_appinsights_connection(dry_run: bool = True) -> dict:
    """Verify that Application Insights is connected to the Foundry project.

    Args:
        dry_run: If True, log what would be checked without calling Azure.

    Returns:
        Dict with connection status.
    """
    result = {
        "timestamp": timestamp_iso(),
        "check": "appinsights_connection",
        "dry_run": dry_run,
    }

    if dry_run:
        logger.info("=== DRY RUN: AppInsights Connection Check ===")
        logger.info("Would call project_client.telemetry.get_application_insights_connection_string()")
        logger.info("=== No Azure calls made ===")
        result["connected"] = None
        result["connection_string_prefix"] = "[dry-run]"
        return result

    # --- EXECUTE MODE ---
    from src.agent_client import get_project_client

    project_client = get_project_client()
    with project_client:
        conn_str = project_client.telemetry.get_application_insights_connection_string()

    result["connected"] = bool(conn_str)
    result["connection_string_prefix"] = conn_str[:50] + "..." if conn_str else ""
    result["dry_run"] = False

    if conn_str:
        logger.info("Application Insights connected: %s...", conn_str[:50])
    else:
        logger.warning("Application Insights NOT connected to project.")

    return result


def query_evaluation_traces(
    *,
    run_id: str | None = None,
    hours: int = 24,
    dry_run: bool = True,
) -> dict:
    """Query Application Insights for evaluation result traces.

    Uses the Log Analytics / Kusto query API to search for
    `gen_ai.evaluation.result` traces.

    Args:
        run_id: Optional run ID to filter by.
        hours: How many hours back to search.
        dry_run: If True, show the query without executing.

    Returns:
        Dict with query results or dry-run info.
    """
    run_id_filter = ""
    if run_id:
        run_id_filter = f'\n| where customDimensions["gen_ai.thread.run.id"] == "{run_id}"'

    query = f"""traces
| where timestamp > ago({hours}h)
| where message == "gen_ai.evaluation.result"{run_id_filter}
| project
    timestamp,
    run_id = tostring(customDimensions["gen_ai.thread.run.id"]),
    evaluator = tostring(customDimensions["gen_ai.evaluation.evaluator_name"]),
    score = todouble(customDimensions["gen_ai.evaluation.score"])
| order by timestamp desc"""

    result = {
        "timestamp": timestamp_iso(),
        "check": "evaluation_traces",
        "query": query,
        "hours": hours,
        "dry_run": dry_run,
    }

    if dry_run:
        logger.info("=== DRY RUN: Kusto Query ===")
        logger.info("Query:\n%s", query)
        logger.info("Workspace: $LOGS_WORKSPACE_ID")
        logger.info("=== No Azure calls made ===")
        result["rows"] = []
        return result

    # --- EXECUTE MODE ---
    from azure.identity import DefaultAzureCredential
    from azure.monitor.query import LogsQueryClient, LogsQueryStatus

    workspace_id = require_env("LOGS_WORKSPACE_ID")
    credential = DefaultAzureCredential()
    client = LogsQueryClient(credential)

    response = client.query_workspace(
        workspace_id,
        query,
        timespan=timedelta(hours=hours),
    )

    rows = []
    if response.status == LogsQueryStatus.SUCCESS:
        for table in response.tables:
            for row in table.rows:
                rows.append(dict(zip(table.columns, row)))
    else:
        logger.warning("Partial query result: %s", response.partial_error)
        for table in response.partial_data:
            for row in table.rows:
                rows.append(dict(zip(table.columns, row)))

    result["rows"] = rows
    result["count"] = len(rows)
    result["dry_run"] = False
    logger.info("Query returned %d evaluation traces.", len(rows))

    return result


def list_eval_runs(
    eval_id: str,
    *,
    limit: int = 10,
    dry_run: bool = True,
) -> dict:
    """List recent evaluation runs for a given eval object.

    Uses openai_client.evals.runs.list() to retrieve run metadata
    including report URLs.

    Args:
        eval_id: The evaluation object ID.
        limit: Maximum number of runs to retrieve.
        dry_run: If True, show what would be queried.

    Returns:
        Dict with run list or dry-run info.
    """
    result = {
        "timestamp": timestamp_iso(),
        "check": "eval_runs",
        "eval_id": eval_id,
        "limit": limit,
        "dry_run": dry_run,
    }

    if dry_run:
        logger.info("=== DRY RUN: List Eval Runs ===")
        logger.info("Would call openai_client.evals.runs.list(eval_id='%s', limit=%d)", eval_id, limit)
        logger.info("=== No Azure calls made ===")
        result["runs"] = []
        return result

    # --- EXECUTE MODE ---
    from src.agent_client import get_project_client

    project_client = get_project_client()
    with project_client:
        openai_client = project_client.get_openai_client()
        run_list = openai_client.evals.runs.list(
            eval_id=eval_id,
            order="desc",
            limit=limit,
        )

    runs = []
    for run in run_list.data:
        runs.append({
            "id": run.id,
            "status": run.status,
            "report_url": getattr(run, "report_url", None),
            "created_at": getattr(run, "created_at", None),
        })

    result["runs"] = runs
    result["count"] = len(runs)
    result["dry_run"] = False
    logger.info("Found %d evaluation runs for eval_id=%s.", len(runs), eval_id)

    return result
