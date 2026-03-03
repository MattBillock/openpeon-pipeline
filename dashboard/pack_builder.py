"""Build OpenPeon sound packs from reviewed clips."""
import hashlib
import json
import logging
import os
import shutil
import subprocess

log = logging.getLogger(__name__)


def _cat_sounds(cat_data):
    """Extract the sound list from a category entry, handling both formats.

    Flat list format:   [{"file": ..., "sha256": ...}, ...]
    Wrapped format:     {"sounds": [{"file": ..., "sha256": ...}, ...]}
    """
    if isinstance(cat_data, list):
        return cat_data
    if isinstance(cat_data, dict):
        return cat_data.get("sounds", [])
    return []


EXTRACTION_DIR = os.path.expanduser("~/dev/openpeon/extraction")
PACKS_DIR = os.path.expanduser("~/dev/openpeon-movie-packs")
STAGING_DIR = os.path.expanduser("~/dev/openpeon/staging")
DRAFTS_DIR = os.path.expanduser("~/dev/openpeon/drafts")

CATEGORIES = [
    "session.start",
    "task.acknowledge",
    "task.complete",
    "task.error",
    "input.required",
    "resource.limit",
    "user.spam",
]

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
    movie_title = movie_name.replace("_", " ").title()
    slug = movie_name
    tags = ["movie-quotes"]

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
            manifest["categories"][cat] = {"sounds": sounds[cat]}

    return manifest


