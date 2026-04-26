#!/usr/bin/env python3
"""
Generate character and background images using the Replicate API.

Pipeline per image:
  1. POST /v1/predictions (text-to-image model) → Replicate generates image
  2. Poll /v1/predictions/{id} until status: succeeded → get output URL
  3. Download PNG to ./characters/ or ./backgrounds/
  4. Upload to Replicate Files API → get permanent public URL
  5. Store that URL as image_url in characters.json / backgrounds.json

Config — create a .env file in your project directory:
  REPLICATE_API_TOKEN=your_replicate_api_token_here

  On first run the script auto-creates a .env template if one is not found.
  Real environment variables always take precedence over .env values.

Usage:
  cd /path/to/your/project
  python ~/.claude/skills/generating-character-and-background-images/scripts/generate_images.py

  # Choose a different model
  python ~/.claude/skills/generating-character-and-background-images/scripts/generate_images.py --model black-forest-labs/flux-schnell

  # List supported models
  python ~/.claude/skills/generating-character-and-background-images/scripts/generate_images.py --list-models

Requirements:
  pip install requests
"""

import os
import json
import time
import argparse
from pathlib import Path
import requests


# ── Supported Replicate text-to-image models ──────────────────────────────────

IMAGE_MODELS = {
    "black-forest-labs/flux-1.1-pro": {
        "description": "FLUX 1.1 Pro — high quality (default)",
        "prompt_key": "prompt",
        "aspect_ratio_key": "aspect_ratio",
        "extra_params": {"output_format": "png"},
    },
    "black-forest-labs/flux-schnell": {
        "description": "FLUX Schnell — fast, good quality",
        "prompt_key": "prompt",
        "aspect_ratio_key": "aspect_ratio",
        "extra_params": {"output_format": "png"},
    },
    "black-forest-labs/flux-1.1-pro-ultra": {
        "description": "FLUX 1.1 Pro Ultra — highest fidelity",
        "prompt_key": "prompt",
        "aspect_ratio_key": "aspect_ratio",
        "extra_params": {"output_format": "png"},
    },
    "stability-ai/stable-diffusion-3.5-large": {
        "description": "Stable Diffusion 3.5 Large",
        "prompt_key": "prompt",
        "aspect_ratio_key": "aspect_ratio",
        "extra_params": {},
    },
    "ideogram-ai/ideogram-v2": {
        "description": "Ideogram v2 — excellent rendering",
        "prompt_key": "prompt",
        "aspect_ratio_key": "aspect_ratio",
        "extra_params": {},
    },
}

DEFAULT_MODEL = "black-forest-labs/flux-1.1-pro"

REPLICATE_API_BASE = "https://api.replicate.com/v1"
POLL_INTERVAL = 5
MAX_POLLS = 60  # max ~5 minutes per image


# ── Config loading (.env) ─────────────────────────────────────────────────────

_ENV_TEMPLATE = """\
# Story-to-Animation — API Keys
# Get your Replicate token from: https://replicate.com/account/api-tokens

REPLICATE_API_TOKEN=your_replicate_api_token_here
"""

def load_env() -> None:
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
    val = os.environ.get(name, "").strip()
    placeholder = f"your_{name.lower()}_here"
    if not val or val == placeholder:
        print(f"\nERROR: '{name}' is not set in .env")
        print(f"  Open .env in your project directory and set:  {name}=your_actual_key")
        raise SystemExit(1)
    return val


load_env()
REPLICATE_API_TOKEN = get_key("REPLICATE_API_TOKEN")
AUTH_HEADER = {"Authorization": f"Bearer {REPLICATE_API_TOKEN}"}


# ── Replicate API helpers ─────────────────────────────────────────────────────

