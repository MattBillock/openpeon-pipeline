# OpenPeon Movie Pack Roadmap

## Status Legend
- PUBLISHED = live in registry
- IN PROGRESS = extraction/building underway
- READY = on D-drive, pack designed, ready to extract
- NEEDS MOVE = not on D-drive yet

---

## PUBLISHED (20 packs, 7 movies)

| Movie | Packs | Status |
|---|---|---|
| The Big Lebowski (1998) | `lebowski_the_dude`, `lebowski_walter`, `lebowski_jesus`, `lebowski_maude`, `lebowski_big_lebowski` | PUBLISHED v1.0.0 |
| Anchorman (2004) | `anchorman_burgundy`, `anchorman_brick`, `anchorman_news_team` | PUBLISHED v1.0.0 |
| Starship Troopers (1997) | `starship_rico`, `starship_rasczak` | PUBLISHED v1.0.0 |
| Super Troopers (2001) | `super_troopers`, `super_troopers_farva` | PUBLISHED v1.0.0 |
| The Blues Brothers (1980) | `blues_brothers_jake`, `blues_brothers_elwood`, `blues_brothers` | PUBLISHED v1.0.0 |
| Zoolander (2001) | `zoolander_derek`, `zoolander_hansel` | PUBLISHED v1.0.0 |
| Office Space (1999) | `office_space`, `office_space_lumbergh`, `office_space_peter` | PUBLISHED v1.0.0 |

---

## IN PROGRESS (6 packs, 2 movies)

### Whiplash (2014) — 3 packs — EXTRACTING
- `whiplash_fletcher_classroom` — Fletcher: The Teacher
- `whiplash_fletcher_concert` — Fletcher: The Monster
- `whiplash_neiman` — Andrew Neiman
- Source: MKV on D-drive, extraction running

### Ghostbusters (1984) — 3 packs — BLOCKED (ISO format)
- `ghostbusters_venkman` — Peter Venkman (Bill Murray)
- `ghostbusters_ray` — Ray Stantz (Dan Aykroyd)
- `ghostbusters_egon` — Egon Spengler (Harold Ramis)
- Source: ISO on D-drive, SMB+UDF bottleneck. Needs local copy or remux.

---

## TIER 1: User-Requested (on D-drive, design needed)

### A Few Good Men (1992) — 2 packs
**`afewgoodmen_jessup`** — Col. Nathan Jessup (Jack Nicholson)
*When your agent thinks it can handle the truth*

| Category | Quotes |
|---|---|
| `session.start` | "You want answers?" / "I have a greater responsibility than you can possibly fathom." / "Son, we live in a world that has walls." |
| `task.acknowledge` | "Is there another kind?" / "You're goddamn right I did!" / "I'd appreciate it if he would address me as Colonel or Sir." |
| `task.complete` | "You're goddamn right I did!" / "I have neither the time nor the inclination." / "Santiago is dead." |
| `task.error` | "YOU CAN'T HANDLE THE TRUTH!" / "Are we clear?" / "Don't I feel like the fucking asshole." |
| `input.required` | "You want answers?" / "Are we clear?!" / "ARE WE CLEAR?!" |
| `resource.limit` | "I have neither the time nor the inclination to explain myself to a man who rises and sleeps under the blanket of the very freedom I provide." / "You don't want the truth because deep down in places you don't talk about at parties, you want me on that wall." |
| `user.spam` | "YOU CAN'T HANDLE THE TRUTH!" / "I'm gonna rip the eyes out of your head and piss in your dead skull!" / "Don't call me son." |

**`afewgoodmen_kaffee`** — Lt. Daniel Kaffee (Tom Cruise)
*The slacker lawyer who finally shows up*

| Category | Quotes |
|---|---|
| `session.start` | "I want the truth!" / "Hi there." / "I'm Kaffee." |
| `task.acknowledge` | "I want the truth!" / "I strenuously object." / "Is the colonel's underwear a matter of national security?" |
| `task.complete` | "The witness has rights." / "These are the facts of the case, and they are undisputed." / "The defense rests." |
| `task.error` | "Oh, now I really am gonna strenuously object." / "I have a problem." / "Did you order the Code Red?" |
| `input.required` | "Did you order the Code Red?!" / "I want the truth!" / "One more question." |
| `resource.limit` | "I think I've done something terrible." / "We're in a lot of trouble." |
| `user.spam` | "DID YOU ORDER THE CODE RED?!" / "I object!" / "I strenuously object!" |

