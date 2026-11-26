---
name: sfx
description: Make any non-musical, non-speech sound for a project, locally with code, and put it on the exact frame. No API keys, no models, no accounts. Use this whenever the user wants a sound on a moment or under a scene, even when they never say "sound effect": "a build-up and a hit on the title", "a pop on each bullet", "what sound should go on this lower third", "add typing sounds", "rain under the narration", "a thunder clap", "a whoosh on the cut", "make the video feel more polished". It makes hits, booms, risers, braams, whooshes, stingers, sub drops, clicks, pops, chimes, notifications, error buzzes, sparkles, typing, countdowns, alarms, phone tones, glitches, retro game and sci-fi sounds, cartoon sounds, heartbeats and clocks; ambiences that loop (rain, fire, wind, room tone, sea, crickets, vinyl crackle); a stream; thunder, explosions, sparks and electrical arcing, liquid pouring, footsteps on wood, concrete or dirt. For real objects it cannot synthesize well (footsteps on other ground, glass, dripping, doors, engines, animals) it finds a free recording with no key. Also use it when the user says SFX, sound design, foley, UI sounds or game sounds; when sounds must be synced to cuts, titles, animation or music, tuned to a key, cut to a length or made in variations; to edit an existing sound (reverse, pitch, stretch, loop); or to get a free sound from the web, including when they name a site such as Freesound. Not for music or songs, speech or voices, word timestamps, or model-generated sound (ElevenLabs and the like).
---

# SFX

One script, `scripts/sfx.py`, run with uv. It needs numpy and scipy (uv fetches them) and nothing else: no key, no model, no account. Only `find` and `fetch` touch the network. ffmpeg is optional, for reading files that are not WAV.

```
uv run scripts/sfx.py list                      every recipe and transform
uv run scripts/sfx.py list riser                when to use it, its level and its parameters
uv run scripts/sfx.py make riser seconds=2 root=A2
uv run scripts/sfx.py make tick --variations 6 --vary 0.15
uv run scripts/sfx.py make rain seconds=12 --events   the sidecar lists every drop's time, to draw the picture from it
uv run scripts/sfx.py make riser_hit lead=1.5   a compound: the hit is exactly 1.5 s into the file
uv run scripts/sfx.py lay cues.json             put sounds on a timeline, each sync point on its event
uv run scripts/sfx.py fx boom_from door.wav drop=-18
uv run scripts/sfx.py find whoosh               free sounds, no key (a CC0 kit, Wikimedia Commons)
uv run scripts/sfx.py fetch kit:whoosh-fast-hard
uv run scripts/sfx.py check sfx/*.wav           measurements and flags
uv run scripts/sfx.py spec sfx/riser_v001.wav   a spectrogram picture you can Read
uv run scripts/sfx.py compare mine.wav real.mp3  how a made sound differs from a real recording, in numbers and words
uv run scripts/sfx.py audition sfx/             a local page for the user to listen, keep and kill
```

Run it from the project root. Output goes to `./sfx/` (or `--out`) as `name_v001.wav` (48 kHz, 24-bit, stereo) with a `name_v001.json` sidecar holding the recipe, parameters, seed and measurements. The same seed and parameters give the same sound.

## Rules

