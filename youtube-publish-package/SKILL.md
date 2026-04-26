---
name: youtube-publish-package
description: >
  Generates a complete YouTube publishing package after the final animation is
  ready. Reads story.md, characters.json, backgrounds.json, and shots.json to
  produce: (1) publish.md with 5 SEO-optimized title options, full YouTube
  description with timestamps, 30+ tags, hashtags, Shorts strategy with
  recommended shot ranges, posting schedule, and community post text;
  (2) a YouTube-optimized thumbnail via Replicate (generate_thumbnail.py);
  (3) vertical 9:16 Shorts clips extracted from final_animation.mp4 via FFmpeg
  (extract_shorts.py). Only needs REPLICATE_API_TOKEN in .env. Part of the
  Story-to-Animation pipeline (Step 6 of 6, publishing step). Use when
  final_animation.mp4 exists and the user wants to prepare everything needed to
  upload to YouTube. After generating all assets, ALWAYS present the output and
  wait for explicit user approval. Do NOT upload anything automatically.
---

# YouTube Publish Package

Generate everything needed to publish the animation on YouTube with maximum
discoverability: metadata, thumbnail, and Shorts clips.

## Prerequisites

- `story.md`, `characters.json`, `backgrounds.json`, `shots.json` must exist
- `final_animation.mp4` must exist (from Step 5)
- `.env` in project directory with `REPLICATE_API_TOKEN`
- `pip install requests`
- FFmpeg installed and in PATH (for Shorts extraction)

## Phase 1 — Metadata (Claude generates directly)

Read all project files and generate `publish.md` with the following sections.

### Title Options (5 titles)

Generate 5 title options ranked by SEO potential. Follow these kids content
title patterns:

- Pattern A: `[Character] [Action/Adventure] | [Series/Topic] for Kids`
- Pattern B: `[Topic] Song/Story | Fun [Educational Topic] for Children`
- Pattern C: `[Emotion] [Character] [Does Something] | Kids Animation`

Rules:
- Max 60 characters (YouTube truncates longer titles on mobile)
- Front-load keywords (first 3 words matter most)
- Include "for Kids" or "for Children" in at least 3 options
- One option should be curiosity-driven (question or cliffhanger)
- No clickbait — title must honestly reflect the content

### YouTube Description

Write a full description with this structure:

```
[2-line hook — shown in search results, must grab attention and include keywords]

[1 paragraph story summary — natural keyword placement]

Timestamps:
0:00 — [Scene 1 title]
0:XX — [Scene 2 title]
...

Subscribe for new animations every week!

#hashtag1 #hashtag2 #hashtag3

---
[Series/Channel name] brings you fun animated stories for kids!
[brief channel description with keywords]
```

Timestamps must match actual shot boundaries from shots.json (cumulative 8-sec
segments mapped to scene titles).

### Tags (30+)

Generate 30-40 tags organized by type:

- **Broad** (5-8): kids animation, cartoon for kids, animated stories, etc.
- **Topic-specific** (8-12): based on story theme, educational content, genre
- **Character** (3-5): character names, character descriptions
- **Long-tail** (8-12): 3-5 word phrases people actually search
- **Competitor adjacency** (3-5): terms similar channels rank for

Format as a comma-separated list ready to paste into YouTube Studio.

### Hashtags

- 3 primary hashtags (shown above the title): `#KidsAnimation #[Topic] #[Character]`
- 5 secondary hashtags (in the description)
- Always include: `#ForKids` or `#KidsCartoon`

### Shorts Strategy

Analyze shots.json and recommend 3-4 Shorts clips:

For each recommended Short:
- Shot range (e.g., shots 3-6)
- Duration (must be under 60 seconds)
- Why this segment works as a standalone Short
- Suggested Short title (different from the main video title)
- Suggested caption/hook text

Prioritize segments with:
- High visual action or emotion
- A self-contained mini-arc (setup → payoff)
- The most visually striking composites

### Posting Schedule

- Best days/times for kids content (Saturday/Sunday 8-10 AM local)
- Recommend staggering Shorts: post 1 Short the day before the main video,
  1 Short same day, remaining Shorts over next 3-5 days
