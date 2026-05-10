#!/usr/bin/env python3
"""
Generate composite images and video clips for each shot — fully parallelized.
Both phases use the Replicate API with user-selectable models.

Phase 1 — Composite images via Replicate (selectable image model)
Phase 2 — Video clips via Replicate (selectable video model)

Config — create a .env file in your project directory:
  REPLICATE_API_TOKEN=your_replicate_api_token_here

Usage:
  cd /path/to/your/project

  # Default models
  python generate_videos.py

  # Choose models
  python generate_videos.py --image-model google/imagen-4-ultra --video-model kwaivgi/kling-v2.5-turbo-pro

  # Single shot mode
  python generate_videos.py --shot shot_001

  # List supported models
  python generate_videos.py --list-models

Requirements:
  pip install requests
"""

import os
import json
import time
import threading
import argparse
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests


# ── Safety prompt rules (appended automatically) ─────────────────────────────

COMPOSITE_SAFETY_SUFFIX = (
    "Pixar-style 3D animation, cinematic 16:9 wide composition, warm golden-hour lighting, "
    "high-detail render. STRICTLY ANATOMICALLY CORRECT: each character has exactly the correct "
    "number of limbs — never extra limbs, never duplicated hands, never fused bodies. Every "
    "character is physically supported — sitting on a surface, standing on the ground, or clearly "
    "gripping something with visible hands; NO characters floating unsupported in mid-air. "
    "ABSOLUTELY no text, no captions, no on-screen lyrics, no letters, no words, no numbers, "
    "no UI elements, no watermarks, no logos anywhere in the image."
)

VIDEO_NEGATIVE_PROMPT = (
    "text, captions, lyrics, subtitles, letters, words, numbers, watermark, logo, ui elements, "
    "extra limbs, extra hands, deformed anatomy, blurry, low quality, floating character, "
    "levitating, character suspended in mid-air, unsupported character, character hovering, "
    "disappearing limbs, morphing bodies, characters merging, new characters appearing, "
    "characters spawning into frame, characters walking into frame from off-screen"
)

VIDEO_ANCHOR_SUFFIX = (
    "IMPORTANT: every character remains physically supported throughout the entire shot — "
    "either firmly on the ground, standing on a surface, or clearly gripping something "
    "with both hands. NO character is ever floating or hovering unsupported in mid-air. "
    "Anatomy stays consistent throughout — correct number of limbs and features at all times."
)


# ── Supported Replicate image models (Phase 1 — composites) ──────────────────

IMAGE_MODELS = {
    "google/nano-banana": {
        "description": "Google Nano Banana — proven quality for composites (default)",
        "prompt_key": "prompt",
        "image_key": "input_images",
        "image_is_array": True,
        "extra_params": {"aspect_ratio": "16:9"},
    },
    "google/imagen-4-ultra": {
        "description": "Google Imagen 4 Ultra — highest quality, slower",
        "prompt_key": "prompt",
        "image_key": "reference_images",
        "image_is_array": True,
        "extra_params": {"aspect_ratio": "16:9"},
    },
    "bytedance/seedream-4.5": {
        "description": "ByteDance Seedream 4.5 — strong spatial understanding",
        "prompt_key": "prompt",
        "image_key": "image",
        "image_is_array": False,
        "extra_params": {"aspect_ratio": "16:9"},
    },
    "black-forest-labs/flux-2-pro": {
        "description": "FLUX.2 Pro — high-quality editing, 8 reference images",
        "prompt_key": "prompt",
        "image_key": "input_images",
        "image_is_array": True,
        "extra_params": {"aspect_ratio": "16:9"},
    },
    "black-forest-labs/flux-2-flex": {
        "description": "FLUX.2 Flex — max-quality, 10 reference images",
        "prompt_key": "prompt",
        "image_key": "input_images",
        "image_is_array": True,
        "extra_params": {"aspect_ratio": "16:9"},
    },
    "black-forest-labs/flux-2-max": {
        "description": "FLUX.2 Max — highest fidelity from Black Forest Labs",
        "prompt_key": "prompt",
        "image_key": "input_images",
        "image_is_array": True,
        "extra_params": {"aspect_ratio": "16:9"},
    },
    "google/nano-banana-2": {
        "description": "Google Nano Banana 2 — fast, multi-image fusion",
        "prompt_key": "prompt",
        "image_key": "input_images",
        "image_is_array": True,
        "extra_params": {"aspect_ratio": "16:9", "resolution": "1K"},
    },
    "google/nano-banana-pro": {
        "description": "Google Nano Banana Pro — state of the art editing",
        "prompt_key": "prompt",
        "image_key": "input_images",
        "image_is_array": True,
        "extra_params": {"aspect_ratio": "16:9", "resolution": "1K"},
    },
    "bytedance/seedream-5-lite": {
        "description": "ByteDance Seedream 5.0 Lite — reasoning + editing",
        "prompt_key": "prompt",
        "image_key": "image",
        "image_is_array": False,
        "extra_params": {"aspect_ratio": "16:9"},
    },
    "xai/grok-imagine-image": {
        "description": "xAI Grok Imagine — SOTA image model",
        "prompt_key": "prompt",
        "image_key": "image",
        "image_is_array": False,
        "extra_params": {},
    },
}

