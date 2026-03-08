"""Tests for campaign asset generation functionality."""
import json
import os
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from src.models import CampaignBrief, Product
from src.pipeline.campaign_generator import (
    CampaignGenerator,
    _campaign_folder,
    _upload_image,
    _write_report,
)


@pytest.fixture
def sample_brief():
    """Sample campaign brief for testing."""
    return CampaignBrief(
        campaign_name="Summer Essentials",
        region="US",
        audience="Active outdoor enthusiasts aged 25-45",
        message="Gear up for the perfect summer adventure",
        aspect_ratios=["1:1", "9:16"],
        products=[
            Product(
                name="UltraShield Sunscreen SPF50",
                slug="ultrashield-sunscreen-spf50",
                description="Lightweight, water-resistant mineral sunscreen with SPF 50.",
            ),
            Product(
                name="AquaGlide Beach Towel",
                slug="aquaglide-beach-towel",
                description="Ultra-absorbent microfiber beach towel.",
            ),
        ],
    )


@pytest.fixture
def brief_with_assets(sample_brief, tmp_path):
    """Brief where products have reference assets."""
    asset1 = tmp_path / "asset1.png"
    asset1.write_bytes(b"fake-image-data-1")
    sample_brief.products[0].reference_asset = asset1

    asset2 = tmp_path / "asset2.png"
    asset2.write_bytes(b"fake-image-data-2")
    sample_brief.products[1].reference_asset = asset2

    return sample_brief


@pytest.fixture
def mock_imagen_client():
    """Mock ImagenClient for testing."""
    with patch("src.pipeline.campaign_generator.ImagenClient") as mock_client:
        mock_instance = Mock()
        mock_instance.generate.return_value = b"generated-image-data"
        mock_client.return_value = mock_instance
        yield mock_client


@pytest.fixture
def mock_dropbox_client():
    """Mock DropboxClient for testing."""
    with patch("src.pipeline.campaign_generator.DropboxClient") as mock_client:
        mock_instance = Mock()
        mock_instance.upload.return_value = "/adobe-poc/outputs/cli/campaign/run/product/ratio.png"
        mock_instance.get_temporary_link.return_value = "https://dl.dropboxusercontent.com/temp-link"
        mock_client.return_value = mock_instance
        yield mock_client


@pytest.fixture
def mock_env_vars():
    """Mock environment variables."""
    with patch.dict(
        os.environ,
        {
            "GOOGLE_API_KEY": "test-google-key",
            "DROPBOX_ACCESS_TOKEN": "test-dropbox-token",
            "DROPBOX_APP_NAME": "adobe-poc",
        },
    ):
        yield


class TestCampaignFolderHelper:
    """Test suite for _campaign_folder helper function."""

    def test_campaign_folder_with_simple_name(self, sample_brief):
        """Test folder path generation with simple campaign name."""
        folder = _campaign_folder(sample_brief)

        assert folder == "/adobe-poc/outputs/cli/summer-essentials"

    def test_campaign_folder_with_spaces(self):
        """Test folder path generation converts spaces to hyphens."""
        brief = CampaignBrief(
            campaign_name="Summer Essentials Pro",
            region="US",
            audience="test",
            message="test",
            products=[
                Product(name="Product 1", description="test"),
                Product(name="Product 2", description="test"),
            ],
        )
        folder = _campaign_folder(brief)

        assert folder == "/adobe-poc/outputs/cli/summer-essentials-pro"

    def test_campaign_folder_with_special_chars(self):
        """Test folder path generation handles special characters."""
        brief = CampaignBrief(
            campaign_name="Summer: Essentials & Gear",
            region="US",
            audience="test",
            message="test",
            products=[
                Product(name="Product 1", description="test"),
                Product(name="Product 2", description="test"),
            ],
        )
        folder = _campaign_folder(brief)

        # Colons are replaced with 'x', spaces with hyphens, special chars like & preserved
        assert folder == "/adobe-poc/outputs/cli/summer-essentials-gear"

    def test_campaign_folder_uses_configured_dropbox_app_name(self, sample_brief):
        """Test folder path generation uses DROPBOX_APP_NAME when configured."""
        with patch.dict(os.environ, {"DROPBOX_APP_NAME": "custom-root"}):
            folder = _campaign_folder(sample_brief)

        assert folder == "/custom-root/outputs/cli/summer-essentials"


