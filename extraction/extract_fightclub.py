#!/usr/bin/env python3
"""Extract Fight Club (1999) audio clips from MKV file."""
import sys
from extractor import run_extraction

MKV = "/Volumes/D-drive-music/Movies/Fight Club (1999)/Fight Club (1999) Remux-1080p.mkv"
AUDIO_STREAM = "0:1"  # English DTS 5.1

CLIPS = [
    # === TYLER DURDEN (Brad Pitt) ===
    ("first_rule", 2400, "The first rule of Fight Club is: you do not talk about Fight Club.", 5),
    ("second_rule", 2400, "The second rule of Fight Club is: you DO NOT talk about Fight Club.", 5),
    ("welcome_to_fight_club", 2400, "Welcome to Fight Club.", 2),
    ("hit_me_as_hard", 2100, "I want you to hit me as hard as you can.", 3),
    ("lost_everything_free", 5400, "It's only after we've lost everything that we're free to do anything.", 4),
    ("not_beautiful_snowflake", 4800, "You are not a beautiful and unique snowflake.", 3),
    ("not_your_khakis", 4800, "You are not your fucking khakis.", 3),
    ("things_you_own", 2700, "The things you own end up owning you.", 3),
    ("hows_that_working", 1800, "How's that working out for you?", 2),
    ("sticking_feathers", 4800, "Sticking feathers up your butt does not make you a chicken.", 3),
    ("hitting_bottom", 5400, "Hitting bottom isn't a weekend retreat.", 3),
    ("self_improvement_masturbation", 4200, "Self-improvement is masturbation.", 3),
    ("this_is_your_pain", 3600, "This is your pain.", 2),
    ("his_name_robert_paulson", 6600, "His name is Robert Paulson.", 2),
    ("his_name_robert_paulson_loud", 6600, "HIS NAME IS ROBERT PAULSON.", 2),
    ("is_that_what_man_looks_like", 3000, "Is that what a man looks like?", 2),
    ("you_dont_know_where_ive_been", 3600, "You don't know where I've been.", 2),
    # === THE NARRATOR (Edward Norton) ===
    ("jacks_inflamed_rejection", 3000, "I am Jack's inflamed sense of rejection.", 3),
    ("jacks_smirking_revenge", 4200, "I am Jack's smirking revenge.", 2),
    ("jacks_complete_lack_surprise", 5400, "I am Jack's complete lack of surprise.", 3),
    ("jacks_wasted_life", 4800, "I am Jack's wasted life.", 2),
    ("jacks_broken_heart", 6000, "I am Jack's broken heart.", 2),
    ("jacks_cold_sweat", 5400, "I am Jack's cold sweat.", 2),
    ("jacks_raging_bile_duct", 3600, "I am Jack's raging bile duct.", 2),
    ("insomnia_nothings_real", 300, "With insomnia, nothing's real.", 2),
    ("people_asking_tyler", 120, "People are always asking me if I know Tyler Durden.", 3),
    ("copy_of_a_copy", 600, "Everything's a copy of a copy of a copy.", 3),
    ("strange_time_in_my_life", 8100, "You met me at a very strange time in my life.", 3),
    ("felt_like_destroying", 4800, "I felt like destroying something beautiful.", 3),
    ("is_this_a_test", 3000, "Is this a test?", 2),
    ("what_do_you_want_me_to_do", 5400, "What do you want me to do?", 2),
    ("narrator_ok", 2400, "OK.", 1),
]

if __name__ == "__main__":
    run_extraction(
        movie_name="fightclub",
        mkv_path=MKV,
        audio_stream=AUDIO_STREAM,
        clips=CLIPS,
        targets=sys.argv[1:] if len(sys.argv) > 1 else None,
    )