0. **Timing comes first.** A sound on the wrong frame is a wrong sound. Before making anything, get the time of each event from the project (frame numbers, cut times, word times), never from a guess. Fit each sound's length to the time available, and place it by its sync point: file start = event time minus `sync.at`. Every `make` prints the sync point and writes it to the sidecar; `lay` does the placing. Read `references/timing.md` before placing anything. Don't render a lead-in (a riser, a swell, a whoosh into something) on an assumed time: its length depends on the event's time and the room before it, so get those first.
1. **You cannot hear. The user can.** `check` and `spec` find faults; they do not tell you a sound is good. Never call a sound good, and never pick between takes for the user. Make a few candidates that differ in a real way, build the `audition` page, give the user its `file://` link and let them choose. Tell them in one line per group what they are comparing and what to listen for; a pile of unexplained sounds gets rejected.
2. **Never overwrite or delete a sound.** Every render gets the next version number. Fetched files are kept. Don't pass `ffmpeg -y`.
3. **Synthesis is the main route.** Make the sound with a recipe or a compound. Fetch a sound when the user asks for one, or when the sound is a real, recognisable thing that no recipe covers. Edit an existing sound when the user asks.
4. **Fit real-world sounds to a real recording before the user hears them.** When you build or tune anything that exists in the world (weather, fire, water, machines, crowds), fetch a recording of it, run `compare`, and fix what it reports. Then put the recording first on the audition page. Check the recording for other sounds first (a crowd, traffic). Tuning by reasoning alone, and building from a published model alone, both failed here; `references/ambience.md` has the method and what it found.
5. **Read `list <name>` before using a recipe.** It says when the sound is used, how it should sync to picture and what each parameter does. Unknown parameters are errors.
6. **Record where fetched sounds came from.** `fetch` writes the source page, author and licence into the sidecar. Don't filter by licence and don't lecture: record it, and tell the user in one line when a fetched sound needs attribution (the sidecar says `attribution_required`).
7. **Search the web slowly.** Wikimedia rate-limits anonymous tools: a few requests a minute, and it sometimes refuses downloads for a while (the Internet Archive is the fallback, `references/sources.md`). Don't loop over searches. The kit's catalogue is cached after the first use and then searches offline.
8. **Every recipe renders close up, and there is no working way yet to move one further away.** A first distance model (low-pass, blur, narrowing, more reverb) was rejected by ear: a far stream sounded muffled and close at once, and footsteps down a hall drowned in echo. Do not fake distance with a low-pass or with the `room` transform. If a sound must be far off, say that the skill cannot do that yet and lower its level in the mix. This is an open problem (`CONTRIBUTING.md` in the repository).
9. Flags from `check` mean "a person should listen for this", not "rejected". CLICK is expected on sounds made of sudden edges (`glitch`, `static`, `clock`, crackling fire). Fix the ones that are plainly faults (CLIP, CUT_HEAD, CUT_TAIL, DC, PHASE, LEAD_SILENCE on a hit) before the user hears the sound.

## Which route

| The need | Route |
|---|---|
| One event: a click, pop, chime, whoosh, hit, riser, stinger | `make` a recipe. Pitched recipes take `root=` as Hz or a note name (`A2`, `C#4`); tune them to the music. |
| A lead-in and its payoff, or several sounds that belong to one moment | `make` a compound (below). One file, one sync point, exact to the sample. |
| A real, recognisable thing that code does badly: a door, glass, footsteps, water, an animal, a crowd | `find <words>`, then `fetch` (no key needed). Say plainly that it is a found recording, and what it is, before the user hears it. Quality on Wikimedia Commons is uneven, so offer two or three. |
| A stock version of a standard video or UI sound, when the user wants one or a recipe was rejected | `find <words> --source kit`, then `fetch`: 320 designed CC0 sounds with sync points. |
| The user asks to change a sound they have: reverse, pitch, stretch, loop, add a room, turn it into a riser, boom, whoosh or drone | `fx` a transform (`list` shows them). Only on request: transformed recordings are hit and miss, so don't offer them unprompted. |
| Speech, music, or a sound nothing here can make or find | Say so. Other skills cover speech and music; a model-generated effect is the user's call (it may cost money). |

## Compounds

A compound is several recipes on one timeline, built around one sync point. `lead` is the time before the event; the event is then exactly `lead` seconds into the file. Use one instead of placing a riser and a hit separately: two files placed by hand drift apart.

