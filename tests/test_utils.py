"""Tests for shared utility functions."""
import pytest
from pathlib import Path

from src.models import CampaignBrief, Product
from src.utils import sanitize_campaign_slug, serialize_brief_for_export


class TestSanitizeCampaignSlug:
    """Test suite for campaign name sanitization."""

    def test_basic_sanitization(self):
        """Test basic lowercase and space replacement."""
        assert sanitize_campaign_slug("Summer Campaign") == "summer-campaign"

    def test_special_characters_removed(self):
        """Test that special characters are removed."""
        assert sanitize_campaign_slug("Summer Campaign 2026!") == "summer-campaign-2026"
        assert sanitize_campaign_slug("Campaign: Winter Edition") == "campaign-winter-edition"
        assert sanitize_campaign_slug("Product@#$%Launch") == "productlaunch"

    def test_whitespace_normalization(self):
        """Test that various whitespace types are normalized."""
        assert sanitize_campaign_slug("Summer  Campaign") == "summer-campaign"
        assert sanitize_campaign_slug("Summer\tCampaign") == "summer-campaign"
        assert sanitize_campaign_slug("Summer\nCampaign") == "summer-campaign"

    def test_underscore_to_hyphen(self):
        """Test that underscores are converted to hyphens."""
        assert sanitize_campaign_slug("Summer_Campaign") == "summer-campaign"
        assert sanitize_campaign_slug("Product_Launch___Beta") == "product-launch-beta"

    def test_multiple_hyphens_collapsed(self):
        """Test that multiple consecutive hyphens are collapsed."""
        assert sanitize_campaign_slug("Summer---Campaign") == "summer-campaign"
        assert sanitize_campaign_slug("Product--Launch") == "product-launch"

    def test_leading_trailing_hyphens_stripped(self):
        """Test that leading and trailing hyphens are removed."""
        assert sanitize_campaign_slug("-Summer Campaign-") == "summer-campaign"
        assert sanitize_campaign_slug("---Campaign---") == "campaign"

    def test_only_special_characters(self):
        """Test that a name with only special chars gets default fallback."""
        assert sanitize_campaign_slug("!!!") == "campaign"
        assert sanitize_campaign_slug("@#$%") == "campaign"
        assert sanitize_campaign_slug("   ") == "campaign"

    def test_unicode_characters(self):
        """Test that unicode characters are handled."""
        assert sanitize_campaign_slug("Café Campaign") == "caf-campaign"
        assert sanitize_campaign_slug("日本語 Campaign") == "campaign"

    def test_mixed_case_and_numbers(self):
        """Test mixed case and numbers."""
        assert sanitize_campaign_slug("Q1-2026 Campaign") == "q1-2026-campaign"
        assert sanitize_campaign_slug("Campaign2026Launch") == "campaign2026launch"

    def test_path_separator_safety(self):
        """Test that path separators are removed for filesystem safety."""
        assert sanitize_campaign_slug("Campaign/2026") == "campaign2026"
        assert sanitize_campaign_slug("Campaign\\2026") == "campaign2026"

    def test_dropbox_path_collision_scenario(self):
        """Test scenarios that could cause path collisions."""
        # These should produce different slugs if inputs are inherently different
        slug1 = sanitize_campaign_slug("Summer 2026")
        slug2 = sanitize_campaign_slug("Summer-2026")
        assert slug1 == slug2  # Note: This is expected behavior, documents potential collision

        # These should be clearly different
        slug3 = sanitize_campaign_slug("Summer 2026")
        slug4 = sanitize_campaign_slug("Winter 2026")
        assert slug3 != slug4

    def test_empty_string(self):
        """Test empty string input."""
        assert sanitize_campaign_slug("") == "campaign"

    def test_real_world_examples(self):
        """Test real-world campaign name examples."""
        assert sanitize_campaign_slug("Holiday Sale: 50% Off!") == "holiday-sale-50-off"
        assert sanitize_campaign_slug("Back-to-School 2026") == "back-to-school-2026"
        assert sanitize_campaign_slug("New Product Launch (Beta)") == "new-product-launch-beta"


class TestSerializeBriefForExport:
    """Test suite for brief serialization helper."""

    def test_basic_serialization(self):
        """Test basic brief serialization without paths."""
        brief = CampaignBrief(
            campaign_name="Test Campaign",
            products=[
                Product(name="Product 1", description="Desc 1"),
                Product(name="Product 2", description="Desc 2"),
            ],
            region="US",
            audience="Test audience",
            message="Test message",
        )
        
        result = serialize_brief_for_export(brief)
        
        assert result["campaign_name"] == "Test Campaign"
        assert len(result["products"]) == 2
        assert result["region"] == "US"

    def test_path_to_string_conversion(self):
        """Test that Path objects are converted to strings."""
        brief = CampaignBrief(
            campaign_name="Test Campaign",
            products=[
                Product(
                    name="Product 1",
                    description="Desc 1",
                    reference_asset=Path("/test/path/asset.png"),
                ),
                Product(name="Product 2", description="Desc 2"),
            ],
            region="US",
            audience="Test audience",
            message="Test message",
        )
        
        result = serialize_brief_for_export(brief)
        
        # First product should have string path
        assert isinstance(result["products"][0]["reference_asset"], str)
        assert "asset.png" in result["products"][0]["reference_asset"]
        
        # Second product should have None
        assert result["products"][1]["reference_asset"] is None

    def test_multiple_products_with_paths(self):
        """Test serialization with multiple products having paths."""
        brief = CampaignBrief(
            campaign_name="Test Campaign",
            products=[
                Product(
                    name="Product 1",
                    description="Desc 1",
                    reference_asset=Path("/path/one.png"),
                ),
                Product(
                    name="Product 2",
                    description="Desc 2",
                    reference_asset=Path("/path/two.png"),
                ),
            ],
            region="US",
            audience="Test audience",
            message="Test message",
        )
        
        result = serialize_brief_for_export(brief)
        
        assert all(isinstance(p["reference_asset"], str) for p in result["products"])

    def test_optional_fields_preserved(self):
        """Test that optional fields are preserved."""
        brief = CampaignBrief(
            campaign_name="Test Campaign",
            products=[
                Product(name="Product 1", description="Desc 1"),
                Product(name="Product 2", description="Desc 2"),
            ],
            region="IT",
            audience="Test audience",
            message="Test message",
            language="English",
            aspect_ratios=["1:1", "16:9"],
        )
        
        result = serialize_brief_for_export(brief)
        
        assert result["language"] == "English"
        assert result["aspect_ratios"] == ["1:1", "16:9"]

    def test_slug_auto_generated_preserved(self):
        """Test that auto-generated product slugs are preserved."""
        brief = CampaignBrief(
            campaign_name="Test Campaign",
            products=[
                Product(name="Cool Product Name", description="Desc"),
                Product(name="Another Product", description="Desc 2"),
            ],
            region="US",
            audience="Test audience",
            message="Test message",
        )
        
        result = serialize_brief_for_export(brief)
        
        # Slug should be auto-generated by Product model validator
        assert result["products"][0]["slug"] == "cool-product-name"
        assert result["products"][1]["slug"] == "another-product"