class TestUploadImageHelper:
    """Test suite for _upload_image helper function."""

    def test_upload_image_creates_correct_path(self, sample_brief, mock_dropbox_client):
        """Test that upload creates the correct Dropbox path."""
        mock_dbx = Mock()
        mock_dbx.upload.return_value = "/uploaded/path"
        mock_dbx.get_temporary_link.return_value = "https://temp-link"

        url = _upload_image(
            dbx=mock_dbx,
            image_bytes=b"image-data",
            run_id="20260307_120000",
            brief=sample_brief,
            product_slug="ultrashield-sunscreen-spf50",
            ratio="1:1",
        )

        # Verify upload was called
        mock_dbx.upload.assert_called_once()
        call_args = mock_dbx.upload.call_args

        # Path should include campaign slug, run_id, product slug, and ratio
        path = call_args[0][1]
        assert "/adobe-poc/outputs/cli/summer-essentials/" in path
        assert "20260307_120000" in path
        assert "ultrashield-sunscreen-spf50" in path
        assert "1:1_" in path
        assert url == "https://temp-link"

    def test_upload_image_returns_temporary_link(self, sample_brief):
        """Test that upload returns a temporary URL."""
        mock_dbx = Mock()
        mock_dbx.upload.return_value = "/uploaded/path"
        mock_dbx.get_temporary_link.return_value = "https://temp-link-url"

        url = _upload_image(
            dbx=mock_dbx,
            image_bytes=b"image-data",
            run_id="test-run",
            brief=sample_brief,
            product_slug="product-slug",
            ratio="1:1",
        )

        assert url == "https://temp-link-url"
        mock_dbx.get_temporary_link.assert_called_once()

    def test_upload_image_handles_upload_error(self, sample_brief):
        """Test that upload errors are propagated."""
        mock_dbx = Mock()
        mock_dbx.upload.side_effect = Exception("Upload failed")

        with pytest.raises(Exception, match="Upload failed"):
            _upload_image(
                dbx=mock_dbx,
                image_bytes=b"image-data",
                run_id="test-run",
                brief=sample_brief,
                product_slug="product-slug",
                ratio="1:1",
            )


class TestWriteReportHelper:
    """Test suite for _write_report helper function."""

    def test_write_report_creates_correct_path(self, sample_brief):
        """Test that report is written to correct Dropbox path."""
        mock_dbx = Mock()

        report = {"run_id": "test-run", "campaign": "Summer Essentials"}

        _write_report(
            dbx=mock_dbx,
            run_id="test-run",
            brief=sample_brief,
            report=report,
        )

        mock_dbx.upload.assert_called_once()
        call_args = mock_dbx.upload.call_args

        # Check path contains correct structure
        path = call_args[0][1]
        assert "/adobe-poc/outputs/cli/summer-essentials/" in path
        assert "test-run" in path
        assert "report.json" in path

    def test_write_report_contains_report_data(self, sample_brief):
        """Test that report JSON contains the provided data."""
        mock_dbx = Mock()

        report = {
            "run_id": "test-run",
            "campaign": "Summer Essentials",
            "outputs": {"product1": {"1:1": "url1"}},
        }

        _write_report(
            dbx=mock_dbx,
            run_id="test-run",
            brief=sample_brief,
            report=report,
        )

        call_args = mock_dbx.upload.call_args
        report_bytes = call_args[0][0]
        report_json = json.loads(report_bytes.decode("utf-8"))

        assert report_json["run_id"] == "test-run"
        assert report_json["campaign"] == "Summer Essentials"
        assert report_json["outputs"]["product1"]["1:1"] == "url1"

    def test_write_report_handles_write_error(self, sample_brief):
        """Test that write errors are propagated."""
        mock_dbx = Mock()
        mock_dbx.upload.side_effect = Exception("Write failed")

        report = {"run_id": "test-run"}

        with pytest.raises(Exception, match="Write failed"):
            _write_report(
                dbx=mock_dbx,
                run_id="test-run",
                brief=sample_brief,
                report=report,
            )


