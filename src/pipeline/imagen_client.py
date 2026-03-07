"""Google Gemini image generation client."""
import logging

from google import genai
from google.genai import types

log = logging.getLogger(__name__)

DEFAULT_IMAGE_MODEL = "gemini-2.5-flash-image"


class ImagenClient:
    """Wraps the google-genai SDK for text-to-image and img2img generation.

    The model is configurable via the `model` parameter (or GEMINI_MODEL env var).
    Defaults to gemini-2.5-flash-image.
    """

    def __init__(self, api_key: str, model: str = DEFAULT_IMAGE_MODEL) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def generate(
        self,
        prompt: str,
        ratio: str,
        reference_image_bytes: bytes | None,
    ) -> bytes:
        """Generate an image from a prompt, optionally guided by a reference image.

        Args:
            prompt: Text prompt describing the desired image.
            ratio: Aspect ratio string accepted by Imagen ("1:1", "9:16", "16:9").
            reference_image_bytes: Raw image bytes for img2img guidance, or None.

        Returns:
            Raw PNG image bytes from the API response.
        """
        config = types.GenerateContentConfig(
            response_modalities=["IMAGE", "TEXT"],
            image_config=types.ImageConfig(aspect_ratio=ratio),
        )

        if reference_image_bytes is not None:
            contents = [
                types.Part.from_bytes(
                    data=reference_image_bytes,
                    mime_type="image/png",
                ),
                types.Part.from_text(text=prompt),
            ]
        else:
            contents = [types.Part.from_text(text=prompt)]

        log.debug("Calling model=%s ratio=%s img2img=%s", self._model, ratio, reference_image_bytes is not None)
        try:
            response = self._client.models.generate_content(
                model=self._model,
                contents=contents,
                config=config,
            )
        except Exception as exc:
            # Re-raise with model name included so callers can surface it clearly
            raise RuntimeError(f"Gemini API call failed (model={self._model}): {exc}") from exc

        for part in response.parts:
            if part.inline_data is not None:
                return part.inline_data.data

        # The API returned a response but contained no image data — likely a
        # content policy rejection or unsupported prompt. Log the full response
        # text (if any) to help diagnose.
        text_parts = [p.text for p in response.parts if getattr(p, "text", None)]
        log.error("No image in response from model=%s. Text parts: %s", self._model, text_parts)
        raise RuntimeError(
            f"No image data returned from Gemini API (model={self._model}). "
            f"Response text: {text_parts or '(none)'}"
        )
