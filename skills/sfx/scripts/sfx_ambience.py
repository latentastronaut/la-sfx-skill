"""Ambiences that loop: rain, fire, wind, room tone.

Built from published procedural-audio designs, not from filtered noise alone (see references/ambience.md for sources
and the reasons). The rules they share:

- Events lead, the bed follows. A place is recognised from many small separate events (drops, crackles); a steady
  band of noise is heard as static, however it is filtered.
- Nothing steady above about 2 kHz. Every layer's level follows a slow random curve; no fixed-rate wobble, which the
  ear picks out as a cycle.
- Events are short bursts of noise through a wide filter, with a 1-2 ms soft start. A narrow filter or a sine makes
  each one a beep, a bubble or a laser; a hard start makes it a click.
- Lows stay in the middle, only the highs are spread; events are panned one by one.
"""
import numpy as np

import sfx_dsp as d
from sfx_dsp import SR, secs
from sfx_recipes import LEVELS, note, recipe

LEVELS.update({"rain": -30.0, "fire": -30.0, "wind": -30.0, "room": -50.0})

BED_SYNC = ("the start of the scene", "Not frame-critical. Start it with the scene and fade it in and out over half a second in the edit; "
            "a bed that starts or stops hard is noticed.")
FADE = 1.2                                                    # seconds of the end blended into the start to close the loop


def wander(n, rng, lo, hi, hold_lo, hold_hi):
    """A slow random curve between lo and hi: random targets, each held for a random time, eased with a raised cosine."""
    xs, vs, t = [0], [rng.uniform(lo, hi)], 0
    while t < n:
        t += secs(rng.uniform(hold_lo, hold_hi))
        xs.append(t)
        vs.append(rng.uniform(lo, hi))
    xs, vs = np.array(xs), np.array(vs)
    i = np.arange(n)
    k = np.searchsorted(xs, i, side="right") - 1
    p = (i - xs[k]) / (xs[k + 1] - xs[k])
    return vs[k] + (vs[k + 1] - vs[k]) * (0.5 - 0.5 * np.cos(np.pi * p))


def bpq(x, f, q):
    """A two-pole band-pass at centre f with quality q (low q = wide and unpitched)."""
    half = f / (2.0 * q)
    lo = np.sqrt(f * f + half * half) - half
    return d.bp(x, lo, lo + f / q, 1)


def unit(x):
    return x / max(float(np.sqrt(np.mean(np.square(x)))), 1e-9)


def burst(rng, length, decay, attack=0.0015):
    """One event: white noise with a soft start and an exponential fall. `decay` is how many time-constants fit in the length."""
    m = max(secs(length), 8)
    t = np.arange(m) / m
    a = min(max(secs(attack), 2), m // 2)
    env = np.exp(-decay * t)
    env[:a] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(a) / a)
    env[-a:] *= np.linspace(1.0, 0.0, a)
    return rng.uniform(-1.0, 1.0, m) * env


def put(out, x, at, pos=0.0, gain=1.0):
    """Add a mono event to a stereo track at sample `at`, panned with equal power."""
    if at >= len(out):
        return
    note(at, pos, gain * float(np.max(np.abs(x))) if len(x) else 0.0)
    x = x[:len(out) - at]
    th = (pos + 1.0) * np.pi / 4.0
    out[at:at + len(x), 0] += x * (gain * np.cos(th))
    out[at:at + len(x), 1] += x * (gain * np.sin(th))


def spread(x, rng, split=800.0, ms=14.0):
    """Mono bed to stereo: everything under `split` Hz stays in the middle, the highs are shifted apart in time."""
    low = d.lp(x, split, 1)
    high = x - low
    k = secs(ms / 1000.0)
    return np.stack([low + np.roll(high, -k), low + np.roll(high, k)], axis=1)


def close(x, seconds):
    """Close the loop and return exactly `seconds`. Nothing may filter the result afterwards or the seam breaks."""
    return d.finish(d.loop(x, FADE)[:secs(seconds)], fade_in=0, fade_out=0, dc=False, tail_db=None)