DEFAULT_IMAGE_MODEL = "google/nano-banana"


# ── Supported Replicate video models (Phase 2 — clips) ───────────────────────

VIDEO_MODELS = {
    "kwaivgi/kling-v2.5-turbo-pro": {
        "description": "Kling v2.5 Turbo Pro — high quality, consistent motion (default)",
        "input_key": "start_image",
        "prompt_key": "prompt",
        "supports_end_image": True,
        "supports_negative_prompt": True,
        "negative_prompt_key": "negative_prompt",
        "extra_params": {"duration": 5, "aspect_ratio": "16:9"},
    },
    "prunaai/p-video": {
        "description": "PrunaAI P-Video — fast video generation",
        "input_key": "image",
        "prompt_key": "prompt",
        "supports_end_image": False,
        "supports_negative_prompt": False,
        "negative_prompt_key": None,
        "extra_params": {},
    },
}

DEFAULT_VIDEO_MODEL = "kwaivgi/kling-v2.5-turbo-pro"


# ── Config loading (.env) ─────────────────────────────────────────────────────

_ENV_TEMPLATE = """\
# Story-to-Animation — API Keys
# Get your Replicate token from: https://replicate.com/account/api-tokens

REPLICATE_API_TOKEN=your_replicate_api_token_here
"""

def load_env() -> None:
    """Load .env from the project directory into os.environ."""
    env_path = Path(".env")
    if not env_path.exists():
        env_path.write_text(_ENV_TEMPLATE, encoding="utf-8")
        print("\n  .env file created in your project directory.")
        print("  -> Open .env, fill in your REPLICATE_API_TOKEN, then re-run.\n")
        raise SystemExit(0)

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if key and key not in os.environ:
            os.environ[key] = val

    print("  Loaded API keys from .env")

def get_key(name: str) -> str:
    """Return a required key from os.environ."""
    val = os.environ.get(name, "").strip()
    placeholder = f"your_{name.lower()}_here"
    if not val or val == placeholder:
        print(f"\nERROR: '{name}' is not set in .env")
        print(f"  Open .env in your project directory and set:  {name}=your_actual_key")
        raise SystemExit(1)
    return val


load_env()
REPLICATE_API_TOKEN = get_key("REPLICATE_API_TOKEN")


# ── Replicate API ─────────────────────────────────────────────────────────────

REPLICATE_API_BASE = "https://api.replicate.com/v1"
AUTH_HEADER = {"Authorization": f"Bearer {REPLICATE_API_TOKEN}"}


# ── Tunable settings ──────────────────────────────────────────────────────────

