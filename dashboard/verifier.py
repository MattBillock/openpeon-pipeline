"""Clip verification module — re-runs STT on extracted clips to verify quality."""
import json
import logging
import os
import re
import subprocess
import tempfile
from difflib import SequenceMatcher

log = logging.getLogger(__name__)


WHISPER_PYTHON = "/opt/homebrew/Cellar/openai-whisper/20250625_3/libexec/bin/python3"
EXTRACTION_DIR = os.path.expanduser("~/Development/AIOutput/openpeon/extraction")


def _normalize(text):
    """Normalize text for comparison."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return " ".join(text.split())


def transcribe_mp3(mp3_path):
    """Run Whisper on an MP3 file and return the transcription text."""
    script = f"""
import whisper
import json
model = whisper.load_model("small")
result = model.transcribe("{mp3_path}", language="en")
print(json.dumps({{"text": result.get("text", "").strip()}}))
"""
    try:
        result = subprocess.run(
            [WHISPER_PYTHON, "-c", script],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            return {"error": result.stderr[-300:]}
        data = json.loads(result.stdout.strip())
        return {"text": data.get("text", "")}
    except subprocess.TimeoutExpired:
        return {"error": "Whisper timeout"}
    except Exception as e:
        return {"error": str(e)}


def verify_clip(mp3_path, expected_quote):
    """Verify a single clip by transcribing and comparing to expected quote."""
    result = transcribe_mp3(mp3_path)
    if "error" in result:
        return {
            "status": "error",
            "error": result["error"],
            "expected": expected_quote,
            "heard": "",
            "score": 0.0,
        }

    heard = result["text"]
    norm_expected = _normalize(expected_quote)
    norm_heard = _normalize(heard)

    score = SequenceMatcher(None, norm_expected, norm_heard).ratio()

    if score >= 0.7:
        status = "pass"
    elif score >= 0.4:
        status = "review"
    else:
        status = "fail"

    return {
        "status": status,
        "expected": expected_quote,
        "heard": heard,
        "score": round(score, 3),
    }


def get_clips_from_script(movie_name):
    """Parse the CLIPS array from an extraction script to get expected quotes."""
    script_path = os.path.join(EXTRACTION_DIR, f"extract_{movie_name}.py")
    if not os.path.exists(script_path):
        return {}

    clips = {}
    try:
        with open(script_path) as f:
            content = f.read()
        # Parse tuples: ("filename", timestamp, "quote", duration)
        pattern = r'\("([^"]+)",\s*(\d+),\s*"([^"]+)",\s*(\d+)\)'
        for match in re.finditer(pattern, content):
            filename = match.group(1)
            timestamp = int(match.group(2))
            quote = match.group(3)
            duration = int(match.group(4))
            clips[filename] = {
                "timestamp": timestamp,
                "quote": quote,
                "duration": duration,
            }
    except Exception as e:
        log.warning("Failed to parse clips from %s: %s", script_path, e)
    return clips


def get_verification_state(movie_name):
    """Load existing verification results for a movie."""
    verify_path = os.path.join(EXTRACTION_DIR, movie_name, "verify.json")
    if os.path.exists(verify_path):
        try:
            with open(verify_path) as f:
                return json.load(f)
        except Exception as e:
            log.error("Corrupted verify.json for %s: %s", movie_name, e)
    return {}


def save_verification(movie_name, clip_name, result):
    """Save verification result for a clip."""
    output_dir = os.path.join(EXTRACTION_DIR, movie_name)
    verify_path = os.path.join(output_dir, "verify.json")

    state = get_verification_state(movie_name)
    state[clip_name] = result

    os.makedirs(output_dir, exist_ok=True)
    with open(verify_path, "w") as f:
        json.dump(state, f, indent=2)
    return state


def verify_movie(movie_name, force=False):
    """Verify all extracted clips for a movie. Returns summary."""
    script_clips = get_clips_from_script(movie_name)
    output_dir = os.path.join(EXTRACTION_DIR, movie_name)
    existing = get_verification_state(movie_name)

    results = {"pass": 0, "review": 0, "fail": 0, "error": 0, "pending": 0}
    details = []

    for clip_name, clip_info in script_clips.items():
        mp3_path = os.path.join(output_dir, f"{clip_name}.mp3")
        has_mp3 = os.path.exists(mp3_path)

        if clip_name in existing and not force:
            v = existing[clip_name]
            results[v.get("status", "error")] += 1
            details.append({
                "name": clip_name,
                "has_mp3": has_mp3,
                "verified": True,
                **v,
            })
        elif has_mp3:
            results["pending"] += 1
            details.append({
                "name": clip_name,
                "has_mp3": True,
                "verified": False,
                "status": "pending",
                "expected": clip_info["quote"],
                "heard": "",
                "score": 0.0,
            })
        else:
            results["pending"] += 1
            details.append({
                "name": clip_name,
                "has_mp3": False,
                "verified": False,
                "status": "not_extracted",
                "expected": clip_info["quote"],
                "heard": "",
                "score": 0.0,
            })

    return {"summary": results, "clips": details}


def run_verification_batch(movie_name, max_clips=5):
    """Verify up to max_clips unverified clips. Returns list of results."""
    script_clips = get_clips_from_script(movie_name)
    output_dir = os.path.join(EXTRACTION_DIR, movie_name)
    existing = get_verification_state(movie_name)

    verified = []
    count = 0

    for clip_name, clip_info in script_clips.items():
        if count >= max_clips:
            break

        if clip_name in existing:
            continue

        mp3_path = os.path.join(output_dir, f"{clip_name}.mp3")
        if not os.path.exists(mp3_path):
            continue

        result = verify_clip(mp3_path, clip_info["quote"])
        save_verification(movie_name, clip_name, result)
        verified.append({"name": clip_name, **result})
        count += 1

    return verified


def get_all_movies_with_clips():
    """Get all movies that have extraction scripts and/or extracted clips."""
    movies = []
    for entry in sorted(os.listdir(EXTRACTION_DIR)):
        script = os.path.join(EXTRACTION_DIR, f"extract_{entry}.py")
        output_dir = os.path.join(EXTRACTION_DIR, entry)
        if os.path.isdir(output_dir):
            mp3s = [f for f in os.listdir(output_dir) if f.endswith(".mp3")]
            if mp3s or os.path.exists(script):
                script_clips = get_clips_from_script(entry)
                verify_state = get_verification_state(entry)
                movies.append({
                    "name": entry,
                    "extracted": len(mp3s),
                    "total": len(script_clips),
                    "verified": len(verify_state),
                    "passed": sum(1 for v in verify_state.values() if v.get("status") == "pass"),
                    "failed": sum(1 for v in verify_state.values() if v.get("status") == "fail"),
                    "needs_review": sum(1 for v in verify_state.values() if v.get("status") == "review"),
                })
    return movies
