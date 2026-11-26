"""Transforms: any sound in, a new sound out. The input can be a rendered recipe, a fetched recording or the
project's own audio. Simple ones change one thing; the *_from ones are whole designs built on a source.
"""
import numpy as np

import sfx_dsp as d
from sfx_dsp import SR, secs
from sfx_recipes import coerce

TRANSFORMS = {}


# Designs get a level of their own (same scale as the recipes); one-step transforms keep the loudness of their input.
LEVELS = {"boom_from": -18.0, "swell_from": -20.0, "riser_from": -20.0, "whoosh_from": -19.0, "drone_from": -28.0}


def transform(about, use, **params):
    def wrap(fn):
        TRANSFORMS[fn.__name__] = {"fn": fn, "about": about, "use": use, "params": params, "level": LEVELS.get(fn.__name__)}
        return fn
    return wrap


def apply(name, x, seed=1, **overrides):
    if name not in TRANSFORMS:
        raise KeyError(f"no transform named {name!r}; run `sfx.py list`")
    spec = TRANSFORMS[name]
    bad = set(overrides) - set(spec["params"])
    if bad:
        raise KeyError(f"{name} has no parameter {sorted(bad)}; it takes {sorted(spec['params'])}")
    p = {k: v[0] for k, v in spec["params"].items()}
    for k, v in overrides.items():
        p[k] = coerce(p[k], v)
    return spec["fn"](x, np.random.default_rng(seed), **p), p


def _even(x, smooth=0.05, floor_db=-50.0):
    """Flatten a source's own loudness shape, so a design can impose its own (a slam becomes steady texture).

    Parts quieter than floor_db below the loudest point are not lifted all the way, so silence stays silent.
    """
    e = d.envelope(x, 0.005, smooth)
    return x / np.maximum(e, e.max() * d.db(floor_db))


def _fit(x, seconds, seed):
    """Make a source last about `seconds`: smear it longer if it is short, take the loudest stretch if it is long."""
    n = secs(seconds)
    if len(x) < n * 0.9:
        x = d.stretch(x, max(n / len(x), 1.5), window=0.18, seed=seed)
    if len(x) > n:
        e = np.convolve(np.abs(d.mono(x)), np.ones(n) / n, mode="valid")
        i = int(np.argmax(e))
        x = x[i:i + n]
    return d.pad_to(x, n)


# ---------------------------------------------------------------- one-step transforms
@transform("Play it backwards.", "Turns any decaying sound into a swell that sucks into a cut. Reverse a cymbal, a piano note or a reverb tail.")
def reverse(x, rng):
    return d.finish(d.reverse(x), fade_in=0.01, fade_out=0.003)


@transform("Tape-style pitch shift: lower is longer and heavier, higher is shorter and smaller.",
           "-12 to -24 turns a door slam into a boom and a kitten into a monster. +12 makes things small, fast and cute.",
           semitones=(-12.0, "pitch change in semitones (-36 to 24)"))
def pitch(x, rng, semitones):
    return d.finish(d.pitch(x, semitones))


@transform("Extreme time-stretch that smears a sound into a pad.",
           "Any sound to an ambience, drone or eerie bed: a bell, a voice, a chord, a scrape. 8-50x is the useful range.",
           factor=(12.0, "how many times longer (4-100)"),
           window=(0.25, "smear size in seconds; bigger = smoother and more tonal, smaller = grainier"))
def stretch(x, rng, factor, window):
    return d.finish(d.stretch(x, factor, window, seed=int(rng.integers(1 << 30))), fade_in=0.2, fade_out=0.5)


@transform("Put the sound in a room.", "Distance and size. Short and bright = a tiled room; long and dark = a cave or a trailer tail.",
           t60=(1.5, "tail length in seconds (0.3 room, 1.5 hall, 4+ cathedral)"),
           mix=(0.25, "amount of room (0.1 touch, 0.5 far away, 1 only the room)"),
           bright=(0.5, "0 dark, 1 bright"))
def room(x, rng, t60, mix, bright):
    return d.finish(d.reverb(x, t60, mix, bright, seed=int(rng.integers(1 << 30))), fade_out=min(0.5, t60 * 0.3))


@transform("Make it fly past: pitch bend, volume swell and a left-to-right move.",
           "Turns any steady sound into a pass-by: an engine, a buzz, a tone, a voice. Works best on sounds 1 s or longer.",
           speed=(30.0, "metres per second (10 a bike, 30 a car, 100 a jet)"),
           distance=(3.0, "how close it passes in metres; closer = sharper"),
           at=(0.5, "when it passes, 0-1 of the length"))
