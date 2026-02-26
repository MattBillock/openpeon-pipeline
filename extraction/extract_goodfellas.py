#!/usr/bin/env python3
"""Extract GoodFellas (1990) audio clips."""
import sys
from extractor import run_extraction

MKV = "/Volumes/D-drive-music/Movies/GoodFellas (1990)/GoodFellas (1990) WEBDL-2160p.mkv"
AUDIO_STREAM = "0:1"

CLIPS = [
    # === TOMMY DeVITO (Joe Pesci) ===
    ("funny_how", 1200, "Funny how? Funny like a clown? Do I amuse you?", 4),
    ("funny_like_im_a_clown", 1200, "What do you mean funny? Funny like I'm a clown? I amuse you?", 4),
    ("tommy_now_go_home", 3600, "Now go home and get your fucking shinebox!", 3),
    ("tommy_you_think_im_funny", 1200, "You think I'm funny?", 2),
    ("tommy_what_do_you_mean", 1200, "What do you mean I'm funny?", 2),
    ("tommy_im_funny_how", 1200, "I'm funny how? I mean funny like I'm a clown?", 3),
    # === HENRY HILL (Ray Liotta) ===
    ("henry_as_far_back", 60, "As far back as I can remember, I always wanted to be a gangster.", 4),
    ("henry_goodfella", 600, "You're a goodfella. That's what we were. Goodfellas.", 3),
    ("henry_never_rat", 4800, "Never rat on your friends and always keep your mouth shut.", 3),
    ("henry_one_day", 7200, "One day some of the kids from the neighborhood carried my mother's groceries all the way home.", 5),
    ("henry_everybody", 5400, "Everybody had their hands out.", 2),
    # === JIMMY CONWAY (Robert De Niro) ===
    ("jimmy_dont_buy_anything", 4200, "Don't buy anything. Don't get anything. Nothing big. Don't make yourself conspicuous.", 5),
    ("jimmy_i_gotta_talk_to_you", 5400, "I gotta talk to you.", 2),
    # === PAULIE (Paul Sorvino) ===
    ("paulie_bring_me", 3000, "Bring me some.", 1),
]

if __name__ == "__main__":
    run_extraction(
        movie_name="goodfellas",
        mkv_path=MKV,
        audio_stream=AUDIO_STREAM,
        clips=CLIPS,
        targets=sys.argv[1:] if len(sys.argv) > 1 else None,
    )