- Community post text to build anticipation (1-2 sentences + question to
  drive engagement)

### End Screen / Cards

- Suggest which previous video to link as end screen (or "first video" placeholder)
- Suggest a mid-roll card placement time (after a dramatic moment)

## Phase 2 — Thumbnail (Replicate API)

After generating publish.md, instruct the user to run the thumbnail script:

```bash
python ~/.claude/skills/youtube-publish-package/scripts/generate_thumbnail.py
```

The script:
1. Reads `characters.json` to get the main character's image_url
2. Reads `story.md` to understand the story context
3. Builds a thumbnail-optimized prompt (bright colors, close-up, expressive)
4. Generates image via Replicate (16:9 aspect ratio)
5. Uploads to Replicate Files API for a hosted URL
6. Saves as `./thumbnail.png`

The user should add text overlay afterward using Canva (free) or similar tool.

### Thumbnail prompt guidelines

When Claude writes `thumbnail_brief.json` (input for the script), the prompt must:
- Feature the main character in a CLOSE-UP with BIG expressive eyes/face
- Use bright, saturated, contrasting colors
- Include a dramatic or emotional moment from the story
- Have a clean, uncluttered composition (text goes on top later)
- End with: `"YouTube thumbnail style, bright saturated colors, dramatic lighting, close-up character portrait, clean background, no text, 4K, highly detailed"`

### thumbnail_brief.json format

```json
{
  "character_name": "Main character name",
  "character_image_url": "image_url from characters.json",
  "prompt": "Full thumbnail generation prompt...",
  "text_overlay_suggestion": "2-4 words to add in Canva (e.g., 'OH NO!' or 'MAGIC SEED')"
}
```

Claude MUST generate this file before telling the user to run the script.

## Phase 3 — Shorts Extraction (FFmpeg)

After thumbnail is approved, instruct the user to run:

```bash
# Extract the recommended Shorts
python ~/.claude/skills/youtube-publish-package/scripts/extract_shorts.py

# Or extract specific shot ranges
python ~/.claude/skills/youtube-publish-package/scripts/extract_shorts.py --shots 3-6
python ~/.claude/skills/youtube-publish-package/scripts/extract_shorts.py --shots 1-3 --shots 8-10
```

The script:
1. Reads `shots.json` for shot boundaries
2. Reads `shorts_plan.json` (Claude-generated) for recommended ranges
3. Extracts each range from `final_animation.mp4`
4. Center-crops to 9:16 vertical format
5. Saves to `./shorts/short_001.mp4`, `short_002.mp4`, etc.

### shorts_plan.json format

```json
{
  "shorts": [
    {
      "short_id": "short_001",
      "title": "Suggested Short title",
      "shot_range": [3, 6],
      "caption": "Hook text for the Short description"
    }
  ]
}
```

Claude MUST generate this file before telling the user to run the script.

## Review Gate (MANDATORY)

After ALL phases complete, present this EXACTLY:

```
YouTube Publish Package complete!

Phase 1 — Metadata:
- publish.md saved with 5 title options, description, 30+ tags
- Recommended title: "[best title option]"

Phase 2 — Thumbnail:
- thumbnail.png saved (add text overlay in Canva)
- Suggested overlay text: "[text_overlay_suggestion]"

Phase 3 — Shorts:
- [X] Shorts extracted to ./shorts/
  [short_001.mp4: "Title", short_002.mp4: "Title", ...]

Full publishing checklist:
1. Upload final_animation.mp4 to YouTube
2. Paste title, description, tags from publish.md
3. Upload thumbnail.png (add text in Canva first)
4. Set video as "Made for Kids"
5. Add to playlist
6. Schedule Shorts uploads per the stagger plan in publish.md
7. Post community teaser from publish.md

Please review all outputs. You can:
  - Approve all -> ready to upload
  - Request changes -> e.g., "make the titles more playful"
  - Regenerate thumbnail -> "redo thumbnail with [changes]"

Waiting for your approval.
```

**NEVER** upload or publish anything automatically. This is a preparation step only.