def submit_prediction(model_id: str, input_payload: dict) -> tuple:
    """Submit a prediction. Returns (prediction_id, None) or (None, error)."""
    try:
        resp = requests.post(
            f"{REPLICATE_API_BASE}/predictions",
            headers={**AUTH_HEADER, "Content-Type": "application/json"},
            json={"model": model_id, "input": input_payload},
            timeout=30,
        )
        data = resp.json()
        if resp.status_code in (200, 201) and data.get("id"):
            return data["id"], None
        return None, f"HTTP {resp.status_code}: {data.get('detail', data.get('error', str(data)))}"
    except Exception as e:
        return None, str(e)


def poll_prediction(prediction_id: str, label: str) -> tuple:
    """Poll until done. Returns (output_url, None) or (None, error)."""
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
                return None, f"Unexpected output format: {output}"
            elif status == "failed":
                return None, data.get("error", "Prediction failed")
            elif status == "canceled":
                return None, "Prediction was canceled"
            else:
                elapsed = attempt * POLL_INTERVAL
                if elapsed % 30 == 0:
                    print(f"    [{label}] {status or 'starting'} — {elapsed}s elapsed...")
        except Exception as e:
            print(f"    [{label}] poll error: {e}")

    timeout_s = MAX_POLLS * POLL_INTERVAL
    return None, f"Timed out after {timeout_s // 60}m{timeout_s % 60:02d}s"


def download_file(url: str, output_path: Path) -> bool:
    try:
        resp = requests.get(url, timeout=60)
        output_path.write_bytes(resp.content)
        return output_path.stat().st_size > 0
    except Exception as e:
        print(f"    Download failed: {e}")
        return False


