"""OpenPeon Pipeline Dashboard — Streamlit App.

Self-sufficient management UI for the OpenPeon movie quote extraction pipeline.
Handles extraction control, STT verification review, pack building, and monitoring.
"""
import logging
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
import radarr_client
import pack_builder
import icon_generator

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
page = st.sidebar.radio("Navigate", [
    "Overview",
    "Extraction Control",
    "Clip Review",
    "Pack Review",
    "Pack Designer",
    "Pack Status",
    "Radarr",
])

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
st.sidebar.caption("Use Refresh button to update")


# ============================================================
# PAGE: Overview
# ============================================================
if page == "Overview":
    st.title("Pipeline Overview")

    published = pack_builder.get_published_packs()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Movies", len(scripts))
    col2.metric("Running", running)
    col3.metric("Clips Extracted", f"{total_extracted}/{total_clips}")
    col4.metric("STT Verified", total_verified)
    col5.metric("Published Packs", len(published))

    st.markdown("---")

    # Extraction progress table
    st.subheader("Extraction Progress")
    for s in scripts:
        if s["is_running"]:
            icon = "🔄"
        elif s["extracted_count"] >= s["total_clips"] and s["total_clips"] > 0:
            icon = "✅"
        elif s["extracted_count"] > 0:
            icon = "⏸️"
        else:
            icon = "⬜"

        pct = (s["extracted_count"] / s["total_clips"]) if s["total_clips"] > 0 else 0

        cols = st.columns([2, 3, 1, 1, 1, 1])
        cols[0].markdown(f"{icon} **{s['name']}**")
        cols[1].progress(min(pct, 1.0))
        cols[2].caption(f"{s['extracted_count']}/{s['total_clips']}")
        cols[3].caption(f"✅ {s['verified']}")
        cols[4].caption(f"👁️ {s['needs_review']}")
        cols[5].caption(f"👍 {s['approved']}")

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

    # Batch actions
    st.subheader("Batch Actions")
    bcol1, bcol2, bcol3 = st.columns(3)
    with bcol1:
        if st.button("Start ALL idle", type="primary"):
            started = 0
            for s in scripts:
                if not s["is_running"] and s["extracted_count"] < s["total_clips"]:
                    extraction.start_extraction(s["name"])
                    started += 1
            st.success(f"Started {started} extractions")
            st.rerun()
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
        # D-drive mount check
        d_drive = os.path.exists("/Volumes/D-drive-music/Movies")
        if d_drive:
            st.success("D-drive mounted")
        else:
            st.error("D-drive NOT mounted!")

    st.markdown("---")

    # Per-movie controls
    for s in scripts:
        icon = "🔄" if s["is_running"] else ("✅" if s["verified"] == s["total_clips"] and s["total_clips"] > 0 else "⏸️")

        with st.expander(
            f"{icon} {s['name']} — {s['extracted_count']}/{s['total_clips']} extracted, "
            f"{s['verified']} verified, {s['needs_review']} review, {s['failed']} failed",
            expanded=s["is_running"]
        ):
            # Controls
            ctrl1, ctrl2, ctrl3, ctrl4 = st.columns(4)
            with ctrl1:
                if s["is_running"]:
                    if st.button(f"Stop", key=f"stop_{s['name']}"):
                        extraction.stop_extraction(s["name"])
                        st.rerun()
                else:
                    if st.button(f"Start", key=f"start_{s['name']}", type="primary"):
                        extraction.start_extraction(s["name"])
                        st.rerun()
            with ctrl2:
                if not s["is_running"]:
                    if st.button("Force restart", key=f"force_{s['name']}"):
                        extraction.stop_extraction(s["name"])
                        extraction.start_extraction(s["name"])
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

            # Console log
            log_text = extraction.get_extraction_log(s["name"], tail=30)
            if log_text:
                with st.expander("Console log (last 30 lines)"):
                    st.code(log_text, language="text")

    # ---- Add Movie / Add Clips section ----
    st.markdown("---")
    st.subheader("Add Movie")

    add_tab1, add_tab2 = st.tabs(["New Movie", "Add Clips to Existing"])

    with add_tab1:
        # ---- New Movie ----
        acol1, acol2 = st.columns(2)
        with acol1:
            new_movie_name = st.text_input("Movie slug", placeholder="baseketball", help="Lowercase, no spaces (e.g. 'baseketball', 'spacejam')")
        with acol2:
            new_movie_title = st.text_input("Display title", placeholder="BASEketball (1998)")

        # MKV finder
        mkv_search = st.text_input("Search D-drive for MKV", placeholder="Type movie name to search...", key="mkv_search")
        mkv_path_manual = ""
        if mkv_search:
            mkv_results = extraction.find_mkv_files(mkv_search)
            if mkv_results:
                mkv_options = [f"{r['dir_name']} — {r['size_gb']}GB" for r in mkv_results]
                mkv_choice = st.selectbox("Select MKV", mkv_options, key="mkv_select")
                idx = mkv_options.index(mkv_choice)
                mkv_path_manual = mkv_results[idx]["mkv_path"]
                st.caption(f"`{mkv_path_manual}`")
            else:
                st.info(f"No MKV found matching '{mkv_search}' — you can enter the path manually below or add via Radarr")

        mkv_path_override = st.text_input("MKV path (manual override)", value=mkv_path_manual, key="mkv_path_manual",
                                          help="Full path to MKV file. Leave empty to add later.")
        audio_stream = st.text_input("Audio stream", value="0:1", help="ffmpeg audio stream index")

        # Quotes textarea — paste multiple at once
        st.caption("Paste initial quotes (one per line): `clip_name | timestamp_seconds | quote text | duration`")
        st.caption("Example: `yippee_ki_yay | 3600 | Yippee-ki-yay, motherfucker. | 3`")
        quotes_text = st.text_area("Quotes (optional — can add later)", height=150, key="new_movie_quotes",
                                   placeholder="clip_name | timestamp | quote text | duration\nclip_name | timestamp | quote text | duration")

        if st.button("Create Movie", type="primary", key="create_movie_btn"):
            if not new_movie_name:
                st.error("Movie slug is required")
            elif not new_movie_title:
                st.error("Display title is required")
            else:
                slug = extraction.slugify(new_movie_name)
                mkv = mkv_path_override or f"/Volumes/D-drive-music/Movies/{new_movie_title}/{new_movie_title} Remux-1080p.mkv"

                # Parse quotes
                clips = []
                if quotes_text.strip():
                    for line in quotes_text.strip().split("\n"):
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

                result = extraction.create_movie_script(slug, new_movie_title, mkv, audio_stream, clips or None)
                if result.get("ok"):
                    st.success(f"Created extract_{slug}.py with {len(clips)} clips!")
                    st.rerun()
                else:
                    st.error(result.get("error", "Unknown error"))

    with add_tab2:
        # ---- Add Clips to Existing ----
        existing_names = [s["name"] for s in scripts]
        if not existing_names:
            st.info("No movies yet. Create one in the 'New Movie' tab first.")
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
                    # Auto-suggest category
                    suggestions = extraction.suggest_category(
                        clip.get("expected_quote", ""), clip["name"]
                    )
                    suggested_cat = suggestions[0][0] if suggestions else ""
                    current_cat = clip.get("category", "") or suggested_cat

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
                            if (clip["has_mp3"] or ext_status == "failed") and st.button("🔄", key=f"qe_{clip['name']}_{i}"):
                                extraction.retry_clip(selected_movie, clip["name"])
                                st.info(f"Re-extracting {clip['name']}")

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
                        # Category suggestion
                        suggestions = extraction.suggest_category(
                            clip.get("expected_quote", ""), clip["name"]
                        )
                        suggested_cat = suggestions[0][0] if suggestions else ""

                        # Default to saved category, then suggestion
                        default_cat = clip["category"] if clip["category"] else suggested_cat
                        default_idx = categories.index(default_cat) if default_cat in categories else 0

                        new_cat = st.selectbox(
                            "Category",
                            categories,
                            index=default_idx,
                            key=f"cat_{clip['name']}_{i}"
                        )

                        # Show suggestion hint if no category set yet
                        if not clip["category"] and suggestions:
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
            sound_filter = st.selectbox("Show sounds", [
                "All", "Needs attention", "Unreviewed", "Flagged only", "Pending fix", "OK only"
            ], key="pack_sound_filter")

            st.markdown("---")

            # Sound review by category
            for cat_idx, (cat, sounds) in enumerate(details["categories"].items()):
                cat_flagged = sum(1 for s in sounds if s["review_status"] in ("needs-update", "needs-fix"))
                cat_ok = sum(1 for s in sounds if s["review_status"] == "ok")
                cat_unreviewed = sum(1 for s in sounds if s["review_status"] == "unreviewed")
                cat_icon = "🔴" if cat_flagged else ("✅" if cat_ok == len(sounds) else "⬜")

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

                # Skip empty categories when filtering
                if not filtered_sounds and sound_filter != "All":
                    continue

                with st.expander(
                    f"{cat_icon} {cat} — {len(sounds)} sounds ({cat_ok} ok, {cat_flagged} flagged)",
                    expanded=(cat_ok < len(sounds))
                ):
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
                                st.error("File missing!")

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

            with dcol3:
                if st.button("Build Pack", type="primary", key=f"build_{selected}"):
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
                            f"Built: {result['sounds']} sounds, "
                            f"{result['size_bytes']//1024}KB, "
                            f"{result['categories']} categories"
                        )

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


