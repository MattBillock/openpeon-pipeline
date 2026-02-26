"""Build OpenPeon sound packs from reviewed clips."""
import hashlib
import json
import logging
import os
import shutil
import subprocess

log = logging.getLogger(__name__)


EXTRACTION_DIR = os.path.expanduser("~/Development/AIOutput/openpeon/extraction")
PACKS_DIR = os.path.expanduser("~/Development/openpeon-movie-packs")
STAGING_DIR = os.path.expanduser("~/Development/AIOutput/openpeon/staging")
DRAFTS_DIR = os.path.expanduser("~/Development/AIOutput/openpeon/drafts")

CATEGORIES = [
    "session.start",
    "task.acknowledge",
    "task.complete",
    "task.error",
    "input.required",
    "resource.limit",
    "user.spam",
]

# Movie display names for placeholder generation
_MOVIE_DISPLAY = {
    "afewgoodmen": ("A Few Good Men", "afewgoodmen", "military, courtroom, drama, jack-nicholson, tom-cruise"),
    "airplane": ("Airplane!", "airplane", "comedy, parody, leslie-nielsen, disaster-movie"),
    "diehard": ("Die Hard", "diehard", "action, christmas, bruce-willis, hans-gruber, alan-rickman"),
    "fifthelement": ("The Fifth Element", "fifthelement", "sci-fi, action, bruce-willis, luc-besson"),
    "fightclub": ("Fight Club", "fightclub", "drama, brad-pitt, edward-norton, twist"),
    "fullmetaljacket": ("Full Metal Jacket", "fullmetaljacket", "war, military, kubrick, r-lee-ermey"),
    "glengarry": ("Glengarry Glen Ross", "glengarry", "drama, sales, alec-baldwin, al-pacino"),
    "goodfellas": ("Goodfellas", "goodfellas", "crime, mafia, scorsese, ray-liotta, joe-pesci"),
    "pulpfiction": ("Pulp Fiction", "pulpfiction", "crime, tarantino, samuel-jackson, john-travolta"),
    "spaceballs": ("Spaceballs", "spaceballs", "comedy, parody, mel-brooks, star-wars"),
    "tommyboy": ("Tommy Boy", "tommyboy", "comedy, chris-farley, david-spade, road-trip"),
    "tuckerdale": ("Tucker and Dale vs Evil", "tuckerdale", "comedy, horror, alan-tudyk, tyler-labine"),
    "whiplash": ("Whiplash", "whiplash", "drama, music, jk-simmons, drums, jazz"),
}


# =================================================================
# Pack Drafts — save/load in-progress pack descriptions
# =================================================================

def save_draft(pack_name, draft_data):
    """Save a pack draft (form state) to disk."""
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    path = os.path.join(DRAFTS_DIR, f"{pack_name}.json")
    with open(path, "w") as f:
        json.dump(draft_data, f, indent=2)
    return path


