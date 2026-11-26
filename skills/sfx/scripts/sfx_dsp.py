"""Building blocks for sound effects: sources, envelopes, filters, space, transforms, file I/O.

Everything is numpy/scipy, offline and seeded. Signals are float arrays in [-1, 1] at SR, either mono (n,) or
stereo (n, 2). Functions take and return either unless they say otherwise.
"""
import shutil
import subprocess
import warnings
import wave
from math import gcd
from pathlib import Path

import numpy as np
from scipy import signal
from scipy.io import wavfile

SR = 48000


# ---------------------------------------------------------------- basics
def secs(seconds):
    return max(1, int(round(seconds * SR)))


def db(x):
    """Decibels to a linear gain."""
    return 10.0 ** (x / 20.0)


def to_db(x):
    return 20.0 * np.log10(np.maximum(np.abs(x), 1e-12))


def stereo(x):
    return x if x.ndim == 2 else np.stack([x, x], axis=1)


def mono(x):
    return x if x.ndim == 1 else x.mean(axis=1)


def per_channel(fn, x, *a, **k):
    if x.ndim == 1:
        return fn(x, *a, **k)
    return np.stack([fn(x[:, c], *a, **k) for c in range(x.shape[1])], axis=1)


def pad_to(x, n):
    if len(x) >= n:
        return x
    shape = (n - len(x),) + x.shape[1:]
    return np.concatenate([x, np.zeros(shape, dtype=x.dtype)])


# ---------------------------------------------------------------- curves and envelopes
def line(n, a, b, curve=1.0):
    """a to b over n samples. curve > 1 stays near a for longer (a late rise), curve < 1 moves early."""
    return a + (b - a) * np.linspace(0.0, 1.0, n) ** curve


def glide(n, f0, f1, curve=1.0):
    """A frequency glide that is even in pitch (geometric), which is how the ear hears a sweep."""
    return f0 * (f1 / f0) ** (np.linspace(0.0, 1.0, n) ** curve)


def decay(n, t60):
    """Exponential decay that falls 60 dB in t60 seconds."""
    return np.exp(-6.908 * np.arange(n) / (t60 * SR))


def perc(n, attack=0.002, t60=0.3):
    """A percussive envelope: a short raised-cosine attack, then an exponential decay."""
    a = min(secs(attack), n)
    e = decay(n, t60)
    e[:a] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(a) / a)
    return e


def bell_curve(n, peak=0.5, width=0.25, skew=1.0):
    """A smooth hump that peaks at `peak` (0..1 of the length). skew > 1 makes the fall slower than the rise."""
    x = np.linspace(0.0, 1.0, n)
    w = np.where(x < peak, width, width * skew)
    return np.exp(-0.5 * ((x - peak) / w) ** 2)


def fade(x, fade_in=0.0, fade_out=0.0):
    """Raised-cosine fades. Every sound should start and end at zero, or it clicks."""
    y = x.copy()
    n = len(y)
    a, b = min(secs(fade_in), n) if fade_in else 0, min(secs(fade_out), n) if fade_out else 0
    if a:
        w = 0.5 - 0.5 * np.cos(np.pi * np.arange(a) / a)
        y[:a] = y[:a] * (w if y.ndim == 1 else w[:, None])
    if b:
        w = 0.5 + 0.5 * np.cos(np.pi * np.arange(b) / b)
        y[-b:] = y[-b:] * (w if y.ndim == 1 else w[:, None])
    return y


def gain_env(x, env):
    return x * (env if x.ndim == 1 else env[:, None])


# ---------------------------------------------------------------- sources
def _phase(freq, n=None):
    """Running phase in cycles for a frequency that may change every sample."""
    f = np.full(n, float(freq)) if np.isscalar(freq) else np.asarray(freq, dtype=float)
    return np.concatenate([[0.0], np.cumsum(f[:-1])]) / SR, f


def sine(freq, n=None, phase=0.0):
    p, _ = _phase(freq, n)
    return np.sin(2 * np.pi * (p + phase))


def _polyblep(p, dt):
    """Correction that removes most aliasing from a saw or square edge."""
    out = np.zeros_like(p)
    lo = p < dt
    x = p[lo] / dt[lo]
    out[lo] = x + x - x * x - 1.0
    hi = p > 1.0 - dt
    x = (p[hi] - 1.0) / dt[hi]
    out[hi] = x * x + x + x + 1.0
    return out


