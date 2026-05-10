---
name: generating-composite-and-video
description: >
  Reads shots.json and processes each shot in two fully-parallel phases using
  the Replicate API: (1) generates composite scene images by blending character
  and background images (image_url fields) via a selectable Replicate image
  model, saving to ./composites/; (2) generates video clips from each composite
  via a selectable Replicate video model, saving to ./clips/. Both phases run
  concurrently — total time is the slowest single job, not the sum. After clips
  are approved, runs scripts/merge_clips.py (FFmpeg) to concatenate all clips
  using the timeline[] array into ./final_animation.mp4 with time-stretching.
  Only needs REPLICATE_API_TOKEN in .env. Part of the Story-to-Animation pipeline
  (Step 5 of 6). Use when shots.json exists and characters.json/backgrounds.json
  have image_url fields (populated by generate_images.py in Step 3). After
  generating and merging, ALWAYS present output and wait for explicit user approval.
---

# Composite Image + Video Generation -> Final Merge

Three phases: composite scene images -> video clips -> merged final animation.
Both generation phases use the **Replicate API** with user-selectable models.

All shots are processed concurrently — for 15 shots the total runtime is roughly
the time for one composite + one video, not 15x that.

## Setup: .env

Only `REPLICATE_API_TOKEN` is needed for this script:

```
REPLICATE_API_TOKEN=your_replicate_api_token_here
```

Get it from: https://replicate.com/account/api-tokens

If no `.env` is present, the script auto-creates a template and exits.

## Prerequisites

- `shots.json` must exist (from Skill 4) — with `shots[]` and `timeline[]` arrays
- `characters.json` and `backgrounds.json` must have `image_url` fields
  (permanent Replicate Files URLs set by `generate_images.py` in Step 3)
- `.env` in project directory with `REPLICATE_API_TOKEN`
- `pip install requests`
- FFmpeg installed and in PATH (for merge step)
  - Windows: `winget install ffmpeg`
  - Mac: `brew install ffmpeg`
  - Linux: `sudo apt install ffmpeg`

## API Endpoint

This script uses the correct Replicate endpoint:
```
POST /v1/models/{owner}/{name}/predictions
{ "input": { ... } }
```

Do NOT use `/v1/predictions` with a `model` field — that returns HTTP 422.

## Running the Script

### Selecting Models

Use `--image-model` and `--video-model` to choose Replicate models:

```bash
# Default models (google/nano-banana + kwaivgi/kling-v2.5-turbo-pro)
python ~/.claude/skills/generating-composite-and-video/scripts/generate_videos.py

# Choose specific models
python ~/.claude/skills/generating-composite-and-video/scripts/generate_videos.py \
  --image-model google/imagen-4-ultra --video-model kwaivgi/kling-v2.5-turbo-pro

# Enable start+end frame technique for transition shots
python ~/.claude/skills/generating-composite-and-video/scripts/generate_videos.py \
  --shot shot_005 --use-end-frame

# List all supported models
python ~/.claude/skills/generating-composite-and-video/scripts/generate_videos.py --list-models
```

### Per-shot mode (recommended — approve each clip before the next)

```bash
python ~/.claude/skills/generating-composite-and-video/scripts/generate_videos.py --shot shot_001
python ~/.claude/skills/generating-composite-and-video/scripts/generate_videos.py --shot shot_002
# ... etc.
```

### Bulk mode (generate all shots at once, approve at the end)

```bash
cd /path/to/your/project
python ~/.claude/skills/generating-composite-and-video/scripts/generate_videos.py
```

## What the Script Does

### Phase 1 — Composite images (parallel, Replicate image model)

All shots submitted simultaneously via the Replicate predictions API.

- Reference images = [background `image_url`, character `image_url`(s)] from JSON
- `prompt` = shot `action` + safety suffix (anatomy, no-floating, no-text rules auto-appended)
- Models that support multiple reference images (nano-banana, flux-2-flex, etc.)
  receive all image URLs; single-image models receive the background only