# ============================================================
# PAGE: Pack Status
# ============================================================
elif page == "Pack Status":
    st.title("Pack Status — Designed Packs")
    st.caption("20 movie packs designed across 7 movies per the plan.")

    # Load the plan to show pack designs
    plan_path = os.path.expanduser("~/.claude/plans/sunny-toasting-snowglobe.md")
    packs_designed = [
        ("lebowski_the_dude", "The Dude", "The Big Lebowski"),
        ("lebowski_walter", "Walter Sobchak", "The Big Lebowski"),
        ("lebowski_jesus", "Jesus Quintana", "The Big Lebowski"),
        ("lebowski_maude", "Maude Lebowski", "The Big Lebowski"),
        ("lebowski_big_lebowski", "The Big Lebowski", "The Big Lebowski"),
        ("starship_rico", "Johnny Rico", "Starship Troopers"),
        ("starship_rasczak", "Lt. Rasczak", "Starship Troopers"),
        ("super_troopers", "Ensemble", "Super Troopers"),
        ("super_troopers_farva", "Farva", "Super Troopers"),
        ("blues_brothers_jake", "Jake Blues", "The Blues Brothers"),
        ("blues_brothers_elwood", "Elwood Blues", "The Blues Brothers"),
        ("blues_brothers", "Ensemble", "The Blues Brothers"),
        ("anchorman_burgundy", "Ron Burgundy", "Anchorman"),
        ("anchorman_brick", "Brick Tamland", "Anchorman"),
        ("anchorman_news_team", "News Team", "Anchorman"),
        ("zoolander_derek", "Derek Zoolander", "Zoolander"),
        ("zoolander_hansel", "Hansel", "Zoolander"),
        ("ghostbusters_venkman", "Peter Venkman", "Ghostbusters"),
        ("ghostbusters_ray", "Ray Stantz", "Ghostbusters"),
        ("ghostbusters_egon", "Egon Spengler", "Ghostbusters"),
    ]

    published = pack_builder.get_published_packs()
    published_names = {p["name"] for p in published}

    # Also check which movies have extraction scripts
    existing_scripts = set(extraction.get_all_movie_names())

    for pack_slug, character, movie in packs_designed:
        is_published = pack_slug in published_names

        # Check if the movie has an extraction script (simplified name match)
        movie_key = movie.lower().replace(" ", "").replace("the", "")

        if is_published:
            icon = "✅"
        elif any(movie_key[:6] in s for s in existing_scripts):
            icon = "🔄"
        else:
            icon = "⬜"

        st.markdown(f"{icon} **{pack_slug}** — {character} ({movie})")

    st.markdown("---")
    st.subheader("Legend")
    st.markdown("✅ Published | 🔄 Extraction in progress | ⬜ Not started")