def saw(freq, n=None, phase=0.0):
    p, f = _phase(freq, n)
    p = (p + phase) % 1.0
    return 2.0 * p - 1.0 - _polyblep(p, f / SR)


def square(freq, n=None, width=0.5, phase=0.0):
    p, f = _phase(freq, n)
    p = (p + phase) % 1.0
    dt = f / SR
    return np.where(p < width, 1.0, -1.0) + _polyblep(p, dt) - _polyblep((p - width) % 1.0, dt)


def triangle(freq, n=None, phase=0.0):
    p, _ = _phase(freq, n)
    return 4.0 * np.abs(((p + phase + 0.25) % 1.0) - 0.5) - 1.0


def fm(carrier, ratio, index, n=None):
    """Two-operator FM (one sine bending another's phase). index may be an envelope; bigger = brighter, more metallic."""
    pc, _ = _phase(carrier, n)
    f = np.full(len(pc), float(carrier)) if np.isscalar(carrier) else np.asarray(carrier, dtype=float)
    pm, _ = _phase(f * ratio)
    return np.sin(2 * np.pi * pc + index * np.sin(2 * np.pi * pm))


def noise(n, rng, color="white"):
    """white = flat hiss; pink = equal energy per octave (natural, the usual choice); brown = rumble."""
    w = rng.standard_normal(n)
    if color == "white":
        return w / 3.0
    tilt = {"pink": 0.5, "brown": 1.0, "blue": -0.5}[color]
    spec = np.fft.rfft(w)
    f = np.fft.rfftfreq(n, 1.0 / SR)
    f[0] = f[1] if n > 1 else 1.0
    shape = np.maximum(f, 20.0) ** (-tilt)
    y = np.fft.irfft(spec * shape, n)
    return y / (np.sqrt(np.mean(y * y)) * 3.0 + 1e-12)


def modal(freqs, t60s, amps, n, rng=None, hardness=0.5):
    """A struck object: a sum of ringing partials, hit by a short pulse. hardness sets how bright the strike is."""
    tt = np.arange(n) / SR
    y = np.zeros(n)
    for f, d, a in zip(freqs, t60s, amps):
        if f < SR * 0.45:
            ph = 0.0 if rng is None else rng.uniform(0, 0.25)
            y += a * np.exp(-6.908 * tt / d) * np.sin(2 * np.pi * (f * tt + ph))
    m = max(1, secs(0.00003 + 0.0007 * (1.0 - hardness) ** 2))  # contact time: a soft mallet stays on longer and dulls the top
    pulse = np.hanning(2 * m + 1) if m > 1 else np.array([1.0])
    return signal.fftconvolve(y, pulse / pulse.sum())[:n]


def pluck(freq, n, rng, t60=1.5, bright=0.5):
    """Karplus-Strong: a burst of noise circulating in a tuned delay; a plucked string or a tight tom."""
    period = max(2, int(round(SR / freq)))
    burst = np.zeros(n)
    burst[:period] = lp(rng.uniform(-1, 1, period + 64), 1500 + 9000 * bright)[64:]
    g = 10 ** (-3.0 * period / (t60 * SR))
    a = np.zeros(period + 2)
    a[0], a[period], a[period + 1] = 1.0, -g * (0.5 + 0.5 * bright), -g * (0.5 - 0.5 * bright)
    return signal.lfilter([1.0], a, burst)


# ---------------------------------------------------------------- filters
def _sos(kind, f, order):
    f = np.clip(np.atleast_1d(f).astype(float), 10.0, SR * 0.49)
    return signal.butter(order, f if len(f) > 1 else f[0], btype=kind, fs=SR, output="sos")


def lp(x, f, order=2):
    return signal.sosfilt(_sos("lowpass", f, order), x, axis=0)


def hp(x, f, order=2):
    return signal.sosfilt(_sos("highpass", f, order), x, axis=0)


def bp(x, lo, hi, order=2):
    return signal.sosfilt(_sos("bandpass", [lo, hi], order), x, axis=0)


def _biquad(kind, f, q):
    w = 2 * np.pi * min(max(f, 10.0), SR * 0.45) / SR
    c, al = np.cos(w), np.sin(w) / (2.0 * q)
    if kind == "lp":
        b = [(1 - c) / 2, 1 - c, (1 - c) / 2]
    elif kind == "hp":
        b = [(1 + c) / 2, -(1 + c), (1 + c) / 2]
    elif kind == "bp":
        b = [al, 0.0, -al]
    else:
        raise ValueError(f"unknown filter kind {kind!r} (lp, hp, bp)")
    a0 = 1 + al
    return np.array(b) / a0, np.array([1.0, -2 * c / a0, (1 - al) / a0])


