#!/usr/bin/env python3
"""Extract Tucker and Dale vs. Evil (2010) audio clips from MKV file."""
import sys
from extractor import run_extraction

MKV = "/Volumes/D-drive-music/Movies/Tucker and Dale vs. Evil (2010)/Tucker and Dale vs. Evil (2010) WEBDL-1080p.mkv"
AUDIO_STREAM = "0:1"  # English EAC3 2.0

CLIPS = [
    # === TUCKER (Alan Tudyk) ===
    ("tucker_hey_hi_there", 300, "Hey, hi there.", 2),
    ("vacation_home", 720, "It's our vacation home!", 2),
    ("hidy_ho_officer", 3000, "Oh hidy ho, officer.", 2),
    ("good_thing_going", 900, "We got a good thing going here.", 2),
    ("tucker_all_right", 900, "All right.", 1),
    ("fixer_upper", 720, "It's a fixer-upper.", 2),
    ("tucker_beautiful", 1200, "Beautiful.", 1),
    ("hucked_into_wood_chipper", 2100, "He just hucked himself right into the wood chipper!", 3),
    ("tucker_oh_god", 1800, "Oh God. Oh my God.", 2),
    ("killing_themselves_on_property", 2400, "These kids are coming out here and killing themselves all over my property!", 4),
    ("tucker_what_are_we_gonna_do", 1800, "What are we gonna do?", 2),
    ("tucker_are_you_ok", 1500, "Are you OK?", 1),
    ("really_hard_day", 3000, "I am having a really hard day.", 3),
    ("guy_like_me_talked_to_girl", 3600, "I should have known if a guy like me talked to a girl like you, somebody would end up dead.", 5),
    ("suicide_pact", 2400, "This is a suicide pact!", 2),
    ("tucker_college_kids", 1800, "College kids!", 2),
    ("tucker_dale_need_to_ask", 1800, "Dale, I need to ask you something.", 2),
    # === DALE (Tyler Labine) ===
    ("heavy_for_half_a_guy", 2100, "He's heavy for half a guy!", 2),
    ("dale_hey", 300, "Hey!", 1),
    ("dale_we_have_to_hide", 1800, "We have to hide!", 2),
    ("dale_ok", 900, "OK!", 1),
    ("dale_i_got_it", 1200, "I got it!", 1),
    ("dale_im_on_it", 1200, "I'm on it, Tucker!", 2),
    ("dale_i_got_her", 1200, "I got her!", 2),
    ("dale_we_did_it", 4800, "We did it!", 1),
    ("glad_im_not_dead", 5100, "I never thought I'd say this, but I'm glad I'm not dead.", 3),
    ("dale_you_look_hurt", 1500, "Are you OK? You look like you got hurt.", 2),
    ("dale_oh_god", 2100, "Oh God!", 1),
    ("dale_i_know_what_this_looks_like", 2100, "I know what this looks like.", 2),
    ("doozy_of_a_day", 2700, "Officer, we have had a doozy of a day.", 3),
    ("dale_what_do_we_do", 1800, "What do we do?", 1),
    ("half_the_man", 2100, "You're half the man you used to be.", 2),
    ("dale_im_not_ok", 3600, "I'm not OK!", 2),
    ("dale_college_kids", 2400, "College kids!", 2),
    ("college_kids_killing_themselves", 2700, "These college kids keep killing themselves!", 3),
    ("dale_should_i_talk_to_her", 900, "Should I go talk to her?", 2),
]

if __name__ == "__main__":
    run_extraction(
        movie_name="tuckerdale",
        mkv_path=MKV,
        audio_stream=AUDIO_STREAM,
        clips=CLIPS,
        targets=sys.argv[1:] if len(sys.argv) > 1 else None,
    )
