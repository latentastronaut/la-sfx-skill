"""Sounds built from measured shapes: footsteps (wood, concrete, dirt) and a close stream.

Each was measured from reference recordings chosen by ear: the loudness of 32 frequency bands every few
milliseconds, per step (data/steps.npz, about 85 steps) or over a whole take (data/stream.npz). A step is then one
broadband noise shaped to a measured step, chosen at random and varied in length, tone and level, so no two are alike.
No audio is stored or played back; the data files hold loudness curves only.

What was tried and rejected on the way: a separate noise per band rang like a struck cable; grass, gravel and snow
came out wet and close by this method and are not offered.
"""
import os

import numpy as np
from scipy import signal

import sfx_dsp as d
from sfx_ambience import FADE, close
from sfx_dsp import SR, secs
from sfx_recipes import LEVELS, recipe

LEVELS.update({"footsteps": -24.0, "stream": -30.0})
_LOADED = {}


def _data(name):
    if name not in _LOADED:
        _LOADED[name] = np.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", name + ".npz"))
    return _LOADED[name]


def shaped_noise(rng, env, edges, hop=120, grain=0.0):
    """Noise whose loudness follows `env` (bands x frames, one frame per `hop` samples), smooth across frequency."""
    n = env.shape[1] * hop
    cen = np.sqrt(edges[:-1] * edges[1:])
    dens = env / np.sqrt(edges[1:] - edges[:-1])[:, None]       # level per Hz, so wide and narrow bands compare
    out = np.zeros(n)
    for win, lo, hi in ((2048, 0.0, 700.0), ((256 if grain <= 0 else 96), 700.0, 30000.0)):          # long windows for the lows, short for the highs: sharp attacks stay sharp
        step = win // 4
        carrier = rng.standard_normal(n)
        if grain > 0 and lo > 0:                                # dry, crisp grain: the highs are made of separate tiny clicks, not a smooth hiss
            p_on = 1.0 - 0.985 * grain
            carrier = carrier * (rng.random(n) < p_on) / np.sqrt(p_on)
        f, t, Z = signal.stft(carrier, SR, nperseg=win, noverlap=win - step, boundary="zeros", padded=True)
        frames = np.clip((t * SR / hop), 0, env.shape[1] - 1)
        at_t = np.stack([np.interp(frames, np.arange(env.shape[1]), dens[b]) for b in range(len(cen))])      # bands x stft frames
        logf = np.log(np.maximum(f, 20.0))
        mask = np.stack([np.interp(logf, np.log(cen), at_t[:, j]) for j in range(at_t.shape[1])], axis=1)
        mask[(f < 40)] = 0.0
        _, x = signal.istft(Z * mask, SR, nperseg=win, noverlap=win - step)
        x = d.pad_to(x[:n], n)
        x = d.lp(x, hi, 4) if hi < 20000 else x
        x = d.hp(x, lo, 4) if lo > 0 else x
        out += x
    return out


def _gate(T):
    """Fade a measured step to nothing once it has fallen 32 dB below its peak: what is left is the recording's background."""
    total = np.sqrt((T ** 2).sum(axis=0))
    k = int(total.argmax())
    keep = np.ones_like(total)
    low = np.nonzero(total[k:] < total[k] * 0.025)[0]
    if len(low):
        end = k + int(low[0])
        fade = np.clip(1.0 - (np.arange(len(total)) - end) / 12.0, 0.0, 1.0)     # 30 ms
        keep = np.where(np.arange(len(total)) > end, fade, 1.0)
    return T * keep[None, :]


@recipe("foley", "Footsteps: every step follows the measured shape of a real recorded step, as one broadband noise with nothing to ring; no two alike.",
        "A character walking, a point-of-view shot, a story or podcast scene, a game. Each step has a mark at the heel strike.",
        sync=("each foot landing", "Steps are about 1 / `pace` seconds apart with slight human unevenness; each has a mark (step1, step2, ...) at the heel strike."),
        surface=("wood", "wood, concrete or dirt (the surfaces that passed by ear; grass, gravel and snow did not)"),
        steps=(6, "number of steps"),
        pace=(0.0, "steps per second; 0 = the pace of the measured walk (about 1.7 to 2)"),
        weight=(0.5, "how heavily the feet land (0 = light, 1 = stomping): more low end"),
        dry=(-1.0, "how crisp and dry the surface sounds (0 = soft and smooth, 1 = separate dry grains); -1 = the surface's own setting (0 on wood and concrete)"))