def sweep(x, kind, freq, q=0.707, block=32):
    """A filter whose cutoff moves: the heart of risers, whooshes and wah-like motion.

    freq (and q) are per-sample arrays or scalars. Higher q = a whistling, resonant peak at the cutoff.
    """
    n = len(x)
    f = np.full(n, float(freq)) if np.isscalar(freq) else np.asarray(freq, dtype=float)
    qq = np.full(n, float(q)) if np.isscalar(q) else np.asarray(q, dtype=float)

    def one(ch):
        out, zi = np.empty(n), np.zeros(2)
        for i in range(0, n, block):
            b, a = _biquad(kind, f[i], qq[i])
            out[i:i + block], zi = signal.lfilter(b, a, ch[i:i + block], zi=zi)
        return out

    return per_channel(one, x)


def tilt(x, db_per_octave, pivot=1000.0):
    """Tilt the whole spectrum: negative = darker and heavier, positive = brighter and thinner."""
    def one(ch):
        spec = np.fft.rfft(ch)
        f = np.maximum(np.fft.rfftfreq(len(ch), 1.0 / SR), 20.0)
        return np.fft.irfft(spec * (f / pivot) ** (db_per_octave / 6.0206), len(ch))
    return per_channel(one, x)


# ---------------------------------------------------------------- colour and dynamics
def saturate(x, drive=2.0):
    """Soft clipping (tanh), oversampled so it adds warmth instead of fizz. Glues layers and thickens lows."""
    up = signal.resample_poly(x, 2, 1, axis=0)
    y = np.tanh(up * drive) / np.tanh(drive)
    return signal.resample_poly(y, 1, 2, axis=0)[:len(x)]


def envelope(x, attack=0.002, release=0.05):
    """The loudness outline of a sound, for imposing on another sound or for ducking."""
    r = np.abs(mono(x))
    ca, cr = np.exp(-1.0 / (attack * SR)), np.exp(-1.0 / (release * SR))
    out, e = np.empty(len(r)), 0.0
    for i, v in enumerate(r):
        e = v + (ca if v > e else cr) * (e - v)
        out[i] = e
    return out


def transient(x, attack_gain=1.5, sustain_gain=1.0):
    """Push the hit (attack) and the ring (sustain) apart: more punch, or a softer front."""
    fast, slow = envelope(x, 0.0005, 0.02), envelope(x, 0.02, 0.2)
    amt = np.clip((fast - slow) / (fast + 1e-9), 0.0, 1.0)
    return gain_env(x, sustain_gain + (attack_gain - sustain_gain) * amt)


# ---------------------------------------------------------------- space
def pan(x, pos):
    """Mono to stereo. pos is -1 (left) to 1 (right), a number or a per-sample curve. Equal power."""
    th = (np.asarray(pos, dtype=float) + 1.0) * np.pi / 4.0
    m = mono(x)
    return np.stack([m * np.cos(th), m * np.sin(th)], axis=1)


def widen(x, rng, amount=0.5):
    """Make a mono sound wide: a short diffuse echo is added to one ear and subtracted from the other.

    The two cancel when summed, so the sound is unchanged on a mono phone speaker. Lows stay centred.
    """
    m = mono(x)
    k = secs(0.025)
    burst = rng.standard_normal(k) * np.exp(-np.arange(k) / (k / 4.0))
    burst[:secs(0.002)] = 0.0                                 # a gap first, so transients stay sharp
    side = hp(signal.fftconvolve(m, burst / np.sqrt(np.sum(burst * burst)))[:len(m)], 200.0, 2) * amount
    return np.stack([m + side, m - side], axis=1)


