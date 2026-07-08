#!/usr/bin/env python3
"""Build a Codex pet atlas from exact scaled Dopefish GIF pixels."""

from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from PIL import Image, ImageOps, ImageSequence


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "build"
SWIM_GIF = ROOT / "source/local-refs/swimfish2.gif"
CHOMP_STILL_GIF = ROOT / "source/local-refs/chomp-still.gif"
CHOMP_FULL_GIF = ROOT / "source/local-refs/chomp-full-animation.gif"
BURP_GIF = ROOT / "source/local-refs/burpfish.gif"
EXTRA_SHEET = ROOT / "source/local-refs/more-sprites-dopefish.png"
BUILD_ID = "dopefish-v0.14.0"

CELL_WIDTH = 192
CELL_HEIGHT = 208
SCALE = 2

ROW_SPECS = {
    "idle": 6,
    "running-right": 8,
    "running-left": 8,
    "waving": 4,
    "jumping": 5,
    "failed": 8,
    "waiting": 6,
    "running": 6,
    "review": 6,
}

BLACK = (0, 0, 0, 255)
BODY_GREEN = (0, 171, 0, 255)
WHITE = (255, 255, 255, 255)
BUBBLE_CYAN = (64, 255, 255, 255)
BUBBLE_ORANGE = (255, 154, 34, 255)

SHEET_BACKGROUND = (0, 128, 128, 255)
SHEET_CLEAR = (168, 0, 168, 255)
SHEET_LABEL_GREEN = (64, 255, 64, 255)

SHEET_SPRITE_CLEAR_COLORS = {
    SHEET_BACKGROUND,
    SHEET_CLEAR,
    SHEET_LABEL_GREEN,
    BUBBLE_CYAN,
    BUBBLE_ORANGE,
}
BUBBLE_CLEAR_COLORS = {SHEET_BACKGROUND, SHEET_CLEAR, SHEET_LABEL_GREEN}

EXTRA_SPRITE_BOXES = {
    "idle_front": (1, 25, 81, 97),
    "attack_ready": (36, 152, 112, 216),
    "charge": (35, 217, 121, 281),
    "charging": (30, 291, 118, 369),
}
BUBBLE_BOXES = {
    "white": (122, 137, 137, 152),
}


def load_frames(path: Path) -> list[Image.Image]:
    with Image.open(path) as source:
        frames = []
        for frame in ImageSequence.Iterator(source):
            rgba = frame.convert("RGBA")
            data = bytearray(rgba.tobytes())
            for index in range(0, len(data), 4):
                if data[index + 3] == 0:
                    data[index] = data[index + 1] = data[index + 2] = 0
            frames.append(Image.frombytes("RGBA", rgba.size, bytes(data)))
    if not frames:
        raise SystemExit(f"no frames in {path}")
    return frames


def visible_crop(frame: Image.Image) -> Image.Image:
    alpha = frame.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        raise SystemExit("source frame has no visible pixels")
    return frame.crop(bbox)


def clear_colors(image: Image.Image, colors: set[tuple[int, int, int, int]]) -> Image.Image:
    rgba = image.convert("RGBA")
    data = bytearray(rgba.tobytes())
    for index in range(0, len(data), 4):
        if tuple(data[index : index + 4]) in colors:
            data[index] = data[index + 1] = data[index + 2] = data[index + 3] = 0
    return Image.frombytes("RGBA", rgba.size, bytes(data))


