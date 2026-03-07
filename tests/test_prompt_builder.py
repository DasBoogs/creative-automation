"""Tests for prompt building functionality."""
import pytest

from src.models import CampaignBrief, Product
from src.pipeline.prompt_builder import build_prompt, build_reference_prompt


@pytest.fixture
def sample_product():
    """Sample product for testing."""
    return Product(
        name="UltraShield Sunscreen SPF50",
        slug="ultrashield-sunscreen-spf50",
        description="Lightweight, water-resistant mineral sunscreen with SPF 50.",
    )


@pytest.fixture
def sample_product_with_asset(tmp_path):
    """Sample product with a reference asset."""
    asset_path = tmp_path / "product.png"
    asset_path.write_bytes(b"fake-image")
    
    return Product(
        name="AquaGlide Beach Towel",
        slug="aquaglide-beach-towel",
        description="Ultra-absorbent microfiber beach towel.",
        reference_asset=asset_path,
    )


@pytest.fixture
def sample_brief():
    """Sample campaign brief for testing."""
    return CampaignBrief(
        campaign_name="Summer Essentials",
        region="US",
        audience="Active outdoor enthusiasts aged 25-45",
        message="Gear up for the perfect summer adventure",
        aspect_ratios=["1:1", "9:16", "16:9"],
        products=[
            Product(
                name="Product One",
                slug="product-one",
                description="First product",
            ),
            Product(
                name="Product Two",
                slug="product-two",
                description="Second product",
            ),
        ],
    )


class TestBuildReferencePrompt:
    """Test suite for build_reference_prompt function."""

    def test_build_reference_prompt_includes_product_name(self, sample_product):
        """Test that reference prompt includes the product name."""
        prompt = build_reference_prompt(sample_product)
        
        assert sample_product.name in prompt
        assert "UltraShield Sunscreen SPF50" in prompt

    def test_build_reference_prompt_includes_description(self, sample_product):
        """Test that reference prompt includes the product description."""
        prompt = build_reference_prompt(sample_product)
        
        assert sample_product.description in prompt
        assert "Lightweight, water-resistant mineral sunscreen" in prompt

    def test_build_reference_prompt_has_studio_requirements(self, sample_product):
        """Test that reference prompt includes studio photography requirements."""
        prompt = build_reference_prompt(sample_product)
        
        assert "Professional product photograph" in prompt
        assert "clean, neutral light-gray background" in prompt
        assert "Studio lighting" in prompt
        assert "centered composition" in prompt
        assert "sharp focus" in prompt

    def test_build_reference_prompt_excludes_text_and_overlays(self, sample_product):
        """Test that reference prompt explicitly excludes text and overlays."""
        prompt = build_reference_prompt(sample_product)
        
        assert "No text" in prompt
        assert "no overlays" in prompt
        assert "no people" in prompt
        assert "no brand marks" in prompt

    def test_build_reference_prompt_is_high_quality(self, sample_product):
        """Test that reference prompt requests high-quality output."""
        prompt = build_reference_prompt(sample_product)
        
        assert "High-quality" in prompt or "product photography reference" in prompt


class TestBuildPrompt:
    """Test suite for build_prompt function."""

    def test_build_prompt_without_reference_asset(self, sample_product, sample_brief):
        """Test building a prompt for a product without a reference asset."""
        prompt = build_prompt(sample_product, sample_brief, "1:1")
        
        assert sample_product.name in prompt
        assert sample_product.description in prompt
        assert sample_brief.message in prompt
        assert sample_brief.audience in prompt
        assert sample_brief.region in prompt

    def test_build_prompt_with_reference_asset(self, sample_product_with_asset, sample_brief):
        """Test building an img2img prompt for a product with a reference asset."""
        prompt = build_prompt(sample_product_with_asset, sample_brief, "1:1")
        
        assert "Reimagine this product image" in prompt
        assert sample_product_with_asset.name in prompt
        assert sample_brief.message in prompt
        assert sample_brief.audience in prompt
        assert sample_brief.region in prompt

    def test_build_prompt_includes_ratio_1x1(self, sample_product, sample_brief):
        """Test that 1:1 ratio includes appropriate guidance."""
        prompt = build_prompt(sample_product, sample_brief, "1:1")
        
        assert "square format" in prompt or "centered composition" in prompt

    def test_build_prompt_includes_ratio_9x16(self, sample_product, sample_brief):
        """Test that 9:16 ratio includes appropriate guidance."""
        prompt = build_prompt(sample_product, sample_brief, "9:16")
        
        assert "vertical" in prompt or "portrait" in prompt or "Stories" in prompt or "Reels" in prompt

    def test_build_prompt_includes_ratio_16x9(self, sample_product, sample_brief):
        """Test that 16:9 ratio includes appropriate guidance."""
        prompt = build_prompt(sample_product, sample_brief, "16:9")
        
        assert "horizontal" in prompt or "landscape" in prompt or "banner" in prompt

    def test_build_prompt_handles_unknown_ratio(self, sample_product, sample_brief):
        """Test that unknown ratios still generate valid prompts."""
        prompt = build_prompt(sample_product, sample_brief, "4:3")
        
        assert sample_product.name in prompt
        assert sample_brief.message in prompt
        # Should fall back to default guidance
        assert len(prompt) > 0

    def test_build_prompt_message_is_prominent(self, sample_product, sample_brief):
        """Test that the campaign message is marked as prominent."""
        prompt = build_prompt(sample_product, sample_brief, "1:1")
        
        assert "prominently display" in prompt.lower() or "prominently" in prompt.lower()
        assert f'"{sample_brief.message}"' in prompt

    def test_build_prompt_specifies_font_style(self, sample_product, sample_brief):
        """Test that font style is specified in the prompt."""
        prompt = build_prompt(sample_product, sample_brief, "1:1")
        
        assert "bold" in prompt.lower() and "legible" in prompt.lower()

    def test_build_prompt_professional_style(self, sample_product, sample_brief):
        """Test that prompts request professional style."""
        prompt = build_prompt(sample_product, sample_brief, "1:1")
        
        assert "professional" in prompt.lower()
        assert "clean composition" in prompt.lower() or "product photography" in prompt.lower()
