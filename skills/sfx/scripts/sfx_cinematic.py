"""Trailer sounds built in layers: the braam, and a whoosh with real pass-by motion.

A braam is low brass + a synth with movement + a sub, driven hard
and put in a long dark room; a pass-by whoosh is a pitch fall (doppler) AND a comb filter that sweeps, because the
sound reaches the ear twice, once direct and once off the ground.
"""
import numpy as np

import sfx_dsp as d
from sfx_dsp import SR, secs
from sfx_recipes import LEVELS, hz, part, recipe

LEVELS.update({"braam": -17.0, "pass_by": -19.0})


def _hump(n, peak, sharp):
    x = np.arange(n) / n
    return np.where(x < peak, np.sin(0.5 * np.pi * x / peak), np.sin(0.5 * np.pi * (1.0 - x) / (1.0 - peak))) ** (2.0 * sharp)


@recipe("cinematic", "A braam: the huge low brass blast of film trailers. Detuned saws with a rasping growl, a sub, and a long dark room.",
        "The biggest reveal of a trailer or intro; a title; a villain. Once, maybe twice: 'one well-placed hit is powerful; four is a "
        "parody'. It sits in the bass, so keep it off the same beat as another heavy hit and tune it to the music.",
        sync=("the cut or the frame the title lands", "The blast starts at the `hit` mark: the start of the file, or `lead` seconds in when it rises first."),
        root=(36.71, "pitch in Hz or a note, C1 to C2 (33-65 Hz); a semitone off the music is the usual clash"),
        seconds=(1.4, "how long the blast is held before it dies away (0.3 = a stab, 2 = long)"),
        growl=(0.6, "the brassy rasp at the start (0 smooth, 1 snarling)"),
        drive=(0.6, "distortion (0 clean, 1 torn)"),
        lead=(0.0, "seconds of rising swell before the blast (0 = none; 0.8-2 = it climbs in pitch and volume into the hit)"),
        tail=(4.0, "length of the room in seconds (2-6)"))
def braam(rng, root, seconds, growl, drive, lead, tail):
    f0 = hz(root)
    hold, fall = seconds, min(2.0, 0.7 + seconds)                # a stab dies away faster than a held blast
    n0, n = secs(lead), secs(lead + hold + fall * 2.4)          # run until the dry sound is 60 dB down; stopping sooner was heard as a cut-off
    t = (np.arange(n) - n0) / SR                                # 0 at the hit
    after = np.maximum(t, 0.0)
    amp = np.where(t < 0, (np.arange(n) / max(n0, 1)) ** 2.5 * 0.5, np.minimum(1.0, 0.5 + after / 0.025) * np.where(after < hold, 1.0, np.exp(-(after - hold) / (fall / 3.0))))
    # pitch: a climb into the hit when there is a lead; a 50 ms wobble at the onset; a slow sag through the note
    bend = np.where(t < 0, -7.0 * np.clip(-t / max(lead, 1e-6), 0, 1) ** 1.5, -0.7 * np.clip(after / (hold + fall * 2.4), 0, 1))
    voices = np.zeros((n, 2))
    for k in range(18):
        ratio = 1.0 if k % 5 < 3 else 2.0                       # about 60% on the root, 40% an octave up
        cents = rng.uniform(5, 25) * rng.choice([-1, 1]) + rng.uniform(-60, 60) * np.exp(-after / 0.02) * (t >= 0)
        v = d.saw(f0 * ratio * 2.0 ** (bend / 12.0 + cents / 1200.0), phase=rng.random())
        voices += d.pan(v, rng.uniform(-0.8, 0.8)) / (1.0 + 0.6 * (ratio > 1))
    voices /= 6.0
    # brass: the filter opens more slowly than the volume, so the top "speaks" late; the growl is a fast shake of the filter
    opening = np.where(t < 0, 0.25, np.minimum(1.0, 0.15 + after / 0.15)) * np.where(after < hold, 1.0, np.exp(-(after - hold) / (fall / 2.0)))
    shake = 1.0 + growl * 0.6 * (0.2 + 0.8 * np.exp(-after / 0.35)) * (2.0 * np.abs(2.0 * ((after * 75.0) % 1.0) - 1.0) - 1.0)
    cutoff = np.clip((3.0 * f0 + (1800.0 - 3.0 * f0) * opening) * shake, 60.0, 8000.0)
    brass = np.stack([d.sweep(voices[:, c], "lp", cutoff, q=0.9) for c in (0, 1)], axis=1) * amp[:, None]
    edge = d.bp(brass, 150.0, 2500.0, 1)
    edge = d.lp(np.tanh(d.hp(edge, 120.0, 1) * (4.0 + 26.0 * drive * (0.6 + 0.4 * np.clip(after / max(hold, 0.1), 0, 1)))[:, None]), 4200.0, 2)
    fs = f0 / 2.0 if f0 >= 55.0 else f0
    sub = (d.sine(fs * 2.0 ** (bend / 12.0)) + 0.25 * d.triangle(fs * 2.0 ** (bend / 12.0))) * amp * np.minimum(1.0, (np.arange(n) / SR) / 0.02)
    bloom = np.minimum(1.0, after / 0.3) * (t >= 0) * amp      # a ship-horn layer that swells up behind the brass
    organ = sum(d.sine(f0 * h * 2.0 ** ((bend * 100 + c) / 1200.0)) * d.db(g) for h, g in ((1, 0), (2, -4), (3, -8), (4, -10), (6, -14), (8, -18)) for c in (-7, 7)) * bloom * 0.5
    breath = d.bp(d.noise(n, rng, "pink"), 300.0, 2000.0, 1) * amp
    parts = [(brass, 0, 0), (edge, 0, -8 + 4 * drive), (sub, 0, -4), (organ, 0, -9), (breath, 0, -20)]
    if n0 < n:
        knock, _ = part("impact", rng, weight=0.7, bright=0.1, punch=0.1, tail=0.8, root=f0, boom=1.0)   # so it lands hard
        parts.append((knock, lead, -8))
    dry = np.tanh(d.layer(parts) * 1.2)
    room = d.reverb(d.lp(dry, 2500.0, 2), t60=tail, mix=1.0, bright=0.2, pre_delay=0.03, seed=int(rng.integers(1 << 30)))
    out = d.layer([(dry, 0, 0), (d.hp(room, 90.0, 2), 0, -10)])                    # the sub stays dry and out of the room
    return d.finish(d.trim(out, -62, keep=0.05), fade_in=0.004, fade_out=1.0), {"hit": float(lead), "start": 0.0}