def load_draft(pack_name):
    """Load a saved pack draft, or return None."""
    path = os.path.join(DRAFTS_DIR, f"{pack_name}.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def list_drafts():
    """List all saved drafts."""
    if not os.path.isdir(DRAFTS_DIR):
        return []
    drafts = []
    for f in sorted(os.listdir(DRAFTS_DIR)):
        if f.endswith(".json"):
            name = f[:-5]
            path = os.path.join(DRAFTS_DIR, f)
            try:
                with open(path) as fh:
                    data = json.load(fh)
                drafts.append({
                    "name": name,
                    "display_name": data.get("display_name", name),
                    "movie": data.get("movie", ""),
                    "description": data.get("description", ""),
                    "sound_count": len(data.get("clip_names", [])),
                })
            except Exception:
                drafts.append({"name": name, "display_name": name, "movie": "", "description": ""})
    return drafts


def generate_placeholder(movie_name, pack_name=""):
    """Generate placeholder text for a pack based on movie and clip data.

    Returns dict with: display_name, description, tags, pack_name
    """
    movie_info = _MOVIE_DISPLAY.get(movie_name, (movie_name.replace("_", " ").title(), movie_name, "movie-quotes"))
    movie_title, slug, tag_str = movie_info
    tags = ["movie-quotes"] + [t.strip() for t in tag_str.split(",")]

    # Get approved clips to analyze
    clips = get_approved_clips(movie_name)
    clip_names = [c["name"] for c in clips]

    # Generate a default pack name from movie
    if not pack_name:
        pack_name = slug

    display_name = movie_title

    # Generate description from clip count and categories
    cat_set = set(c["category"] for c in clips) if clips else set()
    n_cats = len(cat_set)
    n_clips = len(clips)

    if n_clips > 0:
        description = f"{movie_title} quotes for your Claude Code notifications. {n_clips} clips across {n_cats} categories."
    else:
        description = f"{movie_title} quotes as Claude Code notification sounds."

    return {
        "pack_name": pack_name,
        "display_name": display_name,
        "description": description,
        "tags": tags,
        "clip_names": clip_names,
    }


def get_approved_clips(movie_name):
    """Get all approved clips with their category assignments."""
    review_path = os.path.join(EXTRACTION_DIR, movie_name, "review.json")
    if not os.path.exists(review_path):
        return []

    with open(review_path) as f:
        review = json.load(f)

    clips = []
    for clip_name, data in review.items():
        if data.get("status") == "approved" and data.get("category"):
            clip_path = os.path.join(EXTRACTION_DIR, movie_name, f"{clip_name}.mp3")
            if os.path.exists(clip_path):
                clips.append({
                    "name": clip_name,
                    "path": clip_path,
                    "category": data["category"],
                    "notes": data.get("notes", ""),
                })
    return clips


def _get_clip_labels(movie_name):
    """Get quote text for clips from extraction_log.json to use as labels."""
    log_path = os.path.join(EXTRACTION_DIR, movie_name, "extraction_log.json")
    if not os.path.exists(log_path):
        return {}
    try:
        with open(log_path) as f:
            data = json.load(f)
        return {k: v.get("quote", "") for k, v in data.items() if isinstance(v, dict)}
    except Exception:
        return {}


def preview_manifest(pack_name, display_name, description, movie_name,
                     tags=None, author_name="Willow Billock", author_github="MattBillock"):
    """Generate a preview of the openpeon.json manifest."""
    clips = get_approved_clips(movie_name)
    if not clips:
        return None

    # Get quote labels
    labels = _get_clip_labels(movie_name)

    # Group by category
    sounds = {}
    for clip in clips:
        cat = clip["category"]
        if cat not in sounds:
            sounds[cat] = []
        # Compute SHA256
        with open(clip["path"], "rb") as f:
            sha = hashlib.sha256(f.read()).hexdigest()
        entry = {
            "file": f"sounds/{clip['name']}.mp3",
            "sha256": sha,
        }
        # Add label from quote text
        label = labels.get(clip["name"], "")
        if label:
            entry["label"] = label
        sounds[cat].append(entry)

    manifest = {
        "name": pack_name,
        "display_name": display_name,
        "version": "1.0.0",
        "description": description,
        "author": {"name": author_name, "github": author_github},
        "license": "fair-use",
        "language": "en",
        "tags": tags or [],
        "categories": {},
    }

    for cat in CATEGORIES:
        if cat in sounds:
            manifest["categories"][cat] = sounds[cat]

    return manifest


def build_pack(pack_name, display_name, description, movie_name,
               tags=None, author_name="Willow Billock", author_github="MattBillock"):
    """Build a pack: copy clips, write manifest, add to monorepo."""
    manifest = preview_manifest(pack_name, display_name, description, movie_name,
                                 tags, author_name, author_github)
    if not manifest:
        return {"error": "No approved clips with categories"}

    pack_dir = os.path.join(PACKS_DIR, pack_name)
    sounds_dir = os.path.join(pack_dir, "sounds")
    os.makedirs(sounds_dir, exist_ok=True)

    # Copy clips
    clips = get_approved_clips(movie_name)
    for clip in clips:
        dest = os.path.join(sounds_dir, f"{clip['name']}.mp3")
        shutil.copy2(clip["path"], dest)

    # Write manifest
    manifest_path = os.path.join(pack_dir, "openpeon.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    # Count
    total_sounds = sum(len(v) for v in manifest["categories"].values())
    total_size = sum(
        os.path.getsize(os.path.join(sounds_dir, f))
        for f in os.listdir(sounds_dir) if f.endswith(".mp3")
    )

    return {
        "status": "built",
        "pack_dir": pack_dir,
        "sounds": total_sounds,
        "size_bytes": total_size,
        "categories": len(manifest["categories"]),
    }


def get_published_packs():
    """List all published packs in the monorepo."""
    packs = []
    if not os.path.isdir(PACKS_DIR):
        return packs

    for d in sorted(os.listdir(PACKS_DIR)):
        manifest_path = os.path.join(PACKS_DIR, d, "openpeon.json")
        if os.path.exists(manifest_path):
            try:
                with open(manifest_path) as f:
                    m = json.load(f)
                sound_count = sum(
                    len(v) if isinstance(v, list)
                    else len(v.get("sounds", [])) if isinstance(v, dict)
                    else 0
                    for v in m.get("categories", {}).values()
                )
                pack_dir = os.path.join(PACKS_DIR, d)
                has_icon = os.path.exists(os.path.join(pack_dir, "icons", "pack.png"))
                packs.append({
                    "name": m.get("name", d),
                    "display_name": m.get("display_name", d),
                    "version": m.get("version", "?"),
                    "description": m.get("description", ""),
                    "sound_count": sound_count,
                    "tags": m.get("tags", []),
                    "has_icon": has_icon,
                    "dir": pack_dir,
                })
            except Exception as e:
                log.error("Failed to load manifest for pack %s: %s", d, e)
    return packs


def get_pack_details(pack_name):
    """Get full details for a published pack including all sounds and review state."""
    pack_dir = os.path.join(PACKS_DIR, pack_name)
    manifest_path = os.path.join(pack_dir, "openpeon.json")
    if not os.path.exists(manifest_path):
        return None

    with open(manifest_path) as f:
        manifest = json.load(f)

    # Load pack review state
    review = _load_pack_review(pack_name)

    # Build per-category sound list with file info
    categories = {}
    for cat in CATEGORIES:
        cat_sounds = manifest.get("categories", {}).get(cat, {})
        # Handle both list format and dict format
        sound_list = cat_sounds if isinstance(cat_sounds, list) else cat_sounds.get("sounds", [])
        sounds = []
        for s in sound_list:
            filename = s.get("file", "")
            # Strip sounds/ prefix if present
            bare_name = filename.replace("sounds/", "") if filename.startswith("sounds/") else filename
            filepath = os.path.join(pack_dir, "sounds", bare_name)
            sound_review = review.get(bare_name, {})
            sounds.append({
                "file": bare_name,
                "path": filepath,
                "label": s.get("label", bare_name.replace(".mp3", "").replace("_", " ")),
                "sha256": s.get("sha256", ""),
                "exists": os.path.exists(filepath),
                "size_kb": round(os.path.getsize(filepath) / 1024, 1) if os.path.exists(filepath) else 0,
                "review_status": sound_review.get("status", "unreviewed"),
                "review_notes": sound_review.get("notes", ""),
            })
        if sounds:
            categories[cat] = sounds

    # Icon info
    icon_path = os.path.join(pack_dir, "icons", "pack.png")
    has_icon = os.path.exists(icon_path)

    # Count review stats
    all_sounds = [s for cat_sounds in categories.values() for s in cat_sounds]
    flagged = sum(1 for s in all_sounds if s["review_status"] in ("needs-update", "needs-fix"))
    pending_fix = sum(1 for s in all_sounds if s["review_status"] == "pending-fix")
    reviewed_ok = sum(1 for s in all_sounds if s["review_status"] == "ok")

    # Pack-level status
    pack_status = review.get("_pack_status", {}).get("status", "unreviewed")

    return {
        "name": manifest.get("name", pack_name),
        "display_name": manifest.get("display_name", pack_name),
        "version": manifest.get("version", "?"),
        "description": manifest.get("description", ""),
        "author": manifest.get("author", {}),
        "license": manifest.get("license", ""),
        "tags": manifest.get("tags", []),
        "categories": categories,
        "has_icon": has_icon,
        "icon_path": icon_path if has_icon else None,
        "dir": pack_dir,
        "total_sounds": len(all_sounds),
        "flagged": flagged,
        "pending_fix": pending_fix,
        "reviewed_ok": reviewed_ok,
        "unreviewed": len(all_sounds) - flagged - pending_fix - reviewed_ok,
        "pack_status": pack_status,
    }


def _load_pack_review(pack_name):
    """Load pack_review.json for a published pack."""
    review_path = os.path.join(PACKS_DIR, pack_name, "pack_review.json")
    if os.path.exists(review_path):
        try:
            with open(review_path) as f:
                return json.load(f)
        except Exception as e:
            log.error("Corrupted pack_review.json for %s: %s", pack_name, e)
    return {}


def save_pack_sound_review(pack_name, sound_file, status, notes=""):
    """Save review status for a sound in a published pack.

    status: 'ok', 'needs-update', 'needs-fix', 'pending-fix', 'unreviewed'
    """
    pack_dir = os.path.join(PACKS_DIR, pack_name)
    review_path = os.path.join(pack_dir, "pack_review.json")

    review = _load_pack_review(pack_name)
    if status == "unreviewed":
        review.pop(sound_file, None)
    else:
        review[sound_file] = {"status": status, "notes": notes}

    with open(review_path, "w") as f:
        json.dump(review, f, indent=2)

    return review


def get_pack_status(pack_name):
    """Get the pack-level completion status.

    Returns: 'complete', 'needs-work', or 'unreviewed'
    """
    review = _load_pack_review(pack_name)
    return review.get("_pack_status", {}).get("status", "unreviewed")


def set_pack_status(pack_name, status, notes=""):
    """Set the pack-level completion status.

    status: 'complete', 'needs-work', 'unreviewed'
    """
    review = _load_pack_review(pack_name)
    review["_pack_status"] = {"status": status, "notes": notes}
    pack_dir = os.path.join(PACKS_DIR, pack_name)
    review_path = os.path.join(pack_dir, "pack_review.json")
    with open(review_path, "w") as f:
        json.dump(review, f, indent=2)


def auto_fix_sound(pack_name, sound_file):
    """Automatically fix a pack sound: trim silence, normalize audio, update manifest.

    Steps:
    1. Back up original to sounds/.backups/
    2. Apply ffmpeg: trim leading/trailing silence + normalize to -14 LUFS
    3. Update SHA256 in openpeon.json manifest
    4. Reset review status to 'unreviewed' for re-listening

    Returns dict with fix results or error.
    """
    pack_dir = os.path.join(PACKS_DIR, pack_name)
    sound_path = os.path.join(pack_dir, "sounds", sound_file)

    if not os.path.exists(sound_path):
        return {"ok": False, "error": f"Sound file not found: {sound_file}"}

    # 1. Back up original
    backup_dir = os.path.join(pack_dir, "sounds", ".backups")
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, sound_file)
    shutil.copy2(sound_path, backup_path)

    # 2. Apply ffmpeg audio fix pipeline:
    #    - silenceremove: trim leading silence (threshold -40dB)
    #    - areverse + silenceremove + areverse: trim trailing silence
    #    - loudnorm: normalize to -14 LUFS (broadcast standard)
    tmp_path = sound_path + ".fixing.mp3"
    ffmpeg = "/opt/homebrew/bin/ffmpeg"
    if not os.path.exists(ffmpeg):
        ffmpeg = "ffmpeg"

    # Two-pass loudnorm for accurate normalization
    # Pass 1: measure levels
    measure_cmd = [
        ffmpeg, "-y", "-i", sound_path,
        "-af", (
            "silenceremove=start_periods=1:start_silence=0.05:start_threshold=-40dB,"
            "areverse,"
            "silenceremove=start_periods=1:start_silence=0.05:start_threshold=-40dB,"
            "areverse,"
            "loudnorm=I=-14:LRA=11:TP=-1:print_format=json"
        ),
        "-f", "null", "-"
    ]
    try:
        result = subprocess.run(
            measure_cmd, capture_output=True, text=True, timeout=30
        )
        # Parse loudnorm stats from stderr
        stderr = result.stderr
        loudnorm_stats = {}
        if '"input_i"' in stderr:
            import re
            for key in ["input_i", "input_tp", "input_lra", "input_thresh",
                        "target_offset"]:
                m = re.search(rf'"{key}"\s*:\s*"([^"]+)"', stderr)
                if m:
                    loudnorm_stats[key] = m.group(1)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "ffmpeg measurement pass timed out"}
    except FileNotFoundError:
        return {"ok": False, "error": "ffmpeg not found"}

    # Pass 2: apply normalization with measured values
    if loudnorm_stats.get("input_i"):
        loudnorm_filter = (
            f"loudnorm=I=-14:LRA=11:TP=-1:"
            f"measured_I={loudnorm_stats['input_i']}:"
            f"measured_LRA={loudnorm_stats.get('input_lra', '7')}:"
            f"measured_tp={loudnorm_stats.get('input_tp', '-1')}:"
            f"measured_thresh={loudnorm_stats.get('input_thresh', '-24')}:"
            f"offset={loudnorm_stats.get('target_offset', '0')}:"
            f"linear=true"
        )
    else:
        # Fallback: single-pass loudnorm
        loudnorm_filter = "loudnorm=I=-14:LRA=11:TP=-1"

    fix_cmd = [
        ffmpeg, "-y", "-i", sound_path,
        "-af", (
            "silenceremove=start_periods=1:start_silence=0.05:start_threshold=-40dB,"
            "areverse,"
            "silenceremove=start_periods=1:start_silence=0.05:start_threshold=-40dB,"
            "areverse,"
            + loudnorm_filter
        ),
        "-codec:a", "libmp3lame", "-b:a", "192k",
        tmp_path,
    ]
    try:
        result = subprocess.run(fix_cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            os.unlink(tmp_path) if os.path.exists(tmp_path) else None
            return {"ok": False, "error": f"ffmpeg fix failed: {result.stderr[-200:]}"}
    except subprocess.TimeoutExpired:
        os.unlink(tmp_path) if os.path.exists(tmp_path) else None
        return {"ok": False, "error": "ffmpeg fix pass timed out"}

    # Replace original with fixed version
    os.replace(tmp_path, sound_path)

    # 3. Update SHA256 in manifest
    new_sha = hashlib.sha256(open(sound_path, "rb").read()).hexdigest()
    old_size = os.path.getsize(backup_path)
    new_size = os.path.getsize(sound_path)
    _update_manifest_sha(pack_name, sound_file, new_sha)

    # 4. Reset review status to unreviewed for re-listening
    save_pack_sound_review(pack_name, sound_file, "unreviewed")

    return {
        "ok": True,
        "file": sound_file,
        "old_size": old_size,
        "new_size": new_size,
        "new_sha": new_sha[:12],
        "backup": backup_path,
    }


def auto_fix_flagged(pack_name):
    """Auto-fix all flagged sounds in a pack.

    Returns list of per-sound results.
    """
    review = _load_pack_review(pack_name)
    results = []
    for key, val in review.items():
        if key == "_pack_status":
            continue
        if isinstance(val, dict) and val.get("status") in ("needs-update", "needs-fix"):
            r = auto_fix_sound(pack_name, key)
            results.append(r)
    return results


def restore_backup(pack_name, sound_file):
    """Restore a sound file from its backup.

    Returns True if restored, False if no backup exists.
    """
    pack_dir = os.path.join(PACKS_DIR, pack_name)
    sound_path = os.path.join(pack_dir, "sounds", sound_file)
    backup_path = os.path.join(pack_dir, "sounds", ".backups", sound_file)

    if not os.path.exists(backup_path):
        return False

    shutil.copy2(backup_path, sound_path)

    # Update SHA256 in manifest
    new_sha = hashlib.sha256(open(sound_path, "rb").read()).hexdigest()
    _update_manifest_sha(pack_name, sound_file, new_sha)

    # Reset review status
    save_pack_sound_review(pack_name, sound_file, "unreviewed")
    return True


def _update_manifest_sha(pack_name, sound_file, new_sha):
    """Update the SHA256 for a sound file in the pack manifest."""
    pack_dir = os.path.join(PACKS_DIR, pack_name)
    manifest_path = os.path.join(pack_dir, "openpeon.json")
    if not os.path.exists(manifest_path):
        return

    with open(manifest_path) as f:
        manifest = json.load(f)

    # Search through all categories for the sound
    for cat, cat_data in manifest.get("categories", {}).items():
        sound_list = cat_data if isinstance(cat_data, list) else cat_data.get("sounds", [])
        for s in sound_list:
            bare = s.get("file", "").replace("sounds/", "")
            if bare == sound_file:
                s["sha256"] = new_sha

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)


