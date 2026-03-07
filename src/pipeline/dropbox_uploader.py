"""Dropbox uploader for campaign briefs and assets."""
import json
import logging
import os
from pathlib import Path

import click
import yaml

from src.models import CampaignBrief
from src.pipeline.dropbox_client import DropboxClient
from src.utils import sanitize_campaign_slug, serialize_brief_for_export

log = logging.getLogger(__name__)


class CampaignUploader:
    """Handles uploading campaign briefs and assets to Dropbox."""

    def __init__(self, dropbox_client: DropboxClient, app_name: str | None = None):
        """Initialize uploader with a Dropbox client.
        
        Args:
            dropbox_client: Configured DropboxClient instance
            app_name: Dropbox app folder name. Defaults to DROPBOX_APP_NAME or "adobe-poc".
        """
        self.client = dropbox_client
        resolved_app_name = (app_name or os.environ.get("DROPBOX_APP_NAME") or "adobe-poc").strip("/")
        if not resolved_app_name:
            resolved_app_name = "adobe-poc"
        self.base_path = f"/{resolved_app_name}/inputs/cli"

    def upload_campaign(
        self,
        brief: CampaignBrief,
        assets_folder: Path | None = None,
    ) -> dict[str, str]:
        """Upload a campaign brief and its assets to Dropbox.
        
        Args:
            brief: The campaign brief to upload
            assets_folder: Optional folder containing product reference assets
            
        Returns:
            Dictionary mapping uploaded file types to their Dropbox paths:
            {
                "brief_yaml": "/path/to/brief.yaml",
                "brief_json": "/path/to/brief.json",
                "products": {
                    "product-slug": "/path/to/asset.png"
                }
            }
            
        Raises:
            RuntimeError: If any critical uploads fail (brief files or product assets)
        """
        campaign_slug = sanitize_campaign_slug(brief.campaign_name)
        campaign_path = f"{self.base_path}/{campaign_slug}"
        
        click.echo(click.style(f"\n📤 Uploading campaign to Dropbox: {campaign_path}", fg="cyan", bold=True))
        
        uploaded_files = {
            "brief_yaml": None,
            "brief_json": None,
            "products": {}
        }
        
        errors = []
        
        # Upload brief as YAML
        try:
            brief_yaml_path = f"{campaign_path}/brief.yaml"
            brief_dict = serialize_brief_for_export(brief)
            yaml_data = yaml.dump(brief_dict, default_flow_style=False, sort_keys=False)
            self.client.upload(yaml_data.encode("utf-8"), brief_yaml_path)
            uploaded_files["brief_yaml"] = brief_yaml_path
            click.echo(click.style(f"  ✓ Uploaded brief.yaml", fg="green"))
        except Exception as e:
            error_msg = f"Failed to upload brief.yaml: {e}"
            click.echo(click.style(f"  ✗ {error_msg}", fg="red"))
            log.error(error_msg)
            errors.append(error_msg)
        
        # Upload brief as JSON
        try:
            brief_json_path = f"{campaign_path}/brief.json"
            brief_dict = serialize_brief_for_export(brief)
            json_data = json.dumps(brief_dict, indent=2)
            self.client.upload(json_data.encode("utf-8"), brief_json_path)
            uploaded_files["brief_json"] = brief_json_path
            click.echo(click.style(f"  ✓ Uploaded brief.json", fg="green"))
        except Exception as e:
            error_msg = f"Failed to upload brief.json: {e}"
            click.echo(click.style(f"  ✗ {error_msg}", fg="red"))
            log.error(error_msg)
            errors.append(error_msg)
        
        # Check if critical brief files failed - fail immediately if so
        if not uploaded_files["brief_yaml"] or not uploaded_files["brief_json"]:
            click.echo(click.style("\n✗ Critical upload failure: Brief files must be uploaded to continue.", fg="red", bold=True))
            raise RuntimeError(f"Failed to upload campaign brief files: {'; '.join(errors)}")
        
        # Upload product reference assets
        if assets_folder:
            click.echo(click.style("\n📦 Uploading product assets...", fg="cyan"))
            product_errors = []
            
            for product in brief.products:
                if not product.slug:
                    continue
                    
                if product.reference_asset and product.reference_asset.exists():
                    try:
                        product_folder = f"{campaign_path}/{product.slug}"
                        asset_filename = product.reference_asset.name
                        asset_path = f"{product_folder}/{asset_filename}"
                        
                        with open(product.reference_asset, "rb") as f:
                            asset_data = f.read()
                        
                        self.client.upload(asset_data, asset_path)
                        uploaded_files["products"][product.slug] = asset_path
                        click.echo(
                            click.style(f"  ✓ {product.name}: ", fg="green") +
                            f"{asset_filename} → {asset_path}"
                        )
                    except Exception as e:
                        error_msg = f"Failed to upload {product.name}: {e}"
                        click.echo(click.style(f"  ✗ {error_msg}", fg="red"))
                        log.error("Failed to upload asset for %s: %s", product.name, e)
                        product_errors.append(error_msg)
            
            # Check if any product assets failed - fail if so
            if product_errors:
                click.echo(click.style(f"\n✗ Product asset upload failure: {len(product_errors)} asset(s) failed to upload.", fg="red", bold=True))
                raise RuntimeError(f"Failed to upload product assets: {'; '.join(product_errors)}")
        
        # Summary
        product_count = len(uploaded_files["products"])
        total_products = len(brief.products)
        
        click.echo(click.style("\n✨ Upload Summary:", fg="cyan", bold=True))
        click.echo(f"  Campaign: {brief.campaign_name}")
        click.echo(f"  Brief files: {sum([1 for v in [uploaded_files['brief_yaml'], uploaded_files['brief_json']] if v])}/2")
        click.echo(f"  Product assets: {product_count}/{total_products}")
        click.echo(f"  Base path: {campaign_path}")
        click.echo(click.style("  ✓ All uploads completed successfully", fg="green", bold=True))
        
        return uploaded_files


def get_dropbox_client_from_env() -> DropboxClient:
    """Create a DropboxClient from environment variables.
    
    Automatically loads variables from .env file in the project root.
    
    Required environment variables:
    - DROPBOX_ACCESS_TOKEN: Your Dropbox access token
    
    Optional environment variables (for automatic token refresh):
    - DROPBOX_REFRESH_TOKEN: Refresh token for automatic renewal
    - DROPBOX_APP_KEY: Your Dropbox app key
    - DROPBOX_APP_SECRET: Your Dropbox app secret (if required)
    
    Returns:
        Configured DropboxClient instance
        
    Raises:
        ValueError: If DROPBOX_ACCESS_TOKEN is not set in .env file
    """
    access_token = os.environ.get("DROPBOX_ACCESS_TOKEN")
    if not access_token:
        raise ValueError(
            "DROPBOX_ACCESS_TOKEN not found in environment. "
            "Please add it to your .env file."
        )
    
    refresh_token = os.environ.get("DROPBOX_REFRESH_TOKEN")
    app_key = os.environ.get("DROPBOX_APP_KEY")
    app_secret = os.environ.get("DROPBOX_APP_SECRET")
    
    return DropboxClient(
        access_token=access_token,
        refresh_token=refresh_token,
        app_key=app_key,
        app_secret=app_secret,
    )
