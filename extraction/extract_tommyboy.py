#!/usr/bin/env python3
"""Extract Tommy Boy (1995) audio clips."""
import sys
from extractor import run_extraction

MKV = "/Volumes/D-drive-music/Movies/Tommy Boy (1995)/Tommy Boy (1995) Remux-1080p.mkv"
AUDIO_STREAM = "0:2"  # AC3 5.1 (stream 1 is TrueHD)

CLIPS = [
    # === TOMMY (Chris Farley) ===
    ("fat_guy_in_a_little_coat", 2400, "Fat guy in a little coat.", 2),
    ("tommy_holy_schnikes", 1800, "Holy schnikes!", 1),
    ("tommy_that_was_awesome", 3000, "That was awesome!", 1),
    ("tommy_what_id_do", 1800, "What'd I do?", 1),
    ("tommy_brothers_dont_shake", 600, "Brothers don't shake hands. Brothers gotta hug!", 3),
    ("tommy_guarantee", 4200, "I can get a good look at a T-bone by sticking my head up a bull's ass, but I'd rather take the butcher's word for it.", 7),
    ("tommy_road_trip", 2400, "Hey, I'll tell you what. If you want me to take a dump in a box and mark it guaranteed, I will.", 6),
    ("tommy_bees", 3000, "Bees! Bees! Bees in the car! Bees everywhere!", 3),
    ("tommy_housekeeping", 3600, "Housekeeping! You want me jerk you off?", 3),
    ("tommy_your_brain", 1200, "I can actually hear you getting fatter.", 3),
    ("tommy_sorry", 2400, "Sorry.", 1),
    ("tommy_did_i_catch_a_niner", 1800, "Did I catch a niner in there?", 2),
    # === RICHARD (David Spade) ===
    ("richard_kill_me", 3600, "Kill me. Kill me now.", 2),
    ("richard_not_here_not_now", 1200, "Not here. Not now.", 2),
    ("richard_i_can_hear_you_getting_fatter", 1200, "I can actually hear you getting fatter.", 3),
    ("richard_great", 2400, "Great.", 1),
    ("richard_shut_up", 1800, "Shut up, Richard.", 2),
    ("richard_oh_no", 3000, "Oh, no.", 1),
]

if __name__ == "__main__":
    run_extraction(
        movie_name="tommyboy",
        mkv_path=MKV,
        audio_stream=AUDIO_STREAM,
        clips=CLIPS,
        targets=sys.argv[1:] if len(sys.argv) > 1 else None,
    )