| Compound | The moment | Sync point |
|---|---|---|
| `riser_hit` | The one big reveal: a title card, a before/after, the main section starting | `hit`: the cut, or the frame the title lands |
| `riser_drop` | A reveal that falls away instead of banging: slow motion, a serious turn | `drop`: the cut |
| `swell_hit` | A harder lead-in (the hit's tail reversed): trailers, tech, a dramatic word | `hit` |
| `whoosh_hit` | Something flies in and lands: a title slam, a card dropping, a punch-in zoom | `hit`: the frame it stops |
| `swish_pop` | Something small slides in and settles: text, icons, lower thirds. Safe to repeat | `pop`: the frame it settles |
| `reveal` | "Here it is": the result, the finished thing | `reveal`: the first frame it is visible |
| `logo_sting` | The channel ident, the same in every video | `hit`: the frame the logo is fully formed |
| `pop_run` | List items appearing one by one (`times=` takes each item's time) | `pop1`, `pop2`, ... |
| `typing` | Text typing onto the screen (`seconds=` the time it takes) | `start` and `enter` |
| `count_up` | A number running up to its value | `land`: the frame the number stops |
| `countdown` | "3, 2, 1, go": beeps on exact times | `go`, and `beep1`, `beep2`, ... |
| `glitch_cut` | A hard digital scene change: a stutter that runs up to the cut and stops dead on it | `cut` |
| `rewind` | "Let's go back": tape winding down to a dead stop | `stop`: the frame the rewinding stops |
| `time_skip` | "Two hours later": a whir and speeding clock, landing on a pop | `land`: the frame normal speed resumes |

## Other recipes

Beyond the core video and UI sounds (`list` shows all, `list <name>` the details):

- **Signals:** `alarm` (beep, siren, two-tone, klaxon), `phone` (dial tone, ring, busy, keypad digits with a mark per digit).
- **Broken electronics:** `static` (lost signal), `glitch`.
- **Sci-fi:** `scifi` (zap, teleport, scan, power up, power down).
- **Cartoon:** `cartoon` (boing, falling slide whistle, bonk).
- **Pulses on exact times:** `heartbeat` (a mark per beat, at a set tempo), `clock` (a mark per tick).
- **Ambiences (seamless loops):** `rain`, `fire` (a campfire), `wind` (with an optional howl), `room` (room tone, very quiet on purpose), and `bed kind=hum` (electrical hum). Repeat the loop for the length of the scene and fade it in and out in the edit. Not frame-critical; everything else is. Rain, fire and wind were fitted to field recordings (`references/ambience.md`).
- **Big events:** `thunder` (a low roll in uneven surges with a long decay) and `explosion` (a full-range bang, a sinking low body and the bang's echo). For a storm, loop `rain` and `wind` and lay `thunder` on top with `lay`.
- **Trailer sounds:** `braam` (the low brass blast; `lead` makes it rise into the hit) and `pass_by` (a heavy whoosh whose pitch falls as it passes: a slow sweep by default, `seconds=0.45 speed=0.9 weight=0.2` for a quick swing).
- **More real-world sounds:** `ocean` (the sea on a beach, a loop), `crickets` (a loop; `count=1` for the lone cricket of an awkward silence), `spark` (one snap), `arc` (electrical arcing), `pour` (liquid into a vessel; `full` mark), `vinyl` (a silent record's crackle, a loop), `footsteps` (wood, concrete or dirt; a mark per step), `stream` (a close brook, a loop). Footsteps on grass, gravel or snow, breaking glass, an engine and water drops have been tried more than once and failed by ear: use a found recording for those.

Timing, frames, cue sheets: `references/timing.md`. What works generatively and what doesn't, with reasons: `references/sound-design.md`. What sound goes where in a video, podcast, game or app: `references/inventory.md`. Where an agent can get sounds with no key, and which sites block it: `references/sources.md`. How the ambiences are built and how to build another: `references/ambience.md`.

## The workflow

1. **List the moments** that need sound, each with its exact time or frame, the time available before it (since the last cut or the end of the last spoken line), and how big it should feel. Get the frame rate. A sound marks a change on screen; no change, no sound. `references/inventory.md` has the usual moments by medium.
2. **Choose the sound** for each (tables above). Reuse: one sound per kind of event, everywhere in the piece.
3. **Make candidates to fit.** Set `lead`, `seconds` or `times` from the times in step 1, not from the defaults. For a pitched sound, ask for or work out the music's key and pass `root=`. For anything repeated (clicks, footsteps, coins), render `--variations 5 --vary 0.15` and rotate the takes; `--vary` leaves timing alone.
4. **Check them.** `check` every file; `spec` and Read the picture when the shape matters (a riser must grow to its end, a hit must be at the very start, a whoosh must peak where the motion peaks). Fix faults. For a real-world texture, `compare` it with a recording.
5. **Audition.** `audition <folder>` and give the user the link. They press K, M or X per sound and can copy the verdicts back to you. Wait for them.
6. **Place the keepers.** Write a cue sheet (each file and the time or frame of its event) and run `lay`; it puts each sync point on its event and writes one track to drop at 0:00. Read its report against your list of moments. Sounds are rendered at mix-ready levels on one scale (see `list <name>`), so they sit together and under a voice without level changes; `--level peak` gives full-scale files instead (game engines usually want those).
7. **The user watches it.** Timing that measures right can still feel wrong against the picture. Move things by frames on their word.

## Known-good settings

Everything below was tuned by ear, most of it over several listening rounds. A recipe is known-good at the settings listed (the defaults, unless stated); other settings are candidates, so say so and audition them.

| Sound | Known-good | Keep away from |
|---|---|---|
| `click`, `tick`, `pop`, `chime`, `notify`, `error`, `sparkle` | Defaults (the click is the soft one) | A sharp, bright click (`pitch=2400 soft=0.3`) |
| `riser`, `sub_drop`, `stinger`, `whir`, `downlifter` | Defaults; `downlifter` is tone only and deep | A noisy downlifter |
| `impact` | The default (soft, deep, no crack); `boom=0.5` to `1` for a slam; `boom=1 weight=1 tail=3` for the biggest | `bright` or `punch` above about 0.3: tinny, like a toy |
| `whoosh` | The default (low and heavy) | `hi` above about 2500 or `sharp` high: too much in the highs |
| `riser_hit`, `swell_hit`, `whoosh_hit` | Defaults (all land on the slam); `riser_hit lead=4 weight=1 tail=3.5` for a trailer build | `boom=0` after a lead-in: the hit turns into a tom drum |
| `riser_drop`, `pop_run`, `count_up`, `time_skip`, `countdown` | Defaults | |
| `swish_pop` | Default and tight (`lead=0.12 swish=0.3`) | A loud swish (`swish=0.9`) |
| `reveal`, `logo_sting` | Defaults (light reveal; dark minor sting) | Added thud, glitter or a major chord |
| `typing` | Default (fast, thin, no heavier last key) | Slow and deep |
| `glitch`, `glitch_cut`, `static` | Defaults | |
| `rewind` | Default (stops dead) | `stop` above 0 |
| `alarm`, `phone`, `scifi`, `cartoon`, `retro` | Every kind that exists | |
| `heartbeat`, `clock` | Defaults; `heartbeat pitch=36 depth=1`; `clock pitch=1100`, `clock gap=0.25 pitch=3400` | |
| `rain` | Default, `amount=0.15 drops=0.7`, `amount=0.95 drops=0.2`, `dull=0.8` | |
| `fire` | Default | `crackle` above about 0.7, `pops` above 0.5 |
| `wind` | `howl=0` (default), or a clear howl (`howl=0.6` to `0.9`) | A faint howl: it is heard as a fault in the sound |
| `room`, `bed kind=hum` | Defaults | Turning room tone up: it is quiet on purpose |
| `thunder`, `explosion` | Defaults | |
| `braam` | Default, `lead=1.2`, a stab (`seconds=0.3 tail=2`), smooth (`growl=0.15 drive=0.15`) | |
| `pass_by` | Default (slow heavy sweep), `seconds=0.45 speed=0.9 weight=0.2` (quick swing) | About 1 s at middling speed: it sounds as if it is inside a tube |
| `ocean` | Default; `amount=0.9 foam=0.8` for heavy surf | |
| `crickets` | `count=1`, 4 and 6 | |
| `spark` | Default | |
| `arc` | Default, `amount=0.1` (steady), `amount=1` (sputtering), `mains=50` | |
| `pour` | Default, `seconds=7 size=1` (a jug); slightly synthetic | |
| `vinyl` | `wear=0.1` to `0.15` (the default) | `wear` near 0.9: harsh |
| `footsteps` | `surface=wood`; `surface=concrete` and `surface=dirt` are usable but weaker | Grass, gravel, snow: failed, not in the recipe |
| `stream` | Default: a very close stream | `bright=1`: harsh and still close. There is no far stream |

Not tuned by ear: the transforms (`fx`) and found recordings from Commons. Tried more than once and not in the skill: footsteps on grass, gravel and snow, breaking glass, an engine, water drops. Do not offer them as synthesized sounds; fetch a recording.

### What listening has taught

These held across many rounds. Apply them to anything new.

- **Dark, low and unpitched reads as cinematic; bright and pitched reads as a toy.** A sine with a fast pitch drop is a drum. A ringing sine is a note, a chime or a laser.
- **Steady noise is static.** A place is recognised from many separate events over a moving bed, never from a band of noise.
- **No patterns.** Evenly spaced surges sound like a clock, three equal knocks like triplets, steady chirps like clockwork. Real events cluster, pause and vary, and each has its own place in width and depth.
- **A faint layer is heard as a fault.** A howl too quiet to be a howl sounds like an artifact. A layer is clearly there or it is out.
- **Endings matter.** A sound stopped while still audible is heard as cut off; let it fall to silence.
- **Listeners count and compare.** When the user describes a rhythm or a balance, measure the reference the same way (list the events, in order) before changing anything.
- **Fitted to a recording, it passed; built from a model alone, it failed.** Nearly every time (arcing and vinyl passed from research alone).
- **Look at the spectrograms side by side.** Band statistics and an AI listener both passed attempts at glass, footsteps and a stream that a person rejected at once, and one look at the two spectrograms showed why (a real bottle break is separate bounces with thin ringing lines; the attempt was one smear of noise). `spec` the reference and the candidate and Read both before any audition.
- **A reference can be bad.** Free recordings vary a lot. Ask the user which reference they accept before fitting to it.

## What lives where

- `scripts/sfx.py` (command line), `sfx_recipes.py` (the recipes and their levels), `sfx_compound.py` (compounds), `sfx_signals.py` (signals, glitch, sci-fi, cartoon, pulses, hum), `sfx_ambience.py` (rain, fire, wind, room), `sfx_events.py` (thunder, explosion), `sfx_cinematic.py` (braam, pass_by), `sfx_world.py` (spark, crickets, ocean), `sfx_more.py` (arc, pour, vinyl), `sfx_measured.py` with `data/` (footsteps, stream: built from loudness curves measured on reference recordings), `sfx_fx.py` (transforms), `sfx_dsp.py` (building blocks: oscillators, noise, filters, reverb, stretch, granular, loudness, WAV I/O), `sfx_check.py` (measurements, flags, spectrogram), `sfx_sources.py` (find and fetch).
- `tests/test_sfx.py`: `uv run tests/test_sfx.py`, about 30 s, no network.
- To add a recipe: write a function in `sfx_recipes.py` with the `@recipe` decorator (family, what it is, when to use it, parameters with their meaning), give it a level in `LEVELS`, end it with `d.finish(...)`, return `(signal, {mark: seconds})` if its sync point is not the first sample, and compare it with a reference sound (`compare`, `check`, `spec`) before the user hears it. Build from layers (low, body, attack, tail), one job per layer.