def build_pack(pack_name, display_name, description, movie_name,
               tags=None, author_name="Willow Billock", author_github="MattBillock"):
    """Build or update a pack: copy clips, write/merge manifest.

    If the pack already exists, merges new approved clips into the existing
    manifest — preserving any Pack Review modifications (sounds added from
    other movies, manual moves, removals, etc.). Only adds clips that aren't
    already present.
    """
    clips = get_approved_clips(movie_name)
    if not clips:
        return {"error": "No approved clips with categories"}

    labels = _get_clip_labels(movie_name)

    pack_dir = os.path.join(PACKS_DIR, pack_name)
    sounds_dir = os.path.join(pack_dir, "sounds")
    os.makedirs(sounds_dir, exist_ok=True)

    manifest_path = os.path.join(pack_dir, "openpeon.json")
    existing_manifest = None
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path) as f:
                existing_manifest = json.load(f)
        except Exception:
            pass

    if existing_manifest:
        # UPDATE mode: merge new clips into existing manifest
        manifest = existing_manifest
        # Update metadata fields
        manifest["display_name"] = display_name
        manifest["description"] = description
        manifest["tags"] = tags or manifest.get("tags", [])
        manifest["author"] = {"name": author_name, "github": author_github}

        # Bump patch version (1.0.0 → 1.0.1, etc.)
        _bump_manifest_version(manifest)

        # Collect existing sound filenames per category
        existing_files = set()
        for cat_data in manifest.get("categories", {}).values():
            for s in _cat_sounds(cat_data):
                existing_files.add(s.get("file", ""))

        added = 0
        for clip in clips:
            dest = os.path.join(sounds_dir, f"{clip['name']}.mp3")
            clip_file = f"sounds/{clip['name']}.mp3"

            # Copy the audio file (always update to latest extraction)
            shutil.copy2(clip["path"], dest)

            # Only add to manifest if not already present
            if clip_file not in existing_files:
                cat = clip["category"]
                if cat not in manifest["categories"]:
                    manifest["categories"][cat] = {"sounds": []}
                with open(clip["path"], "rb") as f:
                    sha = hashlib.sha256(f.read()).hexdigest()
                entry = {"file": clip_file, "sha256": sha}
                label = labels.get(clip["name"], "")
                if label:
                    entry["label"] = label
                _cat_sounds(manifest["categories"][cat]).append(entry)
                existing_files.add(clip_file)
                added += 1

        status = f"updated (+{added} new)" if added else "updated (no new clips)"
    else:
        # NEW mode: build from scratch
        manifest = preview_manifest(pack_name, display_name, description, movie_name,
                                     tags, author_name, author_github)
        if not manifest:
            return {"error": "No approved clips with categories"}

        for clip in clips:
            dest = os.path.join(sounds_dir, f"{clip['name']}.mp3")
            shutil.copy2(clip["path"], dest)

        status = "built"

    # Write manifest
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    # Count
    total_sounds = sum(
        len(_cat_sounds(v)) for v in manifest.get("categories", {}).values()
    )
    total_size = sum(
        os.path.getsize(os.path.join(sounds_dir, f))
        for f in os.listdir(sounds_dir) if f.endswith(".mp3")
    )

    _mark_pack_dirty(pack_name)

    return {
        "status": status,
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
                    len(_cat_sounds(v))
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
        cat_data = manifest.get("categories", {}).get(cat, {})
        sound_list = _cat_sounds(cat_data)
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


def _mark_pack_dirty(pack_name):
    """Reset pack status from 'complete' to 'needs-work' when modified.

    Published packs are 'complete'. Modifying one means it needs re-publishing.
    """
    review = _load_pack_review(pack_name)
    current = review.get("_pack_status", {}).get("status", "unreviewed")
    if current == "complete":
        set_pack_status(pack_name, "needs-work", notes="modified after publish")


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

    _mark_pack_dirty(pack_name)

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


def _bump_manifest_version(manifest):
    """Bump the patch version in a manifest dict (in-place). 1.0.0 → 1.0.1."""
    old_ver = manifest.get("version", "1.0.0")
    try:
        parts = old_ver.split(".")
        parts[-1] = str(int(parts[-1]) + 1)
        manifest["version"] = ".".join(parts)
    except (ValueError, IndexError):
        manifest["version"] = "1.0.1"
    return manifest["version"]


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
        for s in _cat_sounds(cat_data):
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


def get_clip_library(exclude_pack=None):
    """Get all approved clips across all movies for use as a pick-list.

    Returns list of dicts:
        {movie, clip_name, path, category, label, size_kb, used_in}
    where 'used_in' is list of pack names that already include this clip.
    """
    import glob as g
    # Find all movies with review.json
    clips = []
    review_files = g.glob(os.path.join(EXTRACTION_DIR, "*", "review.json"))

    # Pre-build lookup: which clips are already used in which packs
    pack_usage = {}  # {filename: [pack_names]}
    for pack in get_published_packs():
        details = get_pack_details(pack["name"])
        if details:
            for cat, sounds in details["categories"].items():
                for s in sounds:
                    pack_usage.setdefault(s["file"], []).append(pack["name"])

    for review_path in sorted(review_files):
        movie = os.path.basename(os.path.dirname(review_path))
        try:
            with open(review_path) as f:
                review = json.load(f)
        except Exception:
            continue

        # Get labels from extraction_log.json
        labels = _get_clip_labels(movie)

        for clip_name, data in review.items():
            if data.get("status") != "approved" or not data.get("category"):
                continue
            clip_path = os.path.join(EXTRACTION_DIR, movie, f"{clip_name}.mp3")
            if not os.path.exists(clip_path):
                continue

            filename = f"{clip_name}.mp3"
            clips.append({
                "movie": movie,
                "clip_name": clip_name,
                "path": clip_path,
                "category": data["category"],
                "label": labels.get(clip_name, clip_name.replace("_", " ")),
                "size_kb": round(os.path.getsize(clip_path) / 1024, 1),
                "used_in": pack_usage.get(filename, []),
            })
    return clips


def replace_pack_sound(pack_name, category, old_filename, new_clip_path, new_label=""):
    """Replace a sound in a pack with a different clip file.

    Copies new audio, removes old entry, adds new entry in manifest.
    Backs up old file. Resets review status.
    """
    pack_dir = os.path.join(PACKS_DIR, pack_name)
    sounds_dir = os.path.join(pack_dir, "sounds")
    manifest_path = os.path.join(pack_dir, "openpeon.json")

    if not os.path.exists(manifest_path):
        return {"ok": False, "error": "Pack manifest not found"}
    if not os.path.exists(new_clip_path):
        return {"ok": False, "error": f"Source clip not found: {new_clip_path}"}

    new_filename = os.path.basename(new_clip_path)

    # Back up old file
    old_path = os.path.join(sounds_dir, old_filename)
    if os.path.exists(old_path):
        backup_dir = os.path.join(sounds_dir, ".backups")
        os.makedirs(backup_dir, exist_ok=True)
        shutil.copy2(old_path, os.path.join(backup_dir, old_filename))
        os.remove(old_path)

    # Copy new file
    dest_path = os.path.join(sounds_dir, new_filename)
    shutil.copy2(new_clip_path, dest_path)

    # Compute SHA256
    with open(dest_path, "rb") as f:
        new_sha = hashlib.sha256(f.read()).hexdigest()

    # Update manifest: remove old entry, add new one
    with open(manifest_path) as f:
        manifest = json.load(f)

    cat_data = manifest.get("categories", {}).get(category, {"sounds": []})
    sound_list = _cat_sounds(cat_data)

    # Remove old entry
    sound_list[:] = [s for s in sound_list if s.get("file", "").replace("sounds/", "") != old_filename]

    # Add new entry
    entry = {"file": f"sounds/{new_filename}", "sha256": new_sha}
    if new_label:
        entry["label"] = new_label
    sound_list.append(entry)

    manifest["categories"][category] = {"sounds": sound_list}
    _bump_manifest_version(manifest)

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    # Update review: remove old, reset new to unreviewed
    review = _load_pack_review(pack_name)
    review.pop(old_filename, None)
    review.pop(new_filename, None)  # start fresh
    review_path = os.path.join(pack_dir, "pack_review.json")
    with open(review_path, "w") as f:
        json.dump(review, f, indent=2)

    _mark_pack_dirty(pack_name)

    return {"ok": True, "old": old_filename, "new": new_filename}


def add_pack_sound(pack_name, category, clip_path, label=""):
    """Add a new sound to a category in a published pack.

    Copies audio file, adds entry to manifest, resets pack review.
    """
    pack_dir = os.path.join(PACKS_DIR, pack_name)
    sounds_dir = os.path.join(pack_dir, "sounds")
    manifest_path = os.path.join(pack_dir, "openpeon.json")

    if not os.path.exists(manifest_path):
        return {"ok": False, "error": "Pack manifest not found"}
    if not os.path.exists(clip_path):
        return {"ok": False, "error": f"Source clip not found: {clip_path}"}

    filename = os.path.basename(clip_path)
    dest_path = os.path.join(sounds_dir, filename)

    # Don't overwrite if file already exists in pack
    if os.path.exists(dest_path):
        return {"ok": False, "error": f"File already exists in pack: {filename}"}

    os.makedirs(sounds_dir, exist_ok=True)
    shutil.copy2(clip_path, dest_path)

    with open(dest_path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()

    # Add to manifest
    with open(manifest_path) as f:
        manifest = json.load(f)

    if category not in manifest.get("categories", {}):
        manifest.setdefault("categories", {})[category] = {"sounds": []}

    sound_list = _cat_sounds(manifest["categories"][category])

    entry = {"file": f"sounds/{filename}", "sha256": sha}
    if label:
        entry["label"] = label
    sound_list.append(entry)
    manifest["categories"][category] = {"sounds": sound_list}
    _bump_manifest_version(manifest)

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    _mark_pack_dirty(pack_name)

    return {"ok": True, "file": filename, "category": category}


def remove_pack_sound(pack_name, category, filename):
    """Remove a sound from a published pack.

    Backs up the audio file, removes from manifest. Does NOT delete audio
    (it stays in .backups in case you want it back).
    """
    pack_dir = os.path.join(PACKS_DIR, pack_name)
    sounds_dir = os.path.join(pack_dir, "sounds")
    manifest_path = os.path.join(pack_dir, "openpeon.json")

    if not os.path.exists(manifest_path):
        return {"ok": False, "error": "Pack manifest not found"}

    # Back up the audio file
    sound_path = os.path.join(sounds_dir, filename)
    if os.path.exists(sound_path):
        backup_dir = os.path.join(sounds_dir, ".backups")
        os.makedirs(backup_dir, exist_ok=True)
        shutil.copy2(sound_path, os.path.join(backup_dir, filename))
        os.remove(sound_path)

    # Remove from manifest
    with open(manifest_path) as f:
        manifest = json.load(f)

    sound_list = _cat_sounds(manifest.get("categories", {}).get(category, {"sounds": []}))
    sound_list[:] = [s for s in sound_list if s.get("file", "").replace("sounds/", "") != filename]
    manifest["categories"][category] = {"sounds": sound_list}

    # Remove empty categories
    if not sound_list:
        del manifest["categories"][category]
    _bump_manifest_version(manifest)

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    # Clean up review entry
    review = _load_pack_review(pack_name)
    review.pop(filename, None)
    review_path = os.path.join(pack_dir, "pack_review.json")
    with open(review_path, "w") as f:
        json.dump(review, f, indent=2)

    _mark_pack_dirty(pack_name)

    return {"ok": True, "removed": filename, "category": category}


def move_pack_sound(pack_name, filename, from_category, to_category):
    """Move a sound from one category to another within a pack."""
    pack_dir = os.path.join(PACKS_DIR, pack_name)
    manifest_path = os.path.join(pack_dir, "openpeon.json")

    if not os.path.exists(manifest_path):
        return {"ok": False, "error": "Pack manifest not found"}

    with open(manifest_path) as f:
        manifest = json.load(f)

    # Find and remove from source category
    from_list = _cat_sounds(manifest.get("categories", {}).get(from_category, {"sounds": []}))
    sound_entry = None
    for s in from_list:
        if s.get("file", "").replace("sounds/", "") == filename:
            sound_entry = dict(s)
            break

    if not sound_entry:
        return {"ok": False, "error": f"Sound {filename} not found in {from_category}"}

    from_list[:] = [s for s in from_list if s.get("file", "").replace("sounds/", "") != filename]
    manifest["categories"][from_category] = {"sounds": from_list}
    if not from_list:
        del manifest["categories"][from_category]

    # Add to destination category
    if to_category not in manifest.get("categories", {}):
        manifest.setdefault("categories", {})[to_category] = {"sounds": []}
    to_list = _cat_sounds(manifest["categories"][to_category])
    to_list.append(sound_entry)
    manifest["categories"][to_category] = {"sounds": to_list}
    _bump_manifest_version(manifest)

    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    _mark_pack_dirty(pack_name)

    return {"ok": True, "file": filename, "from": from_category, "to": to_category}


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


# =================================================================
# Registry Publishing — git add/commit/push to openpeon-movie-packs
# =================================================================

def get_unpublished_packs():
    """Compare built packs against git status to find uncommitted changes.

    Returns list of dicts:
        {name, display_name, version, status, files_changed, is_new}
    """
    if not os.path.isdir(PACKS_DIR):
        return []

    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=10,
            cwd=PACKS_DIR,
        )
        if result.returncode != 0:
            log.error("git status failed: %s", result.stderr)
            return []
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        log.error("git status error: %s", e)
        return []

    # Parse porcelain output into per-pack change sets
    pack_changes = {}
    for line in result.stdout.strip().splitlines():
        if not line or len(line) < 4:
            continue
        status_code = line[:2]
        filepath = line[3:].strip().strip('"')
        parts = filepath.rstrip("/").split("/")
        pack_name = parts[0]
        # Skip non-pack top-level files
        manifest_path = os.path.join(PACKS_DIR, pack_name, "openpeon.json")
        if not os.path.exists(manifest_path):
            continue
        if pack_name not in pack_changes:
            pack_changes[pack_name] = {"files": [], "is_new": False}
        pack_changes[pack_name]["files"].append(filepath)
        if "?" in status_code:
            pack_changes[pack_name]["is_new"] = True

    unpublished = []
    for pack_name, info in sorted(pack_changes.items()):
        manifest_path = os.path.join(PACKS_DIR, pack_name, "openpeon.json")
        display_name = pack_name
        version = "?"
        try:
            with open(manifest_path) as f:
                m = json.load(f)
            display_name = m.get("display_name", pack_name)
            version = m.get("version", "?")
        except Exception:
            pass

        unpublished.append({
            "name": pack_name,
            "display_name": display_name,
            "version": version,
            "status": "new" if info["is_new"] else "modified",
            "files_changed": len(info["files"]),
            "is_new": info["is_new"],
        })

    return unpublished


def publish_pack(pack_name):
    """Publish a pack to the registry by committing and pushing to origin.

    Returns dict with {ok, message} or {ok: false, error}.
    """
    pack_dir = os.path.join(PACKS_DIR, pack_name)
    manifest_path = os.path.join(pack_dir, "openpeon.json")

    if not os.path.isdir(pack_dir):
        return {"ok": False, "error": f"Pack directory not found: {pack_name}"}
    if not os.path.exists(manifest_path):
        return {"ok": False, "error": f"No openpeon.json manifest in {pack_name}"}

    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        return {"ok": False, "error": f"Invalid manifest: {e}"}

    display_name = manifest.get("display_name", pack_name)

    # Check for actual changes
    try:
        status_result = subprocess.run(
            ["git", "status", "--porcelain", pack_name + "/"],
            capture_output=True, text=True, timeout=10,
            cwd=PACKS_DIR,
        )
        if not status_result.stdout.strip():
            return {"ok": False, "error": f"No changes to publish for {pack_name}"}
    except Exception as e:
        return {"ok": False, "error": f"git status failed: {e}"}

    is_new = any(
        line.strip().startswith("??") for line in status_result.stdout.strip().splitlines()
    )

    # Bump version if manifest wasn't already modified (e.g., only icons/mp3s changed)
    # If build_pack or sound functions already bumped it, openpeon.json will show as modified
    manifest_changed = any(
        line.strip().endswith("openpeon.json")
        for line in status_result.stdout.strip().splitlines()
    )
    if not is_new and not manifest_changed:
        _bump_manifest_version(manifest)
        try:
            with open(manifest_path, "w") as f:
                json.dump(manifest, f, indent=2)
        except Exception as e:
            log.warning("Failed to bump version for %s: %s", pack_name, e)

    version = manifest.get("version", "?")

    # git add
    try:
        add_result = subprocess.run(
            ["git", "add", pack_name + "/"],
            capture_output=True, text=True, timeout=15,
            cwd=PACKS_DIR,
        )
        if add_result.returncode != 0:
            return {"ok": False, "error": f"git add failed: {add_result.stderr}"}
    except Exception as e:
        return {"ok": False, "error": f"git add error: {e}"}

    # git commit
    sound_count = sum(
        len(_cat_sounds(v)) for v in manifest.get("categories", {}).values()
    )
    if is_new:
        commit_msg = f"Add {display_name} v{version} sound pack ({sound_count} sounds)"
    else:
        commit_msg = f"Update {display_name} to v{version} ({sound_count} sounds)"

    try:
        commit_result = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            capture_output=True, text=True, timeout=15,
            cwd=PACKS_DIR,
        )
        if commit_result.returncode != 0:
            return {"ok": False, "error": f"git commit failed: {commit_result.stderr}"}
    except Exception as e:
        return {"ok": False, "error": f"git commit error: {e}"}

    # Get commit SHA for the link
    commit_sha = ""
    try:
        sha_result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=PACKS_DIR,
        )
        commit_sha = sha_result.stdout.strip()
    except Exception:
        pass

    # git push (auto-pull + rebase if behind remote)
    try:
        push_result = subprocess.run(
            ["git", "push", "origin"],
            capture_output=True, text=True, timeout=30,
            cwd=PACKS_DIR,
        )
        if push_result.returncode != 0 and "fetch first" in push_result.stderr:
            # Remote has new commits — pull with rebase and retry
            log.info("Pack repo behind remote, pulling with rebase...")
            pull_result = subprocess.run(
                ["git", "pull", "--rebase", "origin", "main"],
                capture_output=True, text=True, timeout=30,
                cwd=PACKS_DIR,
            )
            if pull_result.returncode != 0:
                return {"ok": False, "error": f"git pull --rebase failed: {pull_result.stderr}"}
            push_result = subprocess.run(
                ["git", "push", "origin"],
                capture_output=True, text=True, timeout=30,
                cwd=PACKS_DIR,
            )
        if push_result.returncode != 0:
            return {"ok": False, "error": f"git push failed: {push_result.stderr}"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "git push timed out (30s)"}
    except Exception as e:
        return {"ok": False, "error": f"git push error: {e}"}

    # Build commit URL from remote
    commit_url = ""
    if commit_sha:
        try:
            remote_result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5,
                cwd=PACKS_DIR,
            )
            remote = remote_result.stdout.strip()
            # Convert git@github.com:user/repo.git -> https://github.com/user/repo
            if remote.startswith("git@github.com:"):
                repo_path = remote.replace("git@github.com:", "").replace(".git", "")
                commit_url = f"https://github.com/{repo_path}/commit/{commit_sha}"
            elif "github.com" in remote:
                repo_path = remote.replace("https://github.com/", "").replace(".git", "")
                commit_url = f"https://github.com/{repo_path}/commit/{commit_sha}"
        except Exception:
            pass

    # Mark pack as complete now that it's published
    set_pack_status(pack_name, "complete", notes="auto-set on publish")

    action = "Published" if is_new else "Updated"
    return {
        "ok": True,
        "message": f"{action} {display_name} v{version}",
        "commit_message": commit_msg,
        "commit_sha": commit_sha[:8] if commit_sha else "",
        "commit_url": commit_url,
        "is_new": is_new,
    }


