#!/usr/bin/env python3
"""
Merge all generated video clips into a single final animation.

Supports two modes based on shots.json structure:
  1. Timeline mode: If shots.json has a "timeline" array, uses it for playback
     order with time-stretching to fill allocated durations (chorus reuse).
  2. Simple mode: Falls back to concatenating shots[] in order (legacy behavior).

Each clip is time-stretched via FFmpeg setpts to match its allocated duration
in the timeline. This allows 5-second Kling clips to fill longer slots.

Output: ./final_animation.mp4

Usage:
  cd /path/to/your/project
  python ~/.claude/skills/generating-composite-and-video/scripts/merge_clips.py

  # Specify audio file length for last segment duration
  python ~/.claude/skills/generating-composite-and-video/scripts/merge_clips.py --audio audio.mp3

Requirements:
  FFmpeg installed and in PATH.
    Windows : winget install ffmpeg
    Mac     : brew install ffmpeg
    Linux   : sudo apt install ffmpeg
"""

import json
import subprocess
import argparse
from pathlib import Path


# ── Helpers ───────────────────────────────────────────────────────────────────

def check_ffmpeg() -> bool:
    """Return True if ffmpeg is available in PATH."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True, text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", audio_path],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def get_video_duration(video_path: Path) -> float:
    """Get video duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(video_path)],
            capture_output=True, text=True, timeout=10,
        )
        return float(result.stdout.strip())
    except Exception:
        return 5.0  # default assumption for Kling clips


