#!/usr/bin/env python3
"""Extract Die Hard (1988) audio clips."""
import sys
from extractor import run_extraction

MKV = "/Volumes/D-drive-music/Movies/Die Hard (1988)/Die Hard (1988) Remux-2160p.mkv"
AUDIO_STREAM = "0:1"

CLIPS = [
    # === JOHN McCLANE (Bruce Willis) ===
    ("yippee_ki_yay", 4800, "Yippee-ki-yay, motherfucker.", 3),
    ("welcome_to_the_party", 3600, "Welcome to the party, pal!", 2),
    ("come_out_to_the_coast", 5400, "Come out to the coast, we'll get together, have a few laughs.", 4),
    ("now_i_have_a_machine_gun", 2400, "Now I have a machine gun. Ho ho ho.", 3),
    ("nine_million_terrorists", 1800, "Nine million terrorists in the world and I gotta kill one with feet smaller than my sister.", 5),
    ("just_a_fly_in_the_ointment", 3000, "Just a fly in the ointment, Hans. The monkey in the wrench.", 4),
    ("mcclane_oh_shit", 3600, "Oh, shit!", 1),
    ("fists_with_toes", 600, "Fists with your toes.", 2),
    ("you_throw_quite_a_party", 5400, "You throw quite a party. I didn't realize they celebrated Christmas in Japan.", 5),
    # === HANS GRUBER (Alan Rickman) ===
    ("hans_mr_cowboy", 3600, "Mr. Mystery Guest? Are you still there?", 3),
    ("hans_benefits_of_classical_education", 3600, "The benefits of a classical education.", 3),
    ("hans_shoot_the_glass", 5400, "Shoot the glass!", 2),
    ("hans_nice_suit", 2400, "Nice suit. John Phillips, London.", 3),
    ("hans_ho_ho_ho", 3600, "Ho ho ho. Now I have a machine gun.", 3),
    ("hans_i_am_an_exceptional_thief", 4800, "I am an exceptional thief, Mrs. McClane. And since I'm moving up to kidnapping, you should be more polite.", 6),
    ("hans_when_alexander_saw", 4800, "When Alexander saw the breadth of his domain, he wept, for there were no more worlds to conquer.", 6),
    # === SGT. AL POWELL ===
    ("powell_welcome_to_the_party", 3600, "I hear you, partner.", 2),
    ("powell_roy_rogers", 2400, "Roy Rogers, huh?", 2),
]

if __name__ == "__main__":
    run_extraction(
        movie_name="diehard",
        mkv_path=MKV,
        audio_stream=AUDIO_STREAM,
        clips=CLIPS,
        targets=sys.argv[1:] if len(sys.argv) > 1 else None,
    )
