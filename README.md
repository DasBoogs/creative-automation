# Creative Automation Pipeline

A flexible Python-based tool for loading, validating, localizing, and generating campaign creatives from structured briefs. Campaign inputs and outputs are uploaded to Dropbox, and image/text generation is powered by Google Gemini.

## Features

- 📝 Load campaign briefs from YAML or JSON files
- ✅ Validate campaign data with Pydantic models
- 🖼️ Automatically match product reference assets by normalized name (slug)
- 🎨 Generate missing reference assets with Google Gemini image models
- 🌐 Automatically localize campaign text for target regions
- ☁️ Automatically upload campaign inputs/outputs to Dropbox
- 🎯 Support for multiple products per campaign
- 📊 Multiple aspect ratios for creative generation

## Notable Assumptions

- Reference assets are images in png format
- Region uses country codes (This can be expanded for customizable market regions)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd creative-automation
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up required integrations in `.env`:
  - Copy `.env.example` to `.env`
  - Add your Google key as `GOOGLE_API_KEY`
  - Add your Dropbox token as `DROPBOX_ACCESS_TOKEN`
  - Optional: set `DROPBOX_APP_NAME` to change the Dropbox app root folder (default: `adobe-poc`)
  - The `.env` file will be automatically loaded when you run the tool
  - See [Google Integration](#google-integration), [Localization](#localization), and [Dropbox Integration](#dropbox-integration)

## Usage

**Note:** Non-validation runs require both `GOOGLE_API_KEY` and `DROPBOX_ACCESS_TOKEN`. Credentials are loaded from `.env` automatically.

### Basic Usage

Load and upload a campaign brief with reference assets:
```bash
python load_brief.py briefs/example.yaml --assets-folder briefs/assets
```

Asset files should be named to match product slugs (e.g., `ultra-shield-sunscreen-spf50.png`).

This will automatically:
- Load and validate the brief
- Match provided assets to products by slug (when `--assets-folder` is set)
- Generate missing product reference assets with Gemini (if needed), saved under `genoutput/runs/{timestamp}/`
- Upload `brief.yaml` and `brief.json` to `/{DROPBOX_APP_NAME}/inputs/cli/{campaign_name}/`
- Upload each product's reference asset to `/{DROPBOX_APP_NAME}/inputs/cli/{campaign_name}/{product_slug}/`
- Localize campaign message and product descriptions for the target region
- Generate creatives for each product × aspect ratio using Gemini image generation
- Upload generated creatives to `/{DROPBOX_APP_NAME}/outputs/cli/{campaign_slug}/{run_id}/...`
- Write `report.json` with output URLs, timings, and localization details

### Run Artifacts

After each run completes, artifacts are saved locally in `genoutput/runs/{run_id}/`:

**For asset generation runs** (when missing product assets are generated):
- `brief.yaml` - Campaign brief in YAML format
- `brief.json` - Campaign brief in JSON format
- `{product-slug}.png` - Generated product reference images
- `SUMMARY.md` - Markdown summary with campaign info, products, and generation results

**For campaign generation runs** (full pipeline execution):
- `SUMMARY.md` - Comprehensive markdown log including:
  - Campaign information and settings
  - Product details with reference assets
  - Localization details (original and translated text)
  - Generated creatives with timing and Dropbox URLs
  - Complete pipeline execution log

💡 **Tip:** The `SUMMARY.md` file provides a human-readable record of each run, making it easy to track what was generated and review localization changes.

### Validation Only

Validate a brief without uploading:
```bash
python load_brief.py briefs/example.yaml --validate-only
```

### JSON Output

Output the brief as JSON (also uploads):
```bash
python load_brief.py briefs/example.yaml --json
```

## Campaign Brief Format

Campaign briefs can be written in YAML or JSON format. Here's an example:

```yaml
campaign_name: Summer Essentials
region: US
audience: Active outdoor enthusiasts aged 25-45
message: "Gear up for the perfect summer adventure"
aspect_ratios:
  - "1:1"
  - "9:16"
  - "16:9"
products:
  - name: UltraShield Sunscreen SPF50
    description: >
      Lightweight, water-resistant mineral sunscreen with SPF 50.
      Reef-safe formula ideal for outdoor sports.
  - name: AquaGlide Beach Towel
    description: >
      Ultra-absorbent microfiber beach towel with quick-dry technology.
      Available in vibrant summer colors.
```

### Required Fields

- `campaign_name`: Name of the campaign
- `products`: List of at least 2 products, each with:
  - `name`: Product name
  - `description`: Product description
- `region`: Target region
- `audience`: Target audience description
- `message`: Campaign message

### Legal Safety Validation

Brief validation also performs a legal-safety phrase check on:

- Campaign `message`
- Each product `description`

The check blocks prohibited marketing language (50 case-insensitive phrases), including examples like:

- `free money`
- `guaranteed`
- `100% safe`

If any prohibited phrase is found, loading fails with a user-friendly legal-safety message, remediation guidance, and detailed field-level matches.

### Optional Fields

- `aspect_ratios`: List of aspect ratios (default: `["1:1", "9:16", "16:9"]`)
- `language`: Language of the brief text (defaults to `"English"` when omitted)
- Product `slug`: Auto-generated from name if not provided
- Product `reference_asset`: Path to reference image (set by `--assets-folder`)

## Localization

For full localization behavior, language rules (including default-to-English when `language` is omitted), examples, supported regions/languages, and report format, see:

- `LOCALIZATION.md`
- `LOCALIZATION_QUICKSTART.md`

## Google Integration

### Setup (Required for generation/localization)

Add the following to your `.env`:

- `GOOGLE_API_KEY`: Required for asset generation, campaign creative generation, and localization
- `GEMINI_MODEL` (optional): Image model override (default: `gemini-2.5-flash-image`)

### What Google powers in this pipeline

- Generates missing product reference assets
- Generates final campaign creatives from prompt + reference image
- Localizes campaign message and product descriptions for non-English target regions

## Dropbox Integration

### Setup (Required)

The tool automatically loads Dropbox credentials from your `.env` file.

1. **Get a Dropbox Access Token**:
   - Go to [Dropbox App Console](https://www.dropbox.com/developers/apps)
   - Create a new app or select an existing one
   - Generate an access token
   - Copy `.env.example` to `.env` and add your token as `DROPBOX_ACCESS_TOKEN`

2. **Optional: Enable Token Refresh** (recommended for production):
   - Set up OAuth 2.0 with refresh token
   - Add these to your `.env`:
     - `DROPBOX_REFRESH_TOKEN`
     - `DROPBOX_APP_KEY`
     - `DROPBOX_APP_SECRET`

3. **Optional: Configure app root folder name**:
  - Set `DROPBOX_APP_NAME` in `.env`
  - Default is `adobe-poc`
  - This controls the top-level Dropbox path prefix for both inputs and outputs

### Upload Structure

When you run the tool, campaign files are automatically organized as:

```
/{DROPBOX_APP_NAME}/inputs/cli/
  └── {campaign_name}/
      ├── brief.yaml
      ├── brief.json
      ├── {product_slug_1}/
      │   └── {asset_filename}
      ├── {product_slug_2}/
      │   └── {asset_filename}
      └── ...
```

Example:
```
/adobe-poc/inputs/cli/
  └── Summer Essentials/
      ├── brief.yaml
      ├── brief.json
      ├── ultrashield-sunscreen-spf50/
      │   └── ultrashield-sunscreen-spf50.png
      ├── aquaglide-beach-towel/
      │   └── aquaglide-beach-towel.jpg
      └── hydroflow-water-bottle/
          └── hydroflow-water-bottle.png
```

Generated outputs are uploaded to:

```
/{DROPBOX_APP_NAME}/outputs/cli/{campaign_slug}/{run_id}/
  ├── {product_slug}/
  │   └── {aspect_ratio}_{timestamp}.png
  └── report.json
```

## Project Structure

```
creative-automation/
├── load_brief.py              # CLI entry point
├── requirements.txt           # Python dependencies
├── .env.example              # Environment variables template
├── briefs/                   # Campaign brief files
│   ├── example.yaml
│   └── assets/              # Product reference images
├── genoutput/                # Local run artifacts
│   └── runs/
│       └── {run_id}/         # Each run's output
│           ├── SUMMARY.md    # Markdown summary log
│           ├── brief.yaml    # Campaign brief (YAML)
│           ├── brief.json    # Campaign brief (JSON)
│           └── *.png         # Generated assets
├── src/
│   ├── brief_loader.py      # Brief loading logic
│   ├── models.py            # Pydantic models
│   └── pipeline/
│       ├── asset_generator.py   # Product asset generation
│       ├── campaign_generator.py # Campaign creative generation
│       ├── dropbox_client.py    # Dropbox SDK wrapper
│       ├── dropbox_uploader.py  # Campaign upload logic
│       ├── imagen_client.py     # Google Imagen integration
│       ├── localizer.py         # Text localization
│       ├── prompt_builder.py    # Prompt generation
│       └── summary_logger.py    # Run summary logging
└── tests/
    ├── test_brief_loader.py     # Unit tests
    ├── test_campaign_generator.py
    ├── test_asset_generator.py
    ├── test_summary_logger.py   # Summary log tests

    ## Known Limitations

    ### Legal Safety Validation

    - **English-only validation**: Prohibited phrase checking currently runs only on the original English brief text. Localized translations generated by Gemini are **not re-validated** for legal safety compliance. Enhanced multilingual validation is planned for a future release.

    ### Dropbox Integration

    - **Temporary link expiration**: Dropbox temporary download links expire after 4 hours. If you need persistent links, consider using shared links or permanent storage.

    ### Campaign Generation

    - **Reference assets required**: All products must have reference assets (matched from `--assets-folder` or generated via Imagen) before campaign creative generation can proceed. There is no fallback for missing references.

    - **Best-effort generation**: The pipeline uses best-effort semantics—if one product or aspect ratio fails during generation, the run continues and completes with partial results. Failed generations are logged but do not abort the entire campaign.

    - **Path normalization**: Campaign names containing special characters (e.g., `Campaign: 2026!`) are normalized to filesystem-safe slugs (e.g., `campaign-2026`). This may cause path collisions if multiple campaigns differ only in special characters.

    ### Localization

    - **AI-generated translations**: Localized text is generated by Gemini and may occasionally produce unexpected phrasings or fail to preserve marketing tone. Always review localized content before use in production campaigns.

    - **Limited region coverage**: Only regions defined in `src/pipeline/localizer.py` have explicit language mappings. Unlisted regions default to English or skip localization.
    └── ...
```



