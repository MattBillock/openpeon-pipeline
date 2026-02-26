#!/usr/bin/env python3
"""Extract The Fifth Element (1997) audio clips from MKV file."""
import sys
from extractor import run_extraction

MKV = "/Volumes/D-drive-music/Movies/The Fifth Element (1997)/The Fifth Element (1997) Remux-2160p.mkv"
AUDIO_STREAM = "0:2"  # English AC3 5.1

CLIPS = [
    # === KORBEN DALLAS (Bruce Willis) ===
    ("multipass", 1500, "Multipass.", 1),
    ("leeloo_dallas_multipass", 1800, "Leeloo Dallas. Multipass.", 3),
    ("multipass_screaming", 2400, "MULTIPASS!", 1),
    ("negative_meat_popsicle", 900, "Negative. I am a meat popsicle.", 3),
    ("big_bada_boom", 3600, "Big bada boom.", 2),
    ("anybody_else_negotiate", 5400, "Anybody else want to negotiate?", 2),
    ("only_two_languages", 3000, "Lady, I only speak two languages: English and bad English.", 4),
    ("were_saved", 7200, "We're saved.", 2),
    ("what_am_i_supposed_to_do", 3600, "What the hell am I supposed to do?", 2),
    ("korben_unbelievable", 4200, "Unbelievable.", 1),
    ("korben_yeah_hi", 600, "Yeah, hi.", 1),
    ("green", 3000, "Green.", 1),
    # === RUBY RHOD (Chris Tucker) ===
    ("bzzzz", 3600, "Bzzzz!", 1),
    ("supergreen", 3600, "Supergreen!", 1),
    ("korben_dallas_here_he_is", 3600, "Korben Dallas! Here he is!", 2),
    ("quiver_ladies", 4200, "Quiver, ladies. Quiver.", 2),
    ("were_all_gonna_die", 5700, "We're all gonna die!", 2),
    ("oh_no_nononono", 5400, "Oh no. Oh no no no no no.", 3),
    ("ruby_unbelievable", 4800, "Unbelievable!", 1),
    ("korben_my_man", 4200, "Korben? Korben, my man?", 2),
    ("whats_happening", 5400, "What's happening?", 1),
    ("i_have_no_fire", 6600, "I have no fire.", 2),
    ("commercial", 4800, "Commercial! COMMERCIAL!", 2),
    ("i_am_so_great", 3600, "I am so great.", 2),
    # === LEELOO (Milla Jovovich) ===
    ("leeloo_multipass", 1500, "Mul-ti-pass.", 2),
    ("big_bada_boom_leeloo", 1200, "Big bada boom.", 2),
    ("please_help", 1200, "Please help.", 2),
    ("leeloo_minai", 1200, "Leeloo Minai Lekarariba-Laminai-Tchai Ekbat De Sebat.", 4),
    # === ZORG (Gary Oldman) ===
    ("zorg_fire_one_million", 3000, "Fire one million.", 2),
    ("zorg_i_know", 4800, "I know.", 1),
    ("zorg_zero_stones", 6600, "Zero stones, zero crates!", 2),
    ("zorg_what_a_lovely_day", 2400, "What a lovely day for an exorcism.", 3),
]

if __name__ == "__main__":
    run_extraction(
        movie_name="fifthelement",
        mkv_path=MKV,
        audio_stream=AUDIO_STREAM,
        clips=CLIPS,
        targets=sys.argv[1:] if len(sys.argv) > 1 else None,
    )
