"""Tests for summary_logger module."""
import pytest
from datetime import datetime
from pathlib import Path

from src.models import CampaignBrief, Product
from src.pipeline.summary_logger import write_summary_log


@pytest.fixture
def sample_brief():
    """Create a sample campaign brief for testing."""
    return CampaignBrief(
        campaign_name="Test Campaign",
        region="US",
        language="English",
        audience="Test audience",
        message="Test message",
        aspect_ratios=["1:1", "9:16"],
        products=[
            Product(
                name="Test Product 1",
                slug="test-product-1",
                description="A test product description",
                reference_asset=Path("test-asset-1.png"),
            ),
            Product(
                name="Test Product 2",
                slug="test-product-2",
                description="Another test product",
                reference_asset=None,
            ),
        ],
    )


@pytest.fixture
def sample_campaign_result():
    """Create a sample campaign generation result."""
    return {
        "status": "complete",
        "run_id": "20260307_120000",
        "outputs": {
            "test-product-1": {
                "1:1": "https://dropbox.com/test1-1x1",
                "9:16": "https://dropbox.com/test1-9x16",
            },
            "test-product-2": {
                "1:1": "https://dropbox.com/test2-1x1",
            },
        },
        "timings": {
            "test-product-1": {
                "1:1": 2.5,
                "9:16": 3.1,
            },
            "test-product-2": {
                "1:1": 2.8,
            },
        },
        "localization": {
            "target_language": "Spanish",
            "message_translated": True,
            "original_message": "Test message",
            "localized_message": "Mensaje de prueba",
            "products": {
                "test-product-1": {
                    "translated": True,
                    "original": "A test product description",
                    "localized": "Una descripción de producto de prueba",
                    "language": "Spanish",
                },
                "test-product-2": {
                    "translated": False,
                },
            },
        },
        "log": [
            "Localization completed (target_language=Spanish)",
            "Generated Test Product 1 1:1 in 2.5s",
            "Generated Test Product 1 9:16 in 3.1s",
        ],
    }


def test_write_summary_log_asset_generation(tmp_path, sample_brief):
    """Test writing a summary log for asset generation."""
    run_id = "20260307_120000"
    generated_assets = ["test-product-2.png"]
    
    summary_path = write_summary_log(
        run_dir=tmp_path,
        run_id=run_id,
        brief=sample_brief,
        log_type="asset_generation",
        generated_assets=generated_assets,
    )
    
    assert summary_path.exists()
    assert summary_path.name == "SUMMARY.md"
    
    content = summary_path.read_text(encoding="utf-8")
    
    # Check header content
    assert "# Pipeline Run Summary" in content
    assert f"**Run ID:** `{run_id}`" in content
    assert "**Run Type:** Asset Generation" in content
    
    # Check campaign info
    assert "## Campaign Information" in content
    assert "**Campaign Name:** Test Campaign" in content
    assert "**Region:** US" in content
    assert "**Language:** English" in content
    assert "**Audience:** Test audience" in content
    assert "**Message:** Test message" in content
    assert "**Aspect Ratios:** 1:1, 9:16" in content
    
    # Check products
    assert "## Products (2)" in content
    assert "### 1. Test Product 1" in content
    assert "**Slug:** `test-product-1`" in content
    assert "**Description:** A test product description" in content
    assert "**Reference Asset:** `test-asset-1.png`" in content
    assert "### 2. Test Product 2" in content
    
    # Check asset generation results
    assert "## Asset Generation Results" in content
    assert "**Status:** ✅ Success" in content
    assert "**Generated Assets:** 1" in content
    assert "### Generated Files" in content
    assert "- `test-product-2.png`" in content
    assert "💡 **Tip:**" in content


def test_write_summary_log_asset_generation_no_assets(tmp_path, sample_brief):
    """Test summary log when no assets were generated."""
    run_id = "20260307_120000"
    
    summary_path = write_summary_log(
        run_dir=tmp_path,
        run_id=run_id,
        brief=sample_brief,
        log_type="asset_generation",
        generated_assets=[],
    )
    
    content = summary_path.read_text(encoding="utf-8")
    
    assert "## Asset Generation Results" in content
    assert "ℹ️ No assets generated" in content


