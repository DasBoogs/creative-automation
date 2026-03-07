"""Campaign asset generator: generates ad creatives for each product x ratio and uploads to Dropbox."""
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import click

from src.models import CampaignBrief, Product
from src.pipeline.dropbox_client import DropboxClient
from src.pipeline.imagen_client import DEFAULT_IMAGE_MODEL, ImagenClient
from src.pipeline.prompt_builder import build_prompt

log = logging.getLogger(__name__)


def _campaign_folder(brief: CampaignBrief) -> str:
    """Return the stable Dropbox folder prefix for this campaign (no date).
    
    Keeping the folder name date-free lets multiple runs for the same campaign
    share the same structure.
    """
    slug = brief.campaign_name.lower().replace(" ", "-").replace(":", "x")
    return f"/adobe-poc/outputs/cli/{slug}"


def _upload_image(
    dbx: DropboxClient,
    image_bytes: bytes,
    run_id: str,
    brief: CampaignBrief,
    product_slug: str,
    ratio: str,
) -> str:
    """Upload an image to Dropbox and return its temporary link URL.
    
    Args:
        dbx: DropboxClient instance.
        image_bytes: Raw PNG image bytes.
        run_id: Unique run identifier.
        brief: Campaign brief.
        product_slug: Product slug.
        ratio: Aspect ratio string.
        
    Returns:
        Temporary download link URL from Dropbox.
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dbx_path = f"{_campaign_folder(brief)}/{run_id}/{product_slug}/{ratio}_{ts}.png"
    
    try:
        dbx.upload(image_bytes, dbx_path)
        url = dbx.get_temporary_link(dbx_path)
        log.info("run=%s uploaded product=%s ratio=%s → %s", run_id, product_slug, ratio, url)
        return url
    except Exception as exc:
        log.error("run=%s failed to upload product=%s ratio=%s: %s", run_id, product_slug, ratio, exc)
        raise


def _write_report(
    dbx: DropboxClient,
    run_id: str,
    brief: CampaignBrief,
    report: dict,
) -> None:
    """Write a run report to Dropbox as JSON.
    
    Args:
        dbx: DropboxClient instance.
        run_id: Unique run identifier.
        brief: Campaign brief.
        report: Dictionary containing run results and timings.
    """
    campaign_slug = brief.campaign_name.lower().replace(" ", "-").replace(":", "x")
    report_path = f"/adobe-poc/outputs/cli/{campaign_slug}/{run_id}/report.json"
    
    try:
        report_json = json.dumps(report, indent=2)
        dbx.upload(report_json.encode("utf-8"), report_path)
        log.info("run=%s wrote report → %s", run_id, report_path)
    except Exception as exc:
        log.error("run=%s failed to write report: %s", run_id, exc)
        raise


class CampaignGenerator:
    """Generate and upload ad creatives for a campaign brief."""
    
    def __init__(
        self,
        google_api_key: str | None = None,
        dropbox_token: str | None = None,
        gemini_model: str = DEFAULT_IMAGE_MODEL,
    ):
        """Initialize the campaign generator.
        
        Args:
            google_api_key: Google API key. If not provided, reads from GOOGLE_API_KEY env var.
            dropbox_token: Dropbox access token. If not provided, reads from DROPBOX_ACCESS_TOKEN env var.
            gemini_model: Gemini model ID to use for image generation.
            
        Raises:
            ValueError: If required credentials are not provided and not set in environment.
        """
        self.google_api_key = google_api_key or os.getenv("GOOGLE_API_KEY")
        if not self.google_api_key:
            raise ValueError("GOOGLE_API_KEY not provided and not set in environment")
        
        self.dropbox_token = dropbox_token or os.getenv("DROPBOX_ACCESS_TOKEN")
        if not self.dropbox_token:
            raise ValueError("DROPBOX_ACCESS_TOKEN not provided and not set in environment")
        
        self.gemini_model = gemini_model
        self._imagen_client = ImagenClient(api_key=self.google_api_key, model=gemini_model)
        self._dropbox_client = DropboxClient(access_token=self.dropbox_token)
    
    def generate_campaign_assets(
        self,
        run_id: str,
        brief: CampaignBrief,
    ) -> dict:
        """Generate and upload ad creatives for all products x ratios.
        
        Stages:
            1. For each product: verify reference asset exists.
            2. For each product x ratio: generate ad creative using the reference.
            3. Upload each creative to Dropbox.
            4. Write a run report.
        
        Args:
            run_id: Unique run identifier.
            brief: Validated CampaignBrief with products and reference assets.
            
        Returns:
            Dictionary with status, outputs, and log.
            {
                "status": "complete" | "error",
                "run_id": str,
                "outputs": {product_slug: {ratio: url, ...}, ...},
                "timings": {product_slug: {ratio: seconds, ...}, ...},
                "log": [messages...],
                "error": str (if status == "error")
            }
        """
        pipeline_log: list[str] = []
        outputs: dict[str, dict[str, str]] = {}
        timings: dict[str, dict[str, float]] = {}
        
        log.info(
            "run=%s generating campaign=%s products=%s ratios=%s",
            run_id,
            brief.campaign_name,
            [p.slug for p in brief.products],
            brief.aspect_ratios,
        )
        click.echo()
        click.echo(
            click.style(
                f"🎬 Generating ad creatives for {brief.campaign_name}",
                fg="cyan",
                bold=True,
            )
        )
        click.echo(click.style(f"Run ID: {run_id}", fg="cyan"))
        click.echo()
        
        # Progress tracking
        n_products = len(brief.products)
        n_ratios = len(brief.aspect_ratios)
        total_tasks = n_products * n_ratios
        completed = 0
        
        try:
            # Stage 1: Verify reference assets
            missing_assets = []
            for product in brief.products:
                if product.reference_asset is None:
                    missing_assets.append(product.name)
            
            if missing_assets:
                msg = f"⚠ Warning: {len(missing_assets)} product(s) without reference assets: {', '.join(missing_assets)}"
                click.echo(click.style(msg, fg="yellow"))
                pipeline_log.append(msg)
                log.warning("run=%s missing reference assets for: %s", run_id, missing_assets)
            
            # Stage 2 & 3: Generate and upload for each product x ratio
            for product in brief.products:
                outputs[product.slug] = {}
                timings[product.slug] = {}
                
                # Skip if no reference asset
                if product.reference_asset is None:
                    pipeline_log.append(f"Skipping {product.name}: no reference asset")
                    log.info("run=%s skipping product=%s (no reference asset)", run_id, product.slug)
                    continue
                
                # Read reference asset bytes
                try:
                    if isinstance(product.reference_asset, Path):
                        ref_bytes = product.reference_asset.read_bytes()
                    else:
                        ref_bytes = Path(product.reference_asset).read_bytes()
                    log.info("run=%s loaded reference for product=%s (%d bytes)", run_id, product.slug, len(ref_bytes))
                except Exception as exc:
                    msg = f"Failed to load reference asset for {product.name}: {exc}"
                    click.echo(click.style(f"  ✗ {msg}", fg="red"))
                    pipeline_log.append(msg)
                    log.error("run=%s %s", run_id, msg)
                    continue
                
                click.echo(click.style(f"📦 {product.name}", fg="green", bold=True))
                
                # Generate each ratio
                for ratio in brief.aspect_ratios:
                    progress_pct = int(completed / total_tasks * 100)
                    click.echo(f"  Generating {ratio}... ({progress_pct}%)", nl=False)
                    
                    try:
                        prompt = build_prompt(product, brief, ratio=ratio)
                        t_start = time.monotonic()
                        
                        image_bytes = self._imagen_client.generate(
                            prompt=prompt,
                            ratio=ratio,
                            reference_image_bytes=ref_bytes,
                        )
                        
                        elapsed = time.monotonic() - t_start
                        timings[product.slug][ratio] = round(elapsed, 2)
                        
                        # Upload to Dropbox
                        url = _upload_image(
                            dbx=self._dropbox_client,
                            image_bytes=image_bytes,
                            run_id=run_id,
                            brief=brief,
                            product_slug=product.slug,
                            ratio=ratio,
                        )
                        outputs[product.slug][ratio] = url
                        
                        pipeline_log.append(f"Generated {product.name} {ratio} in {elapsed:.1f}s → {url}")
                        click.echo(f"\r  ✓ {ratio} generated in {elapsed:.1f}s")
                        
                    except Exception as exc:
                        msg = f"Failed to generate {product.name} {ratio}: {exc}"
                        click.echo(f"\r  ✗ {ratio} failed: {exc}")
                        pipeline_log.append(msg)
                        log.error("run=%s %s", run_id, msg)
                    
                    completed += 1
            
            # Stage 4: Write report
            try:
                report = {
                    "run_id": run_id,
                    "campaign": brief.campaign_name,
                    "timestamp": datetime.now().isoformat(),
                    "timings": timings,
                    "outputs": outputs,
                }
                _write_report(
                    dbx=self._dropbox_client,
                    run_id=run_id,
                    brief=brief,
                    report=report,
                )
                pipeline_log.append("Report written to Dropbox")
                click.echo()
                click.echo(click.style("✓ Report written to Dropbox", fg="green"))
            except Exception as exc:
                msg = f"Warning: could not write report: {exc}"
                pipeline_log.append(msg)
                log.warning("run=%s %s", run_id, msg)
                click.echo(click.style(f"⚠ {msg}", fg="yellow"))
            
            click.echo()
            click.echo(click.style("✓ Campaign generation complete!", fg="green", bold=True))
            click.echo()
            
            return {
                "status": "complete",
                "run_id": run_id,
                "outputs": outputs,
                "timings": timings,
                "log": pipeline_log,
            }
            
        except Exception as exc:
            error_msg = f"Pipeline failed: {exc}"
            pipeline_log.append(error_msg)
            log.error("run=%s %s", run_id, error_msg)
            click.echo(click.style(f"✗ {error_msg}", fg="red"))
            
            return {
                "status": "error",
                "run_id": run_id,
                "error": str(exc),
                "log": pipeline_log,
            }
