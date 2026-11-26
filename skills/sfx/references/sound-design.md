# Sound design: what works, and why

Working notes for an agent that cannot hear. Opinions here come from a side-by-side comparison with the wyzowl sfx-kit (measurements and spectrograms) and from standard practice. What has been tuned by ear is listed under "Known-good settings" in SKILL.md.

## What code does well, and what it doesn't

| Sound | Synthesis | Why | Do this instead when it's weak |
|---|---|---|---|
| UI: click, pop, tick, toggle | Good | Tiny sounds are a few damped partials and a noise snap; there is little texture to get wrong. | |
| Chime, notification, success, error | Good | Pitched and simple; tuning to the key is something only code can do. | |
| Riser, downlifter, sub drop | Good | They are a filter sweep, a pitch glide and an envelope: pure control curves. | `riser_from` on the project's own audio for character. |
| Whoosh, swish | Good to fair | Filtered noise with a swell is the textbook method. It lacks the grain of real air and cloth, and turns hissy when the sweep goes above about 2.5 kHz; low and heavy works. | `whoosh_from` on a real texture. |
| Stinger, logo hit | Fair | The chord is easy; a memorable sting is composition, which is taste. | Offer several and let the user pick. |
| Sparkle, shimmer | Good | Scattered high bells. | |
| Retro game sounds | Good | They were synthesized to begin with. | |
| Drone, tonal ambience, hum | Good | Slow filtered noise and smeared tones. | `drone_from` any sound. |
| Rain, fire, wind, room tone | Fair to good, when fitted to a recording | Filtered noise alone is heard as static. They work as many separate events over a moving bed, with band levels copied from a real recording (`ambience.md`). | Fetch a recording when a specific place matters. |
| Cinematic impact, boom | Fair | The sub and the tail are easy. The first 50 ms of a real hit (wood, metal, air) is complex, and a synthetic attack sounds synthetic: a pitched knock or a bright crack reads as a toy drum. Keep it dark, unpitched and low, with a held rumble between 60 and 170 Hz. | The kit's `cinematic-slam-big`, or `boom_from` a real slam: real attack, synthetic sub and tail. |
| Real objects: glass, doors, footsteps, cloth, paper, water drops and pouring, engines | Poor (tried from physical models and rejected by ear) | The ear knows these from life. A model needs the physics of each material to pass. | Fetch a recording. |
| Animals, voices, crowds | No | | Fetch a recording. |
| Comedy: record scratch, boing, slide whistle | Poor to fair | Recognisable recordings. | Fetch. |

## How a sound is built

- **Layers by job.** Low (the weight: a sine or sub), body (the mid-range that every speaker can play), attack (the first few milliseconds: a click, a crack), tail (the room). One layer per job. Two layers fighting for the same band make mud.
- **The attack decides what it is; the tail decides how big it is.** Shorten the tail and a boom becomes a thud. Soften the attack and a click becomes a tap.
- **Real texture, designed shape.** The strongest results come from a real recording carrying the texture while code supplies the shape (envelope, pitch, sweep, space). That is what the `*_from` transforms do.
- **Pitch is size.** Down an octave reads as about twice as big and heavy. `pitch` moves length with it, which is correct for physical things.
- **Reverb is distance and scale.** A short bright room puts a sound in a place. A long dark tail makes it large. Keep the low end out of the reverb or it booms.
- **Phones play almost nothing under 150 to 200 Hz.** A sound that must be noticed needs energy between 300 Hz and 4 kHz. `check` flags ALL_LOW. A sub drop adds feel on good speakers and nothing on a phone, so never let it carry meaning.
- **Keep it mono-safe.** Wide sounds are made so left and right still add up (`widen`). `check` flags PHASE when they would cancel.

## Fitting sound to picture

The short version; `timing.md` has the full method (getting event times, frames, lengths, the `lay` command).

- **A hit lands on the frame.** The start of the file is the hit; put it on the cut or the frame the thing lands. If in doubt go a frame early, never late: late sound looks like a mistake.
- **A riser ends on the cut.** Its last sample is the peak (`tail=0`), or a very short release follows (`tail=0.12`, the default). Put an impact, a new scene or silence straight after.
- **A whoosh peaks in the middle of the move.** `peak` sets where the loudest point falls. For a move that eases in and out, sync the peak to the middle; for something flying in and stopping, peak late; flying away, peak early.
- **A pop or click goes on the first frame the thing is visible.**
- **A fetched kit sound has its sync point in its sidecar** (`sync.at`, in seconds, and what it should meet).

## Using sound in a piece

- **A sound marks a change.** Something appears, moves, completes, fails. No change on screen, no sound.
- **One sound per kind of event.** Every step complete uses the same chime, every pop the same pop. Repetition teaches the viewer what the sound means.
- **Density.** About one effect every 5 to 10 seconds in busy passages, and real silence between. Wall-to-wall effects stop registering.
- **Under a voice.** Effects sit well below speech. The built-in levels do this: UI sounds render around -27 LUFS (loudest 150 ms), notifications and pops around -22, whooshes and risers around -19 to -20, impacts around -18, against a voice mixed near -16 LUFS. If an effect has to be loud under speech, shorten it or move it into a gap.
- **Repeated sounds need takes.** The same file five times in a row sounds like a machine. Render variations and rotate them, with slightly uneven timing.
- **A family should sound like a family.** Tune pitched sounds to one root (the music's key, or one note for the whole piece), and use the fifth or octave if unsure of the key: they clash least.
- **One big moment.** A riser and an impact once or twice per video. On every cut they mean nothing.

## Loudness and files

- Levels are measured as the loudest 150 ms, K-weighted (the same scale the kit uses), so made and fetched sounds match. `--level -20` sets one by hand; `--level peak` renders at the true-peak ceiling (`--peak`, default -1 dB).
- 48 kHz, 24-bit WAV. Stereo by default; `--mono` for sounds a game positions in space.
- For the web, convert a copy with ffmpeg (ogg or mp3). Keep the WAV; never overwrite.

## Listening without ears (optional)

`check` and `spec` are the built-in tools. If the user has access to a model that accepts audio and says yes, it can listen to a file and describe it; that sends the audio to the model's provider, so it is the user's call, and it still does not replace their ears.