- Polls `GET /v1/predictions/{id}` until `status: succeeded`
- Downloads to `./composites/{shot_id}.png`
- **Uploads each composite to Replicate Files API** for permanent URL (required by Kling)

### Phase 2 — Video clips (parallel, Replicate video model)

All shots submitted simultaneously via the Replicate predictions API.

- `start_image` = permanent Replicate Files URL of the composite
- `prompt` = `veo_prompt` field + video anchor safety suffix (auto-appended)
- `negative_prompt` = anti-text, anti-floating, anti-morphing rules (auto-appended)
- For transition shots with `--use-end-frame`: extracts last frame of previous clip,
  uploads to Replicate Files, sends as `start_image` with composite as `end_image`
- Polls `GET /v1/predictions/{id}` until `status: succeeded`
- Downloads to `./clips/{shot_id}.mp4`

The script skips shots where `./clips/{shot_id}.mp4` already exists — safe to re-run.

### Phase 3 — Merge clips (FFmpeg)

After all clips are approved, run the merge script:

```bash
cd /path/to/your/project
python ~/.claude/skills/generating-composite-and-video/scripts/merge_clips.py

# With audio file for accurate last-segment duration
python ~/.claude/skills/generating-composite-and-video/scripts/merge_clips.py --audio audio.mp3
```

- Reads `timeline[]` from `shots.json` for playback order and timing
- Each segment duration = `timeline[i+1].start_s - timeline[i].start_s`
- Time-stretches each clip via `ffmpeg setpts` to fill its allocated slot
- Reused shot_ids (chorus/hook) use the same clip file — generated once, played many times
- Falls back to simple concatenation if no `timeline[]` array exists
- Output: `./final_animation.mp4`

## Safety Prompts (Applied Automatically)

The script automatically appends these rules — no manual action needed:

**Composite prompt suffix:**
```
Pixar-style 3D animation, cinematic 16:9 wide composition, warm golden-hour lighting,
high-detail render. STRICTLY ANATOMICALLY CORRECT: each character has exactly the correct
number of limbs. Every character is physically supported. ABSOLUTELY no text, no captions,
no watermarks, no logos anywhere in the image.
```

**Video negative prompt (sent with every job):**
```
text, captions, lyrics, subtitles, letters, words, numbers, watermark, logo, ui elements,
extra limbs, extra hands, deformed anatomy, blurry, low quality, floating character,
levitating, disappearing limbs, morphing bodies, characters merging, new characters appearing
```

**Video prompt anchor suffix:**
```
IMPORTANT: every character remains physically supported throughout the entire shot.
Anatomy stays consistent throughout — correct number of limbs and features at all times.
```

## Supported Image Models (Phase 1 — composites)

| Model ID | Description | Multi-ref |
|----------|-------------|-----------|
| `google/nano-banana` | Google Nano Banana — proven quality (default) | Yes |
| `google/imagen-4-ultra` | Google Imagen 4 Ultra — highest quality | Yes |
| `black-forest-labs/flux-2-flex` | FLUX.2 Flex — max-quality, 10 ref images | Yes |
| `black-forest-labs/flux-2-pro` | FLUX.2 Pro — high-quality, 8 ref images | Yes |
| `black-forest-labs/flux-2-max` | FLUX.2 Max — highest fidelity | Yes |
| `google/nano-banana-pro` | Google Nano Banana Pro — state of the art | Yes |
| `google/nano-banana-2` | Google Nano Banana 2 — fast, multi-image fusion | Yes |
| `bytedance/seedream-4.5` | ByteDance Seedream 4.5 — spatial understanding | No |
| `bytedance/seedream-5-lite` | ByteDance Seedream 5.0 Lite — reasoning + editing | No |
| `xai/grok-imagine-image` | xAI Grok Imagine — SOTA image model | No |

## Supported Video Models (Phase 2 — clips)

