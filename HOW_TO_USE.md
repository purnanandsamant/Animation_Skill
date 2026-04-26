# How to Use the Story-to-Animation Pipeline

## What This Is

A 6-step AI pipeline that turns a one-sentence story idea into a fully produced
animated video with YouTube-ready publishing assets. You talk to Claude, Claude
guides you through each step, and you approve everything before moving forward.

## One-Time Setup

### 1. Get a Replicate API Token

- Go to https://replicate.com/account/api-tokens
- Create an account (free tier available, pay-per-use after)
- Copy your API token

### 2. Install Requirements

```bash
# Python dependency
pip install requests

# FFmpeg (needed for merging clips and extracting Shorts)
# Windows:
winget install ffmpeg
# Mac:
brew install ffmpeg
# Linux:
sudo apt install ffmpeg
```

### 3. Create Your Project Folder

Create a new folder for each animation project:

```
C:\Users\YourName\Animations\MyFirstVideo\
```

### 4. Create a .env File

Inside your project folder, create a file called `.env`:

```
REPLICATE_API_TOKEN=your_actual_token_here
```

This single key powers the entire pipeline. Never share it or commit it to git.

> If you forget this step, the scripts auto-create a template `.env` on first
> run and remind you to fill it in.

---

## The 6-Step Pipeline

Open Claude Code from your project folder:

```bash
cd C:\Users\YourName\Animations\MyFirstVideo
claude
```

Then follow the steps below. Each step ends with a review gate — Claude always
waits for your explicit approval before moving on.

---

### Step 1 — Give Claude Your Story Idea

**What you say:**

> "A tiny robot finds a glowing seed in a junkyard and plants it, bringing
> color back to a grey world."

**What Claude does:**
- Expands your idea into an 8-15 scene screenplay
- Adds scene locations, characters, dialogue, camera directions, and tone
- Saves as `story.md`

**What you review:**
- Does the story flow well?
- Are the characters interesting?
- Is the pacing right for a 2-4 minute animation?

**To proceed:** Say "approved" or "looks good"
**To change:** Describe what to modify — Claude rewrites and asks again

---

### Step 2 — Extract Characters and Backgrounds

**What you say:**

> "Extract the characters and backgrounds"

**What Claude does:**
- Reads `story.md`
- Identifies every unique character and location
- Writes detailed Pixar-style image-generation prompts for each
- Saves as `characters.json` and `backgrounds.json`

**What you review:**
- Are all characters captured?
- Are the visual descriptions accurate (hair color, clothing, etc.)?
- Are all unique locations identified?

**To proceed:** Say "approved"
**To change:** e.g., "Make Luna's hair red instead of brown"

---

### Step 3 — Generate Reference Images

**What you say:**

> "Generate the images"

**What Claude tells you to run:**

```bash
python ~/.claude/skills/generating-character-and-background-images/scripts/generate_images.py
```

**What the script does:**
- Generates character images (1:1 square, reference sheet style)
- Generates background images (16:9 cinematic wide shots)
- Uploads each to Replicate Files API for permanent hosting
- Writes `image_url` back into the JSON files

**Optional:** Choose a different model:
```bash
python ~/.claude/skills/generating-character-and-background-images/scripts/generate_images.py --model black-forest-labs/flux-schnell
```

**What you review:**
- Do the characters look right?
- Do the backgrounds match the story locations?
- Is the art style consistent?

**To redo a specific image:** Update the prompt in the JSON, delete the PNG,
re-run the script (it skips existing files).

---

### Step 4 — Create the Shot List

**What you say:**

> "Create the shot list"

**What Claude does:**
- Reads `story.md`, `characters.json`, `backgrounds.json`
- Breaks each scene into 1-3 shots of 8 seconds each
- Assigns character IDs and background IDs to each shot
- Writes a self-contained video-generation prompt (veo_prompt) for each shot
- Saves as `shots.json`

**What you review:**
- Does each shot's action match the story?
- Are the veo_prompts descriptive enough?
- Is the pacing right (number of shots per scene)?

**To proceed:** Say "approved"
**To change:** e.g., "Add a close-up of Luna's face after shot_003"

---

### Step 5 — Generate Video Clips and Merge

**What you say:**

> "Generate the videos"

**Per-shot mode (recommended):**
```bash
python ~/.claude/skills/generating-composite-and-video/scripts/generate_videos.py --shot shot_001
# Review, then:
python ~/.claude/skills/generating-composite-and-video/scripts/generate_videos.py --shot shot_002
# ... etc.
```

**Bulk mode (all at once):**
```bash
python ~/.claude/skills/generating-composite-and-video/scripts/generate_videos.py
```

**What the script does:**
1. Phase 1 — Generates composite scene images (character + background blended)
2. Phase 2 — Animates each composite into an 8-second video clip
3. Both phases run in parallel — total time is roughly one job, not N jobs

