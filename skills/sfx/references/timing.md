# Timing

A sound that is right and 80 ms late reads as a mistake. A plain sound on the exact frame reads as polish. Get the time of the event first, then make the sound to fit it, then place it by its sync point. Never place by eye, by the start of the file, or by a round number.

## Sync points

Every sound has one moment that must meet the event on screen: its sync point. It is rarely the start of the file.

| Sound | Sync point | Meets |
|---|---|---|
| Hit, click, pop, chime, error, stinger | The start of the file | The first frame the thing is visible, lands or changes |
| Riser | Its peak, at the end | The cut. The file starts `seconds` earlier |
| Whoosh | Its loudest point (the `peak` mark) | The middle of the move; for a move that stops hard, the frame it stops |
| Compound (`riser_hit`, `whoosh_hit`, ...) | The hit, exactly `lead` seconds in | The cut, or the frame the thing lands |
| Run (`pop_run`, `typing`, `count_up`) | The first sound; every later one has its own mark | Each item, the last key, the number stopping |
| Fetched kit sound | `sync.at` in its sidecar | What `sync.meets` and `sync.how` say |

`make` prints the sync point and writes it into the sidecar: `sync.at` (seconds into the file), `sync.meets`, `sync.how`, and `marks` (every named moment). Marks are computed from the parameters, so they are exact to the sample. `--vary` never changes a timing parameter (`seconds`, `lead`, `gap`, `peak`), so every take of a sound drops onto the same spot.

**Events inside a sound.** `make <recipe> --events` also lists every separate small sound in the sidecar (`events`: each raindrop, fire crackle and pop, cricket pulse, vinyl click, thunder or explosion fragment) as `{t, pos, gain}`: seconds into the file, left-right position (-1 to 1) and loudness relative to the loudest. They are the numbers the sound was built from, so they are exact. Use them to draw the picture from the sound: a dot per drop, a flash per crackle. In code, `sfx_recipes.render_events(name, seed, **params)` returns them as a fourth value. Recipes with no separate events give an empty list.


**File start = event time minus the sync point.** A riser_hit with `lead=1.5` whose hit belongs at 12.40 s starts at 10.90 s.

## Get the event times from the source

In order of trust:

1. **The project's own data.** The edit list, the animation's keyframes, the code that draws the motion, the captions file, the game's event code. If the project is built by code (Remotion, a web animation, a game), read the frame numbers from the code.
2. **Measured from the media.** Cuts: `ffmpeg -i in.mp4 -vf "select='gt(scene,0.3)',showinfo" -f null -` prints the time of each scene change. Spoken words: a transcript with word times (a speech-to-text tool that reports them). Beats of the music: ask for the tempo and work in beats (one beat = 60 / BPM seconds).
3. **The user.** Ask "what time does the title land?" rather than guess.

Don't guess from a description ("about two seconds in"). If you can't get a time, say so and ask.

## Frames

Video moves in frames, so an event time is a frame number divided by the frame rate. At 30 fps a frame is 33 ms; at 24 fps, 42 ms; at 60 fps, 17 ms. Get the frame rate with `ffprobe` and work in frames when the project does.

- A hit that is one frame early still looks right. One frame late looks wrong. Two frames late looks broken. When a time falls between frames, take the earlier frame.
- Sound that leads the picture by up to a frame feels tight because the eye is slower than the ear.
- For lip-sync-like precision (a clap, a finger tap, a ball bounce) be within one frame. For a title or a graphic, within one frame early. For a scene transition whoosh, a few frames either way is fine as long as the peak is inside the move.

## Fit the length to the time you have

Decide the length from the picture, not from the recipe's default.

- **Lead-ins** (`riser`, `riser_hit`, `swell_hit`, `whoosh_hit`): `lead` or `seconds` = event time minus the earliest moment the sound may start. That earliest moment is usually the end of the previous sentence or the previous cut. A riser that starts under a spoken line fights it.
- **Moves** (`whoosh`, `swish_pop`): the length of the move on screen. A 6-frame slide at 30 fps is 0.2 s; a 0.8 s whoosh on it is wrong however good it sounds.
- **Runs**: `typing seconds=` the time the text takes to appear; `count_up seconds=` the time the number runs; `pop_run times=` the actual times the items appear (as they are on the timeline; the first is taken as zero).
- **Tails** may run past the event, but not into the next line of speech at full level. Shorten `tail`, or let it sit under the voice if it is quiet.
- **The beat of silence.** `gap=0.08` (about two frames) between a riser and its hit makes the hit land harder. The hit still lands on the mark; the riser ends early.
- **To music.** If music is playing, put big hits on a beat or a bar line, make lead-ins a whole number of beats long, and tune `root` to the key.

## Place with `lay`

`lay` reads a cue sheet and writes one sound file with every sync point on its event. Put that file at 0:00 on the timeline, on its own track.

```json
{"fps": 30, "seconds": 95.2, "cues": [
  {"file": "sfx/riser_hit_v001.wav", "frame": 372, "note": "title lands"},
  {"file": "sfx/swish_pop_v002.wav", "at": 15.2},
  {"file": "sfx/pop_run_v001.wav", "at": 21.4, "mark": "pop1"},
  {"file": "sfx/sources/kit_whoosh-fast-hard.wav", "at": 30.0, "gain": -3}
]}
```

- `at` is the event time in seconds; `frame` is a frame number and needs `fps`. Paths are relative to the sheet.
- The sync point comes from the sound's sidecar. `mark` picks another mark. A file with no sidecar is placed by its start, and the report says so.
- `seconds` (optional) pads the track to the length of the piece.
- The report lists every event with its time, frame, and where its file starts and ends. It warns when a time given in seconds is not on a frame, and stops with an error when a lead-in would have to start before 0:00.
- If stacked sounds would pass the peak ceiling, the whole track is lowered and the report says by how much. Nothing else changes the levels.

To place a single sound by hand in an editor or with ffmpeg, use the same arithmetic: start = event time minus `sync.at`.

## Check after placing

- Read the `lay` report against the event list. Every event has one line, on its time.
- `spec` the track around a big moment and Read the picture when it matters: the hit is a vertical line; it should sit at the event time.
- Then the user watches it. Timing that measures right can still feel wrong against the picture (an animation that eases, a cut on movement). Move it by frames, on their word.