class TestCampaignGeneratorInit:
    """Test suite for CampaignGenerator initialization."""

    def test_init_with_explicit_credentials(self, mock_imagen_client, mock_dropbox_client):
        """Test initialization with explicit credentials."""
        generator = CampaignGenerator(
            google_api_key="test-api-key",
            dropbox_token="test-dropbox-token",
        )

        assert generator.google_api_key == "test-api-key"
        assert generator.dropbox_token == "test-dropbox-token"

    def test_init_from_env_vars(self, mock_env_vars, mock_imagen_client, mock_dropbox_client):
        """Test initialization from environment variables."""
        generator = CampaignGenerator()

        assert generator.google_api_key == "test-google-key"
        assert generator.dropbox_token == "test-dropbox-token"

    def test_init_missing_google_api_key(self, mock_dropbox_client):
        """Test that missing Google API key raises ValueError."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": ""}):
            with pytest.raises(ValueError, match="GOOGLE_API_KEY"):
                CampaignGenerator(dropbox_token="test-token")

    def test_init_missing_dropbox_token(self, mock_imagen_client):
        """Test that missing Dropbox credentials raise ValueError."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}, clear=True):
            with pytest.raises(ValueError, match="Dropbox credentials"):
                CampaignGenerator(google_api_key="test-key")

    def test_init_with_refresh_credentials_only(self, mock_imagen_client, mock_dropbox_client):
        """Test initialization when only refresh-token credentials are provided."""
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-api-key"}, clear=True):
            generator = CampaignGenerator(
                google_api_key="test-api-key",
                dropbox_refresh_token="test-refresh-token",
                dropbox_app_key="test-app-key",
            )

        assert generator.google_api_key == "test-api-key"
        assert generator.dropbox_refresh_token == "test-refresh-token"
        assert generator.dropbox_app_key == "test-app-key"
        mock_dropbox_client.assert_called_once_with(
            access_token="",
            refresh_token="test-refresh-token",
            app_key="test-app-key",
            app_secret=None,
        )

    def test_init_creates_clients(self, mock_imagen_client, mock_dropbox_client, mock_env_vars):
        """Test that initialization creates Imagen and Dropbox clients."""
        generator = CampaignGenerator()

        mock_imagen_client.assert_called_once()
        mock_dropbox_client.assert_called_once()


