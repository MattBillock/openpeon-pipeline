#!/usr/bin/env python3
"""
Shared extraction engine for OpenPeon movie clip extraction.

Fixes from v1 pipeline:
  1. min_score raised from 0.4 to 0.70 (matching threshold)
  2. NO cache bypass — existing clips are re-verified, not auto-accepted
  3. Mandatory post-extraction STT verification on the FINAL mp3
  4. All results logged to extraction_log.json with scores + transcriptions

v2 changes:
  - Whisper model loaded ONCE in-process (not spawned per transcription)
  - Extraction scripts must run under WHISPER_PYTHON for import to work
  - Massive speedup: ~10s/transcription vs ~30s+ with subprocess model reload

v3 changes:
  - Full-movie transcription mode (default): transcribe entire movie once,
    then search the full transcript for all quotes. Eliminates timestamp
    guessing and dramatically improves hit rate.
  - Falls back to windowed search only if full transcription fails.
  - Cached transcripts in {movie}/full_transcript.json for reuse.

Usage from extraction scripts:
    from extractor import run_extraction
    run_extraction(
        movie_name="mymovie",
        mkv_path="/path/to/movie.mkv",
        audio_stream="0:1",
        clips=[("filename", timestamp, "expected quote", duration), ...],
        targets=sys.argv[1:],  # optional CLI filter
    )
"""

import json
import os
import subprocess
import sys
import tempfile
import time
import warnings
from datetime import datetime
from difflib import SequenceMatcher

# Suppress FP16 warning on CPU
warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROJECT_PYTHON = os.path.join(PROJECT_ROOT, ".venv", "bin", "python3")
BASE_DIR = os.path.join(PROJECT_ROOT, "extraction")

# Ensure homebrew binaries are findable
FFMPEG = "/opt/homebrew/bin/ffmpeg"
FFPROBE = "/opt/homebrew/bin/ffprobe"
if not os.path.exists(FFMPEG):
    FFMPEG = "ffmpeg"  # fall back to PATH
if not os.path.exists(FFPROBE):
    FFPROBE = "ffprobe"

# Lazy-loaded Whisper model (loaded once, reused for all transcriptions)
_whisper_model = None

# Thresholds
MIN_MATCH_SCORE = 0.70      # Pre-extraction: minimum fuzzy match to attempt clip extraction
MIN_VERIFY_SCORE = 0.60     # Post-extraction: minimum score on re-STT of final mp3
REVIEW_SCORE = 0.50         # Post-extraction: below this = fail, above but below MIN_VERIFY = review

# Full-movie transcription: chunk size in seconds (30 min chunks to manage memory)
CHUNK_DURATION = 1800


def _normalize_text(text):
    """Normalize text for comparison — lowercase, strip punctuation."""
    import re
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    return " ".join(text.split())


def filter_low_confidence_words(words):
    """Filter out words that are likely hallucinated or non-speech audio.

    Whisper hallucinates words over music/silence — these have low probability
    and high no_speech_prob. Old transcripts lacking these fields pass through
    unchanged via safe defaults.

    Returns filtered list of word dicts.
    """
    filtered = []
    for w in words:
        prob = w.get("probability", 1.0)
        nsp = w.get("no_speech_prob", 0.0)
        if prob < 0.25:
            continue  # likely hallucinated
        if nsp > 0.60:
            continue  # likely music/silence
        filtered.append(w)
    return filtered