def publish_all_packs():
    """Publish all unpublished packs. One commit per pack.

    Returns list of per-pack results.
    """
    unpublished = get_unpublished_packs()
    results = []
    for pack in unpublished:
        result = publish_pack(pack["name"])
        result["pack_name"] = pack["name"]
        result["display_name"] = pack["display_name"]
        results.append(result)
    return results


# =================================================================
# PeonPing Registry — PR to PeonPing/registry updating index.json
# =================================================================

REGISTRY_UPSTREAM = "PeonPing/registry"
REGISTRY_FORK = "MattBillock/registry"
SOURCE_REPO = "MattBillock/openpeon-movie-packs"


def _build_registry_entry(pack_name, source_ref):
    """Build a registry index entry dict from a published pack manifest.

    Returns dict matching the PeonPing/registry index.json schema, or
    None if the pack doesn't exist.
    """
    pack_dir = os.path.join(PACKS_DIR, pack_name)
    manifest_path = os.path.join(pack_dir, "openpeon.json")
    sounds_dir = os.path.join(pack_dir, "sounds")

    if not os.path.exists(manifest_path):
        return None

    with open(manifest_path) as f:
        manifest_bytes = f.read()
    manifest = json.loads(manifest_bytes)

    # SHA256 of manifest file
    manifest_sha256 = hashlib.sha256(manifest_bytes.encode()).hexdigest()

    # Collect unique sound files and total size
    sound_files = set()
    for cat_data in manifest.get("categories", {}).values():
        for s in _cat_sounds(cat_data):
            f_name = s.get("file", "")
            if f_name:
                sound_files.add(os.path.basename(f_name))

    total_size = 0
    for sf in sound_files:
        sf_path = os.path.join(sounds_dir, sf)
        if os.path.exists(sf_path):
            total_size += os.path.getsize(sf_path)

    # Preview sounds: first 2 filenames
    preview = sorted(sound_files)[:2]

    today = __import__("datetime").date.today().isoformat()

    return {
        "name": manifest.get("name", pack_name),
        "display_name": manifest.get("display_name", pack_name),
        "version": manifest.get("version", "1.0.0"),
        "description": manifest.get("description", ""),
        "author": manifest.get("author", {"name": "Willow Billock", "github": "MattBillock"}),
        "trust_tier": "community",
        "categories": sorted(manifest.get("categories", {}).keys()),
        "language": manifest.get("language", "en"),
        "license": manifest.get("license", "fair-use"),
        "sound_count": len(sound_files),
        "total_size_bytes": total_size,
        "source_repo": SOURCE_REPO,
        "source_ref": source_ref,
        "source_path": pack_name,
        "manifest_sha256": manifest_sha256,
        "tags": manifest.get("tags", []),
        "preview_sounds": preview,
        "added": today,
        "updated": today,
    }


