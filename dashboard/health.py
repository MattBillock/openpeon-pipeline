"""System health checks and movie diagnostics for the OpenPeon pipeline.

Every function returns plain-English results a non-technical user can act on.
"""
import json
import logging
import os
import re
import subprocess
import time

import streamlit as st

log = logging.getLogger(__name__)

EXTRACTION_DIR = os.path.expanduser("~/dev/openpeon/extraction")
MOVIES_DIR = "/Volumes/D-drive-music/Movies"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_PYTHON = os.path.join(PROJECT_ROOT, ".venv", "bin", "python3")

# Known error patterns in extraction.log
_ERROR_PATTERNS = [
    (r"ERROR: whisper not available", "Whisper not installed",
     "Run extraction on Mini where Whisper is installed, or install openai-whisper locally."),
    (r"not found\. Mount the D-drive", "D-drive disconnected",
     "Plug in the D-drive and wait for it to mount at /Volumes/D-drive-music."),
    (r"ssh: Could not resolve hostname", "Mini unreachable",
     "Check that the Mini is powered on and on the same network."),
    (r"Traceback \(most recent call last\)", "Script crashed",
     "Check the console log for the full traceback — may need a code fix."),
    (r"TimeoutExpired|timed out", "Operation timed out",
     "The extraction step took too long. Try again or check disk/network speed."),
    (r"MemoryError|Killed|signal 9", "Out of memory",
     "The system ran out of RAM. Close other apps or reduce Whisper model size."),
]


# ------------------------------------------------------------------
# Individual health checks
# ------------------------------------------------------------------

def check_d_drive():
    """Is /Volumes/D-drive-music/Movies mounted?"""
    ok = os.path.isdir(MOVIES_DIR)
    return {
        "ok": ok,
        "name": "D-drive",
        "message": "D-drive mounted" if ok else "D-drive not connected",
        "fix": "" if ok else "Plug in the D-drive USB cable and wait for it to appear in Finder.",
    }


def check_whisper():
    """Does the Whisper Python path exist?"""
    ok = os.path.exists(PROJECT_PYTHON)
    return {
        "ok": ok,
        "name": "Whisper",
        "message": "Project venv OK (whisper available)" if ok else "Project venv missing",
        "fix": "" if ok else (
            "Create the project venv:\n"
            "  python3.13 -m venv .venv && .venv/bin/pip install streamlit anthropic openai-whisper"
        ),
    }


def check_ffmpeg():
    """Is ffmpeg installed?"""
    ffmpeg_path = "/opt/homebrew/bin/ffmpeg"
    ok = os.path.exists(ffmpeg_path)
    if not ok:
        # Check PATH as fallback
        try:
            subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
            ok = True
        except Exception:
            pass
    return {
        "ok": ok,
        "name": "ffmpeg",
        "message": "ffmpeg available" if ok else "ffmpeg not installed",
        "fix": "" if ok else "Install ffmpeg: brew install ffmpeg",
    }


def check_system_load():
    """Check CPU load average vs core count."""
    try:
        load_1, load_5, _ = os.getloadavg()
        ncpu = os.cpu_count() or 4
        ratio = load_1 / ncpu
        if ratio > 0.9:
            return {
                "ok": False,
                "name": "System Load",
                "message": f"Heavy load ({load_1:.1f} on {ncpu} cores) — extraction may be slow",
                "load_1": load_1,
                "load_5": load_5,
                "ncpu": ncpu,
            }
        return {
            "ok": True,
            "name": "System Load",
            "message": f"Load {load_1:.1f}/{ncpu} cores",
            "load_1": load_1,
            "load_5": load_5,
            "ncpu": ncpu,
        }
    except Exception:
        return {"ok": True, "name": "System Load", "message": "Load unknown"}


def check_mini_ssh():
    """Can we SSH to Mini? (3s timeout)"""
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=3", "-o", "BatchMode=yes", "mini", "echo ok"],
            capture_output=True, text=True, timeout=5,
        )
        ok = result.returncode == 0 and "ok" in result.stdout
    except Exception:
        ok = False
    return {
        "ok": ok,
        "name": "Mini SSH",
        "message": "Mini reachable" if ok else "Cannot connect to Mini",
        "fix": "" if ok else "Check that the Mini is powered on and on the same network.",
    }


@st.cache_data(ttl=30)
def check_all():
    """Run all health checks and return a summary."""
    checks = [
        check_d_drive(),
        check_whisper(),
        check_ffmpeg(),
        check_mini_ssh(),
    ]
    ok_count = sum(1 for c in checks if c["ok"])
    fail_count = len(checks) - ok_count
    return {
        "checks": checks,
        "ok_count": ok_count,
        "fail_count": fail_count,
        "all_ok": fail_count == 0,
    }