def poisson(rng, n, rate):
    """Sample positions of random events at `rate` per second (a number or a per-sample curve)."""
    return np.nonzero(rng.random(n) < np.asarray(rate) / SR)[0]


BANDS = (63, 125, 250, 500, 1000, 2000, 4000, 8000, 14000)


def tint(n, rng, levels):
    """Noise whose octave bands (63 Hz to 14 kHz) sit at the given levels in dB: the spectrum of a real recording, copied."""
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.maximum(np.fft.rfftfreq(n, 1.0 / SR), 1.0)
    width = np.log2(np.array(BANDS) * 1.414 / (np.array(BANDS) / 1.414))            # bands are an octave wide: white noise gains 3 dB per octave
    gain = np.interp(np.log2(f), np.log2(BANDS), np.asarray(levels, float) - 3.01 * np.log2(np.array(BANDS) / 1000.0) / width)
    gain[f < 30] = -80.0
    return unit(np.fft.irfft(spec * 10.0 ** (gain / 20.0), n))


# Octave-band levels measured from field recordings (references/ambience.md names them).
RAIN = (-12.9, -13.1, -11.7, -10.7, -12.0, -7.2, -7.4, -12.5, -27.3)        # summer rain in a courtyard, from a window
FIRE_FAR = (-4.7, -8.8, -11.8, -26.0, -34.0, -42.0, -48.0, -52.0, -56.0)    # a campfire from a few metres: the steady part is all rumble
WIND_LULL = (-15.0, -7.0, -5.5, -7.5, -9.0, -14.0, -24.0, -32.0, -38.0)
WIND_GUST = (-15.7, -7.7, -5.9, -7.3, -6.6, -8.8, -15.8, -22.7, -27.8)      # gusts through trees and round a house


# ================================================================ rain
@recipe("bed", "Rain: the bright hush of thousands of drops, with the nearer ones heard one by one.",
        "Under a scene or narration to place it outdoors or by a window; a sad, calm or cosy mood. Loops without a seam.",
        sync=BED_SYNC,
        seconds=(12.0, "length of the loop (8-30; longer loops are harder to notice)"),
        amount=(0.5, "light shower to downpour (0-1): more drops, and a fuller, steadier hush"),
        drops=(0.4, "how far the separate drops stand out from the hush (0 = a soft wash, 1 = clear patter)"),
        dull=(0.0, "0 = heard outdoors or at an open window, 1 = heard from inside, through a wall or roof"))