def test_write_summary_log_campaign_generation(tmp_path, sample_brief, sample_campaign_result):
    """Test writing a summary log for campaign generation."""
    run_id = "20260307_120000"
    
    summary_path = write_summary_log(
        run_dir=tmp_path,
        run_id=run_id,
        brief=sample_brief,
        log_type="campaign_generation",
        result=sample_campaign_result,
    )
    
    assert summary_path.exists()
    content = summary_path.read_text(encoding="utf-8")
    
    # Check header
    assert "# Pipeline Run Summary" in content
    assert f"**Run ID:** `{run_id}`" in content
    assert "**Run Type:** Campaign Generation" in content
    
    # Check campaign generation results
    assert "## Campaign Generation Results" in content
    assert "**Status:** ✅ Complete" in content
    
    # Check localization section
    assert "### Localization" in content
    assert "**Target Language:** Spanish" in content
    assert "**Campaign Message:**" in content
    assert "- Original: _Test message_" in content
    assert "- Localized: _Mensaje de prueba_" in content
    assert "**Translated Product Descriptions:** 1" in content
    assert "#### test-product-1" in content
    
    # Check generated creatives
    assert "### Generated Creatives" in content
    assert "**Total Creatives Generated:** 3" in content
    assert "#### test-product-1" in content
    assert "| Aspect Ratio | Generation Time | Dropbox URL |" in content
    assert "| 1:1 | 2.5s | [View](https://dropbox.com/test1-1x1) |" in content
    assert "| 9:16 | 3.1s | [View](https://dropbox.com/test1-9x16) |" in content
    
    # Check pipeline log
    assert "### Pipeline Log" in content
    assert "Localization completed (target_language=Spanish)" in content
    assert "Generated Test Product 1 1:1 in 2.5s" in content


def test_write_summary_log_campaign_generation_no_localization(tmp_path, sample_brief):
    """Test summary log when no localization was needed."""
    run_id = "20260307_120000"
    result = {
        "status": "complete",
        "run_id": run_id,
        "outputs": {},
        "timings": {},
        "localization": {},
        "log": [],
    }
    
    summary_path = write_summary_log(
        run_dir=tmp_path,
        run_id=run_id,
        brief=sample_brief,
        log_type="campaign_generation",
        result=result,
    )
    
    content = summary_path.read_text(encoding="utf-8")
    
    assert "### Localization" in content
    assert "ℹ️ No localization required" in content


def test_write_summary_log_campaign_generation_failed(tmp_path, sample_brief):
    """Test summary log for failed campaign generation."""
    run_id = "20260307_120000"
    result = {
        "status": "error",
        "run_id": run_id,
        "error": "Test error message",
        "localization": {},
        "log": ["Pipeline started", "Error occurred"],
    }
    
    summary_path = write_summary_log(
        run_dir=tmp_path,
        run_id=run_id,
        brief=sample_brief,
        log_type="campaign_generation",
        result=result,
    )
    
    content = summary_path.read_text(encoding="utf-8")
    
    assert "**Status:** ❌ Failed" in content
    assert "**Error:** Test error message" in content
    assert "### Pipeline Log" in content
    assert "Error occurred" in content


def test_write_summary_log_invalid_type(tmp_path, sample_brief):
    """Test that invalid log_type raises ValueError."""
    with pytest.raises(ValueError, match="Invalid log_type"):
        write_summary_log(
            run_dir=tmp_path,
            run_id="20260307_120000",
            brief=sample_brief,
            log_type="invalid_type",
        )


def test_write_summary_log_creates_directory(sample_brief):
    """Test that summary log can be written to a new directory."""
    run_dir = Path("genoutput/test_runs/test_dir")
    run_id = "20260307_120000"
    
    # Clean up if directory exists
    if run_dir.exists():
        import shutil
        shutil.rmtree(run_dir.parent)
    
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
        
        summary_path = write_summary_log(
            run_dir=run_dir,
            run_id=run_id,
            brief=sample_brief,
            log_type="asset_generation",
            generated_assets=["test.png"],
        )
        
        assert summary_path.exists()
        assert summary_path.parent == run_dir
    finally:
        # Clean up
        if run_dir.exists():
            import shutil
            shutil.rmtree(run_dir.parent)


def test_write_summary_log_with_path_reference_asset(tmp_path, sample_brief):
    """Test summary log handles Path objects for reference assets."""
    # Modify brief to use Path objects
    sample_brief.products[0].reference_asset = Path("assets/test-product-1.png")
    
    summary_path = write_summary_log(
        run_dir=tmp_path,
        run_id="20260307_120000",
        brief=sample_brief,
        log_type="asset_generation",
        generated_assets=[],
    )
    
    content = summary_path.read_text(encoding="utf-8")
    assert "**Reference Asset:** `test-product-1.png`" in content


def test_write_summary_log_with_string_reference_asset(tmp_path, sample_brief):
    """Test summary log handles string paths for reference assets."""
    # Modify brief to use string paths
    sample_brief.products[0].reference_asset = "assets/test-product-1.png"
    
    summary_path = write_summary_log(
        run_dir=tmp_path,
        run_id="20260307_120000",
        brief=sample_brief,
        log_type="asset_generation",
        generated_assets=[],
    )
    
    content = summary_path.read_text(encoding="utf-8")
    assert "**Reference Asset:** `test-product-1.png`" in content
