"""Tests for campaign brief loading functionality."""
import json
from pathlib import Path

import pytest
import yaml

from src.models import CampaignBrief, Product
from src.brief_loader import load_brief_from_file
from load_brief import assign_reference_assets


@pytest.fixture
def sample_brief_data():
    """Sample campaign brief data."""
    return {
        "campaign_name": "Summer Essentials",
        "region": "US",
        "audience": "Active outdoor enthusiasts aged 25-45",
        "message": "Gear up for the perfect summer adventure",
        "aspect_ratios": ["1:1", "9:16", "16:9"],
        "products": [
            {
                "name": "UltraShield Sunscreen SPF50",
                "slug": "ultrashield-sunscreen-spf50",
                "description": "Lightweight, water-resistant mineral sunscreen with SPF 50.",
            },
            {
                "name": "AquaGlide Beach Towel",
                "slug": "aquaglide-beach-towel",
                "description": "Ultra-absorbent microfiber beach towel with quick-dry technology.",
            },
        ],
    }


@pytest.fixture
def yaml_brief_file(tmp_path, sample_brief_data):
    """Create a temporary YAML brief file."""
    brief_file = tmp_path / "test_brief.yaml"
    with open(brief_file, "w") as f:
        yaml.dump(sample_brief_data, f)
    return brief_file


@pytest.fixture
def json_brief_file(tmp_path, sample_brief_data):
    """Create a temporary JSON brief file."""
    brief_file = tmp_path / "test_brief.json"
    with open(brief_file, "w") as f:
        json.dump(sample_brief_data, f, indent=2)
    return brief_file


class TestBriefLoader:
    """Test suite for brief loading functionality."""

    def test_load_yaml_brief(self, yaml_brief_file):
        """Test loading a YAML campaign brief."""
        brief = load_brief_from_file(yaml_brief_file)
        
        assert isinstance(brief, CampaignBrief)
        assert brief.campaign_name == "Summer Essentials"
        assert brief.region == "US"
        assert brief.audience == "Active outdoor enthusiasts aged 25-45"
        assert brief.message == "Gear up for the perfect summer adventure"
        assert brief.aspect_ratios == ["1:1", "9:16", "16:9"]
        assert len(brief.products) == 2

    def test_load_json_brief(self, json_brief_file):
        """Test loading a JSON campaign brief."""
        brief = load_brief_from_file(json_brief_file)
        
        assert isinstance(brief, CampaignBrief)
        assert brief.campaign_name == "Summer Essentials"
        assert len(brief.products) == 2

    def test_products_parsed_correctly(self, yaml_brief_file):
        """Test that products are parsed as Product objects."""
        brief = load_brief_from_file(yaml_brief_file)
        
        assert all(isinstance(p, Product) for p in brief.products)
        assert brief.products[0].name == "UltraShield Sunscreen SPF50"
        assert brief.products[0].slug == "ultrashield-sunscreen-spf50"
        assert brief.products[1].name == "AquaGlide Beach Towel"

    def test_auto_generate_slug_when_missing(self, tmp_path):
        """Test that slugs are auto-generated when not provided."""
        brief_data = {
            "campaign_name": "Test Campaign",
            "region": "US",
            "audience": "Everyone",
            "message": "Test message",
            "products": [
                {
                    "name": "Product One",
                    "description": "Description one",
                },
                {
                    "name": "Product Two!",
                    "description": "Description two",
                },
            ],
        }
        
        brief_file = tmp_path / "test.yaml"
        with open(brief_file, "w") as f:
            yaml.dump(brief_data, f)
        
        brief = load_brief_from_file(brief_file)
        
        assert brief.products[0].slug == "product-one"
        assert brief.products[1].slug == "product-two"

    def test_file_not_found_raises_error(self):
        """Test that loading a non-existent file raises an error."""
        with pytest.raises(FileNotFoundError):
            load_brief_from_file(Path("nonexistent.yaml"))

    def test_invalid_extension_raises_error(self, tmp_path):
        """Test that unsupported file extensions raise an error."""
        brief_file = tmp_path / "test.txt"
        brief_file.write_text("some text")
        
        with pytest.raises(ValueError, match="Unsupported file format"):
            load_brief_from_file(brief_file)

    def test_validation_error_less_than_two_products(self, tmp_path):
        """Test that briefs with less than 2 products fail validation."""
        brief_data = {
            "campaign_name": "Test Campaign",
            "region": "US",
            "audience": "Everyone",
            "message": "Test message",
            "products": [
                {
                    "name": "Product One",
                    "slug": "product-one",
                    "description": "Description one",
                }
            ],
        }
        
        brief_file = tmp_path / "test.yaml"
        with open(brief_file, "w") as f:
            yaml.dump(brief_data, f)
        
        with pytest.raises(ValueError, match="at least 2 products"):
            load_brief_from_file(brief_file)

    def test_default_aspect_ratios(self, tmp_path):
        """Test that aspect_ratios defaults to ["1:1", "9:16", "16:9"]."""
        brief_data = {
            "campaign_name": "Test Campaign",
            "region": "US",
            "audience": "Everyone",
            "message": "Test message",
            "products": [
                {
                    "name": "Product One",
                    "slug": "product-one",
                    "description": "Description one",
                },
                {
                    "name": "Product Two",
                    "slug": "product-two",
                    "description": "Description two",
                },
            ],
        }
        
        brief_file = tmp_path / "test.yaml"
        with open(brief_file, "w") as f:
            yaml.dump(brief_data, f)
        
        brief = load_brief_from_file(brief_file)
        
        assert brief.aspect_ratios == ["1:1", "9:16", "16:9"]


class TestReferenceAssets:
    """Test suite for assigning reference assets to products."""

    def test_assign_reference_assets_matches_by_slug(self, yaml_brief_file, tmp_path):
        """Test that assets are assigned when filename matches product slug."""
        brief = load_brief_from_file(yaml_brief_file)
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()

        matching_asset = assets_dir / "ultrashield-sunscreen-spf50.png"
        matching_asset.write_bytes(b"fake-image")

        assign_reference_assets(brief, assets_dir)

        assert brief.products[0].reference_asset == matching_asset
        assert brief.products[1].reference_asset is None

    def test_assign_reference_assets_matches_underscore_filenames(self, yaml_brief_file, tmp_path):
        """Test that underscore filenames also match hyphenated product slugs."""
        brief = load_brief_from_file(yaml_brief_file)
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()

        matching_asset = assets_dir / "aquaglide_beach_towel.jpg"
        matching_asset.write_bytes(b"fake-image")

        assign_reference_assets(brief, assets_dir)

        assert brief.products[1].reference_asset == matching_asset
        assert brief.products[0].reference_asset is None

    def test_assign_reference_assets_ignores_non_image_files(self, yaml_brief_file, tmp_path):
        """Test that non-image files are ignored for asset assignment."""
        brief = load_brief_from_file(yaml_brief_file)
        assets_dir = tmp_path / "assets"
        assets_dir.mkdir()

        non_image = assets_dir / "ultrashield-sunscreen-spf50.txt"
        non_image.write_text("not-an-image", encoding="utf-8")

        assign_reference_assets(brief, assets_dir)

        assert brief.products[0].reference_asset is None
        assert brief.products[1].reference_asset is None
