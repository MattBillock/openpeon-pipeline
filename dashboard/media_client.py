"""Unified media client for Radarr (movies), Sonarr (TV), and Lidarr (music).

One-stop interface: search → pick → add to library + create extraction batch.
"""
import json
import logging
import os
import urllib.request
import urllib.parse
import urllib.error

log = logging.getLogger(__name__)


def _load_env():
    env_path = os.path.expanduser("~/.openpeon/.env")
    env = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


# Service configuration: defaults + env overrides
_env = _load_env()

SERVICES = {
    "movie": {
        "name": "Radarr",
        "url": _env.get("RADARR_URL", "http://htpc.local:7878"),
        "api_key": _env.get("RADARR_API_KEY", ""),
        "api_version": "v3",
        "lookup_endpoint": "movie/lookup",
        "add_endpoint": "movie",
        "root_folder_endpoint": "rootfolder",
        "quality_profile_endpoint": "qualityprofile",
        "default_quality_profile": 6,  # HD - 720p/1080p
        "default_root_folder": "D:\\Movies",
    },
    "tv": {
        "name": "Sonarr",
        "url": _env.get("SONARR_URL", "http://htpc.local:8989"),
        "api_key": _env.get("SONARR_API_KEY", ""),
        "api_version": "v3",
        "lookup_endpoint": "series/lookup",
        "add_endpoint": "series",
        "root_folder_endpoint": "rootfolder",
        "quality_profile_endpoint": "qualityprofile",
        "default_quality_profile": 6,  # HD - 720p/1080p
        "default_language_profile": 1,  # English
        "default_root_folder": "G:\\television",
    },
    "music": {
        "name": "Lidarr",
        "url": _env.get("LIDARR_URL", "http://htpc.local:8686"),
        "api_key": _env.get("LIDARR_API_KEY", ""),
        "api_version": "v1",
        "lookup_endpoint": "artist/lookup",
        "add_endpoint": "artist",
        "root_folder_endpoint": "rootfolder",
        "quality_profile_endpoint": "qualityprofile",
        "default_quality_profile": 1,  # Any
        "default_root_folder": "D:\\Music",
    },
}


def _api_get(service_key, endpoint):
    """Generic GET for any *arr service."""
    svc = SERVICES[service_key]
    sep = "&" if "?" in endpoint else "?"
    url = f"{svc['url']}/api/{svc['api_version']}/{endpoint}{sep}apikey={svc['api_key']}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def _api_post(service_key, endpoint, data):
    """Generic POST for any *arr service."""
    svc = SERVICES[service_key]
    url = f"{svc['url']}/api/{svc['api_version']}/{endpoint}?apikey={svc['api_key']}"
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()[:300]
        # Common case: already exists
        if e.code == 400 and "already been added" in error_body.lower():
            return {"error": "already_exists", "message": error_body}
        return {"error": f"{e.code}: {error_body}"}
    except Exception as e:
        return {"error": str(e)}


def is_available(service_key):
    """Check if a service is configured (has API key)."""
    return bool(SERVICES.get(service_key, {}).get("api_key"))


def get_status(service_key):
    """Ping a service to check if it's up."""
    return _api_get(service_key, "system/status")


def get_root_folders(service_key):
    """Get root folders for a service."""
    svc = SERVICES[service_key]
    return _api_get(service_key, svc["root_folder_endpoint"])


def get_quality_profiles(service_key):
    """Get quality profiles for a service."""
    svc = SERVICES[service_key]
    return _api_get(service_key, svc["quality_profile_endpoint"])


# ---- Search / Lookup ----

def search(service_key, term):
    """Search for media across any *arr service.

    Returns normalized list of results:
        {id, title, year, overview, poster_url, service, raw}
    """
    svc = SERVICES[service_key]
    encoded = urllib.parse.quote(term)
    raw_results = _api_get(service_key, f"{svc['lookup_endpoint']}?term={encoded}")

    if isinstance(raw_results, dict) and "error" in raw_results:
        return raw_results

    if not isinstance(raw_results, list):
        return []

    results = []
    for r in raw_results[:10]:  # cap at 10
        results.append(_normalize_result(service_key, r))

    return results


def _normalize_result(service_key, raw):
    """Normalize a search result from any *arr service into a common format."""
    if service_key == "movie":
        poster = _extract_image(raw, "poster")
        return {
            "id": raw.get("tmdbId"),
            "title": raw.get("title", "Unknown"),
            "year": raw.get("year", ""),
            "overview": (raw.get("overview") or "")[:200],
            "poster_url": poster,
            "service": "movie",
            "service_name": "Radarr",
            "already_added": raw.get("id", 0) > 0 and raw.get("path", "") != "",
            "raw": raw,
        }
    elif service_key == "tv":
        poster = _extract_image(raw, "poster")
        return {
            "id": raw.get("tvdbId"),
            "title": raw.get("title", "Unknown"),
            "year": raw.get("year", ""),
            "overview": (raw.get("overview") or "")[:200],
            "poster_url": poster,
            "service": "tv",
            "service_name": "Sonarr",
            "already_added": raw.get("id", 0) > 0 and raw.get("path", "") != "",
            "raw": raw,
        }
    elif service_key == "music":
        poster = _extract_image(raw, "poster") or _extract_image(raw, "fanart")
        return {
            "id": raw.get("foreignArtistId"),
            "title": raw.get("artistName", "Unknown"),
            "year": "",
            "overview": (raw.get("overview") or "")[:200],
            "poster_url": poster,
            "service": "music",
            "service_name": "Lidarr",
            "already_added": raw.get("id", 0) > 0 and raw.get("path", "") != "",
            "raw": raw,
        }
    return {}