def stretch_clip(input_path: Path, output_path: Path, target_duration: float) -> bool:
    """Time-stretch a clip to target_duration using setpts filter.
    Returns True on success."""
    actual_duration = get_video_duration(input_path)
    if actual_duration <= 0:
        return False

    factor = target_duration / actual_duration

    # If factor is close to 1.0, just copy
    if 0.95 <= factor <= 1.05:
        import shutil
        shutil.copy2(input_path, output_path)
        return True

    cmd = [
        "ffmpeg", "-y", "-i", str(input_path),
        "-filter:v", f"setpts={factor}*PTS",
        "-an",  # drop audio from individual clips
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return result.returncode == 0


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Merge video clips into final_animation.mp4 using timeline from shots.json."
    )
    parser.add_argument(
        "--audio", metavar="AUDIO_FILE",
        help="Audio file to determine total duration (for last timeline segment).",
    )
    args = parser.parse_args()

    print("\n=== Story-to-Animation: Merge Clips -> final_animation.mp4 ===\n")

    # ── Check FFmpeg ──────────────────────────────────────────────────────────
    if not check_ffmpeg():
        print("ERROR: FFmpeg not found in PATH.")
        print("  Windows : winget install ffmpeg   (then restart terminal)")
        print("  Mac     : brew install ffmpeg")
        print("  Linux   : sudo apt install ffmpeg")
        raise SystemExit(1)

    # ── Load shot data ─────────────────────────────────────────────────────────
    if not Path("shots.json").exists():
        print("ERROR: shots.json not found in current directory")
        raise SystemExit(1)

    shots_data = json.loads(Path("shots.json").read_text(encoding="utf-8"))
    all_shots  = shots_data.get("shots", [])
    timeline   = shots_data.get("timeline", [])

    if not all_shots:
        print("ERROR: No shots found in shots.json")
        raise SystemExit(1)

    # ── Determine mode ─────────────────────────────────────────────────────────
    clips_dir = Path("clips")

    if timeline:
        # Timeline mode: use timeline[] for order and duration calculation
        print(f"  Mode: Timeline-based ({len(timeline)} entries, {len(all_shots)} unique shots)")

        # Determine total duration (from audio or last timeline entry + default)
        total_duration = None
        if args.audio and Path(args.audio).exists():
            total_duration = get_audio_duration(args.audio)
            print(f"  Audio duration: {total_duration:.1f}s")

        # Calculate segment durations
        segments = []
        for i, entry in enumerate(timeline):
            shot_id = entry["shot_id"]
            start_s = entry["start_s"]

            if i + 1 < len(timeline):
                duration = timeline[i + 1]["start_s"] - start_s
            elif total_duration:
                duration = total_duration - start_s
            else:
                # Default: use the clip's natural duration
                duration = get_video_duration(clips_dir / f"{shot_id}.mp4")

            segments.append({"shot_id": shot_id, "start_s": start_s, "duration": duration})

        # Process segments: stretch clips to fit their allocated duration
        stretched_dir = Path("_stretched")
        stretched_dir.mkdir(exist_ok=True)

        available = []
        missing = []

        for i, seg in enumerate(segments):
            clip_path = clips_dir / f"{seg['shot_id']}.mp4"
            if not clip_path.exists():
                missing.append(f"{seg['shot_id']} (timeline entry {i})")
                continue

            stretched_path = stretched_dir / f"seg_{i:03d}_{seg['shot_id']}.mp4"
            if stretch_clip(clip_path, stretched_path, seg["duration"]):
                available.append((f"seg_{i:03d}", stretched_path))
            else:
                print(f"  WARNING: Failed to stretch {seg['shot_id']} for segment {i}")
                missing.append(f"{seg['shot_id']} (stretch failed)")

        print(f"\n  Segments ready : {len(available)}")
        if missing:
            print(f"  Missing/failed : {', '.join(missing)}")
        print()

    else:
        # Simple mode: concatenate shots[] in order (legacy behavior)
        print(f"  Mode: Simple concatenation ({len(all_shots)} shots in order)")

        available = []
        missing   = []

        for shot in all_shots:
            sid       = shot["shot_id"]
            clip_path = clips_dir / f"{sid}.mp4"
            if clip_path.exists():
                available.append((sid, clip_path))
            else:
                missing.append(sid)

        print(f"  Clips found    : {len(available)}")
        if missing:
            print(f"  Missing clips  : {', '.join(missing)}")
        print()

    if not available:
        print("ERROR: No clips available — run generate_videos.py first.")
        raise SystemExit(1)

    if len(available) == 1:
        print("Only one clip — copying directly to final_animation.mp4")
        import shutil
        shutil.copy2(available[0][1], "final_animation.mp4")
        print("Done -> ./final_animation.mp4")
        return

    # ── Write FFmpeg concat list ──────────────────────────────────────────────
    concat_path = Path("concat.txt")
    with open(concat_path, "w", encoding="utf-8") as f:
        for label, clip_path in available:
            abs_path = clip_path.resolve().as_posix()
            f.write(f"file '{abs_path}'\n")

    print(f"Merging {len(available)} segments in order:")
    for label, _ in available:
        print(f"  {label}")
    print()

    output_path = Path("final_animation.mp4")

    # ── Run FFmpeg ────────────────────────────────────────────────────────────
    if timeline:
        # Re-encode for timeline mode since clips have been stretched
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_path),
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            str(output_path),
        ]
    else:
        # Stream copy for simple mode (fast, no re-encoding)
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_path),
            "-c", "copy",
            str(output_path),
        ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    concat_path.unlink(missing_ok=True)

    if result.returncode != 0:
        print("ERROR: FFmpeg failed:")
        print(result.stderr[-3000:] if result.stderr else "(no output)")
        raise SystemExit(1)

    # ── Summary ───────────────────────────────────────────────────────────────
    size_mb = output_path.stat().st_size / (1024 * 1024)

    print(f"{'='*50}")
    print(f"  Output   : ./final_animation.mp4")
    print(f"  Size     : {size_mb:.1f} MB")
    print(f"  Merged   : {len(available)} segments")
    if timeline:
        unique_shots = len(set(seg["shot_id"] for seg in segments))
        reused = len(segments) - unique_shots
        print(f"  Unique shots: {unique_shots} | Reused: {reused} times")
    if missing:
        print(f"  Skipped  : {len(missing)} missing")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
