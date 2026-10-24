"""
Smartphone / Tablet Launcher Icon Generator & Normalizer.
Generates square (1:1) and rounded adaptive icons if converting a TV-only APK to Smartphone.
"""

import os
import glob
from pathlib import Path
from PIL import Image, ImageDraw

DENSITIES = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}

def ensure_smartphone_icons(decoded_dir: Path, app_label: str = "Android App") -> str:
    """
    Checks if valid launcher icons exist. If absent or only banners exist,
    synthesizes crisp square and circular launcher icons across mipmap densities.
    Returns: '@mipmap/ic_launcher'
    """
    existing_icons = glob.glob(str(decoded_dir / "res" / "mipmap*" / "*launcher*.png")) + \
                     glob.glob(str(decoded_dir / "res" / "drawable*" / "*launcher*.png"))
    if existing_icons:
        # Valid icon already exists
        return "@mipmap/ic_launcher" if any("mipmap" in x for x in existing_icons) else "@drawable/ic_launcher"

    # Search for any banner image to crop or extract from
    banner_matches = glob.glob(str(decoded_dir / "res" / "drawable*" / "*banner*.png"))
    base_img = None
    if banner_matches:
        try:
            b_img = Image.open(banner_matches[0]).convert("RGBA")
            # Crop square center
            bw, bh = b_img.size
            sq_size = min(bw, bh)
            left = (bw - sq_size) // 2
            top = (bh - sq_size) // 2
            base_img = b_img.crop((left, top, left + sq_size, top + sq_size))
        except Exception:
            base_img = None

    if base_img is None:
        # Create stylish modern square icon
        base_img = Image.new("RGBA", (512, 512), (30, 27, 75, 255))
        draw = ImageDraw.Draw(base_img)
        for y in range(512):
            r = int(30 + (15 - 30) * (y / 512))
            g = int(27 + (118 - 27) * (y / 512))
            b = int(75 + (110 - 75) * (y / 512))
            draw.line([(0, y), (512, y)], fill=(r, g, b, 255))
        
        draw.rounded_rectangle([40, 40, 472, 472], radius=90, outline=(56, 189, 248, 255), width=10)
        # Mobile glyph
        draw.rounded_rectangle([160, 100, 352, 412], radius=40, outline=(241, 245, 249, 255), width=12, fill=(15, 23, 42, 220))
        draw.line([(230, 130), (282, 130)], fill=(241, 245, 249, 255), width=6)
        draw.ellipse([240, 350, 272, 382], fill=(56, 189, 248, 255))

    # Generate across densities
    for folder, size in DENSITIES.items():
        target_dir = decoded_dir / "res" / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Standard icon
        square = base_img.resize((size, size), Image.Resampling.LANCZOS)
        square.save(target_dir / "ic_launcher.png", format="PNG")

        # Round icon
        round_img = square.copy()
        mask = Image.new("L", (size, size), 0)
        mask_draw = ImageDraw.Draw(mask)
        mask_draw.ellipse([0, 0, size, size], fill=255)
        round_img.putalpha(mask)
        round_img.save(target_dir / "ic_launcher_round.png", format="PNG")

    return "@mipmap/ic_launcher"
