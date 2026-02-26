"""Generate stylized pack icons for OpenPeon sound packs.

Creates 256x256 PNG icons from web-sourced actor photos (Wikipedia/IMDB)
with themed borders and character name overlay.
Falls back to Pillow-drawn icons if web fetch fails.
Registry spec: 256x256 px, PNG/JPEG/WebP/SVG, max 500KB per icon.
"""
import hashlib
import math
import os
import re
import time
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


PACKS_DIR = os.path.expanduser("~/Development/openpeon-movie-packs")

# Wikipedia article titles for actor headshots
# Format: pack_name -> {"actor": "Wikipedia_article_title", "character": "display name", ...theme}
PACK_THEMES = {
    # Big Lebowski
    "lebowski_the_dude": {
        "bg": "#5B3A29", "accent": "#F5DEB3", "icon": "bowling", "initials": "TD",
        "actor": "Jeff_Bridges", "character": "The Dude",
    },
    "lebowski_walter": {
        "bg": "#556B2F", "accent": "#FFD700", "icon": "gun", "initials": "WS",
        "actor": "John_Goodman", "character": "Walter",
    },
    "lebowski_jesus": {
        "bg": "#800080", "accent": "#FF69B4", "icon": "bowling", "initials": "JQ",
        "actor": "John_Turturro", "character": "Jesus",
    },
    "lebowski_maude": {
        "bg": "#8B0000", "accent": "#DDA0DD", "icon": "art", "initials": "ML",
        "actor": "Julianne_Moore", "character": "Maude",
    },
    "lebowski_big_lebowski": {
        "bg": "#191970", "accent": "#C0C0C0", "icon": "money", "initials": "BL",
        "actor": "David_Huddleston", "character": "Big Lebowski",
    },
    # Starship Troopers
    "starship_rico": {
        "bg": "#2F4F4F", "accent": "#FF4500", "icon": "star", "initials": "JR",
        "actor": "Casper_Van_Dien", "character": "Rico",
    },
    "starship_rasczak": {
        "bg": "#3B3B3B", "accent": "#B22222", "icon": "star", "initials": "LR",
        "actor": "Michael_Ironside", "character": "Rasczak",
    },
    # Super Troopers
    "super_troopers": {
        "bg": "#004225", "accent": "#DAA520", "icon": "badge", "initials": "ST",
        "actor": "Super_Troopers", "character": "Troopers",
    },
    "super_troopers_farva": {
        "bg": "#8B4513", "accent": "#FFD700", "icon": "badge", "initials": "F!",
        "actor": "Kevin_Heffernan_(actor)", "character": "Farva",
    },
    # Blues Brothers
    "blues_brothers_jake": {
        "bg": "#000000", "accent": "#FFFFFF", "icon": "sunglasses", "initials": "JB",
        "actor": "John_Belushi", "character": "Jake",
    },
    "blues_brothers_elwood": {
        "bg": "#1C1C1C", "accent": "#4169E1", "icon": "sunglasses", "initials": "EB",
        "actor": "Dan_Aykroyd", "character": "Elwood",
    },
    "blues_brothers": {
        "bg": "#000000", "accent": "#4169E1", "icon": "sunglasses", "initials": "BB",
        "actor": "The_Blues_Brothers", "character": "Blues Bros",
    },
    # Anchorman
    "anchorman_burgundy": {
        "bg": "#800020", "accent": "#FFD700", "icon": "mic", "initials": "RB",
        "actor": "Will_Ferrell", "character": "Burgundy",
    },
    "anchorman_brick": {
        "bg": "#FF6347", "accent": "#FFFFE0", "icon": "lamp", "initials": "BT",
        "actor": "Steve_Carell", "character": "Brick",
    },
    "anchorman_news_team": {
        "bg": "#4B0082", "accent": "#FFD700", "icon": "mic", "initials": "C4",
        "actor": "Anchorman:_The_Legend_of_Ron_Burgundy", "character": "News Team",
    },
    # Zoolander
    "zoolander_derek": {
        "bg": "#4682B4", "accent": "#C0C0C0", "icon": "face", "initials": "DZ",
        "actor": "Ben_Stiller", "character": "Derek",
    },
    "zoolander_hansel": {
        "bg": "#FF8C00", "accent": "#FFFAF0", "icon": "face", "initials": "H!",
        "actor": "Owen_Wilson", "character": "Hansel",
    },
    # Ghostbusters
    "ghostbusters_venkman": {
        "bg": "#2E8B57", "accent": "#FF0000", "icon": "ghost", "initials": "PV",
        "actor": "Bill_Murray", "character": "Venkman",
    },
    "ghostbusters_ray": {
        "bg": "#3CB371", "accent": "#FFD700", "icon": "ghost", "initials": "RS",
        "actor": "Dan_Aykroyd", "character": "Ray",
    },
    "ghostbusters_egon": {
        "bg": "#006400", "accent": "#00CED1", "icon": "ghost", "initials": "ES",
        "actor": "Harold_Ramis", "character": "Egon",
    },
    # Office Space
    "office_space": {
        "bg": "#708090", "accent": "#B22222", "icon": "stapler", "initials": "OS",
        "actor": "Office_Space", "character": "Office Space",
    },
    "office_space_lumbergh": {
        "bg": "#2F4F4F", "accent": "#FFD700", "icon": "coffee", "initials": "BL",
        "actor": "Gary_Cole", "character": "Lumbergh",
    },
    "office_space_peter": {
        "bg": "#696969", "accent": "#87CEEB", "icon": "stapler", "initials": "PG",
        "actor": "Ron_Livingston", "character": "Peter",
    },
}