def flyby(x, rng, speed, distance, at):
    return d.finish(d.doppler(x, speed, distance, at), fade_in=0.02, fade_out=0.05)


@transform("Scatter grains of the sound over time.",
           "Textures from one sound: debris from a single clink, a crowd from one clap, shimmer from a bell, static from paper.",
           seconds=(3.0, "length of the result"),
           grain=(0.06, "grain length in seconds (0.01 buzzy, 0.2 recognisable chunks)"),
           density=(40.0, "grains per second (5 sparse, 200 dense wash)"),
           pitch_spread=(3.0, "random pitch per grain in semitones"),
           pitch_center=(0.0, "overall pitch shift in semitones"))
def cloud(x, rng, seconds, grain, density, pitch_spread, pitch_center):
    g = d.granular(x, seconds, rng, grain, density, pitch_spread, pitch_center)
    return d.finish(d.reverb(g, 1.2, 0.2, 0.6, seed=int(rng.integers(1 << 30))), fade_in=0.05, fade_out=0.4)


@transform("Make it loop without a click or a bump.", "Ambiences, drones, engine hums, room tone: anything that repeats under a scene.",
           crossfade=(0.5, "seconds blended across the seam; longer hides more"))
def loop(x, rng, crossfade):
    return d.normalize(d.loop(d.stereo(x), crossfade), -1.0)


# ---------------------------------------------------------------- designs built on a source
@transform("A cinematic boom made from any thud, slam, knock or drum hit.",
           "The classic trick: pitch a real hit far down, add a synthetic sub under it and a dark tail. The source gives "
           "the texture that pure synthesis lacks. Try a door slam, a book dropped on a table, a kick drum, a car door.",
           drop=(-14.0, "semitones to pitch the source down (-7 punchy, -24 enormous)"),
           weight=(0.7, "level of the added sub (0 none, 1 huge)"),
           tail=(2.5, "reverb length in seconds"),
           root=(45.0, "pitch of the sub in Hz or a note"))
def boom_from(x, rng, drop, weight, tail, root):
    src = d.trim(d.mono(x), -50)
    i = int(np.argmax(np.abs(src)))
    src = src[max(0, i - secs(0.01)):]                       # start at the hit
    low = d.lp(d.pitch(src, drop), 3500, 2)
    low = d.saturate(d.transient(low, 1.6, 1.0) / (np.max(np.abs(low)) + 1e-9), 2.0)
    n = max(len(low), secs(1.6))
    tt = np.arange(n) / SR
    sub = d.saturate(d.sine(root * (1.0 + 2.2 * np.exp(-tt / 0.04))) * d.perc(n, 0.001, 0.6 + 1.2 * weight), 1.5)
    wet = d.reverb(d.lp(low, 2500), t60=tail, mix=1.0, bright=0.3, pre_delay=0.02, seed=int(rng.integers(1 << 30)))
    out = d.layer([(low, 0, 0), (sub, 0, -20 + 20 * weight), (wet, 0, -10)])
    return d.finish(out, fade_out=min(0.5, tail * 0.3))


@transform("A reverse swell that grows out of nothing and lands on the sound itself.",
           "Makes any hit feel announced: the sound's own reverb, reversed, leads into it. Put the cut where the swell ends.",
           seconds=(1.5, "length of the swell before the hit"),
           land=(True, "true = the original sound plays at the end; false = swell only, cut to silence"))
def swell_from(x, rng, seconds, land):
    wet = d.reverb(x, t60=seconds * 1.3, mix=1.0, bright=0.6, seed=int(rng.integers(1 << 30)))
    wet = d.reverse(wet[:secs(seconds)] if len(wet) > secs(seconds) else wet)
    wet = d.gain_env(wet, np.linspace(0, 1, len(wet)) ** 1.5)
    wet = d.normalize(wet, -6.0)
    if not land:
        return d.finish(wet, fade_in=0.02, fade_out=0.004)
    return d.finish(d.layer([(wet, 0, 0), (d.normalize(d.stereo(x), -1.0), len(wet) / SR, 0)]), fade_in=0.02)


@transform("A riser made from any sustained or textured sound.",
           "Smears the source, then winds its pitch up and opens a filter. A riser made from the project's own music, "
           "voice or ambience belongs to the piece in a way a stock riser does not.",
           seconds=(3.0, "length"),
           octaves=(1.0, "how far the pitch climbs"),
           air=(0.5, "how much the top end opens up (0-1)"))
