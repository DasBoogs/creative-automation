#!/usr/bin/env python3
"""CLI script for loading and displaying campaign briefs."""
import logging
import sys
from pathlib import Path

import click
from dotenv import load_dotenv

from src.brief_loader import load_brief_from_file
from src.models import CampaignBrief
from src.pipeline.asset_generator import AssetGenerator
from src.pipeline.dropbox_uploader import CampaignUploader, get_dropbox_client_from_env

# Load environment variables from .env file
load_dotenv()

log = logging.getLogger(__name__)


def assign_reference_assets(brief: CampaignBrief, assets_folder: Path) -> None:
    """
    Assign reference assets to products by matching image filenames to product slugs.
    
    Args:
        brief: Campaign brief with products to assign assets to
        assets_folder: Path to folder containing reference image assets
        
    Looks for image files (png, jpg, jpeg, gif, webp) that match product slugs.
    For example, a product with slug "ultra-shield-sunscreen-spf50" would match
    files like "ultra-shield-sunscreen-spf50.png" or "ultrashield-sunscreen-spf50.jpg".
    """
    # Supported image extensions
    image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff", ".tif"}
    
    # Get all image files in the assets folder
    image_files = [
        f for f in assets_folder.iterdir()
        if f.is_file() and f.suffix.lower() in image_extensions
    ]
    
    # Create a mapping of normalized filenames to actual paths
    file_map = {f.stem.lower().replace("_", "-"): f for f in image_files}
    
    matched_count = 0
    
    for product in brief.products:
        if not product.slug:
            continue
            
        # Try to find a matching file
        normalized_slug = product.slug.lower().replace("_", "-")
        
        if normalized_slug in file_map:
            product.reference_asset = file_map[normalized_slug]
            matched_count += 1
            click.echo(
                click.style(f"✓ Matched {product.name}: ", fg="green") +
                f"{file_map[normalized_slug].name}"
            )
    
    # Report summary
    if matched_count == 0:
        click.echo(click.style("⚠ No reference assets matched to products", fg="yellow"))
    elif matched_count < len(brief.products):
        click.echo(
            click.style(
                f"⚠ Matched {matched_count}/{len(brief.products)} products to assets",
                fg="yellow"
            )
        )
    else:
        click.echo(click.style(f"✓ All {matched_count} products matched to assets", fg="green"))
    click.echo()


@click.command()
@click.argument(
    "brief_file",
    type=click.Path(exists=True, path_type=Path),
)
@click.option(
    "--json",
    "output_json",
    is_flag=True,
    help="Output the brief as JSON",
)
@click.option(
    "--validate-only",
    is_flag=True,
    help="Only validate the brief without displaying details",
)
@click.option(
    "--assets-folder",
    "assets_folder",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    help="Path to folder containing product reference images. Images will be matched to products by slug.",
)
def main(brief_file: Path, output_json: bool, validate_only: bool, assets_folder: Path | None):
    """
    Load and display a campaign brief from a YAML or JSON file.
    The brief and assets will be automatically uploaded to Dropbox.
    
    BRIEF_FILE: Path to the campaign brief file (.yaml, .yml, or .json)
    
    Dropbox credentials are automatically loaded from your .env file.
    
    Examples:
    
        # Load and upload a brief with reference assets
        python load_brief.py briefs/example.yaml --assets-folder briefs/assets
        
        # Validate a brief without uploading
        python load_brief.py briefs/example.yaml --validate-only
        
        # Output brief as JSON (also uploads)
        python load_brief.py briefs/example.yaml --json
    """
    try:
        # Load the brief
        brief = load_brief_from_file(brief_file)
        
        # Assign reference assets if assets folder is provided
        if assets_folder:
            assign_reference_assets(brief, assets_folder)
        
        if validate_only:
            click.echo(click.style("✓ Brief is valid", fg="green"))
            return
        
        # Generate missing reference assets using Imagen
        products_without_assets = [p for p in brief.products if p.reference_asset is None]
        if products_without_assets:
            try:
                click.echo()
                generator = AssetGenerator()
                # Generate into timestamped run directory at workspace root
                workspace_root = Path.cwd()
                brief = generator.generate_missing_assets(brief, workspace_root)
            except ValueError as e:
                click.echo(
                    click.style(
                        f"\n⚠ Warning: Could not generate missing assets - {e}",
                        fg="yellow"
                    )
                )
                click.echo(
                    click.style(
                        "  Some products will not have reference assets.",
                        fg="yellow"
                    )
                )
            except Exception as e:
                click.echo(
                    click.style(
                        f"\n⚠ Warning: Asset generation failed - {e}",
                        fg="yellow"
                    )
                )
                log.error("Asset generation error: %s", e)
        
        # Upload to Dropbox (always required)
        try:
            client = get_dropbox_client_from_env()
            uploader = CampaignUploader(client)
            uploaded_files = uploader.upload_campaign(brief, assets_folder)
        except ValueError as e:
            click.echo(click.style(f"\nError: {e}", fg="red"), err=True)
            click.echo(click.style("\nMake sure DROPBOX_ACCESS_TOKEN is set in your .env file.", fg="yellow"))
            sys.exit(1)
        except Exception as e:
            click.echo(click.style(f"\nError uploading to Dropbox: {e}", fg="red"), err=True)
            sys.exit(1)
        
        if output_json:
            # Output as JSON
            click.echo(brief.model_dump_json(indent=2))
        else:
            # Display formatted output
            display_brief(brief)
            
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(1)
    except ValueError as e:
        click.echo(click.style(f"Error: {e}", fg="red"), err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(click.style(f"Unexpected error: {e}", fg="red"), err=True)
        sys.exit(1)


def display_brief(brief: CampaignBrief):
    """Display a formatted campaign brief."""
    click.echo()
    click.echo(click.style("=" * 60, fg="cyan"))
    click.echo(click.style(f"Campaign: {brief.campaign_name}", fg="cyan", bold=True))
    click.echo(click.style("=" * 60, fg="cyan"))
    click.echo()
    
    click.echo(click.style("Region:", fg="yellow"))
    click.echo(f"  {brief.region}")
    click.echo()
    
    click.echo(click.style("Audience:", fg="yellow"))
    click.echo(f"  {brief.audience}")
    click.echo()
    
    click.echo(click.style("Message:", fg="yellow"))
    click.echo(f"  {brief.message}")
    click.echo()
    
    click.echo(click.style("Aspect Ratios:", fg="yellow"))
    click.echo(f"  {', '.join(brief.aspect_ratios)}")
    click.echo()
    
    click.echo(click.style(f"Products ({len(brief.products)}):", fg="yellow"))
    click.echo()
    
    for i, product in enumerate(brief.products, 1):
        click.echo(click.style(f"{i}. {product.name}", fg="green", bold=True))
        click.echo(f"   Slug: {product.slug}")
        click.echo(f"   Description: {product.description}")
        if product.reference_asset:
            click.echo(f"   Reference Asset: {product.reference_asset}")
        click.echo()
    
    click.echo(click.style("=" * 60, fg="cyan"))
    click.echo()


if __name__ == "__main__":
    main()