def hex_to_rgb(hex_color):
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def fetch_wikipedia_image(article_title, size=500):
    """Fetch the main image from a Wikipedia article.

    Returns PIL Image or None on failure.
    """
    try:
        resp = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "titles": article_title,
                "prop": "pageimages",
                "format": "json",
                "pithumbsize": size,
            },
            headers={"User-Agent": "OpenPeon/1.0 (icon generator; personal use)"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            thumb = page.get("thumbnail", {})
            img_url = thumb.get("source")
            if img_url:
                img_resp = requests.get(
                    img_url,
                    headers={"User-Agent": "OpenPeon/1.0"},
                    timeout=15,
                )
                img_resp.raise_for_status()
                return Image.open(BytesIO(img_resp.content)).convert("RGB")
    except Exception as e:
        print(f"  Wikipedia fetch failed for '{article_title}': {e}")
    return None


def process_portrait(img, size=256, border_color=None, border_width=6):
    """Crop to square, resize, optionally add colored border."""
    w, h = img.size
    s = min(w, h)
    left = (w - s) // 2
    top = (h - s) // 2
    img = img.crop((left, top, left + s, top + s))
    img = img.resize((size, size), Image.LANCZOS)

    if border_color:
        bordered = Image.new("RGB", (size, size), hex_to_rgb(border_color))
        inner_size = size - 2 * border_width
        inner = img.resize((inner_size, inner_size), Image.LANCZOS)
        bordered.paste(inner, (border_width, border_width))
        img = bordered

    return img


def add_character_label(img, character_name, accent_color, size=256):
    """Add character name label at the bottom of the image."""
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size // 10)
    except Exception:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", size // 10)
        except Exception:
            font = ImageFont.load_default()

    text = character_name.upper()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    # Semi-transparent background bar
    bar_height = th + 12
    bar_y = size - bar_height
    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle([0, bar_y, size, size], fill=(0, 0, 0, 160))

    img_rgba = img.convert("RGBA")
    img_rgba = Image.alpha_composite(img_rgba, overlay)
    img = img_rgba.convert("RGB")

    draw = ImageDraw.Draw(img)
    tx = (size - tw) // 2
    ty = bar_y + 6
    color = hex_to_rgb(accent_color) if isinstance(accent_color, str) else accent_color
    draw.text((tx, ty), text, fill=color, font=font)

    return img


def generate_web_icon(pack_name, size=256):
    """Generate an icon by fetching the actor's photo from Wikipedia.

    Returns (PIL Image, source_info) or (None, error_info).
    """
    theme = PACK_THEMES.get(pack_name)
    if not theme or "actor" not in theme:
        return None, "no_theme"

    actor = theme["actor"]
    character = theme.get("character", pack_name)
    accent = theme.get("accent", "#FFFFFF")
    bg = theme.get("bg", "#333333")

    img = fetch_wikipedia_image(actor, size=500)
    if img is None:
        return None, f"fetch_failed:{actor}"

    img = process_portrait(img, size=size, border_color=bg, border_width=6)
    img = add_character_label(img, character, accent, size=size)

    return img, f"wikipedia:{actor}"


# --- Fallback: Pillow-drawn icons (original) ---

def draw_bowling_icon(draw, cx, cy, r, color):
    ball_r = r * 0.4
    draw.ellipse([cx - ball_r, cy - ball_r + r*0.1, cx + ball_r, cy + ball_r + r*0.1],
                 fill=color)
    hole_r = ball_r * 0.12
    for dx, dy in [(-0.15, -0.2), (0.1, -0.25), (0.2, -0.05)]:
        hx, hy = cx + ball_r * dx, cy + ball_r * dy + r*0.1
        draw.ellipse([hx - hole_r, hy - hole_r, hx + hole_r, hy + hole_r],
                     fill=hex_to_rgb("#333333"))
    pin_x = cx + r * 0.3
    pin_bottom = cy - r * 0.1
    draw.ellipse([pin_x - r*0.1, pin_bottom - r*0.5, pin_x + r*0.1, pin_bottom],
                 fill="#FFFFFF")


def draw_star_icon(draw, cx, cy, r, color):
    points = []
    for i in range(5):
        angle = math.radians(-90 + i * 72)
        points.append((cx + r*0.5 * math.cos(angle), cy + r*0.5 * math.sin(angle)))
        angle2 = math.radians(-90 + i * 72 + 36)
        points.append((cx + r*0.2 * math.cos(angle2), cy + r*0.2 * math.sin(angle2)))
    draw.polygon(points, fill=color)


def draw_ghost_icon(draw, cx, cy, r, color):
    body_top = cy - r * 0.4
    body_bottom = cy + r * 0.4
    body_left = cx - r * 0.3
    body_right = cx + r * 0.3
    draw.pieslice([body_left, body_top, body_right, body_top + (body_right - body_left)],
                  180, 0, fill=color)
    draw.rectangle([body_left, cy - r*0.05, body_right, body_bottom], fill=color)
    wave_w = (body_right - body_left) / 3
    for i in range(3):
        wx = body_left + i * wave_w
        draw.pieslice([wx, body_bottom - wave_w/2, wx + wave_w, body_bottom + wave_w/2],
                      0, 180, fill=color)
    eye_r = r * 0.06
    for dx in [-0.1, 0.1]:
        ex = cx + r * dx
        ey = cy - r * 0.15
        draw.ellipse([ex - eye_r, ey - eye_r, ex + eye_r, ey + eye_r], fill="#000000")


def draw_sunglasses_icon(draw, cx, cy, r, color):
    draw.rectangle([cx - r*0.45, cy - r*0.3, cx + r*0.45, cy - r*0.22], fill=color)
    draw.rectangle([cx - r*0.25, cy - r*0.55, cx + r*0.25, cy - r*0.3], fill=color)
    glass_w = r * 0.2
    glass_h = r * 0.12
    for dx in [-0.15, 0.15]:
        gx = cx + r * dx
        gy = cy - r * 0.05
        draw.rectangle([gx - glass_w/2, gy - glass_h/2, gx + glass_w/2, gy + glass_h/2],
                       fill=color)
    draw.line([cx - r*0.05, cy - r*0.05, cx + r*0.05, cy - r*0.05], fill=color, width=2)


def draw_mic_icon(draw, cx, cy, r, color):
    draw.ellipse([cx - r*0.12, cy - r*0.4, cx + r*0.12, cy - r*0.1], fill=color)
    draw.line([cx, cy - r*0.1, cx, cy + r*0.2], fill=color, width=max(2, int(r*0.04)))
    draw.line([cx - r*0.15, cy + r*0.2, cx + r*0.15, cy + r*0.2],
              fill=color, width=max(2, int(r*0.04)))


def draw_generic_icon(draw, cx, cy, r, color):
    draw.ellipse([cx - r*0.35, cy - r*0.35, cx + r*0.35, cy + r*0.35],
                 outline=color, width=max(3, int(r*0.06)))


ICON_DRAWERS = {
    "bowling": draw_bowling_icon,
    "star": draw_star_icon,
    "ghost": draw_ghost_icon,
    "sunglasses": draw_sunglasses_icon,
    "mic": draw_mic_icon,
}


def generate_icon(pack_name, size=256):
    """Generate an icon for a pack. Tries web fetch first, falls back to drawn."""
    # Try web-sourced icon first
    web_img, source = generate_web_icon(pack_name, size=size)
    if web_img is not None:
        return web_img

    # Fallback: Pillow-drawn icon
    theme = PACK_THEMES.get(pack_name, {
        "bg": "#333333",
        "accent": "#FFFFFF",
        "icon": "generic",
        "initials": pack_name[:2].upper(),
    })

    bg_color = hex_to_rgb(theme["bg"])
    accent_color = hex_to_rgb(theme["accent"])

    img = Image.new("RGB", (size, size), bg_color)
    draw = ImageDraw.Draw(img)

    cx, cy = size / 2, size / 2
    r = size / 2

    margin = size * 0.08
    draw.ellipse([margin, margin, size - margin, size - margin],
                 outline=accent_color + (80,), width=max(2, size // 64))

    icon_type = theme.get("icon", "generic")
    drawer = ICON_DRAWERS.get(icon_type, draw_generic_icon)
    drawer(draw, cx, cy - size * 0.08, r, accent_color)

    initials = theme.get("initials", pack_name[:2].upper())
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size // 5)
    except Exception:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/SFNSMono.ttf", size // 5)
        except Exception:
            font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), initials, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = cx - tw / 2
    ty = size - margin - th - size * 0.02
    draw.text((tx, ty), initials, fill=accent_color, font=font)

    return img


def generate_and_save_icon(pack_name, size=256, force_web=False):
    """Generate and save icon to pack's icons/pack.png.

    Args:
        pack_name: Name of the pack
        size: Icon size in pixels
        force_web: If True, always try web fetch even if icon exists
    """
    pack_dir = os.path.join(PACKS_DIR, pack_name)
    if not os.path.isdir(pack_dir):
        return {"error": f"Pack directory not found: {pack_dir}"}

    icon_dir = os.path.join(pack_dir, "icons")
    os.makedirs(icon_dir, exist_ok=True)
    icon_path = os.path.join(icon_dir, "pack.png")

    source = "fallback"
    if force_web:
        web_img, src = generate_web_icon(pack_name, size=size)
        if web_img is not None:
            web_img.save(icon_path, "PNG", optimize=True)
            source = src
        else:
            img = generate_icon(pack_name, size)
            img.save(icon_path, "PNG", optimize=True)
    else:
        img = generate_icon(pack_name, size)
        img.save(icon_path, "PNG", optimize=True)
        # Check if web icon was used
        web_img, src = generate_web_icon(pack_name, size=size)
        if web_img is not None:
            source = src

    file_size = os.path.getsize(icon_path)
    return {
        "path": icon_path,
        "size_bytes": file_size,
        "size_kb": round(file_size / 1024, 1),
        "within_limit": file_size <= 500 * 1024,
        "source": source,
    }


def generate_all_icons(size=256, force_web=False, delay=2.0):
    """Generate icons for all packs that don't have one yet (or all if force_web).

    Args:
        delay: Seconds to wait between web fetches to avoid rate limiting.
    """
    results = []
    for pack_name in sorted(PACK_THEMES.keys()):
        pack_dir = os.path.join(PACKS_DIR, pack_name)
        icon_path = os.path.join(pack_dir, "icons", "pack.png")
        if os.path.isdir(pack_dir) and (force_web or not os.path.exists(icon_path)):
            result = generate_and_save_icon(pack_name, size, force_web=force_web)
            result["pack"] = pack_name
            results.append(result)
            if force_web and result.get("source", "").startswith("wikipedia"):
                time.sleep(delay)
    return results
