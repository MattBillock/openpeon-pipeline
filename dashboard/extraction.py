"""Extraction pipeline scanner and controller."""
import glob
import json
import logging
import os
import re
import subprocess
import signal
import time

log = logging.getLogger(__name__)


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_PYTHON = os.path.join(PROJECT_ROOT, ".venv", "bin", "python3")
EXTRACTION_DIR = os.path.join(PROJECT_ROOT, "extraction")
SCRIPTS_PATTERN = os.path.join(EXTRACTION_DIR, "extract_*.py")
MOVIES_DIR = "/Volumes/D-drive-music/Movies"

# Default concurrent extractions — adjustable via sidebar slider in the UI.
# Stored in a mutable container so the UI can update it at runtime.
_SETTINGS_PATH = os.path.join(PROJECT_ROOT, ".openpeon_settings.json")


def _load_settings():
    try:
        with open(_SETTINGS_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_settings(settings):
    try:
        with open(_SETTINGS_PATH, "w") as f:
            json.dump(settings, f, indent=2)
    except Exception as e:
        log.warning("Failed to save settings: %s", e)


def get_max_concurrent():
    return _load_settings().get("max_concurrent_extractions", 2)


def set_max_concurrent(n):
    settings = _load_settings()
    settings["max_concurrent_extractions"] = max(1, min(n, 4))
    _save_settings(settings)


# Legacy constant — use get_max_concurrent() instead
MAX_CONCURRENT_EXTRACTIONS = 2

# Template for new extraction scripts
_SCRIPT_TEMPLATE = '''#!/usr/bin/env python3
"""Extract {title} audio clips."""
import sys
from extractor import run_extraction

MKV = "{mkv_path}"
AUDIO_STREAM = "{audio_stream}"

CLIPS = [
{clips_block}]

if __name__ == "__main__":
    run_extraction(
        movie_name="{name}",
        mkv_path=MKV,
        audio_stream=AUDIO_STREAM,
        clips=CLIPS,
        targets=sys.argv[1:] if len(sys.argv) > 1 else None,
    )
'''


def find_mkv_files(search_term=""):
    """Search for MKV files on D-drive.

    Returns list of dicts with 'dir_name', 'mkv_path', 'size_gb'.
    """
    results = []
    if not os.path.isdir(MOVIES_DIR):
        return results

    for movie_dir in sorted(os.listdir(MOVIES_DIR)):
        if search_term and search_term.lower() not in movie_dir.lower():
            continue
        full_dir = os.path.join(MOVIES_DIR, movie_dir)
        if not os.path.isdir(full_dir):
            continue
        for f in os.listdir(full_dir):
            if f.endswith(".mkv"):
                mkv_path = os.path.join(full_dir, f)
                try:
                    size_gb = round(os.path.getsize(mkv_path) / (1024**3), 1)
                except OSError:
                    size_gb = 0
                results.append({
                    "dir_name": movie_dir,
                    "mkv_path": mkv_path,
                    "size_gb": size_gb,
                })
    return results


def create_movie_script(name, title, mkv_path, audio_stream="0:1", clips=None):
    """Create a new extraction script for a movie.

    Args:
        name: slug name (e.g. 'baseketball')
        title: display title (e.g. 'BASEketball (1998)')
        mkv_path: full path to MKV file
        audio_stream: ffmpeg audio stream (default '0:1')
        clips: optional list of (clip_name, timestamp, quote, duration) tuples

    Returns:
        dict with 'ok' and 'script_path' or 'error'
    """
    script_path = os.path.join(EXTRACTION_DIR, f"extract_{name}.py")
    if os.path.exists(script_path):
        return {"ok": False, "error": f"Script already exists: extract_{name}.py"}

    # Format clips block
    if clips:
        lines = []
        for clip_name, ts, quote, dur in clips:
            # Escape quotes in the quote text
            safe_quote = quote.replace('"', '\\"')
            lines.append(f'    ("{clip_name}", {ts}, "{safe_quote}", {dur}),')
        clips_block = "\n".join(lines) + "\n"
    else:
        clips_block = "    # Add clips: (clip_name, timestamp_seconds, quote_text, duration_seconds)\n"

    content = _SCRIPT_TEMPLATE.format(
        title=title,
        name=name,
        mkv_path=mkv_path,
        audio_stream=audio_stream,
        clips_block=clips_block,
    )

    # Write script
    with open(script_path, "w") as f:
        f.write(content)

    # Create output directory
    output_dir = os.path.join(EXTRACTION_DIR, name)
    os.makedirs(output_dir, exist_ok=True)

    log.info("Created extraction script: %s", script_path)
    return {"ok": True, "script_path": script_path}


def add_clips_to_script(name, new_clips):
    """Add clips to an existing extraction script.

    Args:
        name: movie slug
        new_clips: list of (clip_name, timestamp, quote, duration) tuples

    Returns:
        dict with 'ok' and 'added' count or 'error'
    """
    script_path = os.path.join(EXTRACTION_DIR, f"extract_{name}.py")
    if not os.path.exists(script_path):
        return {"ok": False, "error": f"Script not found: extract_{name}.py"}

    with open(script_path) as f:
        content = f.read()

    # Find existing clip names to avoid duplicates
    existing = set()
    pattern = r'\("([^"]+)",\s*(\d+),\s*"([^"]+)",\s*(\d+)\)'
    for match in re.finditer(pattern, content):
        existing.add(match.group(1))

    # Build new clip lines
    added = 0
    new_lines = []
    for clip_name, ts, quote, dur in new_clips:
        if clip_name in existing:
            continue
        safe_quote = quote.replace('"', '\\"')
        new_lines.append(f'    ("{clip_name}", {ts}, "{safe_quote}", {dur}),')
        added += 1

    if not new_lines:
        return {"ok": True, "added": 0, "message": "All clips already exist"}

    # Insert before the closing bracket of CLIPS
    # Find the CLIPS = [ ... ] block and insert before the last ]
    insert_text = "\n".join(new_lines) + "\n"

    # Find the ']' that closes CLIPS
    clips_start = content.find("CLIPS = [")
    if clips_start < 0:
        return {"ok": False, "error": "Could not find CLIPS = [ in script"}

    # Find matching close bracket
    bracket_depth = 0
    close_pos = None
    for i in range(clips_start, len(content)):
        if content[i] == '[':
            bracket_depth += 1
        elif content[i] == ']':
            bracket_depth -= 1
            if bracket_depth == 0:
                close_pos = i
                break

    if close_pos is None:
        return {"ok": False, "error": "Could not find closing ] for CLIPS"}

    # Insert new lines before the closing ]
    new_content = content[:close_pos] + insert_text + content[close_pos:]

    with open(script_path, "w") as f:
        f.write(new_content)

    log.info("Added %d clips to %s", added, script_path)
    return {"ok": True, "added": added}


def remove_clip_from_script(name, clip_name):
    """Remove a clip from an extraction script.

    Returns:
        dict with 'ok' or 'error'
    """
    script_path = os.path.join(EXTRACTION_DIR, f"extract_{name}.py")
    if not os.path.exists(script_path):
        return {"ok": False, "error": f"Script not found: extract_{name}.py"}

    with open(script_path) as f:
        content = f.read()

    # Find and remove the line for this clip
    pattern = rf'\s*\("{re.escape(clip_name)}",\s*\d+,\s*"[^"]*",\s*\d+\),?\n?'
    new_content, count = re.subn(pattern, "\n", content)

    if count == 0:
        return {"ok": False, "error": f"Clip '{clip_name}' not found in script"}

    with open(script_path, "w") as f:
        f.write(new_content)

    return {"ok": True}


def slugify(text):
    """Convert text to a clean slug for clip/movie names."""
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9\s_]', '', text)
    text = re.sub(r'\s+', '_', text)
    text = re.sub(r'_+', '_', text)
    return text.strip('_')


