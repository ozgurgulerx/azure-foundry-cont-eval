"""Shared utilities for the continuous evaluation test project.

Provides:
- Environment loading from .env
- YAML config loading
- Logging setup
- Dry-run argument parsing
- Project root resolution
- JSON output helpers
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv


def get_project_root() -> Path:
    """Return the project root directory (where SPEC.md lives)."""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "SPEC.md").exists():
            return current
        current = current.parent
    # Fallback: assume src/ is one level below root.
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = get_project_root()


def load_env() -> None:
    """Load environment variables from .env file at project root."""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        logging.warning("No .env file found at %s — using environment variables only.", env_path)


def load_config(config_name: str) -> dict:
    """Load a YAML config file from the configs/ directory.

    Args:
        config_name: Filename (e.g., "agent.yaml") or path relative to configs/.

    Returns:
        Parsed YAML as a dict.
    """
    config_path = PROJECT_ROOT / "configs" / config_name
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    with open(config_path) as f:
        return yaml.safe_load(f)


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure logging and return the root logger.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR).

    Returns:
        Configured logger instance.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger("cont-eval")


def create_arg_parser(description: str) -> argparse.ArgumentParser:
    """Create an argument parser with the standard --execute flag.

    All scripts default to dry-run mode. The --execute flag opts in
    to performing real Azure operations.

    Args:
        description: Script description for help text.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Execute real Azure operations (default: dry-run mode).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (default: INFO).",
    )
    return parser


def require_env(name: str) -> str:
    """Get a required environment variable or exit with an error.

    Args:
        name: Environment variable name.

    Returns:
        The environment variable value.
    """
    value = os.environ.get(name, "").strip()
    if not value:
        logging.error("Required environment variable %s is not set.", name)
        sys.exit(1)
    return value


def get_env(name: str, default: str = "") -> str:
    """Get an optional environment variable with a default.

    Args:
        name: Environment variable name.
        default: Default value if not set.

    Returns:
        The environment variable value or default.
    """
    return os.environ.get(name, default).strip()


def save_run_artifact(filename: str, data: dict) -> Path:
    """Save a JSON artifact to the runs/ directory.

    Args:
        filename: Output filename (e.g., "agent-verification.json").
        data: Dictionary to serialize.

    Returns:
        Path to the saved file.
    """
    runs_dir = PROJECT_ROOT / "runs"
    runs_dir.mkdir(exist_ok=True)
    output_path = runs_dir / filename
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    logging.info("Saved run artifact: %s", output_path)
    return output_path


def save_result_artifact(filename: str, data: dict) -> Path:
    """Save a JSON artifact to the results/ directory.

    Args:
        filename: Output filename (e.g., "eval-results.json").
        data: Dictionary to serialize.

    Returns:
        Path to the saved file.
    """
    results_dir = PROJECT_ROOT / "results"
    results_dir.mkdir(exist_ok=True)
    output_path = results_dir / filename
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    logging.info("Saved result artifact: %s", output_path)
    return output_path


def timestamp_iso() -> str:
    """Return the current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


# Phase gate prerequisite artifacts.
# Maps each script to the artifact(s) it requires from prior phases.
PHASE_PREREQUISITES: dict[str, list[tuple[str, str]]] = {
    "setup_agent.py": [],  # Phase 4 — no prior artifacts needed
    "setup_evaluation.py": [
        ("runs/agent-verification.json", "setup_agent.py --execute"),
    ],
    "generate_traffic.py": [
        ("runs/agent-verification.json", "setup_agent.py --execute"),
        ("runs/rule-verification.json", "setup_evaluation.py --execute"),
    ],
    "verify_evaluation.py": [
        ("runs/rule-verification.json", "setup_evaluation.py --execute"),
        ("runs/traffic-log.json", "generate_traffic.py --execute"),
    ],
    "collect_results.py": [
        ("runs/traffic-log.json", "generate_traffic.py --execute"),
    ],
}


def check_phase_gate(script_name: str, *, execute: bool) -> bool:
    """Check that prerequisite artifacts from prior phases exist.

    In dry-run mode, missing prerequisites are logged as warnings.
    In execute mode, missing prerequisites cause the script to exit.

    Args:
        script_name: Name of the current script (e.g., "generate_traffic.py").
        execute: Whether the script is running in execute mode.

    Returns:
        True if all prerequisites are met or in dry-run mode.
    """
    prereqs = PHASE_PREREQUISITES.get(script_name, [])
    if not prereqs:
        return True

    logger = logging.getLogger("cont-eval")
    missing = []

    for artifact_path, remedy in prereqs:
        full_path = PROJECT_ROOT / artifact_path
        if not full_path.exists():
            missing.append((artifact_path, remedy))
        else:
            # Check it's not a dry-run artifact when in execute mode.
            if execute:
                try:
                    with open(full_path) as f:
                        data = json.load(f)
                    if data.get("mode") == "dry-run":
                        missing.append((artifact_path, remedy))
                        logger.warning(
                            "Phase gate: %s exists but is a dry-run artifact. "
                            "Run '%s' first.", artifact_path, remedy,
                        )
                except (json.JSONDecodeError, KeyError):
                    pass  # Non-JSON or missing mode field — treat as valid.

    if not missing:
        logger.info("Phase gate: all prerequisites met for %s.", script_name)
        return True

    for artifact_path, remedy in missing:
        msg = "Phase gate: missing prerequisite '%s'. Run '%s' first."
        if execute:
            logger.error(msg, artifact_path, remedy)
        else:
            logger.warning(msg + " (continuing in dry-run mode)", artifact_path, remedy)

    if execute:
        logger.error("Phase gate check FAILED. Cannot proceed in execute mode.")
        sys.exit(1)

    return False