def rain(rng, seconds, amount, drops, dull):
    n = secs(seconds + FADE)
    swell = wander(n, rng, 0.8, 1.15, 3.0, 9.0)                # the shower thickening and thinning
    shape = np.array(RAIN) - dull * np.array((0, 0, 0, 1, 3, 7, 12, 18, 24.0)) + (amount - 0.5) * np.array((3, 2, 1, 0, 0, 0, 0, 0, 0.0))
    low = d.lp(tint(n, rng, shape), 900.0, 1)                   # two halves that breathe apart, so the hush is never frozen
    hush = tint(n, rng, shape)
    hush = low * wander(n, rng, 0.8, 1.2, 0.8, 3.0) + (hush - d.lp(hush, 900.0, 1)) * wander(n, rng, 0.75, 1.25, 0.5, 2.5)
    bed = spread(unit(hush) * swell, rng, 800.0, 14.0)

    # the drops: three distances. Far drops are many, quiet and narrow; near drops are few, loud and wide
    hits = np.zeros((n, 2))
    k = 0.3 + 2.2 * amount
    top = 4500.0 * 2.0 ** (-2.0 * dull)
    for rate, gain, width in ((3.0 * k, 1.0, 0.92), (14.0 * k, 0.5, 0.55), (60.0 * k, 0.26, 0.28)):
        times = list(poisson(rng, n, rate * swell))
        for at in poisson(rng, n, 0.4 * k * (gain > 0.3)):                  # a run of drops close together, off a leaf or a gutter
            run = np.cumsum(secs(0.006) + (rng.random(int(rng.integers(2, 8))) ** 2 * secs(0.034)).astype(int))
            times += list(at + run[at + run < n])
        for at in times:
            f = np.exp(rng.uniform(np.log(900.0), np.log(top)))
            x = bpq(burst(rng, rng.uniform(0.008, 0.035), rng.uniform(5.0, 9.0), 0.0012), f, rng.uniform(0.5, 0.9))
            put(hits, x, int(at), rng.uniform(-width, width), gain * np.exp(rng.uniform(-3.2, 0.0)))
    echo = np.zeros_like(hits)                                  # first reflections off the ground and walls: what puts the drops in a place
    for ms_l, ms_r, g in ((11, 13.1, 0.55), (19, 17.3, 0.42), (31, 29.1, 0.32), (47, 51.2, 0.24), (66, 63.1, 0.17), (89, 93.0, 0.11)):
        echo[secs(ms_l / 1000):, 0] += hits[:n - secs(ms_l / 1000), 0] * g
        echo[secs(ms_r / 1000):, 1] += hits[:n - secs(ms_r / 1000), 1] * g
    hits = d.lp(hits + d.lp(echo, 2500.0, 1) * 0.35, 6000.0, 2)
    level = d.db(-15.0 + 16.0 * (drops - 0.4) - 4.0 * (amount - 0.5))        # in a downpour single drops are lost in the hush
    y = bed + hits / max(float(np.sqrt(np.mean(hits ** 2))), 1e-9) * level
    return close(d.hp(y, 40.0, 2), seconds)


# ================================================================ fire
@recipe("bed", "A campfire: a low breathing rumble, constant random crackle spread in width and depth, and low pops in loose groups.",
        "A campfire, a fireplace, a cosy or tense night scene. Loops without a seam.",
        sync=BED_SYNC,
        seconds=(12.0, "length of the loop (8-30)"),
        amount=(0.5, "embers to a big blaze (0-1): the weight of the rumble"),
        crackle=(0.4, "how busy the bright crackle is (0 = nearly none, 0.7 = lively; higher was rejected by ear as too much)"),
        pops=(0.3, "how many low pops there are (0 = few, 1 = many); above 0.5 was heard as too much popping"))