**Comedy highlight:** "YOU CAN'T HANDLE THE TRUTH!" for `task.error` — your code broke and Jessup is SCREAMING at you that you can't handle it. "Did you order the Code Red?!" for `input.required` — the agent needs your permission and is cross-examining you for it.

---

### Fight Club (1999) — 2 packs
**`fightclub_tyler`** — Tyler Durden (Brad Pitt)
*Anarchist philosophy as coding notifications*

| Category | Quotes |
|---|---|
| `session.start` | "The first rule of Fight Club is: you do not talk about Fight Club." / "Welcome to Fight Club." / "I want you to hit me as hard as you can." |
| `task.acknowledge` | "You don't know where I've been." / "It's only after we've lost everything that we're free to do anything." / "How's that working out for you?" |
| `task.complete` | "You met me at a very strange time in my life." / "I am Jack's complete lack of surprise." / "Sticking feathers up your butt does not make you a chicken." |
| `task.error` | "The things you own end up owning you." / "You are not a beautiful and unique snowflake." / "Hitting bottom isn't a weekend retreat." / "This is your pain." |
| `input.required` | "I want you to hit me as hard as you can." / "How's that working out for you?" / "Is that what a man looks like?" |
| `resource.limit` | "It's only after we've lost everything that we're free to do anything." / "You are not your fucking khakis." / "Self-improvement is masturbation." |
| `user.spam` | "His name is Robert Paulson." / "His name is Robert Paulson." / "HIS NAME IS ROBERT PAULSON." |

**`fightclub_narrator`** — The Narrator (Edward Norton)
*Exhausted, dissociated, done with everything*

| Category | Quotes |
|---|---|
| `session.start` | "I am Jack's inflamed sense of rejection." / "With insomnia, nothing's real." / "People are always asking me if I know Tyler Durden." |
| `task.acknowledge` | "I am Jack's smirking revenge." / "OK." / "I am Jack's complete lack of surprise." |
| `task.complete` | "I am Jack's smirking revenge." / "You met me at a very strange time in my life." / "I felt like destroying something beautiful." |
| `task.error` | "I am Jack's wasted life." / "I am Jack's broken heart." / "I am Jack's cold sweat." / "I am Jack's inflamed sense of rejection." |
| `input.required` | "People are always asking me if I know Tyler Durden." / "Is this a test?" / "What do you want me to do?" |
| `resource.limit` | "I am Jack's complete lack of surprise." / "With insomnia, nothing's real." / "Everything's a copy of a copy of a copy." |
| `user.spam` | "I am Jack's raging bile duct." / "I am Jack's cold sweat." / "I want you to hit me as hard as you can." |

**Comedy highlight:** user.spam for Tyler is "His name is Robert Paulson" three times — the same chant escalating. The Narrator's "I am Jack's [x]" fills every category perfectly.

---

### The Fifth Element (1997) — 2 packs
**`fifthelement_korben`** — Korben Dallas (Bruce Willis)
*Reluctant hero cab driver energy*

| Category | Quotes |
|---|---|
| `session.start` | "Leeloo Dallas. Multipass." / "Yeah, hi." / "Negative. I am a meat popsicle." |
| `task.acknowledge` | "Big bada boom." / "Anybody else want to negotiate?" / "Multipass." |
| `task.complete` | "Big bada boom." / "We're saved." / "I know she's made to be perfect." |
| `task.error` | "Negative. I am a meat popsicle." / "Unbelievable." / "What the hell am I supposed to do?" |
| `input.required` | "Leeloo Dallas. Multipass." / "Multipass!" / "MULTIPASS!" |
| `resource.limit` | "I am a meat popsicle." / "What the hell am I supposed to do?" / "Lady, I only speak two languages: English and bad English." |
| `user.spam` | "Anybody else want to negotiate?" / "Multipass!" / "Green." |

**`fifthelement_ruby`** — Ruby Rhod (Chris Tucker)
*Maximum flamboyant panic as a notification sound*

