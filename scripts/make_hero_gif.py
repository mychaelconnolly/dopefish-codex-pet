#!/usr/bin/env python3
"""Render docs/hero.gif: a looping hero reel from built pet frames.

Requires build/frames from scripts/build_exact_dopefish.py. Frame timings
mirror the Codex app durations documented in the hatch-pet skill's
animation-rows.md.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
FRAMES = ROOT / "build/frames"
OUT = ROOT / "docs/hero.gif"

HERO_SCALE = 2
TRANSPARENT_INDEX = 255

# (state, per-frame durations ms, loops)
SEQUENCE = [
    ("idle", [280, 110, 110, 140, 140, 320], 2),
    ("running-right", [120] * 7 + [220], 2),
    ("waving", [140] * 3 + [280], 3),
    ("failed", [140] * 7 + [240], 1),
]


def to_gif_frame(rgba: Image.Image) -> Image.Image:
    scaled = rgba.resize(
        (rgba.width * HERO_SCALE, rgba.height * HERO_SCALE),
        Image.Resampling.NEAREST,
    )
    alpha = scaled.getchannel("A")
    frame = scaled.convert("RGB").convert("P", palette=Image.ADAPTIVE, colors=255)
    frame.paste(TRANSPARENT_INDEX, alpha.point(lambda a: 255 if a < 128 else 0))
    return frame


def main() -> None:
    frames: list[Image.Image] = []
    durations: list[int] = []
    for state, state_durations, loops in SEQUENCE:
        cells = sorted((FRAMES / state).glob("*.png"))
        if len(cells) != len(state_durations):
            raise SystemExit(
                f"{state}: expected {len(state_durations)} frames, got {len(cells)}"
            )
        rendered = [to_gif_frame(Image.open(path).convert("RGBA")) for path in cells]
        for _ in range(loops):
            frames.extend(rendered)
            durations.extend(state_durations)

    frames[0].save(
        OUT,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        disposal=2,
        transparency=TRANSPARENT_INDEX,
    )
    print(f"wrote {OUT} ({len(frames)} frames)")


if __name__ == "__main__":
    main()