def footsteps(rng, surface, steps, pace, weight, dry):
    data = _data("steps")
    if surface not in ("wood", "concrete", "dirt"):
        raise ValueError("footsteps: surface must be wood, concrete or dirt. Grass, gravel and snow were rejected by ear: fetch a recording for those")
    bank, edges = data[surface].astype(np.float64), data["edges"].astype(np.float64)
    power = (bank ** 2).sum(axis=(1, 2))
    tot = np.sqrt((bank ** 2).sum(axis=1))
    dur = (tot > 0.1 * tot.max(axis=1, keepdims=True)).sum(axis=1)
    ok = (power >= 0.45 * np.median(power)) & (dur >= 0.6 * np.median(dur)) & (dur <= 1.6 * np.median(dur))
    bank = bank[ok]                                             # drop fragments and doubles: steps the measuring cut badly
    gap = 1.0 / pace if pace > 0 else float(data[surface + "_gap"][0])
    times = 0.03 + np.cumsum(np.concatenate([[0.0], gap * rng.uniform(0.94, 1.06, int(steps) - 1)]))
    frames = int((times[-1] + 1.0) * SR / 120)
    env = np.zeros((32, frames))
    last = []
    for t0 in times:
        k = int(rng.choice([j for j in range(len(bank)) if j not in last]))
        last = (last + [k])[-min(6, len(bank) - 1):]
        T = _gate(bank[k])
        stretch = rng.uniform(0.92, 1.1)
        m = int(T.shape[1] * stretch)
        a = int((t0 - 0.02 * stretch) * SR / 120)
        m = min(m, frames - a)
        colour = d.db(np.interp(np.arange(32), [0, 10, 21, 31], rng.uniform(-2.0, 2.0, 4)) + (weight - 0.5) * 6.0 * np.linspace(1, -0.3, 32))
        src = np.arange(m) / stretch
        for b in range(32):
            env[b, a:a + m] += np.interp(src, np.arange(T.shape[1]), T[b]) * colour[b] * d.db(rng.uniform(-2.0, 2.0))
    grain = dry if dry >= 0 else (0.0 if surface in ("wood", "concrete") else 0.95)
    y = shaped_noise(rng, env, edges, grain=grain)
    return d.finish(d.stereo(y), fade_in=0.001, fade_out=0.03, tail_db=-60.0), {f"step{i + 1}": float(x) for i, x in enumerate(times)}


@recipe("bed", "A stream: one broadband noise shaped, smoothly across frequency, to loudness curves measured on real stream recordings.",
        "A brook, a river bank, a garden fountain, a calm nature scene. Loops without a seam.",
        sync=("the start of the scene", "Not frame-critical. Fade it in and out in the edit."),
        seconds=(12.0, "length of the loop (up to about 22 s)"),
        take=(0, "which measured stream to follow: 1, 2 or 3; 0 = all three in a random order"),
        bright=(0.5, "how much the highs are held back (0 = as measured, 0.5 = softer, 1 = dull and distant)"))
def stream(rng, seconds, take, bright):
    tex = _data("stream")
    bank, edges = tex["stream"].astype(np.float64), tex["edges"].astype(np.float64)
    order = [(int(take) - 1) % len(bank)] if take else list(rng.permutation(len(bank)))
    T = np.concatenate([bank[k] for k in order], axis=1)
    need = int((seconds + FADE) * SR / 240) + 2
    if need > T.shape[1]:
        raise ValueError(f"stream: seconds can be at most {T.shape[1] * 240 / SR - FADE:.1f}")
    start = int(rng.integers(0, T.shape[1] - need + 1))
    cen = np.sqrt(edges[:-1] * edges[1:])
    env = T[:, start:start + need] * d.db(-5.0 * np.clip(np.log2(cen / 2500.0), 0.0, 2.0) / 2.0 * bright / 0.5)[:, None]   # the water was too prominent in the highs
    left, right = shaped_noise(rng, env, edges, hop=240), shaped_noise(rng, env, edges, hop=240)
    y = np.stack([left, right], axis=1)[:secs(seconds + FADE)]
    mid = y.mean(axis=1, keepdims=True)
    return close(mid + (y - mid) * 0.6, seconds)
