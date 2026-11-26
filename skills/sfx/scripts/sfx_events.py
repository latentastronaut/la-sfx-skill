"""Big natural events: thunder and explosions.

Both follow published designs (Andy Farnell, *Designing Sound*, practicals 17 and 31; the thunder roll follows the
SleepSounds thunder worklet). The shared idea: a big distant event is not one bang with a fade. Its sound arrives over
seconds from many places, so it is built from several overlapping low surges, each with its own rise and fall.
"""
import numpy as np

import sfx_dsp as d
from sfx_ambience import bpq, burst, put
from sfx_dsp import SR, secs
from sfx_recipes import LEVELS, recipe

LEVELS.update({"thunder": -26.0, "explosion": -17.0})


def _surge(rng, n, at, cutoff, attack, fall, peak):
    """Low-passed noise that rises in `attack` seconds and dies away with time-constant `fall`."""
    m = min(secs(attack + fall * 6.0), n - at)
    if m <= 8:
        return np.zeros(0)
    t = np.arange(m) / SR
    env = np.minimum(t / attack, 1.0) * np.exp(-np.maximum(t - attack, 0.0) / fall)
    return d.lp(rng.standard_normal(m), cutoff, 2) * env * peak


@recipe("nature", "Thunder: a low roll that arrives in uneven surges and takes a long time to die away.",
        "A storm, a dramatic turn, a reveal with menace, a scene change to bad weather. Keep it under the scene. "
        "Real thunder follows its lightning by about 3 seconds per kilometre: put the flash that much earlier.",
        sync=("the first sound of the thunder", "The first surge is at the start of the file. "
              "Place it after the lightning flash: 0.3 s for a strike overhead, 3 s for one a kilometre away."),
        distance=(0.5, "0 = close: a hard, fuller first surge; 1 = far off: a soft start and only the deepest rumble"),
        size=(0.6, "how big the roll is: the number of surges (0-1)"),
        seconds=(14.0, "about how long the roll lasts (8-25); real thunder rumbles on far longer than it seems to"))
def thunder(rng, distance, size, seconds):
    near = 1.0 - distance
    n = secs(seconds + 8.0)
    y = np.zeros((n, 2))
    where = rng.uniform(-0.3, 0.3)
    # surge times: uneven on purpose. Evenly spaced surges were heard as a clock. Gaps are random and mostly short early on,
    # with the odd long pause, and each surge has its own size.
    times, t = [0.0], 0.0
    for _ in range(int(3 + 7 * size)):
        t += rng.exponential(seconds / (4.0 + 6.0 * size)) * rng.uniform(0.3, 1.7) + 0.25
        if t > seconds * 0.9:
            break
        times.append(t)
    for k, t in enumerate(times):
        progress = t / seconds
        level = (1.0 if k == 0 else np.exp(rng.uniform(-1.4, 0.0))) * (1.0 - 0.6 * progress)
        for _ in range(int(rng.integers(1, 4))):               # each surge is a few overlapping swells, never one clean bump
            at = secs(max(0.0, t + (rng.uniform(-0.35, 0.35) if k else rng.uniform(0.0, 0.12))))
            cutoff = rng.uniform(60.0, 130.0) * (1.0 + 1.2 * near * (k == 0))       # only the first, when close, is fuller
            attack = rng.uniform(0.02, 0.06) if (k == 0 and near > 0.4) else rng.uniform(0.12, 0.5)
            g = _surge(rng, n, at, cutoff, attack, rng.uniform(0.8, 2.6), level * rng.uniform(0.5, 1.0))
            put(y, g, at, where + rng.uniform(-0.3, 0.3))
    deep = _surge(rng, n, 0, rng.uniform(45.0, 65.0), 0.3, seconds * rng.uniform(0.25, 0.4), 0.5)
    put(y, deep, 0, 0.0)
    y = y / (np.max(np.abs(y)) + 1e-9)
    wet = d.reverb(y, t60=5.0 + 4.0 * distance, mix=0.3 + 0.3 * distance, bright=0.15, pre_delay=0.04, seed=int(rng.integers(1 << 30)))
    wet = d.lp(d.hp(wet, 22.0, 2), 300.0 + 900.0 * near, 1)    # measured: real thunder has almost nothing above 500 Hz
    return d.finish(d.trim(np.tanh(wet / (np.max(np.abs(wet)) + 1e-9) * 1.3), -58, keep=0.05), fade_in=0.004, fade_out=2.0)


