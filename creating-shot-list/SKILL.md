---
name: creating-shot-list
description: >
  Reads story.md, characters.json, and backgrounds.json to decompose the story
  into individual 8-second shots. Each shot maps to specific character IDs, a
  background ID, camera movement, action description, and a self-contained Veo 3
  video-generation prompt. Saves output as shots.json. Part of the
  Story-to-Animation pipeline (Step 4 of 6). Use when story and asset JSON files
  exist and the user wants to create the shot-by-shot breakdown for video
  generation. After generating shots.json, ALWAYS present the output and wait
  for explicit user approval. Do NOT automatically trigger the next pipeline step.
---

# Shot List Creation

Decompose the story into discrete 8-second shots mapped to asset IDs and Veo 3
generation prompts. Save as `shots.json` using the two-layer schema (shots + timeline).

## Instructions

1. Read `story.md`, `characters.json`, and `backgrounds.json`.
2. Break each scene into **1-3 shots** of exactly 8 seconds each.
3. Assign sequential IDs: `shot_001`, `shot_002`, ...
4. For each shot:
   - **characters**: List of `character_id`s present (must match characters.json IDs)
   - **background**: The `bg_id` for this location (must match backgrounds.json IDs)
   - **action**: Clear visual description of what happens in this 8-second clip
   - **camera_movement**: e.g., `"static wide shot"`, `"slow dolly-in"`, `"pan left"`, `"close-up on face"`, `"tracking shot"`
   - **dialogue**: Spoken line if any, or `""` if none
   - **mood**: Emotional tone
   - **veo_prompt**: Self-contained Veo 3 generation prompt (see format below)
   - **transition_shot** (optional): Set to `true` if this shot needs the start+end frame technique (e.g., character falls, jumps, transitions between states)

## Veo Prompt Format

Each `veo_prompt` must be fully self-contained — describe the shot as if standalone.
Do NOT use asset IDs (char_001, bg_001) — Veo reads this directly.

Pattern:
```
[Art style], [shot type + camera movement], [character description + action],
[setting description], [lighting and mood], [duration hint]
```

Example:
```
Pixar-style 3D animation, slow dolly-in from wide to medium shot, a 12-year-old
girl with curly auburn hair and teal jacket steps into a magical sunlit forest
clearing, bioluminescent mushrooms and golden sunbeams, sense of wonder, 8 seconds
```

## Timeline-Based Shot Reuse (Chorus Optimization)

For stories with repeated sections (chorus in music videos, recurring motifs),
use the timeline to reference the same shot_id multiple times without generating
duplicate clips.

- `shots[]` = unique clips to generate (each generated and paid for once)
- `timeline[]` = playback order with timestamps (reuse shot_ids as needed)

Rules:
- Every shot_id in `timeline[]` MUST exist in `shots[]`
- Repeated sections (chorus, hook) should reference the same shot_id
- `start_s` values define when each segment begins in the final video
- The merge script will time-stretch clips to fill their allocated duration

## Output File: shots.json (Two-Layer Schema)

```json
{
  "shots": [
    {
      "shot_id": "shot_001",
      "scene_number": 1,
      "scene_title": "Scene title from story.md",
      "shot_number_in_scene": 1,
      "duration_seconds": 8,
      "characters": ["char_001"],
      "background": "bg_001",
      "action": "Luna steps into the forest clearing, eyes wide with wonder",
      "camera_movement": "Slow dolly-in from wide shot to medium shot",
      "dialogue": "",
      "mood": "Wonder and discovery",
      "transition_shot": false,
      "veo_prompt": "Pixar-style 3D animation, slow dolly-in from wide to medium shot, a 12-year-old girl with curly auburn hair and teal adventure jacket steps cautiously into a magical forest clearing with bioluminescent mushrooms, warm golden sunbeams filter through ancient oak trees, sense of awe and discovery, 8 seconds"
    }
  ],
  "timeline": [
    {"start_s": 0.0, "shot_id": "shot_001"},
    {"start_s": 8.0, "shot_id": "shot_002"},
    {"start_s": 16.0, "shot_id": "shot_003"},
    {"start_s": 24.0, "shot_id": "shot_001"}
  ]
}
```

For simple stories without repeated sections, `timeline[]` is just each shot
in order with `start_s` incrementing by `duration_seconds`.

## Prompt Safety Rules (Applied Automatically in Step 5)

The following safety rules are automatically appended by `generate_videos.py` —
you do NOT need to include them in veo_prompt. But you MUST ensure your prompts
do not contradict them:

- Characters must always be physically supported (on ground, on surface, gripping something)
- Never describe characters floating, hovering, or unsupported
- Never include text, captions, UI elements, or watermarks in descriptions
- Always specify correct limb count when describing character poses

## Review Gate (MANDATORY)

After saving `shots.json`, present this EXACTLY:

```
Shot List Creation complete. Output saved to shots.json.

Summary:
- Total unique shots: [X]
- Timeline entries: [X] (reused shots: [X])
- Scenes covered: [X]
- Characters referenced: [list unique char_ids used]
- Backgrounds referenced: [list unique bg_ids used]
- Transition shots (start+end frame): [X]
- Estimated total video length: [timeline entries x duration = X seconds (~X min)]
- Estimated generation cost: [unique shots] clips to generate

Please review shots.json. Key things to check:
  - Does each shot's action match the story flow?
  - Are veo_prompts detailed and fully self-contained (no asset ID references)?
  - Are all character_ids and bg_ids valid (match the JSON files)?
  - Is the pacing right (shots per scene)?
  - Are repeated sections correctly reusing shot_ids in timeline?
  - Are transition_shot flags set for shots needing start+end frame technique?

You can:
  - Approve -> say "approved" or "proceed"
  - Request changes -> e.g., "add a close-up of Luna's face after shot_003"
  - Edit shots.json directly -> tell me when done

Waiting for your approval before generating video clips.
```

**NEVER** proceed to the next skill automatically. Wait for explicit approval.

Allow iterative refinement — add, remove, or reorder shots as needed.
