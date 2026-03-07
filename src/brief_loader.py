"""Brief loader module for loading campaign briefs from files."""
import json
from pathlib import Path

import yaml

from src.models import CampaignBrief


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
    except Exception as e:
        raise ValueError(f"Failed to parse brief: {e}") from e
    
    return brief
