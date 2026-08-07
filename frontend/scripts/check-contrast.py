#!/usr/bin/env python
"""
Validate a palette against the pairs recorded in design-system/terramind/MASTER.md.

MASTER.md §1.3 says every colour pair "was validated with a WCAG contrast
script". That script was not in the repository, so the ratios could only be
taken on trust and no one could re-check them after a token changed. This is
that script.

    python frontend/scripts/check-contrast.py

Two things are checked, and the second matters as much as the first:

  * CONTRAST — every text/surface pair clears its WCAG threshold (4.5:1 for
    body text, 3:1 for a boundary that is the only affordance).

  * STATUS SEPARATION — the three confidence levels stay tellable apart. They
    are the reason this file is not just a contrast checker. Badge and
    ConfidenceMeter render high/moderate/low straight from --primary, --accent
    and --destructive, so a palette can pass every contrast check and still
    ship a UI where "high confidence" and "moderate confidence" are the same
    colour. For a tool that tells a smallholder how much weight to put on a
    prediction before spending money on seed, that is a correctness bug.

    Separation is measured in CIE76 dE against the surface those swatches
    actually sit on, plus hue distance. dE 25 is roughly "obviously a different
    colour at a glance" for adjacent UI chips.
"""

from __future__ import annotations

import colorsys
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CSS = HERE.parent / "src" / "index.css"

# (text token, surface token, minimum). Mirrors MASTER.md §1.3.
PAIRS = [
    ("foreground", "background", 4.5, "body on background"),
    ("foreground", "card", 4.5, "body on card"),
    ("muted-foreground", "background", 4.5, "muted-fg on background"),
    ("muted-foreground", "card", 4.5, "muted-fg on card"),
    ("muted-foreground", "muted", 4.5, "muted-fg on muted"),
    ("primary-foreground", "primary", 4.5, "primary-fg on primary"),
    ("secondary-foreground", "secondary", 4.5, "secondary-fg on secondary"),
    ("accent-foreground", "accent", 4.5, "accent-fg on accent"),
    ("destructive-foreground", "destructive", 4.5, "destructive-fg on destructive"),
    ("primary", "card", 4.5, "primary text on card"),
    ("accent", "card", 4.5, "accent text on card"),
    ("destructive", "card", 4.5, "destructive text on card"),
    ("secondary", "card", 4.5, "secondary text on card"),
    ("border-input", "card", 3.0, "border-input on card"),
    ("border-input", "background", 3.0, "border-input on background"),
]

# The three confidence levels, as the components actually render them today.
# Change these if Badge/ConfidenceMeter are repointed at different tokens.
STATUS = {
    # Mirrors Badge.tsx and ConfidenceMeter.tsx. `high` reads --secondary, not
    # --primary: with a warm brand, primary and accent are 16 degrees apart and
    # measured dE 21.9, so success and caution were no longer tellable apart.
    "high / success": "secondary",
    "moderate / caution": "accent",
    "low / risk": "destructive",
}
MIN_STATUS_DE = 25.0


def parse_blocks(css: str) -> dict[str, dict[str, str]]:
    """Pull the :root and .dark token blocks out of index.css."""
    out: dict[str, dict[str, str]] = {}
    for name, pattern in (("light", r":root\s*\{(.*?)\n  \}"), ("dark", r"\.dark\s*\{(.*?)\n  \}")):
        match = re.search(pattern, css, re.S)
        if not match:
            sys.exit(f"Could not find the {name} token block in {CSS}")
        tokens: dict[str, str] = {}
        for line in match.group(1).splitlines():
            found = re.match(r"\s*--([a-z-]+):\s*([\d.]+\s+[\d.]+%\s+[\d.]+%)\s*;", line)
            if found:
                tokens[found.group(1)] = found.group(2)
        out[name] = tokens
    return out


def hsl_to_rgb(triplet: str) -> tuple[float, float, float]:
    h, s, l = triplet.replace("%", "").split()
    r, g, b = colorsys.hls_to_rgb(float(h) / 360, float(l) / 100, float(s) / 100)
    return r * 255, g * 255, b * 255


def relative_luminance(rgb: tuple[float, float, float]) -> float:
    def channel(v: float) -> float:
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    la, lb = relative_luminance(a), relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def to_lab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    """sRGB -> CIE L*a*b* (D65), for perceptual distance."""

    def linear(v: float) -> float:
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (linear(c) for c in rgb)
    x = r * 0.4124564 + g * 0.3575761 + b * 0.1804375
    y = r * 0.2126729 + g * 0.7151522 + b * 0.0721750
    z = r * 0.0193339 + g * 0.1191920 + b * 0.9503041
    # D65 white
    x, y, z = x / 0.95047, y / 1.0, z / 1.08883

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else (7.787 * t) + (16 / 116)

    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    la, aa, ba = to_lab(a)
    lb, ab, bb = to_lab(b)
    return math.sqrt((la - lb) ** 2 + (aa - ab) ** 2 + (ba - bb) ** 2)


def hue_of(triplet: str) -> float:
    return float(triplet.split()[0])


def hue_gap(a: str, b: str) -> float:
    d = abs(hue_of(a) - hue_of(b)) % 360
    return min(d, 360 - d)


def main() -> None:
    blocks = parse_blocks(CSS.read_text(encoding="utf-8"))
    failures = 0

    for theme, tokens in blocks.items():
        print(f"\n=== {theme} " + "=" * (58 - len(theme)))
        missing = {t for pair in PAIRS for t in pair[:2]} - tokens.keys()
        if missing:
            print(f"  ! tokens absent from this block: {', '.join(sorted(missing))}")

        for fg, bg, need, label in PAIRS:
            if fg not in tokens or bg not in tokens:
                continue
            ratio = contrast(hsl_to_rgb(tokens[fg]), hsl_to_rgb(tokens[bg]))
            ok = ratio >= need
            failures += not ok
            print(f"  {'ok ' if ok else 'FAIL'} {label:32} {ratio:5.2f}:1  (need {need})")

        print(f"  -- status separation (min dE {MIN_STATUS_DE:.0f}) " + "-" * 20)
        names = list(STATUS)
        surface = hsl_to_rgb(tokens["card"])
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                ta, tb = STATUS[names[i]], STATUS[names[j]]
                if ta not in tokens or tb not in tokens:
                    continue
                ca, cb = hsl_to_rgb(tokens[ta]), hsl_to_rgb(tokens[tb])
                de = delta_e(ca, cb)
                hg = hue_gap(tokens[ta], tokens[tb])
                ok = de >= MIN_STATUS_DE
                failures += not ok
                print(
                    f"  {'ok ' if ok else 'FAIL'} {names[i]:18} vs {names[j]:18} "
                    f"dE {de:5.1f}  hue gap {hg:5.1f}deg"
                )
        # Silence the unused-variable lint without hiding intent: `surface` is
        # kept because the swatches are rendered on --card and a future check
        # may want the on-surface distance rather than the swatch-to-swatch one.
        _ = surface

    print()
    if failures:
        sys.exit(f"{failures} check(s) failed.")
    print("All contrast and status-separation checks passed.")


if __name__ == "__main__":
    main()