class TestCampaignGeneratorAssetGeneration:
    """Test suite for campaign asset generation."""

    def test_generate_campaign_assets_success(
        self, brief_with_assets, mock_imagen_client, mock_dropbox_client, mock_env_vars
    ):
        """Test successful campaign asset generation."""
        generator = CampaignGenerator()

        result = generator.generate_campaign_assets(
            run_id="20260307_120000",
            brief=brief_with_assets,
        )

        assert result["status"] == "complete"
        assert result["run_id"] == "20260307_120000"
        assert "outputs" in result
        assert "timings" in result
        assert "log" in result

    def test_generate_creates_outputs_for_all_products_and_ratios(
        self, brief_with_assets, mock_imagen_client, mock_dropbox_client, mock_env_vars
    ):
        """Test that outputs are created for all product x ratio combinations."""
        generator = CampaignGenerator()

        result = generator.generate_campaign_assets(
            run_id="test-run",
            brief=brief_with_assets,
        )

        # Should have 2 products × 2 ratios = 4 images
        assert len(result["outputs"]) == 2  # 2 products
        assert len(result["outputs"]["ultrashield-sunscreen-spf50"]) == 2  # 2 ratios
        assert len(result["outputs"]["aquaglide-beach-towel"]) == 2

    def test_generate_tracks_timings(
        self, brief_with_assets, mock_imagen_client, mock_dropbox_client, mock_env_vars
    ):
        """Test that generation timings are tracked."""
        generator = CampaignGenerator()

        result = generator.generate_campaign_assets(
            run_id="test-run",
            brief=brief_with_assets,
        )

        # Verify timings structure
        assert "timings" in result
        assert "ultrashield-sunscreen-spf50" in result["timings"]
        assert "1:1" in result["timings"]["ultrashield-sunscreen-spf50"]
        assert isinstance(result["timings"]["ultrashield-sunscreen-spf50"]["1:1"], float)

    def test_generate_logs_progress(
        self, brief_with_assets, mock_imagen_client, mock_dropbox_client, mock_env_vars
    ):
        """Test that progress is logged."""
        generator = CampaignGenerator()

        result = generator.generate_campaign_assets(
            run_id="test-run",
            brief=brief_with_assets,
        )

        assert len(result["log"]) > 0
        log_text = "\n".join(result["log"])
        assert "Generated" in log_text or "uploaded" in log_text or "Uploaded" in log_text

    def test_generate_calls_imagen_for_each_ratio(
        self, brief_with_assets, mock_imagen_client, mock_dropbox_client, mock_env_vars
    ):
        """Test that Imagen is called for each product x ratio combination."""
        mock_imagen = mock_imagen_client.return_value

        generator = CampaignGenerator()
        generator.generate_campaign_assets(
            run_id="test-run",
            brief=brief_with_assets,
        )

        # Should be called for each product × ratio combination
        assert mock_imagen.generate.call_count == 4  # 2 products × 2 ratios

    def test_generate_uploads_each_image(
        self, brief_with_assets, mock_imagen_client, mock_dropbox_client, mock_env_vars
    ):
        """Test that each generated image is uploaded."""
        mock_dbx = mock_dropbox_client.return_value

        generator = CampaignGenerator()
        generator.generate_campaign_assets(
            run_id="test-run",
            brief=brief_with_assets,
        )

        # Upload should be called for each generated image + report
        assert mock_dbx.upload.call_count >= 4  # At least 4 images

    def test_generate_writes_report(
        self, brief_with_assets, mock_imagen_client, mock_dropbox_client, mock_env_vars
    ):
        """Test that a run report is written."""
        mock_dbx = mock_dropbox_client.return_value

        generator = CampaignGenerator()
        generator.generate_campaign_assets(
            run_id="test-run",
            brief=brief_with_assets,
        )

        # Verify that a report was written (contains "report.json")
        calls = mock_dbx.upload.call_args_list
        report_uploaded = any("report.json" in str(call) for call in calls)
        assert report_uploaded

    def test_generate_skips_products_without_assets(
        self, sample_brief, mock_imagen_client, mock_dropbox_client, mock_env_vars
    ):
        """Test that products without reference assets are skipped with warning."""
        # sample_brief has no reference assets
        generator = CampaignGenerator()

        result = generator.generate_campaign_assets(
            run_id="test-run",
            brief=sample_brief,
        )

        # Should complete but with a warning logged about missing assets
        assert result["status"] == "complete"
        log_text = "\n".join(result["log"])
        # Verify that missing assets are mentioned in the log
        assert "missing" in log_text.lower() or "without" in log_text.lower()

    def test_generate_handles_missing_reference_asset_file(
        self, sample_brief, mock_imagen_client, mock_dropbox_client, mock_env_vars, tmp_path
    ):
        """Test that missing reference asset files are handled gracefully."""
        # Create a product with a non-existent asset path
        asset_path = tmp_path / "nonexistent.png"
        sample_brief.products[0].reference_asset = asset_path

        generator = CampaignGenerator()

        result = generator.generate_campaign_assets(
            run_id="test-run",
            brief=sample_brief,
        )

        # Should handle the error
        assert "status" in result
        assert "log" in result

    def test_generate_uses_correct_prompt_format(
        self, brief_with_assets, mock_imagen_client, mock_dropbox_client, mock_env_vars
    ):
        """Test that prompts are built correctly for each generation."""
        mock_imagen = mock_imagen_client.return_value

        generator = CampaignGenerator()
        generator.generate_campaign_assets(
            run_id="test-run",
            brief=brief_with_assets,
        )

        # Check that generate was called with correct arguments
        calls = mock_imagen.generate.call_args_list
        for call in calls:
            kwargs = call[1]
            assert "prompt" in kwargs
            assert "ratio" in kwargs
            assert "reference_image_bytes" in kwargs
            # Verify reference bytes are provided (img2img mode)
            assert kwargs["reference_image_bytes"] is not None

    def test_generate_returns_urls_in_outputs(
        self, brief_with_assets, mock_imagen_client, mock_dropbox_client, mock_env_vars
    ):
        """Test that generated output contains URLs."""
        generator = CampaignGenerator()

        result = generator.generate_campaign_assets(
            run_id="test-run",
            brief=brief_with_assets,
        )

        # Check that all outputs have URLs
        for product_slug, ratios in result["outputs"].items():
            for ratio, url in ratios.items():
                assert isinstance(url, str)
                assert "http" in url or "/" in url  # URL format


