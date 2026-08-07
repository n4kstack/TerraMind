#!/usr/bin/env python
"""
Decode the landing-page hero video into a scroll-scrubbable frame sequence.

The landing hero is not a <video>. It is a canvas that draws one still per
scroll position, so the footage advances only as fast as the user scrolls and
stops dead when they do. That needs the video pre-split into numbered stills,
which is what this script does.

Run it once whenever the source clip changes:

    python frontend/scripts/extract-hero-frames.py

It reads the first video file it finds in frontend/scripts/source/, and writes:

    frontend/public/hero/wide/frame-0000.webp     ... desktop tier
    frontend/public/hero/compact/frame-0000.webp  ... phone tier
    frontend/src/features/landing/frameManifest.ts  ... generated constants

Two tiers rather than one because this is the single heaviest asset on the
site. A phone gets a 720-wide set at roughly a sixth of the bytes; sending it
the desktop set would cost more than the rest of the page combined.

WebP rather than JPEG: same perceptual quality at ~30% fewer bytes, and every
browser that can run this app has supported it since 2020. Note that *.webp
must be LFS-tracked in .gitattributes — the Hugging Face Space rejects any push
carrying a plain binary blob.

ffmpeg comes from the imageio-ffmpeg wheel (a static build), so there is no
system ffmpeg to install:

    python -m pip install imageio-ffmpeg
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg

HERE = Path(__file__).resolve().parent
FRONTEND = HERE.parent
SOURCE_DIR = HERE / "source"
# Cleaned masters land in a subfolder so they are never picked up as a second
# input on the next run: find_source() only scans SOURCE_DIR itself, so the
# original stays the one true source and --delogo is always applied to pristine
# footage rather than to a file it has already been applied to.
CLEAN_DIR = SOURCE_DIR / "clean"
PUBLIC_DIR = FRONTEND / "public" / "hero"
GENERATED_TS = FRONTEND / "src" / "features" / "landing" / "frameManifest.ts"

VIDEO_SUFFIXES = {".mp4", ".mov", ".webm", ".m4v", ".mkv", ".avi"}

# Watermark box for the current wheat clip, in SOURCE pixels, measured rather
# than eyeballed: a static semi-transparent overlay raises the floor of every
# pixel it covers, so the per-pixel minimum across all 120 stills isolates it
# against otherwise near-black surroundings. That put the generator's sparkle at
# x 1136-1183, y 576-623 — a 48x48 mark — and the box below pads it by 6px so
# delogo has clean pixels to interpolate the edges from.
#
# Re-measure if the clip changes; these coordinates mean nothing for other
# footage. `--delogo none` disables it.
DEFAULT_DELOGO = "1130:570:60:60"

# Frame count is a quality/weight dial, not a property of the source. Scroll
# scrubbing is not playback: the eye tracks position, not motion, so it reads as
# smooth far below 24fps. 120 frames over a three-viewport pin puts a new frame
# roughly every 20px of scroll, which is past the point where more frames stop
# being visible and start being bytes.
DEFAULT_FRAMES = 120

TIERS = {
    # name        width  quality
    "wide": (1440, 72),
    "compact": (720, 70),
}


def find_source(explicit: str | None) -> Path:
    if explicit:
        path = Path(explicit)
        if not path.is_absolute():
            path = Path.cwd() / path
        if not path.exists():
            sys.exit(f"No such file: {path}")
        return path

    if not SOURCE_DIR.exists():
        sys.exit(
            f"Drop the hero clip into {SOURCE_DIR} (any of {sorted(VIDEO_SUFFIXES)}) "
            "and run this again."
        )

    candidates = sorted(
        p for p in SOURCE_DIR.iterdir() if p.suffix.lower() in VIDEO_SUFFIXES
    )
    if not candidates:
        sys.exit(f"No video found in {SOURCE_DIR}. Expected one of {sorted(VIDEO_SUFFIXES)}.")
    if len(candidates) > 1:
        print(f"  ! {len(candidates)} videos present, using {candidates[0].name}")
    return candidates[0]


def probe(ffmpeg: str, video: Path) -> tuple[float, int, int]:
    """Duration in seconds and pixel dimensions, read off ffmpeg's own banner.

    The imageio-ffmpeg wheel ships ffmpeg but not ffprobe, so the stream line is
    parsed directly. `-i` with no output makes ffmpeg dump metadata and exit
    non-zero, which is expected and not an error here.
    """
    out = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(video)],
        capture_output=True,
        text=True,
        errors="replace",
    ).stderr

    duration_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", out)
    if not duration_match:
        sys.exit(f"Could not read a duration from {video.name}. Is it a video file?")
    hours, minutes, seconds = duration_match.groups()
    duration = int(hours) * 3600 + int(minutes) * 60 + float(seconds)

    size_match = re.search(r"Stream #.*Video:.*?(\d{2,5})x(\d{2,5})", out)
    if not size_match:
        sys.exit(f"Could not read frame dimensions from {video.name}.")
    width, height = (int(v) for v in size_match.groups())

    return duration, width, height


def parse_delogo(spec: str | None, width: int, height: int) -> str | None:
    """`X:Y:W:H` in source pixels -> an ffmpeg delogo filter, or None."""
    if not spec or spec.lower() == "none":
        return None
    try:
        x, y, w, h = (int(part) for part in spec.split(":"))
    except ValueError:
        sys.exit(f"--delogo wants X:Y:W:H in source pixels, got {spec!r}")
    # delogo rebuilds the box by interpolating from the pixels immediately
    # around it, so it needs at least one row/column of real footage on every
    # side. A box flush against an edge makes ffmpeg fail mid-encode.
    if x < 1 or y < 1 or x + w > width - 1 or y + h > height - 1:
        sys.exit(
            f"--delogo box {spec} does not fit inside {width}x{height} with a 1px margin"
        )
    return f"delogo=x={x}:y={y}:w={w}:h={h}"


def write_clean_master(ffmpeg: str, video: Path, delogo: str | None) -> Path:
    """Re-encode the source without its watermark and without any audio.

    The frame sequence never carries audio and never sees the watermark, so this
    is not needed to build the site. It exists so the repaired clip is the one
    kept for reuse — otherwise the only watermark-free copy of the footage would
    be 120 stills.
    """
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)
    out = CLEAN_DIR / f"{video.stem}.clean.mp4"

    command = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(video)]
    if delogo:
        command += ["-vf", delogo]
    command += [
        # -an drops the audio stream outright rather than muting it.
        "-an",
        "-c:v", "libx264",
        # Visually lossless for a master that may be re-encoded again later.
        "-crf", "18",
        "-preset", "slow",
        "-pix_fmt", "yuv420p",
        # Web-playable without downloading the whole file first.
        "-movflags", "+faststart",
        str(out),
    ]
    subprocess.run(command, check=True)
    return out


def extract(
    ffmpeg: str,
    video: Path,
    duration: float,
    frames: int,
    tier: str,
    source_width: int,
    delogo: str | None,
) -> tuple[int, int, int]:
    """Write one tier's stills. Returns (count, width, height)."""
    width, quality = TIERS[tier]
    # Never encode wider than the source. Upscaling here bakes the interpolation
    # into every still and costs real bytes for detail that is not in the clip:
    # a 1280-wide source pushed to 1440 measured 60 KB/frame against 44 KB at
    # native, for a picture the browser can reconstruct just as well by scaling
    # the canvas. Downscaling to a tier is still worth doing — that is a genuine
    # bandwidth saving for phones.
    width = min(width, source_width)
    out_dir = PUBLIC_DIR / tier

    # Wholesale rebuild. Leaving stale frames behind is worse than the rewrite
    # cost: a shorter clip would keep the tail of the previous one, and the
    # sequence would run off the end of the new footage into old footage.
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    # delogo comes first in the chain, before fps and scale: its box is in
    # source pixels, so running it after a scale would erase the wrong region —
    # on the phone tier, a region a little over half the size in the wrong
    # place.
    chain = ",".join(
        filter(None, [delogo, f"fps={frames}/{duration:.6f}", f"scale={width}:-2:flags=lanczos"])
    )

    # `fps` resamples rather than selecting keyframes, so the stills are evenly
    # spaced in *time* regardless of how the source was encoded. -fps_mode
    # passthrough stops ffmpeg from duplicating frames to hit a container rate.
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel", "error",
            "-i", str(video),
            "-fps_mode", "passthrough",
            "-vf", chain,
            "-c:v", "libwebp",
            "-quality", str(quality),
            "-compression_level", "6",
            "-preset", "picture",
            str(out_dir / "frame-%04d.webp"),
        ],
        check=True,
    )

    written = sorted(out_dir.glob("frame-*.webp"))
    if not written:
        sys.exit(f"ffmpeg produced no frames for tier '{tier}'.")

    # ffmpeg's fps filter lands within a frame or two of the request depending on
    # where the last sample falls. Trim the overshoot; pad an undershoot by
    # repeating the final still so every tier is exactly `frames` long and the
    # component can index both with one number.
    if len(written) > frames:
        for extra in written[frames:]:
            extra.unlink()
        written = written[:frames]
    while len(written) < frames:
        clone = out_dir / f"frame-{len(written):04d}.webp"
        shutil.copyfile(written[-1], clone)
        written.append(clone)

    # ffmpeg numbers from 1; the component indexes from 0.
    for index, path in enumerate(sorted(out_dir.glob("frame-*.webp"))):
        target = out_dir / f"tmp-{index:04d}.webp"
        path.rename(target)
    for path in sorted(out_dir.glob("tmp-*.webp")):
        path.rename(out_dir / path.name.replace("tmp-", "frame-"))

    first = out_dir / "frame-0000.webp"
    height = round(width * probe_image_ratio(first))
    return len(written), width, height


