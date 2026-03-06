"""OpenPeon Pipeline Dashboard — Streamlit App.

Self-sufficient management UI for the OpenPeon movie quote extraction pipeline.
Handles extraction control, STT verification review, pack building, and monitoring.
"""
import logging
import re
import subprocess
import streamlit as st
import os
import sys
import json

# Configure logging so swallowed exceptions surface in Streamlit's terminal output
logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

sys.path.insert(0, os.path.dirname(__file__))

import extraction
import health
import radarr_client
import media_client
import pack_builder
import icon_generator
import quote_generator

# Surface quote generation failures in Streamlit terminal
logging.getLogger("quote_generator").setLevel(logging.INFO)

st.set_page_config(
    page_title="OpenPeon Pipeline",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Custom CSS ---
st.markdown("""<style>
    .stProgress > div > div > div > div { background-color: #4CAF50; }
    div[data-testid="stMetric"] {
        background: #1a1f2e;
        padding: 12px 16px;
        border-radius: 8px;
        border: 1px solid #2d3348;
    }
    div[data-testid="stMetric"] label { color: #9ca3af !important; font-weight: 600; }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] { color: #e0e0e0 !important; }
    .stExpander { border: 1px solid #2d3348; border-radius: 8px; }
    section[data-testid="stSidebar"] div[data-testid="stMetric"] {
        background: #151922;
        border: 1px solid #2d3348;
    }
</style>""", unsafe_allow_html=True)

# --- Sidebar ---
st.sidebar.title("OpenPeon Pipeline")
# Support "Go fix" navigation from Things to Do
if "nav_page" in st.session_state:
    _default_page = st.session_state.pop("nav_page")
else:
    _default_page = None

_pages = [
    "Overview",
    "Things to Do",
    "Extraction Control",
    "Clip Review",
    "Pack Review",
    "Pack Designer",
    "Pack Status",
    "Media Library",
]
page = st.sidebar.radio(
    "Navigate", _pages,
    index=_pages.index(_default_page) if _default_page in _pages else 0,
)

if st.sidebar.button("Refresh"):
    st.rerun()

st.sidebar.markdown("---")

# Quick stats in sidebar
scripts = extraction.get_all_scripts()
running = sum(1 for s in scripts if s["is_running"])
total_extracted = sum(s["extracted_count"] for s in scripts)
total_clips = sum(s["total_clips"] for s in scripts)
total_verified = sum(s["verified"] for s in scripts)
total_approved = sum(s["approved"] for s in scripts)

st.sidebar.metric("Running", f"{running} / {len(scripts)}")
st.sidebar.metric("Extracted", f"{total_extracted} / {total_clips}")
st.sidebar.metric("STT Verified", total_verified)
st.sidebar.metric("Approved", total_approved)

st.sidebar.markdown("---")

# Sidebar health indicator
_health = health.check_all()
if _health["all_ok"]:
    st.sidebar.success("Systems OK")
else:
    st.sidebar.error(f"{_health['fail_count']} system issue{'s' if _health['fail_count'] != 1 else ''}")

st.sidebar.caption("Use Refresh button to update")


def _nav_button(label, target_page, key):
    """Render a button that navigates to a different page."""
    if st.button(label, key=key):
        st.session_state["nav_page"] = target_page
        st.rerun()


# ============================================================
# PAGE: Things to Do
# ============================================================
if page == "Things to Do":
    st.title("Things to Do")
    st.caption("Actionable items across the entire pipeline, sorted by priority.")

    # --- Data gathering ---
    diagnoses = {s["name"]: health.diagnose_movie(s) for s in scripts}
    pack_summaries = pack_builder.get_all_pack_review_summary()
    pack_details_cache = {}
    for ps in pack_summaries:
        pack_details_cache[ps["name"]] = pack_builder.get_pack_details(ps["name"])
    unpublished = pack_builder.get_unpublished_packs()
    registry_status = pack_builder.get_registry_status()

    # --- Build to-do items ---
    items_p1 = []  # Blockers
    items_p2 = []  # Important
    items_p3 = []  # Nice to have

    # P1: System health failures
    for chk in _health["checks"]:
        if not chk["ok"]:
            items_p1.append({
                "label": f"System: {chk['name']} — {chk['message']}",
                "detail": chk["fix"],
                "severity": "error",
                "nav": None,
            })

    # P1: Red-severity movies
    for s in scripts:
        diag = diagnoses[s["name"]]
        if diag["severity"] == "red":
            items_p1.append({
                "label": f"{s['name']} — {diag['summary']}",
                "detail": "; ".join(diag["fixes"][:2]) if diag["fixes"] else "",
                "severity": "error",
                "nav": "Extraction Control",
            })

    # P1: Packs with missing sound files
    for ps in pack_summaries:
        details = pack_details_cache.get(ps["name"])
        if details:
            missing_files = 0
            for cat, sounds in details["categories"].items():
                missing_files += sum(1 for s_item in sounds if not s_item["exists"])
            if missing_files:
                items_p1.append({
                    "label": f"Pack '{ps['display_name']}' — {missing_files} missing sound file(s)",
                    "detail": "Sound files referenced in manifest but not on disk.",
                    "severity": "error",
                    "nav": "Pack Review",
                })

    # P2: Unreviewed clips per movie
    movies_with_unreviewed = [(s["name"], s["unreviewed"]) for s in scripts if s["unreviewed"] > 0]
    movies_with_unreviewed.sort(key=lambda x: x[1], reverse=True)
    for name, count in movies_with_unreviewed:
        items_p2.append({
            "label": f"{name} — {count} clip(s) to review",
            "detail": "Listen and approve/reject extracted clips.",
            "severity": "warning",
            "nav": "Clip Review",
        })

    # P2: Orange-severity movies (incomplete extraction, not running)
    for s in scripts:
        diag = diagnoses[s["name"]]
        if diag["severity"] == "orange" and not s["is_running"]:
            items_p2.append({
                "label": f"{s['name']} — {diag['summary']}",
                "detail": "; ".join(diag["fixes"][:2]) if diag["fixes"] else "",
                "severity": "warning",
                "nav": "Extraction Control",
            })

    # P2: Packs with empty CESP categories
    for ps in pack_summaries:
        details = pack_details_cache.get(ps["name"])
        if details:
            empty_cats = [c for c in pack_builder.CATEGORIES
                         if not details["categories"].get(c)]
            if empty_cats:
                items_p2.append({
                    "label": f"Pack '{ps['display_name']}' — {len(empty_cats)} empty category(ies)",
                    "detail": f"Missing: {', '.join(empty_cats)}",
                    "severity": "warning",
                    "nav": "Pack Review",
                })

    # P2: Packs with flagged sounds
    for ps in pack_summaries:
        if ps["flagged"] > 0:
            items_p2.append({
                "label": f"Pack '{ps['display_name']}' — {ps['flagged']} flagged sound(s)",
                "detail": "Sounds marked as needing fix or update.",
                "severity": "warning",
                "nav": "Pack Review",
            })

    # P2: Packs with unreviewed sounds
    for ps in pack_summaries:
        unrev = ps["unreviewed"]
        if unrev > 0:
            items_p2.append({
                "label": f"Pack '{ps['display_name']}' — {unrev} unreviewed sound(s)",
                "detail": "Listen to each sound and mark OK or flag.",
                "severity": "warning",
                "nav": "Pack Review",
            })

    # P2: Movies with approved clips but no pack built
    published_packs = pack_builder.get_published_packs()
    published_pack_names = {p["name"] for p in published_packs}
    for s in scripts:
        if s["approved"] > 0:
            slug = s["name"]
            # Check if any pack exists for this movie (approximate match)
            has_pack = any(slug in pn for pn in published_pack_names)
            if not has_pack:
                items_p2.append({
                    "label": f"{s['name']} — {s['approved']} approved clip(s), no pack built",
                    "detail": "Go to Pack Designer to build a sound pack.",
                    "severity": "warning",
                    "nav": "Pack Designer",
                })

    # P2: Packs missing icons
    for ps in pack_summaries:
        if not ps["has_icon"]:
            items_p2.append({
                "label": f"Pack '{ps['display_name']}' — missing icon",
                "detail": "Generate or upload a pack icon.",
                "severity": "warning",
                "nav": "Pack Review",
            })

    # P3: Unpublished packs
    for pack in unpublished:
        items_p3.append({
            "label": f"Pack '{pack['display_name']}' — unpublished changes ({pack['files_changed']} file(s))",
            "detail": "Commit and push to the registry.",
            "severity": "info",
            "nav": "Pack Designer",
        })

    # P3: Unregistered packs
    for name, info in registry_status.items():
        if not info["registered"]:
            items_p3.append({
                "label": f"Pack '{name}' — not registered in PeonPing registry",
                "detail": "Create a PR to add this pack to the official index.",
                "severity": "info",
                "nav": "Pack Designer",
            })

    # P3: Approved clips missing category assignment
    for s in scripts:
        uncat = extraction.count_uncategorized_approved(s["name"])
        if uncat > 0:
            items_p3.append({
                "label": f"{s['name']} — {uncat} approved clip(s) need category",
                "detail": "Assign CESP categories in Clip Review.",
                "severity": "info",
                "nav": "Clip Review",
            })

    total_items = len(items_p1) + len(items_p2) + len(items_p3)

    # --- Summary metrics ---
    mcol1, mcol2, mcol3, mcol4 = st.columns(4)
    mcol1.metric("Total Items", total_items)
    mcol2.metric("Blockers", len(items_p1))
    mcol3.metric("Important", len(items_p2))
    mcol4.metric("Nice to Have", len(items_p3))

    # --- Pipeline progress funnel ---
    st.markdown("---")
    st.subheader("Pipeline Progress")
    total_movies = len(scripts)
    movies_extracted = sum(1 for s in scripts if s["extracted_count"] > 0)
    movies_with_approved_clips = sum(1 for s in scripts if s["approved"] > 0)
    packs_built = len(published_packs)
    packs_qad = sum(1 for ps in pack_summaries if ps["pack_status"] == "complete")
    packs_registered = sum(1 for _, info in registry_status.items() if info["registered"])

    funnel_cols = st.columns(6)
    funnel_cols[0].metric("Movies", total_movies)
    funnel_cols[1].metric("Extracted", movies_extracted)
    funnel_cols[2].metric("Clips Approved", movies_with_approved_clips)
    funnel_cols[3].metric("Packs Built", packs_built)
    funnel_cols[4].metric("Packs QA'd", packs_qad)
    funnel_cols[5].metric("Registered", packs_registered)

    # --- Prioritized sections ---
    st.markdown("---")

    if items_p1:
        st.subheader(f"Blockers ({len(items_p1)})")
        for idx, item in enumerate(items_p1):
            st.error(f"**{item['label']}**")
            if item["detail"]:
                st.caption(item["detail"])
            if item["nav"]:
                _nav_button("Go fix", item["nav"], key=f"p1_fix_{idx}")

    if items_p2:
        st.subheader(f"Important ({len(items_p2)})")
        for idx, item in enumerate(items_p2):
            st.warning(f"**{item['label']}**")
            if item["detail"]:
                st.caption(item["detail"])
            if item["nav"]:
                _nav_button("Go fix", item["nav"], key=f"p2_fix_{idx}")

    if items_p3:
        st.subheader(f"Nice to Have ({len(items_p3)})")
        for idx, item in enumerate(items_p3):
            st.info(f"**{item['label']}**")
            if item["detail"]:
                st.caption(item["detail"])
            if item["nav"]:
                _nav_button("Go fix", item["nav"], key=f"p3_fix_{idx}")

    if total_items == 0:
        st.success("Nothing to do! Pipeline is fully caught up.")


# ============================================================
# PAGE: Overview
# ============================================================
elif page == "Overview":
    st.title("Pipeline Overview")

    published = pack_builder.get_published_packs()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Movies", len(scripts))
    col2.metric("Running", running)
    col3.metric("Clips Extracted", f"{total_extracted}/{total_clips}")
    col4.metric("STT Verified", total_verified)
    col5.metric("Published Packs", len(published))

    st.markdown("---")

    # Needs Attention section — problem movies at the top
    _diagnoses = {s["name"]: health.diagnose_movie(s) for s in scripts}
    _problem_movies = [s for s in scripts if _diagnoses[s["name"]]["severity"] == "red"]
    _warning_movies = [s for s in scripts if _diagnoses[s["name"]]["severity"] == "orange"]

    if _problem_movies or _warning_movies:
        st.subheader("Needs Attention")
        for s in _problem_movies:
            diag = _diagnoses[s["name"]]
            st.error(f"**{s['name']}** — {diag['summary']}")
        for s in _warning_movies:
            diag = _diagnoses[s["name"]]
            st.warning(f"**{s['name']}** — {diag['summary']}")
        st.markdown("---")

    # Extraction progress table with diagnose_movie summaries
    st.subheader("Extraction Progress")
    for s in scripts:
        diag = _diagnoses[s["name"]]
        pct = (s["extracted_count"] / s["total_clips"]) if s["total_clips"] > 0 else 0

        cols = st.columns([2, 3, 1, 1, 1, 1])
        severity = diag["severity"]
        status_text = diag["summary"]
        if severity == "red":
            cols[0].markdown(f":red[**{s['name']}**]")
        elif severity == "orange":
            cols[0].markdown(f":orange[**{s['name']}**]")
        else:
            cols[0].markdown(f":green[**{s['name']}**]")
        cols[1].progress(min(pct, 1.0))
        cols[2].caption(status_text)
        cols[3].caption(f"V:{s['verified']}")
        cols[4].caption(f"R:{s['needs_review']}")
        cols[5].caption(f"A:{s['approved']}")

    st.markdown("---")

    # Published packs
    st.subheader(f"Published Packs ({len(published)})")
    if published:
        pack_data = [{
            "Pack": p["display_name"],
            "Sounds": p["sound_count"],
            "Version": p["version"],
            "Tags": ", ".join(p["tags"][:3]),
        } for p in published]
        st.dataframe(pack_data, use_container_width=True, hide_index=True)


# ============================================================
# PAGE: Extraction Control
# ============================================================
elif page == "Extraction Control":
    st.title("Extraction Control")

    # --- Health + load banner ---
    _ec_health = health.check_all()
    _load_info = health.check_system_load()
    if _ec_health["all_ok"] and _load_info["ok"]:
        st.success("All systems ready")
    else:
        if not _ec_health["all_ok"]:
            st.error(f"{_ec_health['fail_count']} issue{'s' if _ec_health['fail_count'] != 1 else ''} blocking extraction")
            for chk in _ec_health["checks"]:
                if not chk["ok"]:
                    st.warning(f"**{chk['name']}**: {chk['message']}  \n{chk['fix']}")
        if not _load_info["ok"]:
            st.warning(f"**System load**: {_load_info['message']}")

    # --- Queue-aware batch actions (Phase 5D) ---
    st.subheader("Batch Actions")
    _running_count = sum(1 for s in scripts if s["is_running"])
    _max_concurrent = extraction.get_max_concurrent()
    _idle_incomplete = [s for s in scripts if not s["is_running"]
                        and s["extracted_count"] < s["total_clips"]
                        and s["total_clips"] > 0
                        and (s["approved"] + s["rejected"]) < s["total_clips"]]

    bcol1, bcol2, bcol3, bcol4 = st.columns([2, 1, 1, 1])
    with bcol1:
        if _running_count >= _max_concurrent:
            st.info(f"{_running_count}/{_max_concurrent} slots in use. "
                    f"{len(_idle_incomplete)} movie{'s' if len(_idle_incomplete) != 1 else ''} waiting.")
        elif _idle_incomplete:
            if st.button("Start next idle", type="primary"):
                result = extraction.start_extraction(_idle_incomplete[0]["name"])
                if "error" in result:
                    st.error(result["error"])
                else:
                    st.success(f"Started {_idle_incomplete[0]['name']}")
                    st.rerun()
        else:
            st.caption("No idle movies to start")
    with bcol2:
        if st.button("Stop ALL"):
            stopped = 0
            for s in scripts:
                if s["is_running"]:
                    extraction.stop_extraction(s["name"])
                    stopped += 1
            st.success(f"Stopped {stopped} extractions")
            st.rerun()
    with bcol3:
        d_check = health.check_d_drive()
        if d_check["ok"]:
            st.success(d_check["message"])
        else:
            st.error(d_check["message"])
    with bcol4:
        new_max = st.select_slider("Max concurrent", options=[1, 2, 3, 4],
                                    value=_max_concurrent, key="max_concurrent_slider")
        if new_max != _max_concurrent:
            extraction.set_max_concurrent(new_max)
            st.rerun()

    st.markdown("---")

    # Per-movie controls with diagnosis
    for s in scripts:
        diag = health.diagnose_movie(s)
        severity = diag["severity"]

        # Descriptive expander label instead of vague icons
        if severity == "red":
            label_prefix = "PROBLEM"
        elif severity == "green" and s["is_running"]:
            label_prefix = "RUNNING"
        elif severity == "green":
            label_prefix = "OK"
        else:
            label_prefix = "WARN"

        with st.expander(
            f"[{label_prefix}] {s['name']} — {diag['summary']}",
            expanded=(severity == "red" or s["is_running"])
        ):
            # Per-movie diagnosis panel (Phase 1C)
            if severity == "red":
                st.error(diag["summary"])
                for detail in diag["details"]:
                    st.markdown(f"- {detail}")
                for fix in diag["fixes"]:
                    st.info(f"Suggested fix: {fix}")
            elif severity == "orange":
                st.warning(diag["summary"])
                for detail in diag["details"]:
                    st.markdown(f"- {detail}")
                for fix in diag["fixes"]:
                    st.info(f"Suggested fix: {fix}")

            # One-click fix buttons (Phase 4C)
            transcript_check = health.check_transcript(s["name"])
            if not transcript_check["ok"] and transcript_check["exists"]:
                if st.button("Delete corrupt transcript & restart",
                             key=f"fix_transcript_{s['name']}", type="primary"):
                    del_result = extraction.delete_transcript(s["name"])
                    if del_result["ok"]:
                        start_result = extraction.start_extraction(s["name"])
                        if "error" in start_result:
                            st.success("Transcript deleted.")
                            st.warning(f"Could not auto-start: {start_result['error']}")
                        else:
                            st.success("Transcript deleted and extraction restarted!")
                    else:
                        st.error(f"Failed: {del_result.get('error', 'Unknown error')}")
                    st.rerun()

            if not s["is_running"] and s["extracted_count"] > 0 and s["failed"] > 0:
                if st.button("Reset extraction & start fresh",
                             key=f"reset_{s['name']}"):
                    reset_result = extraction.reset_movie_extraction(s["name"])
                    if reset_result["ok"]:
                        st.success(f"Reset {s['name']} — deleted: {', '.join(reset_result['deleted'])}")
                    else:
                        st.error(f"Reset failed: {reset_result.get('error', 'Unknown error')}")
                    st.rerun()

            # Controls
            ctrl1, ctrl2, ctrl3, ctrl4 = st.columns(4)
            with ctrl1:
                if s["is_running"]:
                    if st.button("Stop", key=f"stop_{s['name']}"):
                        extraction.stop_extraction(s["name"])
                        st.rerun()
                else:
                    if st.button("Start", key=f"start_{s['name']}", type="primary"):
                        result = extraction.start_extraction(s["name"])
                        if "error" in result:
                            st.error(result["error"])
                        else:
                            st.rerun()
            with ctrl2:
                if not s["is_running"]:
                    if st.button("Force restart", key=f"force_{s['name']}"):
                        extraction.stop_extraction(s["name"])
                        result = extraction.start_extraction(s["name"])
                        if "error" in result:
                            st.error(result["error"])
                        else:
                            st.rerun()
            with ctrl3:
                st.metric("Extracted", s["extracted_count"])
            with ctrl4:
                st.metric("Verified", s["verified"])

            # Extraction log JSON viewer
            if s["ext_log"]:
                st.caption("Extraction Results (from STT pipeline)")
                log_data = []
                for clip_name, entry in s["ext_log"].items():
                    status = entry.get("final_status", entry.get("verify_status", "?"))
                    v_score = entry.get("verify_score", 0)
                    v_heard = entry.get("verify_heard", "")[:60]
                    quote = entry.get("quote", "")[:60]
                    log_data.append({
                        "Clip": clip_name,
                        "Status": status,
                        "V.Score": f"{v_score:.2f}" if v_score else "-",
                        "Expected": quote,
                        "Heard": v_heard,
                    })
                if log_data:
                    st.dataframe(log_data, use_container_width=True, hide_index=True)

            # Parsed error summary (Phase 3B) — replaces raw console log
            log_errors = health.parse_log_errors(s["name"])
            if log_errors:
                st.caption("Detected Issues")
                for err in log_errors:
                    st.warning(f"**{err['label']}**: {err['fix']}")

            # Raw console log in nested expander for power users
            log_text = extraction.get_extraction_log(s["name"], tail=30)
            if log_text:
                with st.expander("Raw console log (last 30 lines)"):
                    st.code(log_text, language="text")

    # ---- Quick Add: type name → search → add to library + extraction batch ----
    st.markdown("---")
    st.subheader("Quick Add")

    qa_tab1, qa_tab2, qa_tab3, qa_tab4, qa_tab5 = st.tabs([
        "🎬 Movie", "📺 TV Show", "🎵 Music", "📂 Local Movie", "📋 Add Clips"
    ])

    for tab, svc_key, svc_label, placeholder in [
        (qa_tab1, "movie", "Radarr", "Search for a movie"),
        (qa_tab2, "tv", "Sonarr", "Search for a show"),
        (qa_tab3, "music", "Lidarr", "Search for an artist"),
    ]:
        with tab:
            if not media_client.is_available(svc_key):
                st.warning(f"{svc_label} not configured — add API key to ~/.openpeon/.env")
                continue

            search_term = st.text_input(
                f"Search {svc_label}",
                placeholder=placeholder,
                key=f"qa_search_{svc_key}",
            )

            if search_term:
                results = media_client.search(svc_key, search_term)
                if isinstance(results, dict) and "error" in results:
                    st.error(f"{svc_label} error: {results['error']}")
                elif not results:
                    st.info("No results found")
                else:
                    for i, r in enumerate(results[:6]):
                        col_poster, col_info, col_btn = st.columns([1, 4, 1])
                        with col_poster:
                            if r.get("poster_url"):
                                st.image(r["poster_url"], width=60)
                            else:
                                st.markdown("🎬" if svc_key == "movie" else "📺" if svc_key == "tv" else "🎵")
                        with col_info:
                            year_str = f" ({r['year']})" if r.get("year") else ""
                            st.markdown(f"**{r['title']}**{year_str}")
                            if r.get("overview"):
                                st.caption(r["overview"][:120] + ("..." if len(r.get("overview", "")) > 120 else ""))
                        with col_btn:
                            if r.get("already_added"):
                                st.markdown("✅ Added")
                            else:
                                if st.button("➕ Add", key=f"qa_add_{svc_key}_{i}", type="primary"):
                                    with st.spinner(f"Adding to {svc_label}..."):
                                        qa_result = media_client.quick_add(svc_key, r)

                                    # Report library result
                                    lib = qa_result.get("library_result", {})
                                    if qa_result.get("library_already_existed"):
                                        st.info(f"Already in {svc_label}: {qa_result['title']}")
                                    elif isinstance(lib, dict) and "error" in lib:
                                        st.error(f"{svc_label}: {lib['error'][:200]}")
                                    else:
                                        st.success(f"Added to {svc_label}: {qa_result['title']}")

                                    # Report batch result
                                    batch = qa_result.get("batch_result")
                                    if batch:
                                        if batch.get("already_exists"):
                                            st.info(f"Extraction batch already exists: {batch.get('slug', '')}")
                                        elif batch.get("ok"):
                                            st.success("Extraction batch created!")
                                        elif batch.get("error"):
                                            st.error(f"Quote generation failed: {batch['error'][:200]}")
                                            st.caption("Use 'Retry Quotes' in Media Library > Pipeline Targets to try again.")

    with qa_tab4:
        # ---- Add Local Movie as Extraction Batch ----
        st.caption("Create extraction batch for a movie already on disk — quotes auto-generated via LLM")

        local_search = st.text_input("Search D-drive for MKV", placeholder="Movie name",
                                     key="local_movie_search")
        if local_search:
            mkv_results = extraction.find_mkv_files(local_search)
            if not mkv_results:
                st.warning("No MKV files found matching that name on D-drive")
            else:
                for i, mkv in enumerate(mkv_results[:8]):
                    col_info, col_btn = st.columns([4, 1])
                    with col_info:
                        st.markdown(f"**{mkv['dir_name']}**")
                        st.caption(f"`{mkv['mkv_path']}` — {mkv['size_gb']} GB")
                    with col_btn:
                        slug = extraction.slugify(mkv["dir_name"].split("(")[0].strip())
                        script_exists = os.path.exists(os.path.join(
                            extraction.EXTRACTION_DIR, f"extract_{slug}.py"
                        ))
                        if script_exists:
                            st.markdown("✅ Exists")
                        else:
                            if st.button("🎬 Create", key=f"local_add_{i}", type="primary"):
                                # Parse year from dir name if present
                                year_match = re.search(r'\((\d{4})\)', mkv["dir_name"])
                                year = year_match.group(1) if year_match else ""
                                title = mkv["dir_name"].split("(")[0].strip()

                                with st.spinner(f"Generating quotes for {title} via LLM..."):
                                    result = quote_generator.populate_extraction_script(
                                        name=slug,
                                        title=title,
                                        mkv_path=mkv["mkv_path"],
                                        year=year,
                                        audio_stream="0:1",
                                    )

                                if isinstance(result, dict) and result.get("ok"):
                                    st.success(
                                        f"Created extraction batch for {title} "
                                        f"with {result.get('clip_count', 0)} quotes!"
                                    )
                                    st.rerun()
                                elif isinstance(result, dict) and result.get("error"):
                                    st.error(f"Error: {result['error'][:200]}")
                                else:
                                    st.error("Unknown error creating batch")

    with qa_tab5:
        # ---- Add Clips to Existing ----
        existing_names = [s["name"] for s in scripts]
        if not existing_names:
            st.info("No movies yet. Add one via Quick Add or Local Movie first.")
        else:
            target_movie = st.selectbox("Movie", existing_names, key="add_clips_movie")
            st.caption("Add quotes (one per line): `clip_name | timestamp_seconds | quote text | duration`")
            add_quotes_text = st.text_area("New quotes", height=150, key="add_clips_quotes",
                                           placeholder="clip_name | timestamp | quote text | duration")

            acol1, acol2 = st.columns(2)
            with acol1:
                if st.button("Add Clips", type="primary", key="add_clips_btn"):
                    if not add_quotes_text.strip():
                        st.error("Enter at least one quote")
                    else:
                        clips = []
                        for line in add_quotes_text.strip().split("\n"):
                            parts = [p.strip() for p in line.split("|")]
                            if len(parts) >= 4:
                                try:
                                    clips.append((
                                        extraction.slugify(parts[0]),
                                        int(parts[1]),
                                        parts[2],
                                        int(parts[3]),
                                    ))
                                except ValueError:
                                    st.warning(f"Skipping invalid line: {line}")
                        if clips:
                            result = extraction.add_clips_to_script(target_movie, clips)
                            if result.get("ok"):
                                st.success(f"Added {result['added']} clips to {target_movie}")
                                st.rerun()
                            else:
                                st.error(result.get("error", "Unknown error"))


# ============================================================
# PAGE: Clip Review
# ============================================================
elif page == "Clip Review":
    st.title("Clip Review")

    movie_names = [s["name"] for s in scripts]
    if not movie_names:
        st.info("No extraction scripts found.")
    else:
        # --- Filters bar ---
        fcol1, fcol2, fcol3 = st.columns([2, 2, 2])
        with fcol1:
            selected_movie = st.selectbox("Movie", movie_names)
        with fcol2:
            extraction_filter = st.selectbox("Extraction status", [
                "Any", "Has Audio", "Verified", "Needs Review", "Failed", "Not Extracted"
            ])
        with fcol3:
            review_filter = st.selectbox("Review status", [
                "Any", "Unreviewed", "Approved", "Rejected"
            ])

        if selected_movie:
            all_clips = extraction.get_clips_for_review(selected_movie)
            clips = all_clips[:]

            # Apply extraction filter
            if extraction_filter == "Has Audio":
                clips = [c for c in clips if c["has_mp3"]]
            elif extraction_filter == "Verified":
                clips = [c for c in clips if c["extraction_status"] == "verified"]
            elif extraction_filter == "Needs Review":
                clips = [c for c in clips if c["extraction_status"] == "review"]
            elif extraction_filter == "Failed":
                clips = [c for c in clips if c["extraction_status"] == "failed"]
            elif extraction_filter == "Not Extracted":
                clips = [c for c in clips if not c["has_mp3"]]

            # Apply review filter
            if review_filter == "Unreviewed":
                clips = [c for c in clips if c["status"] == "unreviewed"]
            elif review_filter == "Approved":
                clips = [c for c in clips if c["status"] == "approved"]
            elif review_filter == "Rejected":
                clips = [c for c in clips if c["status"] == "rejected"]

            # --- Summary stats ---
            total = len(all_clips)
            has_audio = sum(1 for c in all_clips if c["has_mp3"])
            n_verified = sum(1 for c in all_clips if c["extraction_status"] == "verified")
            n_review = sum(1 for c in all_clips if c["extraction_status"] == "review")
            n_failed = sum(1 for c in all_clips if c["extraction_status"] == "failed")
            n_approved = sum(1 for c in all_clips if c["status"] == "approved")
            n_rejected = sum(1 for c in all_clips if c["status"] == "rejected")

            scol1, scol2, scol3, scol4, scol5, scol6 = st.columns(6)
            scol1.metric("Total", total)
            scol2.metric("Audio", has_audio)
            scol3.metric("Verified", n_verified)
            scol4.metric("Review", n_review)
            scol5.metric("Approved", n_approved)
            scol6.metric("Rejected", n_rejected)

            # View mode toggle
            compact_mode = st.toggle("Compact mode", value=True,
                                     help="Quick approve/reject with auto-category", key="compact_toggle")

            # --- Batch actions ---
            bcol1, bcol2, bcol3, bcol4, bcol5 = st.columns(5)
            with bcol1:
                if st.button("Approve all verified", type="primary"):
                    count = 0
                    for c in all_clips:
                        if c["extraction_status"] == "verified" and c["status"] == "unreviewed":
                            # Auto-suggest category if none set
                            cat = c.get("category", "")
                            if not cat:
                                suggs = extraction.suggest_category(c.get("expected_quote", ""), c["name"])
                                cat = suggs[0][0] if suggs else ""
                            extraction.save_clip_review(selected_movie, c["name"], "approved", cat)
                            count += 1
                    if count:
                        st.success(f"Approved {count}")
                    st.rerun()
            with bcol2:
                if st.button("Reject all failed"):
                    count = 0
                    for c in all_clips:
                        if c["extraction_status"] == "failed" and c["status"] == "unreviewed":
                            extraction.save_clip_review(selected_movie, c["name"], "rejected")
                            count += 1
                    if count:
                        st.success(f"Rejected {count}")
                    st.rerun()
            with bcol3:
                if n_failed > 0:
                    if st.button(f"🔄 Retry {n_failed} failed"):
                        count = 0
                        for c in all_clips:
                            if c["extraction_status"] == "failed":
                                extraction.retry_clip(selected_movie, c["name"])
                                count += 1
                        if count:
                            st.info(f"Re-extracting {count} clips on Mini")
                else:
                    st.button("🔄 Retry failed", disabled=True)
            with bcol4:
                if st.button("🔄 Sync from Mini"):
                    result = extraction.sync_from_mini()
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.success("Synced!")
                        st.rerun()
            with bcol5:
                st.caption(f"Showing {len(clips)} / {total} clips")

            st.markdown("---")

            categories = [""] + pack_builder.CATEGORIES
            cat_counts = extraction.get_category_counts(selected_movie)

            # --- Clip review cards ---
            for i, clip in enumerate(clips):
                ext_status = clip["extraction_status"]
                rev_status = clip["status"]
                v_score = clip["verify_score"]

                # Status icon
                if rev_status == "approved":
                    icon = "👍"
                elif rev_status == "rejected":
                    icon = "👎"
                elif ext_status == "verified":
                    icon = "🟢"
                elif ext_status == "review":
                    icon = "🟡"
                elif ext_status == "failed":
                    icon = "🔴"
                else:
                    icon = "⬜"

                # ========== COMPACT MODE ==========
                if compact_mode:
                    # Auto-suggest category (always returns at least one)
                    suggestions = extraction.suggest_category(
                        clip.get("expected_quote", ""), clip["name"], cat_counts
                    )
                    suggested_cat = suggestions[0][0] if suggestions else ""
                    stored_cat = clip.get("category", "")
                    current_cat = stored_cat or suggested_cat

                    score_str = f"{v_score:.0%}" if v_score else ""
                    quote_short = clip["expected_quote"][:40] if clip["expected_quote"] else ""

                    c1, c2, c3, c4, c5, c6 = st.columns([0.3, 1.5, 1.5, 1, 0.8, 1])
                    with c1:
                        st.write(icon)
                    with c2:
                        st.caption(f"**{clip['name']}** {score_str}")
                        if clip["has_mp3"]:
                            try:
                                with open(clip["path"], "rb") as f:
                                    audio_bytes = f.read()
                                st.audio(audio_bytes, format="audio/mp3")
                            except Exception:
                                pass
                    with c3:
                        st.caption(f"\"{quote_short}\"" if quote_short else "—")
                    with c4:
                        new_cat = st.selectbox(
                            "cat", categories,
                            index=categories.index(current_cat) if current_cat in categories else 0,
                            key=f"cc_{clip['name']}_{i}", label_visibility="collapsed"
                        )
                    # Auto-save category when dropdown changes
                    if new_cat and new_cat != stored_cat:
                        extraction.save_clip_category(selected_movie, clip["name"], new_cat)
                    with c5:
                        if rev_status != "approved":
                            if st.button("✅", key=f"qa_{clip['name']}_{i}",
                                         type="primary" if clip["has_mp3"] else "secondary"):
                                extraction.save_clip_review(selected_movie, clip["name"], "approved", new_cat)
                                st.rerun()
                        else:
                            st.write("👍")
                    with c6:
                        bc1, bc2 = st.columns(2)
                        with bc1:
                            if st.button("❌", key=f"qr_{clip['name']}_{i}"):
                                extraction.save_clip_review(selected_movie, clip["name"], "rejected", new_cat)
                                st.rerun()
                        with bc2:
                            if clip["has_mp3"] or ext_status == "failed":
                                rc1, rc2 = st.columns(2)
                                with rc1:
                                    if st.button("🔄", key=f"qe_{clip['name']}_{i}"):
                                        extraction.retry_clip(selected_movie, clip["name"])
                                        st.info(f"Re-extracting {clip['name']}")
                                with rc2:
                                    ov_ts = st.number_input(
                                        "ts", min_value=0, step=1,
                                        key=f"ov_{clip['name']}_{i}",
                                        label_visibility="collapsed",
                                        placeholder="override sec",
                                    )
                                    if ov_ts and st.button("🎯", key=f"ovb_{clip['name']}_{i}",
                                                           help="Retry at exact timestamp"):
                                        extraction.retry_clip(selected_movie, clip["name"],
                                                              override_timestamp=ov_ts)
                                        st.info(f"Re-extracting {clip['name']} at {ov_ts}s")

                    continue  # Skip the detailed expander

                # ========== DETAILED MODE ==========
                score_str = f" ({v_score:.0%})" if v_score else ""
                label = f"{icon} {clip['name']}{score_str}"
                if clip["expected_quote"]:
                    label += f" — \"{clip['expected_quote'][:50]}{'...' if len(clip['expected_quote']) > 50 else ''}\""

                with st.expander(label, expanded=(ext_status in ("verified", "review") and rev_status == "unreviewed")):
                    col_audio, col_info, col_actions = st.columns([2, 2, 2])

                    with col_audio:
                        if clip["expected_quote"]:
                            st.markdown(f"**Expected:** \"{clip['expected_quote']}\"")
                        if clip["verify_heard"]:
                            st.markdown(f"**Heard:** \"{clip['verify_heard']}\"")
                        if clip["has_mp3"]:
                            try:
                                with open(clip["path"], "rb") as f:
                                    audio_bytes = f.read()
                                st.audio(audio_bytes, format="audio/mp3")
                            except Exception:
                                st.warning("Audio load failed")
                            st.caption(f"{clip['size_kb']} KB")
                        else:
                            st.info("Not extracted yet")

                    with col_info:
                        if v_score:
                            st.metric("Verify Score", f"{v_score:.0%}")
                        if clip["pre_match_score"]:
                            st.caption(f"Pre-match: {clip['pre_match_score']:.0%}")
                        st.caption(f"Extraction: {ext_status}")
                        st.caption(f"Review: {rev_status}")
                        if clip.get("notes"):
                            st.caption(f"Note: {clip['notes']}")

                    with col_actions:
                        # Category suggestion (always returns at least one)
                        suggestions = extraction.suggest_category(
                            clip.get("expected_quote", ""), clip["name"], cat_counts
                        )
                        suggested_cat = suggestions[0][0] if suggestions else ""

                        # Default to saved category, then suggestion
                        stored_cat = clip["category"] if clip["category"] else ""
                        default_cat = stored_cat or suggested_cat
                        default_idx = categories.index(default_cat) if default_cat in categories else 0

                        new_cat = st.selectbox(
                            "Category",
                            categories,
                            index=default_idx,
                            key=f"cat_{clip['name']}_{i}"
                        )

                        # Auto-save category when dropdown changes
                        if new_cat and new_cat != stored_cat:
                            extraction.save_clip_category(selected_movie, clip["name"], new_cat)

                        # Show suggestion hint if no category set yet
                        if not stored_cat and suggestions:
                            top3 = ", ".join(f"{c} ({s:.0%})" for c, s in suggestions[:3])
                            st.caption(f"Suggested: {top3}")

                        a1, a2, a3, a4 = st.columns(4)
                        with a1:
                            if st.button("✅", key=f"ok_{clip['name']}_{i}", help="Approve",
                                         type="primary" if clip["has_mp3"] and rev_status != "approved" else "secondary"):
                                extraction.save_clip_review(selected_movie, clip["name"], "approved", new_cat)
                                st.rerun()
                        with a2:
                            if st.button("❌", key=f"no_{clip['name']}_{i}", help="Reject"):
                                extraction.save_clip_review(selected_movie, clip["name"], "rejected", new_cat)
                                st.rerun()
                        with a3:
                            if clip["has_mp3"] or ext_status == "failed":
                                if st.button("🔄", key=f"re_{clip['name']}_{i}",
                                             help="Re-extract clip on Mini (clears log, re-runs Whisper)"):
                                    result = extraction.retry_clip(selected_movie, clip["name"])
                                    if "error" in result:
                                        st.error(f"Retry failed: {result['error']}")
                                    else:
                                        st.info(f"Re-extracting {clip['name']} on Mini (PID {result['pid']})")
                                ov_ts = st.number_input(
                                    "Override timestamp (sec)", min_value=0, step=1,
                                    key=f"ovd_{clip['name']}_{i}",
                                )
                                if ov_ts and st.button("🎯 Retry at timestamp", key=f"ovdb_{clip['name']}_{i}"):
                                    result = extraction.retry_clip(
                                        selected_movie, clip["name"], override_timestamp=ov_ts)
                                    if "error" in result:
                                        st.error(f"Override retry failed: {result['error']}")
                                    else:
                                        st.info(f"Re-extracting {clip['name']} at {ov_ts}s")
                        with a4:
                            if st.button("🔄🔁", key=f"sync_{clip['name']}_{i}",
                                         help="Sync results from Mini"):
                                result = extraction.sync_from_mini(selected_movie)
                                if "error" in result:
                                    st.error(result["error"])
                                else:
                                    st.success("Synced!")
                                    st.rerun()

                        reject_note = st.text_input(
                            "Note",
                            value=clip.get("notes", ""),
                            key=f"note_{clip['name']}_{i}",
                            placeholder="Rejection reason"
                        )
                        if reject_note and st.button("Reject + note", key=f"rn_{clip['name']}_{i}"):
                            extraction.save_clip_review(
                                selected_movie, clip["name"], "rejected",
                                new_cat, reject_note
                            )
                            st.rerun()


# ============================================================
# PAGE: Pack Review (QA for published packs)
# ============================================================
elif page == "Pack Review":
    st.title("Pack Review")
    st.caption("QA workflow for published packs — listen to every sound, flag issues, track icon status.")

    pack_summaries = pack_builder.get_all_pack_review_summary()

    if not pack_summaries:
        st.info("No published packs found.")
    else:
        # Overview metrics
        total_packs = len(pack_summaries)
        total_sounds = sum(p["sound_count"] for p in pack_summaries)
        total_flagged = sum(p["flagged"] for p in pack_summaries)
        total_ok = sum(p["ok"] for p in pack_summaries)
        total_icons = sum(1 for p in pack_summaries if p["has_icon"])

        mcol1, mcol2, mcol3, mcol4, mcol5 = st.columns(5)
        mcol1.metric("Packs", total_packs)
        mcol2.metric("Sounds", total_sounds)
        mcol3.metric("Reviewed OK", total_ok)
        mcol4.metric("Flagged", total_flagged)
        mcol5.metric("Icons", f"{total_icons}/{total_packs}")

        if total_icons < total_packs:
            if st.button(f"Generate {total_packs - total_icons} missing icons"):
                results = icon_generator.generate_all_icons()
                st.success(f"Generated {len(results)} icons")
                st.rerun()

        st.markdown("---")

        # Pack selector
        pack_options = [f"{p['display_name']} ({p['name']})" for p in pack_summaries]
        pack_names = [p["name"] for p in pack_summaries]
        selected_idx = st.selectbox("Select pack", range(len(pack_options)),
                                     format_func=lambda i: pack_options[i])
        selected_pack_name = pack_names[selected_idx]

        # Load full pack details
        details = pack_builder.get_pack_details(selected_pack_name)
        if not details:
            st.error("Could not load pack details.")
        else:
            # Pack header
            hcol1, hcol2, hcol3 = st.columns([3, 1, 1])
            with hcol1:
                st.subheader(f"{details['display_name']}")
                st.caption(f"v{details['version']} — {details['description']}")
                if details["tags"]:
                    st.caption(f"Tags: {', '.join(details['tags'][:6])}")
            with hcol2:
                st.metric("Sounds", details["total_sounds"])
                st.metric("Categories", len(details["categories"]))
            with hcol3:
                if details["has_icon"]:
                    st.success("Icon: pack.png")
                    try:
                        st.image(details["icon_path"], width=64)
                    except Exception as e:
                        st.warning(f"Icon load failed: {e}")
                else:
                    st.warning("No icon")

            # Pack completion status banner
            pack_status = details.get("pack_status", "unreviewed")
            pending_fix = details.get("pending_fix", 0)
            if pack_status == "needs-work":
                st.error(f"NEEDS WORK — {pending_fix} sound(s) pending fix")
            elif pack_status == "ready-for-review":
                st.warning("Fixes applied — ready for re-review")
            elif pack_status == "complete":
                st.success("COMPLETE")
            elif details["reviewed_ok"] == details["total_sounds"] and details["total_sounds"] > 0:
                st.success("All sounds reviewed OK")

            # Review stats for this pack
            scol1, scol2, scol3, scol4 = st.columns(4)
            scol1.metric("OK", details["reviewed_ok"])
            scol2.metric("Flagged", details["flagged"])
            scol3.metric("Pending Fix", pending_fix)
            scol4.metric("Unreviewed", details["unreviewed"])

            # Batch actions
            bcol1, bcol2, bcol3, bcol4 = st.columns(4)
            with bcol1:
                if st.button("Mark all OK", type="primary"):
                    count = 0
                    for cat, sounds in details["categories"].items():
                        for s in sounds:
                            if s["review_status"] == "unreviewed":
                                pack_builder.save_pack_sound_review(
                                    selected_pack_name, s["file"], "ok")
                                count += 1
                    if count:
                        st.success(f"Marked {count} sounds OK")
                    st.rerun()
            with bcol2:
                if details["flagged"] > 0:
                    if st.button(f"🔧 Auto-fix {details['flagged']} flagged"):
                        results = pack_builder.auto_fix_flagged(selected_pack_name)
                        ok = [r for r in results if r.get("ok")]
                        fail = [r for r in results if not r.get("ok")]
                        if ok:
                            st.success(f"Fixed {len(ok)} sound(s) — trimmed silence, normalized volume")
                        if fail:
                            for r in fail:
                                st.error(f"Fix failed for {r.get('file', '?')}: {r.get('error', 'unknown')}")
                        st.rerun()
                else:
                    st.button("🔧 Auto-fix flagged", disabled=True, help="No flagged sounds")
            with bcol3:
                if pack_status == "ready-for-review":
                    if st.button("Mark complete"):
                        pack_builder.set_pack_status(selected_pack_name, "complete")
                        st.success("Pack marked complete!")
                        st.rerun()
                elif details["reviewed_ok"] == details["total_sounds"] and details["total_sounds"] > 0:
                    if st.button("Mark complete"):
                        pack_builder.set_pack_status(selected_pack_name, "complete")
                        st.success("Pack marked complete!")
                        st.rerun()
            with bcol4:
                if st.button("Clear all reviews"):
                    count = 0
                    for cat, sounds in details["categories"].items():
                        for s in sounds:
                            if s["review_status"] != "unreviewed":
                                pack_builder.save_pack_sound_review(
                                    selected_pack_name, s["file"], "unreviewed")
                                count += 1
                    pack_builder.set_pack_status(selected_pack_name, "unreviewed")
                    if count:
                        st.info(f"Cleared {count} reviews")
                    st.rerun()

            st.markdown("---")

            # --- Sound filter ---
            fcol1, fcol2 = st.columns([2, 1])
            with fcol1:
                sound_filter = st.selectbox("Show sounds", [
                    "All", "Needs attention", "Unreviewed", "Flagged only", "Pending fix", "OK only"
                ], key="pack_sound_filter")

            st.markdown("---")

            # Load clip library once for all add/replace operations
            clip_library = pack_builder.get_clip_library(exclude_pack=selected_pack_name)
            # Index: files already in this pack
            pack_files = set()
            for _cat, _sounds in details["categories"].items():
                for _s in _sounds:
                    pack_files.add(_s["file"])

            # Show ALL 7 CESP categories (including missing ones)
            all_cats_in_pack = set(details["categories"].keys())
            missing_cats = [c for c in pack_builder.CATEGORIES if c not in all_cats_in_pack]

            # Sound review by category
            for cat_idx, cat in enumerate(pack_builder.CATEGORIES):
                sounds = details["categories"].get(cat, [])
                cat_flagged = sum(1 for s in sounds if s["review_status"] in ("needs-update", "needs-fix"))
                cat_ok = sum(1 for s in sounds if s["review_status"] == "ok")
                cat_missing_files = sum(1 for s in sounds if not s["exists"])

                if not sounds:
                    cat_icon = "🚫"
                    cat_label = f"{cat_icon} {cat} — EMPTY (no sounds!)"
                elif cat_missing_files:
                    cat_icon = "💀"
                    cat_label = f"{cat_icon} {cat} — {len(sounds)} sounds ({cat_missing_files} MISSING FILES)"
                elif cat_flagged:
                    cat_icon = "🔴"
                    cat_label = f"{cat_icon} {cat} — {len(sounds)} sounds ({cat_ok} ok, {cat_flagged} flagged)"
                elif cat_ok == len(sounds):
                    cat_icon = "✅"
                    cat_label = f"{cat_icon} {cat} — {len(sounds)} sounds (all ok)"
                else:
                    cat_icon = "⬜"
                    cat_label = f"{cat_icon} {cat} — {len(sounds)} sounds ({cat_ok} ok)"

                # Filter sounds
                if sound_filter == "Needs attention":
                    filtered_sounds = [s for s in sounds if s["review_status"] not in ("ok",)]
                elif sound_filter == "Unreviewed":
                    filtered_sounds = [s for s in sounds if s["review_status"] == "unreviewed"]
                elif sound_filter == "Flagged only":
                    filtered_sounds = [s for s in sounds if s["review_status"] in ("needs-update", "needs-fix")]
                elif sound_filter == "Pending fix":
                    filtered_sounds = [s for s in sounds if s["review_status"] == "pending-fix"]
                elif sound_filter == "OK only":
                    filtered_sounds = [s for s in sounds if s["review_status"] == "ok"]
                else:
                    filtered_sounds = sounds

                # Skip categories only when they have sounds but all are filtered out
                if sounds and not filtered_sounds and sound_filter != "All":
                    continue

                should_expand = (not sounds) or cat_missing_files or (cat_ok < len(sounds))
                with st.expander(cat_label, expanded=should_expand):

                    # === EMPTY CATEGORY: big "add sound" prompt ===
                    if not sounds:
                        st.warning(f"This category has no sounds. Packs need all 7 CESP categories filled.")
                        # Show clips from library matching this category
                        matching = [c for c in clip_library if c["category"] == cat
                                    and c["clip_name"] + ".mp3" not in pack_files]
                        other = [c for c in clip_library if c["category"] != cat
                                 and c["clip_name"] + ".mp3" not in pack_files]

                        if matching:
                            st.caption(f"{len(matching)} approved clips already categorized as **{cat}**:")
                            options_matching = [
                                f"{c['clip_name']} — \"{c['label'][:50]}\" ({c['movie']}, {c['size_kb']}KB)"
                                for c in matching
                            ]
                            sel = st.selectbox(
                                f"Add clip to {cat}", options_matching,
                                key=f"add_empty_{cat}_{cat_idx}"
                            )
                            sel_idx = options_matching.index(sel) if sel else 0
                            sel_clip = matching[sel_idx]
                            # Preview audio
                            try:
                                with open(sel_clip["path"], "rb") as af:
                                    st.audio(af.read(), format="audio/mp3")
                            except Exception:
                                pass
                            if st.button(f"➕ Add to {cat}", key=f"add_btn_empty_{cat}_{cat_idx}",
                                         type="primary"):
                                result = pack_builder.add_pack_sound(
                                    selected_pack_name, cat, sel_clip["path"], sel_clip["label"])
                                if result.get("ok"):
                                    st.success(f"Added {sel_clip['clip_name']} to {cat}")
                                else:
                                    st.error(result.get("error", "Failed"))
                                st.rerun()

                        if other:
                            with st.popover(f"Browse all {len(other)} clips"):
                                st.caption("Clips from other categories (will be re-assigned)")
                                options_other = [
                                    f"{c['clip_name']} — \"{c['label'][:40]}\" [{c['category']}] ({c['movie']})"
                                    for c in other
                                ]
                                sel_o = st.selectbox(
                                    "Pick clip", options_other,
                                    key=f"add_other_{cat}_{cat_idx}"
                                )
                                sel_o_idx = options_other.index(sel_o) if sel_o else 0
                                sel_o_clip = other[sel_o_idx]
                                try:
                                    with open(sel_o_clip["path"], "rb") as af:
                                        st.audio(af.read(), format="audio/mp3")
                                except Exception:
                                    pass
                                if st.button(f"➕ Add to {cat}", key=f"add_other_btn_{cat}_{cat_idx}"):
                                    result = pack_builder.add_pack_sound(
                                        selected_pack_name, cat, sel_o_clip["path"], sel_o_clip["label"])
                                    if result.get("ok"):
                                        st.success(f"Added {sel_o_clip['clip_name']}")
                                    else:
                                        st.error(result.get("error", "Failed"))
                                    st.rerun()
                        continue  # skip sound iteration for empty categories

                    # === SOUND-BY-SOUND REVIEW ===
                    if not filtered_sounds:
                        st.caption("All sounds filtered out.")

                    for s_idx, sound in enumerate(filtered_sounds):
                        rev = sound["review_status"]
                        if rev == "ok":
                            s_icon = "✅"
                        elif rev == "pending-fix":
                            s_icon = "🔧"
                        elif rev == "needs-update":
                            s_icon = "🟡"
                        elif rev == "needs-fix":
                            s_icon = "🔴"
                        else:
                            s_icon = "⬜"

                        st.markdown(f"**{s_icon} {sound['label']}** — `{sound['file']}` ({sound['size_kb']} KB)")

                        acol1, acol2 = st.columns([3, 3])
                        with acol1:
                            if sound["exists"]:
                                try:
                                    with open(sound["path"], "rb") as f:
                                        audio_bytes = f.read()
                                    st.audio(audio_bytes, format="audio/mp3")
                                except Exception:
                                    st.warning("Audio load failed")
                            else:
                                st.error("File missing! Use Replace to swap in a working clip.")

                        with acol2:
                            key_base = f"pr_{selected_pack_name}_{cat_idx}_{s_idx}"
                            if rev == "pending-fix":
                                st.info("Previously fixed — listen and re-review")
                                rbtn1, rbtn2, rbtn3 = st.columns(3)
                                with rbtn1:
                                    if st.button("OK", key=f"ok_fix_{key_base}",
                                                 type="primary", help="Sound is good"):
                                        pack_builder.save_pack_sound_review(
                                            selected_pack_name, sound["file"], "ok")
                                        pack_builder.resolve_fix(
                                            selected_pack_name, sound["file"])
                                        pack_builder.save_pack_sound_review(
                                            selected_pack_name, sound["file"], "ok")
                                        st.rerun()
                                with rbtn2:
                                    if st.button("🔧 Re-fix", key=f"refix_{key_base}",
                                                 help="Try auto-fix again"):
                                        with st.spinner("Re-fixing audio..."):
                                            result = pack_builder.auto_fix_sound(
                                                selected_pack_name, sound["file"])
                                        if result.get("ok"):
                                            st.success("Re-fixed")
                                        else:
                                            st.error(f"Failed: {result.get('error')}")
                                        st.rerun()
                                with rbtn3:
                                    if st.button("Restore", key=f"restore_{key_base}",
                                                 help="Restore from backup"):
                                        restored = pack_builder.restore_backup(
                                            selected_pack_name, sound["file"])
                                        if restored:
                                            st.success("Restored original audio")
                                        else:
                                            st.warning("No backup found")
                                        st.rerun()
                            else:
                                btn1, btn2, btn3, btn4 = st.columns(4)
                                with btn1:
                                    if st.button("OK", key=f"ok_{key_base}",
                                                 type="primary" if rev != "ok" else "secondary"):
                                        pack_builder.save_pack_sound_review(
                                            selected_pack_name, sound["file"], "ok")
                                        st.rerun()
                                with btn2:
                                    if st.button("🚩 Flag", key=f"flag_{key_base}",
                                                 type="secondary" if rev not in ("needs-fix", "needs-update") else "primary",
                                                 help="Mark as bad — wrong quote, bad audio, or wrong category"):
                                        pack_builder.save_pack_sound_review(
                                            selected_pack_name, sound["file"], "needs-fix")
                                        st.rerun()
                                with btn3:
                                    if st.button("🔧 Fix", key=f"upd_{key_base}",
                                                 help="Auto-fix: trim silence, normalize volume"):
                                        with st.spinner("Fixing audio..."):
                                            result = pack_builder.auto_fix_sound(
                                                selected_pack_name, sound["file"])
                                        if result.get("ok"):
                                            old_kb = round(result["old_size"] / 1024, 1)
                                            new_kb = round(result["new_size"] / 1024, 1)
                                            st.success(
                                                f"Fixed: {old_kb} KB → {new_kb} KB")
                                        else:
                                            st.error(f"Fix failed: {result.get('error')}")
                                        st.rerun()
                                with btn4:
                                    if st.button("↩ Restore", key=f"fix_{key_base}",
                                                 help="Restore original audio from backup"):
                                        restored = pack_builder.restore_backup(
                                            selected_pack_name, sound["file"])
                                        if restored:
                                            st.success("Restored original audio")
                                        else:
                                            st.info("No backup to restore")
                                        st.rerun()

                            # --- Sound management: Replace / Remove / Move ---
                            mgmt_cols = st.columns(3)
                            with mgmt_cols[0]:
                                with st.popover("🔄 Replace"):
                                    st.caption("Swap this sound with a different clip")
                                    avail = [c for c in clip_library
                                             if c["clip_name"] + ".mp3" not in pack_files
                                             or c["clip_name"] + ".mp3" == sound["file"]]
                                    if avail:
                                        opts = [
                                            f"{c['clip_name']} — \"{c['label'][:40]}\" ({c['movie']})"
                                            for c in avail
                                        ]
                                        pick = st.selectbox("Replacement", opts,
                                                            key=f"repl_{key_base}")
                                        pick_idx = opts.index(pick) if pick else 0
                                        pick_clip = avail[pick_idx]
                                        try:
                                            with open(pick_clip["path"], "rb") as af:
                                                st.audio(af.read(), format="audio/mp3")
                                        except Exception:
                                            pass
                                        st.caption(f"Category: {pick_clip['category']} | {pick_clip['size_kb']}KB")
                                        if st.button("Confirm replace", key=f"repl_go_{key_base}",
                                                     type="primary"):
                                            result = pack_builder.replace_pack_sound(
                                                selected_pack_name, cat, sound["file"],
                                                pick_clip["path"], pick_clip["label"])
                                            if result.get("ok"):
                                                st.success(f"Replaced with {pick_clip['clip_name']}")
                                            else:
                                                st.error(result.get("error", "Failed"))
                                            st.rerun()
                                    else:
                                        st.info("No replacement clips available")
                            with mgmt_cols[1]:
                                with st.popover("🗑️ Remove"):
                                    st.warning(f"Remove **{sound['file']}** from this pack?")
                                    st.caption("Audio is backed up, not deleted forever.")
                                    if st.button("Yes, remove it", key=f"rm_{key_base}",
                                                 type="primary"):
                                        result = pack_builder.remove_pack_sound(
                                            selected_pack_name, cat, sound["file"])
                                        if result.get("ok"):
                                            st.success(f"Removed {sound['file']}")
                                        else:
                                            st.error(result.get("error", "Failed"))
                                        st.rerun()
                            with mgmt_cols[2]:
                                other_cats = [c for c in pack_builder.CATEGORIES if c != cat]
                                with st.popover("➡️ Move"):
                                    st.caption(f"Move from **{cat}** to:")
                                    dest_cat = st.selectbox("Destination", other_cats,
                                                            key=f"mv_{key_base}")
                                    if st.button("Move", key=f"mv_go_{key_base}",
                                                 type="primary"):
                                        result = pack_builder.move_pack_sound(
                                            selected_pack_name, sound["file"], cat, dest_cat)
                                        if result.get("ok"):
                                            st.success(f"Moved to {dest_cat}")
                                        else:
                                            st.error(result.get("error", "Failed"))
                                        st.rerun()

                            note = st.text_input(
                                "Note", value=sound["review_notes"],
                                key=f"note_{key_base}",
                                placeholder="What needs fixing?"
                            )
                            if note != sound["review_notes"] and st.button(
                                "Save note", key=f"sn_{key_base}"
                            ):
                                pack_builder.save_pack_sound_review(
                                    selected_pack_name, sound["file"],
                                    sound["review_status"] if sound["review_status"] != "unreviewed" else "needs-update",
                                    note
                                )
                                st.rerun()

                        if s_idx < len(filtered_sounds) - 1:
                            st.markdown("---")

                    # === ADD CLIP TO THIS CATEGORY (at bottom of category) ===
                    st.markdown("---")
                    avail_for_cat = [c for c in clip_library
                                     if c["clip_name"] + ".mp3" not in pack_files]
                    # Show clips matching this category first, then others
                    matching_cat = [c for c in avail_for_cat if c["category"] == cat]
                    other_cat = [c for c in avail_for_cat if c["category"] != cat]
                    all_for_add = matching_cat + other_cat

                    if all_for_add:
                        with st.popover(f"➕ Add clip to {cat}"):
                            opts_add = []
                            for c in all_for_add:
                                tag = f" [{c['category']}]" if c["category"] != cat else ""
                                opts_add.append(
                                    f"{c['clip_name']} — \"{c['label'][:40]}\"{tag} ({c['movie']})"
                                )
                            pick_add = st.selectbox("Clip", opts_add,
                                                    key=f"add_cat_{cat}_{cat_idx}")
                            pick_add_idx = opts_add.index(pick_add) if pick_add else 0
                            pick_add_clip = all_for_add[pick_add_idx]
                            try:
                                with open(pick_add_clip["path"], "rb") as af:
                                    st.audio(af.read(), format="audio/mp3")
                            except Exception:
                                pass
                            st.caption(f"From: {pick_add_clip['movie']} | {pick_add_clip['size_kb']}KB")
                            if st.button("➕ Add", key=f"add_go_{cat}_{cat_idx}",
                                         type="primary"):
                                result = pack_builder.add_pack_sound(
                                    selected_pack_name, cat,
                                    pick_add_clip["path"], pick_add_clip["label"])
                                if result.get("ok"):
                                    st.success(f"Added {pick_add_clip['clip_name']}")
                                else:
                                    st.error(result.get("error", "Failed"))
                                st.rerun()

            # --- Icon management section ---
            st.markdown("---")
            st.subheader("Pack Icon")
            st.caption("Registry spec: 256x256 PNG, max 500KB, stored in icons/pack.png")

            if details["has_icon"]:
                icol1, icol2 = st.columns([1, 3])
                with icol1:
                    try:
                        st.image(details["icon_path"], width=128)
                    except Exception:
                        st.warning("Could not display icon")
                with icol2:
                    icon_size = os.path.getsize(details["icon_path"])
                    st.success(f"Icon exists: {icon_size // 1024} KB")
                    if icon_size > 500 * 1024:
                        st.warning("Exceeds 500KB limit!")
                    if st.button("Regenerate icon", key=f"regen_icon_{selected_pack_name}"):
                        result = icon_generator.generate_and_save_icon(selected_pack_name)
                        if "error" in result:
                            st.error(result["error"])
                        else:
                            st.success(f"Regenerated: {result['size_kb']}KB")
                        st.rerun()
            else:
                st.info("No icon yet. Generate one or upload a PNG below.")
                if st.button("Generate icon", key=f"gen_icon_{selected_pack_name}",
                             type="primary"):
                    result = icon_generator.generate_and_save_icon(selected_pack_name)
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.success(f"Generated: {result['size_kb']}KB")
                    st.rerun()

            uploaded = st.file_uploader(
                "Upload pack icon (PNG, 256x256, max 500KB)",
                type=["png"],
                key=f"icon_upload_{selected_pack_name}"
            )
            if uploaded:
                if uploaded.size > 500 * 1024:
                    st.error(f"File too large: {uploaded.size // 1024}KB (max 500KB)")
                else:
                    icon_dir = os.path.join(details["dir"], "icons")
                    os.makedirs(icon_dir, exist_ok=True)
                    icon_dest = os.path.join(icon_dir, "pack.png")
                    with open(icon_dest, "wb") as f:
                        f.write(uploaded.read())
                    st.success(f"Saved icon to {icon_dest}")
                    st.rerun()


# ============================================================
# PAGE: Pack Designer
# ============================================================
elif page == "Pack Designer":
    st.title("Pack Designer")

    # Show movies with approved clips
    movies_with_approved = [s["name"] for s in scripts if s["approved"] > 0]

    if not movies_with_approved:
        st.info("No movies have approved clips yet. Go to Clip Review first.")
    else:
        # Saved drafts indicator
        drafts = pack_builder.list_drafts()
        if drafts:
            st.caption(f"{len(drafts)} saved draft(s): {', '.join(d['name'] for d in drafts)}")

        selected = st.selectbox("Source movie", movies_with_approved, key="build_movie")

        if selected:
            approved = pack_builder.get_approved_clips(selected)
            st.caption(f"{len(approved)} approved clips with categories")

            # Show category assignments compactly
            st.subheader("Category Assignments")
            by_cat = {}
            for c in approved:
                cat = c["category"]
                if cat not in by_cat:
                    by_cat[cat] = []
                by_cat[cat].append(c["name"])

            all_filled = True
            for cat in pack_builder.CATEGORIES:
                clips_in_cat = by_cat.get(cat, [])
                icon = "✅" if clips_in_cat else "⬜"
                if not clips_in_cat:
                    all_filled = False
                st.markdown(f"{icon} **{cat}** — {len(clips_in_cat)} clips: {', '.join(clips_in_cat) if clips_in_cat else 'none'}")

            if not all_filled:
                st.warning("Some categories are empty. Go to Clip Review to assign clips to all 7 categories.")

            st.markdown("---")

            # Load draft or generate placeholder
            draft = pack_builder.load_draft(selected)
            placeholder = pack_builder.generate_placeholder(selected)

            # Use draft values if saved, otherwise placeholder
            default_pack_name = draft.get("pack_name", placeholder["pack_name"]) if draft else placeholder["pack_name"]
            default_display = draft.get("display_name", placeholder["display_name"]) if draft else placeholder["display_name"]
            default_desc = draft.get("description", placeholder["description"]) if draft else placeholder["description"]
            default_tags = draft.get("tags", placeholder["tags"]) if draft else placeholder["tags"]

            # Build form
            st.subheader("Build Pack")
            if draft:
                st.caption("Loaded from saved draft")

            pack_name = st.text_input("Pack name (slug)", value=default_pack_name,
                                      key=f"pn_{selected}")
            display_name = st.text_input("Display name", value=default_display,
                                         key=f"dn_{selected}")
            description = st.text_area("Description", value=default_desc,
                                       key=f"desc_{selected}", height=80)
            tags_input = st.text_input("Tags (comma-separated)",
                                       value=", ".join(default_tags),
                                       key=f"tags_{selected}")
            tags = [t.strip() for t in tags_input.split(",") if t.strip()]

            # Action buttons
            dcol1, dcol2, dcol3, dcol4 = st.columns(4)
            with dcol1:
                if st.button("💾 Save Draft", key=f"save_{selected}"):
                    pack_builder.save_draft(selected, {
                        "pack_name": pack_name,
                        "display_name": display_name,
                        "description": description,
                        "tags": tags,
                        "movie": selected,
                        "clip_names": [c["name"] for c in approved],
                    })
                    st.success("Draft saved")

            with dcol2:
                if st.button("Preview Manifest", key=f"preview_{selected}"):
                    manifest = pack_builder.preview_manifest(
                        pack_name, display_name, description, selected, tags
                    )
                    if manifest:
                        st.json(manifest)
                    else:
                        st.warning("No approved clips with categories found")

            # Detect existing pack
            existing_pack_dir = os.path.join(
                os.path.expanduser("~/dev/openpeon-movie-packs"), pack_name
            )
            pack_exists = os.path.exists(
                os.path.join(existing_pack_dir, "openpeon.json")
            )
            build_label = "🔄 Update Pack" if pack_exists else "🏗️ Build Pack"
            if pack_exists:
                st.info(f"Pack **{pack_name}** already exists — Build will merge new clips into it.")

            with dcol3:
                if st.button(build_label, type="primary", key=f"build_{selected}"):
                    # Auto-save draft before building
                    pack_builder.save_draft(selected, {
                        "pack_name": pack_name,
                        "display_name": display_name,
                        "description": description,
                        "tags": tags,
                        "movie": selected,
                        "clip_names": [c["name"] for c in approved],
                    })
                    result = pack_builder.build_pack(
                        pack_name, display_name, description, selected, tags
                    )
                    if "error" in result:
                        st.error(result["error"])
                    else:
                        st.success(
                            f"{result['status'].capitalize()}: {result['sounds']} sounds, "
                            f"{result['size_bytes']//1024}KB, "
                            f"{result['categories']} categories"
                        )
                        if st.button("📤 Publish to Registry", key=f"quick_pub_{selected}"):
                            with st.spinner(f"Publishing {pack_name}..."):
                                pub_result = pack_builder.publish_pack(pack_name)
                            if pub_result.get("ok"):
                                msg = pub_result["message"]
                                url = pub_result.get("commit_url", "")
                                if url:
                                    st.success(f"{msg} — [view commit]({url})")
                                else:
                                    st.success(msg)
                            else:
                                st.error(pub_result["error"])

            with dcol4:
                if st.button("🔄 Reset", key=f"reset_{selected}",
                             help="Reset to auto-generated placeholder"):
                    pack_builder.save_draft(selected, {
                        "pack_name": placeholder["pack_name"],
                        "display_name": placeholder["display_name"],
                        "description": placeholder["description"],
                        "tags": placeholder["tags"],
                        "movie": selected,
                    })
                    st.rerun()

    st.markdown("---")

    # Published packs
    published = pack_builder.get_published_packs()
    st.subheader(f"Published Packs ({len(published)})")
    if published:
        for p in published:
            st.markdown(
                f"- **{p['display_name']}** v{p['version']} — "
                f"{p['sound_count']} sounds — {', '.join(p['tags'][:4])}"
            )

    # ---- Publish to Registry ----
    st.markdown("---")
    st.subheader("Publish to Registry")
    st.caption("Commit and push pack changes to the GitHub registry.")

    unpublished = pack_builder.get_unpublished_packs()

    if not unpublished:
        st.success("All packs are up to date with the registry.")
    else:
        st.warning(f"{len(unpublished)} pack(s) have unpublished changes")

        # Batch publish button
        if len(unpublished) > 1:
            if st.button(f"📤 Publish all {len(unpublished)} packs", type="primary",
                         key="publish_all"):
                with st.spinner("Publishing all packs..."):
                    results = pack_builder.publish_all_packs()
                ok_results = [r for r in results if r.get("ok")]
                fail_results = [r for r in results if not r.get("ok")]
                if ok_results:
                    names = ", ".join(r["display_name"] for r in ok_results)
                    last_url = next((r.get("commit_url", "") for r in reversed(ok_results) if r.get("commit_url")), "")
                    if last_url:
                        st.success(f"Published {len(ok_results)} pack(s): {names} — [view commits]({last_url})")
                    else:
                        st.success(f"Published {len(ok_results)} pack(s): {names}")
                for r in fail_results:
                    st.error(f"Failed: {r.get('pack_name', '?')} — {r.get('error', 'unknown')}")
                st.rerun()

        # Individual pack rows
        for pack in unpublished:
            pcol1, pcol2, pcol3 = st.columns([3, 1, 1])
            with pcol1:
                status_icon = "🆕" if pack["is_new"] else "📝"
                st.markdown(
                    f"{status_icon} **{pack['display_name']}** v{pack['version']} "
                    f"— {pack['files_changed']} file(s) changed"
                )
            with pcol2:
                status_label = "New pack" if pack["is_new"] else "Modified"
                st.caption(status_label)
            with pcol3:
                if st.button("Publish", key=f"publish_{pack['name']}"):
                    with st.spinner(f"Publishing {pack['display_name']}..."):
                        pub_result = pack_builder.publish_pack(pack["name"])
                    if pub_result.get("ok"):
                        url = pub_result.get("commit_url", "")
                        if url:
                            st.success(f"{pub_result['message']} — [view commit]({url})")
                        else:
                            st.success(pub_result["message"])
                    else:
                        st.error(pub_result["error"])
                    st.rerun()

    # ---- Register in PeonPing Registry ----
    st.markdown("---")
    st.subheader("Register in PeonPing Registry")
    st.caption("Create a PR to PeonPing/registry to list packs in the official index.")

    registry_status = pack_builder.get_registry_status()
    unregistered = [
        (name, info) for name, info in registry_status.items()
        if not info["registered"]
    ]
    registered = [
        (name, info) for name, info in registry_status.items()
        if info["registered"]
    ]

    if registered:
        with st.expander(f"Already registered ({len(registered)})"):
            for name, info in sorted(registered):
                st.markdown(f"- **{name}** — registry v{info['registry_version']}")

    if not unregistered:
        st.success("All published packs are registered in PeonPing/registry.")
    else:
        st.warning(f"{len(unregistered)} pack(s) not yet in PeonPing registry")

        # Source ref (tag) selector
        try:
            tag_result = subprocess.run(
                ["git", "tag", "-l", "--sort=-v:refname"],
                capture_output=True, text=True, timeout=5,
                cwd=pack_builder.PACKS_DIR,
            )
            tags = [t.strip() for t in tag_result.stdout.strip().splitlines() if t.strip()]
        except Exception:
            tags = []

        source_ref = st.selectbox(
            "Source tag (source_ref)", tags if tags else ["v1.0.0"],
            help="Git tag on MattBillock/openpeon-movie-packs that CI will validate against"
        )

        # Batch register
        unreg_names = [name for name, _ in unregistered]
        if len(unregistered) > 1:
            if st.button(f"Register all {len(unregistered)} packs", type="primary",
                         key="register_all"):
                with st.spinner("Creating registry PR..."):
                    result = pack_builder.register_all_packs(source_ref, unreg_names)
                if result.get("ok"):
                    pr_url = result.get("pr_url", "")
                    if pr_url:
                        st.success(f"PR created: [{pr_url}]({pr_url})")
                    else:
                        st.success(result.get("message", "Done"))
                else:
                    st.error(result["error"])
                st.rerun()

        for name, info in sorted(unregistered):
            rcol1, rcol2 = st.columns([4, 1])
            with rcol1:
                st.markdown(f"**{name}** — not in registry")
            with rcol2:
                if st.button("Register", key=f"reg_{name}"):
                    with st.spinner(f"Registering {name}..."):
                        result = pack_builder.register_pack(name, source_ref)
                    if result.get("ok"):
                        pr_url = result.get("pr_url", "")
                        if pr_url:
                            st.success(f"PR created: [{pr_url}]({pr_url})")
                        else:
                            st.success(result.get("message", "Registered"))
                    else:
                        st.error(result["error"])
                    st.rerun()


# ============================================================
# PAGE: Pack Status
# ============================================================
elif page == "Pack Status":
    st.title("Pack Status")

    # Dynamic view from published packs and review summaries
    review_summary = pack_builder.get_all_pack_review_summary()
    published = pack_builder.get_published_packs()
    published_names = {p["name"] for p in published}

    # Also check which movies have extraction scripts
    existing_scripts = set(extraction.get_all_movie_names())

    if review_summary:
        for pack in review_summary:
            name = pack["name"]
            display = pack["display_name"]
            sounds = pack["sound_count"]
            status = pack["pack_status"]
            flagged = pack["flagged"]
            ok_count = pack["ok"]

            if status == "approved":
                icon = "✅"
            elif flagged > 0:
                icon = "🔧"
            elif ok_count > 0:
                icon = "🔄"
            else:
                icon = "⬜"

            st.markdown(f"{icon} **{name}** — {display} ({sounds} sounds, status: {status})")
    elif published:
        for p in published:
            st.markdown(f"✅ **{p['name']}** — {p['display_name']} ({p['sound_count']} sounds)")
    else:
        st.info("No packs published yet. Build packs from the Pack Builder page.")

    if existing_scripts:
        st.markdown("---")
        st.subheader("Movies with extraction scripts")
        for name in sorted(existing_scripts):
            in_packs = name in published_names or any(name in p for p in published_names)
            icon = "✅" if in_packs else "🔄"
            st.markdown(f"{icon} {name}")

    st.markdown("---")
    st.subheader("Legend")
    st.markdown("✅ Published/Approved | 🔧 Needs fixes | 🔄 In progress | ⬜ Not started")


# ============================================================
# PAGE: Media Library
# ============================================================
elif page == "Media Library":
    st.title("Media Library")

    # Service status row
    svc_cols = st.columns(3)
    for col, (svc_key, svc_icon) in zip(svc_cols, [("movie", "🎬"), ("tv", "📺"), ("music", "🎵")]):
        svc = media_client.SERVICES[svc_key]
        with col:
            if media_client.is_available(svc_key):
                status = media_client.get_status(svc_key)
                if isinstance(status, dict) and "error" not in status:
                    st.success(f"{svc_icon} {svc['name']} v{status.get('version', '?')}")
                else:
                    st.error(f"{svc_icon} {svc['name']} offline")
            else:
                st.warning(f"{svc_icon} {svc['name']} not configured")

    st.markdown("---")

    # ---- Quick Add (the box) ----
    st.subheader("Quick Add")
    st.caption("Type a name, pick from results, it gets added to your library + extraction pipeline.")

    ml_tab1, ml_tab2, ml_tab3 = st.tabs(["🎬 Movie", "📺 TV Show", "🎵 Music"])

    for tab, svc_key, svc_label, placeholder in [
        (ml_tab1, "movie", "Radarr", "Search for a movie"),
        (ml_tab2, "tv", "Sonarr", "Search for a show"),
        (ml_tab3, "music", "Lidarr", "Search for an artist"),
    ]:
        with tab:
            if not media_client.is_available(svc_key):
                st.warning(f"{svc_label} not configured — add API key to ~/.openpeon/.env")
                continue

            search_term = st.text_input(
                f"Search {svc_label}",
                placeholder=placeholder,
                key=f"ml_search_{svc_key}",
            )

            if search_term:
                results = media_client.search(svc_key, search_term)
                if isinstance(results, dict) and "error" in results:
                    st.error(f"{svc_label} error: {results['error']}")
                elif not results:
                    st.info("No results found")
                else:
                    for i, r in enumerate(results[:8]):
                        col_poster, col_info, col_btn = st.columns([1, 4, 1])
                        with col_poster:
                            if r.get("poster_url"):
                                st.image(r["poster_url"], width=60)
                            else:
                                st.markdown("🎬" if svc_key == "movie" else "📺" if svc_key == "tv" else "🎵")
                        with col_info:
                            year_str = f" ({r['year']})" if r.get("year") else ""
                            st.markdown(f"**{r['title']}**{year_str}")
                            if r.get("overview"):
                                st.caption(r["overview"][:150] + ("..." if len(r.get("overview", "")) > 150 else ""))
                        with col_btn:
                            if r.get("already_added"):
                                st.markdown("✅ Added")
                            else:
                                if st.button("➕ Add", key=f"ml_add_{svc_key}_{i}", type="primary"):
                                    with st.spinner(f"Adding to {svc_label}..."):
                                        qa_result = media_client.quick_add(svc_key, r)

                                    lib = qa_result.get("library_result", {})
                                    if qa_result.get("library_already_existed"):
                                        st.info(f"Already in {svc_label}: {qa_result['title']}")
                                    elif isinstance(lib, dict) and "error" in lib:
                                        st.error(f"{svc_label}: {lib['error'][:200]}")
                                    else:
                                        st.success(f"Added to {svc_label}: {qa_result['title']}")

                                    batch = qa_result.get("batch_result")
                                    if batch:
                                        if batch.get("already_exists"):
                                            st.info(f"Extraction batch exists: {batch.get('slug', '')}")
                                        elif batch.get("ok"):
                                            st.success("Extraction batch created!")
                                        elif batch.get("error"):
                                            st.error(f"Quote generation failed: {batch['error'][:200]}")
                                            st.caption("Use 'Retry Quotes' in Pipeline Targets below to try again.")

    # ---- Download Queue ----
    st.markdown("---")
    st.subheader("Download Queue")
    queue = radarr_client.get_queue()
    if isinstance(queue, dict) and "error" not in queue:
        records = queue.get("records", [])
        if records:
            queue_data = []
            for rec in records:
                movie = rec.get("movie", {})
                size = rec.get("size", 1)
                left = rec.get("sizeleft", 0)
                pct = (1 - left / max(size, 1)) * 100
                queue_data.append({
                    "Title": movie.get("title", rec.get("title", "Unknown")),
                    "Status": rec.get("status", "?"),
                    "Progress": f"{pct:.0f}%",
                })
            st.dataframe(queue_data, use_container_width=True, hide_index=True)
        else:
            st.info("No active downloads")
    else:
        st.warning("Could not fetch queue")

    # ---- Pipeline movie library ----
    st.markdown("---")
    st.subheader("Pipeline Targets")
    summary = radarr_client.get_movie_status_summary()
    if "error" not in summary:
        # Build extraction status index
        _script_names = set(extraction.get_all_movie_names())
        _script_data = {s["name"]: s for s in scripts}

        # Show ALL movies in Radarr with extraction status
        all_movies = []
        movies_needing_quotes = []
        for m in summary["movies"]:
            status_emoji = "🟢" if m["has_file"] else "🔴"
            slug = extraction.slugify(m["title"])

            # Determine extraction script status
            if slug in _script_names:
                clip_count = _script_data.get(slug, {}).get("total_clips", 0)
                if clip_count > 0:
                    ext_status = f"✅ {clip_count} quotes"
                else:
                    ext_status = "⚠️ Empty script"
                    movies_needing_quotes.append(m)
            else:
                ext_status = "❌ No script"
                movies_needing_quotes.append(m)

            all_movies.append({
                "": status_emoji,
                "Title": f"{m['title']} ({m['year']})",
                "Downloaded": "Yes" if m["has_file"] else "No",
                "Size (GB)": m["size_gb"],
                "Extraction": ext_status,
            })
        if all_movies:
            st.dataframe(all_movies, use_container_width=True, hide_index=True)
        else:
            st.info("No movies in Radarr")

        # Movies needing quote generation
        if movies_needing_quotes:
            st.markdown("---")
            st.subheader("Movies Needing Quote Generation")
            st.caption("These movies have no extraction script or empty scripts.")
            for mi, m in enumerate(movies_needing_quotes):
                mcol1, mcol2 = st.columns([4, 1])
                with mcol1:
                    st.markdown(f"**{m['title']}** ({m['year']})")
                with mcol2:
                    if st.button("🔄 Retry Quotes", key=f"retry_quotes_{mi}"):
                        with st.spinner(f"Generating quotes for {m['title']}..."):
                            result = media_client.retry_quote_generation(
                                m["title"], m["year"])
                        if isinstance(result, dict) and result.get("ok"):
                            clip_count = result.get("clip_count", 0)
                            st.success(f"Generated {clip_count} quotes for {m['title']}!")
                            st.rerun()
                        elif isinstance(result, dict) and result.get("error"):
                            st.error(f"Failed: {result['error'][:200]}")
                        elif isinstance(result, dict) and result.get("message"):
                            st.info(result["message"])
                        else:
                            st.error("Unknown error")


# --- Auto-refresh removed ---
# Previously used HTML meta-refresh which caused full page reloads every 30s,
# destroying interactive state. Use the sidebar "Refresh" button instead.