def get_all_scripts():
    """Get all extraction scripts with their metadata."""
    scripts = []
    for script_path in sorted(glob.glob(SCRIPTS_PATTERN)):
        name = os.path.basename(script_path).replace("extract_", "").replace(".py", "")
        output_dir = os.path.join(EXTRACTION_DIR, name)

        # Parse clip count and clip details from script
        total_clips = 0
        clip_details = {}
        try:
            with open(script_path) as f:
                content = f.read()
            pattern = r'\("([^"]+)",\s*(\d+),\s*"([^"]+)",\s*(\d+)\)'
            for match in re.finditer(pattern, content):
                filename = match.group(1)
                timestamp = int(match.group(2))
                quote = match.group(3)
                duration = int(match.group(4))
                clip_details[filename] = {
                    "timestamp": timestamp,
                    "quote": quote,
                    "duration": duration,
                }
                total_clips += 1
        except Exception as e:
            log.warning("Failed to parse clips from %s: %s", script_path, e)

        # Count extracted clips (exclude unverified/ subdirectory)
        extracted = []
        if os.path.isdir(output_dir):
            extracted = [f for f in os.listdir(output_dir)
                        if f.endswith(".mp3") and not f.startswith(".")]

        # Load extraction log (new pipeline)
        ext_log = _load_extraction_log(name)

        # Check if running
        is_running = _is_script_running(script_path)

        # Load review state
        review = _load_review(name)

        # Compute counts from extraction log
        verified = sum(1 for v in ext_log.values() if v.get("verify_status") == "verified")
        review_count = sum(1 for v in ext_log.values() if v.get("verify_status") == "review" or v.get("final_status") == "review")
        failed = sum(1 for v in ext_log.values() if v.get("final_status") == "failed")

        # Review counts
        approved_count = len([c for c in review.values() if c.get("status") == "approved"])
        rejected_count = len([c for c in review.values() if c.get("status") == "rejected"])
        unreviewed_count = len(extracted) - approved_count - rejected_count

        # Last activity from extraction_log.json mtime
        last_activity = get_last_activity(name)

        scripts.append({
            "name": name,
            "script_path": script_path,
            "output_dir": output_dir,
            "total_clips": total_clips,
            "clip_details": clip_details,
            "extracted_count": len(extracted),
            "extracted_files": sorted(extracted),
            "is_running": is_running,
            "approved": approved_count,
            "rejected": rejected_count,
            "unreviewed": max(0, unreviewed_count),
            "verified": verified,
            "needs_review": review_count,
            "failed": failed,
            "ext_log": ext_log,
            "last_activity": last_activity,
        })

    return scripts


