"""Tests for asset generation functionality."""
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.models import CampaignBrief, Product
from src.pipeline.asset_generator import AssetGenerator


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
                name="UltraShield Sunscreen SPF50",
                slug="ultrashield-sunscreen-spf50",
                description="Lightweight sunscreen.",
            ),
            Product(
                name="AquaGlide Beach Towel",
                slug="aquaglide-beach-towel",
                description="Quick-dry towel.",
            ),
        ],
    )


@pytest.fixture
def brief_with_assets(sample_brief, tmp_path):
    """Brief where some products already have assets."""
    asset_path = tmp_path / "existing-asset.png"
    asset_path.write_bytes(b"fake-image")
    sample_brief.products[0].reference_asset = asset_path
    return sample_brief


@pytest.fixture
def mock_imagen_client():
    """Mock ImagenClient for testing."""
    with patch("src.pipeline.asset_generator.ImagenClient") as mock_client:
        mock_instance = Mock()
        mock_instance.generate.return_value = b"fake-generated-image"
        mock_client.return_value = mock_instance
        yield mock_client


@pytest.fixture
def mock_env_vars():
    """Mock environment variables."""
    with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-api-key", "GEMINI_MODEL": "test-model"}):
        yield


class TestAssetGeneratorInit:
    """Test suite for AssetGenerator initialization."""

    def test_init_with_api_key(self, mock_imagen_client):
        """Test initialization with explicit API key."""
        generator = AssetGenerator(api_key="test-key")
        
        mock_imagen_client.assert_called_once()
        assert generator is not None

    def test_init_with_model(self, mock_imagen_client):
        """Test initialization with custom model."""
        generator = AssetGenerator(api_key="test-key", model="custom-model")
        
        mock_imagen_client.assert_called_once_with(api_key="test-key", model="custom-model")

    def test_init_from_env_vars(self, mock_env_vars, mock_imagen_client):
        """Test initialization from environment variables."""
        generator = AssetGenerator()
        
        mock_imagen_client.assert_called_once()

    def test_init_without_api_key_raises_error(self):
        """Test that missing API key raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="GOOGLE_API_KEY not set"):
                AssetGenerator()


class TestGenerateMissingAssets:
    """Test suite for generate_missing_assets method."""

    def test_generate_for_products_without_assets(
        self, mock_env_vars, mock_imagen_client, sample_brief, tmp_path
    ):
        """Test generating assets for products without reference assets."""
        generator = AssetGenerator()
        updated_brief = generator.generate_missing_assets(sample_brief, tmp_path)
        
        # All products should now have reference assets
        assert all(p.reference_asset is not None for p in updated_brief.products)
        
        # Verify generate was called for each product
        assert mock_imagen_client.return_value.generate.call_count == 2

    def test_skip_products_with_existing_assets(
        self, mock_env_vars, mock_imagen_client, brief_with_assets, tmp_path
    ):
        """Test that products with existing assets are skipped."""
        generator = AssetGenerator()
        updated_brief = generator.generate_missing_assets(brief_with_assets, tmp_path)
        
        # Only one product should have been generated (the one without an asset)
        assert mock_imagen_client.return_value.generate.call_count == 1

    def test_creates_timestamped_run_directory(
        self, mock_env_vars, mock_imagen_client, sample_brief, tmp_path
    ):
        """Test that a timestamped run directory is created."""
        generator = AssetGenerator()
        
        with patch("src.pipeline.asset_generator.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 3, 7, 14, 30, 45)
            mock_datetime.strftime = datetime.strftime
            
            generator.generate_missing_assets(sample_brief, tmp_path)
        
        expected_dir = tmp_path / "genoutput" / "runs" / "20260307_143045"
        assert expected_dir.exists()

    def test_saves_images_with_slug_names(
        self, mock_env_vars, mock_imagen_client, sample_brief, tmp_path
    ):
        """Test that images are saved with product slug names."""
        generator = AssetGenerator()
        
        with patch("src.pipeline.asset_generator.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 3, 7, 14, 30, 45)
            mock_datetime.strftime = datetime.strftime
            
            generator.generate_missing_assets(sample_brief, tmp_path)
        
        run_dir = tmp_path / "genoutput" / "runs" / "20260307_143045"
        
        # Check that images were saved with correct names
        assert (run_dir / "ultrashield-sunscreen-spf50.png").exists()
        assert (run_dir / "aquaglide-beach-towel.png").exists()

    def test_saves_brief_copies_in_run_directory(
        self, mock_env_vars, mock_imagen_client, sample_brief, tmp_path
    ):
        """Test that brief is saved in YAML and JSON formats."""
        generator = AssetGenerator()
        
        with patch("src.pipeline.asset_generator.datetime") as mock_datetime:
            mock_datetime.now.return_value = datetime(2026, 3, 7, 14, 30, 45)
            mock_datetime.strftime = datetime.strftime
            
            generator.generate_missing_assets(sample_brief, tmp_path)
        
        run_dir = tmp_path / "genoutput" / "runs" / "20260307_143045"
        
        assert (run_dir / "brief.yaml").exists()
        assert (run_dir / "brief.json").exists()

    def test_uses_first_aspect_ratio_for_reference(
        self, mock_env_vars, mock_imagen_client, sample_brief, tmp_path
    ):
        """Test that the first aspect ratio is used for reference generation."""
        generator = AssetGenerator()
        generator.generate_missing_assets(sample_brief, tmp_path)
        
        # Verify that generate was called with the first ratio
        calls = mock_imagen_client.return_value.generate.call_args_list
        for call in calls:
            assert call[1]["ratio"] == "1:1"  # First ratio in sample_brief

    def test_handles_generation_errors_gracefully(
        self, mock_env_vars, mock_imagen_client, sample_brief, tmp_path
    ):
        """Test that generation errors don't crash the process."""
        # Make the first call fail, second succeed
        mock_imagen_client.return_value.generate.side_effect = [
            Exception("API Error"),
            b"fake-image-data",
        ]
        
        generator = AssetGenerator()
        updated_brief = generator.generate_missing_assets(sample_brief, tmp_path)
        
        # Second product should have an asset, first should not
        assert updated_brief.products[0].reference_asset is None
        assert updated_brief.products[1].reference_asset is not None

    def test_returns_updated_brief(
        self, mock_env_vars, mock_imagen_client, sample_brief, tmp_path
    ):
        """Test that the method returns the updated brief."""
        generator = AssetGenerator()
        updated_brief = generator.generate_missing_assets(sample_brief, tmp_path)
        
        assert isinstance(updated_brief, CampaignBrief)
        assert updated_brief.campaign_name == sample_brief.campaign_name

    def test_no_assets_needed_returns_early(
        self, mock_env_vars, mock_imagen_client, brief_with_assets, tmp_path
    ):
        """Test early return when all products have assets."""
        # Give all products assets
        asset_path = tmp_path / "asset2.png"
        asset_path.write_bytes(b"fake")
        brief_with_assets.products[1].reference_asset = asset_path
        
        generator = AssetGenerator()
        updated_brief = generator.generate_missing_assets(brief_with_assets, tmp_path)
        
        # No generation should have occurred
        mock_imagen_client.return_value.generate.assert_not_called()
        assert updated_brief == brief_with_assets

    def test_uses_build_reference_prompt(
        self, mock_env_vars, mock_imagen_client, sample_brief, tmp_path
    ):
        """Test that build_reference_prompt is used for generation."""
        with patch("src.pipeline.asset_generator.build_reference_prompt") as mock_build:
            mock_build.return_value = "test reference prompt"
            
            generator = AssetGenerator()
            generator.generate_missing_assets(sample_brief, tmp_path)
            
            # Should be called once for each product without assets
            assert mock_build.call_count == 2
            
            # Verify the prompt was used
            calls = mock_imagen_client.return_value.generate.call_args_list
            for call in calls:
                assert call[1]["prompt"] == "test reference prompt"

    def test_default_workspace_root_uses_cwd(
        self, mock_env_vars, mock_imagen_client, sample_brief
    ):
        """Test that workspace_root defaults to current working directory."""
        with patch("src.pipeline.asset_generator.Path.cwd") as mock_cwd:
            mock_cwd.return_value = Path("/fake/workspace")
            
            generator = AssetGenerator()
            
            with patch("src.pipeline.asset_generator.datetime") as mock_datetime:
                mock_datetime.now.return_value = datetime(2026, 3, 7, 14, 30, 45)
                mock_datetime.strftime = datetime.strftime
                
                generator.generate_missing_assets(sample_brief, None)
            
            mock_cwd.assert_called_once()
