# Localization Integration Summary

## Overview

The creative automation pipeline now includes automatic localization for campaign messages and product descriptions. The system intelligently translates text content based on the target region and the language of the brief.

This document is the canonical localization reference. The main `README.md` now includes only a short pointer here to keep it compact.

## What Was Added

### 1. New Module: `src/pipeline/localizer.py`
A complete localization module that:
- Detects the native language of 30+ regions worldwide
- Only translates when the brief language differs from the region's native language
- Uses Gemini AI for high-quality, context-aware translations
- Falls back gracefully to original text if translation fails
- Logs all localization decisions and outcomes

### 2. Model Updates: `src/models.py`
- Added optional `language` field to `CampaignBrief` model (e.g., "English", "Spanish")
- Maintains backward compatibility with existing briefs

### 3. Campaign Generator Integration: `src/pipeline/campaign_generator.py`
- New `localize_brief()` method that:
  - Localizes campaign message
  - Localizes all product descriptions
  - Tracks what was translated and to which language
  - Returns a localized copy of the brief
- Updated `generate_campaign_assets()` to:
  - Run localization as Stage 0 (before generation)
  - Use localized text for all creative generation
  - Include localization details in reports
  - Display localization summary in console output

### 4. Report Enhancements
Campaign reports now include detailed localization information:
```json
{
  "localization": {
    "target_language": "Italian",
    "message_translated": true,
    "original_message": "Original text",
    "localized_message": "Translated text",
    "products": {
      "product-slug": {
        "translated": true,
        "original": "Original description",
        "localized": "Translated description",
        "language": "Italian"
      }
    }
  }
}
```

### 5. Updated UI: `load_brief.py`
- Display function now shows the language field when present
- Helps users understand what language their brief is in

### 6. Test Suite: `tests/test_localizer.py`
Comprehensive unit tests covering:
- Language resolution logic
- Message localization
- Description localization
- Error handling and fallbacks
- Edge cases (empty descriptions, matching languages, etc.)

### 7. Example Briefs
Three new example briefs to demonstrate localization:
- `briefs/example_italy.yaml` - English brief for Italian market (will translate)
- `briefs/example_france.yaml` - French brief for French market (no translation)
- `briefs/example_germany.yaml` - English brief for German market (will translate)

### 8. Documentation: `README.md`
Added comprehensive localization section covering:
- How localization works
- When translation occurs
- Supported languages
- Usage examples
- Report format

## How It Works

### Translation Logic

1. **Determine Target Language**
   - If region is English-speaking (US, UK, AU, etc.) and no `language` field → No translation
   - If region is English-speaking but `language` field specifies non-English → Translate to that language
   - If region is non-English and `language` matches region's native language → No translation
   - If region is non-English and `language` differs (or is unspecified) → Translate to region's native language

2. **Translate Content**
   - Campaign message: Short, punchy marketing slogan translation
   - Product descriptions: Natural, marketing-focused translation
   - Uses Gemini AI with context-specific prompts
   - Strips quotes and extra whitespace from responses

3. **Track Results**
   - Records whether translation occurred
   - Stores both original and translated text
   - Notes the target language
   - Includes all details in the final report

### Console Output Example

When running a campaign with localization:

```
🎬 Generating ad creatives for Italian Summer Campaign
Run ID: 20260307_123456
Region: IT

🌐 Localizing campaign content...
  ✓ Campaign message localized to Italian
  ✓ UltraShield Sunscreen SPF50 description localized
  ✓ AquaGlide Beach Towel description localized
  ✓ HydroFlow Water Bottle description localized
  ℹ No message translation needed  # (if already in target language)

📦 UltraShield Sunscreen SPF50
  ✓ 1:1 generated in 3.2s
  ✓ 9:16 generated in 3.5s
  ✓ 16:9 generated in 3.4s

...

📝 Localization Summary:
  Target Language: Italian
  Original Message: Gear up for the perfect summer adventure
  Localized Message: Preparati per l'avventura estiva perfetta
  Translated Products: ultrashield-sunscreen-spf50, aquaglide-beach-towel, hydroflow-water-bottle

✓ Campaign generation complete!
```

## Supported Regions and Languages

