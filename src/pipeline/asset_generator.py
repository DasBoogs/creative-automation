"""Generate missing product assets using Imagen."""
import json
import logging
import os
from datetime import datetime
from pathlib import Path

import click
import yaml

from src.models import CampaignBrief, Product
from src.pipeline.imagen_client import ImagenClient
from src.pipeline.prompt_builder import build_reference_prompt
from src.pipeline.summary_logger import write_summary_log
from src.utils import serialize_brief_for_export

log = logging.getLogger(__name__)


class AssetGenerator:
    """Generate missing product reference assets using Imagen."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        """Initialize the asset generator.
        
        Args:
            api_key: Google API key. If not provided, reads from GOOGLE_API_KEY env var.
            model: Gemini model to use. If not provided, reads from GEMINI_MODEL env var.
        
        Raises:
            ValueError: If API key is not provided and GOOGLE_API_KEY is not set.
        """
        api_key = api_key or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not set in environment")
        
        model = model or os.getenv("GEMINI_MODEL")
        self._client = ImagenClient(api_key=api_key, model=model) if model else ImagenClient(api_key=api_key)

    def generate_missing_assets(
        self,
        brief: CampaignBrief,
        workspace_root: Path | None = None,
    ) -> CampaignBrief:
        """Generate reference assets for products that don't have them.

        Args:
            brief: Campaign brief with products to process.
            workspace_root: Root directory of the workspace. If None, uses current working directory.

        Returns:
            Updated campaign brief with reference_asset paths set for generated assets.
        """
        if workspace_root is None:
            workspace_root = Path.cwd()
        
        # Create timestamped run directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = workspace_root / "genoutput" / "runs" / timestamp
        run_dir.mkdir(parents=True, exist_ok=True)
        
        products_to_generate = [p for p in brief.products if p.reference_asset is None]
        
        if not products_to_generate:
            click.echo(click.style("✓ All products have reference assets", fg="green"))
            return brief
        
        click.echo(
            click.style(
                f"\n🎨 Generating missing reference assets ({len(products_to_generate)}/{len(brief.products)})",
                fg="cyan",
                bold=True
            )
        )
        click.echo(click.style(f"📁 Output directory: {run_dir}", fg="cyan"))
        
        # Use the first aspect ratio as standard for reference asset generation
        reference_ratio = brief.aspect_ratios[0] if brief.aspect_ratios else "1:1"
        
        generated_count = 0
        for product in products_to_generate:
            try:
                click.echo(click.style(f"\nGenerating: {product.name}...", fg="blue"))
                
                prompt = build_reference_prompt(product)
                log.debug("Using prompt: %s", prompt)
                
                image_bytes = self._client.generate(
                    prompt=prompt,
                    ratio=reference_ratio,
                    reference_image_bytes=None,
                )
                
                # Save generated image with slug-based naming (no _reference suffix)
                # This allows easy copying to input folders for automatic matching
                asset_path = run_dir / f"{product.slug}.png"
                asset_path.write_bytes(image_bytes)
                
                product.reference_asset = asset_path
                generated_count += 1
                
                click.echo(
                    click.style(f"  ✓ Generated: ", fg="green") +
                    f"{product.slug}.png"
                )
                
            except Exception as exc:
                click.echo(
                    click.style(f"  ✗ Failed to generate asset: {exc}", fg="red")
                )
                log.error("Failed to generate asset for %s: %s", product.name, exc)
        
        # Save the brief that was used for generation
        self._save_brief_to_run_dir(brief, run_dir)
        
        # Write summary log
        generated_filenames = [f"{p.slug}.png" for p in products_to_generate if p.reference_asset]
        try:
            summary_path = write_summary_log(
                run_dir=run_dir,
                run_id=timestamp,
                brief=brief,
                log_type="asset_generation",
                generated_assets=generated_filenames,
            )
            click.echo(click.style(f"📋 Summary log: {summary_path.name}", fg="green"))
        except Exception as exc:
            log.warning("Failed to write summary log: %s", exc)
            click.echo(click.style(f"  ⚠ Could not write summary log: {exc}", fg="yellow"))
        
        click.echo(
            click.style(
                f"\n✨ Generated {generated_count}/{len(products_to_generate)} reference assets",
                fg="cyan"
            )
        )
        click.echo(
            click.style(
                f"💡 Tip: Copy {run_dir / '*.png'} to your assets folder to use in future runs",
                fg="yellow"
            )
        )
        return brief
    
    def _save_brief_to_run_dir(self, brief: CampaignBrief, run_dir: Path) -> None:
        """Save the campaign brief to the run directory for reference.
        
        Args:
            brief: Campaign brief to save.
            run_dir: Directory to save the brief in.
        """
        try:
            brief_dict = serialize_brief_for_export(brief)
            # Save as YAML
            yaml_path = run_dir / "brief.yaml"
            with open(yaml_path, "w", encoding="utf-8") as f:
                yaml.dump(brief_dict, f, default_flow_style=False, sort_keys=False)
            
            # Save as JSON
            json_path = run_dir / "brief.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(brief_dict, f, indent=2)
            
            click.echo(click.style(f"📄 Saved brief to run directory", fg="green"))
        except Exception as e:
            log.warning("Failed to save brief to run directory: %s", e)
            click.echo(click.style(f"  ⚠ Could not save brief: {e}", fg="yellow"))
