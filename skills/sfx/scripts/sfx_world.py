"""Real-world sounds that passed by ear: a spark, crickets, the sea.

Water drops, a stream, pouring, footsteps, breaking glass, an engine and arcing were built here from published
physical models with no recording to fit them to, and every one was rejected by ear. The ones that passed were fitted to recordings. For the rejected kinds, use a found recording.
"""
import numpy as np
from scipy import signal  # noqa: F401

import sfx_dsp as d
from sfx_ambience import BED_SYNC, FADE, bpq, close, put, spread, unit, wander  # noqa: F401
from sfx_dsp import SR, secs
from sfx_recipes import LEVELS, recipe

LEVELS.update({"spark": -22.0, "crickets": -34.0, "ocean": -28.0})


@recipe("scifi", "A spark: the sharp snap of electricity jumping a gap.",
        "A short circuit, a broken machine, a plug going in, a 'zap' with a real-world edge (see scifi kind=zap for a clean one).")
def spark(rng):
    k = secs(0.5)
    t = np.arange(k) / SR
    e1 = np.clip(1.0 - t / 0.5, 0, 1) ** 3
    e2 = np.clip(1.0 - t / 0.010, 0, 1)
    raw = e1 * rng.standard_normal(k) * 0.5 + d.sine(e2 * 7000.0 + 20.0) * e2
    f = sum(bpq(raw, c * 1.8, q) * g for c, q, g in ((4600, 5, 2.0), (7200, 5, 2.0), (480, 7, 1.2), (720, 8, 2.5)))
    y = bpq(f, 2500.0, 0.5) * np.exp(-t / 0.06)
    return d.finish(d.reverb(d.stereo(y), t60=0.3, mix=0.1, bright=0.7, seed=int(rng.integers(1 << 30))), fade_in=0.0002, fade_out=0.03, tail_db=-55.0)


@recipe("bed", "Crickets: each one a steady 'chirp, chirp, chirp' of three or four quick pulses, several of them at their own pace.",
        "A night scene, a warm evening outdoors, or the lone cricket of an awkward silence (count=1). Loops without a seam.",
        sync=BED_SYNC,
        seconds=(12.0, "length of the loop (8-30)"),
        count=(4, "number of crickets (1 = the lone cricket of an awkward pause)"),
        pitch=(4900.0, "pitch of the song in Hz (measured on a field cricket: 4900)"),
        pace=(1.0, "overall speed (1 = as measured; 0.6 = a cold night)"),
        rests=(0.0, "how often it stops for a second or two (0 = never, as in the recording; 1 = often)"))
def crickets(rng, seconds, count, pitch, pace, rests):
    # Measured chirp by chirp on a solo field cricket (Gryllus campestris), and checked by ear:
    # - a chirp is 4 pulses (now and then 3), 31 ms apart, at 4.9 kHz; the first pulse is quiet and the rest are near full;
    # - chirps come in small clusters, not a steady stream: 3 to 8 at a fast pace (205 ms apart), with a breath between
    #   clusters that is about one missed beat;
    # - the pace changes by passage: fast clusters, then slow ones (pairs and triples, 330 ms apart), then medium ones,
    #   with a pause of about half a second between passages;
    # - its loudness drifts slowly as it turns. Crickets do not answer each other; each keeps its own pattern.
    n = secs(seconds + FADE)
    y = np.zeros((n, 2))
    one = int(count) == 1
    passages = {"fast": (0.205, (3, 9), (0.09, 0.21)), "medium": (0.26, (1, 8), (0.1, 0.2)), "slow": (0.33, (2, 4), (0.12, 0.2))}
    for k in range(int(count)):
        f = pitch * (1.0 if one else rng.uniform(0.95, 1.05))
        far = 0.0 if one else float(np.clip(k / max(int(count) - 1, 1) + rng.uniform(-0.12, 0.12), 0.0, 1.0))   # one close, the rest further and further off
        pos = 0.0 if one else rng.uniform(-0.9, 0.9)
        voice = np.zeros((n, 2))
        turn = wander(n, rng, 0.45, 1.0, 2.0, 7.0)              # louder and softer as it moves about
        t, last = rng.uniform(0.0, 1.0), None
        while t < n / SR:
            name = rng.choice([p for p in passages if p != last], p=None)
            last = name
            beat, size, breath = passages[name]
            for _ in range(int(rng.integers(2, 6))):            # clusters in this passage
                for _ in range(int(rng.integers(*size))):
                    if t >= n / SR:
                        break
                    pulses = 4 if rng.random() < 0.9 else 3
                    for i, lv in enumerate((0.3, 0.8, 0.95, 1.0)[4 - pulses:]):
                        m = secs(0.018 * rng.uniform(0.94, 1.06))
                        tt = np.arange(m) / SR
                        tone = np.sin(2 * np.pi * f * (tt - 0.6 * tt * tt))     # the pitch sags a little through each pulse
                        put(voice, tone * np.sin(np.pi * tt / (m / SR)) ** 0.8, secs(t + i * 0.0312), pos,
                            lv * turn[min(secs(t), n - 1)] * rng.uniform(0.92, 1.0))
                    t += beat / pace * rng.uniform(0.96, 1.04)
                t += rng.uniform(*breath) / pace                # the breath between clusters
            t += (rng.uniform(1.0, 2.5) if rng.random() < 0.5 * rests else rng.uniform(0.2, 0.3)) / pace
        if far > 0:                                             # distance: quieter, duller, and with more of the open air round it
            voice = d.lp(voice, 9000.0 * 2.0 ** (-1.6 * far), 2)
            voice = voice + d.reverb(voice, t60=0.9, mix=1.0, bright=0.25, pre_delay=0.02, seed=int(rng.integers(1 << 30)))[:n] * 0.5 * far
        y += voice * np.exp(-3.4 * far)
    return close(y, seconds)


