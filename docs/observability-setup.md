# Observability Setup

> **Status:** Complete — Phase 2.

## Overview

Continuous evaluation requires Application Insights connected to the Foundry project. Evaluation results are written as traces with the message `gen_ai.evaluation.result` and can be queried via Log Analytics (Kusto) or viewed in the Foundry Observability dashboard.

## Prerequisites

| Requirement | Details |
|------------|---------|
| Foundry project | Must be a **Foundry project** (not hub-based). See [project types](https://learn.microsoft.com/en-us/azure/ai-foundry/what-is-foundry#how-do-i-know-which-type-of-project-i-have). |
| Application Insights resource | Standard Application Insights in the same subscription. |
| Log Analytics workspace | Automatically associated with Application Insights. |
| RBAC roles | **Contributor** on Application Insights; **Log Analytics Reader** for querying logs. |
| Project managed identity | Must have **Azure AI User** role on the Foundry project resource. |

## Step 1: Create Application Insights Resource

If you don't have an existing Application Insights resource:

```bash
# Create resource group (if needed)
az group create \
  --name <resource-group> \
  --location <region>

# Create Application Insights
az monitor app-insights component create \
  --app <appinsights-name> \
  --location <region> \
  --resource-group <resource-group> \
  --kind web \
  --application-type web

# Get the connection string
az monitor app-insights component show \
  --app <appinsights-name> \
  --resource-group <resource-group> \
  --query connectionString \
  --output tsv
```

Save the connection string to `.env` as `APPLICATIONINSIGHTS_CONNECTION_STRING`.

## Step 2: Connect Application Insights to Foundry Project

### Via Portal (New Foundry)

1. Sign in to [Microsoft Foundry](https://ai.azure.com). Ensure the **New Foundry** toggle is **on**.
2. Navigate to your project.
3. Go to **Build** → select your agent → **Monitor** tab.
4. Select the **gear icon** to open Monitor settings.
5. Under **Operational metrics**, connect your Application Insights resource.

### Via Portal (Classic Foundry)

1. Sign in to [Microsoft Foundry](https://ai.azure.com). Ensure the **New Foundry** toggle is **off**.
2. Select **Monitoring** on the left-hand menu → **Application Analytics**.
3. Connect your Application Insights resource to the project.

### Programmatic Verification

After connecting, verify via SDK:

```python
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

project_client = AIProjectClient(
    endpoint=os.environ["AZURE_AI_PROJECT_ENDPOINT"],
    credential=DefaultAzureCredential(),
)

# This should return a non-empty connection string
conn_str = project_client.telemetry.get_application_insights_connection_string()
print(f"AppInsights connected: {bool(conn_str)}")
print(f"Connection string: {conn_str[:50]}...")
```

## Step 3: Assign Managed Identity Permissions

The Foundry project's managed identity needs the **Azure AI User** role to create evaluation rules:

```bash
# Get the project's managed identity principal ID
# (Find this in Azure Portal → Foundry project resource → Identity)

# Assign Azure AI User role
az role assignment create \
  --assignee <project-managed-identity-principal-id> \
  --role "Azure AI User" \
  --scope /subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.MachineLearningServices/workspaces/<project-name>
```

## Step 4: Verify Telemetry Flow

After the agent handles at least one interaction, verify traces appear in Application Insights.

### Kusto Query: Check for Agent Traces

```kusto
traces
| where timestamp > ago(1h)
| where message has "gen_ai"
| summarize count() by message
| order by count_ desc
```

### Kusto Query: Check for Evaluation Results

```kusto
traces
| where timestamp > ago(1h)
| where message == "gen_ai.evaluation.result"
| project
    timestamp,
    customDimensions["gen_ai.thread.run.id"],
    customDimensions["gen_ai.evaluation.evaluator_name"],
    customDimensions["gen_ai.evaluation.score"]
| order by timestamp desc
```

### Kusto Query: Check for Specific Agent's Evaluations

```kusto
traces
| where timestamp > ago(24h)
| where message == "gen_ai.evaluation.result"
| extend
    run_id = tostring(customDimensions["gen_ai.thread.run.id"]),
    evaluator = tostring(customDimensions["gen_ai.evaluation.evaluator_name"]),
    score = todouble(customDimensions["gen_ai.evaluation.score"])
| summarize
    avg_score = avg(score),
    min_score = min(score),
    max_score = max(score),
    count = count()
    by evaluator
```

## Step 5: Access the Foundry Monitoring Dashboard

1. In Microsoft Foundry (new), go to **Build** → select your agent.
2. Select the **Monitor** tab.
3. The dashboard shows:
   - **Token usage** — token counts for agent traffic
   - **Latency** — response time for agent runs
   - **Run success rate** — percentage of successful runs
   - **Evaluation metrics** — scores from continuous evaluation
4. Adjust the time range to match your traffic generation window.

## Environment Variables Summary

| Variable | Source | Purpose |
|----------|--------|---------|
| `AZURE_AI_PROJECT_ENDPOINT` | Foundry project overview page | SDK authentication |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Application Insights resource | Direct AppInsights access |
| `APPINSIGHTS_RESOURCE_ID` | Application Insights resource | Resource identification |
| `LOGS_WORKSPACE_ID` | Log Analytics workspace | Kusto query target |

## Troubleshooting

| Symptom | Likely Cause | Resolution |
|---------|-------------|------------|
| No traces in Application Insights | AppInsights not connected to project | Re-do Step 2 |
| Traces appear but no evaluation results | Evaluation rule not created or not enabled | Check `scripts/setup_evaluation.py` output |
| Authorization errors on Kusto queries | Missing Log Analytics Reader role | Assign role per Step 3 |
| Evaluation rule creation fails | Missing Azure AI User role on managed identity | Assign role per Step 3 |
| Dashboard shows no data | Time range doesn't include traffic window | Expand time range; wait for ingestion (up to 5 min) |