def _extract_image(data, cover_type):
    """Extract image URL from *arr API response."""
    for img in data.get("images", []):
        if img.get("coverType") == cover_type:
            url = img.get("remoteUrl") or img.get("url", "")
            if url:
                return url
    return ""


# ---- Add to Library ----

def add_to_library(service_key, result):
    """Add a search result to the appropriate *arr library.

    Takes a normalized result from search(). Returns the API response.
    """
    svc = SERVICES[service_key]

    if service_key == "movie":
        return _add_movie(result)
    elif service_key == "tv":
        return _add_series(result)
    elif service_key == "music":
        return _add_artist(result)
    return {"error": f"Unknown service: {service_key}"}


def _add_movie(result):
    """Add movie to Radarr."""
    raw = result["raw"]
    raw["qualityProfileId"] = SERVICES["movie"]["default_quality_profile"]
    raw["rootFolderPath"] = SERVICES["movie"]["default_root_folder"]
    raw["monitored"] = True
    raw["addOptions"] = {"searchForMovie": True}
    return _api_post("movie", "movie", raw)


def _add_series(result):
    """Add TV series to Sonarr."""
    raw = result["raw"]
    raw["qualityProfileId"] = SERVICES["tv"]["default_quality_profile"]
    raw["languageProfileId"] = SERVICES["tv"]["default_language_profile"]
    raw["rootFolderPath"] = SERVICES["tv"]["default_root_folder"]
    raw["monitored"] = True
    raw["addOptions"] = {
        "monitor": "all",
        "searchForMissingEpisodes": True,
        "searchForCutoffUnmetEpisodes": False,
    }
    return _api_post("tv", "series", raw)


def _add_artist(result):
    """Add music artist to Lidarr."""
    raw = result["raw"]
    raw["qualityProfileId"] = SERVICES["music"]["default_quality_profile"]
    raw["metadataProfileId"] = 1  # Standard
    raw["rootFolderPath"] = SERVICES["music"]["default_root_folder"]
    raw["monitored"] = True
    raw["addOptions"] = {
        "monitor": "all",
        "searchForMissingAlbums": True,
    }
    return _api_post("music", "artist", raw)


# ---- Quick Add: combined add + extraction batch ----

def quick_add(service_key, result):
    """Add media to *arr library and create extraction batch.

    Returns:
        {
            "library_result": {...},  # *arr API response
            "batch_result": {...},    # extraction script result (movies only for now)
            "title": "...",
            "service": "movie"|"tv"|"music",
        }
    """
    import extraction

    # Add to library
    library_result = add_to_library(service_key, result)

    already_existed = False
    if isinstance(library_result, dict) and library_result.get("error") == "already_exists":
        already_existed = True

    title = result["title"]
    year = result.get("year", "")
    display_title = f"{title} ({year})" if year else title

    # Create extraction batch (movie/tv for now)
    batch_result = None
    if service_key in ("movie", "tv"):
        slug = extraction.slugify(title)
        # Check if extraction script already exists
        script_path = os.path.join(
            os.path.expanduser("~/dev/openpeon/extraction"),
            f"extract_{slug}.py"
        )
        if os.path.exists(script_path):
            batch_result = {"ok": True, "already_exists": True, "slug": slug}
        else:
            # Try to find MKV file
            mkv_results = extraction.find_mkv_files(title)
            mkv_path = mkv_results[0]["mkv_path"] if mkv_results else ""
            if not mkv_path:
                # Use default path pattern — it'll be updated when file arrives
                mkv_path = f"/Volumes/D-drive-music/Movies/{display_title}/{display_title} Remux-1080p.mkv"

            # Use LLM to generate quotes, then create script with them
            import quote_generator
            batch_result = quote_generator.populate_extraction_script(
                name=slug,
                title=title,
                mkv_path=mkv_path,
                year=str(year),
                audio_stream="0:1",
            )

    return {
        "library_result": library_result,
        "library_already_existed": already_existed,
        "batch_result": batch_result,
        "title": display_title,
        "service": service_key,
    }


def retry_quote_generation(title, year):
    """Retry quote generation for a movie that failed during add.

    Checks if an extraction script exists and has real clips. If the script
    is empty or missing, regenerates quotes via populate_extraction_script().

    Returns dict with 'ok' or 'error'.
    """
    import extraction
    import quote_generator
    import re as _re

    slug = extraction.slugify(title)
    script_path = os.path.join(
        os.path.expanduser("~/dev/openpeon/extraction"),
        f"extract_{slug}.py"
    )

    # Check if script exists and has real clips
    has_real_clips = False
    if os.path.exists(script_path):
        try:
            with open(script_path) as f:
                content = f.read()
            pattern = r'\("([^"]+)",\s*(\d+),\s*"([^"]+)",\s*(\d+)\)'
            matches = list(_re.finditer(pattern, content))
            has_real_clips = len(matches) > 0
        except Exception:
            pass

    if has_real_clips:
        return {"ok": True, "message": f"Script already has clips: {slug}", "slug": slug}

    # Script is empty or missing — generate quotes
    # Try to find MKV file
    mkv_results = extraction.find_mkv_files(title)
    mkv_path = mkv_results[0]["mkv_path"] if mkv_results else ""
    if not mkv_path:
        display_title = f"{title} ({year})" if year else title
        mkv_path = f"/Volumes/D-drive-music/Movies/{display_title}/{display_title} Remux-1080p.mkv"

    # If script exists but is empty, delete it so populate can recreate
    if os.path.exists(script_path) and not has_real_clips:
        try:
            os.unlink(script_path)
        except OSError:
            pass

    result = quote_generator.populate_extraction_script(
        name=slug,
        title=title,
        mkv_path=mkv_path,
        year=str(year),
        audio_stream="0:1",
    )

    return result
