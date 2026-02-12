"""Schema validation for Argus scenario YAML files."""

import json
import yaml
import jsonschema
from pathlib import Path
from typing import Any


SCHEMA_PATH = Path(__file__).parent.parent / "schemas" / "scenario.schema.json"


def load_schema() -> dict:
    """Load the scenario JSON Schema."""
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def load_scenario(scenario_path: str | Path) -> dict:
    """Load a scenario YAML file."""
    with open(scenario_path) as f:
        return yaml.safe_load(f)


def validate_scenario(scenario: dict, schema: dict | None = None) -> list[str]:
    """
    Validate a scenario dict against the JSON Schema.
    Returns a list of error messages (empty if valid).
    """
    if schema is None:
        schema = load_schema()

    errors = []
    validator = jsonschema.Draft7Validator(schema)

    for error in sorted(validator.iter_errors(scenario), key=lambda e: list(e.path)):
        path = ".".join(str(p) for p in error.absolute_path) or "(root)"
        errors.append(f"[{path}] {error.message}")

    return errors


def validate_scenario_file(scenario_path: str | Path) -> tuple[dict | None, list[str]]:
    """
    Load and validate a scenario file.
    Returns (scenario_dict, errors).
    """
    try:
        scenario = load_scenario(scenario_path)
    except Exception as e:
        return None, [f"Failed to load YAML: {e}"]

    errors = validate_scenario(scenario)
    return scenario, errors