def fire(rng, seconds, amount, crackle, pops):
    n = secs(seconds + FADE)
    a = wander(n, rng, 0.55, 1.0, 2.0, 6.0)                     # slow "breaths" that the rumble follows
    b = wander(n, rng, 0.60, 1.0, 1.5, 4.5)
    steady = spread(tint(n, rng, FIRE_FAR) * a * b, rng, 500.0, 14.0)

    # crackle: constant and random, each click somewhere of its own across the width and at its own depth. Near ones are
    # bright, loud and dry; far ones are duller, quieter and carry more of the open air. Most are small; a few are far louder.
    crack = np.zeros((n, 2))
    for depth_lo, depth_hi, top, air in ((0.0, 0.33, 12000.0, 0.10), (0.33, 0.66, 6000.0, 0.30), (0.66, 1.0, 3200.0, 0.60)):
        layer = np.zeros((n, 2))
        for at_ in poisson(rng, n, (15.0 + 90.0 * crackle) * np.clip(a * b * 1.6, 0.4, 1.4)):
            depth = rng.uniform(depth_lo, depth_hi)
            put(layer, burst(rng, rng.uniform(0.0003, 0.004), rng.uniform(7.0, 12.0), 0.0002), int(at_), rng.uniform(-0.95, 0.95) * (1.0 - 0.4 * depth),
                np.exp(-3.0 * depth) * rng.lognormal(-1.2, 0.75))
        layer = d.lp(d.hp(layer, 3500.0, 2), top + 4000.0, 2)           # measured: the crackle of a real campfire lives above 4 kHz
        crack += layer + d.reverb(layer, t60=0.6, mix=1.0, bright=0.3, pre_delay=0.015, seed=int(rng.integers(1 << 30)))[:n] * air

    # the low pops come in loose groups: one to five of them, unevenly spaced, each with its own tone and place
    thumps = np.zeros((n, 2))
    t = rng.uniform(0.2, 1.5)
    while t < n / SR:
        tt, group = t, np.exp(rng.uniform(-1.5, 0.0))
        for _ in range(int(min(rng.geometric(0.45), 5))):
            m = secs(rng.uniform(0.025, 0.09))                  # long enough to have a body, not only a tap
            e = np.exp(-rng.uniform(4.0, 9.0) * np.arange(m) / m)
            e[:secs(0.0015)] *= np.linspace(0, 1, secs(0.0015))
            tone = d.lp(rng.uniform(-1, 1, m), np.exp(rng.uniform(np.log(110.0), np.log(520.0))), 2) * 3.0
            f = rng.uniform(55.0, 160.0)                        # a low thump under every pop gives it fullness
            tone = 0.6 * tone + 0.4 * d.sine(f * (1.0 + 0.5 * np.exp(-np.arange(m) / SR / 0.012)), None)
            put(thumps, tone * e, secs(tt), rng.uniform(-0.8, 0.8), group * np.exp(rng.uniform(-1.5, 0.0)))
            tt += rng.exponential(0.09) + 0.02
        t = tt + rng.exponential(1.4) / (0.4 + 1.6 * pops) + 0.15

    def at(x, db):
        return x / max(float(np.sqrt(np.mean(x ** 2))), 1e-9) * d.db(db)
    y = steady * (0.7 + 0.6 * amount) + at(crack, -26.0 + 6.0 * (crackle - 0.4)) + at(thumps, -20.0 + 6.0 * (pops - 0.3))
    return close(d.hp(y, 30.0, 2), seconds)


# ================================================================ wind
@recipe("bed", "Wind: a broad rush that swells and brightens in gusts, with a low howl round edges if wanted.",
        "An exposed place, a mountain, a storm outside a window, emptiness, unease. Loops without a seam.",
        sync=BED_SYNC,
        seconds=(20.0, "length of the loop (12-40). About one gust per 7 s; the loop starts and ends in a lull"),
        amount=(0.5, "how gusty (0 = a steady breeze, 1 = strong gusts with deep lulls)"),
        howl=(0.0, "the low howl round a building or through a gap: 0 = none (open country), 0.5 = clear, 1 = a draughty house at night. "
              "There is no faint setting: a howl too quiet to be heard as one was heard as a fault"),
        pitch=(250.0, "pitch of the howl in Hz at a middling wind (180-450); it rises and falls with the gusts"))
