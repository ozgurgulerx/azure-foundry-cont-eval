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