@recipe("cinematic", "Something passing close and fast: noise and a low growl whose pitch falls as it goes by, with a sweeping hollow tone.",
        "A camera fly-through, an object crossing the frame, a fast pan, a vehicle or projectile, a big transition. Heavier and more "
        "real than `whoosh`; use `whoosh` for small graphic moves.",
        sync=("the moment it is closest", "The `peak` mark is the closest point. Put it on the frame the object crosses the middle of the "
              "screen, or on the cut; start the file 10-20 ms before the move starts."),
        seconds=(2.2, "length (0.45 a quick swing, 2.2 a slow cinematic sweep). Around 1 s at middling speed was rejected: it sounds as if it is inside a tube"),
        peak=(0.55, "where the closest point falls (0-1); later = a long approach"),
        speed=(0.3, "how fast it passes (0-1): a bigger pitch fall and a sharper peak; 0.9 with a short length for a swing"),
        weight=(0.9, "low-end weight (0 = a thin swing, 1 = something heavy)"),
        travel=(1.0, "1 = left to right, -1 = right to left, 0 = centred"))
def pass_by(rng, seconds, peak, speed, weight, travel):
    n = secs(seconds)
    tp = peak * seconds
    t = np.arange(n) / SR
    hump = _hump(n, peak, 1.0 + 1.5 * speed)
    # the source: mid noise that sweeps up to the peak and back, a thin band of air only at the peak, and a tonal growl
    centre = 300.0 * (2200.0 / 300.0) ** hump
    pink = d.noise(n, rng, "pink")
    mid = d.sweep(pink, "bp", centre, q=2.0) + 0.63 * d.sweep(pink, "bp", centre / 2.83, q=1.5)
    air = d.lp(d.hp(d.noise(n, rng, "pink"), 3500.0, 2), 10000.0, 1) * hump ** 2
    g0 = rng.uniform(60.0, 110.0)
    growl = np.tanh(sum(d.saw(g0 * 2.0 ** (c / 1200.0), n, phase=rng.random()) for c in (-18, -6, 7, 19)) * 0.8)
    src = (mid * 1.0 + air * 0.25 + d.hp(d.lp(growl, 1500.0, 1), 180.0, 2) * 0.3) * hump
    # doppler: the sound left the source a moment ago; that moment grows as it moves away, so the pitch falls
    v, dist, c = 25.0 + 70.0 * speed, 4.0, 343.0
    r = np.sqrt(dist ** 2 + (v * (t - tp)) ** 2)
    moved = np.interp(t - (r - dist) / c, t, src, left=0.0, right=0.0)
    # the hollow sweep: the same sound again off the ground, 4 ms late far away and 9 ms late overhead (measured on real pass-bys)
    late = (4.0 + 5.0 * (dist / r)) / 1000.0
    moved = moved + 0.65 * np.interp(t - late, t, moved, left=0.0)
    near = dist / r                                             # distance takes the highs
    moved = d.lp(moved, 1500.0, 1) * (1.0 - near) + d.lp(moved, 12000.0, 1) * near
    low = (d.lp(d.hp(d.noise(n, rng, "brown"), 40.0, 2), 220.0, 2) * 3.0 + d.sine(55.0, n) * 0.5) * np.roll(_hump(n, peak, 0.7), secs(0.04))
    pos = travel * np.arctan(v * (t - tp) / dist) / (np.pi / 2.0)
    rms = lambda x: float(np.sqrt(np.mean(x ** 2))) + 1e-9  # noqa: E731
    out = d.pan(moved / rms(moved), np.clip(pos, -1, 1)) + d.stereo(low / rms(low)) * d.db(-24.0 + 12.0 * weight)
    out = np.tanh(out / (np.max(np.abs(out)) + 1e-9) * 2.0)
    wet = d.reverb(out, t60=0.7, mix=0.18, bright=0.4, seed=int(rng.integers(1 << 30)))
    return d.finish(wet[:n + secs(0.4)], fade_in=0.01, fade_out=0.15, tail_db=-55.0), {"peak": float(tp), "start": 0.0}
