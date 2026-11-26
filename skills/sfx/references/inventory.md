# What sound goes where

Every row is an event with a time. Get that time before choosing the sound (`timing.md`).

The usual moments by medium, with the route for each. "kit:" names a category of the free kit (`sfx.py find --categories`); a bare name is a recipe or transform (`sfx.py list <name>`); "fetch" means a real recording from Commons.

## Video: tutorial, explainer, essay

| Moment | Sound | Route |
|---|---|---|
| Hook, title card | A short riser into one impact on the title | `riser_hit lead=1.5` |
| Channel or logo sting | A short tonal motif, the same every video | `logo_sting` tuned to the theme, or kit: logo-stings |
| Chapter titles, section changes | A soft whoosh, the same one each time | `whoosh` (0.4 to 0.8 s), kit: whooshes, swipes |
| Cuts with movement, whip pans | A fast whoosh peaking on the cut | `whoosh seconds=0.3`, kit: whooshes (fast) |
| Text or graphic appears | A pop on the first visible frame | `pop`, kit: pops, appear-and-vanish |
| Text or graphic slides in | A swish ending in a pop as it settles | `swish_pop lead=<length of the move>` |
| List items appear one by one | A pop per item, each a step higher | `pop_run times=<each item's time>` |
| Text or graphic leaves | A pop falling in pitch | `pop direction=-1` |
| Arrow, underline, drawing on | A swipe or pencil stroke | kit: writing-and-drawing, swishes-and-zips |
| Zoom, scale, spin | A short zip | `whoosh` (sharp), kit: bounce-spin-zoom, shape-changes |
| Cursor click in a screen recording | A quiet click per click | `click`, kit: interface |
| Typing on screen | Key ticks with human timing | `typing seconds=<time the text takes>`, kit: keyboard |
| Steps 1, 2, 3 | The same blip, a step higher each time | `pop` or `notify` with rising `pitch`/`root` |
| Step done, correct | A rising chime | `chime`, kit: notifications (success) |
| Error, warning, "don't do this" | A dull buzz or a tense sting | `error`, `stinger chord=dim`, kit: notifications (error, failure) |
| Reveal, result, before/after | A chime, shimmer and soft hit together | `reveal`, kit: shimmers |
| Time skip, sped-up footage | A whir, or a clock | `whir`, kit: time |
| Rewind, "go back" | A falling whir | `whir direction=-1` |
| Numbers counting up, data | Blips that climb and land on a chime | `count_up seconds=<time it counts>`, kit: data, money |
| Joke | Record scratch, boing, rimshot | fetch |
| Slow motion, dramatic pause | A build that falls away, or a sub drop alone | `riser_drop`, `sub_drop` |
| End card, subscribe | A soft sting, a pop on the button | `stinger chord=major`, `pop` |
| Under narration | A quiet bed | `drone_from`, then `loop` |

## Podcast and audio-only

| Moment | Sound | Route |
|---|---|---|
| Intro and outro sting | A short tonal motif | `stinger`, kit: logo-stings |
| Segment change | A whoosh, or a soft chime | `whoosh`, `notify` |
| Emphasis, a reveal | A low hit, quiet | `impact weight=0.4 tail=0.8` |
| Scene setting in a story | Real ambience and foley | fetch; `drone_from` + `loop` for beds |
| Phone, message, door in a story | The real thing | fetch, kit: phone, everyday-props |

With no picture, every sound must read on its own: prefer recognisable real sounds, fewer of them, and leave room around speech.

## Game

| Moment | Sound | Route |
|---|---|---|
| Menu move, select, back | Blip, click, soft pop | `retro kind=blip`, `click`, `pop` |
| Pickup, coin, point | A bright two-note | `retro kind=coin`, `chime pattern=fifth` |
| Jump, dash | A rising chirp, a short whoosh | `retro kind=jump`, `whoosh seconds=0.2` |
| Shoot, zap | A falling chirp | `retro kind=laser` |
| Hit, damage | A thud with a snap | `retro kind=hit`, `impact weight=0.3 tail=0.3` |
| Explosion | Noise that falls in pitch, a boom | `retro kind=explode`, `impact`, `boom_from` a real hit |
| Power-up, level up | A rising run of notes | `retro kind=powerup`, `chime pattern=arp` |
| Win, lose | A major or minor sting | `stinger chord=major`, `stinger chord=minor`, `downlifter` |
| Footsteps, doors, weapons, creatures | Real recordings, many takes | fetch, then `pitch` and `--variations` |
| Ambience, engine, wind | A seamless loop | fetch or `drone_from`, then `loop` |

