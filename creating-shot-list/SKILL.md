---
name: creating-shot-list
description: >
  Reads story.md, characters.json, and backgrounds.json to decompose the story
  into individual 8-second shots. Each shot maps to specific character IDs, a
  background ID, camera movement, action description, and a self-contained Kling
  video-generation prompt. Saves output as shots.json. Part of the
  Story-to-Animation pipeline (Step 4 of 6). Use when story and asset JSON files
  exist and the user wants to create the shot-by-shot breakdown for video
  generation. After generating shots.json, ALWAYS present the output and wait
  for explicit user approval. Do NOT automatically trigger the next pipeline step.
---

# Shot List Creation (Scene-by-Scene Collaborative Mode)

Work through the story **one scene at a time** with the user. For each scene,
ask the user to describe their vision, then craft Kling-optimized video prompts
based on their direction. Save as `shots.json` using the two-layer schema.

## CRITICAL: Scene-by-Scene Workflow

Do NOT generate all shots at once. Follow this loop for EVERY scene:

### Step A — Present the scene

Read `story.md` and present the current scene to the user:

```
Scene [X]: [Scene Title]
Location: [location from story]
Characters: [who appears]
Story action: [what happens in this scene]

How do you visualize this scene? Describe the shots you want —
camera angles, mood, character actions, pacing, anything specific.
```

### Step B — Listen and craft

The user describes their vision. Based on their direction, draft 1-3 shots
for this scene with full Kling-optimized prompts. Present each shot:

```
Shot [shot_XXX] — Scene [X]: [title]
  Characters : [char_ids]
  Background : [bg_id]
  Camera     : [camera movement]
  Action     : [what happens]
  Video Prompt:
    [full Kling prompt — see format below]

Does this match your vision? Approve / Edit / Add another shot?
```

### Step C — Iterate until approved

Refine prompts based on user feedback. Only move to the next scene after
the user explicitly approves all shots for the current scene.

### Step D — Repeat for every scene

After the last scene is approved, assemble all shots into `shots.json`
and present the final summary.

## Kling 2.5 Turbo Pro Prompt Format

Kling understands multi-step causal instructions and precise camera language.
Write prompts that leverage this — NOT generic art-style-first descriptions.

### Prompt Structure

```
[Opening state + setting context], [camera specification],
[step-by-step action sequence using "first... then... finally..."],
[lighting/mood/atmosphere], [style anchor]
```

### Key Principles for Kling Prompts

1. **Multi-step causal chains** — Kling excels at "first X, then Y, finally Z"
   sequences. Break the 5-8 second action into 2-3 sequential beats.

2. **Precise camera language** — Use cinematic terminology Kling understands:
   - "camera slowly dollies in from wide to medium close-up"
   - "smooth lateral tracking shot following the character left to right"
   - "static locked-off wide shot, no camera movement"
   - "camera cranes up revealing the landscape below"
   - "slow push-in on the character's face"
   - "handheld-style gentle drift"

3. **Anchor to the start image** — Since we feed a composite as `start_image`,
   the prompt should describe motion FROM that starting state. Begin with
   "Starting from..." or describe the initial pose, then the movement.

4. **Physical grounding** — Describe how characters are physically supported
   (standing on, sitting on, gripping). Kling respects this.

5. **Style consistency cue** — End with a brief style anchor:
   "Pixar-style 3D animation, cinematic lighting, high detail"

6. **No text references** — Never mention text, captions, titles, or UI.

### Example Kling Prompts

**Action shot:**
```
A small orange fox stands at the edge of a sunlit cliff, tail swishing nervously.
Camera holds a wide shot then slowly pushes in to a medium close-up on the fox's
face. First the fox looks down at the valley below, ears pinning back, then it
looks up at an eagle soaring overhead, eyes widening with determination. Finally
it crouches low, muscles tensing, preparing to leap. Golden hour lighting casts
long shadows across the rocky cliff edge. Pixar-style 3D animation, cinematic
depth of field.
```

**Emotional beat:**
```
Two monkeys sit side by side on a thick jungle branch, their tails intertwined.
Static medium shot, no camera movement. First the smaller monkey slowly turns to
look at the larger one, then reaches out a hand and places it on the other's
shoulder. The larger monkey responds with a gentle nod, closing its eyes briefly.
Warm dappled sunlight filters through the canopy above. Soft, intimate mood.
Pixar-style 3D rendering, shallow depth of field.
```

**High-energy action:**
```
Five colorful parrots perched in a row on a vine suddenly take flight in sequence.
Smooth tracking shot following the birds left to right as they launch one by one.
First the red parrot spreads its wings and pushes off, then the blue and green
follow in rapid succession, finally the last two launch together in a burst of
feathers. Motion blur on the wing tips, jungle canopy rushing past in the
background. Dynamic, exhilarating energy. Pixar-style 3D animation, fast-paced
cinematic motion.
```

**Music video lyric-sync:**
```
A lone wolf stands on a moonlit hilltop, head tilted back. Camera starts on a
wide establishing shot then slowly cranes up. First the wolf opens its mouth and
howls upward, chest expanding with the breath, then the camera continues rising
to reveal a vast starfield above. The wolf's silhouette grows smaller against the
enormous sky. Cool blue moonlight with silver rim lighting on the wolf's fur.
Atmospheric, epic scale. Pixar-style 3D animation, dramatic composition.
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
      "video_prompt": "A young girl with curly auburn hair and a teal adventure jacket stands at the entrance of a magical forest clearing filled with bioluminescent mushrooms. Camera slowly dollies in from a wide establishing shot to a medium shot. First she takes a cautious step forward, looking around in awe, then she reaches out to touch a glowing mushroom near her, finally she smiles as golden sunbeams shift through the ancient oak canopy above. Warm golden-hour lighting with soft volumetric rays. Pixar-style 3D animation, cinematic depth of field."
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
you do NOT need to include them in video_prompt. But you MUST ensure your prompts
do not contradict them:

- Characters must always be physically supported (on ground, on surface, gripping something)
- Never describe characters floating, hovering, or unsupported
- Never include text, captions, UI elements, or watermarks in descriptions
- Always specify correct limb count when describing character poses

## Review Gate (MANDATORY)

After ALL scenes are approved and `shots.json` is saved, present:

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

You can still:
  - Revisit any scene -> "go back to scene 3"
  - Edit shots.json directly -> tell me when done
  - Approve -> say "approved" to proceed to video generation

Waiting for your final approval before generating video clips.
```

**NEVER** proceed to the next skill automatically. Wait for explicit approval.
