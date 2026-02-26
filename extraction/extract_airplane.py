#!/usr/bin/env python3
"""Extract Airplane! (1980) audio clips."""
import sys
from extractor import run_extraction

MKV = "/Volumes/D-drive-music/Movies/Airplane! (1980)/Airplane! (1980) Remux-1080p.mkv"
AUDIO_STREAM = "0:1"

CLIPS = [
    # === DR. RUMACK (Leslie Nielsen) ===
    ("dont_call_me_shirley", 1200, "I am serious. And don't call me Shirley.", 3),
    ("rumack_hospital", 3000, "A hospital! What is it?", 2),
    ("rumack_its_a_big_building", 3000, "It's a big building with patients, but that's not important right now.", 4),
    ("rumack_good_luck", 4800, "Good luck. We're all counting on you.", 3),
    ("rumack_picked_wrong_week", 2400, "Looks like I picked the wrong week to quit smoking.", 3),
    ("rumack_surely_you_cant_be_serious", 1200, "Surely you can't be serious.", 2),
    ("rumack_food_poisoning", 2400, "The life of everyone on board depends upon just one thing: finding someone back there who can not only fly this plane, but who didn't have fish for dinner.", 8),
    # === McCROSKEY (Lloyd Bridges) ===
    ("wrong_week_quit_smoking", 1800, "Looks like I picked the wrong week to quit smoking.", 3),
    ("wrong_week_quit_drinking", 2400, "Looks like I picked the wrong week to quit drinking.", 3),
    ("wrong_week_quit_sniffing", 3000, "Looks like I picked the wrong week to quit sniffing glue.", 3),
    ("wrong_week_quit_amphetamines", 3600, "Looks like I picked the wrong week to quit amphetamines.", 3),
    # === JOHNNY ===
    ("johnny_jive", 2400, "Oh stewardess, I speak jive.", 2),
    ("roger_roger", 1200, "Roger, Roger. What's our vector, Victor?", 3),
    ("over_over", 1200, "Over, Oveur.", 1),
    ("clearance_clarence", 600, "Roger, Roger. What's our clearance, Clarence?", 3),
    # === TED STRIKER (Robert Hays) ===
    ("striker_drinking_problem", 1800, "Drinking problem.", 1),
    ("striker_win_just_one", 4200, "Win just one for the Zipper.", 2),
]

if __name__ == "__main__":
    run_extraction(
        movie_name="airplane",
        mkv_path=MKV,
        audio_stream=AUDIO_STREAM,
        clips=CLIPS,
        targets=sys.argv[1:] if len(sys.argv) > 1 else None,
    )
