"""Build Imagen prompts for text-to-image and img2img generation."""
from src.models import CampaignBrief, Product


class RatioCopy:
    RATIO_1x1 = "square format centered composition"
    RATIO_9x16 = "vertical portrait format for Stories and Reels"
    RATIO_16x9 = "wide horizontal landscape banner format"
    DEFAULT = "balanced composition"


_RATIO_GUIDANCE = {
    "1:1": RatioCopy.RATIO_1x1,
    "9:16": RatioCopy.RATIO_9x16,
    "16:9": RatioCopy.RATIO_16x9,
}


def build_reference_prompt(product: Product) -> str:
    """Build a prompt for generating a reference product photograph.

    Creates a clean, neutral product image suitable as a reference asset.
    No campaign-specific messaging or branding.

    Args:
        product: The product to generate a reference image for.

    Returns:
        Prompt string for generating a reference product photograph.
    """
    return (
        f"Professional product photograph of {product.name}. "
        f"{product.description}. "
        f"Shot against a clean, neutral light-gray background. "
        f"Studio lighting, centered composition, sharp focus. "
        f"No text, no overlays, no people, no brand marks. "
        f"High-quality product photography reference."
    )


def build_prompt(product: Product, brief: CampaignBrief, ratio: str) -> str:
    """Build the text prompt for image generation.

    When the product has a reference_asset, returns an img2img-style prompt.
    Otherwise returns a text-to-image prompt.

    Args:
        product: The product to generate for.
        brief: The campaign brief with message, audience, region.
        ratio: Aspect ratio string ("1:1", "9:16", or "16:9").

    Returns:
        Prompt string to pass to the Imagen client.
    """
    guidance = _RATIO_GUIDANCE.get(ratio, RatioCopy.DEFAULT)

    if product.reference_asset is not None:
        return (
            f"Reimagine this product image as a {ratio} social media advertisement. "
            f"Maintain the product's visual identity for {product.name}. "
            f"Prominently display the text: \"{brief.message}\" in a bold, legible font. "
            f"Target audience: {brief.audience}. Market: {brief.region}. "
            f"Style: {guidance}, professional product photography, clean composition."
        )

    return (
        f"A high-quality advertisement for {product.name}. "
        f"{product.description}. "
        f"Designed for {brief.audience} in {brief.region}. "
        f"The image prominently displays the text: \"{brief.message}\" in a bold, legible font. "
        f"Style: professional product photography, clean composition, {guidance}."
    )
