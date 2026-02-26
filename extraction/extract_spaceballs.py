#!/usr/bin/env python3
"""Extract Spaceballs (1987) audio clips."""
import sys
from extractor import run_extraction

MKV = "/Volumes/D-drive-music/Movies/Spaceballs (1987)/Spaceballs (1987) Bluray-1080p Proper.mkv"
AUDIO_STREAM = "0:1"

CLIPS = [
    # === DARK HELMET (Rick Moranis) ===
    ("schwartz_as_big", 3600, "I see your Schwartz is as big as mine.", 3),
    ("ludicrous_speed", 600, "Ludicrous speed! GO!", 2),
    ("gone_to_plaid", 600, "They've gone to plaid!", 2),
    ("helmet_surrounded_by_assholes", 1200, "I'm surrounded by assholes!", 2),
    ("helmet_fooled_you", 3600, "Fooled you!", 1),
    ("helmet_evil_will_always_triumph", 3600, "Evil will always triumph, because good is dumb.", 3),
    ("helmet_say_goodbye", 4200, "Say goodbye to your two best friends. And I don't mean your pals in the Winnebago.", 5),
    ("helmet_keep_firing_assholes", 4200, "Keep firing, assholes!", 2),
    ("helmet_what_happened", 3000, "What happened to then?", 2),
    ("helmet_now", 3000, "Now. Everything that happens now is happening now.", 3),
    ("helmet_when", 3000, "When will then be now?", 2),
    ("helmet_soon", 3000, "Soon.", 1),
    ("helmet_out_of_order", 2400, "Even in the future nothing works!", 2),
    ("helmet_comb_the_desert", 2400, "Comb the desert!", 2),
    ("helmet_raspberry", 3600, "There's only one man who would dare give me the raspberry! Lone Starr!", 4),
    # === LONE STARR (Bill Pullman) ===
    ("lonestarr_may_schwartz", 4800, "May the Schwartz be with you.", 2),
    ("lonestarr_take_only_what_you_need", 1800, "Take only what you need to survive.", 3),
    # === BARF (John Candy) ===
    ("barf_im_a_mog", 1200, "I'm a Mog. Half man, half dog. I'm my own best friend.", 4),
    ("barf_not_in_here_mister", 600, "Not in here, mister. This is a Mercedes.", 3),
    # === YOGURT (Mel Brooks) ===
    ("yogurt_merchandising", 3000, "Merchandising! Merchandising! Where the real money from the movie is made!", 4),
    ("yogurt_moichandising", 3000, "Moichandising!", 1),
    ("yogurt_may_the_schwartz", 3000, "May the Schwartz be with you!", 2),
]

if __name__ == "__main__":
    run_extraction(
        movie_name="spaceballs",
        mkv_path=MKV,
        audio_stream=AUDIO_STREAM,
        clips=CLIPS,
        targets=sys.argv[1:] if len(sys.argv) > 1 else None,
    )