def extract_window(mkv_path, audio_stream, timestamp_s, window_s=60):
    """Extract a window of audio from the MKV file to a temp WAV."""
    start = max(0, timestamp_s - window_s // 2)
    tmp = tempfile.mktemp(suffix=".wav")
    cmd = [
        FFMPEG, "-y",
        "-ss", str(start),
        "-i", mkv_path,
        "-t", str(window_s),
        "-map", audio_stream,
        "-ac", "1",
        "-ar", "16000",
        "-acodec", "pcm_s16le",
        tmp
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=600)
    if result.returncode != 0:
        return None, start
    return tmp, start


def _get_whisper_model():
    """Load Whisper model once and cache it."""
    global _whisper_model
    if _whisper_model is None:
        try:
            import whisper
            print("  Loading Whisper model (one-time)...")
            _whisper_model = whisper.load_model("small")
            print("  Whisper model loaded.")
        except ImportError:
            print("  ERROR: whisper not available. Run with project venv: .venv/bin/python3")
            return None
    return _whisper_model


def whisper_transcribe(audio_path, is_mp3=False):
    """Run Whisper on an audio file, return word-level timestamps.

    v2: Uses in-process model (loaded once) instead of spawning subprocess.
    """
    model = _get_whisper_model()
    if model is None:
        return None

    try:
        result = model.transcribe(audio_path, language="en", word_timestamps=True)
        words = []
        for seg in result.get("segments", []):
            seg_nsp = seg.get("no_speech_prob", 0.0)
            for word in seg.get("words", []):
                words.append({
                    "word": word["word"].strip(),
                    "start": word["start"],
                    "end": word["end"],
                    "probability": round(word.get("probability", 1.0), 4),
                    "no_speech_prob": round(seg_nsp, 4),
                })
        full_text = result.get("text", "").strip()
        return {"words": words, "text": full_text}
    except Exception as e:
        print(f"    Whisper error: {e}")
        return None


def get_movie_duration(mkv_path):
    """Get movie duration in seconds using ffprobe."""
    cmd = [
        FFPROBE, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        mkv_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"  ffprobe error: {e}")
        return None


def transcribe_full_movie(mkv_path, audio_stream, output_dir):
    """Transcribe the entire movie audio and cache the result.

    Strategy: Extract the FULL audio track to a single WAV file first (one
    ffmpeg pass over the MKV), then transcribe in chunks from the local WAV.
    This avoids repeated slow seeks into large MKV files over network storage.

    Returns: list of word dicts [{word, start, end}, ...] or None on failure.
    """
    cache_path = os.path.join(output_dir, "full_transcript.json")

    # Check for cached transcript
    if os.path.exists(cache_path):
        print(f"  Loading cached full transcript from {cache_path}...")
        try:
            with open(cache_path) as f:
                data = json.load(f)
            words = data.get("words", [])
            if words:
                print(f"  Loaded {len(words)} words from cache.")
                return words
        except Exception as e:
            print(f"  Cache load failed ({e}), re-transcribing...")

    model = _get_whisper_model()
    if model is None:
        return None

    # Get movie duration
    duration = get_movie_duration(mkv_path)
    if duration is None:
        print("  ERROR: Could not determine movie duration.")
        return None

    print(f"  Movie duration: {duration:.0f}s ({duration/60:.0f}min)")

    # Phase 1: Extract full audio track to a compressed OGG file
    # OGG is ~10x smaller than WAV (20-50MB vs 200-500MB), and Whisper accepts it natively.
    # This avoids starving macOS audio with massive temp files.
    full_audio = os.path.join(output_dir, "full_audio.ogg")
    full_wav_legacy = os.path.join(output_dir, "full_audio.wav")

    # Backward compat: use existing WAV if present (from previous runs)
    if os.path.exists(full_wav_legacy):
        print(f"  Using existing full audio WAV: {full_wav_legacy}")
        full_audio = full_wav_legacy
    elif os.path.exists(full_audio):
        print(f"  Using existing full audio OGG: {full_audio}")
    else:
        print(f"  Extracting full audio track to OGG (this may take a few minutes)...")
        cmd = [
            FFMPEG, "-y",
            "-i", mkv_path,
            "-map", audio_stream,
            "-ac", "1",
            "-ar", "16000",
            "-acodec", "libvorbis",
            "-q:a", "4",
            full_audio,
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=1800)  # 30min timeout
            if result.returncode != 0:
                stderr = result.stderr.decode("utf-8", errors="replace")[:500]
                print(f"  ERROR: ffmpeg audio extraction failed: {stderr}")
                return None
            audio_size = os.path.getsize(full_audio) / (1024 * 1024)
            print(f"  Full audio extracted: {audio_size:.0f}MB")
        except subprocess.TimeoutExpired:
            print(f"  ERROR: ffmpeg audio extraction timed out (30 min limit)")
            try:
                os.unlink(full_audio)
            except OSError:
                pass
            return None

    # Phase 2: Transcribe the WAV in chunks
    num_chunks = int(duration // CHUNK_DURATION) + 1
    print(f"  Transcribing in {num_chunks} chunks of {CHUNK_DURATION}s...")

    all_words = []
    full_text_parts = []

    for chunk_idx in range(num_chunks):
        chunk_start = chunk_idx * CHUNK_DURATION
        chunk_end = min(chunk_start + CHUNK_DURATION, duration)
        if chunk_start >= duration:
            break

        chunk_len = chunk_end - chunk_start
        print(f"  Chunk {chunk_idx + 1}/{num_chunks}: {chunk_start:.0f}s - {chunk_end:.0f}s "
              f"({chunk_start/60:.0f}min - {chunk_end/60:.0f}min)...")

        # Extract chunk from the local audio file (fast — no MKV seeking)
        tmp_chunk = tempfile.mktemp(suffix=".wav")
        cmd = [
            FFMPEG, "-y",
            "-ss", str(chunk_start),
            "-i", full_audio,
            "-t", str(chunk_len),
            "-acodec", "pcm_s16le",
            tmp_chunk,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode != 0:
            print(f"    -> ffmpeg chunk extraction failed")
            continue

        # Transcribe chunk
        try:
            result = model.transcribe(tmp_chunk, language="en", word_timestamps=True)
            chunk_words = 0
            for seg in result.get("segments", []):
                seg_nsp = seg.get("no_speech_prob", 0.0)
                for word in seg.get("words", []):
                    all_words.append({
                        "word": word["word"].strip(),
                        "start": round(word["start"] + chunk_start, 3),
                        "end": round(word["end"] + chunk_start, 3),
                        "probability": round(word.get("probability", 1.0), 4),
                        "no_speech_prob": round(seg_nsp, 4),
                    })
                    chunk_words += 1
            chunk_text = result.get("text", "").strip()
            if chunk_text:
                full_text_parts.append(chunk_text)
            print(f"    -> {len(result.get('segments', []))} segments, {chunk_words} words")
        except Exception as e:
            print(f"    -> Whisper error on chunk {chunk_idx + 1}: {e}")
        finally:
            try:
                os.unlink(tmp_chunk)
            except OSError:
                pass

    # Clean up full audio file (not needed after transcription)
    try:
        os.unlink(full_audio)
        print(f"  Cleaned up {os.path.basename(full_audio)}")
    except OSError:
        pass

    if not all_words:
        print("  ERROR: Full transcription produced no words.")
        return None

    # Cache the transcript
    print(f"  Full transcription complete: {len(all_words)} words total.")
    cache_data = {
        "movie": os.path.basename(mkv_path),
        "duration": duration,
        "transcribed_at": datetime.now().isoformat(),
        "word_count": len(all_words),
        "full_text": " ".join(full_text_parts),
        "words": all_words,
    }
    with open(cache_path, "w") as f:
        json.dump(cache_data, f)
    print(f"  Cached transcript to {cache_path}")

    return all_words


def _extract_and_verify(mkv_path, audio_stream, output_path, start, end, quote, log_entry):
    """Extract a clip at the given timestamps and run STT verification.

    Shared by both transcript-search and manual-override paths.
    Returns: "verified", "review", "rejected", or "failed"
    """
    actual_start = max(0, start - 0.3)
    duration = (end - start) + 0.6
    duration = max(1.0, min(duration, 10.0))

    cmd = [
        FFMPEG, "-y",
        "-ss", str(actual_start),
        "-i", mkv_path,
        "-t", str(duration),
        "-map", audio_stream,
        "-vn",
        "-acodec", "libmp3lame",
        "-q:a", "2",
        "-ac", "1",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    if result.returncode != 0:
        print(f"    -> ffmpeg clip extraction failed")
        return "failed"

    # POST-EXTRACTION VERIFICATION
    print(f"  POST-VERIFY: Re-running STT on extracted clip...")
    verify = verify_extracted_clip(output_path, quote)
    verify_score = verify["score"]
    verify_status = verify["status"]
    verify_heard = verify["heard"]

    log_entry["pre_match_score"] = log_entry.get("pre_match_score", 0)
    log_entry["found_at"] = round(start, 1)
    log_entry["verify_score"] = verify_score
    log_entry["verify_heard"] = verify_heard
    log_entry["verify_status"] = verify_status

    if verify_status == "rejected":
        print(f"  POST-VERIFY FAILED: score={verify_score:.3f}")
        print(f"    Expected: \"{quote}\"")
        print(f"    Heard:    \"{verify_heard}\"")
        try:
            os.unlink(output_path)
        except OSError:
            pass
        return "rejected"

    if verify_status == "review":
        print(f"  POST-VERIFY MARGINAL: score={verify_score:.3f}")
        print(f"    Expected: \"{quote}\"")
        print(f"    Heard:    \"{verify_heard}\"")
        return "review"

    print(f"  POST-VERIFY PASSED: score={verify_score:.3f}")
    print(f"    Expected: \"{quote}\"")
    print(f"    Heard:    \"{verify_heard}\"")
    return "verified"


def process_clip_from_transcript(mkv_path, audio_stream, output_dir, filename,
                                  quote, expected_duration, log_entry, full_words,
                                  override_timestamp=None):
    """Process a single clip using the full-movie transcript.

    Searches the full transcript for the best match, extracts the clip,
    and verifies it.

    Args:
        override_timestamp: If set, skip transcript search and extract directly
            at this timestamp (seconds). Used for manual corrections.

    Returns: "verified", "review", "rejected", or "failed"
    """
    print(f"\n{'='*60}")
    print(f"  CLIP: {filename}")
    print(f"  QUOTE: \"{quote}\"")
    if override_timestamp is not None:
        print(f"  OVERRIDE: extracting at {override_timestamp}s")
    print(f"{'='*60}")

    output_path = os.path.join(output_dir, filename + ".mp3")

    # Manual timestamp override — skip transcript search entirely
    if override_timestamp is not None:
        start = float(override_timestamp)
        end = start + max(1.0, min(expected_duration, 10.0))
        log_entry["attempts"].append({
            "method": "manual_override",
            "timestamp": round(start, 1),
        })
        log_entry["pre_match_score"] = 0
        log_entry["pre_match_text"] = "(manual override)"
        return _extract_and_verify(mkv_path, audio_stream, output_path,
                                   start, end, quote, log_entry)

    # Filter out hallucinated/music words before searching
    filtered_words = filter_low_confidence_words(full_words)

    # Read exclude_positions from log_entry (accumulated from previous retries)
    exclude_positions = log_entry.get("exclude_positions", [])

    # Search full transcript (with exclusions if retrying)
    match = find_quote(filtered_words, quote, exclude_positions=exclude_positions)
    if match is None and exclude_positions:
        # Fall back to searching without exclusions
        print(f"    -> No match with {len(exclude_positions)} exclusion(s), trying without...")
        match = find_quote(filtered_words, quote)
        if match:
            print(f"    -> WARNING: Only found match in excluded region")

    if match is None:
        # Try with a lower threshold to at least get candidates
        match_loose = find_quote(filtered_words, quote, min_score=REVIEW_SCORE)
        if match_loose:
            start, end, score, matched_text = match_loose
            print(f"    -> Loose match: score={score:.3f} at {start:.1f}s")
            print(f"    -> Matched: \"{matched_text}\"")
            log_entry["attempts"].append({
                "method": "full_transcript",
                "result": "loose_match",
                "score": round(score, 3),
                "matched_text": matched_text,
                "timestamp": round(start, 1),
            })
        else:
            print(f"    -> No match found in full transcript")
            log_entry["attempts"].append({
                "method": "full_transcript",
                "result": "no_match",
            })
        print(f"  FAILED: Could not find quote in full movie transcript")
        return "failed"

    start, end, score, matched_text = match
    print(f"    -> MATCH: score={score:.3f} at {start:.1f}s ({start/60:.0f}:{start%60:02.0f})")
    print(f"    -> Matched: \"{matched_text}\"")

    log_entry["attempts"].append({
        "method": "full_transcript",
        "result": "matched",
        "score": round(score, 3),
        "matched_text": matched_text,
        "timestamp": round(start, 1),
    })
    log_entry["pre_match_score"] = round(score, 3)
    log_entry["pre_match_text"] = matched_text

    return _extract_and_verify(mkv_path, audio_stream, output_path,
                               start, end, quote, log_entry)


def find_quote(words, expected_quote, min_score=MIN_MATCH_SCORE, exclude_positions=None):
    """Find the best match for the expected quote in the transcription.

    Args:
        words: list of word dicts with start/end times
        expected_quote: the quote text to search for
        min_score: minimum fuzzy match score
        exclude_positions: list of timestamps (seconds) to skip. A 2-second
            buffer around each position is excluded, preventing retry loops
            from finding the same wrong match.

    Returns (start_time, end_time, score, matched_text) or None.
    """
    expected_words = _normalize_text(expected_quote).split()
    n = len(expected_words)
    if n == 0 or not words:
        return None

    word_texts = [_normalize_text(w["word"]) for w in words]
    expected_joined = " ".join(expected_words)

    # Build exclusion check
    _exclude = exclude_positions or []
    EXCLUDE_BUFFER = 2.0

    def _is_excluded(start_time):
        for pos in _exclude:
            if abs(start_time - pos) < EXCLUDE_BUFFER:
                return True
        return False

    best_score = 0
    best_match = None
    best_text = ""

    for window in range(max(1, n - 2), n + 4):
        for i in range(len(word_texts) - window + 1):
            # Skip regions near excluded positions
            if _exclude and _is_excluded(words[i]["start"]):
                continue
            candidate = " ".join(word_texts[i:i + window])
            score = SequenceMatcher(None, expected_joined, candidate).ratio()
            if score > best_score:
                best_score = score
                best_match = (
                    words[i]["start"],
                    words[min(i + window - 1, len(words) - 1)]["end"]
                )
                best_text = " ".join(w["word"] for w in words[i:i + window])

    if best_score >= min_score and best_match:
        return best_match[0], best_match[1], best_score, best_text
    return None


def extract_clip(mkv_path, audio_stream, start_s, end_s, output_path, window_offset):
    """Extract final MP3 clip from the MKV."""
    actual_start = window_offset + start_s - 0.3
    duration = (end_s - start_s) + 0.6
    duration = max(1.0, min(duration, 10.0))

    cmd = [
        FFMPEG, "-y",
        "-ss", str(actual_start),
        "-i", mkv_path,
        "-t", str(duration),
        "-map", audio_stream,
        "-vn",
        "-acodec", "libmp3lame",
        "-q:a", "2",
        "-ac", "1",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    return result.returncode == 0


def verify_extracted_clip(mp3_path, expected_quote):
    """Post-extraction verification: run STT on the final MP3 and compare.

    Returns dict with status, heard_text, score.
    """
    data = whisper_transcribe(mp3_path, is_mp3=True)
    if data is None:
        return {"status": "error", "heard": "", "score": 0.0, "error": "whisper_failed"}

    heard = data.get("text", "")
    norm_expected = _normalize_text(expected_quote)
    norm_heard = _normalize_text(heard)

    score = SequenceMatcher(None, norm_expected, norm_heard).ratio()

    if score >= MIN_VERIFY_SCORE:
        status = "verified"
    elif score >= REVIEW_SCORE:
        status = "review"
    else:
        status = "rejected"

    return {
        "status": status,
        "heard": heard,
        "score": round(score, 3),
    }


def process_clip(mkv_path, audio_stream, output_dir, filename, timestamp,
                 quote, expected_duration, log_entry):
    """Process a single clip with full STT pipeline.

    1. Try multiple time windows around approximate timestamp
    2. Run Whisper on each window, fuzzy-match the expected quote
    3. Extract clip ONLY if match score >= 0.70
    4. Run post-extraction STT verification on the final MP3
    5. REJECT if post-verification score < threshold

    Returns: "verified", "review", "rejected", or "failed"
    """
    print(f"\n{'='*60}")
    print(f"  CLIP: {filename}")
    print(f"  QUOTE: \"{quote}\"")
    print(f"  APPROX: {timestamp}s ({timestamp//60}:{timestamp%60:02d})")
    print(f"{'='*60}")

    output_path = os.path.join(output_dir, filename + ".mp3")
    offsets = [0, -30, 30, -60, 60, -90, 90, -120, 120, -150, 150, -180, 180]

    for offset in offsets:
        center = timestamp + offset
        print(f"  Window: center={center}s (offset={offset:+d})...")

        wav, window_start = extract_window(mkv_path, audio_stream, center, window_s=90)
        if wav is None:
            print(f"    -> ffmpeg window extraction failed")
            continue

        data = whisper_transcribe(wav)
        try:
            os.unlink(wav)
        except OSError:
            pass

        if data is None:
            print(f"    -> Whisper transcription failed")
            log_entry["attempts"].append({
                "offset": offset, "center": center,
                "result": "whisper_failed"
            })
            continue

        raw_words = data.get("words", [])
        words = filter_low_confidence_words(raw_words)
        full_text = data.get("text", "")
        if not words:
            print(f"    -> No words detected")
            log_entry["attempts"].append({
                "offset": offset, "center": center,
                "result": "no_words", "heard": full_text
            })
            continue

        match = find_quote(words, quote)
        if match is None:
            # Show what we actually heard for debugging
            snippet = full_text[:100]
            print(f"    -> No match (score < {MIN_MATCH_SCORE})")
            print(f"    -> Heard: \"{snippet}...\"")
            log_entry["attempts"].append({
                "offset": offset, "center": center,
                "result": "no_match", "heard": snippet
            })
            continue

        start, end, score, matched_text = match
        print(f"    -> MATCH: score={score:.3f}")
        print(f"    -> Matched: \"{matched_text}\"")

        log_entry["attempts"].append({
            "offset": offset, "center": center,
            "result": "matched", "score": round(score, 3),
            "matched_text": matched_text
        })

        # Extract the clip
        if not extract_clip(mkv_path, audio_stream, start, end, output_path, window_start):
            print(f"    -> ffmpeg clip extraction failed")
            continue

        # POST-EXTRACTION VERIFICATION: Run STT on the final MP3
        print(f"  POST-VERIFY: Re-running STT on extracted clip...")
        verify = verify_extracted_clip(output_path, quote)
        verify_score = verify["score"]
        verify_status = verify["status"]
        verify_heard = verify["heard"]

        log_entry["pre_match_score"] = round(score, 3)
        log_entry["pre_match_text"] = matched_text
        log_entry["verify_score"] = verify_score
        log_entry["verify_heard"] = verify_heard
        log_entry["verify_status"] = verify_status

        if verify_status == "rejected":
            print(f"  POST-VERIFY FAILED: score={verify_score:.3f}")
            print(f"    Expected: \"{quote}\"")
            print(f"    Heard:    \"{verify_heard}\"")
            print(f"    -> REJECTING clip, trying next window")
            # Delete the bad clip
            try:
                os.unlink(output_path)
            except OSError:
                pass
            continue

        if verify_status == "review":
            print(f"  POST-VERIFY MARGINAL: score={verify_score:.3f}")
            print(f"    Expected: \"{quote}\"")
            print(f"    Heard:    \"{verify_heard}\"")
            print(f"    -> Keeping for human review")
            return "review"

        # Verified!
        print(f"  POST-VERIFY PASSED: score={verify_score:.3f}")
        print(f"    Expected: \"{quote}\"")
        print(f"    Heard:    \"{verify_heard}\"")
        return "verified"

    print(f"  FAILED: Could not find quote in any window")
    return "failed"


def run_extraction(movie_name, mkv_path, audio_stream, clips, targets=None,
                   force=False, windowed=False):
    """Main extraction entry point.

    Args:
        movie_name: e.g. "mymovie"
        mkv_path: path to MKV file
        audio_stream: e.g. "0:2"
        clips: list of (filename, timestamp, quote, duration) tuples
        targets: optional list of filenames to process (CLI filter)
        force: if True, re-process even verified clips
        windowed: if True, use old windowed search instead of full-movie mode
    """
    output_dir = os.path.join(BASE_DIR, movie_name)
    os.makedirs(output_dir, exist_ok=True)

    # Load existing extraction log
    log_path = os.path.join(output_dir, "extraction_log.json")
    if os.path.exists(log_path):
        with open(log_path) as f:
            extraction_log = json.load(f)
    else:
        extraction_log = {}

    if not os.path.exists(mkv_path):
        print(f"ERROR: {mkv_path} not found. Mount the D-drive first.")
        sys.exit(1)

    # Filter clips
    if targets:
        clips_to_process = [(f, t, q, d) for f, t, q, d in clips if f in targets]
    else:
        clips_to_process = clips

    results = {"verified": [], "review": [], "rejected": [], "failed": []}
    start_time = time.time()

    mode = "WINDOWED" if windowed else "FULL-MOVIE"
    print(f"\n{'#'*60}")
    print(f"  EXTRACTION: {movie_name} ({mode} mode)")
    print(f"  MKV: {mkv_path}")
    print(f"  STREAM: {audio_stream}")
    print(f"  CLIPS: {len(clips_to_process)} to process")
    print(f"  MIN_MATCH: {MIN_MATCH_SCORE}, MIN_VERIFY: {MIN_VERIFY_SCORE}")
    print(f"  TIME: {datetime.now().isoformat()}")
    print(f"{'#'*60}")

    # Load manual overrides if present
    overrides_path = os.path.join(output_dir, "overrides.json")
    overrides = {}
    if os.path.exists(overrides_path):
        try:
            with open(overrides_path) as f:
                overrides = json.load(f)
            if overrides:
                print(f"  Loaded {len(overrides)} manual override(s) from overrides.json")
        except Exception as e:
            print(f"  WARNING: Failed to load overrides.json: {e}")

    # Full-movie mode: transcribe entire movie first
    full_words = None
    if not windowed:
        print(f"\n  === PHASE 1: Full-movie transcription ===")
        full_words = transcribe_full_movie(mkv_path, audio_stream, output_dir)
        if full_words is None:
            print(f"  WARNING: Full-movie transcription failed, falling back to windowed mode.")
            windowed = True
        else:
            print(f"\n  === PHASE 2: Finding {len(clips_to_process)} quotes in transcript ===")

    for filename, timestamp, quote, duration in clips_to_process:
        # Check if already verified (unless force)
        existing = extraction_log.get(filename, {})
        if not force and existing.get("verify_status") == "verified":
            print(f"\n--- {filename} --- SKIP (already verified, score={existing.get('verify_score', '?')})")
            results["verified"].append(filename)
            continue

        # Create log entry — carry forward exclude_positions from previous attempts
        existing_excludes = existing.get("exclude_positions", [])
        log_entry = {
            "quote": quote,
            "timestamp": timestamp,
            "duration": duration,
            "attempts": [],
            "extracted_at": datetime.now().isoformat(),
        }
        if existing_excludes:
            log_entry["exclude_positions"] = existing_excludes

        # Check for manual timestamp override
        override_ts = overrides.get(filename)

        if full_words and not windowed:
            status = process_clip_from_transcript(
                mkv_path, audio_stream, output_dir,
                filename, quote, duration, log_entry, full_words,
                override_timestamp=override_ts,
            )
        else:
            status = process_clip(
                mkv_path, audio_stream, output_dir,
                filename, timestamp, quote, duration, log_entry
            )

        log_entry["final_status"] = status
        extraction_log[filename] = log_entry

        results[status].append(filename)

        # Save log after each clip (crash-safe)
        with open(log_path, "w") as f:
            json.dump(extraction_log, f, indent=2)

    elapsed = time.time() - start_time

    print(f"\n{'#'*60}")
    print(f"  EXTRACTION COMPLETE: {movie_name}")
    print(f"  Mode:     {mode}")
    print(f"  Verified: {len(results['verified'])}")
    print(f"  Review:   {len(results['review'])}")
    print(f"  Rejected: {len(results['rejected'])}")
    print(f"  Failed:   {len(results['failed'])}")
    print(f"  Time:     {elapsed:.0f}s ({elapsed/60:.1f}min)")
    print(f"{'#'*60}")

    if results["failed"]:
        print(f"\nFailed clips: {', '.join(results['failed'])}")
    if results["review"]:
        print(f"\nNeeds review: {', '.join(results['review'])}")

    return results
