"""More recipes: signals (alarms, phone tones, countdown beeps), broken electronics (static, glitch), sci-fi,
cartoon sounds, pulses with exact spacing (heartbeat, clock) and looping beds (rain, fire, wind, room tone, hum).

Same contract as sfx_recipes: (rng, **params) -> signal, or (signal, marks) when there is more than one moment to sync.
"""
import numpy as np

import sfx_dsp as d
from sfx_dsp import SR, secs
from sfx_recipes import LEVELS, START, part, recipe

LEVELS.update({"alarm": -22.0, "phone": -24.0, "static": -26.0, "glitch": -22.0, "scifi": -22.0, "cartoon": -22.0,
               "heartbeat": -22.0, "clock": -27.0, "bed": -32.0, "countdown": -22.0})


def _gate(n, on, off, fade=0.004, start=0.0):
    """An on/off pattern as an envelope: `on` seconds of sound, `off` seconds of silence, with soft edges."""
    t = (np.arange(n) / SR - start) % (on + off)
    g = (t < on).astype(float)
    k = max(3, secs(fade))
    return np.convolve(g, np.hanning(k) / np.hanning(k).sum(), mode="same")


def _choice(kind, table, name):
    if kind not in table:
        raise ValueError(f"{name}: kind must be one of {', '.join(table)}")
    return table[kind]


# ================================================================ signals
@recipe("signal", "Alarms and sirens: beeps, a wailing siren, a two-tone siren or a harsh klaxon.",
        "A warning on screen, a timer running out, 'breaking news', a joke about panic. Alarms are built to be impossible to ignore, "
        "so keep them short and low under speech. beep = alarm clock or timer, siren = emergency wail, two_tone = European siren, "
        "klaxon = submarine or factory horn.",
        kind=("beep", "beep, siren, two_tone or klaxon"),
        seconds=(1.6, "length"),
        pitch=(1000.0, "main pitch in Hz or a note (beep 800-2500, siren 500-900, klaxon 180-300)"),
        rate=(4.0, "beeps or cycles per second (beep 2-8, siren 0.3-1, two_tone 1-2, klaxon 1-2)"))
def alarm(rng, kind, seconds, pitch, rate):
    n = secs(seconds)
    t = np.arange(n) / SR
    if kind == "beep":
        y = (d.sine(pitch, n) + 0.25 * d.sine(pitch * 3.0, n)) * _gate(n, 0.5 / rate, 0.5 / rate)
    elif kind == "siren":
        f = pitch * 2.0 ** (0.45 * np.sin(2 * np.pi * rate * t - np.pi / 2))
        y = d.lp(d.saw(f) * 0.6 + d.sine(f), 3500, 2)
    elif kind == "two_tone":
        f = np.where((t * rate) % 1.0 < 0.5, pitch, pitch * 0.75)
        y = d.lp(d.square(f, width=0.4), 3000, 2)
    elif kind == "klaxon":
        y = d.lp(d.saw(pitch, n) * (0.6 + 0.4 * d.square(pitch * 0.5, n)), 2800, 2) * _gate(n, 0.7 / rate, 0.3 / rate, 0.01)
        y = d.saturate(y, 2.5)
    else:
        raise ValueError("alarm: kind must be beep, siren, two_tone or klaxon")
    return d.finish(d.reverb(y, t60=0.3, mix=0.06, bright=0.5, seed=int(rng.integers(1 << 30)))[:n], fade_in=0.004, fade_out=0.02, tail_db=None)


_DTMF = {"1": (697, 1209), "2": (697, 1336), "3": (697, 1477), "4": (770, 1209), "5": (770, 1336), "6": (770, 1477),
         "7": (852, 1209), "8": (852, 1336), "9": (852, 1477), "*": (941, 1209), "0": (941, 1336), "#": (941, 1477)}


@recipe("signal", "Telephone tones at their real frequencies: dial tone, ringing, busy, and keypad digits.",
        "A phone call in a story or sketch, 'calling support', dialling a number on screen. kind=digits plays `digits` as keypad tones, "
        "one mark per digit, so each tone can land on its button press.",
        kind=("ring", "dial (steady tone), ring (the tone the caller hears), busy, or digits"),
        seconds=(4.0, "length for dial, ring and busy"),
        digits=("5550123", "the number to dial when kind=digits"),
        gap=(0.16, "seconds from one digit to the next when kind=digits"),
        line=(True, "sound as if heard through a phone (narrow band); false = clean tones"))