COMPOSITE_MAX_WORKERS = 5
VIDEO_MAX_WORKERS     = 5
POLL_INTERVAL         = 5     # seconds between polls
MAX_POLLS             = 120   # max wait: 120 x 5s = 10 minutes per task


# ── Thread-safe print ─────────────────────────────────────────────────────────

_print_lock = threading.Lock()

def tprint(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)

def fmt_elapsed(start: float) -> str:
    s = int(time.time() - start)
    return f"{s // 60}m{s % 60:02d}s" if s >= 60 else f"{s}s"


# ── Replicate API helpers ─────────────────────────────────────────────────────

def submit_replicate_prediction(model_id: str, input_payload: dict) -> tuple:
    """Submit a Replicate prediction via /v1/models/{owner}/{name}/predictions.
    Returns (prediction_id, None) or (None, error)."""
    try:
        resp = requests.post(
            f"{REPLICATE_API_BASE}/models/{model_id}/predictions",
            headers={**AUTH_HEADER, "Content-Type": "application/json"},
            json={"input": input_payload},
            timeout=30,
        )
        data = resp.json()
        if resp.status_code in (200, 201) and data.get("id"):
            return data["id"], None
        error_detail = data.get("detail", data.get("error", str(data)))
        return None, f"HTTP {resp.status_code}: {error_detail}"
    except Exception as e:
        return None, str(e)


def poll_replicate_prediction(prediction_id: str, label: str) -> tuple:
    """Poll a Replicate prediction until done. Returns (output_url, None) or (None, error)."""
    url = f"{REPLICATE_API_BASE}/predictions/{prediction_id}"

    for attempt in range(1, MAX_POLLS + 1):
        time.sleep(POLL_INTERVAL)
        try:
            resp = requests.get(url, headers=AUTH_HEADER, timeout=30)
            data = resp.json()
            status = data.get("status", "")

            if status == "succeeded":
                output = data.get("output")
                if isinstance(output, str):
                    return output, None
                elif isinstance(output, list) and output:
                    return output[0], None
                elif isinstance(output, dict):
                    for key in ("video", "image", "url", "output"):
                        if output.get(key):
                            return output[key], None
                    vals = list(output.values())
                    if vals:
                        return vals[0], None
                return None, f"succeeded but unexpected output format: {output}"

            elif status == "failed":
                error = data.get("error", "Prediction failed (no reason given)")
                return None, str(error)

            elif status == "canceled":
                return None, "Prediction was canceled"

            else:
                elapsed_s = attempt * POLL_INTERVAL
                if elapsed_s % 30 == 0:
                    tprint(f"    [{label}] {status or 'starting'} — {elapsed_s}s elapsed...")

        except Exception as e:
            tprint(f"    [{label}] poll error: {e}")

    timeout_s = MAX_POLLS * POLL_INTERVAL
    return None, f"Timed out after {timeout_s // 60}m{timeout_s % 60:02d}s"


def download_file(url: str, output_path: Path) -> bool:
    try:
        resp = requests.get(url, timeout=120)
        output_path.write_bytes(resp.content)
        return output_path.stat().st_size > 0
    except Exception as e:
        tprint(f"    Download failed: {e}")
        return False


def upload_to_replicate_files(local_path: Path, content_type: str = "image/png") -> tuple:
    """Upload a local file to Replicate Files API for permanent hosting.
    Returns (permanent_url, None) or (None, error)."""
    try:
        with open(local_path, "rb") as f:
            resp = requests.post(
                f"{REPLICATE_API_BASE}/files",
                headers=AUTH_HEADER,
                files={"content": (local_path.name, f, content_type)},
                timeout=60,
            )
        data = resp.json()
        if resp.status_code in (200, 201):
            url = data.get("urls", {}).get("get") or data.get("url")
            if url:
                return url, None
            return None, f"No URL in response: {data}"
        return None, f"HTTP {resp.status_code}: {data}"
    except Exception as e:
        return None, str(e)


