# Story-to-Animation Skill — Lessons from Monkey Mayhem V3

Use this as a reference when running or improving the skill pipeline for future music video projects.

---

## Critical Fix: Replicate API Endpoint

**Wrong** (returns HTTP 422 "version is required"):
```
POST /v1/predictions
{ "model": "owner/name", "input": { ... } }
```

**Correct**:
```
POST /v1/models/owner/name/predictions
{ "input": { ... } }
```

Apply this to every script: `generate_images.py`, `generate_composites_replicate.py`, `generate_videos_replicate.py`.

After generating composite PNGs, upload each to the Replicate Files API to get a permanent URL:
```
POST /v1/files
Authorization: Bearer {token}
Content-Type: multipart/form-data
files: { content: (filename, file_bytes, "image/png") }
```
The returned `urls.get` value is what Kling accepts as `start_image`.

---

## Do Not Use kie.ai

The `generating-composite-and-video` skill's `generate_videos.py` silently uses kie.ai for video generation despite the README implying Replicate. kie.ai cannot fetch Replicate Files URLs (they require Bearer auth), causing all video jobs to fail with "media file unavailable."

Use Replicate exclusively throughout:
- **Composites**: `google/nano-banana`
- **Video**: `kwaivgi/kling-v2.5-turbo-pro`

---

## Prompt Safety Rules — Add by Default

These rules prevented floating characters, text burn-in, and anatomy errors. Include from shot 1, not reactively.

### Composite prompt suffix (append to every shot's action/prompt)

```
Pixar-style 3D animation, cinematic 16:9 wide composition, warm golden-hour jungle lighting,
high-detail render. STRICTLY ANATOMICALLY CORRECT: each character has exactly the correct
number of limbs — never extra limbs, never duplicated hands, never fused bodies. Every
character is physically supported — sitting on the branch, standing on the branch, or clearly
gripping a vine with visible hands; NO characters floating unsupported in mid-air.
ABSOLUTELY no text, no captions, no on-screen lyrics, no letters, no words, no numbers,
no UI elements, no watermarks, no logos anywhere in the image.
```

### Video negative prompt

```
text, captions, lyrics, subtitles, letters, words, numbers, watermark, logo, ui elements,
extra limbs, extra hands, deformed anatomy, blurry, low quality, floating character,
levitating, character suspended in mid-air, unsupported character, character hovering,
disappearing limbs, morphing bodies, characters merging, new characters appearing,
characters spawning into frame, characters walking into frame from off-screen
```

### Video prompt anchor suffix (append to every shot's video prompt)

```
IMPORTANT: every character remains physically supported throughout the entire shot —
either firmly seated on the branch, standing on the branch, or clearly gripping a vine
with both hands. NO character is ever floating or hovering unsupported in mid-air.
Anatomy stays consistent throughout — correct number of limbs and features at all times.
```

---

## Step-by-Step Review Gates

### Gate 1 — After shot list, before composites

Present each shot one at a time:
```
Shot [shot_001] — Section: Intro
  Camera  : Wide establishing shot
  Action  : Five monkeys sit on a branch, swinging their legs...
  Prompt  : [detailed video prompt]
  Duration: 8.0s

Approve / Edit / Skip?
```
Do not submit any composite jobs until all shots are approved.

### Gate 2 — After each composite, before video

Show the downloaded PNG and ask:
```
Composite ready: composites/shot_001.png
Approve (generate video) / Redo (regenerate composite) / Edit prompt?
```

### Gate 3 — After each video clip

Show the clip and ask:
```
Video ready: clips/shot_001.mp4
Approve / Redo / Edit prompt?
```

---

## Timeline-Based Shot Reuse (Chorus Optimization)

For music videos with repeated sections (chorus, hook), use a two-layer `shots.json` schema instead of generating one clip per timeline entry.

```json
{
  "shots": [
    { "shot_id": "shot_004", "prompt": "...", "composite_url": "..." }
  ],
  "timeline": [
    { "start_s": 14.0, "shot_id": "shot_004" },
    { "start_s": 55.0, "shot_id": "shot_004" },
    { "start_s": 96.0, "shot_id": "shot_004" }
  ]
}
```

- `shots[]` = unique clips to generate (pay once)
- `timeline[]` = playback order (reuse as many times as needed)

In the merge script, each segment's duration = `timeline[i+1].start_s - timeline[i].start_s` (last entry uses audio length). Use `ffmpeg setpts={factor}*PTS` to slow-stretch each 5s Kling clip to fit its allocated duration.

For Monkey Mayhem V3: 16 unique shots → 20 timeline entries. Chorus shots reused 3× each = ~6 video generations saved.

---

## Kling Start + End Frame Technique

For shots that require a specific motion arc (e.g. character falls and crashes), use both `start_image` and `end_image`:

- `start_image` = extract last frame of the preceding clip (mid-action state)
- `end_image` = composite of the destination state

```python
# Extract last frame of shot_011.mp4
ffmpeg -sseof -0.1 -i clips/shot_011.mp4 -frames:v 1 _stage/shot_011_lastframe.png

# Submit to Kling with both frames
{
  "start_image": "<replicate_files_url_of_lastframe>",
  "end_image":   "<composite_url_of_shot_012>",
  "prompt":      "monkeys crash into the jungle floor...",
  "duration":    5,
  "aspect_ratio": "16:9"
}
```

This forces the model to animate the transition between the two frames rather than inventing its own motion.