**After approving all clips, merge:**
```bash
python ~/.claude/skills/generating-composite-and-video/scripts/merge_clips.py
```

Output: `./final_animation.mp4`

**Optional:** Choose different models:
```bash
python ~/.claude/skills/generating-composite-and-video/scripts/generate_videos.py \
  --image-model google/imagen-4-ultra \
  --video-model kwaivgi/kling-v2.5-turbo-pro
```

---

### Step 6 — YouTube Publishing Package

**What you say:**

> "Prepare for YouTube" or "Create the publishing package"

**What Claude does (Phase 1 — metadata):**
- Generates `publish.md` with:
  - 5 SEO-optimized title options
  - Full YouTube description with timestamps
  - 30+ tags ready to paste into YouTube Studio
  - Hashtags (3 above-title + 5 in-description)
  - Shorts strategy (which clips to extract)
  - Posting schedule and community post text
- Generates `thumbnail_brief.json` (thumbnail prompt)
- Generates `shorts_plan.json` (Short clip ranges)

**Phase 2 — thumbnail:**
```bash
python ~/.claude/skills/youtube-publish-package/scripts/generate_thumbnail.py
```
Then add text overlay in Canva (free) or similar tool.

**Phase 3 — Shorts clips:**
```bash
python ~/.claude/skills/youtube-publish-package/scripts/extract_shorts.py
```
Extracts vertical 9:16 clips to `./shorts/`.

---

## Quick Reference Card

| Step | What You Say | Output Files |
|------|-------------|--------------|
| 1 | Your story idea | `story.md` |
| 2 | "Extract characters and backgrounds" | `characters.json`, `backgrounds.json` |
| 3 | "Generate images" (run script) | `./characters/*.png`, `./backgrounds/*.png` |
| 4 | "Create the shot list" | `shots.json` |
| 5 | "Generate videos" (run script) | `./composites/`, `./clips/`, `final_animation.mp4` |
| 6 | "Prepare for YouTube" (run scripts) | `publish.md`, `thumbnail.png`, `./shorts/` |

## Approval Keywords

Any of these move to the next step:
`approved`, `approve`, `looks good`, `proceed`, `next step`, `go ahead`,
`continue`, `LGTM`, `ship it`, `all good`, `move on`, `next`

## Available AI Models

### Image Generation (Step 3)

| Model | Best For |
|-------|---------|
| `black-forest-labs/flux-1.1-pro` | High quality (default) |
| `black-forest-labs/flux-schnell` | Speed |
| `black-forest-labs/flux-1.1-pro-ultra` | Maximum fidelity |
| `stability-ai/stable-diffusion-3.5-large` | Alternative style |
| `ideogram-ai/ideogram-v2` | Text rendering |

### Composite Generation (Step 5, Phase 1)

| Model | Best For |
|-------|---------|
| `black-forest-labs/flux-2-flex` | Multi-reference, max quality (default) |
| `black-forest-labs/flux-2-pro` | Multi-reference, high quality |
| `google/imagen-4-ultra` | Highest quality |
| `google/nano-banana-pro` | State of the art |
| `bytedance/seedream-4.5` | Spatial understanding |

### Video Generation (Step 5, Phase 2)

| Model | Best For |
|-------|---------|
| `prunaai/p-video` | Fast generation (default) |
| `kwaivgi/kling-v2.5-turbo-pro` | Consistent motion, high quality |

Any valid Replicate model ID works via command-line flags.

## Project Folder After a Full Run

```
MyFirstVideo/
├── .env                      # Your API key (never share)
├── story.md                  # The screenplay
├── characters.json           # Character prompts + image_urls
├── backgrounds.json          # Background prompts + image_urls
├── shots.json                # Shot-by-shot breakdown
├── thumbnail_brief.json      # Thumbnail generation prompt
├── shorts_plan.json          # Shorts extraction plan
├── publish.md                # YouTube metadata (titles, tags, etc.)
├── characters/               # Character reference PNGs
├── backgrounds/              # Background reference PNGs
├── composites/               # Blended scene images
├── clips/                    # Individual 8-sec video clips
├── shorts/                   # Vertical 9:16 Shorts clips
├── thumbnail.png             # YouTube thumbnail
└── final_animation.mp4       # The finished video
```

## Tips

- **Start small.** Your first video will take longer as you learn the flow.
  By video 3-4 you will move through the pipeline quickly.
- **Reuse characters.** Copy `characters.json` and `./characters/` PNGs to
  new projects for a recurring character series. Consistency builds subscribers.
- **Edit prompts directly.** The JSON files are plain text — you can tweak any
  prompt and re-run just that step.
- **Per-shot mode is your friend.** In Step 5, approving each shot individually
  catches bad clips early and saves money on re-runs.
