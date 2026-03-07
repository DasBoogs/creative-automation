"""Localize campaign messages and product descriptions to the target region's language using Gemini."""
import logging

from google import genai

log = logging.getLogger(__name__)

DEFAULT_TEXT_MODEL = "gemini-2.5-flash-lite"

# Regions where English is the primary language — no translation needed.
_ENGLISH_REGIONS = {"US", "UK", "AU", "CA", "NZ", "IE", "ZA", "SG"}

_REGION_LANGUAGE: dict[str, str] = {
    "IT": "Italian",
    "FR": "French",
    "DE": "German",
    "ES": "Spanish",
    "MX": "Spanish (Latin American)",
    "PT": "Portuguese (European)",
    "BR": "Portuguese (Brazilian)",
    "NL": "Dutch",
    "BE": "Dutch",
    "JP": "Japanese",
    "KR": "Korean",
    "CN": "Chinese (Simplified)",
    "TW": "Chinese (Traditional)",
    "HK": "Chinese (Traditional)",
    "RU": "Russian",
    "AR": "Arabic",
    "PL": "Polish",
    "SE": "Swedish",
    "NO": "Norwegian",
    "DK": "Danish",
    "FI": "Finnish",
    "GR": "Greek",
    "TR": "Turkish",
    "HE": "Hebrew",
    "IL": "Hebrew",
    "TH": "Thai",
    "VI": "Vietnamese",
    "VN": "Vietnamese",
    "ID": "Indonesian",
    "HU": "Hungarian",
    "RO": "Romanian",
    "CZ": "Czech",
    "SK": "Slovak",
    "HR": "Croatian",
    "UA": "Ukrainian",
    "IN": "Hindi",
}


def _resolve_language(region: str, brief_language: str | None) -> str | None:
    """Return the language name for a region code, or None if English/unknown.
    
    Args:
        region: ISO 3166-1 alpha-2 region code (e.g. "IT", "FR", "US").
        brief_language: Optional language specified in the brief (e.g. "English", "Spanish").
        
    Returns:
        Language name for translation, or None if no translation needed.
    """
    region_upper = region.upper()
    
    # If the region uses English natively, check if brief specifies a different language
    if region_upper in _ENGLISH_REGIONS:
        # If brief language is specified and not English, translate to that language
        if brief_language and brief_language.lower() not in {"english", "en"}:
            return brief_language
        return None
    
    # Get the native language for the region
    target_language = _REGION_LANGUAGE.get(region_upper)
    
    # If brief language matches target language, no translation needed
    if brief_language and target_language:
        if brief_language.lower() in target_language.lower():
            return None
    
    return target_language


def localize_message(
    message: str,
    region: str,
    api_key: str,
    brief_language: str | None = None,
    model: str = DEFAULT_TEXT_MODEL,
) -> tuple[str, str | None]:
    """Translate a campaign message to the language of the target region.

    Returns the original message unchanged for English-speaking regions or
    when the brief language matches the region's native language.
    Falls back to the original on API error.

    Args:
        message: The original campaign message.
        region: ISO 3166-1 alpha-2 region code (e.g. "IT", "FR", "US").
        api_key: Google AI API key.
        brief_language: Optional language specified in the brief.
        model: Gemini text model to use (not the image model).

    Returns:
        Tuple of (translated_message, target_language).
        If no translation occurred, target_language is None.
    """
    language = _resolve_language(region, brief_language)
    if language is None:
        log.info("region=%s brief_language=%s — skipping message localization", region, brief_language)
        return message, None

    log.info("Localizing message for region=%s (%s)", region, language)

    prompt = (
        f"Translate the following advertising slogan to {language}. "
        f"Keep it short, punchy, and suitable for a marketing campaign. "
        f"Preserve the tone and energy of the original. "
        f"Return only the translated text, nothing else.\n\n"
        f'"{message}"'
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=model, contents=prompt)
        translated = response.text.strip().strip("\"'")
        log.info("Localized %r → %r (region=%s, language=%s)", message, translated, region, language)
        return translated, language
    except Exception as exc:
        log.warning(
            "Localization API call failed for region=%s: %s — using original message",
            region, exc,
        )
        return message, None


def localize_description(
    description: str,
    region: str,
    api_key: str,
    brief_language: str | None = None,
    model: str = DEFAULT_TEXT_MODEL,
) -> tuple[str, str | None]:
    """Translate a product description to the language of the target region.

    Returns the original description unchanged for English-speaking regions,
    when the brief language matches the region's native language,
    for empty descriptions, or on API error.

    Args:
        description: The original product description.
        region: ISO 3166-1 alpha-2 region code (e.g. "IT", "FR", "US").
        api_key: Google AI API key.
        brief_language: Optional language specified in the brief.
        model: Gemini text model to use.

    Returns:
        Tuple of (translated_description, target_language).
        If no translation occurred, target_language is None.
    """
    if not description:
        return description, None

    language = _resolve_language(region, brief_language)
    if language is None:
        return description, None

    log.info("Localizing product description for region=%s (%s)", region, language)

    prompt = (
        f"Translate the following product description to {language}. "
        f"Keep it concise and natural-sounding for marketing purposes. "
        f"Return only the translated text, nothing else.\n\n"
        f'"{description}"'
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(model=model, contents=prompt)
        translated = response.text.strip().strip("\"'")
        log.info("Localized description %r → %r (region=%s)", description, translated, region)
        return translated, language
    except Exception as exc:
        log.warning(
            "Description localization failed for region=%s: %s — using original",
            region, exc,
        )
        return description, None