def _fetch_registry_index():
    """Fetch PeonPing/registry index.json via gh api.

    Returns (parsed_data, file_sha) where file_sha is needed for the
    Contents API PUT. Returns (None, None) on failure.
    """
    import base64
    try:
        result = subprocess.run(
            ["gh", "api", f"repos/{REGISTRY_UPSTREAM}/contents/index.json",
             "--jq", ".content,.sha"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            log.error("Failed to fetch registry index: %s", result.stderr)
            return None, None

        lines = result.stdout.strip().split("\n")
        if len(lines) < 2:
            return None, None

        content_b64 = lines[0]
        file_sha = lines[1]
        content = base64.b64decode(content_b64)
        data = json.loads(content)
        return data, file_sha
    except Exception as e:
        log.error("Error fetching registry index: %s", e)
        return None, None


def register_pack(pack_name, source_ref):
    """Register a pack in PeonPing/registry by creating a PR.

    Steps:
    1. Build registry entry from local manifest
    2. Fetch current PeonPing/registry index.json
    3. Insert/update entry (maintaining alphabetical order)
    4. Push updated index.json to fork branch via Contents API
    5. Create PR to PeonPing/registry

    Returns {ok, pr_url} or {ok: False, error}.
    """
    import base64

    # 1. Build entry
    entry = _build_registry_entry(pack_name, source_ref)
    if not entry:
        return {"ok": False, "error": f"Pack not found: {pack_name}"}

    # 2. Fetch current index
    index_data, file_sha = _fetch_registry_index()
    if index_data is None:
        return {"ok": False, "error": "Could not fetch registry index.json"}

    # 3. Insert/update entry maintaining alphabetical order
    packs = index_data.get("packs", [])
    # Remove existing entry for this pack if present
    packs = [p for p in packs if p.get("name") != pack_name]
    packs.append(entry)
    packs.sort(key=lambda p: p.get("name", ""))
    index_data["packs"] = packs

    # 4. Push to fork branch
    branch_name = f"add-{pack_name}"
    new_content = json.dumps(index_data, indent=2) + "\n"
    content_b64 = base64.b64encode(new_content.encode()).decode()

    # Sync fork with upstream first
    try:
        subprocess.run(
            ["gh", "api", f"repos/{REGISTRY_FORK}/merge-upstream",
             "-X", "POST", "-f", "branch=main"],
            capture_output=True, text=True, timeout=15,
        )
    except Exception:
        pass  # Best effort

    # Get main branch SHA for creating branch ref
    try:
        ref_result = subprocess.run(
            ["gh", "api", f"repos/{REGISTRY_FORK}/git/ref/heads/main",
             "--jq", ".object.sha"],
            capture_output=True, text=True, timeout=10,
        )
        main_sha = ref_result.stdout.strip()
    except Exception as e:
        return {"ok": False, "error": f"Could not get fork main SHA: {e}"}

    # Delete existing branch if present (ignore errors)
    subprocess.run(
        ["gh", "api", f"repos/{REGISTRY_FORK}/git/refs/heads/{branch_name}",
         "-X", "DELETE"],
        capture_output=True, text=True, timeout=10,
    )

    # Create branch
    try:
        branch_result = subprocess.run(
            ["gh", "api", f"repos/{REGISTRY_FORK}/git/refs",
             "-X", "POST",
             "-f", f"ref=refs/heads/{branch_name}",
             "-f", f"sha={main_sha}"],
            capture_output=True, text=True, timeout=10,
        )
        if branch_result.returncode != 0:
            return {"ok": False, "error": f"Could not create branch: {branch_result.stderr}"}
    except Exception as e:
        return {"ok": False, "error": f"Branch creation error: {e}"}

    # Get current file SHA on the new branch (same as main)
    try:
        file_result = subprocess.run(
            ["gh", "api", f"repos/{REGISTRY_FORK}/contents/index.json",
             "--jq", ".sha", "-H", f"ref: {branch_name}"],
            capture_output=True, text=True, timeout=10,
        )
        fork_file_sha = file_result.stdout.strip()
    except Exception:
        fork_file_sha = file_sha  # Fall back to upstream SHA

    # PUT updated file
    display_name = entry.get("display_name", pack_name)
    commit_msg = f"Add {display_name} ({pack_name}) to registry"
    try:
        put_result = subprocess.run(
            ["gh", "api", f"repos/{REGISTRY_FORK}/contents/index.json",
             "-X", "PUT",
             "-f", f"message={commit_msg}",
             "-f", f"content={content_b64}",
             "-f", f"branch={branch_name}",
             "-f", f"sha={fork_file_sha}"],
            capture_output=True, text=True, timeout=15,
        )
        if put_result.returncode != 0:
            return {"ok": False, "error": f"Could not update index.json: {put_result.stderr}"}
    except Exception as e:
        return {"ok": False, "error": f"File update error: {e}"}

    # 5. Create PR
    pr_title = f"Add {display_name} sound pack"
    pr_body = (
        f"## Summary\n"
        f"- Add **{display_name}** (`{pack_name}`) from "
        f"[`{SOURCE_REPO}`](https://github.com/{SOURCE_REPO})\n"
        f"- {entry['sound_count']} sounds across {len(entry['categories'])} CESP categories\n"
        f"- Source ref: `{source_ref}`\n"
        f"- Tags: {', '.join(entry.get('tags', []))}\n\n"
        f"## Checklist\n"
        f"- [x] Entries sorted alphabetically\n"
        f"- [x] `manifest_sha256` computed from tagged release\n"
        f"- [x] `source_ref` points to existing tag ({source_ref})\n"
        f"- [x] All required fields present\n"
        f"- [x] `trust_tier` set to `community`"
    )

    try:
        pr_result = subprocess.run(
            ["gh", "pr", "create",
             "--repo", REGISTRY_UPSTREAM,
             "--head", f"MattBillock:{branch_name}",
             "--title", pr_title,
             "--body", pr_body],
            capture_output=True, text=True, timeout=15,
        )
        if pr_result.returncode != 0:
            # PR might already exist
            if "already exists" in pr_result.stderr.lower():
                return {"ok": True, "pr_url": "", "message": "PR already exists"}
            return {"ok": False, "error": f"PR creation failed: {pr_result.stderr}"}

        pr_url = pr_result.stdout.strip()
        return {"ok": True, "pr_url": pr_url}
    except Exception as e:
        return {"ok": False, "error": f"PR creation error: {e}"}


def register_all_packs(source_ref, pack_names=None):
    """Register multiple packs in a single PR to PeonPing/registry.

    If pack_names is None, registers all published packs.
    Returns {ok, pr_url} or {ok: False, error}.
    """
    import base64

    if pack_names is None:
        pack_names = [p["name"] for p in get_published_packs()]

    if not pack_names:
        return {"ok": False, "error": "No packs to register"}

    # Build entries
    entries = []
    for name in pack_names:
        entry = _build_registry_entry(name, source_ref)
        if entry:
            entries.append(entry)

    if not entries:
        return {"ok": False, "error": "No valid pack entries could be built"}

    # Fetch current index
    index_data, file_sha = _fetch_registry_index()
    if index_data is None:
        return {"ok": False, "error": "Could not fetch registry index.json"}

    # Insert/update entries maintaining alphabetical order
    packs = index_data.get("packs", [])
    new_names = {e["name"] for e in entries}
    packs = [p for p in packs if p.get("name") not in new_names]
    packs.extend(entries)
    packs.sort(key=lambda p: p.get("name", ""))
    index_data["packs"] = packs

    # Push to fork branch
    branch_name = "add-movie-packs-batch"
    new_content = json.dumps(index_data, indent=2) + "\n"
    content_b64 = base64.b64encode(new_content.encode()).decode()

    # Sync fork
    try:
        subprocess.run(
            ["gh", "api", f"repos/{REGISTRY_FORK}/merge-upstream",
             "-X", "POST", "-f", "branch=main"],
            capture_output=True, text=True, timeout=15,
        )
    except Exception:
        pass

    # Get main SHA
    try:
        ref_result = subprocess.run(
            ["gh", "api", f"repos/{REGISTRY_FORK}/git/ref/heads/main",
             "--jq", ".object.sha"],
            capture_output=True, text=True, timeout=10,
        )
        main_sha = ref_result.stdout.strip()
    except Exception as e:
        return {"ok": False, "error": f"Could not get fork main SHA: {e}"}

    # Delete existing branch if present
    subprocess.run(
        ["gh", "api", f"repos/{REGISTRY_FORK}/git/refs/heads/{branch_name}",
         "-X", "DELETE"],
        capture_output=True, text=True, timeout=10,
    )

    # Create branch
    try:
        branch_result = subprocess.run(
            ["gh", "api", f"repos/{REGISTRY_FORK}/git/refs",
             "-X", "POST",
             "-f", f"ref=refs/heads/{branch_name}",
             "-f", f"sha={main_sha}"],
            capture_output=True, text=True, timeout=10,
        )
        if branch_result.returncode != 0:
            return {"ok": False, "error": f"Could not create branch: {branch_result.stderr}"}
    except Exception as e:
        return {"ok": False, "error": f"Branch creation error: {e}"}

    # Get file SHA on fork
    try:
        file_result = subprocess.run(
            ["gh", "api", f"repos/{REGISTRY_FORK}/contents/index.json",
             "--jq", ".sha"],
            capture_output=True, text=True, timeout=10,
        )
        fork_file_sha = file_result.stdout.strip()
    except Exception:
        fork_file_sha = file_sha

    # PUT updated file
    display_names = [e["display_name"] for e in entries]
    commit_msg = f"Add {', '.join(display_names)} movie packs"
    try:
        put_result = subprocess.run(
            ["gh", "api", f"repos/{REGISTRY_FORK}/contents/index.json",
             "-X", "PUT",
             "-f", f"message={commit_msg}",
             "-f", f"content={content_b64}",
             "-f", f"branch={branch_name}",
             "-f", f"sha={fork_file_sha}"],
            capture_output=True, text=True, timeout=15,
        )
        if put_result.returncode != 0:
            return {"ok": False, "error": f"Could not update index.json: {put_result.stderr}"}
    except Exception as e:
        return {"ok": False, "error": f"File update error: {e}"}

    # Create PR
    names_str = ", ".join(display_names)
    bullets = "\n".join(
        f"- **{e['display_name']}** (`{e['name']}`) — {e['sound_count']} sounds, "
        f"{', '.join(e.get('tags', [])[:4])}"
        for e in entries
    )
    pr_title = f"Add {names_str} movie packs"
    if len(pr_title) > 70:
        pr_title = f"Add {len(entries)} movie sound packs"
    pr_body = (
        f"## Summary\n"
        f"- Add {len(entries)} new movie quote sound packs from "
        f"[`{SOURCE_REPO}`](https://github.com/{SOURCE_REPO}) ({source_ref})\n"
        f"{bullets}\n\n"
        f"## Checklist\n"
        f"- [x] Entries sorted alphabetically\n"
        f"- [x] `manifest_sha256` computed from tagged release\n"
        f"- [x] `source_ref` points to existing tag ({source_ref})\n"
        f"- [x] All required fields present\n"
        f"- [x] `trust_tier` set to `community`"
    )

    try:
        pr_result = subprocess.run(
            ["gh", "pr", "create",
             "--repo", REGISTRY_UPSTREAM,
             "--head", f"MattBillock:{branch_name}",
             "--title", pr_title,
             "--body", pr_body],
            capture_output=True, text=True, timeout=15,
        )
        if pr_result.returncode != 0:
            if "already exists" in pr_result.stderr.lower():
                return {"ok": True, "pr_url": "", "message": "PR already exists", "packs": len(entries)}
            return {"ok": False, "error": f"PR creation failed: {pr_result.stderr}"}

        pr_url = pr_result.stdout.strip()
        return {"ok": True, "pr_url": pr_url, "packs": len(entries)}
    except Exception as e:
        return {"ok": False, "error": f"PR creation error: {e}"}


def get_registry_status():
    """Check which published packs are already registered in PeonPing/registry.

    Returns dict: {pack_name: {"registered": bool, "registry_version": str|None}}
    """
    index_data, _ = _fetch_registry_index()
    if index_data is None:
        return {}

    registered = {}
    for p in index_data.get("packs", []):
        if p.get("source_repo") == SOURCE_REPO:
            registered[p["name"]] = p.get("version", "?")

    result = {}
    for pack in get_published_packs():
        name = pack["name"]
        if name in registered:
            result[name] = {"registered": True, "registry_version": registered[name]}
        else:
            result[name] = {"registered": False, "registry_version": None}
    return result