Games repeat sounds hundreds of times: always ship several takes of anything frequent, render `--mono` for sounds placed in space, and `--level peak` so the engine sets the volume.

## Website and app

| Moment | Sound | Route |
|---|---|---|
| Button, toggle, tab | A quiet click | `click soft=0.6`, kit: interface |
| Message in, message out | A two-note ping, up or down | `notify`, kit: notifications (message) |
| Success, saved, sent | A short chime | `chime pattern=fifth ring=0.3` |
| Error, invalid | A soft low double note | `error rough=0.2` |
| Something appears, dismisses | A pop up, a pop down | `pop`, `pop direction=-1` |
| Loading done, refresh | A soft tick or shimmer | `tick`, `sparkle seconds=0.5` |

Interface sounds are heard thousands of times. Keep them under 0.3 s, soft, and few; most actions should make no sound at all.

## Trailer and cinematic

| Moment | Sound | Route |
|---|---|---|
| Build and hit | A long riser or a reverse swell into a big impact | `riser_hit lead=4 weight=1 tail=3.5`, `swell_hit lead=2` |
| Hit on the cut, alone | A big impact with a long tail | `impact weight=1 tail=3.5`, kit: cinematic-hits |
| After the hit | Silence, a sub drop or a downlifter | `sub_drop`, `downlifter` |
| Biggest hit of the piece | A slam with a held low rumble | `impact boom=1 weight=1 tail=3`, or kit: `cinematic-slam-big`, `boom-hit-medium` |
| Title | A stinger over the tail of the hit | `stinger` |
| The biggest reveal | A braam, once | `braam`, or `braam lead=1.2` to rise into it |
| Fly-through, something crossing the frame | A pass-by, closest point on the frame it crosses | `pass_by` (slow sweep), or `pass_by seconds=0.45 speed=0.9 weight=0.2` (quick swing) |
| Tension bed | A dark drone | `drone_from` |

## More moments

| Moment | Sound | Route |
|---|---|---|
| Hard digital scene change, "system error" | A glitch running up to the cut | `glitch_cut`, `glitch`, `static seconds=0.3` |
| "Let's go back", replay | A rewind to a dead stop | `rewind lead=<length of the rewinding picture>` |
| "Two hours later", sped-up process | A whir with a speeding clock | `time_skip seconds=<length of the section>` |
| "3, 2, 1, go", a timer ending | Beeps on exact times | `countdown gap=1` |
| Waiting, a deadline | A clock | `clock gap=1` |
| Tension before a decision | A heartbeat, speeding up over the scene | `heartbeat bpm=70`, then `bpm=110` (`pitch=58` if it must be heard on a phone) |
| Warning, breaking news, a timer going off | An alarm, short | `alarm` |
| A phone call in a story | Real phone tones | `phone kind=ring`, `kind=digits` |
| Tech and AI: scanning, switching on, appearing | Sci-fi machines | `scifi kind=scan`, `power_up`, `teleport` |
| A joke, a mistake played for laughs | Boing, falling slide whistle, bonk | `cartoon` |
| A place under a scene; room under narration | A storm, a dramatic turn | Thunder, placed after the flash (0.3 s overhead, 3 s per kilometre), over looping rain and wind | `thunder`, laid over `rain` and `wind` with `lay` |
| A blast, "mind blown", a game explosion | An explosion, the shock on the frame | `explosion size=<0-1>`, `retro kind=explode` for 8-bit |
| Someone walking | Footsteps, a step on each footfall | `footsteps surface=<wood, concrete, dirt>` (a mark per step); other ground: fetch |
| A drink poured | Pouring, ending as the glass fills | `pour seconds=<length>` |
| Something breaks; a dripping tap | The real thing | fetch (synthesized glass and drips were rejected by ear) |
| A brook close by | A loop | `stream` |
| A short circuit | A spark | `spark` |
| Outdoors: a beach, a night | A loop | `ocean`, `crickets` (`crickets count=1` for an awkward silence) |
| A looping ambience | `rain`, `fire`, `wind`, `room` (room tone under a voice), `bed kind=hum` for machines |

## Sounds with no recipe yet

Footsteps, water (drops, pouring, streams), glass, engines and vehicles, weapons, crowds, animals, birds, doors, magic spells, musical instruments. For these: a fetched recording (`find`), the kit, or say so. Add a recipe when one is needed twice.
