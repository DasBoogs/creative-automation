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
from src.pipeline.localizer import (
    DEFAULT_TEXT_MODEL,
    localize_message,
    localize_description,
)
from src.pipeline.prompt_builder import build_prompt
from src.utils import sanitize_campaign_slug

log = logging.getLogger(__name__)


def _dropbox_app_name() -> str:
    """Return configured Dropbox app root folder name."""
    app_name = (os.getenv("DROPBOX_APP_NAME") or "adobe-poc").strip("/")
    return app_name or "adobe-poc"


def _campaign_folder(brief: CampaignBrief) -> str:
    """Return the stable Dropbox folder prefix for this campaign (no date).
    
    Keeping the folder name date-free lets multiple runs for the same campaign
    share the same structure.
    """
    slug = sanitize_campaign_slug(brief.campaign_name)
    return f"/{_dropbox_app_name()}/outputs/cli/{slug}"


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
    report_path = f"{_campaign_folder(brief)}/{run_id}/report.json"
    
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
        dropbox_refresh_token: str | None = None,
        dropbox_app_key: str | None = None,
        dropbox_app_secret: str | None = None,
        gemini_model: str = DEFAULT_IMAGE_MODEL,
        text_model: str | None = None,
    ):
        """Initialize the campaign generator.
        
        Args:
            google_api_key: Google API key. If not provided, reads from GOOGLE_API_KEY env var.
            dropbox_token: Dropbox access token. If not provided, reads from DROPBOX_ACCESS_TOKEN env var.
            dropbox_refresh_token: Dropbox refresh token. If not provided, reads from DROPBOX_REFRESH_TOKEN env var.
            dropbox_app_key: Dropbox app key. If not provided, reads from DROPBOX_APP_KEY env var.
            dropbox_app_secret: Dropbox app secret. If not provided, reads from DROPBOX_APP_SECRET env var.
            gemini_model: Gemini model ID to use for image generation.
            text_model: Gemini text model ID to use for localization. If not provided, reads from GEMINI_TEXT_MODEL env var.
            
        Raises:
            ValueError: If required credentials are not provided and not set in environment.
        """
        self.google_api_key = google_api_key or os.getenv("GOOGLE_API_KEY")
        if not self.google_api_key:
            raise ValueError("GOOGLE_API_KEY not provided and not set in environment")
        
        self.dropbox_token = dropbox_token or os.getenv("DROPBOX_ACCESS_TOKEN")
        self.dropbox_refresh_token = dropbox_refresh_token or os.getenv("DROPBOX_REFRESH_TOKEN")
        self.dropbox_app_key = dropbox_app_key or os.getenv("DROPBOX_APP_KEY")
        self.dropbox_app_secret = dropbox_app_secret or os.getenv("DROPBOX_APP_SECRET")

        has_access_token = bool(self.dropbox_token)
        has_refresh_credentials = bool(self.dropbox_refresh_token and self.dropbox_app_key)
        if not has_access_token and not has_refresh_credentials:
            raise ValueError(
                "Dropbox credentials not provided. Set DROPBOX_ACCESS_TOKEN or "
                "DROPBOX_REFRESH_TOKEN + DROPBOX_APP_KEY."
            )
        
        self.gemini_model = gemini_model
        self.text_model = text_model or os.getenv("GEMINI_TEXT_MODEL", DEFAULT_TEXT_MODEL)
        self._imagen_client = ImagenClient(api_key=self.google_api_key, model=gemini_model)
        self._dropbox_client = DropboxClient(
            access_token=self.dropbox_token or "",
            refresh_token=self.dropbox_refresh_token,
            app_key=self.dropbox_app_key,
            app_secret=self.dropbox_app_secret,
        )
    
    def localize_brief(self, brief: CampaignBrief) -> tuple[CampaignBrief, dict]:
        """Localize campaign message and product descriptions for the target region.
        
        Creates a copy of the brief with translated text if needed. Only translates
        when the brief's language differs from the region's native language.
        
        Args:
            brief: Original campaign brief.
            
        Returns:
            Tuple of (localized_brief, localization_info) where localization_info
            contains details about what was translated.
        """
        localization_info = {
            "target_language": None,
            "message_translated": False,
            "original_message": None,
            "localized_message": None,
            "products": {},
        }
        
        # Localize campaign message
        localized_message, target_language = localize_message(
            message=brief.message,
            region=brief.region,
            api_key=self.google_api_key,
            brief_language=brief.language,
            model=self.text_model,
        )
        
        if target_language:
            localization_info["target_language"] = target_language
            localization_info["message_translated"] = True
            localization_info["original_message"] = brief.message
            localization_info["localized_message"] = localized_message
            log.info("Campaign message localized to %s: %r → %r", target_language, brief.message, localized_message)
            click.echo(click.style(f"  ✓ Campaign message localized to {target_language}", fg="green"))
        else:
            click.echo(click.style("  ℹ No message translation needed", fg="cyan"))
            log.info("Campaign message does not require localization")
        
        # Localize product descriptions
        localized_products = []
        for product in brief.products:
            localized_desc, desc_language = localize_description(
                description=product.description,
                region=brief.region,
                api_key=self.google_api_key,
                brief_language=brief.language,
                model=self.text_model,
            )
            
            # Create a copy of the product with localized description
            localized_product = product.model_copy(update={"description": localized_desc})
            localized_products.append(localized_product)
            
            if desc_language:
                localization_info["products"][product.slug] = {
                    "translated": True,
                    "original": product.description,
                    "localized": localized_desc,
                    "language": desc_language,
                }
                log.info("Product %s description localized to %s", product.name, desc_language)
                click.echo(click.style(f"  ✓ {product.name} description localized", fg="green"))
            else:
                localization_info["products"][product.slug] = {
                    "translated": False,
                }
        
        # Create localized brief
        localized_brief = brief.model_copy(update={
            "message": localized_message,
            "products": localized_products,
        })
        
        return localized_brief, localization_info
    
    def generate_campaign_assets(
        self,
        run_id: str,
        brief: CampaignBrief,
    ) -> dict:
        """Generate and upload ad creatives for all products x ratios.
        
        Stages:
            0. Localize campaign message and product descriptions if needed.
            1. For each product: verify reference asset exists.
            2. For each product x ratio: generate ad creative using the reference.
            3. Upload each creative to Dropbox.
            4. Write a run report.
        
        Args:
            run_id: Unique run identifier.
            brief: Validated CampaignBrief with products and reference assets.
            
        Returns:
            Dictionary with status, outputs, localization info, and log.
            {
                "status": "complete" | "error",
                "run_id": str,
                "outputs": {product_slug: {ratio: url, ...}, ...},
                "timings": {product_slug: {ratio: seconds, ...}, ...},
                "localization": {localization details},
                "log": [messages...],
                "error": str (if status == "error")
            }
        """
        pipeline_log: list[str] = []
        outputs: dict[str, dict[str, str]] = {}
        timings: dict[str, dict[str, float]] = {}
        
        log.info(
            "run=%s generating campaign=%s products=%s ratios=%s region=%s",
            run_id,
            brief.campaign_name,
            [p.slug for p in brief.products],
            brief.aspect_ratios,
            brief.region,
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
        click.echo(click.style(f"Region: {brief.region}", fg="cyan"))
        click.echo()
        
        try:
            # Stage 0: Localize text content
            click.echo(click.style("🌐 Localizing campaign content...", fg="magenta", bold=True))
            localized_brief, localization_info = self.localize_brief(brief)
            pipeline_log.append(f"Localization completed (target_language={localization_info.get('target_language', 'none')})")
            click.echo()
            
            # Use localized brief for the rest of the pipeline
            brief = localized_brief
            
            # Progress tracking
            n_products = len(brief.products)
            n_ratios = len(brief.aspect_ratios)
            total_tasks = n_products * n_ratios
            completed = 0
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
                    "region": brief.region,
                    "timestamp": datetime.now().isoformat(),
                    "localization": localization_info,
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
            
            # Display localization summary
            if localization_info.get("target_language"):
                click.echo()
                click.echo(click.style("📝 Localization Summary:", fg="magenta", bold=True))
                click.echo(click.style(f"  Target Language: {localization_info['target_language']}", fg="magenta"))
                if localization_info.get("message_translated"):
                    click.echo(click.style(f"  Original Message: {localization_info['original_message']}", fg="white"))
                    click.echo(click.style(f"  Localized Message: {localization_info['localized_message']}", fg="green"))
                
                translated_products = [
                    slug for slug, info in localization_info.get("products", {}).items()
                    if info.get("translated")
                ]
                if translated_products:
                    click.echo(click.style(f"  Translated Products: {', '.join(translated_products)}", fg="green"))
            
            click.echo()
            click.echo(click.style("✓ Campaign generation complete!", fg="green", bold=True))
            click.echo()
            
            return {
                "status": "complete",
                "run_id": run_id,
                "outputs": outputs,
                "timings": timings,
                "localization": localization_info,
                "log": pipeline_log,
            }
            
        except Exception as exc:
            error_msg = f"Pipeline failed: {exc}"
            pipeline_log.append(error_msg)
            log.error("run=%s %s", run_id, error_msg)
            click.echo(click.style(f"✗ {error_msg}", fg="red"))
            
            # Try to include localization info even on error
            localization_info = locals().get("localization_info", {})
            
            return {
                "status": "error",
                "run_id": run_id,
                "error": str(exc),
                "localization": localization_info,
                "log": pipeline_log,
            }