| Category | Quotes |
|---|---|
| `session.start` | "Bzzzz!" / "Korben Dallas! Here he is!" / "Supergreen!" |
| `task.acknowledge` | "Supergreen!" / "Quiver, ladies. Quiver." / "I am so great." |
| `task.complete` | "Supergreen!" / "Unbelievable!" / "Green!" |
| `task.error` | "Oh no. Oh nonononono." / "We're all gonna die!" / "AAAAHHH!" |
| `input.required` | "Korben? Korben, my man?" / "Korben Dallas!" / "What's happening?" |
| `resource.limit` | "We're all gonna die!" / "Oh no oh no oh no oh no." / "I have no fire." |
| `user.spam` | "Bzzzz! Bzzzzz! BZZZZZZZ!" / "Commercial! COMMERCIAL!" / "Supergreen supergreen supergreen!" |

**Comedy highlight:** Ruby Rhod is pure chaos. "BZZZZZ!" for user.spam. "We're all gonna die!" for resource.limit. "Supergreen!" works everywhere.

---

### Tucker and Dale vs. Evil (2010) — 2 packs
**`tuckerdale_tucker`** — Tucker (Alan Tudyk)
*Just a guy trying to fix up his vacation home*

| Category | Quotes |
|---|---|
| `session.start` | "Hey, hi there." / "It's our vacation home!" / "Oh hidy ho, officer." |
| `task.acknowledge` | "We got a good thing going here." / "All right." / "We're gonna have a good time." |
| `task.complete` | "It's a fixer-upper." / "We got a good thing going." / "Beautiful." |
| `task.error` | "He just hucked himself right into the wood chipper!" / "Oh God. Oh my God." / "These kids are coming out here and killing themselves all over my property!" |
| `input.required` | "Dale, I need to ask you something." / "Are you OK?" / "What are we gonna do?" |
| `resource.limit` | "I am having a really hard day." / "I should have known if a guy like me talked to a girl like you, somebody would end up dead." / "This is a suicide pact!" |
| `user.spam` | "College kids!" / "It's a suicide pact!" / "They keep killing themselves!" |

**`tuckerdale_dale`** — Dale (Tyler Labine)
*Lovable doofus who can't catch a break*

| Category | Quotes |
|---|---|
| `session.start` | "He's heavy for half a guy!" / "Hey!" / "We have to hide!" |
| `task.acknowledge` | "OK!" / "I got it!" / "I'm on it, Tucker!" |
| `task.complete` | "I got her!" / "We did it!" / "I never thought I'd say this, but I'm glad I'm not dead." |
| `task.error` | "Are you OK? You look like you got hurt." / "Oh God!" / "I know what this looks like." |
| `input.required` | "Officer, we have had a doozy of a day." / "Should I go talk to her?" / "What do we do?" |
| `resource.limit` | "You're half the man you used to be." / "Officer, we have had a doozy of a day." / "I'm not OK!" |
| `user.spam` | "We have had a doozy of a day!" / "College kids!" / "These college kids keep killing themselves!" |

**Comedy highlight:** "Officer, we have had a doozy of a day" is the perfect `input.required` / `resource.limit` line. The absurdist horror-comedy translates perfectly — "He just hucked himself right into the wood chipper!" for `task.error` is priceless.

---

## TIER 2: Strong Candidates (on D-drive)