def reverb_ir(t60=1.5, bright=0.5, pre_delay=0.012, seed=0):
    """A synthetic room: decaying noise whose highs die first, after a few early echoes. No sample files needed."""
    r = np.random.default_rng(seed)
    n, pre = secs(t60 * 1.15), secs(pre_delay)
    tt = np.arange(n) / SR
    ir = np.zeros((n + pre, 2))
    for c in range(2):
        w = r.standard_normal(n)
        lo, mid, hi = lp(w, 350), bp(w, 350, 3500), hp(w, 3500)
        body = (lo * np.exp(-6.908 * tt / (t60 * 1.2)) + mid * np.exp(-6.908 * tt / t60)
                + hi * np.exp(-6.908 * tt / (t60 * (0.2 + 0.6 * bright))))
        build = min(n, secs(0.004 + 0.012 * min(t60, 3.0)))   # the wash builds up; it doesn't start at full level
        body[:build] *= np.linspace(0.0, 1.0, build) ** 2
        for _ in range(6):                                    # sparse early echoes give the room a size
            k = int(r.uniform(0.004, 0.06) * SR)
            if k < n:
                body[k] += r.uniform(0.3, 0.9) * r.choice([-1.0, 1.0]) * np.sqrt(np.sum(body * body)) * 0.05
        ir[pre:, c] = body
    return ir / np.sqrt(np.sum(ir * ir) / 2.0)


def convolve(x, ir):
    """Play x 'through' ir. ir can be a room, or any sound: its character gets stamped onto x."""
    xs, irs = stereo(x), stereo(ir)
    return np.stack([signal.fftconvolve(xs[:, c], irs[:, c]) for c in range(2)], axis=1)


def reverb(x, t60=1.5, mix=0.25, bright=0.5, pre_delay=0.012, seed=0):
    """Dry sound plus room. The result is longer than the input by the tail. Returns stereo."""
    wet = convolve(x, reverb_ir(t60, bright, pre_delay, seed))
    dry = pad_to(stereo(x), len(wet))
    return dry * (1.0 - mix) + wet * mix


def delay(x, time=0.25, feedback=0.4, mix=0.3, tail=None):
    """Repeating echoes. The result is extended so the echoes can die away."""
    d = secs(time)
    extra = secs(tail if tail is not None else time * np.log(0.001) / np.log(max(feedback, 1e-3)))
    xs = pad_to(x, len(x) + extra)
    a = np.zeros(d + 1)
    a[0], a[d] = 1.0, -feedback
    b = np.zeros(d + 1)
    b[d] = 1.0
    return xs * (1.0 - mix) + signal.lfilter(b, a, xs, axis=0) * mix


# ---------------------------------------------------------------- transforms (any sound in, a new sound out)
def reverse(x):
    return x[::-1].copy()


def pitch(x, semitones):
    """Tape-style pitch change: lower is also longer and heavier, higher is shorter and smaller."""
    ratio = 2.0 ** (semitones / 12.0)
    return signal.resample(x, max(2, int(round(len(x) / ratio))), axis=0)


def warp(x, speed):
    """Play x at a speed that changes over time (1 = normal). Pitch follows speed, like a tape or a record."""
    sp = np.asarray(speed, dtype=float)
    pos = np.concatenate([[0.0], np.cumsum(sp[:-1])])
    pos = pos[pos < len(x) - 1]
    idx = np.arange(len(x))
    return per_channel(lambda ch: np.interp(pos, idx, ch), x)


