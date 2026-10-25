"""
Android TV Leanback Banner Generator & Manager.
Standard Android TV banners require a 16:9 aspect ratio, typically 320x180 dp (320x180 px for mdpi, 640x360 px for xhdpi).
Supports dynamic AI theme palettes, custom taglines, and brand badges.
"""

import os
import glob
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BUNDLED_FONT = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "AppFont-Bold.ttf"

COLOR_THEMES = {
    "cyan_indigo": {
        "bg_top": (18, 24, 38),
        "bg_bottom": (30, 41, 70),
        "border": (56, 189, 248, 110),
        "accent": (147, 51, 234, 70),
        "glow": (56, 189, 248, 90),
        "badge_border": (56, 189, 248, 200),
        "text": (241, 245, 249)
    },
    "amber_purple": {
        "bg_top": (26, 16, 37),
        "bg_bottom": (45, 20, 60),
        "border": (251, 191, 36, 110),
        "accent": (217, 70, 239, 70),
        "glow": (251, 191, 36, 90),
        "badge_border": (251, 191, 36, 200),
        "text": (254, 243, 199)
    },
    "emerald_slate": {
        "bg_top": (10, 30, 25),
        "bg_bottom": (15, 45, 38),
        "border": (52, 211, 153, 110),
        "accent": (16, 185, 129, 70),
        "glow": (52, 211, 153, 90),
        "badge_border": (52, 211, 153, 200),
        "text": (236, 253, 245)
    },
    "crimson_night": {
        "bg_top": (35, 15, 20),
        "bg_bottom": (55, 20, 30),
        "border": (248, 113, 113, 110),
        "accent": (239, 68, 68, 70),
        "glow": (248, 113, 113, 90),
        "badge_border": (248, 113, 113, 200),
        "text": (254, 242, 242)
    }
}

def find_best_app_icon(decoded_dir: Path) -> Optional[Path]:
    patterns = [
        "res/mipmap-xxxhdpi/*launcher*.png",
        "res/mipmap-xxhdpi/*launcher*.png",
        "res/mipmap-xhdpi/*launcher*.png",
        "res/mipmap-hdpi/*launcher*.png",
        "res/mipmap-mdpi/*launcher*.png",
        "res/drawable-xxxhdpi/*launcher*.png",
        "res/drawable-xxhdpi/*launcher*.png",
        "res/drawable-xhdpi/*launcher*.png",
        "res/drawable/*launcher*.png",
        "res/mipmap*/*.png",
        "res/drawable*/*.png",
    ]
    for pattern in patterns:
        matches = glob.glob(str(decoded_dir / pattern))
        if matches:
            matches.sort(key=lambda p: os.path.getsize(p), reverse=True)
            return Path(matches[0])
    return None

def generate_tv_banner(
    decoded_dir: Path,
    app_label: str = "Android TV App",
    custom_banner_path: Path | str | None = None,
    width: int = 640,
    height: int = 360,
    tagline: Optional[str] = None,
    color_theme: str = "cyan_indigo",
    badge_text: str = "ANDROID TV EDITION"
) -> str:
    """
    Creates or places a 16:9 Android TV Leanback banner.
    Saves to res/drawable-xhdpi/tv_banner.png and res/drawable/tv_banner.png.
    Returns resource reference: '@drawable/tv_banner'
    """
    drawable_dir = decoded_dir / "res" / "drawable-xhdpi"
    drawable_fallback = decoded_dir / "res" / "drawable"
    drawable_dir.mkdir(parents=True, exist_ok=True)
    drawable_fallback.mkdir(parents=True, exist_ok=True)

    banner_target_xhdpi = drawable_dir / "tv_banner.png"
    banner_target_base = drawable_fallback / "tv_banner.png"

    if custom_banner_path and Path(custom_banner_path).is_file():
        img = Image.open(custom_banner_path).convert("RGBA")
        img = img.resize((width, height), Image.Resampling.LANCZOS)
        img.save(banner_target_xhdpi, format="PNG")
        img.save(banner_target_base, format="PNG")
        return "@drawable/tv_banner"

    theme = COLOR_THEMES.get(color_theme, COLOR_THEMES["cyan_indigo"])
    banner = Image.new("RGBA", (width, height), (15, 23, 42, 255))
    draw = ImageDraw.Draw(banner)

    # Dynamic gradient background
    t_r, t_g, t_b = theme["bg_top"]
    b_r, b_g, b_b = theme["bg_bottom"]
    for y in range(height):
        r = int(t_r + (b_r - t_r) * (y / height))
        g = int(t_g + (b_g - t_g) * (y / height))
        b = int(t_b + (b_b - t_b) * (y / height))
        draw.line([(0, y), (width, y)], fill=(r, g, b, 255))

    # Glow & borders
    draw.rounded_rectangle([16, 16, width - 16, height - 16], radius=20, outline=theme["border"], width=3)
    draw.rounded_rectangle([22, 22, width - 22, height - 22], radius=16, outline=theme["accent"], width=2)

    icon_path = find_best_app_icon(decoded_dir)
    if icon_path and icon_path.is_file():
        try:
            icon_img = Image.open(icon_path).convert("RGBA")
            icon_size = 175
            icon_img = icon_img.resize((icon_size, icon_size), Image.Resampling.LANCZOS)

            x = (width - icon_size) // 2
            y = (height - icon_size) // 2 - 25

            glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow)
            glow_draw.ellipse([x - 20, y - 20, x + icon_size + 20, y + icon_size + 20], fill=theme["glow"])
            glow = glow.filter(ImageFilter.GaussianBlur(16))
            banner.alpha_composite(glow)

            banner.alpha_composite(icon_img, (x, y))
        except Exception:
            pass

    draw = ImageDraw.Draw(banner)
    font_path = str(BUNDLED_FONT) if BUNDLED_FONT.is_file() else "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

    # Display Tagline / Slogan
    final_badge = (tagline or badge_text or "ANDROID TV EDITION").upper()
    pill_w = min(420, max(260, len(final_badge) * 12 + 40))
    pill_h = 36
    pill_x = (width - pill_w) // 2
    pill_y = height - 60
    draw.rounded_rectangle([pill_x, pill_y, pill_x + pill_w, pill_y + pill_h], radius=18, fill=(15, 23, 42, 230), outline=theme["badge_border"], width=2)

    try:
        font = ImageFont.truetype(font_path, 14)
        text_bbox = draw.textbbox((0, 0), final_badge, font=font)
        tw = text_bbox[2] - text_bbox[0]
        th = text_bbox[3] - text_bbox[1]
        draw.text((pill_x + (pill_w - tw) // 2, pill_y + (pill_h - th) // 2 - 2), final_badge, fill=theme["text"], font=font)
    except Exception:
        draw.text((pill_x + 30, pill_y + 10), final_badge, fill=theme["text"])

    banner.save(banner_target_xhdpi, format="PNG")
    banner.save(banner_target_base, format="PNG")
    return "@drawable/tv_banner"
