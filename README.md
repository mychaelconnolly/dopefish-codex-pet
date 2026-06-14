# Dopefish Codex Pet

A calm source-pixel Dopefish fan-art pet for Codex, with chomp-then-burp accents in waiting and running states.

![Dopefish contact sheet](docs/contact-sheet.png)

## Install

After this repository is published at `mychaelconnolly/dopefish-codex-pet`, use:

[Install Dopefish in Codex](codex://pets/install?name=Dopefish&imageUrl=https%3A%2F%2Fraw.githubusercontent.com%2Fmychaelconnolly%2Fdopefish-codex-pet%2Fmain%2Fpets%2Fdopefish%2Fspritesheet.webp&description=A%20calm%20source-pixel%20Dopefish%20fan-art%20pet%20for%20Codex.)

Manual install:

```bash
mkdir -p "$HOME/.codex/pets/dopefish"
cp pets/dopefish/pet.json pets/dopefish/spritesheet.webp "$HOME/.codex/pets/dopefish/"
```

Then open Codex, go to **Settings > Appearance > Pets**, and refresh custom pets
from your local Codex home.

## Package

The installable pet lives in:

```text
pets/dopefish/pet.json
pets/dopefish/spritesheet.webp
```

Current build:

```text
exact-source-nearest-neighbor-scale-v8-running-waiting-chomp
```

Current `spritesheet.webp` SHA-256:

```text
6cbfdc7ced63fb72b4611f4e8ccfc44c6b936691ba1e20f88326453b306cc56e
```

## Rebuild

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

Build source frames into `build/`:

```bash
python3 scripts/build_exact_dopefish.py
```

Compose and validate the Codex atlas with the `hatch-pet` skill scripts:

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/hatch-pet"
python3 "$SKILL_DIR/scripts/inspect_frames.py" \
  --frames-root build/frames \
  --json-out build/qa/review.json \
  --require-components
python3 "$SKILL_DIR/scripts/compose_atlas.py" \
  --frames-root build/frames \
  --output build/final/spritesheet.png \
  --webp-output build/final/spritesheet.webp
python3 "$SKILL_DIR/scripts/validate_atlas.py" \
  build/final/spritesheet.webp \
  --json-out build/final/validation.json
python3 "$SKILL_DIR/scripts/make_contact_sheet.py" \
  build/final/spritesheet.webp \
  --output build/qa/contact-sheet.png
python3 "$SKILL_DIR/scripts/render_animation_previews.py" \
  --frames-root build/frames \
  --output-dir build/qa/previews
```

Update the packaged pet after validation:

```bash
cp build/final/spritesheet.webp pets/dopefish/spritesheet.webp
```

## Notes

This is unofficial fan art. It is not affiliated with or endorsed by id Software,
Bethesda, Microsoft, or any rights holder. See [NOTICE.md](NOTICE.md).
