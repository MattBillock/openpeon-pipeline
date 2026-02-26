#!/usr/bin/env python3
"""Extract A Few Good Men (1992) audio clips from MKV file."""
import sys
from extractor import run_extraction

MKV = "/Volumes/D-drive-music/Movies/A Few Good Men (1992)/A Few Good Men (1992) Remux-2160p.mkv"
AUDIO_STREAM = "0:3"  # English AC3 5.1

CLIPS = [
    # === COL. JESSUP (Jack Nicholson) ===
    ("you_want_answers", 7200, "You want answers?", 2),
    ("you_cant_handle_the_truth", 7200, "You can't handle the truth!", 3),
    ("goddamn_right_i_did", 7260, "You're goddamn right I did!", 2),
    ("greater_responsibility", 7200, "I have a greater responsibility than you can possibly fathom.", 4),
    ("son_we_live_in_a_world", 7200, "Son, we live in a world that has walls.", 3),
    ("neither_time_nor_inclination", 7230, "I have neither the time nor the inclination to explain myself to a man who rises and sleeps under the blanket of the very freedom I provide.", 8),
    ("you_want_me_on_that_wall", 7230, "You don't want the truth because deep down in places you don't talk about at parties, you want me on that wall. You need me on that wall.", 8),
    ("are_we_clear", 7260, "Are we clear?", 2),
    ("are_we_clear_screaming", 7260, "ARE WE CLEAR?!", 2),
    ("dont_i_feel_like_asshole", 7260, "Don't I feel like the fucking asshole.", 3),
    ("santiago_is_dead", 7200, "Santiago is dead.", 2),
    ("rip_eyes_out", 7260, "I'm gonna rip the eyes out of your head and piss in your dead skull!", 4),
    ("you_weep_for_santiago", 7220, "You weep for Santiago and you curse the Marines.", 3),
    ("jessup_is_that_clear", 1500, "Is that clear?", 2),
    ("i_run_guantanamo", 1500, "I run Guantanamo Bay. The way I see fit.", 3),
    ("walk_of_shame", 7260, "What is it you want to discuss now? My favorite color?", 3),
    # === LT. KAFFEE (Tom Cruise) ===
    ("i_want_the_truth", 7200, "I want the truth!", 2),
    ("did_you_order_code_red", 7230, "Did you order the Code Red?", 3),
    ("did_you_order_code_red_screaming", 7260, "DID YOU ORDER THE CODE RED?!", 3),
    ("i_strenuously_object", 6600, "I strenuously object.", 2),
    ("oh_now_strenuously", 6600, "Oh, now I really am gonna strenuously object.", 3),
    ("colonel_underwear", 1800, "Is the colonel's underwear a matter of national security?", 3),
    ("facts_of_the_case", 7500, "These are the facts of the case, and they are undisputed.", 3),
    ("defense_rests", 7500, "The defense rests.", 2),
    ("witness_has_rights", 6900, "The witness has rights.", 2),
    ("one_more_question", 7200, "One more question.", 2),
    ("kaffee_hi", 600, "Hi there.", 1),
    ("kaffee_im_sorry", 3600, "I'm sorry.", 1),
    ("done_something_terrible", 4800, "I think I've done something terrible.", 3),
    ("lot_of_trouble", 6000, "We're in a lot of trouble.", 2),
    ("kaffee_i_object", 6600, "I object!", 2),
    ("have_a_problem", 4200, "I have a problem.", 2),
]

if __name__ == "__main__":
    run_extraction(
        movie_name="afewgoodmen",
        mkv_path=MKV,
        audio_stream=AUDIO_STREAM,
        clips=CLIPS,
        targets=sys.argv[1:] if len(sys.argv) > 1 else None,
    )