# ------------------------------------------------------------------
# Transcript validation
# ------------------------------------------------------------------

def check_transcript(name):
    """Is full_transcript.json corrupted? (< 100 words/hour = bad)."""
    transcript_path = os.path.join(EXTRACTION_DIR, name, "full_transcript.json")
    if not os.path.exists(transcript_path):
        return {
            "ok": True,  # No transcript isn't a corruption issue
            "name": "Transcript",
            "exists": False,
            "message": "No transcript yet",
            "fix": "",
            "word_count": 0,
            "duration_min": 0,
            "words_per_hour": 0,
        }

    try:
        with open(transcript_path) as f:
            data = json.load(f)
    except Exception as e:
        return {
            "ok": False,
            "name": "Transcript",
            "exists": True,
            "message": f"Transcript file is unreadable: {e}",
            "fix": "Delete the corrupt transcript and re-run extraction.",
            "word_count": 0,
            "duration_min": 0,
            "words_per_hour": 0,
        }

    word_count = data.get("word_count", len(data.get("words", [])))
    duration = data.get("duration", 0)
    duration_min = duration / 60 if duration else 0
    duration_hr = duration / 3600 if duration else 1  # avoid div by zero
    words_per_hour = word_count / duration_hr if duration_hr > 0 else 0

    ok = words_per_hour >= 100
    if ok:
        msg = f"Transcript OK ({word_count:,} words for {duration_min:.0f}-min movie)"
    else:
        msg = f"Transcript corrupted ({word_count} words for {duration_min:.0f}-min movie)"

    return {
        "ok": ok,
        "name": "Transcript",
        "exists": True,
        "message": msg,
        "fix": "" if ok else "Delete the corrupt transcript and re-run extraction.",
        "word_count": word_count,
        "duration_min": duration_min,
        "words_per_hour": round(words_per_hour),
    }


# ------------------------------------------------------------------
# Log error parser
# ------------------------------------------------------------------

def parse_log_errors(name):
    """Scan extraction.log for known error patterns.

    Returns list of {pattern, label, fix, line} dicts.
    """
    log_path = os.path.join(EXTRACTION_DIR, name, "extraction.log")
    if not os.path.exists(log_path):
        return []

    try:
        with open(log_path) as f:
            content = f.read()
    except Exception:
        return []

    errors = []
    seen_labels = set()
    for pattern, label, fix in _ERROR_PATTERNS:
        match = re.search(pattern, content)
        if match and label not in seen_labels:
            # Grab the line containing the match
            line_start = content.rfind("\n", 0, match.start()) + 1
            line_end = content.find("\n", match.end())
            line = content[line_start:line_end if line_end > 0 else len(content)].strip()
            errors.append({
                "label": label,
                "fix": fix,
                "line": line[:200],
            })
            seen_labels.add(label)

    return errors


# ------------------------------------------------------------------
# Movie diagnosis
# ------------------------------------------------------------------