def wind(rng, seconds, amount, howl, pitch):
    n = secs(seconds + FADE)
    # the loop starts and ends in a lull with whole gusts between, so every gust is heard from its rise to its fall
    count = max(1, int(round(seconds / 7.0)))
    edges = np.sort(rng.uniform(0.12, 0.88, count - 1)) if count > 1 else np.array([])
    edges = np.concatenate([[0.0], edges, [1.0]]) * (seconds - 1.0) + 0.5
    t = np.arange(n) / SR
    gust = np.zeros(n)
    for a, b in zip(edges[:-1], edges[1:]):
        p = np.clip((t - a) / (b - a), 0.0, 1.0)
        rise = rng.uniform(0.3, 0.5)                            # a gust comes up faster than it dies away
        shape = np.where(p < rise, 0.5 - 0.5 * np.cos(np.pi * p / rise), 0.5 + 0.5 * np.cos(np.pi * (p - rise) / (1.0 - rise)))
        gust = np.maximum(gust, shape * rng.uniform(0.6, 1.0) * ((p > 0) & (p < 1)))
    gust = np.clip(gust + 0.12 * (wander(n, rng, -1.0, 1.0, 0.6, 2.0)) * gust, 0.0, 1.0)
    flutter = wander(n, rng, 0.85, 1.12, 0.22, 0.8)
    depth = 0.25 + 0.65 * amount
    force = (1.0 - depth) + depth * gust ** 1.5
    # a gust is brighter as well as louder: the lull and the gust are two different spectra, crossfaded by the wind speed
    body = (tint(n, rng, WIND_LULL) * (1.0 - gust) + tint(n, rng, WIND_GUST) * gust * 1.4) * force * flutter
    y = spread(body, rng, 1600.0, 13.0)                         # split high: the body of wind is low, and splitting it sounds like two fans
    if howl > 0:
        tones = np.zeros((n, 2))
        for ratio, q, pos in ((1.0, 9.0, -0.3), (1.52, 11.0, 0.35)):
            # a narrow band of noise made without a filter: a tone at the moving pitch, shaped by slow noise.
            # (A swept narrow filter ticked each time it moved, which was heard as artifacts.)
            fc = pitch * ratio * 2.0 ** (0.45 * (gust - 0.5) + 0.03 * wander(n, rng, -1, 1, 0.4, 1.5))
            ph = 2 * np.pi * np.cumsum(fc) / SR
            width = pitch * ratio / q
            strip = d.lp(rng.standard_normal(n), width, 2) * np.cos(ph) + d.lp(rng.standard_normal(n), width, 2) * np.sin(ph)
            tones += d.pan(strip * wander(n, rng, 0.2, 1.0, 1.4, 5.5) * np.clip(gust * 1.6 - 0.3, 0, 1) ** 2, pos) / ratio
        y = y + tones / max(float(np.sqrt(np.mean(tones ** 2))), 1e-9) * float(np.sqrt(np.mean(y ** 2))) * (0.7 + 0.9 * howl)
    return close(d.hp(y, 35.0, 2), seconds)


# ================================================================ room tone
@recipe("bed", "Room tone: the quiet air of an indoor space, a soft vent rush with a trace of machine hum.",
        "Under narration, so gaps and cuts in the voice track are not heard against dead silence; an office, a corridor, a "
        "server room. It must not be noticed: it is far quieter than any other sound here. Loops without a seam.",
        sync=BED_SYNC,
        seconds=(12.0, "length of the loop (8-30)"),
        amount=(0.3, "0 = a still room, 1 = a clearly audible air vent"),
        hum=(0.3, "level of the low machine hum (0 = none)"))
def room(rng, seconds, amount, hum):
    n = secs(seconds + FADE)
    t = np.arange(n) / SR
    body = d.lp(d.hp(d.noise(n, rng, "pink"), 180, 1), 1500 + 300 * amount, 1) * wander(n, rng, 0.90, 1.0, 2.5, 7.0)
    air = d.lp(d.hp(d.noise(n, rng, "pink"), 500, 1), 2700, 1) * wander(n, rng, 0.84, 1.0, 3.5, 9.0)
    casing = bpq(d.noise(n, rng, "white"), rng.uniform(420, 600), 6.0) + 0.7 * bpq(d.noise(n, rng, "white"), rng.uniform(700, 920), 7.0)
    bearing = d.lp(d.noise(n, rng, "brown"), 90, 1)
    f = round(60.0 * seconds) / seconds                       # a whole number of cycles, so the hum closes the loop
    mains = (0.65 * np.sin(2 * np.pi * f * t) + 0.28 * np.sin(2 * np.pi * 2 * f * t)) * wander(n, rng, 0.72, 1.0, 1.8, 5.5)
    y = unit(body) * (0.40 + 0.28 * amount) + unit(air) * (0.10 + 0.14 * amount) + unit(casing) * 0.02 + unit(bearing) * 0.03 \
        + mains * 0.03 * hum
    return close(d.stereo(d.lp(y, 2800 + 1500 * amount, 1)), seconds)   # mono on purpose: widening a steady hush thins it and makes it restless
