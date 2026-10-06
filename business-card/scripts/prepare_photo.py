"""Crop a portrait to a square and save it as site/photo.jpg (600x600).

    python3 business-card/scripts/prepare_photo.py my-photo.jpg              # centre crop, biased up
    python3 business-card/scripts/prepare_photo.py my-photo.jpg X Y SIZE     # explicit square (pixels)
"""
import sys
from pathlib import Path

from PIL import Image, ImageOps

OUT = Path(__file__).resolve().parent.parent / "site" / "photo.jpg"


def main() -> None:
    src = Path(sys.argv[1])
    img = ImageOps.exif_transpose(Image.open(src)).convert("RGB")
    w, h = img.size
    if len(sys.argv) == 5:
        x, y, size = map(int, sys.argv[2:5])
    else:
        size = min(w, h)
        x = (w - size) // 2
        y = max(0, min(h - size, int((h - size) * 0.25)))  # faces usually sit in the upper part
    img = img.crop((x, y, x + size, y + size)).resize((600, 600), Image.LANCZOS)
    img.save(OUT, "JPEG", quality=86, optimize=True, progressive=True)
    print(f"{src} -> {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
