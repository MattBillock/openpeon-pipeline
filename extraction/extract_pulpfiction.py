#!/usr/bin/env python3
"""Extract Pulp Fiction (1994) audio clips from MKV file."""
import sys
from extractor import run_extraction

MKV = "/Volumes/D-drive-music/Movies/Pulp Fiction (1994)/Pulp Fiction (1994) Remux-1080p.mkv"
AUDIO_STREAM = "0:1"  # English DTS 5.1

CLIPS = [
    # === JULES WINNFIELD (Samuel L. Jackson) ===
    ("say_what_again", 1800, "Say 'what' again! Say 'what' again! I dare you! I double dare you, motherfucker!", 5),
    ("english_motherfucker", 1800, "English, motherfucker! Do you speak it?!", 3),
    ("what_does_marsellus_look_like", 1800, "What does Marsellus Wallace look like?", 3),
    ("does_he_look_like_a_bitch", 1800, "Does he look like a bitch?", 2),
    ("ezekiel_2517", 1860, "The path of the righteous man is beset on all sides by the inequities of the selfish and the tyranny of evil men.", 7),
    ("great_vengeance", 1860, "And I will strike down upon thee with great vengeance and furious anger those who attempt to poison and destroy my brothers.", 7),
    ("divine_intervention", 2100, "What happened here was a miracle, and I want you to fucking acknowledge it!", 4),
    ("jules_be_cool", 8100, "Tell that bitch to be cool! Say 'bitch, be cool!'", 3),
    ("royale_with_cheese", 420, "They call it a Royale with Cheese.", 2),
    ("thats_a_tasty_burger", 1740, "Mmm! That is a tasty burger!", 2),
    ("jules_goddamn", 1800, "Oh, I'm sorry. Did I break your concentration?", 3),
    ("check_out_the_big_brain", 1800, "Check out the big brain on Brett!", 2),
    ("correctamundo", 1800, "Correctamundo.", 1),
    ("allow_me_to_retort", 1800, "Well, allow me to retort.", 2),
    ("jules_lets_go", 2100, "Let's go.", 1),
    ("jules_be_cool_honey", 8100, "Everybody be cool, this is a robbery!", 3),
    # === VINCENT VEGA (John Travolta) ===
    ("vincent_oh_man", 2100, "Oh man, I shot Marvin in the face.", 3),
    ("vincent_i_gotta_stab_her", 4200, "I gotta stab her three times?", 2),
    ("vincent_comfortable_silences", 3600, "That's when you know you found somebody special: when you can just shut the fuck up for a minute and comfortably share silence.", 6),
    # === THE WOLF (Harvey Keitel) ===
    ("wolf_im_winston_wolfe", 6900, "I'm Winston Wolfe. I solve problems.", 3),
    ("wolf_pretty_please", 7200, "Pretty please, with sugar on top. Clean the fucking car.", 4),
    ("wolf_lets_not_start", 6900, "Let's not start sucking each other's dicks quite yet.", 3),
    ("wolf_thirty_minutes", 6900, "That's thirty minutes away. I'll be there in ten.", 3),
    ("wolf_you_got_a_problem", 6900, "You've got a corpse in a car, minus a head, in a garage. Take me to it.", 5),
    # === MIA WALLACE (Uma Thurman) ===
    ("mia_dont_be_a_square", 3000, "Don't be a square.", 2),
    ("mia_i_said_goddamn", 3600, "I said goddamn! Goddamn!", 2),
    # === MARSELLUS WALLACE (Ving Rhames) ===
    ("marsellus_medieval", 6300, "I'm gonna get medieval on your ass.", 3),
    ("marsellus_pride_never_helps", 5700, "That's pride fucking with you. Fuck pride.", 3),
    # === BUTCH (Bruce Willis) ===
    ("butch_zeds_dead", 6600, "Zed's dead, baby. Zed's dead.", 3),
    # === PUMPKIN/HONEY BUNNY ===
    ("everybody_be_cool", 300, "Everybody be cool, this is a robbery!", 2),
    ("any_of_you_pricks_move", 300, "Any of you fucking pricks move, and I'll execute every motherfucking last one of ya!", 4),
]

if __name__ == "__main__":
    run_extraction(
        movie_name="pulpfiction",
        mkv_path=MKV,
        audio_stream=AUDIO_STREAM,
        clips=CLIPS,
        targets=sys.argv[1:] if len(sys.argv) > 1 else None,
    )