def phone(rng, kind, seconds, digits, gap, line):
    marks = {"start": 0.0}
    if kind == "digits":
        keys = [c for c in str(digits) if c in _DTMF]
        if not keys:
            raise ValueError("phone: digits needs at least one of 0-9, * or #")
        on = min(0.09, gap * 0.6)
        m = secs(on)
        tone = lambda c: d.fade((d.sine(_DTMF[c][0], m) + d.sine(_DTMF[c][1], m)) * 0.5, 0.003, 0.003)  # noqa: E731
        y = d.mono(d.layer([(tone(c), i * gap, 0) for i, c in enumerate(keys)]))
        marks = {f"digit{i + 1}": i * gap for i in range(len(keys))}
    else:
        a, b, on, off = _choice(kind, {"dial": (350, 440, 1e9, 0.0), "ring": (440, 480, 2.0, 4.0), "busy": (480, 620, 0.5, 0.5)}, "phone")
        n = secs(seconds)
        y = (d.sine(a, n) + d.sine(b, n)) * 0.5 * (_gate(n, on, off, 0.006) if off else 1.0)
    if line:
        y = d.saturate(d.bp(y, 320, 3300, 2), 1.5)
    return d.finish(y, fade_in=0.004, fade_out=0.01, tail_db=None), marks


@recipe("signal", "Countdown beeps on exact times, ending on a longer, higher 'go' beep.",
        "'3, 2, 1, go', a timer's last seconds, a race start, a quiz clock. Each beep has its own mark; put the `go` mark on the "
        "frame the thing starts.",
        sync=("the frame the countdown ends", "The `go` mark is the last, long beep. The earlier beeps are `gap` seconds apart before it: "
              "start the file at (go time) minus the `go` mark and every number on screen gets its beep."),
        count=(3, "number of short beeps before the go beep"),
        gap=(1.0, "seconds from one beep to the next, exactly (1.0 for a real countdown, 0.5 for a quick one)"),
        pitch=(660.0, "pitch of the short beeps in Hz or a note; the go beep is an octave up"),
        go=(0.6, "length of the go beep in seconds (0 = no go beep)"))
def countdown(rng, count, gap, pitch, go):
    count = int(count)
    if count < 1:
        raise ValueError("countdown: count must be at least 1")
    def beep(f, length):
        m = secs(length)
        return d.fade((d.sine(f, m) + 0.2 * d.sine(f * 2.0, m)), 0.004, min(0.03, length / 3))
    parts = [(beep(pitch, 0.12), i * gap, 0) for i in range(count)]
    marks = {f"beep{i + 1}": i * gap for i in range(count)}
    if go > 0:
        parts.append((beep(pitch * 2.0, go), count * gap, 0))
        marks = {"go": count * gap, **marks}
    y = d.reverb(d.layer(parts), t60=0.25, mix=0.06, bright=0.6, seed=int(rng.integers(1 << 30)))
    return d.finish(y, fade_out=0.03, tail_db=-50.0), marks




# ================================================================ broken electronics
@recipe("texture", "Radio or TV static: hiss with crackle and dropouts.",
        "A lost signal, an old TV, switching channel, a flashback, 'transmission' text. "
        "Short bursts (0.2-0.5 s) work as a transition between two scenes.",
        seconds=(1.5, "length"),
        crackle=(0.5, "amount of pops and crackle (0 smooth hiss, 1 badly broken)"),
        dark=(0.3, "0 = bright TV hiss, 1 = muffled AM radio"))
def static(rng, seconds, crackle, dark):
    n = secs(seconds)
    hiss = d.bp(d.noise(n, rng, "white"), 400, 9000 - 6500 * dark, 2)
    wobble = 1.0 + 0.5 * d.lp(rng.standard_normal(n), 6, 2) * 40.0
    y = hiss * np.clip(wobble, 0.3, 1.8)
    if crackle > 0:
        hits = (rng.random(n) < crackle * 40.0 / SR) * rng.uniform(0.3, 1.0, n) * rng.choice([-1.0, 1.0], n)
        y = y + d.bp(np.convolve(hits, np.exp(-np.arange(200) / 25.0), mode="same"), 600, 7000, 2) * 6.0
        drop = d.lp((d.lp(rng.standard_normal(n), 3, 2) * 60.0 > 1.4 - crackle).astype(float), 200, 1)
        y = y * (1.0 - 0.85 * np.clip(drop, 0, 1))                       # the signal cutting out
    return d.finish(d.widen(y, rng, 0.3), fade_in=0.003, fade_out=0.01, tail_db=None)


