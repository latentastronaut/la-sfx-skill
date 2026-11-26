"""Electrical arcing, pouring, and a silent vinyl record.

Arcing: nothing oscillates; the arc dies at each zero crossing of the
mains and re-strikes, so the buzz is a click and a burst of hiss every half-cycle, uneven, with misfires. Pouring:
thousands of tiny bubbles a second, each its own size, heard through the air column of the vessel, whose note climbs
as it fills. Vinyl: hiss, rumble, dust ticks, pops, and scratches that come round once per turn.
"""
import numpy as np
from scipy import signal  # noqa: F401

import sfx_dsp as d
from sfx_ambience import FADE, bpq, close, put, unit, wander  # noqa: F401
from sfx_dsp import SR, secs
from sfx_recipes import LEVELS, note, recipe

LEVELS.update({"arc": -22.0, "pour": -24.0, "vinyl": -38.0})


def power_law(rng, k, db_range=30.0, gamma=-1.5):
    """k event amplitudes: many tiny, a few large (energy P(E) ~ E^gamma over `db_range` dB)."""
    lo, a = 10.0 ** (-db_range / 10.0), gamma + 1.0
    e = (lo ** a + rng.random(k) * (1.0 - lo ** a)) ** (1.0 / a)
    return np.sqrt(e)


def radii(rng, k, r_lo, r_hi, gamma):
    """k bubble radii in metres from a power law: small ones far more common."""
    a = 1.0 - gamma
    return (r_lo ** a + rng.random(k) * (r_hi ** a - r_lo ** a)) ** (1.0 / a)