def extract_last_frame(clip_path: Path, output_path: Path) -> bool:
    """Extract the last frame of a video clip using FFmpeg.
    Returns True if successful."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-sseof", "-0.1", "-i", str(clip_path),
             "-frames:v", "1", str(output_path)],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0 and output_path.exists()
    except Exception:
        return False


# ── Phase 1 worker: composite image via Replicate ────────────────────────────

def run_composite(shot: dict, bg_map: dict, char_map: dict,
                  composite_path: Path, model_id: str, model_config: dict) -> tuple:
    """Generate one composite image via Replicate, upload to Files API.
    Returns (shot_id, permanent_url, None) or (shot_id, None, error)."""
    sid = shot["shot_id"]
    t0  = time.time()

    # Collect reference image URLs: background first, then characters
    bg = bg_map.get(shot.get("background", ""), {})
    input_urls = []
    if bg.get("image_url"):
        input_urls.append(bg["image_url"])
    for cid in shot.get("characters", []):
        c = char_map.get(cid, {})
        if c.get("image_url"):
            input_urls.append(c["image_url"])

    if not input_urls:
        return sid, None, "No image_urls found for this shot"

    # Build prompt with safety suffix
    prompt = (
        f"Composited animation scene: {shot.get('action', 'characters in location')}. "
        f"{COMPOSITE_SAFETY_SUFFIX}"
    )

    # Build input payload based on model config
    input_payload = {model_config["prompt_key"]: prompt}
    input_payload.update(model_config.get("extra_params", {}))

    if model_config.get("image_is_array"):
        input_payload[model_config["image_key"]] = input_urls
    else:
        input_payload[model_config["image_key"]] = input_urls[0]

    pred_id, err = submit_replicate_prediction(model_id, input_payload)
    if not pred_id:
        return sid, None, f"Submit failed: {err}"

    tprint(f"  [{sid}] composite submitted -> prediction: {pred_id[:16]}... (model: {model_id})")

    url, err = poll_replicate_prediction(pred_id, f"{sid}/composite")
    if not url:
        return sid, None, err

    if not download_file(url, composite_path):
        return sid, None, "Download failed"

    # Upload to Replicate Files API for permanent URL (required by Kling)
    perm_url, upload_err = upload_to_replicate_files(composite_path)
    if not perm_url:
        tprint(f"  [{sid}] Files API upload failed ({upload_err}) — using generation URL as fallback")
        perm_url = url

    tprint(f"  [{sid}] composite done ({fmt_elapsed(t0)}) -> composites/{sid}.png")
    return sid, perm_url, None


# ── Phase 2 worker: video via Replicate ───────────────────────────────────────

def run_video(shot: dict, composite_url: str, clip_path: Path,
              model_id: str, model_config: dict,
              end_image_url: str = None) -> tuple:
    """Generate one video clip via Replicate. Returns (shot_id, True, None) or (shot_id, False, error)."""
    sid = shot["shot_id"]
    t0  = time.time()

    # Build video prompt with safety anchor suffix
    base_prompt = shot.get("veo_prompt", shot.get("action", ""))
    prompt = f"{base_prompt} {VIDEO_ANCHOR_SUFFIX}"

    input_payload = {
        model_config["prompt_key"]: prompt,
        model_config["input_key"]: composite_url,
    }
    input_payload.update(model_config.get("extra_params", {}))

    # Add negative prompt if model supports it
    if model_config.get("supports_negative_prompt") and model_config.get("negative_prompt_key"):
        input_payload[model_config["negative_prompt_key"]] = VIDEO_NEGATIVE_PROMPT

    # Add end_image if provided and model supports it (start+end frame technique)
    if end_image_url and model_config.get("supports_end_image"):
        input_payload["end_image"] = end_image_url

    pred_id, err = submit_replicate_prediction(model_id, input_payload)
    if not pred_id:
        return sid, False, f"Submit failed: {err}"

    tprint(f"  [{sid}] video submitted   -> prediction: {pred_id[:16]}... (model: {model_id})")

    url, err = poll_replicate_prediction(pred_id, f"{sid}/video")
    if not url:
        return sid, False, err

    if download_file(url, clip_path):
        tprint(f"  [{sid}] video done ({fmt_elapsed(t0)}) -> clips/{sid}.mp4")
        return sid, True, None

    return sid, False, "Download failed"


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate composite images and video clips via Replicate API."
    )
    parser.add_argument(
        "--shot", metavar="SHOT_ID",
        help="Process a single shot only (e.g. --shot shot_001).",
    )
    parser.add_argument(
        "--image-model", metavar="MODEL_ID",
        default=DEFAULT_IMAGE_MODEL,
        help=f"Replicate model for composite image generation (default: {DEFAULT_IMAGE_MODEL}).",
    )
    parser.add_argument(
        "--video-model", metavar="MODEL_ID",
        default=DEFAULT_VIDEO_MODEL,
        help=f"Replicate model for video generation (default: {DEFAULT_VIDEO_MODEL}).",
    )
    parser.add_argument(
        "--use-end-frame", action="store_true",
        help="Use start+end frame technique: extract last frame of previous clip as transition anchor.",
    )
    parser.add_argument(
        "--list-models", action="store_true",
        help="List all supported Replicate models and exit.",
    )
    args = parser.parse_args()

    if args.list_models:
        print("\n=== Supported Replicate Image Models (Phase 1 — composites) ===\n")
        for mid, info in IMAGE_MODELS.items():
            default_tag = " (default)" if mid == DEFAULT_IMAGE_MODEL else ""
            print(f"  {mid}{default_tag}")
            print(f"    {info['description']}")
            multi = "yes" if info.get("image_is_array") else "no"
            print(f"    Multi-reference images: {multi}")
            print()

        print("=== Supported Replicate Video Models (Phase 2 — clips) ===\n")
        for mid, info in VIDEO_MODELS.items():
            default_tag = " (default)" if mid == DEFAULT_VIDEO_MODEL else ""
            print(f"  {mid}{default_tag}")
            print(f"    {info['description']}")
            end_frame = "yes" if info.get("supports_end_image") else "no"
            neg_prompt = "yes" if info.get("supports_negative_prompt") else "no"
            print(f"    End-image support: {end_frame} | Negative prompt: {neg_prompt}")
            print()

        print("You can also pass any valid Replicate model ID with --image-model or --video-model.")
        print("For custom models, defaults: prompt_key='prompt', image_key='image'.\n")
        return

    # Resolve image model config
    img_model_id = args.image_model
    if img_model_id in IMAGE_MODELS:
        img_model_config = IMAGE_MODELS[img_model_id]
    else:
        print(f"  Note: image model '{img_model_id}' not in built-in list, using default keys")
        img_model_config = {
            "description": f"Custom model: {img_model_id}",
            "prompt_key": "prompt",
            "image_key": "image",
            "image_is_array": False,
            "extra_params": {},
        }

    # Resolve video model config
    vid_model_id = args.video_model
    if vid_model_id in VIDEO_MODELS:
        vid_model_config = VIDEO_MODELS[vid_model_id]
    else:
        print(f"  Note: video model '{vid_model_id}' not in built-in list, using default keys")
        vid_model_config = {
            "description": f"Custom model: {vid_model_id}",
            "input_key": "image",
            "prompt_key": "prompt",
            "supports_end_image": False,
            "supports_negative_prompt": False,
            "negative_prompt_key": None,
            "extra_params": {},
        }

    run_start = time.time()
    print(f"\n=== Story-to-Animation: Step 5 — Composite + Video Generation ===\n")

    # ── Load data ─────────────────────────────────────────────────────────────
    for fname in ["shots.json", "characters.json", "backgrounds.json"]:
        if not Path(fname).exists():
            print(f"ERROR: {fname} not found in current directory")
            raise SystemExit(1)

    shots_data = json.loads(Path("shots.json").read_text(encoding="utf-8"))
    chars_data = json.loads(Path("characters.json").read_text(encoding="utf-8"))
    bgs_data   = json.loads(Path("backgrounds.json").read_text(encoding="utf-8"))

    char_map = {c["character_id"]: c for c in chars_data["characters"]}
    bg_map   = {b["bg_id"]:        b for b in bgs_data["backgrounds"]}

    # Verify image_url fields
    missing = []
    for c in chars_data["characters"]:
        if not c.get("image_url"):
            missing.append(f"  characters/{c['character_id']} — missing image_url")
    for b in bgs_data["backgrounds"]:
        if not b.get("image_url"):
            missing.append(f"  backgrounds/{b['bg_id']} — missing image_url")
    if missing:
        print("ERROR: image_url fields missing. Run generate_images.py (Step 3) first.")
        for m in missing:
            print(m)
        raise SystemExit(1)

    all_shots = shots_data.get("shots", [])

    # ── Build pending list ─────────────────────────────────────────────────────
    if args.shot:
        target = next((s for s in all_shots if s["shot_id"] == args.shot), None)
        if not target:
            print(f"ERROR: shot_id '{args.shot}' not found in shots.json")
            raise SystemExit(1)
        clip_path = Path("clips") / f"{args.shot}.mp4"
        if clip_path.exists():
            print(f"[{args.shot}] clip already exists — nothing to do.")
            return
        pending = [target]
        skipped = []
        print(f"  Mode        : single-shot  ({args.shot})")
    else:
        pending = [s for s in all_shots if not (Path("clips") / f"{s['shot_id']}.mp4").exists()]
        skipped = [s["shot_id"] for s in all_shots if s not in pending]
        print(f"  Mode        : bulk  ({len(pending)} pending, {len(skipped)} already done)")

    print(f"  Image model : {img_model_id}  ({img_model_config['description']})")
    print(f"  Video model : {vid_model_id}  ({vid_model_config['description']})")
    print(f"  End-frame   : {'enabled' if args.use_end_frame else 'disabled'}\n")

    if skipped:
        print(f"Skipping {len(skipped)} shot(s) with existing clips: {', '.join(skipped)}")
    if not pending:
        print("All clips already exist. Nothing to do.")
        return

    Path("composites").mkdir(exist_ok=True)
    Path("clips").mkdir(exist_ok=True)
    Path("_stage").mkdir(exist_ok=True)

    results        = {"success": [], "failed": [], "skipped": skipped}
    composite_urls = {}

    # ── Phase 1: Composites via Replicate ─────────────────────────────────────
    p1_start = time.time()

    if args.shot:
        print(f"Phase 1 — Composite: generating {args.shot} via {img_model_id}...\n")
        sid, url, err = run_composite(
            pending[0], bg_map, char_map,
            Path("composites") / f"{args.shot}.png",
            img_model_id, img_model_config,
        )
        if url:
            composite_urls[sid] = url
        else:
            print(f"  [{sid}] composite FAILED: {err}")
            results["failed"].append(sid)
    else:
        print(f"Phase 1 — Composites: submitting {len(pending)} jobs in parallel via {img_model_id}...\n")
        with ThreadPoolExecutor(max_workers=COMPOSITE_MAX_WORKERS) as ex:
            futures = {
                ex.submit(
                    run_composite,
                    shot, bg_map, char_map,
                    Path("composites") / f"{shot['shot_id']}.png",
                    img_model_id, img_model_config,
                ): shot["shot_id"]
                for shot in pending
            }
            for future in as_completed(futures):
                sid, url, err = future.result()
                if url:
                    composite_urls[sid] = url
                else:
                    tprint(f"  [{sid}] composite FAILED: {err}")
                    results["failed"].append(sid)

    print(f"\nPhase 1 done in {fmt_elapsed(p1_start)}: "
          f"{len(composite_urls)}/{len(pending)} composites ready.\n")

    # ── Phase 2: Videos via Replicate ─────────────────────────────────────────
    video_shots = [s for s in pending if s["shot_id"] in composite_urls]

    if not video_shots:
        print("No composites succeeded — cannot generate any videos.")
    else:
        p2_start = time.time()

        # Build shot order map for end-frame extraction
        shot_order = [s["shot_id"] for s in all_shots]

        if args.shot:
            print(f"Phase 2 — Video: generating {args.shot} via {vid_model_id}...\n")

            # Determine end_image_url if using start+end frame technique
            end_image_url = None
            if args.use_end_frame and vid_model_config.get("supports_end_image"):
                idx = shot_order.index(args.shot) if args.shot in shot_order else -1
                if idx > 0:
                    prev_sid = shot_order[idx - 1]
                    prev_clip = Path("clips") / f"{prev_sid}.mp4"
                    if prev_clip.exists():
                        lastframe_path = Path("_stage") / f"{prev_sid}_lastframe.png"
                        if extract_last_frame(prev_clip, lastframe_path):
                            perm_url, _ = upload_to_replicate_files(lastframe_path)
                            if perm_url:
                                end_image_url = composite_urls[video_shots[0]["shot_id"]]
                                # Swap: start_image = last frame of prev, end_image = this composite
                                composite_urls[video_shots[0]["shot_id"]] = perm_url
                                tprint(f"  [{args.shot}] using start+end frame technique")

            sid, ok, err = run_video(
                video_shots[0],
                composite_urls[video_shots[0]["shot_id"]],
                Path("clips") / f"{video_shots[0]['shot_id']}.mp4",
                vid_model_id, vid_model_config,
                end_image_url=end_image_url,
            )
            if ok:
                results["success"].append(sid)
            else:
                print(f"  [{sid}] video FAILED: {err}")
                results["failed"].append(sid)
        else:
            print(f"Phase 2 — Videos: submitting {len(video_shots)} jobs in parallel via {vid_model_id}...\n")
            with ThreadPoolExecutor(max_workers=VIDEO_MAX_WORKERS) as ex:
                futures = {
                    ex.submit(
                        run_video,
                        shot,
                        composite_urls[shot["shot_id"]],
                        Path("clips") / f"{shot['shot_id']}.mp4",
                        vid_model_id, vid_model_config,
                    ): shot["shot_id"]
                    for shot in video_shots
                }
                for future in as_completed(futures):
                    sid, ok, err = future.result()
                    if ok:
                        results["success"].append(sid)
                    else:
                        tprint(f"  [{sid}] video FAILED: {err}")
                        results["failed"].append(sid)

        print(f"\nPhase 2 done in {fmt_elapsed(p2_start)}: "
              f"{len(results['success'])}/{len(video_shots)} videos ready.")

    # ── Summary ───────────────────────────────────────────────────────────────
    total_run_time = fmt_elapsed(run_start)

    print(f"\n{'='*55}")
    print(f"  Total run time : {total_run_time}")
    print(f"  Image model    : {img_model_id}")
    print(f"  Video model    : {vid_model_id}")
    print(f"  Generated      : {len(results['success'])} clips")
    print(f"  Skipped        : {len(results['skipped'])} (clips already existed)")
    print(f"  Failed         : {len(results['failed'])}")
    print(f"{'='*55}")
    print(f"  Composites -> ./composites/")
    print(f"  Clips      -> ./clips/")

    if results["failed"]:
        print("\nFailed shots (delete composite + clip file then re-run):")
        for sid in results["failed"]:
            print(f"  - {sid}")
        raise SystemExit(1)
    else:
        print("\nAll done! The Story-to-Animation pipeline is complete.")


if __name__ == "__main__":
    main()
