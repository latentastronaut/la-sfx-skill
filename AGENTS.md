# Notes for coding agents

This repo is **sfx**, a Claude skill that makes sound effects with code (numpy and scipy only). If you are an agent helping someone contribute, read this first, then [CONTRIBUTING.md](CONTRIBUTING.md). `CLAUDE.md` points here, so every agent reads the same file.

## You cannot hear

This is the rule everything else follows from.

- Never say a sound is good, and never pick between takes. `check` and `spec` find faults; they don't tell you a sound is right. Make candidates, build the audition page (`sfx.py audition <folder>`), and let the person listen.
- Before a person hears a new real-world sound, fit it to a reference: `sfx.py compare yours.wav reference.wav`, then `sfx.py spec` on both and look at the two pictures side by side. Sounds built from reasoning alone nearly always failed when someone listened.
- A flag from `check` means "a person should listen for this". It is not a verdict.

## Layout

| Path | What it is |
|---|---|
| `skills/sfx/SKILL.md` | What Claude reads when it uses the skill. Its description decides when the skill is picked, so treat edits to it as behaviour changes. |
| `skills/sfx/references/` | Timing, sound design, the ambience method, where free sounds can be had. |
| `skills/sfx/scripts/sfx.py` | The command line. |
| `skills/sfx/scripts/sfx_recipes.py` | The recipe registry (`@recipe`), the levels (`LEVELS`) and the core recipes. The other `sfx_*.py` files register more recipes by kind. |
| `skills/sfx/scripts/sfx_dsp.py` | Building blocks: oscillators, noise, filters, reverb, stretch, loudness, WAV writing. |
| `skills/sfx/scripts/sfx_fx.py`, `sfx_check.py`, `sfx_sources.py` | Transforms; measurements and the spectrogram; the only code that touches the network (`find`, `fetch`). |
| `skills/sfx/scripts/data/` | Measured loudness curves for `footsteps` and `stream`. `tools/measure/` has the scripts that made them. |
| `skills/sfx/tests/test_sfx.py` | The tests. CI runs them on pushes to `main` and on pull requests. |
| `.claude-plugin/` | The plugin and its one-skill marketplace. |
| `assets/` | The banner, social preview and icon; `assets/src/` draws them. |

## Commands

```
uv run skills/sfx/tests/test_sfx.py            # all tests, about 40 seconds, no network
uv run skills/sfx/scripts/sfx.py list           # every recipe and transform
uv run skills/sfx/scripts/sfx.py list riser     # one entry with its parameters
uv run skills/sfx/scripts/sfx.py make riser seconds=2 --out /tmp/try
uv run skills/sfx/scripts/sfx.py check /tmp/try/*.wav
uv run skills/sfx/scripts/sfx.py spec /tmp/try/riser_v001.wav
```

Use `uv run`; each script declares its own dependencies. Render test sounds into a scratch folder with `--out`, not into the repo.

## Rules for a change

- **numpy and scipy only.** No new dependencies, no models, no API keys.
- **No audio files in the repo**, including test fixtures. Measured numbers are fine; say where they came from.
- **Same seed and parameters, same samples.** A recipe takes randomness only from the `rng` it is handed. Never call the global random functions or the clock.
- **The sync point is computed, not measured.** A recipe whose sync point is not its first sample returns `(signal, {mark: seconds})`, with the first mark as the sync point, worked out from the parameters.
- **Write the registry text for someone who can't hear.** A recipe's `about`, `use` and each parameter's description are what an agent reads to choose and set a sound. Give useful values in the text ("0.3 tight, 4 huge").
- **Give every recipe a level** in `LEVELS` and end it with `d.finish(...)`.
- **The network stays in `sfx_sources.py`.** Nothing else may open a connection. `fetch` records each sound's source, author and licence beside the file.
- **Nothing is overwritten.** Output files are versioned (`name_v001.wav`); `write_wav` refuses to replace a file.
- **A new recipe with a sync point gets a test** for that point.
- **Keep the counts true.** If you add or remove a recipe or transform, update the numbers in `README.md` and `RECIPES` in `assets/src/draw.html`.
- **Code style:** follow the file you are in. Long lines are used here on purpose; comments say why, not what.

## What not to attempt without a person

Breaking glass, footsteps on grass, gravel or snow, engines, doors, water drops, and anything meant to sound far away have each failed more than once when listened to. They are the open problems in CONTRIBUTING.md. An attempt is welcome, but it needs a reference to fit to and a person to listen before it goes in a pull request.

## Pull requests

Say what you compared the sound with and who listened. Run the tests. Keep a pull request to one recipe or one fix.
