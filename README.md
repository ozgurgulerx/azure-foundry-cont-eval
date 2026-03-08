# Azure AI Foundry Continuous Evaluation — Test Repository

A reproducible repository for configuring, exercising, and verifying Azure AI Foundry continuous evaluation for Agents (preview).

## Purpose

This project tests **the continuous evaluation feature itself** — not the underlying model's quality. It proves whether continuous evaluation is correctly configured, produces observable results, and is practically useful for monitoring an Azure AI Foundry agent in near real time.

## Repository Structure

```
├── SPEC.md                     # Governing specification
├── README.md                   # This file
├── .env.template               # Environment variable template
├── requirements.txt            # Python dependencies
├── docs/
│   ├── project-charter.md      # Why this project exists
│   ├── architecture.md         # System architecture and data flow
│   ├── observability-setup.md  # Application Insights + tracing setup
│   ├── evaluator-strategy.md   # Evaluator selection and design rationale
│   ├── verification-plan.md    # How we verify evaluation is working
│   └── decision-log.md         # All decisions and assumptions
├── configs/
│   ├── project.yaml            # Project-level settings
│   ├── agent.yaml              # Agent configuration
│   ├── evaluators.yaml         # Evaluator definitions and pass criteria
│   ├── traffic.yaml            # Traffic generation parameters
│   └── azure.yaml              # Azure resource identifiers (no secrets)
├── scripts/
│   ├── setup_agent.py          # Create or retrieve the agent
│   ├── setup_evaluation.py     # Create continuous evaluation schedule
│   ├── generate_traffic.py     # Send controlled prompts to the agent
│   ├── verify_evaluation.py    # Check that evaluation runs exist
│   └── collect_results.py      # Export evaluation results for reporting
├── src/
│   ├── agent_client.py         # Agent interaction utilities
│   ├── evaluators/
│   │   └── deterministic.py    # Custom deterministic evaluators
│   ├── observability.py        # Telemetry helpers
│   └── utils.py                # Shared utilities
├── data/
│   └── knowledge_base.md       # Small knowledge base for the agent
├── runs/                       # Captured run metadata (gitignored)
└── results/                    # Reports and exported metrics (gitignored)
```

## Quickstart

### Prerequisites

- Python >= 3.10
- Azure CLI >= 2.60, logged in (`az login`)
- Azure subscription with Contributor access
- Azure AI Foundry project with GPT-4o deployed
- Application Insights resource connected to the project

### Setup

```bash
# Clone the repository
git clone <repo-url>
cd azure-foundry-cont-eval

# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.template .env
# Edit .env with your Azure resource values
```

### Execution Phases

All scripts default to **dry-run mode**. Add `--execute` to perform real Azure operations.

```bash
# Phase 4: Setup
python scripts/setup_agent.py              # Dry-run: show what would be created
python scripts/setup_agent.py --execute    # Create the agent

python scripts/setup_evaluation.py         # Dry-run: show evaluation schedule
python scripts/setup_evaluation.py --execute  # Create the schedule

# Phase 5: Traffic
python scripts/generate_traffic.py         # Dry-run: show prompts
python scripts/generate_traffic.py --execute  # Send prompts to agent

# Phase 6: Verification (run ~1 hour after traffic)
python scripts/verify_evaluation.py        # Check for evaluation runs
python scripts/collect_results.py          # Export results
```

## Scripts Reference

| Script | Purpose | Dry-run | Execute |
|--------|---------|---------|---------|
| `setup_agent.py` | Create or retrieve the AI Foundry agent | Shows config | Creates agent |
| `setup_evaluation.py` | Create continuous evaluation schedule | Shows schedule definition | Creates schedule |
| `generate_traffic.py` | Send controlled prompts to agent | Prints prompts | Sends to agent |
| `verify_evaluation.py` | Check evaluation runs exist | N/A | Queries runs |
| `collect_results.py` | Export evaluation results | N/A | Exports to results/ |

## Phase Plan

| Phase | Description | Status |
|-------|-------------|--------|
| 0 | Governing spec | Complete |
| 1 | Repository scaffolding | Complete |
| 2 | Agent scenario + observability prerequisites | Complete |
| 3 | Evaluator definitions | Complete |
| 4 | Setup scripts implementation | Complete |
| 5 | Traffic generation implementation | Complete |
| 6 | Verification workflow implementation | Complete |
| 7 | Final report | Complete |

## License

This repository is for testing and evaluation purposes.
