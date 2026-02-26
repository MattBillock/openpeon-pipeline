#!/usr/bin/env python3
"""Extract Glengarry Glen Ross (1992) audio clips from MKV file."""
import sys
from extractor import run_extraction

MKV = "/Volumes/D-drive-music/Movies/Glengarry Glen Ross (1992)/Glengarry Glen Ross (1992) Remux-1080p.mkv"
AUDIO_STREAM = "0:1"  # DTS 5.1 English

CLIPS = [
    # === BLAKE (Alec Baldwin) ===
    ("coffee_is_for_closers", 600, "Put that coffee down. Coffee's for closers only.", 3),
    ("abc_always_be_closing", 600, "A, always. B, be. C, closing. Always be closing. ALWAYS BE CLOSING.", 5),
    ("first_prize_cadillac", 720, "First prize is a Cadillac Eldorado. Second prize is a set of steak knives. Third prize is you're fired.", 6),
    ("you_see_this_watch", 600, "You see this watch? You see this watch?", 3),
    ("good_father", 600, "Nice guy? I don't give a shit. Good father? Fuck you! Go home and play with your kids.", 5),
    ("get_them_to_sign", 720, "Get them to sign on the line which is dotted.", 3),
    ("brass_balls", 600, "You know what it takes to sell real estate? It takes brass balls to sell real estate.", 5),
    ("blake_you_cant_close", 720, "You can't close the leads you're given, you can't close shit. You ARE shit.", 4),
    ("blake_hit_the_bricks", 720, "Hit the bricks, pal. And beat it, because you are going OUT.", 4),
    # === RICKY ROMA (Al Pacino) ===
    ("roma_all_train_compartments", 1800, "All train compartments smell vaguely of shit.", 3),
    ("roma_you_stupid_fucking_cunt", 4200, "You stupid fucking cunt.", 2),
    ("roma_did_i_close", 3600, "Did I close? Did I close?", 2),
    ("roma_i_subscribe", 4800, "I subscribe to the law of contrary public opinion.", 3),
    ("roma_wheres_my_contract", 4200, "Where's my contract?", 2),
    # === SHELLEY LEVENE (Jack Lemmon) ===
    ("levene_the_machine", 3600, "I made it! I'm back! I'm the Machine!", 3),
    ("levene_the_leads", 1200, "The leads! The new leads!", 2),
    ("levene_dont_call_me_shelly", 3000, "Don't call me that.", 2),
    # === DAVE MOSS (Ed Harris) ===
    ("moss_you_know_who_you_are", 2400, "Somebody put a man through that. Somebody put a man through it.", 4),
    ("moss_we_gotta_rob", 2400, "Somebody should stand up and strike back.", 3),
]

if __name__ == "__main__":
    run_extraction(
        movie_name="glengarry",
        mkv_path=MKV,
        audio_stream=AUDIO_STREAM,
        clips=CLIPS,
        targets=sys.argv[1:] if len(sys.argv) > 1 else None,
    )
