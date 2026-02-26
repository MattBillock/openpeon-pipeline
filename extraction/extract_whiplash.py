#!/usr/bin/env python3
"""Extract Whiplash (2014) audio clips from MKV file."""
import sys
from extractor import run_extraction

MKV = "/Volumes/D-drive-music/Movies/Whiplash (2014)/Whiplash (2014) Remux-2160p.mkv"
AUDIO_STREAM = "0:2"  # English AC3 5.1

CLIPS = [
    # === FLETCHER - CLASSROOM (J.K. Simmons) ===
    ("looking_for_players_beyond_the_best", 840, "I'm looking for players who are beyond the best.", 3),
    ("key_is_to_just_relax", 900, "The key is to just relax.", 2),
    ("no_two_words_good_job", 5400, "There are no two words in the English language more harmful than good job.", 5),
    ("were_you_rushing_or_dragging", 1200, "Were you rushing or were you dragging?", 3),
    ("start_counting", 1230, "Start counting.", 2),
    ("rusher_or_dragger", 1260, "Now, are you a rusher or are you a dragger?", 3),
    ("not_bad", 960, "Not bad.", 1),
    ("good_job_just_kidding", 900, "Good job. I'm just kidding.", 3),
    ("not_quite_my_tempo", 1200, "Not quite my tempo.", 2),
    ("my_concern_with_you", 1500, "Here's my concern with you.", 2),
    ("not_boyfriends_dick", 1320, "That is not your boyfriend's dick. Don't come too early.", 4),
    ("answer", 1260, "Answer!", 1),
    ("double_fucking_rainbow", 3300, "Do I look like a double-fucking-rainbow to you?", 3),
    ("stop_being_your_friend", 2700, "I will stop being your friend.", 2),
    ("for_the_last_time", 2400, "For the last time.", 2),
    ("tempo_not_negotiable", 1800, "The tempo is not negotiable.", 2),
    ("why_hurled_chair", 1500, "Why do you suppose I just hurled a chair at your head, Neiman?", 4),
    ("one_more", 1800, "One more.", 1),
    ("deliberately_out_of_tune", 2100, "Either you're deliberately playing out of tune, or you don't know you're out of tune.", 5),
    # === FLETCHER - CONCERT / RAGE ===
    ("here_for_a_reason", 5400, "I am here for a reason.", 2),
    ("get_out_of_my_sight", 3000, "Get the fuck out of my sight before I demolish you.", 3),
    ("faster", 2400, "Faster!", 1),
    ("louder_louder", 2400, "Louder! LOUDER!", 2),
    ("faster_screaming", 3600, "FASTER!", 1),
    ("again", 1800, "Again!", 1),
    ("thats_what_im_looking_for", 4200, "That's what I'm looking for.", 2),
    ("there_it_is", 4800, "THERE it is.", 1),
    ("worthless_friendless", 3000, "You are a worthless, friendless, faggot-lipped little piece of shit.", 5),
    ("completely_utterly_wrong", 2700, "Completely. Utterly. Wrong.", 3),
    ("single_tear_people", 3000, "Are you one of those single-tear people?", 2),
    ("oh_my_dear_god", 2700, "Oh my dear God.", 2),
    ("play", 4800, "PLAY!", 1),
    ("why_are_you_stopping", 2100, "Why are you stopping?!", 2),
    ("did_i_say_to_stop", 2100, "Did I say to stop?!", 2),
    ("fuck_you_like_a_pig", 3000, "I will fuck you like a pig.", 2),
    ("you_are_done", 3000, "You are done.", 2),
    ("pack_up_your_shit", 3000, "Pack up your shit.", 2),
    ("not_my_fucking_tempo", 1200, "Not my fucking tempo!", 2),
    ("again_screaming", 2400, "AGAIN!", 1),
    # === NEIMAN (Miles Teller) ===
    ("im_andrew_neiman", 300, "I'm Andrew Neiman.", 2),
    ("im_here", 600, "I'm here.", 1),
    ("want_to_be_great", 420, "I want to be one of the greats.", 2),
    ("yes_sir", 900, "Yes, sir.", 1),
    ("ill_be_ready", 1200, "I'll be ready.", 1),
    ("work_harder", 1500, "I'm gonna work harder.", 2),
    ("i_did_it", 5700, "I did it.", 1),
    ("neiman_fuck", 1800, "Fuck!", 1),
    ("im_sorry", 1500, "I'm sorry.", 1),
    ("hands_bleeding", 3900, "My hands are bleeding.", 2),
    ("i_cant", 3600, "I can't.", 1),
    ("need_a_minute", 3300, "I need a minute.", 2),
    ("im_trying", 2400, "I'm trying!", 1),
    ("what_do_you_want", 3000, "What do you want from me?", 2),
    ("what_did_i_do_wrong", 1800, "What did I do wrong?", 2),
]

if __name__ == "__main__":
    run_extraction(
        movie_name="whiplash",
        mkv_path=MKV,
        audio_stream=AUDIO_STREAM,
        clips=CLIPS,
        targets=sys.argv[1:] if len(sys.argv) > 1 else None,
    )
