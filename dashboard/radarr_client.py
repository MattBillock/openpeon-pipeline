"""Radarr API client for the OpenPeon pipeline dashboard."""
import json
import os
import urllib.request
import urllib.parse
import urllib.error


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


def _get_config():
    env = _load_env()
    return {
        "url": env.get("RADARR_URL", "http://htpc.local:7878"),
        "api_key": env.get("RADARR_API_KEY", ""),
    }


def _api_get(endpoint):
    cfg = _get_config()
    sep = "&" if "?" in endpoint else "?"
    url = f"{cfg['url']}/api/v3/{endpoint}{sep}apikey={cfg['api_key']}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"error": str(e)}


def _api_post(endpoint, data):
    cfg = _get_config()
    url = f"{cfg['url']}/api/v3/{endpoint}?apikey={cfg['api_key']}"
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {"error": f"{e.code}: {e.read().decode()[:300]}"}
    except Exception as e:
        return {"error": str(e)}


def get_status():
    """Get Radarr system status."""
    return _api_get("system/status")


def get_all_movies():
    """Get all movies in Radarr."""
    return _api_get("movie")


def get_queue():
    """Get download queue."""
    return _api_get("queue")


def get_root_folders():
    """Get root folders."""
    return _api_get("rootfolder")


def lookup_movie(term):
    """Search for a movie by name."""
    encoded = urllib.parse.quote(term)
    return _api_get(f"movie/lookup?term={encoded}")


def add_movie(tmdb_id, quality_profile_id=5, root_folder="D:\\Movies", search=True):
    """Add a movie to Radarr by TMDB ID."""
    results = _api_get(f"movie/lookup?term=tmdb:{tmdb_id}")
    if isinstance(results, dict) and "error" in results:
        return results
    if not results:
        return {"error": "Movie not found"}

    movie_data = results[0]
    movie_data["qualityProfileId"] = quality_profile_id
    movie_data["rootFolderPath"] = root_folder
    movie_data["monitored"] = True
    movie_data["addOptions"] = {"searchForMovie": search}

    return _api_post("movie", movie_data)


def trigger_search(movie_id):
    """Trigger a search for a specific movie."""
    return _api_post("command", {"name": "MoviesSearch", "movieIds": [movie_id]})


def get_movie_status_summary():
    """Get a summary of all movies relevant to the pipeline."""
    movies = get_all_movies()
    if isinstance(movies, dict) and "error" in movies:
        return {"error": movies["error"], "movies": []}

    summary = []
    for m in movies:
        summary.append({
            "id": m.get("id"),
            "title": m.get("title", "Unknown"),
            "year": m.get("year"),
            "has_file": m.get("hasFile", False),
            "monitored": m.get("monitored", False),
            "path": m.get("path", ""),
            "size_gb": round(m.get("sizeOnDisk", 0) / 1e9, 1),
            "status": m.get("status", "unknown"),
        })

    return {"movies": sorted(summary, key=lambda x: x["title"])}
