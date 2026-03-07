"""Pydantic models for the Creative Automation Pipeline."""
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


PROHIBITED_LEGAL_SAFETY_PHRASES = [
    "free money",
    "guaranteed",
    "100% safe",
    "risk-free",
    "no risk",
    "zero risk",
    "completely safe",
    "totally safe",
    "absolutely safe",
    "safe for everyone",
    "safe for all",
    "always safe",
    "no side effects",
    "without side effects",
    "side effect free",
    "cure",
    "cures",
    "cured",
    "prevent disease",
    "treat disease",
    "medical miracle",
    "miracle cure",
    "doctor approved",
    "clinically proven",
    "scientifically proven",
    "proven results",
    "instant results",
    "immediate results",
    "results guaranteed",
    "guaranteed results",
    "money-back guaranteed",
    "double your money",
    "earn instantly",
    "get rich quick",
    "fast cash",
    "easy cash",
    "effortless income",
    "passive income guaranteed",
    "no effort required",
    "lose weight fast",
    "burn fat instantly",
    "anti-aging cure",
    "reverses aging",
    "eliminate wrinkles overnight",
    "works for everyone",
    "works every time",
    "never fails",
    "fail-proof",
    "guaranteed approval",
    "pre-approved",
]


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
    aspect_ratios: list[str] = Field(default_factory=lambda: ["1:1", "9:16", "16:9"])
    language: str | None = None  # Language of the brief text (e.g., "English", "Spanish")

    @field_validator("products")
    @classmethod
    def at_least_two_products(cls, v: list[Product]) -> list[Product]:
        """Validate that the campaign has at least 2 products."""
        if len(v) < 2:
            raise ValueError("A campaign brief must include at least 2 products.")
        return v

    @model_validator(mode="after")
    def validate_prohibited_legal_safety_phrases(self) -> "CampaignBrief":
        """Validate that legal/safety prohibited phrases are not present in brief text."""
        violations: list[tuple[str, str]] = []

        message_lower = self.message.lower()
        for phrase in PROHIBITED_LEGAL_SAFETY_PHRASES:
            if phrase in message_lower:
                violations.append(("message", phrase))

        for index, product in enumerate(self.products):
            description_lower = product.description.lower()
            for phrase in PROHIBITED_LEGAL_SAFETY_PHRASES:
                if phrase in description_lower:
                    violations.append((f"products[{index}].description", phrase))

        if violations:
            details = "; ".join(
                f"{field_path}: '{phrase}'" for field_path, phrase in violations
            )
            raise ValueError(
                f"Legal safety validation failed. Prohibited phrase(s) found: {details}"
            )

        return self

