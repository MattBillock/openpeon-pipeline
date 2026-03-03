"""Generate stylized pack icons for OpenPeon sound packs.

Creates 256x256 PNG icons from movie posters (via Radarr/TMDB), web-sourced
actor photos (Wikipedia), or Pillow-drawn fallbacks.
Priority: movie poster → actor headshot → drawn fallback.
Registry spec: 256x256 px, PNG/JPEG/WebP/SVG, max 500KB per icon.
"""
import hashlib
import json
import math
import os
import re
import sys
import time
from io import BytesIO

import requests
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont


PACKS_DIR = os.path.expanduser("~/dev/openpeon-movie-packs")
THEMES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pack_themes.json")


def _load_themes_config():
    """Load pack themes and movie map from pack_themes.json.

    Returns (movie_map, themes) dicts. Falls back to empty dicts if file missing.
    """
    if not os.path.exists(THEMES_FILE):
        return {}, {}
    try:
        with open(THEMES_FILE) as f:
            data = json.load(f)
        return data.get("movie_map", {}), data.get("themes", {})
    except Exception:
        return {}, {}


def _get_movie_title_for_pack(pack_name):
    """Resolve a pack name to its source movie title.

    Checks the pack's openpeon.json manifest first, then falls back to
    pack_themes.json movie_map (exact match, then prefix match).
    """
    # Try manifest first
    manifest_path = os.path.join(PACKS_DIR, pack_name, "openpeon.json")
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path) as f:
                m = json.load(f)
            title = m.get("display_name")
            if title:
                return title
        except Exception:
            pass

    # Fall back to themes config
    movie_map, _ = _load_themes_config()
    if pack_name in movie_map:
        return movie_map[pack_name]
    for prefix, title in sorted(movie_map.items(), key=lambda x: -len(x[0])):
        if pack_name.startswith(prefix):
            return title
    return None


def _get_radarr_poster_url(movie_title):
    """Look up a movie in Radarr and return its TMDB poster URL.

    Returns (poster_url, movie_title_found) or (None, None) on failure.
    """
    # Import radarr_client from same directory
    dashboard_dir = os.path.dirname(os.path.abspath(__file__))
    if dashboard_dir not in sys.path:
        sys.path.insert(0, dashboard_dir)
    try:
        import radarr_client
    except ImportError:
        print("  radarr_client not available")
        return None, None

    movies = radarr_client.get_all_movies()
    if isinstance(movies, dict) and "error" in movies:
        print(f"  Radarr error: {movies['error']}")
        return None, None

    # Find movie by title (case-insensitive)
    target = movie_title.lower()
    for m in movies:
        if m.get("title", "").lower() == target:
            images = m.get("images", [])
            for img in images:
                if img.get("coverType") == "poster":
                    url = img.get("remoteUrl") or img.get("url")
                    if url:
                        return url, m["title"]
    return None, None


def fetch_movie_poster(pack_name, size=500):
    """Fetch the movie poster for a pack via Radarr/TMDB.

    Returns PIL Image or None on failure.
    """
    movie_title = _get_movie_title_for_pack(pack_name)
    if not movie_title:
        return None

    poster_url, found_title = _get_radarr_poster_url(movie_title)
    if not poster_url:
        print(f"  No poster found for '{movie_title}' in Radarr")
        return None

    try:
        resp = requests.get(poster_url, timeout=15)
        resp.raise_for_status()
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        print(f"  Fetched poster for '{found_title}' ({img.size[0]}x{img.size[1]})")
        return img
    except Exception as e:
        print(f"  Poster download failed for '{movie_title}': {e}")
        return None


def generate_poster_icon(pack_name, size=256):
    """Generate a pack icon from the movie poster.

    Crops the poster to a square (from center-top, since titles/faces
    are usually in the upper portion), resizes to 256x256.
    Adds character name label if the pack is character-specific.

    Returns (PIL Image, source_info) or (None, error_info).
    """
    poster = fetch_movie_poster(pack_name, size=800)
    if poster is None:
        return None, "no_poster"

    w, h = poster.size

    # Movie posters are typically 2:3 portrait. Crop to square from top-center
    # (keeps the title treatment and main characters visible).
    sq = min(w, h)
    left = (w - sq) // 2
    # Bias toward upper portion: start at 10% from top instead of center
    top = min(int(h * 0.10), h - sq)
    top = max(0, top)
    cropped = poster.crop((left, top, left + sq, top + sq))
    resized = cropped.resize((size, size), Image.LANCZOS)

    # Add character label for character-specific packs
    theme = _get_pack_themes().get(pack_name, {})
    character = theme.get("character")
    accent = theme.get("accent", "#FFFFFF")
    if character:
        resized = add_character_label(resized, character, accent, size=size)

    movie_title = _get_movie_title_for_pack(pack_name) or pack_name
    return resized, f"poster:{movie_title}"


def _get_pack_themes():
    """Load pack themes from pack_themes.json config file.

    Returns dict of {pack_name: {bg, accent, icon, initials, actor, character, ...}}.
    Falls back to empty dict if file not found.
    """
    _, themes = _load_themes_config()
    return themes


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
    theme = _get_pack_themes().get(pack_name)
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
    """Generate an icon for a pack.

    Priority: movie poster → Wikipedia actor headshot → Pillow-drawn fallback.
    """
    # Try movie poster first (best for movie packs)
    poster_img, poster_src = generate_poster_icon(pack_name, size=size)
    if poster_img is not None:
        return poster_img

    # Try web-sourced actor headshot
    web_img, source = generate_web_icon(pack_name, size=size)
    if web_img is not None:
        return web_img

    # Fallback: Pillow-drawn icon
    theme = _get_pack_themes().get(pack_name, {
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
        # Try poster first, then Wikipedia, then fallback
        poster_img, poster_src = generate_poster_icon(pack_name, size=size)
        if poster_img is not None:
            poster_img.save(icon_path, "PNG", optimize=True)
            source = poster_src
        else:
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
        # Determine what source was used
        poster_img, poster_src = generate_poster_icon(pack_name, size=size)
        if poster_img is not None:
            source = poster_src
        else:
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

    Discovers packs from both _get_pack_themes() and the packs directory.

    Args:
        delay: Seconds to wait between web fetches to avoid rate limiting.
    """
    # Discover all packs: union of _get_pack_themes() keys and actual pack dirs
    all_packs = set(_get_pack_themes().keys())
    if os.path.isdir(PACKS_DIR):
        for name in os.listdir(PACKS_DIR):
            manifest = os.path.join(PACKS_DIR, name, "openpeon.json")
            if os.path.exists(manifest):
                all_packs.add(name)

    results = []
    for pack_name in sorted(all_packs):
        pack_dir = os.path.join(PACKS_DIR, pack_name)
        icon_path = os.path.join(pack_dir, "icons", "pack.png")
        if os.path.isdir(pack_dir) and (force_web or not os.path.exists(icon_path)):
            result = generate_and_save_icon(pack_name, size, force_web=force_web)
            result["pack"] = pack_name
            results.append(result)
            src = result.get("source", "")
            if force_web and (src.startswith("wikipedia") or src.startswith("poster")):
                time.sleep(delay)
    return results