@recipe("bed", "The sea on a beach: each wave swells, breaks, washes up and drags back, no two the same.",
        "A beach, a coast, calm and space, a holiday scene, the end of a story. Loops without a seam; use a long loop.",
        sync=BED_SYNC,
        seconds=(30.0, "length of the loop (20-60; a wave takes 8 to 15 s, so shorter loops repeat noticeably)"),
        amount=(0.5, "wave size (0 = lapping, 1 = heavy surf)"),
        foam=(0.5, "brightness of the break and the wash (0 = dull and distant, 1 = hissing foam close by)"))
def ocean(rng, seconds, amount, foam):
    n = secs(seconds + FADE)
    undertow = d.bp(d.noise(n, rng, "pink"), 150.0, 450.0, 2)     # measured surf has little under 100 Hz
    surf = d.lp(d.hp(d.noise(n, rng, "pink"), 220, 1), 2000, 1)
    crash = d.lp(d.hp(d.noise(n, rng, "pink"), 650, 1), 2500 + 2500 * foam, 1)
    back = d.lp(d.hp(d.noise(n, rng, "pink"), 130, 1), 650, 1)
    env, e_crash, e_back, pan = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n)
    t0 = -rng.uniform(2.0, 6.0)
    while t0 < n / SR:
        period = rng.uniform(5.0 + amount * 5.0, 10.0 + amount * 10.0)
        a0, k = max(secs(t0), 0), secs(period)
        idx = np.arange(a0, min(secs(t0) + k, n))
        if len(idx):
            p = (idx - secs(t0)) / k
            size = rng.uniform(0.45, 1.0)
            w = np.where(p < 0.38, (p / 0.38) ** 1.6, np.where(p < 0.52, 1.0, ((1.0 - p) / 0.48) ** 0.75)) * size
            env[idx] = np.maximum(env[idx], w)
            tc = (p - 0.34) * period                            # the break: a fold-over, not a slap
            c = np.where(tc > 0, np.minimum(0.5 - 0.5 * np.cos(np.pi * np.clip(tc / (0.2 + 0.5 * amount), 0, 1)), 1.0) * np.exp(-3.0 * np.maximum(tc - (0.2 + 0.5 * amount), 0) / (0.3 * period)), 0.0)
            e_crash[idx] = np.maximum(e_crash[idx], c * size * rng.uniform(0.55, 1.0))
            e_back[idx] = np.maximum(e_back[idx], np.where(p >= 0.6, np.sin(np.pi * np.clip((p - 0.6) / 0.4, 0, 1)) ** 1.3, 0.0) * size)
            pan[idx] = rng.uniform(-0.15, 0.15)                 # a wave leans a little to one side; more than this was heard as one ear cutting out
        t0 += period * rng.uniform(0.75, 1.0)                   # waves overlap a little
    pan = d.lp(pan, 0.15, 1)
    moving = unit(surf) * (0.08 + 0.92 * env ** 1.8) * (0.14 + 0.32 * foam) * (0.6 + 0.4 * amount) + unit(crash) * e_crash * (0.05 + 0.6 * foam ** 2) \
        + unit(back) * e_back * 0.15
    # waves lean slightly to a side (kept). Centring them and spreading their highs instead was heard as artifacts.
    y = d.pan(moving, pan) * 1.6 + spread(unit(undertow) * (0.24 + 0.76 * env) * (0.45 + 0.3 * amount), rng, 800.0, 16.0)
    return close(d.hp(y, 60.0, 2), seconds)