def probe_image_ratio(path: Path) -> float:
    from PIL import Image

    with Image.open(path) as img:
        return img.height / img.width


def human(n: int) -> str:
    return f"{n / 1_048_576:.1f} MB" if n >= 1_048_576 else f"{n / 1024:.0f} KB"


# --------------------------------------------------------------- legibility ---
#
# The hero puts white copy on this footage. Whether that copy is readable is
# decided by two numbers: how bright the footage gets behind it, and how heavy
# the scrim in .hero-frame-scrim is. The first is a property of the clip, so it
# is measured here rather than guessed, and the second is then chosen to match.
#
# Read the "scrim needed" line against the alpha the stylesheet actually ships
# (currently 0.65 where the copy sits). If the measurement comes out higher, the
# scrim is too light for this clip and index.css needs raising.

# Vertical band the hero copy occupies within the viewport, as fractions of
# height. The beats are centred, and this is the widest any of them gets.
COPY_BAND = (0.28, 0.76)

# WCAG 2.1: white (relative luminance 1.0) needs the surface under it at or
# below this to clear 4.5:1.  (1.05 / 4.5) - 0.05
MAX_BACKDROP_LUMINANCE = 0.18333

# Must match --hero-void in src/index.css: hsl(152 44% 4.5%).
HERO_VOID_SRGB = (6, 17, 12)