# ============================================================
# PAGE: Radarr
# ============================================================
elif page == "Radarr":
    st.title("Radarr Integration")

    # Connection status
    status = radarr_client.get_status()
    if isinstance(status, dict) and "error" not in status:
        st.success(f"Connected to Radarr v{status.get('version', '?')}")
    else:
        st.error(f"Cannot connect: {status.get('error', 'Unknown error')}")

    # Download queue
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

    st.markdown("---")

    # Movie library
    st.subheader("Movie Library (Pipeline Targets)")
    target_keywords = [
        "big lebowski", "starship troopers", "super troopers",
        "blues brothers", "anchorman", "zoolander", "ghostbusters",
        "whiplash", "few good men", "fight club", "fifth element",
        "tucker and dale", "pulp fiction", "die hard", "full metal jacket",
        "glengarry", "tommy boy", "spaceballs", "goodfellas", "airplane",
    ]

    summary = radarr_client.get_movie_status_summary()
    if "error" not in summary:
        relevant = []
        for m in summary["movies"]:
            title_lower = m["title"].lower()
            if any(kw in title_lower for kw in target_keywords):
                status_emoji = "🟢" if m["has_file"] else "🔴"
                relevant.append({
                    "Status": status_emoji,
                    "Title": f"{m['title']} ({m['year']})",
                    "Has File": m["has_file"],
                    "Size (GB)": m["size_gb"],
                })
        if relevant:
            st.dataframe(relevant, use_container_width=True, hide_index=True)
        else:
            st.info("No pipeline-relevant movies found")

    # Add movie
    st.markdown("---")
    st.subheader("Add Movie")
    search_term = st.text_input("Search for movie")
    if search_term:
        results = radarr_client.lookup_movie(search_term)
        if isinstance(results, list) and results:
            for r in results[:5]:
                col1, col2 = st.columns([4, 1])
                col1.write(f"**{r.get('title', '?')}** ({r.get('year', '?')})")
                if col2.button("Add", key=f"add_{r.get('tmdbId')}"):
                    result = radarr_client.add_movie(r["tmdbId"])
                    if "error" in result:
                        st.error(result["error"][:200])
                    else:
                        st.success(f"Added: {r['title']}")
        else:
            st.info("No results")


# --- Auto-refresh removed ---
# Previously used HTML meta-refresh which caused full page reloads every 30s,
# destroying interactive state. Use the sidebar "Refresh" button instead.