### Comedy Classics
| Movie | Pack concept | Characters |
|---|---|---|
| Airplane! (1980) | 1-2 packs | Leslie Nielsen (Rumack), Lloyd Bridges (McCroskey) — "Don't call me Shirley", "I picked the wrong week to quit..." |
| Blazing Saddles (1974) | 1-2 packs | Gene Wilder (Waco Kid), Cleavon Little (Bart), Harvey Korman (Hedley Lamarr) |
| Spaceballs (1987) | 2 packs | Dark Helmet (Rick Moranis), Lone Starr — "I see your Schwartz is as big as mine" |
| Young Frankenstein (1974) | 1-2 packs | Gene Wilder, Igor (Marty Feldman), Frau Blucher |
| Robin Hood: Men in Tights (1993) | 1 pack | Ensemble — Mel Brooks comedy |
| DodgeBall (2004) | 1-2 packs | Patches O'Houlihan (Rip Torn), White Goodman (Ben Stiller) — "If you can dodge a wrench..." |
| Step Brothers (2008) | 1-2 packs | Brennan (Ferrell), Dale (Reilly) — "Did we just become best friends?" |
| Talladega Nights (2006) | 1-2 packs | Ricky Bobby (Ferrell) — "If you ain't first, you're last" |
| Tommy Boy (1995) | 1-2 packs | Tommy (Chris Farley), Richard (David Spade) |
| Happy Gilmore (1996) | 1 pack | Happy (Adam Sandler) — "The price is wrong, bitch" |
| Billy Madison (1995) | 1 pack | Billy (Adam Sandler) — "Everyone is now dumber for having listened to it" |
| Wayne's World (1992) | 1-2 packs | Wayne, Garth — "Excellent!", "Party on!" |
| Old School (2003) | 1-2 packs | Frank the Tank (Will Ferrell) — "We're going streaking!" |
| Tropic Thunder (2008) | 2 packs | Kirk Lazarus (RDJ), Tugg Speedman (Stiller), Les Grossman (Cruise) |
| Superbad (2007) | 1-2 packs | McLovin, Seth, Evan |
| Dumb and Dumber (1994) | 1-2 packs | Lloyd (Jim Carrey), Harry (Jeff Daniels) — "So you're telling me there's a chance" |
| Ace Ventura: Pet Detective (1994) | 1 pack | Ace (Jim Carrey) — "Alllrighty then!" |
| Liar Liar (1997) | 1 pack | Fletcher (Jim Carrey) — "THE PEN IS BLUE!" |
| The Mask (1994) | 1 pack | Stanley/The Mask (Jim Carrey) — "Somebody stop me!" |
| Idiocracy (2006) | 1 pack | President Camacho (Terry Crews) — "Shit. I know shit's bad right now." |
| Borat (2006) | 1 pack | Borat — "Very nice!", "Great success!" |

### Action/Drama Quotables
| Movie | Pack concept | Characters |
|---|---|---|
| Pulp Fiction (1994) | 2-3 packs | Jules (Samuel L. Jackson), Vincent (Travolta), The Wolf — "Say 'what' again!" |
| Die Hard (1988) | 1-2 packs | John McClane (Willis), Hans Gruber (Rickman) — "Yippee-ki-yay" |
| Full Metal Jacket (1987) | 1-2 packs | Gunnery Sgt. Hartman (R. Lee Ermey) — pure drill sergeant energy |
| Predator (1987) | 1 pack | Dutch (Schwarzenegger) — "Get to the chopper!" |
| Terminator 2 (1991) | 1 pack | T-800 — "I'll be back", "Hasta la vista, baby" |
| The Dark Knight (2008) | 1-2 packs | Joker (Heath Ledger), Batman — "Why so serious?" |
| Scarface (1983) | 1 pack | Tony Montana — "Say hello to my little friend!" |
| The Wolf of Wall Street (2013) | 1-2 packs | Jordan Belfort (DiCaprio) — "I'm not leaving!" |
| Inglourious Basterds (2009) | 2 packs | Aldo Raine (Pitt), Hans Landa (Waltz) |
| Django Unchained (2012) | 1-2 packs | Django, Dr. King Schultz (Waltz), Calvin Candie (DiCaprio) |
| GoodFellas (1990) | 1-2 packs | Tommy (Pesci), Henry (Liotta) — "Funny how?" |
| Glengarry Glen Ross (1992) | 1-2 packs | Blake/Alec Baldwin, Ricky Roma — "Coffee is for closers!" |
| The Shining (1980) | 1 pack | Jack Torrance (Nicholson) — "Here's Johnny!" |
| Braveheart (1995) | 1 pack | William Wallace (Gibson) — "FREEDOM!" |
| The Princess Bride (1987) | 2 packs | Inigo Montoya, Vizzini — "Inconceivable!" (NEEDS MOVE) |
| Jerry Maguire (1996) | 1 pack | Jerry/Rod Tidwell — "Show me the money!" |
| Forrest Gump (1994) | 1 pack | Forrest — "Life is like a box of chocolates" |

