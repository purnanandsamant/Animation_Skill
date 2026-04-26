---
name: generating-character-and-background-images
description: >
  Reads characters.json and backgrounds.json, then generates reference images
  for each character and background using the Replicate API (text-to-image).
  Character images (1:1 aspect ratio) are saved to ./characters/ and background
  images (16:9) to ./backgrounds/, named by their IDs (char_001.png, bg_001.png,
  etc.). Each image is then uploaded to the Replicate Files API for permanent
  public hosting, and the URL is written back as an image_url field in both JSON
  files — these URLs are required by generate_videos.py. Only needs
  REPLICATE_API_TOKEN in .env. Part of the Story-to-Animation pipeline
  (Step 3 of 5). Run scripts/generate_images.py to execute. Use when both JSON
  prompt files exist and the user wants to generate the actual reference images.
  After generating all images, ALWAYS present the output and wait for explicit
  user approval. Do NOT automatically trigger the next pipeline step.
---

# Character & Background Image Generation

Generate reference images with a Replicate text-to-image model, host them via
the Replicate Files API, and write permanent `image_url` fields back into the
JSON files.

## Setup: .env

On first run the script automatically creates a `.env` template in your project
directory and exits. Open it, fill in your key, then re-run:

```
REPLICATE_API_TOKEN=your_replicate_api_token_here
```

- **REPLICATE_API_TOKEN** — from https://replicate.com/account/api-tokens
- Add `.env` to `.gitignore` — never commit API keys
- Real environment variables always take precedence over `.env` values

## Prerequisites

- `characters.json` and `backgrounds.json` must exist (from Skill 2)
- `.env` in project directory with `REPLICATE_API_TOKEN` filled in (auto-created on first run)
- `pip install requests`

## Running the Script

```bash
cd /path/to/your/project
python ~/.claude/skills/generating-character-and-background-images/scripts/generate_images.py

# Choose a specific model
python ~/.claude/skills/generating-character-and-background-images/scripts/generate_images.py --model black-forest-labs/flux-schnell

# List available models
python ~/.claude/skills/generating-character-and-background-images/scripts/generate_images.py --list-models
```

### What the script does per image:

1. **Generate** — POST to `/v1/predictions` (default model: `flux-1.1-pro`, with aspect_ratio)
2. **Poll** — GET `/v1/predictions/{id}` until `status: succeeded`; extract output URL
3. **Download** — save PNG to `./characters/{id}.png` or `./backgrounds/{id}.png`
4. **Upload** — POST PNG to Replicate Files API (`/v1/files`); get permanent URL
5. **Write back** — store permanent URL as `image_url` in `characters.json` / `backgrounds.json`

Character images: **1:1** aspect ratio (reference sheets)
Background images: **16:9** aspect ratio (cinematic wide shots)

If the Files API upload fails, the original Replicate output URL is used as a fallback.

## Supported Models (default: `black-forest-labs/flux-1.1-pro`)

| Model ID | Description |
|----------|-------------|
| `black-forest-labs/flux-1.1-pro` | FLUX 1.1 Pro — high quality (default) |
| `black-forest-labs/flux-schnell` | FLUX Schnell — fast, good quality |
| `black-forest-labs/flux-1.1-pro-ultra` | FLUX 1.1 Pro Ultra — highest fidelity |
| `stability-ai/stable-diffusion-3.5-large` | Stable Diffusion 3.5 Large |
| `ideogram-ai/ideogram-v2` | Ideogram v2 — excellent rendering |

Any valid Replicate text-to-image model ID works via `--model`.

## Regenerating Specific Images

1. Update the `prompt` field in the JSON
2. Delete the existing PNG (e.g., `./characters/char_001.png`)
3. Re-run the script — it skips existing files, regenerates deleted ones

## Important: image_url Fields

After running, each JSON entry has an `image_url` field containing a permanent
Replicate Files URL. **Skill 5 (`generate_videos.py`) reads these URLs** to
generate composite images — do not delete or overwrite them.

## Review Gate (MANDATORY)

After all images are generated, present this EXACTLY:

```
✅ Image Generation complete.

📋 Summary:
- Character images: [X] generated → ./characters/
  [char_001.png: "Name", char_002.png: "Name", ...]
- Background images: [X] generated → ./backgrounds/
  [bg_001.png: "Name", bg_002.png: "Name", ...]
- Failed: [X] (list any failures)
- image_url (Replicate Files) written to: characters.json, backgrounds.json

👉 Please review the generated images. You can:
  - Approve all → say "approved" or "proceed"
  - Reject specific images → e.g., "regenerate char_001, the hair is wrong"
    (update prompt in characters.json, delete the PNG, re-run script)
  - Replace images manually → save your PNG as ./characters/char_001.png,
    then re-run the script to regenerate + re-upload

⏸️ Waiting for your approval before creating the shot list.
```

**NEVER** proceed to the next skill automatically. Wait for explicit approval.
