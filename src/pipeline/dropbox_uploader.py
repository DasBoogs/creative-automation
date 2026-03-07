"""Dropbox uploader for campaign briefs and assets."""
import json
import logging
import os
from pathlib import Path

import click
import yaml

from src.models import CampaignBrief
from src.pipeline.dropbox_client import DropboxClient

log = logging.getLogger(__name__)


class CampaignUploader:
    """Handles uploading campaign briefs and assets to Dropbox."""

    def __init__(self, dropbox_client: DropboxClient):
        """Initialize uploader with a Dropbox client.
        
        Args:
            dropbox_client: Configured DropboxClient instance
        """
        self.client = dropbox_client
        self.base_path = "/adobe-poc/inputs/cli"

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
        """
        campaign_path = f"{self.base_path}/{brief.campaign_name}"
        
        click.echo(click.style(f"\n📤 Uploading campaign to Dropbox: {campaign_path}", fg="cyan", bold=True))
        
        uploaded_files = {
            "brief_yaml": None,
            "brief_json": None,
            "products": {}
        }
        
        # Upload brief as YAML
        try:
            brief_yaml_path = f"{campaign_path}/brief.yaml"
            brief_dict = brief.model_dump(mode="python")
            # Convert Path objects to strings for YAML serialization
            for product in brief_dict.get("products", []):
                if "reference_asset" in product and product["reference_asset"]:
                    product["reference_asset"] = str(product["reference_asset"])
            
            yaml_data = yaml.dump(brief_dict, default_flow_style=False, sort_keys=False)
            self.client.upload(yaml_data.encode("utf-8"), brief_yaml_path)
            uploaded_files["brief_yaml"] = brief_yaml_path
            click.echo(click.style(f"  ✓ Uploaded brief.yaml", fg="green"))
        except Exception as e:
            click.echo(click.style(f"  ✗ Failed to upload brief.yaml: {e}", fg="red"))
            log.error("Failed to upload brief YAML: %s", e)
        
        # Upload brief as JSON
        try:
            brief_json_path = f"{campaign_path}/brief.json"
            brief_dict = brief.model_dump(mode="python")
            # Convert Path objects to strings for JSON serialization
            for product in brief_dict.get("products", []):
                if "reference_asset" in product and product["reference_asset"]:
                    product["reference_asset"] = str(product["reference_asset"])
            
            json_data = json.dumps(brief_dict, indent=2)
            self.client.upload(json_data.encode("utf-8"), brief_json_path)
            uploaded_files["brief_json"] = brief_json_path
            click.echo(click.style(f"  ✓ Uploaded brief.json", fg="green"))
        except Exception as e:
            click.echo(click.style(f"  ✗ Failed to upload brief.json: {e}", fg="red"))
            log.error("Failed to upload brief JSON: %s", e)
        
        # Upload product reference assets
        if assets_folder:
            click.echo(click.style("\n📦 Uploading product assets...", fg="cyan"))
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
                        click.echo(
                            click.style(f"  ✗ Failed to upload {product.name}: {e}", fg="red")
                        )
                        log.error("Failed to upload asset for %s: %s", product.name, e)
        
        # Summary
        product_count = len(uploaded_files["products"])
        total_products = len(brief.products)
        
        click.echo(click.style("\n✨ Upload Summary:", fg="cyan", bold=True))
        click.echo(f"  Campaign: {brief.campaign_name}")
        click.echo(f"  Brief files: {sum([1 for v in [uploaded_files['brief_yaml'], uploaded_files['brief_json']] if v])}/2")
        click.echo(f"  Product assets: {product_count}/{total_products}")
        click.echo(f"  Base path: {campaign_path}")
        
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
