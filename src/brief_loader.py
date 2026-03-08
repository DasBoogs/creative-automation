"""Brief loader module for loading campaign briefs from files."""
import json
from pathlib import Path

import yaml
from pydantic import ValidationError

from src.models import CampaignBrief


LEGAL_SAFETY_PREFIX = "Legal safety validation failed."


def _format_legal_safety_error(exc: ValidationError) -> str | None:
    """Return a user-friendly legal-safety error message when applicable."""
    matched_messages: list[str] = []

    for error in exc.errors(include_url=False):
        error_message = str(error.get("msg", ""))
        if LEGAL_SAFETY_PREFIX in error_message:
            matched_messages.append(error_message)

    if not matched_messages:
        return None

    details = "\n".join(f"- {message}" for message in matched_messages)
    return (
        "Brief blocked by legal safety validation.\n"
        "Remove prohibited legal/safety claims from the campaign message or product descriptions and try again.\n"
        f"Details:\n{details}"
    )


def load_brief_from_file(file_path: Path | str) -> CampaignBrief:
    """
    Load a campaign brief from a JSON or YAML file.
    
    Args:
        file_path: Path to the brief file (JSON or YAML)
        
    Returns:
        CampaignBrief: Validated campaign brief object
        
    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file format is unsupported or data is invalid
    """
    file_path = Path(file_path)
    
    if not file_path.exists():
        raise FileNotFoundError(f"Brief file not found: {file_path}")
    
    # Determine file format by extension
    extension = file_path.suffix.lower()
    
    if extension in [".yaml", ".yml"]:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    elif extension == ".json":
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        raise ValueError(
            f"Unsupported file format: {extension}. "
            "Supported formats: .yaml, .yml, .json"
        )
    
    # Parse and validate using Pydantic model
    try:
        brief = CampaignBrief(**data)
    except ValidationError as e:
        legal_safety_error = _format_legal_safety_error(e)
        if legal_safety_error:
            raise ValueError(legal_safety_error) from e
        raise ValueError(f"Failed to parse brief: {e}") from e
    except Exception as e:
        raise ValueError(f"Failed to parse brief: {e}") from e
    
    return brief
