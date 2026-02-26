#!/usr/bin/env python3
"""Extract Full Metal Jacket (1987) audio clips from MKV file."""
import sys
from extractor import run_extraction

MKV = "/Volumes/D-drive-music/Movies/Full Metal Jacket (1987)/Full Metal Jacket (1987) Remux-2160p.mkv"
AUDIO_STREAM = "0:6"  # English DTS 5.1 (streams 1-5 are Russian/Ukrainian)

CLIPS = [
    # === GNY. SGT. HARTMAN (R. Lee Ermey) ===
    ("what_is_your_major_malfunction", 2700, "What is your major malfunction, numbnuts?!", 3),
    ("let_me_see_war_face", 900, "Let me see your war face!", 2),
    ("war_face_louder", 900, "Bullshit! You didn't convince me! Let me see your REAL war face!", 4),
    ("you_are_nothing", 300, "You are nothing but unorganized grabastic pieces of amphibian shit!", 4),
    ("i_am_gunnery_sergeant_hartman", 60, "I am Gunnery Sergeant Hartman, your senior drill instructor.", 4),
    ("holy_jesus_what_is_that", 300, "Holy Jesus! What is that? What the fuck is that?!", 4),
    ("jelly_donut", 300, "A jelly donut?!", 2),
    ("best_part_of_you", 300, "I bet you're the kind of guy who would fuck a person in the ass and not even have the goddamn common courtesy to give him a reach-around.", 7),
    ("five_foot_nine", 300, "Five foot nine, I didn't know they stacked shit that high!", 4),
    ("private_pyle", 300, "Private Pyle!", 1),
    ("are_you_quitting_on_me", 1800, "Are you quitting on me? Well, are you?!", 3),
    ("bull_shit", 600, "Bullshit!", 1),
    ("get_on_your_feet", 1500, "Get on your feet!", 2),
    ("i_will_motivate_you", 600, "I will motivate you, Private Pyle, if it short-dicks every cannibal on the Congo!", 5),
    ("hartman_sound_off", 300, "Sound off like you got a pair!", 2),
    ("hartman_do_you_understand", 300, "Do you understand that?!", 2),
    ("outstanding", 1200, "Outstanding!", 1),
    ("sir_yes_sir", 120, "Sir, yes, sir!", 1),
    ("what_is_your_name", 120, "What is your name, scumbag?", 2),
    ("you_will_not_laugh", 300, "You will not laugh! You will not cry!", 3),
    # === JOKER (Matthew Modine) ===
    ("born_to_kill", 3600, "I think I was trying to suggest something about the duality of man.", 4),
    ("joker_is_this_me", 2700, "Is that you, John Wayne? Is this me?", 3),
]

if __name__ == "__main__":
    run_extraction(
        movie_name="fullmetaljacket",
        mkv_path=MKV,
        audio_stream=AUDIO_STREAM,
        clips=CLIPS,
        targets=sys.argv[1:] if len(sys.argv) > 1 else None,
    )
