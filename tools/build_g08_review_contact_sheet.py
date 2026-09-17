#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

LABELS = (
    "cinematic-hook",
    "cinematic-escalation",
    "cinematic-counterattack",
    "cinematic-reversal",
    "cinematic-climax",
    "cinematic-payoff",
    "impact",
    "aftermath",
)


def find_image(directory: Path, label: str) -> Path | None:
    matches = sorted(directory.glob(f"preview-{label}-f*.png"))
    if not matches and label in {"impact", "aftermath"}:
        matches = sorted(directory.glob(f"preview-{label}-f*.png"))
    return matches[0] if matches else None


def fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    return ImageOps.fit(image.convert("RGB"), size, method=Image.Resampling.LANCZOS)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bugatti-dir", required=True)
    parser.add_argument("--generic-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    sources = [
        ("Exact Bugatti", Path(args.bugatti_dir)),
        ("Generic Hypercar", Path(args.generic_dir)),
    ]
    tile = (270, 480)
    label_h = 34
    header_h = 52
    margin = 10
    width = margin + len(LABELS) * (tile[0] + margin)
    height = margin + len(sources) * (header_h + tile[1] + label_h + margin)
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()

    y = margin
    missing: list[str] = []
    for name, directory in sources:
        draw.text((margin, y + 8), name, fill="black", font=font)
        y += header_h
        x = margin
        for label in LABELS:
            path = find_image(directory, label)
            if path is None:
                missing.append(f"{name}:{label}")
                block = Image.new("RGB", tile, "white")
                bd = ImageDraw.Draw(block)
                bd.rectangle((0, 0, tile[0] - 1, tile[1] - 1), outline="black")
                bd.text((10, 10), "MISSING", fill="black", font=font)
            else:
                with Image.open(path) as src:
                    block = fit(src, tile)
            canvas.paste(block, (x, y))
            draw.text((x, y + tile[1] + 7), label, fill="black", font=font)
            x += tile[0] + margin
        y += tile[1] + label_h + margin

    if missing:
        raise SystemExit("G08_CONTACT_SHEET_REQUIRED_IMAGE_MISSING:" + ",".join(missing))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, quality=92)
    if not output.is_file() or output.stat().st_size < 20_000:
        raise SystemExit("G08_CONTACT_SHEET_INVALID")
    print(f"G08_REVIEW_CONTACT_SHEET=PASS:{output}:{output.stat().st_size}")


if __name__ == "__main__":
    main()