@recipe("impact", "An explosion: a full-range bang, a low body that sinks away, and the echo of the bang rolling off.",
        "Action, a joke payoff, a game, 'mind blown', destruction. The bang is the start of the file.",
        size=(0.6, "small bang to huge blast (0-1): the weight and length of the low body and of the echo"),
        spread=(0.0, "0 = one bang; up to 1 = two more blasts following within half a second"),
        distance=(0.3, "0 = close and sharp, 1 = far away: duller and softer at the start, with more echo"),
        debris=(0.2, "level of the bits falling after the bang (0 = none)"))
def explosion(rng, size, spread, distance, debris):
    n = secs(2.5 + 5.0 * size)
    t = np.arange(n) / SR
    y = np.zeros(n)
    blasts = [(0.0, 1.0)] + [(rng.uniform(0.08, 0.5) * spread, rng.uniform(0.4, 0.8)) for _ in range(2 if spread > 0 else 0)]
    for at, g in blasts:
        k = n - secs(at)
        tt = t[:k]
        # the bang is noise across the whole range (measured on a real cannon: every band is equally loud for the first
        # quarter second), falling fast; a low rumble alone was heard as hollow
        bang = d.lp(rng.standard_normal(k), 6000.0 - 4500.0 * distance, 1) * np.minimum(tt / (0.002 + 0.02 * distance), 1.0) * np.exp(-tt / 0.28)
        body = d.lp(rng.standard_normal(k), 140.0, 2) * 6.0 * np.minimum(tt / 0.01, 1.0) * np.exp(-tt / (0.3 + 0.9 * size))
        f = 45.0 + 70.0 * np.exp(-tt / 0.25)                    # the fireball: a low band of noise that sinks in pitch
        ball = d.sweep(d.sweep(rng.standard_normal(k), "bp", f, q=1.0), "lp", f * 1.5, q=0.707)
        ball = ball / (np.std(ball) + 1e-9) * np.minimum(tt / 0.08, 1.0) * np.exp(-tt / (0.5 + 1.4 * size))
        y[secs(at):] += g * (bang * 1.0 + np.tanh(body) * 0.9 + ball * 0.5 * size)
    y = np.tanh(y * 1.4)
    out = d.widen(y, rng, 0.3)
    # the echo is the bang itself coming back off everything around, in the middle of the range and for seconds
    echo = d.reverb(d.bp(out, 150.0, 2500.0 - 1200.0 * distance, 1), t60=2.0 + 3.0 * size, mix=1.0, bright=0.35, pre_delay=0.06,
                    seed=int(rng.integers(1 << 30)))
    parts = [(out, 0, 0), (echo, 0, -9 + 5 * distance)]
    if debris > 0:
        bits = np.zeros((n, 2))
        for at in np.nonzero(rng.random(n) < (25.0 * np.exp(-t / 0.7) * (t > 0.15)) / SR)[0]:
            put(bits, bpq(burst(rng, rng.uniform(0.004, 0.02), 7.0, 0.0008), rng.uniform(500.0, 2200.0), 0.7), int(at), rng.uniform(-0.8, 0.8),
                np.exp(rng.uniform(-2.5, 0.0)))
        parts.append((d.reverb(bits, t60=0.6, mix=0.3, bright=0.3, seed=int(rng.integers(1 << 30))), 0, -26 + 14 * debris))
    return d.finish(d.trim(d.layer(parts), -60, keep=0.05), fade_in=0.0005, fade_out=0.8)
