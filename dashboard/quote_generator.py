"""Generate movie quotes for extraction scripts using Anthropic API.

Uses the anthropic Python SDK to identify iconic/memorable quotes
from a movie, formatted for the extraction pipeline.
"""
import json
import logging
import os
import re
from datetime import datetime

log = logging.getLogger(__name__)

QUOTE_GEN_LOG = os.path.expanduser("~/.openpeon/quote_gen_log.json")
MAX_LOG_ENTRIES = 200


def _log_quote_attempt(title, year, success, clip_count=0, error=""):
    """Log a quote generation attempt to persistent log file."""
    os.makedirs(os.path.dirname(QUOTE_GEN_LOG), exist_ok=True)

    entries = []
    if os.path.exists(QUOTE_GEN_LOG):
        try:
            with open(QUOTE_GEN_LOG) as f:
                entries = json.load(f)
        except Exception:
            entries = []

    entries.append({
        "title": title,
        "year": year,
        "success": success,
        "clip_count": clip_count,
        "error": error[:200] if error else "",
        "timestamp": datetime.now().isoformat(),
    })

    # Cap at MAX_LOG_ENTRIES
    if len(entries) > MAX_LOG_ENTRIES:
        entries = entries[-MAX_LOG_ENTRIES:]

    try:
        with open(QUOTE_GEN_LOG, "w") as f:
            json.dump(entries, f, indent=2)
    except Exception as e:
        log.warning("Failed to write quote gen log: %s", e)

_PROMPT_TEMPLATE = """You are helping build a sound notification pack for a coding tool. Given a movie title, identify the most iconic, memorable, and funny quotes that would work well as short audio notification sounds (1-8 seconds each).

Movie: {title} ({year})

For each quote, provide:
1. A slug filename (lowercase, underscores, no special chars)
2. An approximate timestamp in seconds from the start of the film (your best estimate)
3. The exact quote text
4. Estimated duration in seconds (1-8)

Aim for 15-25 quotes covering a range of characters and memorable moments. Focus on:
- Iconic one-liners
- Funny moments
- Dramatic moments
- Short exclamations that work as notification sounds
- Character catchphrases

Return ONLY a JSON array with no other text. Each element should be:
{{"slug": "quote_slug", "timestamp": 1234, "quote": "The actual quote text", "duration": 3, "character": "Character Name"}}

Example for a hypothetical movie:
[
  {{"slug": "ill_be_back", "timestamp": 2400, "quote": "I'll be back.", "duration": 2, "character": "The Terminator"}},
  {{"slug": "hasta_la_vista", "timestamp": 5100, "quote": "Hasta la vista, baby.", "duration": 2, "character": "The Terminator"}}
]

Return ONLY the JSON array, no markdown fences, no explanation."""


def _get_api_key():
    """Load Anthropic API key from environment or .env file."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    env_path = os.path.expanduser("~/.openpeon/.env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY="):
                    return line.split("=", 1)[1].strip()
    return ""


def generate_quotes(title, year=""):
    """Call Anthropic API to generate movie quotes for extraction.

    Args:
        title: Movie title (e.g. "My Movie")
        year: Optional year (e.g. "1984")

    Returns:
        list of (slug, timestamp, quote, duration) tuples, or
        dict with 'error' key on failure.
    """
    api_key = _get_api_key()
    if not api_key:
        err = "ANTHROPIC_API_KEY not set — add it to ~/.openpeon/.env"
        _log_quote_attempt(title, year, success=False, error=err)
        return {"error": err}

    prompt = _PROMPT_TEMPLATE.format(title=title, year=year or "")

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = re.sub(r'^```\w*\n?', '', raw)
            raw = re.sub(r'\n?```$', '', raw)
            raw = raw.strip()

        quotes = json.loads(raw)
        if not isinstance(quotes, list):
            err = "Expected JSON array from Claude"
            _log_quote_attempt(title, year, success=False, error=err)
            return {"error": err}

        # Convert to extraction pipeline format: (slug, timestamp, quote, duration)
        clips = []
        for q in quotes:
            slug = q.get("slug", "")
            ts = int(q.get("timestamp", 0))
            text = q.get("quote", "")
            dur = int(q.get("duration", 3))
            if slug and text:
                clips.append((slug, ts, text, max(1, min(dur, 8))))

        log.info("Generated %d quotes for %s", len(clips), title)
        _log_quote_attempt(title, year, success=True, clip_count=len(clips))
        return clips

    except json.JSONDecodeError as e:
        err = f"Failed to parse Claude response as JSON: {e}"
        _log_quote_attempt(title, year, success=False, error=err)
        return {"error": err}
    except Exception as e:
        _log_quote_attempt(title, year, success=False, error=str(e))
        return {"error": str(e)}


def populate_extraction_script(name, title, mkv_path, year="", audio_stream="0:1"):
    """Generate quotes and create a fully populated extraction script.

    Combines generate_quotes() + extraction.create_movie_script() for a
    one-shot "add movie with quotes" flow.

    Returns:
        dict with 'ok', 'script_path', 'clip_count', etc.
    """
    import extraction

    # Generate quotes via LLM
    quotes = generate_quotes(title, year)
    if isinstance(quotes, dict) and "error" in quotes:
        return quotes

    if not quotes:
        return {"error": "No quotes generated"}

    # Create the extraction script with the generated clips
    result = extraction.create_movie_script(
        name=name,
        title=f"{title} ({year})" if year else title,
        mkv_path=mkv_path,
        audio_stream=audio_stream,
        clips=quotes,
    )

    if result.get("ok"):
        result["clip_count"] = len(quotes)
        result["quotes"] = quotes
    return result