| Model ID | Description | End-image | Neg prompt |
|----------|-------------|-----------|------------|
| `kwaivgi/kling-v2.5-turbo-pro` | Kling v2.5 Turbo Pro (default) | Yes | Yes |
| `prunaai/p-video` | PrunaAI P-Video — fast generation | No | No |

Any valid Replicate model ID works via `--image-model` or `--video-model`.

## Start+End Frame Technique

For transition shots (character falls, jumps, changes position), use `--use-end-frame`:

```bash
python generate_videos.py --shot shot_012 --use-end-frame
```

This:
1. Extracts the last frame of the previous clip (e.g., `shot_011.mp4`)
2. Uploads it to Replicate Files API
3. Sends it as `start_image` with the current composite as `end_image`
4. Forces Kling to animate the transition between the two frames

Mark shots requiring this technique with `"transition_shot": true` in shots.json.

## Configurable Settings (top of script)

| Setting | Default | Description |
|---------|---------|-------------|
| `COMPOSITE_MAX_WORKERS` | `5` | Max parallel composite jobs |
| `VIDEO_MAX_WORKERS` | `5` | Max parallel video jobs |
| `POLL_INTERVAL` | `5` | Seconds between status polls |
| `MAX_POLLS` | `120` | Max polls per task (120 x 5s = 10 min timeout) |

## Regenerating Failed or Rejected Shots

1. Delete `./composites/{shot_id}.png` and `./clips/{shot_id}.mp4`
2. Optionally update `veo_prompt` in `shots.json`
3. Re-run the script (optionally with different `--image-model` or `--video-model`)

## Review Gates (MANDATORY)

### Gate 1 — Before any generation (shot-by-shot approval)

Present EACH shot for approval before submitting ANY composite jobs:

```
Shot [shot_001] — Section: [scene_title]
  Camera  : [camera_movement]
  Action  : [action]
  Prompt  : [veo_prompt]
  Duration: 8.0s
  Transition: [yes/no]

Approve / Edit / Skip?
```

Do NOT submit any composite jobs until all shots are approved.

### Gate 2 — After each composite, before video (per-shot mode)

After each `--shot` composite completes, present:

```
Composite ready: composites/shot_XXX.png
[show the image]

Approve (generate video) / Redo (regenerate composite) / Edit prompt?
```

Do NOT generate the video until the composite is explicitly approved.

### Gate 3 — After each video clip (per-shot mode)

After each `--shot` video completes, present:

```
Shot [shot_XXX] ready!

- Composite : ./composites/shot_XXX.png
- Video clip: ./clips/shot_XXX.mp4
- Image model: [model used]
- Video model: [model used]
- Run time  : [X min]

Please review this clip. You can:
  - Approve -> say "ok" or "next" to generate the next shot
  - Redo    -> say "redo" (deletes composite + clip, re-runs same shot)
  - Adjust  -> edit veo_prompt in shots.json, then say "redo"
  - Switch models -> say "redo with --image-model X --video-model Y"

Waiting for your approval before generating shot_[next].
```

Only run the next `--shot` after explicit user approval.

### Bulk mode — after ALL shots

```
Composite + Video Generation complete!

Summary:
- Composite images: [X] -> ./composites/
- Video clips: [X] -> ./clips/
- Image model: [model]
- Video model: [model]
- Failed: [X] (list any failures)
- Total run time: [X min]

Please review the clips. You can:
  - Approve all -> say "approved" or "merge" to proceed to final merge
  - Regenerate specific shots -> e.g., "redo shot_003"
    (delete composites/shot_003.png + clips/shot_003.mp4, re-run)

Waiting for your approval before merging.
```

### Phase 3 (merge) — after clips are approved

Run `merge_clips.py` and present:

```
Final animation ready!

- Output : ./final_animation.mp4
- Size   : [X] MB
- Segments: [X] merged (timeline mode / simple mode)
- Unique shots: [X] | Reused: [X] times

The Story-to-Animation pipeline is complete. Please review final_animation.mp4.
```

**NEVER** mark the pipeline as complete without explicit user approval of the final merged video.
