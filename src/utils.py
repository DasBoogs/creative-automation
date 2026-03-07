"""Shared utility functions for the Creative Automation Pipeline."""
import re
from pathlib import Path
from typing import Any

from src.models import CampaignBrief


def sanitize_campaign_slug(campaign_name: str) -> str:
    """Sanitize a campaign name into a strict filesystem-safe slug.
    
    Applies strict normalization to ensure Dropbox/filesystem compatibility:
    - Converts to lowercase
    - Replaces whitespace with hyphens
    - Keeps only alphanumeric chars and hyphens
    - Collapses multiple hyphens into one
    - Strips leading/trailing hyphens
    
    Args:
        campaign_name: Raw campaign name string
        
    Returns:
        Strict slug containing only [a-z0-9-]
        
    Examples:
        >>> sanitize_campaign_slug("Summer Campaign 2026!")
        'summer-campaign-2026'
        >>> sanitize_campaign_slug("Holiday: Winter Edition")
        'holiday-winter-edition'
        >>> sanitize_campaign_slug("Product_Launch___Beta")
        'product-launch-beta'
    """
    # Convert to lowercase
    slug = campaign_name.lower()
    
    # Replace whitespace and underscores with hyphens
    slug = re.sub(r'[\s_]+', '-', slug)
    
    # Keep only alphanumeric and hyphens
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    
    # Collapse multiple hyphens
    slug = re.sub(r'-+', '-', slug)
    
    # Strip leading/trailing hyphens
    slug = slug.strip('-')
    
    # Ensure non-empty result
    if not slug:
        slug = 'campaign'
    
    return slug


def serialize_brief_for_export(brief: CampaignBrief) -> dict[str, Any]:
    """Serialize a CampaignBrief for YAML/JSON export.
    
    Converts the brief to a dictionary and normalizes Path objects to strings
    for compatibility with YAML and JSON serializers.
    
    Args:
        brief: Campaign brief to serialize
        
    Returns:
        Dictionary with Path objects converted to strings
    """
    brief_dict = brief.model_dump(mode="python")
    
    # Convert Path objects to strings for serialization
    for product in brief_dict.get("products", []):
        if "reference_asset" in product and product["reference_asset"]:
            product["reference_asset"] = str(product["reference_asset"])
    
    return brief_dict