@recipe("texture", "A digital glitch: a stutter of chopped tones, noise and dropouts, crushed to low resolution.",
        "A glitch cut between scenes, corrupted data, an error on a screen, tech and AI topics. Keep it very short "
        "(0.1-0.4 s); longer than half a second it stops being a glitch and becomes noise. For a cut, see glitch_cut.",
        seconds=(0.3, "length, exactly"),
        density=(0.5, "how finely it is chopped (0 = a few long slices, 1 = a fast stutter)"),
        pitch=(440.0, "centre pitch of the tonal slices in Hz or a note"),
        crush=(0.6, "bit-crush amount (0 clean, 1 very lo-fi)"),
        holes=(0.25, "share of slices that are silent (0-0.6); silence is what makes it read as a dropout"))
def glitch(rng, seconds, density, pitch, crush, holes):
    n = secs(seconds)
    y, i, last = np.zeros(n), 0, None
    while i < n:
        m = min(secs(rng.uniform(0.012, 0.09) * (1.4 - density)), n - i)
        r = rng.random()
        if r < holes:
            s = np.zeros(m)
        elif last is not None and r < holes + 0.25:                       # a stutter: the last slice again
            s = np.resize(last, m)
        elif r < holes + 0.55:
            s = d.square(pitch * 2.0 ** (rng.integers(-12, 19) / 12.0), m, width=rng.uniform(0.2, 0.5)) * 0.7
        elif r < holes + 0.75:
            s = d.sine(d.glide(m, pitch * rng.uniform(2, 8), pitch * rng.uniform(0.25, 1)))
        else:
            s = rng.uniform(-1, 1, m) * 0.8
        if s.any():
            last = s
        y[i:i + m] = d.fade(s, 0.0008, 0.0008)
        i += m
    hold = max(1, int(1 + 10 * crush))                                    # sample-and-hold: the aliasing of cheap digital audio
    idx = np.arange(n)
    y = y[idx - idx % hold]
    levels = 2.0 ** (8 - 5 * crush)
    y = d.lp(np.round(y * levels) / levels, 15000 - 7000 * crush, 2)
    return d.finish(d.pan(y, np.sign(d.lp(rng.standard_normal(n), 15, 1)) * 0.5), fade_in=0.001, fade_out=0.002, tail_db=None)


# ================================================================ sci-fi and cartoon
@recipe("scifi", "Science-fiction machines: a zap, a teleport shimmer, a scanner sweep, power up and power down.",
        "Tech and AI topics, a futuristic interface, something switching on or off, a transformation. "
        "zap = shot or spark, teleport = something appears or vanishes in a shimmer, scan = analysing, "
        "power_up and power_down = a machine starting or dying.",
        kind=("teleport", "zap, teleport, scan, power_up or power_down"),
        seconds=(1.2, "length (zap 0.15-0.4, teleport 0.6-2, scan 0.8-3, power 0.6-3)"),
        pitch=(220.0, "base pitch in Hz or a note"),
        metal=(0.5, "how metallic and bright (0 soft, 1 harsh)"))
