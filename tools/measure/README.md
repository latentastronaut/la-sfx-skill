# How the data files were measured

Two recipes are not built from a model of the sound. `footsteps` and `stream` shape one broadband noise to loudness curves measured on reference sounds: how loud each of 32 frequency bands is, every few milliseconds. The curves are in `skills/sfx/scripts/data/`. These two scripts made them.

| Script | Makes | Used by |
|---|---|---|
| `steps_analyse.py` | per-step curves: it finds each step in a walk and stores 32 bands every 2.5 ms | `footsteps` (`data/steps.npz`) |
| `texture_analyse.py` | whole-take curves: 32 bands every 5 ms | `stream` (`data/stream.npz`) |

```
uv run tools/measure/steps_analyse.py steps.npz wood=walk_on_wood.wav concrete=walk_on_concrete.wav
uv run tools/measure/texture_analyse.py stream.npz stream=take1.wav,take2.wav,take3.wav
```

Notes:

- The reference sounds themselves are not in this repository, and no audio is in the data files: a curve says how loud a band is, not what it sounds like.
- `data/steps.npz` holds the three surfaces that passed listening (wood, concrete, dirt), with each surface's steps and its median gap. The background-level arrays the script also writes (`*_floor`) were left out of the shipped file.
- The scripts need a sound's real steps to stand clear of its background. A walk with music or talking under it will not measure.
- To add a surface: measure it, add its arrays to `steps.npz`, add the name to `footsteps` in `sfx_measured.py`, and listen. Grass, gravel and snow were measured the same way and still failed by ear.