class TestCampaignGeneratorErrorHandling:
    """Test suite for error handling in campaign generation."""

    def test_generate_error_when_imagen_fails(
        self, brief_with_assets, mock_imagen_client, mock_dropbox_client, mock_env_vars
    ):
        """Test handling when image generation fails."""
        mock_imagen = mock_imagen_client.return_value
        mock_imagen.generate.side_effect = RuntimeError("API error")

        generator = CampaignGenerator()

        result = generator.generate_campaign_assets(
            run_id="test-run",
            brief=brief_with_assets,
        )

        # Result should indicate error or have failed generations
        assert "log" in result

    def test_generate_error_when_upload_fails(
        self, brief_with_assets, mock_imagen_client, mock_dropbox_client, mock_env_vars
    ):
        """Test handling when upload fails."""
        mock_dbx = mock_dropbox_client.return_value
        mock_dbx.upload.side_effect = Exception("Upload failed")

        generator = CampaignGenerator()

        result = generator.generate_campaign_assets(
            run_id="test-run",
            brief=brief_with_assets,
        )

        # Should handle error
        assert "log" in result or "status" in result

    def test_generate_error_when_report_write_fails(
        self, brief_with_assets, mock_imagen_client, mock_dropbox_client, mock_env_vars
    ):
        """Test handling when report write fails."""
        mock_dbx = mock_dropbox_client.return_value

        def upload_side_effect(data, path):
            if "report.json" in path:
                raise Exception("Report write failed")
            return "/uploaded/path"

        mock_dbx.upload.side_effect = upload_side_effect

        generator = CampaignGenerator()

        result = generator.generate_campaign_assets(
            run_id="test-run",
            brief=brief_with_assets,
        )

        # Should warn but still complete
        assert "log" in result


class TestCampaignGeneratorIntegration:
    """Integration tests for campaign generation."""

    def test_full_campaign_generation_workflow(
        self, brief_with_assets, mock_imagen_client, mock_dropbox_client, mock_env_vars
    ):
        """Test complete campaign generation workflow."""
        generator = CampaignGenerator()

        result = generator.generate_campaign_assets(
            run_id="20260307_120000",
            brief=brief_with_assets,
        )

        # Verify complete workflow
        assert result["status"] == "complete"
        assert result["run_id"] == "20260307_120000"
        assert len(result["outputs"]) == 2
        assert len(result["log"]) > 0

    def test_multiple_campaign_runs(
        self, brief_with_assets, mock_imagen_client, mock_dropbox_client, mock_env_vars
    ):
        """Test that multiple campaigns can be generated sequentially."""
        generator = CampaignGenerator()

        # Generate first campaign
        result1 = generator.generate_campaign_assets(
            run_id="run-1",
            brief=brief_with_assets,
        )
        assert result1["status"] == "complete"

        # Generate second campaign
        result2 = generator.generate_campaign_assets(
            run_id="run-2",
            brief=brief_with_assets,
        )
        assert result2["status"] == "complete"

        # Verify they have different run IDs
        assert result1["run_id"] != result2["run_id"]