def scifi(rng, kind, seconds, pitch, metal):
    n = secs(seconds)
    x = np.linspace(0.0, 1.0, n)
    marks = {"start": 0.0}
    if kind == "zap":
        f = d.glide(n, pitch * 8.0, pitch * 0.5, 0.45)
        y = d.fm(f, 2.41, (2.0 + 8.0 * metal) * (1.0 - x) ** 2) * d.perc(n, 0.001, seconds * 1.2)
        y = y + d.hp(d.noise(n, rng, "white"), 3000) * d.perc(n, 0.0005, 0.03) * 0.4
    elif kind == "teleport":
        f = d.glide(n, pitch, pitch * 6.0, 1.6)
        ph = np.cumsum(d.glide(n, 6.0, 40.0, 1.3)) / SR
        shimmer = sum(d.fm(f * r, 3.01, 1.0 + 4.0 * metal * x) for r in (1.0, 1.498, 2.003)) / 3.0
        y = shimmer * (0.55 + 0.45 * np.cos(2 * np.pi * ph)) * d.bell_curve(n, 0.8, 0.35, skew=0.25)
        y = y + d.sweep(d.noise(n, rng, "pink"), "bp", d.glide(n, 800, 9000, 1.5), q=3.0) * x ** 2 * 0.5 * d.bell_curve(n, 0.85, 0.3, skew=0.2)
        marks = {"peak": 0.8 * seconds, "start": 0.0}
    elif kind == "scan":
        sweeps = max(1, int(round(seconds / 0.45)))
        ph = (x * sweeps) % 1.0
        y = d.sine(pitch * 2.0 * 4.0 ** ph) * (1.0 - ph) ** 0.6 * 0.8 + d.fm(pitch * 4.0, 1.5, metal * 3.0, n) * 0.12
        y = d.fade(y, 0.005, 0.05)
    elif kind in ("power_up", "power_down"):
        c = 3.0
        up = (np.exp(c * x) - 1.0) / (np.exp(c) - 1.0)                      # slow to start, then it races: a motor spinning up
        prog = up if kind == "power_up" else (1.0 - x) ** 2.2
        f = pitch * 0.25 * 16.0 ** prog
        tone = d.sweep(d.saw(f) * 0.6 + d.square(f * 0.5, width=0.3) * 0.4, "lp", np.clip(f * (3.0 + 6.0 * metal), 80, 16000), q=1.6)
        whine = d.sine(f * 4.0) * 0.15 * prog
        env = np.clip(prog * 4.0, 0, 1) ** 0.5 if kind == "power_down" else np.clip(x * 12.0, 0, 1)
        y = (tone + whine) * (0.35 + 0.65 * prog) * env
        if kind == "power_up":
            marks = {"on": seconds, "start": 0.0}
    else:
        raise ValueError("scifi: kind must be zap, teleport, scan, power_up or power_down")
    wet = d.reverb(d.widen(y, rng, 0.4), t60=0.5, mix=0.12, bright=0.7, seed=int(rng.integers(1 << 30)))
    exact = kind == "power_up"
    return d.finish(wet[:n] if exact else wet, fade_in=0.003, fade_out=0.006 if exact else 0.08, tail_db=None if exact else -50.0), marks


@recipe("cartoon", "Cartoon sounds: a springy boing, a falling slide whistle and a hollow bonk.",
        "Jokes, playful explainers, kids' content, a mistake played for laughs. Comedy sounds need comic timing: put the bonk "
        "exactly on the contact frame and the slide across the whole fall.",
        kind=("boing", "boing, slide_down or bonk"),
        pitch=(300.0, "base pitch in Hz or a note"),
        seconds=(0.7, "length (boing 0.4-1, slide = the length of the fall on screen, bonk ignores it)"))
def cartoon(rng, kind, pitch, seconds):
    n = secs(seconds)
    t = np.arange(n) / SR
    marks = {"start": 0.0}
    if kind == "boing":
        wob = 0.45 * np.exp(-t / (seconds * 0.4)) * np.sin(2 * np.pi * np.cumsum(d.glide(n, 9.0, 22.0)) / SR)
        y = (d.sine(pitch * (1.0 + wob)) + 0.3 * d.sine(pitch * 2.0 * (1.0 + wob))) * d.perc(n, 0.002, seconds * 1.1)
    elif kind == "slide_down":
        f = d.glide(n, pitch * 4.0, pitch, 1.2)
        f = f * (1.0 + 0.012 * np.sin(2 * np.pi * 6.0 * t))
        y = d.sine(f) * 0.8 + d.sine(f * 2.0) * 0.12 + d.sweep(d.noise(n, rng, "white"), "bp", f, q=6.0) * 0.5
        y = d.fade(y, 0.02, 0.04)
        marks = {"end": seconds, "start": 0.0}
    elif kind == "bonk":
        n = secs(0.35)
        y = d.modal([pitch, pitch * 2.62, pitch * 4.1], [0.22, 0.09, 0.05], [1.0, 0.5, 0.25], n, rng, hardness=0.55) \
            + d.sine(pitch * 0.5 * (1.0 + 0.6 * np.exp(-np.arange(n) / SR / 0.02))) * d.perc(n, 0.001, 0.15) * 0.6
    else:
        raise ValueError("cartoon: kind must be boing, slide_down or bonk")
    return d.finish(d.reverb(y, t60=0.3, mix=0.08, bright=0.6, seed=int(rng.integers(1 << 30))), fade_out=0.03, tail_db=-50.0), marks