def upload_to_replicate_files(local_path: Path) -> tuple:
    """Upload local PNG to Replicate Files API for permanent hosting.
    Returns (permanent_url, None) or (None, error).
    """
    try:
        with open(local_path, "rb") as f:
            resp = requests.post(
                f"{REPLICATE_API_BASE}/files",
                headers=AUTH_HEADER,
                files={"content": (local_path.name, f, "image/png")},
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


# ── Per-image pipeline ────────────────────────────────────────────────────────

def generate_image(prompt: str, aspect_ratio: str, out_path: Path,
                   model_id: str, model_config: dict) -> tuple:
    """
    Generate one image via Replicate, download locally, upload to Replicate Files.
    Returns:
      ("SKIP", None)    — file already exists
      (file_url, None)  — success, permanent Replicate Files URL
      (None, error)     — failure
    """
    if out_path.exists():
        return "SKIP", None

    input_payload = {model_config["prompt_key"]: prompt}
    if model_config.get("aspect_ratio_key"):
        input_payload[model_config["aspect_ratio_key"]] = aspect_ratio
    input_payload.update(model_config.get("extra_params", {}))

    pred_id, err = submit_prediction(model_id, input_payload)
    if not pred_id:
        return None, f"Submit failed: {err}"

    print(f"    submitted → prediction {pred_id[:16]}...")

    gen_url, err = poll_prediction(pred_id, out_path.stem)
    if not gen_url:
        return None, err

    if not download_file(gen_url, out_path):
        return None, "Download failed"

    file_url, err = upload_to_replicate_files(out_path)
    if not file_url:
        print(f"    [files] Upload failed ({err}) — using generation URL as fallback")
        return gen_url, None  # fallback: still works if Step 5 runs soon after

    print(f"    hosted  → {file_url}")
    return file_url, None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate character and background images via Replicate API."
    )
    parser.add_argument(
        "--model", metavar="MODEL_ID",
        default=DEFAULT_MODEL,
        help=f"Replicate text-to-image model to use (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--list-models", action="store_true",
        help="List supported models and exit.",
    )
    args = parser.parse_args()

    if args.list_models:
        print("\n=== Supported Replicate Text-to-Image Models ===\n")
        for mid, info in IMAGE_MODELS.items():
            default_tag = " (default)" if mid == DEFAULT_MODEL else ""
            print(f"  {mid}{default_tag}")
            print(f"    {info['description']}\n")
        print("Any valid Replicate model ID also works via --model.\n")
        return

    model_id = args.model
    if model_id in IMAGE_MODELS:
        model_config = IMAGE_MODELS[model_id]
    else:
        print(f"  Note: model '{model_id}' not in built-in list, using default keys")
        model_config = {
            "description": f"Custom: {model_id}",
            "prompt_key": "prompt",
            "aspect_ratio_key": "aspect_ratio",
            "extra_params": {},
        }

    print(f"\n=== Story-to-Animation: Step 3 — Image Generation ===\n")
    print(f"  Model: {model_id}  ({model_config['description']})\n")

    for fname in ["characters.json", "backgrounds.json"]:
        if not Path(fname).exists():
            print(f"ERROR: {fname} not found in current directory")
            raise SystemExit(1)

    chars_data = json.loads(Path("characters.json").read_text(encoding="utf-8"))
    bgs_data   = json.loads(Path("backgrounds.json").read_text(encoding="utf-8"))

    Path("characters").mkdir(exist_ok=True)
    Path("backgrounds").mkdir(exist_ok=True)

    results    = {"success": [], "skipped": [], "failed": []}
    json_dirty = {"chars": False, "bgs": False}

    # ── Character images (1:1 aspect ratio) ───────────────────────────────────
    characters = chars_data.get("characters", [])
    print(f"Generating {len(characters)} character image(s)...\n")

    for char in characters:
        cid = char["character_id"]
        out = Path("characters") / f"{cid}.png"
        print(f"  [{cid}] {char['name']}...")

        url, err = generate_image(char["prompt"], "1:1", out, model_id, model_config)

        if url == "SKIP":
            print(f"         already exists — skipping (delete PNG to regenerate)")
            results["skipped"].append(f"characters/{cid}.png")
        elif url:
            char["image_url"] = url
            json_dirty["chars"] = True
            print(f"         saved to characters/{cid}.png")
            results["success"].append(f"characters/{cid}.png")
        else:
            print(f"         FAILED: {err}")
            results["failed"].append(f"characters/{cid}.png")

    # ── Background images (16:9 aspect ratio) ─────────────────────────────────
    backgrounds = bgs_data.get("backgrounds", [])
    print(f"\nGenerating {len(backgrounds)} background image(s)...\n")

    for bg in backgrounds:
        bid = bg["bg_id"]
        out = Path("backgrounds") / f"{bid}.png"
        print(f"  [{bid}] {bg['name']}...")

        url, err = generate_image(bg["prompt"], "16:9", out, model_id, model_config)

        if url == "SKIP":
            print(f"         already exists — skipping (delete PNG to regenerate)")
            results["skipped"].append(f"backgrounds/{bid}.png")
        elif url:
            bg["image_url"] = url
            json_dirty["bgs"] = True
            print(f"         saved to backgrounds/{bid}.png")
            results["success"].append(f"backgrounds/{bid}.png")
        else:
            print(f"         FAILED: {err}")
            results["failed"].append(f"backgrounds/{bid}.png")

    # ── Write image_url back into JSON files ──────────────────────────────────
    if json_dirty["chars"]:
        Path("characters.json").write_text(
            json.dumps(chars_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print("\n  characters.json updated with image_url")
    if json_dirty["bgs"]:
        Path("backgrounds.json").write_text(
            json.dumps(bgs_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print("  backgrounds.json updated with image_url")

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*50}")
    print(f"  Generated : {len(results['success'])}")
    print(f"  Skipped   : {len(results['skipped'])} (already existed)")
    print(f"  Failed    : {len(results['failed'])}")
    print(f"{'='*50}")

    if results["skipped"]:
        print("\nNote: Skipped images were not re-uploaded — existing image_url may be stale.")
        print("      Delete the PNG and re-run to generate a fresh URL.")

    if results["failed"]:
        print("\nFailed images (update prompt in JSON, delete PNG, re-run):")
        for f in results["failed"]:
            print(f"  - {f}")
        raise SystemExit(1)
    else:
        print("\nAll done! image_url fields point to Replicate Files hosted URLs.")
        print("Next step: create the shot list (Skill 4), then run generate_videos.py (Skill 5).")


if __name__ == "__main__":
    main()