def bubble_cloud(rng, n, at, r, amp, pan, rise_share=0.1):
    """Add one damped, slightly inharmonic ring per bubble (van den Doel) into a stereo track. All arrays are per bubble."""
    out = np.zeros((n, 2))
    f0 = 3.0 / r * rng.uniform(0.95, 1.05, len(r))
    damp = (0.13 / r + 0.0072 * r ** -1.5) * rng.uniform(0.8, 1.5, len(r))
    xi = np.where(rng.random(len(r)) < rise_share, rng.uniform(0.1, 0.5, len(r)), 0.0)
    length = np.minimum(np.ceil(6.0 / damp * SR), SR * 0.4).astype(int)
    th = (pan + 1.0) * np.pi / 4.0
    for L in (64, 128, 256, 512, 1024, 2048, 4096, 8192, 19200):
        sel = np.nonzero((length <= L) & (length > (L // 2 if L > 64 else 0)))[0]
        if len(sel) == 0:
            continue
        t = np.arange(L)[None, :] / SR
        f, dm, x = f0[sel, None], damp[sel, None], xi[sel, None]
        ph = 2 * np.pi * f * (t + 0.5 * x * dm * t * t)
        onset = np.clip(t * f * 2.0, 0, 1)                      # the ring builds over its first half cycle
        ratio = rng.uniform(1.4, 2.2, (len(sel), 1))            # a real bubble is not a sphere: one extra, faster-dying mode
        ring = (np.sin(ph) * np.exp(-dm * t) + 0.2 * np.sin(ph * ratio) * np.exp(-2 * dm * t)) * (0.5 - 0.5 * np.cos(np.pi * onset))
        ring *= amp[sel, None]
        idx = np.minimum(at[sel, None] + np.arange(L)[None, :], n - 1)
        np.add.at(out[:, 0], idx, ring * np.cos(th[sel, None]))
        np.add.at(out[:, 1], idx, ring * np.sin(th[sel, None]))
    return out


def bubbles(rng, n, rate, r_lo, r_hi, gamma, width=0.8, rise_share=0.1):
    at = np.nonzero(rng.random(n) < np.asarray(rate) / SR)[0]
    if len(at) == 0:
        return np.zeros((n, 2))
    r = radii(rng, len(at), r_lo, r_hi, gamma)
    return bubble_cloud(rng, n, at, r, r ** 1.5 * rng.random(len(at)) ** 10, rng.uniform(-width, width, len(at)), rise_share)


@recipe("water", "Liquid pouring into a glass: a bright rush of countless tiny bubbles, heard through the air column whose note climbs as it fills.",
        "A drink being poured, a how-to or cooking video, 'filling up' as a metaphor. The `full` mark is the end of the pour.",
        sync=("the pour starting", "The pour starts at the start of the file and stops at the `full` mark. Set `seconds` to the length of the pour on screen."),
        seconds=(5.0, "length of the pour, exactly"),
        size=(0.4, "vessel size (0 = a small glass, 1 = a tall jug): the pitch of the hollow note"))
def pour(rng, seconds, size):
    n = secs(seconds + 0.9)
    t = np.arange(n) / SR
    flow = np.clip(t / 0.15, 0, 1) * np.clip((seconds - t) / 0.3, 0, 1) * wander(n, rng, 0.85, 1.15, 0.3, 1.5)
    tex = bubbles(rng, n, 1800.0 * flow, 0.00025, 0.003, 2.5, 0.25)
    glug = bubbles(rng, n, 4.0 * flow, 0.003, 0.008, 1.2, 0.25, rise_share=1.0)
    jet = d.stereo(bpq(rng.standard_normal(n), 4000.0, 0.5) * flow * np.clip(1.0 + 0.5 * d.lp(rng.standard_normal(n), 40, 1) * 60, 0.3, 1.8))
    src = unit(tex) + unit(glug) * d.db(-10) + unit(jet) * d.db(-12)
    fill = np.clip(t / seconds, 0, 1) ** 1.6                                 # the note rises fastest at the end
    L, R = 0.11 + 0.1 * size, 0.03 + 0.012 * size
    f1 = 343.0 / (4.0 * (L * (1.0 - 0.9 * fill) + 0.62 * R))
    column = np.stack([sum(d.sweep(src[:, c], "bp", np.clip(f1 * k, 100, 16000), q=10.0) * g for k, g in ((1, 1.0), (3, 0.5), (5, 0.32), (7, 0.2))) for c in (0, 1)], axis=1)
    mix = unit(column) * 0.6 + unit(src) * 0.4
    wall = np.zeros(n)                                                       # the glass itself rings for the first second, its note falling as water loads it
    for f in rng.uniform(2000.0, 7000.0, 3):
        fg = f * (1.0 - 0.5 * np.clip(t / 1.0, 0, 1))
        wall += d.sweep(d.mono(tex), "bp", fg, q=25.0) * np.clip(1.0 - t / 1.0, 0, 1)
    mix = mix + d.stereo(unit(wall)) * d.db(-18)
    for i in range(int(rng.integers(3, 7))):                                 # the last drips after the pour stops
        td = seconds + 0.1 + i * rng.uniform(0.08, 0.2)
        mix += bubble_cloud(rng, n, np.array([min(secs(td), n - 1)]), np.array([rng.uniform(0.0008, 0.002)]), np.array([0.15]), np.array([0.0])) / 1e-3 * 1e-3
    out = d.reverb(mix, t60=0.3, mix=0.1, bright=0.6, seed=int(rng.integers(1 << 30)))
    return d.finish(out, fade_in=0.002, fade_out=0.08, tail_db=-55.0), {"full": float(seconds), "start": 0.0}


@recipe("scifi", "Electrical arcing: a harsh buzz made of a click and a burst of hiss every half-cycle of the mains, uneven, with misfires and fits of sputter.",
        "A short circuit, a broken neon sign, a sparking cable, a mad-science machine, a power surge.",
        seconds=(2.0, "length"),
        amount=(0.5, "0 = a steady arc, 1 = a sputtering fault that keeps cutting out"),
        mains=(60.0, "mains frequency: 60 (Americas) or 50 (Europe); sets the pitch of the buzz"))
def arc(rng, seconds, amount, mains):
    n = secs(seconds)
    y, win = np.zeros(n), np.zeros(n)
    half = 1.0 / (2.0 * mains)
    p_strike = wander(n, rng, 0.85 - 0.45 * amount, 0.98 - 0.2 * amount, 0.15, 0.5)
    missed = 0
    for k in range(int(seconds / half)):
        t0 = k * half
        if rng.random() > p_strike[min(secs(t0), n - 1)]:
            missed += 1
            continue
        delay = rng.uniform(0.001, 0.0025) + rng.uniform(-0.0003, 0.0003)
        a = (1.0 if k % 2 == 0 else rng.uniform(0.6, 0.85)) * rng.lognormal(0, 0.3) * (1.0 + 0.5 * min(missed, 2))
        missed = 0
        s, e = secs(t0 + delay), secs(t0 + half - rng.uniform(0.0003, 0.0008))
        if e <= s + 8 or e >= n:
            continue
        m = e - s
        w = np.sin(np.pi * (np.arange(m) / SR + delay) * 2 * mains) ** 0.7        # the arc conducts until just before the next zero crossing
        win[s:e] += w * a
        ck = secs(rng.uniform(0.0003, 0.0015))
        y[s:s + ck] += rng.standard_normal(ck) * np.exp(-np.arange(ck) / (ck / 4)) * a * 3.0     # the re-strike click
    hiss = d.hp(rng.standard_normal(n), 2500.0 * (1.0 + 0.3 * wander(n, rng, -1, 1, 0.1, 0.4)).mean(), 2)
    hiss = (hiss + 0.8 * d.hp(hiss, 8000, 1)) * win * np.clip(1.0 + 0.4 * unit(d.lp(rng.standard_normal(n), 500, 1)), 0.2, 2.0)
    body = d.bp(np.diff(win, prepend=0.0), 80.0, 1200.0, 1)                         # the buzz itself: the gating, not an oscillator
    fits = (wander(n, rng, 0.0, 1.0, 0.05, 0.4) > 0.55).astype(float)
    at = np.nonzero(rng.random(n) < (100.0 + 500.0 * amount) * fits * (win > 0) / SR)[0]
    sput = np.zeros(n)
    if len(at):
        sput[at] = power_law(rng, len(at), 30.0) * rng.choice([-1.0, 1.0], len(at))
        sput = d.hp(np.convolve(sput, np.hanning(max(secs(0.0003), 3)), mode="same"), 3000, 2)
    click = d.hp(y, 1500, 2)
    click = click + 0.5 * bpq(click, 4000.0, 2.0) + 0.4 * bpq(click, 8000.0, 2.0)
    mix = unit(click) + unit(hiss) * d.db(-8) + unit(body) * d.db(-10) + (unit(sput) * d.db(-14) if len(at) else 0.0)
    out = d.reverb(d.widen(mix, rng, 0.3), t60=0.4, mix=0.15, bright=0.7, pre_delay=0.005, seed=int(rng.integers(1 << 30)))[:n]
    return d.finish(out, fade_in=0.001, fade_out=0.02, tail_db=None)


@recipe("bed", "A silent vinyl record playing: faint hiss and rumble, fine crackle, the odd pop, and scratches that come round once a turn.",
        "Nostalgia, a flashback, an old-film or lo-fi feel under a scene or under music. Very quiet by design. Loops without a seam.",
        sync=("the start of the scene", "Not frame-critical. Fade it in and out in the edit."),
        seconds=(10.8, "length of the loop; a whole number of turns (1.8 s each at 33 rpm) keeps the repeating scratches in step: 9, 10.8, 14.4"),
        wear=(0.15, "0 = a clean record, 0.4 = some dust and a scratch. Above about 0.5 was rejected by ear as harsh"),
        rpm=(33.33, "33.33 or 45"))
def vinyl(rng, seconds, wear, rpm):
    n = secs(seconds + FADE)
    t = np.arange(n) / SR
    turn = 60.0 / rpm
    y = np.zeros((n, 2))

    def tick(size):
        """One click as the stylus hears it: a dull, very short knock; a big one has a soft thump under it."""
        m = secs(0.004 + 0.004 * size)
        tt = np.arange(m) / SR
        x = np.zeros(m)
        x[:2] = rng.choice([-1.0, 1.0])
        x = d.lp(x, rng.uniform(3500, 9000) * (1.0 - 0.5 * size), 2) * 6.0
        return x + size * 0.5 * np.sin(2 * np.pi * rng.uniform(120, 300) * tt) * np.exp(-tt / 0.0015)

    def stereo_put(x, at, gain):
        lr = rng.uniform(0.3, 1.0, 2) * rng.choice([-1.0, 1.0], 2)                  # each groove wall hears a different click
        a = min(at, n - 1)
        note(a, (abs(lr[1]) - abs(lr[0])) / (abs(lr[1]) + abs(lr[0])), gain * float(np.max(np.abs(x))))
        x = x[:n - a]
        y[a:a + len(x), 0] += x * gain * lr[0]
        y[a:a + len(x), 1] += x * gain * lr[1]

    for at in np.nonzero(rng.random(n) < (6.0 + 40.0 * wear) / SR)[0]:               # fine dust: many, tiny
        stereo_put(tick(0.0), int(at), 0.05 * rng.lognormal(0, 0.8))
    for at in np.nonzero(rng.random(n) < (0.4 + 2.0 * wear) / SR)[0]:                # pops: few, larger, duller
        stereo_put(tick(rng.uniform(0.4, 1.0)), int(at), 0.5 * rng.lognormal(0, 0.5))
    for _ in range(int(1 + 4 * wear)):                                               # a scratch: the same click once every turn, a little different each time
        phase, g, size = rng.uniform(0, turn), rng.uniform(0.2, 0.7), rng.uniform(0.2, 0.8)
        first, turns = rng.uniform(0, seconds), int(rng.integers(3, 12))
        for k in range(turns):
            when = first - (first % turn) + phase + k * turn + rng.uniform(-0.002, 0.002)
            if 0 <= when < seconds + FADE:
                stereo_put(tick(size), secs(when), g * rng.uniform(0.6, 1.0))
    hiss = d.lp(d.hp(rng.standard_normal((n, 2)), 400, 1), 9000, 1) * 0.012 * (0.6 + 0.8 * wear)
    wow = 1.0 + 0.3 * np.sin(2 * np.pi * t / turn + rng.uniform(0, 6))               # the rumble breathes once a turn
    rumble = d.lp(rng.standard_normal(n), 55, 2) * wow
    y = y + hiss + d.stereo(unit(rumble) * 0.02)
    return close(y, seconds)