# Combined alpha .hero-frame-scrim actually paints where the copy sits — the
# radial and the linear multiply: 1 - (1 - 0.28) x (1 - 0.28). Keep in step with
# index.css; this is the figure the measurement below is checked against.
SHIPPED_SCRIM_ALPHA = 0.48


def _relative_luminance(rgb: tuple[float, float, float]) -> float:
    """WCAG relative luminance from 0-255 sRGB."""
    channels = []
    for raw in rgb:
        c = raw / 255
        channels.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    r, g, b = channels
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def measure_copy_band(tier: str, sample: int = 12) -> tuple[float, float]:
    """Brightest realistic backdrop in the copy band, and the scrim alpha it needs.

    Returns (p95 luminance, minimum scrim alpha for white to clear AA).

    The 95th percentile rather than the mean: a mean is dragged down by a dark
    sky and hides the blown highlight that actually sits behind a word. The
    percentile is taken per frame and then maximised across the sampled frames,
    so the answer is the worst moment of the clip, not its average.
    """
    from PIL import Image

    frames = sorted((PUBLIC_DIR / tier).glob("frame-*.webp"))
    if not frames:
        return 0.0, 0.0
    step = max(1, len(frames) // sample)

    # The final frame is included explicitly. A clip that resolves on a sunrise
    # or a sunset — which is most agricultural footage, and is exactly what this
    # one does — ends on its brightest frame, and a plain stride lands on 110 of
    # 120 and never looks at it. That is the frame the closing beat sits on.
    picked = frames[::step]
    if frames[-1] not in picked:
        picked.append(frames[-1])

    worst = 0.0
    for path in picked:
        with Image.open(path) as img:
            rgb = img.convert("RGB")
            top = int(rgb.height * COPY_BAND[0])
            bottom = int(rgb.height * COPY_BAND[1])
            band = rgb.crop((0, top, rgb.width, bottom))
            # Downsample before the per-pixel pass; the percentile of a boxed
            # average is what matters here, not of individual sensor pixels.
            band = band.resize((80, 40), Image.Resampling.BOX)
            # tobytes() rather than getdata(): getdata() is deprecated in
            # Pillow 12 and its replacement does not exist in 11.
            raw = band.tobytes()
            lums = sorted(
                _relative_luminance((raw[i], raw[i + 1], raw[i + 2]))
                for i in range(0, len(raw), 3)
            )
            worst = max(worst, lums[int(len(lums) * 0.95)])

    # Composite in sRGB (which is what the browser does), then re-measure.
    # Bisect rather than invert: luminance is not linear in alpha.
    grey = round(255 * (worst ** (1 / 2.2)))
    low, high = 0.0, 1.0
    for _ in range(40):
        alpha = (low + high) / 2
        mixed = tuple(grey * (1 - alpha) + v * alpha for v in HERO_VOID_SRGB)
        if _relative_luminance(mixed) > MAX_BACKDROP_LUMINANCE:
            low = alpha
        else:
            high = alpha
    return worst, high


def write_ts(frames: int, sizes: dict[str, tuple[int, int]], source: str) -> None:
    wide_w, wide_h = sizes["wide"]
    compact_w, compact_h = sizes["compact"]

    GENERATED_TS.write_text(
        f"""/**
 * GENERATED FILE -- do not edit by hand.
 *
 * Written by frontend/scripts/extract-hero-frames.py from {source}.
 * Re-run that script to change the frame count, tier widths or source clip.
 */

export interface HeroTier {{
  /** Public path prefix, without the frame number. */
  readonly dir: string;
  readonly width: number;
  readonly height: number;
}}

/** Total stills per tier. Both tiers are the same length, so one index drives both. */
export const HERO_FRAME_COUNT = {frames};

export const HERO_TIERS = {{
  wide: {{ dir: '/hero/wide', width: {wide_w}, height: {wide_h} }},
  compact: {{ dir: '/hero/compact', width: {compact_w}, height: {compact_h} }},
}} as const satisfies Record<string, HeroTier>;

/** `/hero/wide/frame-0042.webp` */
export function heroFrameUrl(tier: HeroTier, index: number): string {{
  return `${{tier.dir}}/frame-${{String(index).padStart(4, '0')}}.webp`;
}}
""",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="Video file (default: first clip in scripts/source/)")
    parser.add_argument(
        "--frames", type=int, default=DEFAULT_FRAMES, help=f"Stills to emit (default {DEFAULT_FRAMES})"
    )
    parser.add_argument(
        "--delogo",
        default=DEFAULT_DELOGO,
        help=f"Watermark box X:Y:W:H in source pixels, or 'none' (default {DEFAULT_DELOGO})",
    )
    parser.add_argument(
        "--no-clean-master",
        action="store_true",
        help="Skip re-encoding a watermark-free, audio-free copy of the source",
    )
    args = parser.parse_args()

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    video = find_source(args.input)
    duration, src_w, src_h = probe(ffmpeg, video)
    delogo = parse_delogo(args.delogo, src_w, src_h)

    print(f"  source   {video.name}  {src_w}x{src_h}  {duration:.2f}s")
    print(f"  frames   {args.frames}  ({duration / args.frames * 1000:.0f}ms of footage each)")
    print(f"  delogo   {args.delogo if delogo else 'off'}")

    sizes: dict[str, tuple[int, int]] = {}
    total = 0
    for tier in TIERS:
        count, width, height = extract(
            ffmpeg, video, duration, args.frames, tier, src_w, delogo
        )
        weight = sum(p.stat().st_size for p in (PUBLIC_DIR / tier).glob("*.webp"))
        total += weight
        sizes[tier] = (width, height)
        print(f"  {tier:8} {count} frames  {width}x{height}  {human(weight)}  ({human(weight // count)}/frame)")

    write_ts(args.frames, sizes, video.name)
    print(f"  total    {human(total)} on disk")
    print(f"  wrote    {GENERATED_TS.relative_to(FRONTEND)}")

    if not args.no_clean_master:
        clean = write_clean_master(ffmpeg, video, delogo)
        print(
            f"  master   {clean.relative_to(HERE)}  "
            f"{human(clean.stat().st_size)}  (no watermark, no audio)"
        )

    luminance, needed = measure_copy_band("wide")
    verdict = "ok" if needed <= SHIPPED_SCRIM_ALPHA else "TOO LIGHT — raise it"
    print(
        f"\n  legibility  copy band peaks at {luminance:.3f} relative luminance\n"
        f"              white text needs a scrim of {needed:.2f}; "
        f"index.css ships {SHIPPED_SCRIM_ALPHA:.2f} -> {verdict}"
    )

    print("\n  Remember: *.webp must be LFS-tracked before pushing to the Space.")


if __name__ == "__main__":
    main()