def stretch(x, factor, window=0.25, seed=0):
    """Extreme time-stretch (the 'paulstretch' method): smears a sound into a pad or drone without changing pitch.

    Good from about 4x to 100x. It blurs transients on purpose; for small changes use pitch() or warp().
    """
    r = np.random.default_rng(seed)
    N = secs(window) // 2 * 2
    win = np.sqrt(np.hanning(N + 1)[:N])
    hop_out, hop_in = N // 2, (N // 2) / factor

    def one(ch):
        ch = np.concatenate([np.zeros(N // 2), ch, np.zeros(N)])
        frames = int((len(ch) - N) / hop_in)
        out = np.zeros(frames * hop_out + N)
        for k in range(frames):
            i = int(k * hop_in)
            mag = np.abs(np.fft.rfft(ch[i:i + N] * win))
            buf = np.fft.irfft(mag * np.exp(1j * r.uniform(0, 2 * np.pi, len(mag))), N) * win
            out[k * hop_out:k * hop_out + N] += buf
        return out[N // 2:]

    return per_channel(one, x)


def granular(x, seconds, rng, grain=0.06, density=40.0, pitch_spread=0.0, pitch_center=0.0, region=(0.0, 1.0),
             spread=1.0, reverse_chance=0.0):
    """Chop a sound into tiny grains and spray them over time: clouds, shimmer, debris, crowds of one sound.

    density is grains per second; pitch_spread is in semitones; region is the part of the source to draw from.
    """
    src = mono(x)
    n = secs(seconds)
    out = np.zeros((n + secs(grain * 4), 2))
    for _ in range(max(1, int(density * seconds))):
        rate = 2.0 ** ((pitch_center + rng.uniform(-pitch_spread, pitch_spread)) / 12.0)
        g = secs(grain * rng.uniform(0.6, 1.4))
        need = int(g * rate) + 2
        lo, hi = int(region[0] * len(src)), max(int(region[1] * len(src)) - need, int(region[0] * len(src)) + 1)
        s0 = int(rng.integers(lo, hi)) if hi > lo else 0
        seg = src[s0:s0 + need]
        if len(seg) < 4:
            continue
        seg = np.interp(np.arange(0, len(seg) - 1, rate), np.arange(len(seg)), seg)[:g]
        if rng.random() < reverse_chance:
            seg = seg[::-1]
        seg = seg * np.hanning(len(seg))
        at = int(rng.integers(0, n))
        th = (rng.uniform(-spread, spread) + 1.0) * np.pi / 4.0
        out[at:at + len(seg), 0] += seg * np.cos(th)
        out[at:at + len(seg), 1] += seg * np.sin(th)
    return out


def doppler(x, speed=30.0, distance=3.0, at=0.5):
    """Make x fly past the listener: pitch drops as it passes, it gets loud and crosses left to right.

    speed in metres per second, distance = how close it passes (metres), at = when it passes (0..1 of the length).
    """
    m = mono(x)
    n = len(m)
    tt = (np.arange(n) / SR) - at * n / SR
    along = speed * tt
    r = np.sqrt(distance ** 2 + along ** 2)
    radial = speed * along / r                                # positive = moving away
    y = warp(m, 1.0 / (1.0 + radial / 343.0))
    r, along = r[:len(y)], along[:len(y)]
    return pan(y * (distance / r), np.clip(along / (distance * 3.0), -1.0, 1.0))


# ---------------------------------------------------------------- putting sounds together
def layer(parts):
    """Mix layers. parts is a list of (signal, start_seconds, gain_db). Returns stereo, as long as the longest."""
    end = max(secs(s) + len(x) for x, s, _ in parts)
    out = np.zeros((end, 2))
    for x, s, g in parts:
        i = secs(s) if s > 0 else 0
        out[i:i + len(x)] += stereo(x) * db(g)
    return out


def trim(x, threshold_db=-70.0, keep=0.005):
    """Cut silence off both ends, keeping a few milliseconds so the edges can fade."""
    level = np.abs(x).max(axis=1) if x.ndim == 2 else np.abs(x)
    idx = np.nonzero(level > db(threshold_db))[0]
    if len(idx) == 0:
        return x
    k = secs(keep)
    return x[max(0, idx[0] - k):min(len(x), idx[-1] + k)]


def loop(x, crossfade=0.25):
    """Make a seamless loop: the end is blended into the start with an equal-power crossfade."""
    k = min(secs(crossfade), len(x) // 2)
    w = np.sin(np.linspace(0, np.pi / 2, k))
    w = w if x.ndim == 1 else w[:, None]
    body = x[k:len(x) - k].copy() if len(x) > 2 * k else x[:0]
    head = x[:k] * w + x[len(x) - k:] * w[::-1]
    return np.concatenate([head, body])


# ---------------------------------------------------------------- level
_K1 = ([1.53512485958697, -2.69169618940638, 1.19839281085285], [1.0, -1.69065929318241, 0.73248077421585])
_K2 = ([1.0, -2.0, 1.0], [1.0, -1.99004745483398, 0.99007225036621])


def lufs(x):
    """Perceived loudness (ITU BS.1770, the measure YouTube and broadcasters use). Rough for sounds under 0.4 s."""
    xs = stereo(x)
    k = signal.lfilter(*_K2, signal.lfilter(*_K1, xs, axis=0), axis=0)
    blk, hop = secs(0.4), secs(0.1)
    if len(k) < blk:
        return float(-0.691 + 10 * np.log10(np.sum(np.mean(k * k, axis=0)) + 1e-12))
    p = np.array([np.sum(np.mean(k[i:i + blk] ** 2, axis=0)) for i in range(0, len(k) - blk + 1, hop)])
    loud = -0.691 + 10 * np.log10(p + 1e-12)
    p = p[loud > -70.0]
    if len(p) == 0:
        return -70.0
    rel = -0.691 + 10 * np.log10(np.mean(p)) - 10.0
    p = p[-0.691 + 10 * np.log10(p) > rel]
    return float(-0.691 + 10 * np.log10(np.mean(p) + 1e-12))


def loudest(x, window=0.15):
    """Loudness of the loudest 150 ms (K-weighted, in LUFS): how loud a short sound hits.

    Integrated LUFS is built for programmes, not for a 50 ms click. This is the measure to level effects against
    each other with; it is the scale the wyzowl sfx-kit uses, so generated and fetched sounds sit together.
    """
    k = signal.lfilter(*_K2, signal.lfilter(*_K1, stereo(x), axis=0), axis=0)
    w = secs(window)
    k = pad_to(k, w)
    power = np.sum(k * k, axis=1)
    c = np.concatenate([[0.0], np.cumsum(power)])
    return float(-0.691 + 10 * np.log10(np.max(c[w:] - c[:-w]) / w + 1e-12))


def true_peak_db(x):
    """Peak level between the samples too (4x oversampled), which is what a player's converter really outputs."""
    return float(to_db(np.max(np.abs(signal.resample_poly(stereo(x), 4, 1, axis=0)))))


def normalize(x, peak_db=-1.0):
    """Set the loudest point to peak_db. -1 dB leaves room for lossy encoders (mp3, YouTube)."""
    p = np.max(np.abs(x))
    return x if p < 1e-9 else x * (db(peak_db) / p)


def cut_tail(x, threshold_db=-60.0):
    """Drop the end of a sound once it has fallen for good below threshold (relative to its peak)."""
    level = np.abs(x).max(axis=1) if x.ndim == 2 else np.abs(x)
    idx = np.nonzero(level > level.max() * db(threshold_db))[0]
    return x if len(idx) == 0 else x[:idx[-1] + 1]


def finish(x, peak_db=-1.0, fade_in=0.001, fade_out=0.008, dc=True, tail_db=-60.0):
    """The last step of every recipe: remove DC offset, drop the inaudible end of the tail, put both ends at zero, set the level.

    tail_db=None keeps the full length (for sounds that must end at an exact time).
    """
    y = stereo(x).astype(float)
    if dc:
        y = hp(y, 18.0, 2)
    if tail_db is not None:
        y = cut_tail(y, tail_db)
    return normalize(fade(y, fade_in, min(fade_out, len(y) / SR / 2)), peak_db)


# ---------------------------------------------------------------- files
def write_wav(path, x, bits=24):
    """Write a WAV. Refuses to overwrite: rendered media is never replaced, so pick a new name."""
    path = Path(path)
    y = np.clip(stereo(x) if x.ndim == 2 else x, -1.0, 1.0)
    ch = 1 if y.ndim == 1 else y.shape[1]
    if bits == 24:
        raw = (y * 8388607.0).round().astype("<i4").reshape(-1)
        data = np.frombuffer(raw.tobytes(), dtype=np.uint8).reshape(-1, 4)[:, :3].tobytes()
    elif bits == 16:
        data = (y * 32767.0).round().astype("<i2").tobytes()
    else:
        raise ValueError("bits must be 16 or 24")
    with open(path, "xb") as fh, wave.open(fh, "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(bits // 8)
        w.setframerate(SR)
        w.writeframes(data)
    return path


def read_audio(path):
    """Read any sound file as float at SR. WAV is read directly; other formats need ffmpeg on the machine."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"no such file: {path}")
    if path.suffix.lower() == ".wav":
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", wavfile.WavFileWarning)   # extra metadata chunks are harmless
                sr, data = wavfile.read(path)
        except ValueError:
            sr, data = None, None                             # an odd WAV flavour: let ffmpeg try
        if data is not None:
            if data.dtype == np.uint8:
                x = (data.astype(float) - 128.0) / 128.0
            elif data.dtype.kind == "i":
                x = data.astype(float) / float(2 ** (8 * data.dtype.itemsize - 1))
            else:
                x = data.astype(float)
            if sr != SR:
                g = gcd(SR, sr)
                x = signal.resample_poly(x, SR // g, sr // g, axis=0)
            return x[:, :2] if x.ndim == 2 and x.shape[1] > 2 else x
    if not shutil.which("ffmpeg"):
        raise RuntimeError(f"{path.name} is not a plain WAV and ffmpeg is not installed; convert it to WAV first")
    p = subprocess.run(["ffmpeg", "-v", "error", "-nostdin", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"],
                       capture_output=True, timeout=300)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg could not read {path.name}: {p.stderr.decode(errors='replace').strip()}")
    return np.frombuffer(p.stdout, dtype="<f4").reshape(-1, 2).astype(float)