def send_flagged_for_fix(pack_name):
    """Auto-fix all flagged sounds: trim silence, normalize, update manifest.

    Returns count of sounds fixed.
    """
    results = auto_fix_flagged(pack_name)
    return len([r for r in results if r.get("ok")])


def resolve_fix(pack_name, sound_file):
    """Mark a pending-fix sound as ready for re-review (unreviewed).

    When all pending fixes are resolved, automatically marks pack complete.
    """
    review = _load_pack_review(pack_name)
    if sound_file in review:
        review[sound_file]["status"] = "unreviewed"
        review[sound_file]["notes"] = ""

    # Check if any pending fixes remain
    pending = sum(
        1 for k, v in review.items()
        if k != "_pack_status" and isinstance(v, dict) and v.get("status") == "pending-fix"
    )
    if pending == 0 and review.get("_pack_status", {}).get("status") == "needs-work":
        review["_pack_status"]["status"] = "ready-for-review"
        review["_pack_status"]["pending_fixes"] = 0

    pack_dir = os.path.join(PACKS_DIR, pack_name)
    review_path = os.path.join(pack_dir, "pack_review.json")
    with open(review_path, "w") as f:
        json.dump(review, f, indent=2)

    return pending


def get_all_pack_review_summary():
    """Get review summary across all packs."""
    packs = get_published_packs()
    results = []
    for p in packs:
        review = _load_pack_review(p["name"])
        flagged = sum(
            1 for k, v in review.items()
            if k != "_pack_status" and isinstance(v, dict) and v.get("status") in ("needs-update", "needs-fix")
        )
        ok = sum(
            1 for k, v in review.items()
            if k != "_pack_status" and isinstance(v, dict) and v.get("status") == "ok"
        )
        pending_fix = sum(
            1 for k, v in review.items()
            if k != "_pack_status" and isinstance(v, dict) and v.get("status") == "pending-fix"
        )
        pack_status = review.get("_pack_status", {}).get("status", "unreviewed")
        results.append({
            "name": p["name"],
            "display_name": p["display_name"],
            "sound_count": p["sound_count"],
            "flagged": flagged,
            "ok": ok,
            "pending_fix": pending_fix,
            "unreviewed": p["sound_count"] - flagged - ok - pending_fix,
            "has_icon": p.get("has_icon", False),
            "pack_status": pack_status,
        })
    return results
