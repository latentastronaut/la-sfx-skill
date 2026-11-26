# Contributing

The most useful thing you can send is a recipe for a sound this can't make yet.

## Open problems

These were each tried more than once and failed when a person listened:

- **Breaking glass.** A real bottle break is separate bounces with thin ringing lines. The attempts came out as one smear of noise.
- **Footsteps on grass, gravel and snow.** Wood, concrete and dirt work. The loose surfaces came out wet and close.
- **Distance.** Every recipe renders close up. Low-pass, blur, narrowing and more reverb together did not make a sound read as far away.
- **An engine, a door, water drops.**

If you know how one of these is built, that is the place to start.

## A recipe

A recipe is a Python function, usually about twenty lines, in `skills/sfx/scripts/`. `tick` in `sfx_recipes.py` is a good one to read first.

1. Write the function with the `@recipe` decorator: its family, what it is, when to use it, and every parameter with its meaning. That text is what an agent reads to choose the sound, so write it for someone who can't hear.
2. Build it from layers (low, body, attack, tail), one job per layer, with the building blocks in `sfx_dsp.py`.
3. Give it a level in `LEVELS` and end it with `d.finish(...)`.
4. Return `(signal, {mark: seconds})` if the moment that belongs on the frame is not the first sample.
5. The same seed and parameters must give the same samples. Take randomness only from the `rng` you are handed.

## Before you open a pull request

- **Fit real-world sounds to a real recording.** Run `sfx.py compare yours.wav real.wav` and `sfx.py spec` on both, and look at the two pictures side by side. Sounds built from a model alone nearly always failed; sounds fitted to a recording passed.
- **Listen to it**, and say in the pull request what you compared it with. Numbers find faults. They don't tell you a sound is good.
- **Don't add audio files.** The repository contains none, and that is the point. Measured numbers (loudness curves, like `scripts/data/`) are fine; say what recording they came from and its licence.
- **Don't add dependencies.** numpy and scipy only.
- Run the tests: `uv run skills/sfx/tests/test_sfx.py` (about 40 seconds, no network). Add a test for a new recipe's sync point if it has one.

Bug reports are welcome too: the command you ran, what you got and what you expected.