# ================================================================ pulses on exact times
@recipe("pulse", "A heartbeat: a low double thump, repeated at an exact tempo.",
        "Tension, a countdown to a decision, slow motion, a health or stress topic. Speed it up for rising panic. "
        "Each beat has a mark, so cuts can fall on beats.",
        sync=("a cut or the first beat", "Beats are exactly 60 / bpm seconds apart; each has a mark (beat1, beat2, ...). "
              "Cut the picture on the beats, or start the file where the tension starts."),
        bpm=(70.0, "beats per minute (50 calm, 70 resting, 110 tense, 150 panic)"),
        beats=(4, "number of beats"),
        depth=(0.6, "low-end weight (0 = light tap that phones can play, 1 = deep chest thump)"),
        pitch=(44.0, "pitch of the thump in Hz (36 very deep, 44 deep, 58 higher and easier to hear on small speakers)"))
def heartbeat(rng, bpm, beats, depth, pitch):
    period = 60.0 / bpm
    def thump(f, level):
        m = secs(min(0.28, period * 0.4))
        tt = np.arange(m) / SR
        low = d.sine(f * (1.0 + 0.8 * np.exp(-tt / 0.02))) * d.perc(m, 0.004, 0.2)
        body = d.bp(d.noise(m, rng, "brown"), f * 1.3, f * 5.0, 2) * d.perc(m, 0.003, 0.09) * 3.0
        return (low * (0.4 + 0.6 * depth) + body * (1.0 - 0.5 * depth)) * level
    parts, marks = [], {}
    for i in range(int(beats)):
        parts += [(thump(pitch, 1.0), i * period, 0), (thump(pitch * 1.24, 0.7), i * period + min(0.3, period * 0.32), 0)]
        marks[f"beat{i + 1}"] = i * period
    if not parts:
        raise ValueError("heartbeat: beats must be at least 1")
    return d.finish(d.layer(parts), fade_out=0.05, tail_db=-50.0), marks


@recipe("pulse", "A clock: tick, tock, at an exact interval.",
        "Time passing, a deadline, waiting, a quiz timer. One tick per second reads as a real clock; faster reads as a timer running out.",
        sync=("the first tick", "Ticks are exactly `gap` seconds apart; each has a mark (tick1, tick2, ...). "
              "If a clock or counter is on screen, put a tick on each change."),
        count=(4, "number of ticks"),
        gap=(1.0, "seconds between ticks, exactly"),
        pitch=(1800.0, "pitch of the tick in Hz (1200 wall clock, 2500 wristwatch)"))
def clock(rng, count, gap, pitch):
    if int(count) < 1:
        raise ValueError("clock: count must be at least 1")
    parts, marks = [], {}
    for i in range(int(count)):
        f = pitch * (1.0 if i % 2 == 0 else 0.8)                           # tick, then a lower tock
        m = secs(0.06)
        t = d.modal([f, f * 2.4, f * 0.31], [0.02, 0.012, 0.03], [1.0, 0.5, 0.5], m, rng, hardness=0.9)
        parts.append((t, i * gap, 0 if i % 2 == 0 else -2))
        marks[f"tick{i + 1}"] = i * gap
    return d.finish(d.reverb(d.layer(parts), t60=0.25, mix=0.08, bright=0.5, seed=int(rng.integers(1 << 30))), fade_out=0.02, tail_db=-50.0), marks


# ================================================================ beds
@recipe("bed", "Electrical hum that loops without a seam: mains hum, from clean to buzzy.",
        "Under a machine, a server room, old equipment, a neon sign; at low volume, mixed under other sounds. "
        "For rain, fire, wind and room tone see the recipes of those names.",
        sync=("the start of the scene", "Not frame-critical. Start it with the scene and fade it in and out over half a second in the edit; "
              "a bed that starts or stops hard is noticed."),
        kind=("hum", "hum"),
        seconds=(8.0, "length of the loop (6-20)"),
        amount=(0.5, "clean to buzzy"))
def bed(rng, kind, seconds, amount):
    if kind != "hum":
        raise ValueError("bed: kind must be hum (rain, fire, wind and room are recipes of their own)")
    n = secs(seconds + 0.5)
    base = 60.0
    y = sum(d.sine(base * k, n) / k ** (2.0 - 1.2 * amount) for k in (1, 2, 3, 4, 5, 7)) + d.hp(d.noise(n, rng, "pink"), 2000) * 0.02 * amount
    # a steady tone loops by ending on a whole number of cycles
    return d.finish(d.stereo(y)[:int(round(seconds * base)) * int(SR / base)], fade_in=0, fade_out=0, dc=False, tail_db=None)