def recolor_largest_white_component(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    seen: set[tuple[int, int]] = set()
    largest: list[tuple[int, int]] = []

    for y in range(height):
        for x in range(width):
            if (x, y) in seen or pixels[x, y] != WHITE:
                continue
            component: list[tuple[int, int]] = []
            queue: deque[tuple[int, int]] = deque([(x, y)])
            seen.add((x, y))
            while queue:
                cx, cy = queue.popleft()
                component.append((cx, cy))
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if (
                        0 <= nx < width
                        and 0 <= ny < height
                        and (nx, ny) not in seen
                        and pixels[nx, ny] == WHITE
                    ):
                        seen.add((nx, ny))
                        queue.append((nx, ny))
            if len(component) > len(largest):
                largest = component

    if not largest:
        raise SystemExit("new sprite crop has no white body component")
    for x, y in largest:
        pixels[x, y] = BODY_GREEN
    return rgba


def extract_sheet_sprite(sheet: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    sprite = sheet.crop(box)
    sprite = clear_colors(sprite, SHEET_SPRITE_CLEAR_COLORS)
    sprite = recolor_largest_white_component(sprite)
    return clear_transparent_rgb(visible_crop(sprite))


def extract_bubble(sheet: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    # source bubbles are black orbs with a white rim and shine; clearing the
    # black interior leaves a hollow, translucent-reading bubble
    sprite = sheet.crop(box)
    sprite = clear_colors(sprite, BUBBLE_CLEAR_COLORS | {BLACK})
    return clear_transparent_rgb(visible_crop(sprite))


def make_cell(
    source: Image.Image,
    *,
    flip: bool = False,
    offset: tuple[int, int] = (0, 0),
    scale: float = SCALE,
    squash: tuple[float, float] = (1.0, 1.0),
    overlays: list[tuple[Image.Image, tuple[int, int], float]] | None = None,
) -> Image.Image:
    sprite = visible_crop(source)
    sprite = sprite.resize(
        (round(sprite.width * scale * squash[0]), round(sprite.height * scale * squash[1])),
        Image.Resampling.NEAREST,
    )
    if flip:
        sprite = ImageOps.mirror(sprite)

    cell = Image.new("RGBA", (CELL_WIDTH, CELL_HEIGHT), (0, 0, 0, 0))
    left = (CELL_WIDTH - sprite.width) // 2 + offset[0]
    top = (CELL_HEIGHT - sprite.height) // 2 + offset[1]
    cell.alpha_composite(sprite, (left, top))
    for overlay, position, overlay_scale in overlays or []:
        overlay_sprite = visible_crop(overlay).resize(
            (round(overlay.width * overlay_scale), round(overlay.height * overlay_scale)),
            Image.Resampling.NEAREST,
        )
        cell.alpha_composite(overlay_sprite, position)
    return clear_transparent_rgb(cell)


def make_sheet_cell(
    source: Image.Image,
    *,
    flip: bool = False,
    offset: tuple[int, int] = (0, 0),
    scale: float = SCALE,
    overlays: list[tuple[Image.Image, tuple[int, int], float]] | None = None,
) -> Image.Image:
    return make_cell(source, flip=flip, offset=offset, scale=scale, overlays=overlays)


def make_left_cell(
    source: Image.Image,
    *,
    offset: tuple[int, int] = (0, 0),
    scale: float = SCALE,
    squash: tuple[float, float] = (1.0, 1.0),
    overlays: list[tuple[Image.Image, tuple[int, int], float]] | None = None,
) -> Image.Image:
    return make_cell(source, flip=True, offset=offset, scale=scale, squash=squash, overlays=overlays)


def make_rotated_cell(
    source: Image.Image,
    *,
    angle: float,
    flip: bool = False,
    offset: tuple[int, int] = (0, 0),
    scale: float = 1.8,
    overlays: list[tuple[Image.Image, tuple[int, int], float]] | None = None,
) -> Image.Image:
    sprite = visible_crop(source)
    sprite = sprite.resize(
        (round(sprite.width * scale), round(sprite.height * scale)),
        Image.Resampling.NEAREST,
    )
    if flip:
        sprite = ImageOps.mirror(sprite)
    sprite = sprite.rotate(
        angle,
        resample=Image.Resampling.NEAREST,
        expand=True,
        fillcolor=(0, 0, 0, 0),
    )
    sprite = visible_crop(sprite)

    cell = Image.new("RGBA", (CELL_WIDTH, CELL_HEIGHT), (0, 0, 0, 0))
    left = (CELL_WIDTH - sprite.width) // 2 + offset[0]
    top = (CELL_HEIGHT - sprite.height) // 2 + offset[1]
    cell.alpha_composite(sprite, (left, top))
    for overlay, position, overlay_scale in overlays or []:
        overlay_sprite = visible_crop(overlay).resize(
            (round(overlay.width * overlay_scale), round(overlay.height * overlay_scale)),
            Image.Resampling.NEAREST,
        )
        cell.alpha_composite(overlay_sprite, position)
    return clear_transparent_rgb(cell)


GRAYS = {(87, 87, 87, 255), (171, 171, 171, 255)}


def make_blink_frame(frame: Image.Image) -> Image.Image:
    rgba = frame.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    seen: set[tuple[int, int]] = set()
    eye_pixels: set[tuple[int, int]] = set()

    for y in range(height):
        for x in range(width):
            if (x, y) in seen or pixels[x, y] != WHITE:
                continue
            component: list[tuple[int, int]] = []
            queue: deque[tuple[int, int]] = deque([(x, y)])
            seen.add((x, y))
            while queue:
                cx, cy = queue.popleft()
                component.append((cx, cy))
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if (
                        0 <= nx < width
                        and 0 <= ny < height
                        and (nx, ny) not in seen
                        and pixels[nx, ny] == WHITE
                    ):
                        seen.add((nx, ny))
                        queue.append((nx, ny))
            centroid_y = sum(point[1] for point in component) / len(component)
            # eye whites sit in the top half of the sprite; teeth sit lower
            if centroid_y < height * 0.6:
                eye_pixels.update(component)

    if not eye_pixels:
        raise SystemExit("blink frame: no eye component found in source frame")

    # pull in the gray anti-alias fringe around the eye whites
    for _ in range(2):
        fringe = set()
        for x, y in eye_pixels:
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if (
                    0 <= nx < width
                    and 0 <= ny < height
                    and (nx, ny) not in eye_pixels
                    and pixels[nx, ny] in GRAYS
                ):
                    fringe.add((nx, ny))
        eye_pixels.update(fringe)

    # close each eye column by column: green the opening (whites, grays,
    # pupil blacks between them), keep the outer ring, and lay the lid as an
    # arc along the lower opening contour
    columns: dict[int, list[int]] = {}
    for x, y in eye_pixels:
        columns.setdefault(x, []).append(y)
    for x, ys in columns.items():
        y_top, y_bot = min(ys), max(ys)
        for y in range(y_top, y_bot + 1):
            if pixels[x, y][3]:
                pixels[x, y] = BODY_GREEN
        pixels[x, y_bot] = BLACK
    return rgba


def clear_transparent_rgb(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    data = bytearray(rgba.tobytes())
    for index in range(0, len(data), 4):
        if data[index + 3] == 0:
            data[index] = data[index + 1] = data[index + 2] = 0
    return Image.frombytes("RGBA", rgba.size, bytes(data))


def write_frames(state: str, frames: list[Image.Image]) -> None:
    expected = ROW_SPECS[state]
    if len(frames) != expected:
        raise SystemExit(f"{state}: expected {expected} frames, got {len(frames)}")
    state_dir = RUN / "frames" / state
    state_dir.mkdir(parents=True, exist_ok=True)
    for index, frame in enumerate(frames):
        frame.save(state_dir / f"{index:02d}.png")


def visible_colors(image: Image.Image) -> set[tuple[int, int, int, int]]:
    rgba = image.convert("RGBA")
    data = rgba.tobytes()
    colors: set[tuple[int, int, int, int]] = set()
    for index in range(0, len(data), 4):
        color = tuple(data[index : index + 4])
        if color[3]:
            colors.add(color)
    return colors


def collect_visible_palette(paths: list[Path]) -> list[list[int]]:
    colors: set[tuple[int, int, int, int]] = set()
    for path in paths:
        for frame in load_frames(path):
            colors.update(visible_colors(frame))
    return [list(color) for color in sorted(colors)]


def assert_palette(frames_root: Path, allowed: set[tuple[int, int, int, int]]) -> None:
    bad: dict[str, list[tuple[int, int, int, int]]] = {}
    for path in sorted(frames_root.glob("*/*.png")):
        with Image.open(path) as opened:
            rgba = opened.convert("RGBA")
            data = rgba.tobytes()
            for index in range(0, len(data), 4):
                color = tuple(data[index : index + 4])
                if color[3] == 0:
                    if color != (0, 0, 0, 0):
                        bad.setdefault(str(path), []).append(color)
                elif color not in allowed:
                    bad.setdefault(str(path), []).append(color)
        if path in bad:
            bad[str(path)] = sorted(set(bad[str(path)]))[:20]
    if bad:
        raise SystemExit(json.dumps({"palette_error": bad}, indent=2))


def load_extra_sprites() -> tuple[dict[str, Image.Image], dict[str, Image.Image]]:
    if not EXTRA_SHEET.exists():
        raise SystemExit(f"missing extra sprite sheet: {EXTRA_SHEET}")

    sheet = Image.open(EXTRA_SHEET).convert("RGBA")
    sprites = {name: extract_sheet_sprite(sheet, box) for name, box in EXTRA_SPRITE_BOXES.items()}
    bubbles = {name: extract_bubble(sheet, box) for name, box in BUBBLE_BOXES.items()}

    source_dir = RUN / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    for name, sprite in sprites.items():
        sprite.save(source_dir / f"sheet-{name}.png")
    for name, bubble in bubbles.items():
        bubble.save(source_dir / f"bubble-{name}.png")

    return sprites, bubbles


def main() -> None:
    RUN.mkdir(parents=True, exist_ok=True)
    for dirname in ("frames", "final", "qa", "source"):
        (RUN / dirname).mkdir(parents=True, exist_ok=True)

    swim = load_frames(SWIM_GIF)
    chomp_still = load_frames(CHOMP_STILL_GIF)
    chomp_full = load_frames(CHOMP_FULL_GIF)
    burp = load_frames(BURP_GIF)
    sheet_sprites, bubbles = load_extra_sprites()
    if len(swim) < 2 or not chomp_still or len(chomp_full) < 8 or len(burp) < 2:
        raise SystemExit("expected swim, still chomp, full chomp, and burp GIF frames")

    # body-height continuity: chomp frames at 1.0 must match swim at SCALE
    swim_height = visible_crop(swim[0]).height * SCALE
    chomp_height = visible_crop(chomp_full[0]).height
    if abs(swim_height - chomp_height) > 4:
        raise SystemExit(
            f"body height mismatch: swim {swim_height}px vs chomp {chomp_height}px"
        )

    blink = make_blink_frame(swim[0])
    burp_blink = make_blink_frame(burp[0])

    write_frames(
        "idle",
        [
            make_left_cell(swim[0], offset=(0, 0)),
            make_left_cell(swim[1], offset=(0, 2)),
            make_left_cell(swim[0], offset=(0, 0)),
            make_left_cell(blink, offset=(0, 0)),
            make_left_cell(swim[0], offset=(0, 0)),
            make_left_cell(swim[1], offset=(0, 2)),
        ],
    )
    write_frames(
        "running-right",
        [
            make_left_cell(chomp_full[0], offset=(0, 0), scale=1.0),
            make_left_cell(chomp_full[1], offset=(0, 2), scale=1.0),
            make_left_cell(chomp_full[0], offset=(0, 4), scale=1.0),
            make_left_cell(chomp_full[1], offset=(0, 2), scale=1.0),
            make_left_cell(chomp_full[7], offset=(0, 0), scale=1.0),
            make_left_cell(chomp_full[1], offset=(0, -2), scale=1.0),
            make_left_cell(chomp_full[0], offset=(0, -4), scale=1.0),
            make_left_cell(chomp_full[7], offset=(0, -2), scale=1.0),
        ],
    )
    write_frames(
        "running-left",
        [
            make_left_cell(swim[0], offset=(0, 0)),
            make_left_cell(swim[1], offset=(0, 2)),
            make_left_cell(swim[0], offset=(0, 4)),
            make_left_cell(swim[1], offset=(0, 2)),
            make_left_cell(swim[0], offset=(0, 0)),
            make_left_cell(swim[1], offset=(0, -2)),
            make_left_cell(swim[0], offset=(0, -4)),
            make_left_cell(swim[1], offset=(0, -2)),
        ],
    )
    write_frames(
        "waving",
        [
            make_cell(burp[0], offset=(0, 0)),
            make_cell(burp[1], offset=(0, 2)),
            make_cell(burp[0], offset=(0, 0)),
            make_cell(burp[1], offset=(0, -2)),
        ],
    )
    write_frames(
        "jumping",
        [
            make_left_cell(swim[0], offset=(0, 18), squash=(1.04, 0.92)),
            make_left_cell(swim[1], offset=(0, -8)),
            make_left_cell(swim[0], offset=(0, -28)),
            make_left_cell(swim[1], offset=(0, -12), squash=(0.97, 1.06)),
            make_left_cell(swim[0], offset=(0, 10)),
        ],
    )
    write_frames(
        "failed",
        [
            make_rotated_cell(swim[0], flip=True, angle=0, offset=(0, 0)),
            make_rotated_cell(swim[1], flip=True, angle=-30, offset=(0, 0)),
            make_rotated_cell(swim[0], flip=True, angle=-60, offset=(0, 0)),
            make_rotated_cell(swim[1], flip=True, angle=-90, offset=(0, 0)),
            make_rotated_cell(swim[0], flip=True, angle=-120, offset=(0, 0)),
            make_rotated_cell(
                swim[1],
                flip=True,
                angle=-150,
                offset=(0, 2),
                overlays=[(bubbles["white"], (142, 78), 1.5)],
            ),
            make_rotated_cell(
                swim[0],
                flip=True,
                angle=-180,
                offset=(0, 6),
                overlays=[(bubbles["white"], (148, 46), 2.0)],
            ),
            make_rotated_cell(
                swim[0],
                flip=True,
                angle=-180,
                offset=(0, 10),
                overlays=[(bubbles["white"], (140, 16), 2.0)],
            ),
        ],
    )
    write_frames(
        "waiting",
        [
            make_left_cell(swim[0], offset=(0, 0), overlays=[(bubbles["white"], (10, 116), 1.5)]),
            make_left_cell(swim[1], offset=(0, 1), overlays=[(bubbles["white"], (14, 100), 1.5)]),
            make_left_cell(swim[0], offset=(0, 2), overlays=[(bubbles["white"], (4, 82), 2.0)]),
            make_left_cell(swim[1], offset=(0, 2), overlays=[(bubbles["white"], (10, 64), 2.0)]),
            make_left_cell(swim[0], offset=(0, 1), overlays=[(bubbles["white"], (4, 46), 1.5)]),
            make_left_cell(swim[1], offset=(0, 0), overlays=[(bubbles["white"], (10, 28), 1.5)]),
        ],
    )
    write_frames(
        "running",
        [
            make_left_cell(swim[0], offset=(0, 0)),
            make_left_cell(swim[1], offset=(0, 2)),
            make_cell(chomp_still[0], offset=(0, 0)),
            make_left_cell(chomp_full[7], offset=(0, 0), scale=1.0),
            make_cell(chomp_still[0], offset=(0, 0)),
            make_left_cell(swim[1], offset=(0, 2)),
        ],
    )
    write_frames(
        "review",
        [
            make_cell(burp[0], offset=(0, 0)),
            make_cell(burp[0], offset=(0, 1)),
            make_cell(burp[0], offset=(0, 2)),
            make_cell(burp_blink, offset=(0, 2)),
            make_cell(burp[0], offset=(0, 1)),
            make_cell(burp[0], offset=(0, 0)),
        ],
    )

    allowed_palette = {
        tuple(color)
        for color in collect_visible_palette(
            [SWIM_GIF, CHOMP_STILL_GIF, CHOMP_FULL_GIF, BURP_GIF]
        )
    }
    for sprite in list(sheet_sprites.values()) + list(bubbles.values()):
        allowed_palette.update(visible_colors(sprite))
    assert_palette(RUN / "frames", allowed_palette)

    manifest = {
        "ok": True,
        "source_assets": [
            str(SWIM_GIF),
            str(CHOMP_STILL_GIF),
            str(CHOMP_FULL_GIF),
            str(BURP_GIF),
            str(EXTRA_SHEET),
        ],
        "scale": SCALE,
        "cell": {"width": CELL_WIDTH, "height": CELL_HEIGHT},
        "visible_palette_rgba": [list(color) for color in sorted(allowed_palette)],
        "rows": [
            {
                "state": state,
                "frames": ROW_SPECS[state],
                "method": "components",
                "build_method": BUILD_ID,
            }
            for state in ROW_SPECS
        ],
    }
    (RUN / "frames/frames-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    request = {
        "pet_id": "dopefish",
        "display_name": "Dopefish",
        "description": "The second-dumbest creature in the universe",
        "source_assets": [
            str(SWIM_GIF),
            str(CHOMP_STILL_GIF),
            str(CHOMP_FULL_GIF),
            str(BURP_GIF),
            str(EXTRA_SHEET),
        ],
        "atlas": {
            "columns": 8,
            "rows": 9,
            "cell_width": CELL_WIDTH,
            "cell_height": CELL_HEIGHT,
            "width": 1536,
            "height": 1872,
        },
        "build": BUILD_ID,
    }
    (RUN / "pet_request.json").write_text(json.dumps(request, indent=2) + "\n")

    print(json.dumps({"ok": True, "run_dir": str(RUN)}, indent=2))


if __name__ == "__main__":
    main()