### English-Speaking Regions (No Translation by Default)
US, UK, AU, CA, NZ, IE, ZA, SG

### Supported Translation Languages
- **European**: Italian, French, German, Spanish, Portuguese (European), Portuguese (Brazilian), Dutch, Polish, Swedish, Norwegian, Danish, Finnish, Greek, Turkish, Czech, Slovak, Croatian, Hungarian, Romanian, Ukrainian
- **Asian**: Japanese, Korean, Chinese (Simplified), Chinese (Traditional), Thai, Vietnamese, Indonesian, Hindi, Hebrew
- **Middle Eastern**: Arabic
- **Latin American**: Spanish (Latin American)

## Usage Examples

### Example 1: English Brief for Non-English Region
```yaml
campaign_name: Italian Summer Campaign
region: IT
language: English
message: "Gear up for the perfect summer adventure"
products:
  - name: Sunscreen SPF50
    description: "Lightweight, water-resistant sunscreen"
  - name: Beach Towel
    description: "Quick-dry microfiber towel"
```

**Result**: Message and descriptions will be translated to Italian.

### Example 2: Brief Already in Target Language
```yaml
campaign_name: Campagne Été Française
region: FR
language: French
message: "Préparez-vous pour l'aventure estivale parfaite"
products:
  - name: Crème Solaire
    description: "Crème solaire légère et résistante à l'eau"
```

**Result**: No translation (brief is already in French for French market).

### Example 3: No Language Specified
```yaml
campaign_name: German Campaign
region: DE
message: "Gear up for the perfect summer adventure"
# language not specified, assumes English
```

**Result**: Will translate to German (assumes English source).

## Integration Points

The localization system integrates at these key points:

1. **Campaign Generation Pipeline** (`generate_campaign_assets`)
   - Stage 0: Localization (new)
   - Stage 1: Verify reference assets
   - Stage 2-3: Generate creatives (uses localized text)
   - Stage 4: Write report (includes localization details)

2. **Prompt Building** (`prompt_builder.py`)
   - Automatically uses localized message and descriptions
   - No changes needed - works with localized brief transparently

3. **Reporting** (`_write_report` and return values)
   - All localization details included in JSON reports
   - Console output shows localization summary

## Error Handling

The localization system is designed to be robust:

- **API Failures**: Falls back to original text, logs warning
- **Empty Descriptions**: Skips translation, returns empty string
- **Unknown Regions**: No translation, uses original text
- **Missing Language Field**: Assumes English source for non-English regions

All error cases ensure the pipeline continues without interruption.

## Testing

Run the localization tests:
```bash
pytest tests/test_localizer.py -v
```

Test with example briefs:
```bash
# Italian market (will translate from English)
python load_brief.py briefs/example_italy.yaml --assets-folder briefs/assets

# French market (no translation, already in French)
python load_brief.py briefs/example_france.yaml --assets-folder briefs/assets

# German market (will translate from English)
python load_brief.py briefs/example_germany.yaml --assets-folder briefs/assets
```

## Performance Impact

- **Localization Stage**: ~1-3 seconds per campaign (1 message + N product descriptions)
- **Runs serially**: Each API call completes before the next
- **Optional**: Localization only occurs when needed (region/language mismatch)
- **Cached in brief**: Localized text is used for all subsequent creative generations

## Future Enhancements

Potential improvements for the localization system:

1. **Parallel Translation**: Translate message and all descriptions concurrently
2. **Caching**: Cache translations to avoid re-translating identical text
3. **Custom Prompts**: Allow users to provide translation guidelines in the brief
4. **Validation**: Option to have humans review translations before generation
5. **Multi-Language Campaigns**: Generate creatives in multiple languages simultaneously
6. **Locale-Specific Formatting**: Handle region-specific number, date, currency formats

## Backward Compatibility

All changes are backward compatible:
- Existing briefs without `language` field work as before
- English-speaking regions see no change in behavior
- Localization is transparent to downstream systems
- Reports include localization field (empty if no translation occurred)

## Dependencies

The localization feature requires:
- `google-genai>=0.1.0` (already in requirements.txt)
- Valid `GOOGLE_API_KEY` environment variable
- Internet connection for Gemini API calls

No additional dependencies were added.