def get_last_activity(name):
    """Get the last-modified time of extraction_log.json as a proxy for activity.

    Returns epoch float or None if no log exists.
    """
    log_path = os.path.join(EXTRACTION_DIR, name, "extraction_log.json")
    try:
        return os.path.getmtime(log_path)
    except OSError:
        return None


def _load_extraction_log(name):
    """Load extraction_log.json for a movie."""
    log_path = os.path.join(EXTRACTION_DIR, name, "extraction_log.json")
    if os.path.exists(log_path):
        try:
            with open(log_path) as f:
                return json.load(f)
        except Exception as e:
            log.error("Corrupted extraction_log.json for %s: %s", name, e)
    return {}


def _load_review(name):
    """Load review.json for a movie."""
    review_path = os.path.join(EXTRACTION_DIR, name, "review.json")
    if os.path.exists(review_path):
        try:
            with open(review_path) as f:
                return json.load(f)
        except Exception as e:
            log.error("Corrupted review.json for %s: %s", name, e)
    return {}


def _is_script_running(script_path):
    """Check if an extraction script is currently running."""
    script_name = os.path.basename(script_path)
    try:
        result = subprocess.run(
            ["pgrep", "-f", script_name],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except Exception as e:
        log.warning("pgrep failed for %s: %s", script_name, e)
        return False


def _count_running_extractions():
    """Count how many extraction scripts are currently running."""
    count = 0
    for script_path in glob.glob(SCRIPTS_PATTERN):
        if _is_script_running(script_path):
            count += 1
    return count


def start_extraction(name, targets=None):
    """Start an extraction script as a background process.

    Enforces MAX_CONCURRENT_EXTRACTIONS to protect system resources.
    Uses nice -n 10 so ffmpeg/Whisper don't starve macOS audio.
    """
    script_path = os.path.join(EXTRACTION_DIR, f"extract_{name}.py")
    if not os.path.exists(script_path):
        return {"error": f"Script not found: {script_path}"}

    if _is_script_running(script_path):
        return {"error": f"Already running: {name}"}

    # Enforce concurrency limit
    max_concurrent = get_max_concurrent()
    running_count = _count_running_extractions()
    if running_count >= max_concurrent:
        return {
            "error": f"Limit reached: {running_count}/{max_concurrent} "
                     f"extraction(s) already running. Stop one first or wait for it to finish.",
        }

    output_dir = os.path.join(EXTRACTION_DIR, name)
    log_path = os.path.join(output_dir, "extraction.log")
    os.makedirs(output_dir, exist_ok=True)

    # Use project venv python (has both whisper and all deps).
    # nice -n 10 to avoid starving macOS audio.
    python = PROJECT_PYTHON if os.path.exists(PROJECT_PYTHON) else "python3"
    cmd = ["nice", "-n", "10", python, "-u", script_path]
    if targets:
        cmd.extend(targets)

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    with open(log_path, "w") as log:
        proc = subprocess.Popen(
            cmd,
            stdout=log, stderr=subprocess.STDOUT,
            cwd=EXTRACTION_DIR,
            start_new_session=True,
            env=env,
        )

    return {"status": "started", "pid": proc.pid}


def stop_extraction(name):
    """Stop a running extraction script."""
    script_name = f"extract_{name}.py"
    try:
        result = subprocess.run(
            ["pgrep", "-f", script_name],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                try:
                    os.kill(int(pid), signal.SIGTERM)
                except Exception as e:
                    log.warning("Failed to kill PID %s: %s", pid, e)
            return {"status": "stopped", "pids": pids}
        return {"error": "Not running"}
    except Exception as e:
        return {"error": str(e)}


def get_clips_for_review(name):
    """Get all clips for a movie, combining extraction log + review state + expected quotes."""
    output_dir = os.path.join(EXTRACTION_DIR, name)
    ext_log = _load_extraction_log(name)
    review = _load_review(name)

    # Parse expected quotes from script
    script_path = os.path.join(EXTRACTION_DIR, f"extract_{name}.py")
    clip_details = {}
    try:
        with open(script_path) as f:
            content = f.read()
        pattern = r'\("([^"]+)",\s*(\d+),\s*"([^"]+)",\s*(\d+)\)'
        for match in re.finditer(pattern, content):
            clip_details[match.group(1)] = {
                "quote": match.group(3),
                "timestamp": int(match.group(2)),
            }
    except Exception as e:
        log.warning("Failed to parse clip details for review from %s: %s", script_path, e)

    clips = []
    # Include all expected clips, not just extracted ones
    all_clip_names = set(clip_details.keys())
    if os.path.isdir(output_dir):
        for f in os.listdir(output_dir):
            if f.endswith(".mp3") and not f.startswith("."):
                all_clip_names.add(f.replace(".mp3", ""))

    for clip_name in sorted(all_clip_names):
        mp3_path = os.path.join(output_dir, f"{clip_name}.mp3")
        has_mp3 = os.path.exists(mp3_path)

        clip_review = review.get(clip_name, {})
        log_entry = ext_log.get(clip_name, {})
        detail = clip_details.get(clip_name, {})

        clips.append({
            "name": clip_name,
            "filename": f"{clip_name}.mp3",
            "path": mp3_path,
            "has_mp3": has_mp3,
            "size_kb": round(os.path.getsize(mp3_path) / 1024, 1) if has_mp3 else 0,
            "status": clip_review.get("status", "unreviewed"),
            "category": clip_review.get("category", ""),
            "notes": clip_review.get("notes", ""),
            # Extraction log data
            "expected_quote": detail.get("quote", log_entry.get("quote", "")),
            "verify_score": log_entry.get("verify_score", 0),
            "verify_heard": log_entry.get("verify_heard", ""),
            "verify_status": log_entry.get("verify_status", log_entry.get("final_status", "")),
            "pre_match_score": log_entry.get("pre_match_score", 0),
            "pre_match_text": log_entry.get("pre_match_text", ""),
            "extraction_status": log_entry.get("final_status", "not_extracted" if not has_mp3 else "unknown"),
        })

    return clips


def save_clip_review(name, clip_name, status, category="", notes=""):
    """Save review status for a clip."""
    output_dir = os.path.join(EXTRACTION_DIR, name)
    review_path = os.path.join(output_dir, "review.json")

    review = _load_review(name)
    review[clip_name] = {
        "status": status,
        "category": category,
        "notes": notes,
    }

    os.makedirs(output_dir, exist_ok=True)
    with open(review_path, "w") as f:
        json.dump(review, f, indent=2)

    return review


def save_clip_category(name, clip_name, category):
    """Save only the category for a clip, preserving existing status/notes."""
    review = _load_review(name)
    existing = review.get(clip_name, {})
    existing["category"] = category
    review[clip_name] = existing

    output_dir = os.path.join(EXTRACTION_DIR, name)
    review_path = os.path.join(output_dir, "review.json")
    os.makedirs(output_dir, exist_ok=True)
    with open(review_path, "w") as f:
        json.dump(review, f, indent=2)

    return review


def count_uncategorized_approved(name):
    """Count approved clips that have no category assigned.

    Lightweight scan of review.json — avoids expensive get_clips_for_review().
    """
    review = _load_review(name)
    count = 0
    for clip_data in review.values():
        if clip_data.get("status") == "approved" and not clip_data.get("category"):
            count += 1
    return count


def get_category_counts(name):
    """Get counts of clips assigned to each CESP category for a movie.

    Returns dict of {category: count}. Useful for needs-based suggestions.
    """
    review = _load_review(name)
    counts = {}
    for clip_data in review.values():
        cat = clip_data.get("category", "")
        if cat:
            counts[cat] = counts.get(cat, 0) + 1
    return counts


def get_extraction_log(name, tail=50):
    """Get the last N lines of an extraction log."""
    log_path = os.path.join(EXTRACTION_DIR, name, "extraction.log")
    if not os.path.exists(log_path):
        return ""
    try:
        with open(log_path) as f:
            lines = f.readlines()
        return "".join(lines[-tail:])
    except Exception as e:
        log.warning("Failed to read extraction log for %s: %s", name, e)
        return ""


def get_all_movie_names():
    """Get names of all movies with extraction scripts."""
    names = []
    for script_path in sorted(glob.glob(SCRIPTS_PATTERN)):
        name = os.path.basename(script_path).replace("extract_", "").replace(".py", "")
        names.append(name)
    return names


def retry_clip(name, clip_name, override_timestamp=None):
    """Re-run extraction for a single clip on Mini via SSH.

    Steps:
    1. Clear the clip's verify_status in extraction_log.json (so extractor won't skip it)
    2. If override_timestamp provided, write to overrides.json
    3. SSH to Mini and run the extraction script for just this clip
    4. Sync results back locally
    """
    # 1. Clear clip from extraction log so extractor re-processes it
    _clear_clip_from_log(name, clip_name)

    # 2. Write manual timestamp override if provided
    if override_timestamp is not None:
        overrides_path = os.path.join(EXTRACTION_DIR, name, "overrides.json")
        overrides = {}
        if os.path.exists(overrides_path):
            try:
                with open(overrides_path) as f:
                    overrides = json.load(f)
            except Exception:
                pass
        overrides[clip_name] = float(override_timestamp)
        with open(overrides_path, "w") as f:
            json.dump(overrides, f, indent=2)
        # Sync overrides to Mini
        try:
            subprocess.run(
                ["rsync", "-q", overrides_path,
                 f"mini:~/dev/openpeon/extraction/{name}/overrides.json"],
                timeout=10, capture_output=True,
            )
        except Exception as e:
            log.warning("Failed to sync overrides to Mini: %s", e)

    # 2. Run on Mini via SSH (where Whisper and MKVs are)
    remote_dir = f"~/dev/openpeon/extraction"
    remote_python = "~/dev/openpeon/.venv/bin/python3"
    remote_script = f"{remote_dir}/extract_{name}.py"

    ssh_cmd = [
        "ssh", "mini",
        f"export PATH=/opt/homebrew/bin:$PATH && "
        f"cd {remote_dir} && "
        f"{remote_python} -u {remote_script} {clip_name}"
    ]

    output_dir = os.path.join(EXTRACTION_DIR, name)
    log_path = os.path.join(output_dir, "extraction.log")
    os.makedirs(output_dir, exist_ok=True)

    try:
        with open(log_path, "a") as logfile:
            logfile.write(f"\n--- RETRY: {clip_name} ---\n")
            proc = subprocess.Popen(
                ssh_cmd,
                stdout=logfile, stderr=subprocess.STDOUT,
                start_new_session=True,
            )
    except Exception as e:
        log.error("Failed to start retry for %s/%s: %s", name, clip_name, e)
        return {"error": str(e)}

    return {"status": "started", "pid": proc.pid, "clip": clip_name}


def _clear_clip_from_log(name, clip_name):
    """Clear a clip's verify_status from extraction_log.json so extractor re-processes it.

    Saves the failed found_at timestamp into exclude_positions so the next
    extraction attempt skips that region and finds a different match.

    Also syncs the modified log to Mini via rsync.
    """
    # Clear locally + accumulate exclusions
    local_log = os.path.join(EXTRACTION_DIR, name, "extraction_log.json")
    if os.path.exists(local_log):
        try:
            with open(local_log) as f:
                data = json.load(f)
            if clip_name in data and isinstance(data[clip_name], dict):
                entry = data[clip_name]
                # Save failed position for exclusion on retry
                found_at = entry.get("found_at")
                if found_at is not None:
                    excludes = entry.get("exclude_positions", [])
                    if found_at not in excludes:
                        excludes.append(found_at)
                    entry["exclude_positions"] = excludes

                entry.pop("verify_status", None)
                entry.pop("final_status", None)
                entry.pop("verify_score", None)
                entry.pop("verify_heard", None)
                with open(local_log, "w") as f:
                    json.dump(data, f, indent=2)
                log.info("Cleared local extraction log for %s/%s (excludes: %s)",
                         name, clip_name, entry.get("exclude_positions", []))
        except Exception as e:
            log.warning("Failed to clear local log for %s/%s: %s", name, clip_name, e)

    # Sync modified log to Mini via rsync (replaces fragile inline Python)
    remote_log = f"mini:~/dev/openpeon/extraction/{name}/extraction_log.json"
    try:
        subprocess.run(
            ["rsync", "-q", local_log, remote_log],
            timeout=10, capture_output=True,
        )
    except Exception as e:
        log.warning("Failed to sync log to Mini for %s/%s: %s", name, clip_name, e)


def sync_from_mini(movie_name=None):
    """Sync extraction results from Mini back to local.

    Args:
        movie_name: optional specific movie to sync, or None for all
    """
    sync_script = os.path.join(EXTRACTION_DIR, "sync_from_mini.sh")
    if not os.path.exists(sync_script):
        return {"error": "sync_from_mini.sh not found"}

    try:
        result = subprocess.run(
            [sync_script],
            capture_output=True, text=True, timeout=60,
            cwd=EXTRACTION_DIR,
        )
        return {"status": "ok", "output": result.stdout[-500:]}
    except subprocess.TimeoutExpired:
        return {"error": "Sync timed out (60s)"}
    except Exception as e:
        return {"error": str(e)}


def delete_transcript(name):
    """Delete corrupted full_transcript.json locally and on Mini via SSH."""
    local_path = os.path.join(EXTRACTION_DIR, name, "full_transcript.json")
    deleted_local = False
    deleted_remote = False

    if os.path.exists(local_path):
        try:
            os.unlink(local_path)
            deleted_local = True
        except OSError as e:
            return {"ok": False, "error": f"Failed to delete local transcript: {e}"}

    # Delete on Mini too
    remote_path = f"~/dev/openpeon/extraction/{name}/full_transcript.json"
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=3", "mini", f"rm -f {remote_path}"],
            capture_output=True, text=True, timeout=10,
        )
        deleted_remote = result.returncode == 0
    except Exception as e:
        log.warning("Failed to delete remote transcript for %s: %s", name, e)

    return {
        "ok": True,
        "deleted_local": deleted_local,
        "deleted_remote": deleted_remote,
    }


def reset_movie_extraction(name):
    """Clear extraction_log.json + full_transcript.json for a full re-run.

    Keeps existing MP3 files intact (they'll be re-verified on next run).
    """
    output_dir = os.path.join(EXTRACTION_DIR, name)
    deleted = []

    for filename in ["extraction_log.json", "full_transcript.json"]:
        path = os.path.join(output_dir, filename)
        if os.path.exists(path):
            try:
                os.unlink(path)
                deleted.append(filename)
            except OSError as e:
                return {"ok": False, "error": f"Failed to delete {filename}: {e}"}

    # Also clear on Mini
    for filename in ["extraction_log.json", "full_transcript.json"]:
        remote_path = f"~/dev/openpeon/extraction/{name}/{filename}"
        try:
            subprocess.run(
                ["ssh", "-o", "ConnectTimeout=3", "mini", f"rm -f {remote_path}"],
                capture_output=True, timeout=10,
            )
        except Exception:
            pass  # Best-effort remote cleanup

    return {"ok": True, "deleted": deleted}


# =================================================================
# Category suggestion based on quote content
# =================================================================

# Keyword patterns that suggest CESP categories
_CATEGORY_HINTS = {
    "session.start": {
        "keywords": [
            "hello", "good morning", "good evening", "welcome", "i'm here",
            "let me introduce", "my name is",
            "here i am", "arrived", "greetings",
        ],
        "patterns": [
            r"^(hi|hey|hello|yo|greetings)\b",  # Must be at start of quote
            r"\bwelcome\b",
            r"\bi('m| am)\s+(here|back|ready)\b",
            r"\bgood\s+(morning|evening|day)\b",
            r"\bmy name is\b",
        ],
    },
    "task.acknowledge": {
        "keywords": [
            "on it", "got it", "understood", "will do", "roger", "copy",
            "affirmative", "right", "yes", "sure", "ok", "fine",
            "fair enough", "very well", "certainly", "absolutely",
        ],
        "patterns": [
            r"\b(yes|yeah|yep|sure|ok|fine|right|absolutely)\b",
            r"\b(roger|copy|affirmative)\b",
            r"\bgot\s+it\b",
            r"\bon\s+it\b",
        ],
    },
    "task.complete": {
        "keywords": [
            "done", "finished", "complete", "victory", "success", "nailed it",
            "made it", "we did it", "accomplished", "mission", "won",
            "well done", "good job", "excellent", "amazing",
            "kicked", "got one", "we got", "beautiful", "nice",
        ],
        "patterns": [
            r"\b(done|finished|complete|accomplished)\b",
            r"\bwe\s+(did|made|got)\s+it\b",
            r"\b(victory|success|won)\b",
            r"\bnot\s+(even\s+)?mad\b",
            r"\bkicked\s+(its|his|her|their)\s+ass\b",
            r"\bnice\s+(shot|work|job|one)\b",
        ],
    },
    "task.error": {
        "keywords": [
            "error", "mistake", "wrong", "broke", "broken", "failed",
            "shit", "damn", "fuck", "hell", "disaster", "terrible",
            "regret", "problem", "trouble", "crazy", "insane",
            "oh no", "oh god", "what happened", "slime",
        ],
        "patterns": [
            r"\b(shit|damn|fuck|hell|crap)\b",
            r"\b(mistake|error|wrong|broke|broken|fail)\b",
            r"\b(disaster|terrible|horrible|awful)\b",
            r"\bregret\b",
            r"\b(oh\s+no|oh\s+god)\b",
            r"\bwhat\s+(happened|went\s+wrong)\b",
        ],
    },
    "input.required": {
        "keywords": [
            "what", "who", "where", "when", "why", "how",
            "do you", "are you", "can you", "would you",
            "answer", "tell me", "listen", "attention", "need",
            "permission", "approve", "allow",
        ],
        "patterns": [
            r"\?$",  # Questions end with ?
            r"\b(what|who|where|when|why|how)\b.*\?",
            r"\bdo\s+you\b",
            r"\bare\s+you\b",
            r"\b(tell|listen|pay\s+attention)\b",
            r"\bneed\s+(to|your)\b",
        ],
    },
    "resource.limit": {
        "keywords": [
            "tired", "exhausted", "can't", "cannot", "limit",
            "enough", "too much", "no more", "depleted", "empty",
            "running out", "out of", "overwhelmed", "constraint",
            "hold", "wait", "stop", "pause",
        ],
        "patterns": [
            r"\b(tired|exhausted|depleted)\b",
            r"\bcan('t|not)\b",
            r"\b(limit|constrain|restrict)\b",
            r"\b(no\s+more|too\s+much|enough)\b",
            r"\brunning\s+out\b",
        ],
    },
    "user.spam": {
        "keywords": [
            "shut up", "shut the fuck up", "stop it", "leave me alone", "go away",
            "annoying", "bother", "pest", "enough already",
            "calm down", "relax", "take it easy", "chill",
            "again", "seriously", "knock it off", "get out",
            "fuck off", "piss off", "scram", "beat it",
        ],
        "patterns": [
            r"\bshut\s+(up|the\s+fuck)\b",
            r"\b(go\s+away|leave\s+me)\b",
            r"\b(stop|quit|knock\s+it\s+off)\b",
            r"\b(calm|relax|chill|easy)\b",
            r"\b(annoying|bother|pest)\b",
            r"\bget\s+out\b",
        ],
        # Boost: if quote contains "shut up" or explicit dismissal, this wins over task.error
        "boost": 0.3,
    },
}


def suggest_category(quote, clip_name="", category_counts=None):
    """Suggest a CESP category for a quote based on content analysis.

    Returns list of (category, confidence) tuples sorted by confidence.
    Always returns at least one category — when no patterns match, uses
    needs-based fallback (prefers under-filled categories).

    Args:
        quote: The quote text to categorize.
        clip_name: Optional clip name for heuristics.
        category_counts: Optional dict of {category: count} for needs-based
            fallback. Categories with fewer clips get priority when no
            strong pattern match exists.
    """
    # Default fallback priority (most generic -> most specific)
    _FALLBACK_ORDER = [
        "task.error",       # Most quotes are reactive/exclamatory
        "task.acknowledge",  # Many quotes are agreements/responses
        "session.start",    # Greetings and intros
        "task.complete",    # Victory/done quotes
        "input.required",   # Questions
        "user.spam",        # Dismissals
        "resource.limit",   # Exhaustion/defeat
    ]

    all_categories = list(_CATEGORY_HINTS.keys())

    if not quote:
        # Even with no quote, return a needs-based suggestion
        if category_counts:
            ranked = sorted(all_categories, key=lambda c: category_counts.get(c, 0))
            return [(c, 0.05) for c in ranked]
        return [(c, 0.05) for c in _FALLBACK_ORDER]

    quote_lower = quote.lower().strip()
    scores = {}

    for category, hints in _CATEGORY_HINTS.items():
        score = 0.0

        # Keyword matching (partial)
        for kw in hints["keywords"]:
            if kw in quote_lower:
                score += 0.3

        # Regex pattern matching (stronger signal)
        for pat in hints["patterns"]:
            if re.search(pat, quote_lower, re.IGNORECASE):
                score += 0.5

        # Category boost (e.g., user.spam gets a boost for dismissals)
        if score > 0 and "boost" in hints:
            score += hints["boost"]

        # Clip name heuristics
        name_lower = clip_name.lower()
        if category == "session.start" and any(w in name_lower for w in ["intro", "hello", "greeting", "start", "welcome"]):
            score += 0.4
        if category == "task.error" and any(w in name_lower for w in ["error", "wrong", "broke", "fail", "shit", "damn"]):
            score += 0.4
        if category == "task.complete" and any(w in name_lower for w in ["done", "finish", "complete", "victory", "win"]):
            score += 0.4
        if category == "input.required" and any(w in name_lower for w in ["question", "ask", "what", "need"]):
            score += 0.4

        # Cap at 1.0
        scores[category] = min(score, 1.0)

    # Check if we got any real matches
    has_matches = any(s > 0 for s in scores.values())

    if has_matches:
        # Sort by score descending — include all categories, matched ones first
        matched = [(cat, score) for cat, score in scores.items() if score > 0]
        matched.sort(key=lambda x: x[1], reverse=True)
        # Append unmatched categories with tiny scores for completeness
        unmatched_cats = [c for c in all_categories if scores.get(c, 0) == 0]
        if category_counts:
            unmatched_cats.sort(key=lambda c: category_counts.get(c, 0))
        unmatched = [(c, 0.01) for c in unmatched_cats]
        return matched + unmatched
    else:
        # No pattern matches at all — use needs-based fallback
        if category_counts:
            # Prefer categories with fewest assigned clips
            ranked = sorted(all_categories, key=lambda c: category_counts.get(c, 0))
            return [(c, 0.05) for c in ranked]
        return [(c, 0.05) for c in _FALLBACK_ORDER]
