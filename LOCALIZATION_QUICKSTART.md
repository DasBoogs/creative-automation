# Localization Quick Start Guide

## Basic Usage

### 1. English Brief for Non-English Market

Create a brief with English text for a non-English region:

```yaml
campaign_name: Italian Summer Campaign
region: IT
language: English  # Specify that brief is in English
audience: Active outdoor enthusiasts aged 25-45
message: "Gear up for the perfect summer adventure"
products:
  - name: Sunscreen SPF50
    description: "Lightweight, water-resistant mineral sunscreen"
  - name: Beach Towel  
    description: "Quick-dry microfiber beach towel"
```

Run the campaign:
```bash
python load_brief.py briefs/my_italian_campaign.yaml --assets-folder briefs/assets
```

**What happens:**
- ✅ Campaign message translates to Italian
- ✅ Product descriptions translate to Italian
- ✅ Creatives are generated with Italian text
- ✅ Report includes both original and translated text

### 2. Brief Already in Target Language

Create a brief that's already in the target language:

```yaml
campaign_name: Campagne Été Française
region: FR
language: French  # Brief is already in French
audience: Passionnés d'activités de plein air
message: "Préparez-vous pour l'aventure estivale parfaite"
products:
  - name: Crème Solaire
    description: "Crème solaire légère et résistante à l'eau"
```

Run the campaign:
```bash
python load_brief.py briefs/my_french_campaign.yaml --assets-folder briefs/assets
```

**What happens:**
- ℹ️ No translation needed (brief matches region language)
- ✅ Creatives generated with original French text
- ✅ Report notes no translation occurred

### 3. English Brief for English Market

Standard US/UK campaign in English:

```yaml
campaign_name: Summer Essentials
region: US
audience: Active outdoor enthusiasts aged 25-45
message: "Gear up for the perfect summer adventure"
# language field optional for English regions
products:
  - name: Sunscreen SPF50
    description: "Lightweight, water-resistant mineral sunscreen"
```

**What happens:**
- ℹ️ No translation needed (English region)
- ✅ Creatives generated with original text
- ✅ Works exactly as before (backward compatible)

## Console Output Examples

### With Translation:
```
🎬 Generating ad creatives for Italian Summer Campaign
Run ID: 20260307_123456
Region: IT

🌐 Localizing campaign content...
  ✓ Campaign message localized to Italian
  ✓ Sunscreen SPF50 description localized
  ✓ Beach Towel description localized

📦 Sunscreen SPF50
  ✓ 1:1 generated in 3.2s
  ...

📝 Localization Summary:
  Target Language: Italian
  Original Message: Gear up for the perfect summer adventure
  Localized Message: Preparati per l'avventura estiva perfetta
  Translated Products: sunscreen-spf50, beach-towel
```

### Without Translation:
```
🎬 Generating ad creatives for Summer Essentials
Run ID: 20260307_123456
Region: US

🌐 Localizing campaign content...
  ℹ No message translation needed

📦 Sunscreen SPF50
  ✓ 1:1 generated in 3.2s
  ...
```

## Report Structure

The JSON report includes localization details:

```json
{
  "run_id": "20260307_123456",
  "campaign": "Italian Summer Campaign",
  "region": "IT",
  "timestamp": "2026-03-07T12:34:56",
  "localization": {
    "target_language": "Italian",
    "message_translated": true,
    "original_message": "Gear up for the perfect summer adventure",
    "localized_message": "Preparati per l'avventura estiva perfetta",
    "products": {
      "sunscreen-spf50": {
        "translated": true,
        "original": "Lightweight, water-resistant mineral sunscreen",
        "localized": "Crema solare minerale leggera e resistente all'acqua",
        "language": "Italian"
      },
      "beach-towel": {
        "translated": true,
        "original": "Quick-dry microfiber beach towel",
        "localized": "Asciugamano da spiaggia in microfibra ad asciugatura rapida",
        "language": "Italian"
      }
    }
  },
  "outputs": { ... },
  "timings": { ... }
}
```

## When Does Translation Occur?

| Brief Language | Region Type | Result |
|---------------|------------|--------|
| English | US, UK, AU, CA | ❌ No translation |
| English | IT, FR, DE, ES | ✅ Translates to region language |
| Not specified | US, UK | ❌ No translation (assumes English) |
| Not specified | IT, FR, DE | ✅ Translates to region language (assumes English brief) |
| Italian | IT | ❌ No translation (matches region) |
| French | FR | ❌ No translation (matches region) |
| Spanish | US | ✅ Translates to Spanish (explicit override) |

## Supported Regions

### English (No Translation)
US, UK, AU, CA, NZ, IE, ZA, SG

### European Languages
IT (Italian), FR (French), DE (German), ES (Spanish), PT (Portuguese), BR (Brazilian Portuguese), NL (Dutch), BE (Dutch), PL (Polish), SE (Swedish), NO (Norwegian), DK (Danish), FI (Finnish), GR (Greek), TR (Turkish), CZ (Czech), SK (Slovak), HR (Croatian), HU (Hungarian), RO (Romanian), UA (Ukrainian)

### Asian Languages  
JP (Japanese), KR (Korean), CN (Chinese Simplified), TW (Chinese Traditional), HK (Chinese Traditional), TH (Thai), VI/VN (Vietnamese), ID (Indonesian), IN (Hindi)

### Middle Eastern
AR (Arabic), HE/IL (Hebrew)

## Tips

1. **Always specify the `language` field** for clarity, especially for non-English briefs
2. **Check the console output** to see if translation occurred
3. **Review the report** for the complete localization details
4. **Test first** with `--validate-only` to check the brief is valid
5. **Use example briefs** as templates (see `briefs/example_*.yaml`)

## Environment Requirements

Make sure your `.env` file includes:
```
GOOGLE_API_KEY=your_google_api_key_here
DROPBOX_ACCESS_TOKEN=your_dropbox_token_here
```

The Google API key is used for both image generation AND text localization.

## Troubleshooting

### Translation not happening
- Check the `language` field matches your brief's actual language
- Verify `GOOGLE_API_KEY` is set in `.env`
- Look for warning messages in console output

### Translation failing
- Check internet connection (requires API access)
- Verify Google API key is valid
- System will fall back to original text on error

### Unexpected translations
- Review the `language` field - is it set correctly?
- Check console output for "No translation needed" vs "localized to..."
- Consult the decision table above

## Examples to Try

```bash
# English to Italian
python load_brief.py briefs/example_italy.yaml --assets-folder briefs/assets

# French (no translation)
python load_brief.py briefs/example_france.yaml --assets-folder briefs/assets

# English to German
python load_brief.py briefs/example_germany.yaml --assets-folder briefs/assets

# Original US example (no translation)
python load_brief.py briefs/example.yaml --assets-folder briefs/assets
```

## Next Steps

1. Review the full documentation in `LOCALIZATION.md`
2. Check the `README.md` for complete feature list
3. Run tests: `pytest tests/test_localizer.py -v`
4. Create your own multi-language campaigns!