def diagnose_movie(movie_data):
    """Plain-English diagnosis for any movie in the pipeline.

    Args:
        movie_data: dict from extraction.get_all_scripts() for one movie.

    Returns:
        dict with 'summary', 'severity' ('red'|'orange'|'green'), 'details', 'fixes'.
    """
    name = movie_data["name"]
    total = movie_data["total_clips"]
    extracted = movie_data["extracted_count"]
    verified = movie_data["verified"]
    failed = movie_data["failed"]
    needs_review = movie_data["needs_review"]
    is_running = movie_data["is_running"]
    ext_log = movie_data.get("ext_log", {})
    approved = movie_data.get("approved", 0)
    rejected = movie_data.get("rejected", 0)

    details = []
    fixes = []

    if total == 0:
        return {
            "summary": "No clips defined",
            "severity": "orange",
            "details": ["This movie has no clips in its extraction script."],
            "fixes": ["Add clips via Quick Add > Add Clips."],
        }

    # Fully reviewed: all clips have been approved or rejected by the user
    fully_reviewed = (approved + rejected >= total) and total > 0
    if fully_reviewed and not is_running:
        return {
            "summary": f"Review complete — {approved} approved, {rejected} rejected",
            "severity": "green",
            "details": [],
            "fixes": [],
        }

    # Count specific failure types from extraction log
    whisper_failed = 0
    no_match = 0
    for entry in ext_log.values():
        status = entry.get("final_status", "")
        if status == "failed":
            attempts = entry.get("attempts", [])
            if any(a.get("result") == "whisper_failed" for a in attempts):
                whisper_failed += 1
            elif any(a.get("result") == "no_match" for a in attempts):
                no_match += 1

    # Priority 1: All clips whisper_failed → Whisper unavailable
    if failed > 0 and whisper_failed == failed and failed == total:
        return {
            "summary": f"All {total} clips failed — Whisper unavailable",
            "severity": "red",
            "details": [
                "Every clip failed because Whisper could not run.",
                "Whisper is needed to transcribe audio and find quotes.",
            ],
            "fixes": [
                "Run extraction on Mini where Whisper is installed.",
                "Or install: brew install openai-whisper",
            ],
        }

    # Priority 2: All no_match + transcript corrupted
    if failed > 0 and no_match > 0:
        transcript = check_transcript(name)
        if not transcript["ok"] and transcript["exists"]:
            return {
                "summary": f"Transcript corrupted ({transcript['word_count']} words for {transcript['duration_min']:.0f}-min movie)",
                "severity": "red",
                "details": [
                    f"The transcript has only {transcript['word_count']} words — should have thousands.",
                    f"{no_match} clips couldn't match because the transcript is nearly empty.",
                ],
                "fixes": ["Delete the corrupt transcript and re-run extraction."],
            }

    # Priority 3: All no_match + transcript OK
    if failed > 0 and no_match == failed and no_match == total:
        return {
            "summary": f"All {total} clips failed to match — quotes may be inaccurate",
            "severity": "red",
            "details": [
                "The transcript looks OK but no quotes matched.",
                "The expected quotes might not appear in this movie.",
            ],
            "fixes": ["Review the quotes in the extraction script — they may need editing."],
        }

    # Priority 4: Running but no activity > 30 min
    if is_running:
        last_activity = _get_last_activity_time(name)
        if last_activity and (time.time() - last_activity) > 1800:
            mins_ago = int((time.time() - last_activity) / 60)
            return {
                "summary": f"May be stuck — no activity for {mins_ago} minutes",
                "severity": "orange",
                "details": [
                    f"Extraction is running but nothing has changed in {mins_ago} minutes.",
                ],
                "fixes": ["Stop and restart the extraction."],
            }

        # Running normally
        processed = sum(1 for e in ext_log.values() if e.get("final_status"))
        if last_activity:
            mins_ago = max(1, int((time.time() - last_activity) / 60))
            activity_str = f" — last activity {mins_ago} min ago"
        else:
            activity_str = ""
        return {
            "summary": f"Extracting clip {processed + 1}/{total}{activity_str}",
            "severity": "green",
            "details": [f"{verified} verified, {failed} failed so far."],
            "fixes": [],
        }

    # Priority 5: Not running, incomplete
    if extracted < total and not is_running and extracted > 0:
        return {
            "summary": f"Stopped — {extracted}/{total} extracted, click Start to resume",
            "severity": "orange",
            "details": [
                f"{verified} verified, {needs_review} need review, {failed} failed.",
            ],
            "fixes": ["Click Start to resume extraction."],
        }

    # Not started at all
    if extracted == 0 and not is_running:
        return {
            "summary": f"Not started — {total} clips waiting",
            "severity": "orange",
            "details": ["Extraction has not been started yet."],
            "fixes": ["Click Start to begin extraction."],
        }

    # Priority 6: Mixed results
    if failed > 0 or needs_review > 0:
        parts = []
        if failed:
            parts.append(f"{failed} failed")
        if verified:
            parts.append(f"{verified} verified")
        if needs_review:
            parts.append(f"{needs_review} need review")
        summary = ", ".join(parts)

        # Collect specific issues
        if failed > 0:
            log_errors = parse_log_errors(name)
            for err in log_errors:
                details.append(f"{err['label']}: {err['line']}")
                fixes.append(err["fix"])

        if not details:
            details.append(f"{extracted}/{total} clips extracted.")

        return {
            "summary": summary,
            "severity": "orange" if failed <= total // 2 else "red",
            "details": details,
            "fixes": fixes,
        }

    # Priority 7: Complete
    if verified >= total and total > 0:
        return {
            "summary": f"Complete — {verified}/{total} verified",
            "severity": "green",
            "details": [],
            "fixes": [],
        }

    # Fallback: partially done, no failures
    return {
        "summary": f"{extracted}/{total} extracted, {verified} verified",
        "severity": "green",
        "details": [],
        "fixes": [],
    }


def _get_last_activity_time(name):
    """Get mtime of extraction_log.json as a proxy for last activity."""
    log_path = os.path.join(EXTRACTION_DIR, name, "extraction_log.json")
    try:
        return os.path.getmtime(log_path)
    except OSError:
        return None