def riser_from(x, rng, seconds, octaves, air):
    seed = int(rng.integers(1 << 30))
    n = secs(seconds)
    speed = d.glide(n, 1.0, 2.0 ** octaves, 1.2)
    need = int(np.sum(speed)) + SR                            # the speed-up eats source faster and faster
    src = _even(_fit(d.trim(d.mono(x), -45), need / SR, seed))
    y = d.warp(src, speed)
    y = d.pad_to(y, n)[:n]
    ramp = np.linspace(0, 1, n)
    y = d.tilt(d.sweep(y, "hp", d.glide(n, 60, 400 + 1800 * air, 1.5)), 2.0 * air)
    y = _even(y, 0.1, -70.0) * ramp ** 1.8                    # level it after filtering, so a bassy source still builds
    out = d.reverb(d.widen(y, rng, 0.6), t60=1.4, mix=0.25, bright=0.7, seed=seed)[:n]
    return d.finish(out, fade_out=0.004)


@transform("A whoosh made from any texture: cloth, paper, breath, fire, a crowd, music.",
           "Shapes the source into a pass-by: swell, sweep, pitch bend and a move across the speakers. The source's grain "
           "survives, so a paper whoosh sounds like paper and a flame whoosh like flame.",
           seconds=(0.8, "length"),
           peak=(0.55, "where the loudest point falls (0-1)"),
           travel=(1.0, "1 left-to-right, -1 right-to-left, 0 centred"),
           bend=(4.0, "pitch bend through the pass, in semitones"))
def whoosh_from(x, rng, seconds, peak, travel, bend):
    seed = int(rng.integers(1 << 30))
    n = secs(seconds)
    src = _even(_fit(d.trim(d.mono(x), -45), seconds * 1.4, seed))
    pos = np.linspace(0, 1, n)
    speed = 2.0 ** (bend / 12.0 * (0.5 - 0.5 * np.tanh(4.0 * (pos - peak))) - bend / 24.0)
    y = d.pad_to(d.warp(src, speed), n)[:n]
    shape = d.bell_curve(n, peak, 0.17, skew=1.35)
    y = d.sweep(y, "bp", 350.0 * (5000.0 / 350.0) ** shape, q=0.9) * 1.5 + y * 0.35
    y = y * shape ** 1.4
    position = travel * np.tanh(3.0 * (pos - peak)) / np.tanh(1.5)
    out = d.pan(y, np.clip(position, -1, 1)) * 0.8 + d.widen(y, rng, 0.6) * 0.35
    return d.finish(d.reverb(out, 0.5, 0.12, 0.6, seed=seed), fade_in=0.01, fade_out=0.08)


@transform("A dark, slowly moving drone made from any sound.",
           "Tension beds, sci-fi rooms, dream sequences, the hum under a title. A bell, a vocal note or a bowed object "
           "gives a tonal drone; noise sources give wind and rumble.",
           seconds=(12.0, "length"),
           drop=(-12.0, "pitch shift in semitones before smearing"),
           dark=(0.6, "0 = keep the brightness, 1 = very dark"))
def drone_from(x, rng, seconds, drop, dark):
    seed = int(rng.integers(1 << 30))
    src = d.pitch(d.trim(d.mono(x), -50), drop)
    y = d.stretch(src, max(4.0, secs(seconds) * 1.3 / len(src)), window=0.35, seed=seed)
    y = _even(y, 0.5)[:secs(seconds)]
    y = d.lp(y, 12000 * (1.0 - dark) ** 2 + 600, 2)
    slow = 1.0 + 0.25 * d.lp(rng.standard_normal(len(y)), 0.3, 1) * 300.0
    out = d.widen(y * slow, rng, 0.8)
    return d.finish(d.reverb(out, 3.0, 0.3, 0.3, seed=seed), fade_in=min(1.5, seconds * 0.15), fade_out=min(2.5, seconds * 0.25))


@transform("Stamp another sound's character onto this one (convolution).",
           "Use any recording as the 'room': a clap in a stairwell, a pot lid, a piano with the pedal down, a metal pipe. "
           "A synthetic sound played through a real one picks up its body. Short, percussive stamps work best.",
           stamp=("", "path of the sound to use as the stamp (required)"),
           mix=(0.6, "0 = original, 1 = only the stamped version"))
def stamp(x, rng, stamp, mix):
    if not stamp:
        raise ValueError("stamp needs stamp=<path to a sound file>")
    ir = d.trim(d.read_audio(stamp), -50)
    ir = ir / np.sqrt(np.sum(d.stereo(ir) ** 2) / 2.0 + 1e-12)
    wet = d.convolve(x, ir)
    dry = d.pad_to(d.stereo(x), len(wet))
    wet *= np.sqrt(np.mean(dry ** 2) / (np.mean(wet ** 2) + 1e-12)) if np.any(dry) else 1.0
    return d.finish(dry * (1.0 - mix) + wet * mix, fade_out=0.1)
