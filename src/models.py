"""Pydantic models for the Creative Automation Pipeline."""
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, field_validator, model_validator


class Product(BaseModel):
    """Product model for campaign briefs."""
    name: str
    slug: str | None = None
    description: str
    reference_asset: Path | None = None

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="after")
    def auto_generate_slug(self) -> "Product":
        """Auto-generate slug from name if not provided."""
        if not self.slug:
            # Convert name to lowercase, replace spaces and special chars with hyphens
            slug = re.sub(r'[^\w\s-]', '', self.name.lower())
            slug = re.sub(r'[-\s]+', '-', slug)
            self.slug = slug.strip('-')
        return self


class CampaignBrief(BaseModel):
    """Campaign brief model."""
    campaign_name: str
    products: list[Product]
    region: str
    audience: str
    message: str
    aspect_ratios: list[str] = ["1:1", "9:16", "16:9"]
    language: str | None = None  # Language of the brief text (e.g., "English", "Spanish")

    @field_validator("products")
    @classmethod
    def at_least_two_products(cls, v: list[Product]) -> list[Product]:
        """Validate that the campaign has at least 2 products."""
        if len(v) < 2:
            raise ValueError("A campaign brief must include at least 2 products.")
        return v


class ProgressEvent(BaseModel):
    """Progress event model for tracking pipeline execution."""
    run_id: str
    stage: str  # "localizing" | "localized" | "generating_reference" | "generating" | "generated" | "complete" | "error"
    product: str | None = None
    ratio: str | None = None
    progress: int  # 0–100
    message: str
    url: str | None = None  # populated on "generated" stage with the Dropbox URL
    brief: CampaignBrief | None = None  # populated on "localized" stage with the updated brief


class RunResult(BaseModel):
    """Run result model for pipeline execution."""
    run_id: str
    status: str
    brief: CampaignBrief
    outputs: dict[str, dict[str, str]]          # {product_slug: {ratio: url}}
    reference_outputs: dict[str, str] = {}      # {product_slug: reference_url}
    log: list[str] = []
    localization: dict[str, Any] = {}           # Tracks localization details