### Sci-Fi/Horror/Cult
| Movie | Pack concept | Characters |
|---|---|---|
| Galaxy Quest (1999) | 1-2 packs | Commander Taggart, Alexander Dane — "Never give up, never surrender!" |
| Army of Darkness (1992) | 1 pack | Ash (Bruce Campbell) — "Hail to the king, baby" |
| RoboCop (1987) | 1 pack | RoboCop — "Dead or alive, you're coming with me" |
| They Live (1988) | 1 pack | Nada (Roddy Piper) — "I came here to chew bubblegum..." |
| Shaun of the Dead (2004) | 1 pack | Shaun/Ed — "You've got red on you" |
| Hot Fuzz (2007) | 1 pack | Angel/Danny — "The greater good" |
| Zombieland (2009) | 1 pack | Tallahassee (Woody Harrelson) — "Nut up or shut up" |
| The Matrix (1999) | 1-2 packs | Neo, Morpheus, Agent Smith |
| Demolition Man (1993) | 1 pack | John Spartan (Stallone) / Simon Phoenix (Snipes) |
| Highlander (1986) | 1 pack | Connor MacLeod — "There can be only one!" |
| Scott Pilgrim vs. the World (2010) | 1 pack | Scott Pilgrim — "I'm in lesbians with you" |
| Big Trouble in Little China (1986) | 1 pack | Jack Burton (Kurt Russell) |

### Ensemble/Animated
| Movie | Pack concept | Characters |
|---|---|---|
| Monty Python: Holy Grail (1975) | 2-3 packs | Knights, Tim the Enchanter, French soldiers (NEEDS MOVE) |
| Monty Python: Life of Brian (1979) | 1-2 packs | Brian, various (NEEDS MOVE) |
| Caddyshack (1980) | 2 packs | Carl Spackler (Murray), Judge Smails (Ted Knight), Al Czervik (Dangerfield) (NEEDS MOVE) |
| Napoleon Dynamite (2004) | 1-2 packs | Napoleon, Uncle Rico (NEEDS MOVE) |
| South Park: BLU (1999) | 1-2 packs | Cartman, various |
| Clerks (1994) | 1 pack | Dante, Randal — "I'm not even supposed to be here today!" |
| Animal House (1978) | 1 pack | Bluto (Belushi), Dean Wormer |
| Planes, Trains and Automobiles (1987) | 1-2 packs | Del Griffith (Candy), Neal Page (Martin) |
| The Godfather (1972) | 1-2 packs | Vito, Michael (NEEDS MOVE) |

---

## TIER 3: Fun Stretch Goals

| Movie | Why it's interesting |
|---|---|
| Dead Poets Society (1989) | "O Captain, my Captain!" Robin Williams inspirational |
| The Truman Show (1998) | "Good morning, and in case I don't see ya..." |
| Trading Places (1983) | Eddie Murphy / Dan Aykroyd |
| Coming to America (1988) | Eddie Murphy multiple characters |
| The Usual Suspects (1995) | Keyser Soze reveal |
| Se7en (1995) | "What's in the box?!" |
| Reservoir Dogs (1992) | Mr. Pink, Mr. Blonde |
| O Brother, Where Art Thou! (2000) | "We're in a tight spot!" |
| This Is the End (2013) | Meta celebrity chaos |
| Pineapple Express (2008) | Stoner action comedy |
| Hot Rod (2007) | Andy Samberg physical comedy |
| Forgetting Sarah Marshall (2008) | Jason Segel/Russell Brand |
| Wedding Crashers (2005) | Vince Vaughn rapid-fire |
| Bruce Almighty (2003) | Jim Carrey as God |
| Me, Myself & Irene (2000) | Jim Carrey split personality |
| Kick-Ass (2010) | Hit-Girl, Big Daddy |
| Boondock Saints (1999) | "And shepherds we shall be..." |
| Grandma's Boy (2006) | Programmer comedy |
| Strange Brew (1983) | Bob and Doug McKenzie, eh |
| Hot Tub Time Machine (2010) | "Great White Buffalo" |
| Black Dynamite (2009) | "I threw that shit before I walked in the room!" |

---

## Summary

| Status | Movies | Packs |
|---|---|---|
| Published | 7 | 20 |
| In Progress | 2 | 6 |
| Tier 1 (user-requested) | 4 | 8 |
| Tier 2 (strong candidates) | 40+ | 60-80 |
| Tier 3 (stretch) | 20+ | 20-30 |
| Needs Move to D-drive | 8 | 12-18 |
| **Total potential** | **80+** | **120-150+** |
