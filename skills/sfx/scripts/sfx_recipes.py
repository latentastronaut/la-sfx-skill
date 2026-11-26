"""Sound recipes: one small model per family of sound, built from layers.

Each recipe is a function (rng, **params) -> stereo signal, registered with what it is for and what its
parameters mean. `sfx.py list` prints this registry; `sfx.py make <name>` renders one.

Timing: every sound has a sync point, the moment in the file that must meet the event on screen. A recipe whose
sync point is not its first sample returns (signal, marks), where marks maps names to seconds from the start of the
file and the first mark is the sync point. Marks are exact: they are computed from the parameters, not measured.
"""
import re

import numpy as np

import sfx_dsp as d
from sfx_dsp import SR, secs

RECIPES = {}
_NOTE = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}


def hz(v):
    """A pitch as a number of Hz or a note name (A4, C#3, Eb5). Lets a sound be tuned to the music's key."""
    if isinstance(v, (int, float)):
        return float(v)
    m = re.fullmatch(r"([a-gA-G])([#b]?)(-?\d)", str(v).strip())
    if not m:
        return float(v)
    semis = _NOTE[m[1].lower()] + {"#": 1, "b": -1, "": 0}[m[2]] + 12 * (int(m[3]) + 1)
    return 440.0 * 2.0 ** ((semis - 69) / 12.0)


# How loud each recipe is rendered: the loudest 150 ms, in LUFS (sfx_dsp.loudest). The numbers follow the wyzowl
# sfx-kit's scale, so generated and fetched sounds sit together and sit under a voice without riding a fader.
LEVELS = {"riser": -20.0, "downlifter": -20.0, "impact": -18.0, "sub_drop": -22.0, "whoosh": -19.0, "stinger": -19.0,
          "whir": -21.0, "click": -27.0, "tick": -27.0, "pop": -22.0, "chime": -22.0, "notify": -22.0, "error": -22.0,
          "sparkle": -23.0, "retro": -24.0}

# Events: the separate small sounds inside a recipe (each raindrop, crackle, chirp or pop). While EVENTS is a list, every
# one placed is noted with its time, so a picture can be drawn from the same numbers that made the sound.
EVENTS = None


def note(at, pos=0.0, gain=1.0):
    """Note one event: `at` in samples from the start of the file, pan position (-1 to 1), linear peak gain."""
    if EVENTS is not None:
        EVENTS.append((at / SR, float(pos), float(gain)))


START = ("start", "Put the start of the file on the first frame of the event. If in doubt go a frame early, never late.")



def recipe(family, about, use, sync=START, **params):
    """Register a recipe. params: name=(default, 'what it does and its useful range').
    sync: (what the sync point meets, how to place it)."""
    def wrap(fn):
        RECIPES[fn.__name__] = {"fn": fn, "family": family, "about": about, "use": use, "params": params,
                                "level": LEVELS[fn.__name__], "sync": {"meets": sync[0], "how": sync[1]}}
        return fn
    return wrap


def render(name, seed=1, **overrides):
    """Render a recipe by name. Unknown parameters are an error, so a typo can't silently do nothing."""
    if name not in RECIPES:
        raise KeyError(f"no recipe named {name!r}; run `sfx.py list`")
    spec = RECIPES[name]
    bad = set(overrides) - set(spec["params"])
    if bad:
        raise KeyError(f"{name} has no parameter {sorted(bad)}; it takes {sorted(spec['params'])}")
    p = {k: v[0] for k, v in spec["params"].items()}
    for k, v in overrides.items():
        p[k] = coerce(p[k], v)
    out = spec["fn"](np.random.default_rng(seed), **p)
    x, marks = out if isinstance(out, tuple) else (out, {"start": 0.0})
    for k, v in marks.items():
        if not 0.0 <= v <= len(x) / SR + 1e-9:
            raise ValueError(f"{name}: mark {k!r} at {v} s is outside the sound ({len(x) / SR:.3f} s)")
    return x, p, {k: round(float(v), 6) for k, v in marks.items()}


def render_events(name, seed=1, **overrides):
    """render(), plus the list of events inside the sound: [{"t": seconds, "pos": -1..1, "gain": 0..1}], in time order.
    gain is relative to the loudest event. In a loop, an event placed in the blended tail is reported where it is heard,
    at the start. A recipe that places no separate events gives an empty list."""
    global EVENTS
    EVENTS = []
    try:
        x, p, marks = render(name, seed=seed, **overrides)
        got = EVENTS
    finally:
        EVENTS = None
    dur = len(x) / SR
    top = max((g for _, _, g in got), default=1.0) or 1.0
    ev = sorted(((t % dur if t >= dur else t), pos, g / top) for t, pos, g in got if t >= 0)
    return x, p, marks, [{"t": round(t, 5), "pos": round(pos, 3), "gain": round(g, 4)} for t, pos, g in ev]


def part(name, rng, **p):
    """A recipe rendered as one layer of a bigger sound, at its own mix level, with its marks."""
    x, _, marks = render(name, seed=int(rng.integers(1 << 30)), **p)
    return x * d.db(LEVELS[name] - d.loudest(x)), marks


def coerce(default, v):
    """Turn a command-line value into the type of the parameter's default. Pitches also accept note names."""
    if isinstance(default, bool):
        return v if isinstance(v, bool) else str(v).lower() in ("1", "true", "yes", "on")
    if isinstance(default, (int, float)):
        if isinstance(v, (int, float)):
            return type(default)(v)
        try:
            return type(default)(float(v))
        except ValueError:
            return hz(v)
    return str(v)


# ================================================================ transitions and cinematic
@recipe("transition", "Tension that builds to a cut: rising noise, a rising tone and an accelerating pulse.",
        "Before a reveal, a title, a section change or a drop. End it exactly on the cut and put an impact or silence after it. "
        "1-2 s for a video cut, 3-8 s for a trailer build. One per reveal: a riser on every cut stops meaning anything.",
        seconds=(3.0, "length; the build is slow at first and steep at the end (0.8-8)"),
        root=(110.0, "starting pitch of the tone in Hz or a note name; match the music's key"),
        octaves=(1.5, "how far the tone climbs (0.5 subtle, 2 dramatic)"),
        air=(0.7, "amount of the noise sweep (0-1); high = airy and modern, low = synth-like"),
        tone=(0.45, "amount of the pitched layer (0-1); 0 = pure noise riser, safe over any music"),
        pulse=(0.5, "depth of the accelerating tremolo (0-1); adds urgency"),
        tail=(0.12, "seconds of release after the peak; 0 = hard stop exactly on the cut, 1+ = washes over it"),
        sync=("the cut", "The peak is `seconds` into the file. Start the file at cut time minus `seconds`, so the peak lands on the cut."))
def riser(rng, seconds, root, octaves, air, tone, pulse, tail):
    n = secs(seconds)
    x = np.linspace(0.0, 1.0, n)
    swept = d.sweep(d.noise(n, rng, "pink"), "bp", d.glide(n, 250, 5000, 1.6), q=d.line(n, 1.0, 3.0))
    hiss = d.sweep(d.noise(n, rng, "pink"), "hp", d.glide(n, 1000, 6000, 2.0)) * x ** 3
    air_l = d.widen(d.lp((swept + 0.35 * hiss) * x ** 2.0, 9000, 2), rng, 0.4)
    f = d.glide(n, root, root * 2.0 ** octaves, 1.3)
    voices = sum(d.saw(f * 2.0 ** (c / 1200.0), phase=rng.random()) for c in (-11, 0, 9)) / 3.0
    tone_l = d.sweep(voices, "lp", d.glide(n, 350, 6000, 1.3), q=1.4)
    tone_l = d.sweep(tone_l, "hp", d.glide(n, 40, root * 2.0 ** octaves * 0.9, 2.0)) * x ** 1.6   # the bottom drops out as it climbs
    sub = d.sine(d.glide(n, root / 2.0, root * 2.0 ** (octaves * 0.4) / 2.0)) * x ** 1.2 * (1.0 - x ** 6)
    ph = np.cumsum(d.glide(n, 3.0, 22.0, 1.4)) / SR
    trem = 1.0 - pulse * x * (0.5 + 0.5 * np.cos(2 * np.pi * ph))
    dry = d.layer([(air_l, 0, 0 + 10 * (air - 0.5)), (d.gain_env(d.stereo(tone_l), trem), 0, -6 + 10 * (tone - 0.5)),
                   (sub, 0, -24 + 8 * (tone - 0.5))])
    wet = d.reverb(dry, t60=1.4, mix=0.22, bright=0.7, seed=int(rng.integers(1 << 30)))
    keep = n + (secs(tail) if tail > 0 else 0)
    out = wet[:keep]
    out = out[:n] if tail == 0 else out
    return d.finish(out, fade_out=0.004 if tail == 0 else min(tail, 0.5), tail_db=None), {"peak": len(out) / SR if tail == 0 else seconds}


@recipe("transition", "The opposite of a riser: energy falls away. Falling noise and pitch into a long tail.",
        "After a climax, to close a section, or under a slow-motion moment. Also the 'power down' sound. Start it on the cut.",
        seconds=(2.0, "length (1-6)"),
        root=(440.0, "starting pitch of the tone; it falls from here"),
        octaves=(3.0, "how far it falls"),
        air=(0.2, "amount of falling noise (0-1)"),
        tone=(0.8, "amount of the pitched layer (0-1)"))
def downlifter(rng, seconds, root, octaves, air, tone):
    n = secs(seconds)
    x = np.linspace(0.0, 1.0, n)
    env = (1.0 - x) ** 1.8
    swept = d.sweep(d.noise(n, rng, "pink"), "bp", d.glide(n, 5000, 180, 0.6), q=d.line(n, 3.0, 1.0))
    air_l = d.widen(d.lp(swept * env, 9000, 2), rng, 0.4)
    f = d.glide(n, root, root / 2.0 ** octaves, 0.7)
    voices = sum(d.saw(f * 2.0 ** (c / 1200.0), phase=rng.random()) for c in (-10, 0, 8)) / 3.0
    tone_l = d.sweep(voices, "lp", d.glide(n, 6000, 200, 0.6), q=1.3) * env
    sub = d.sine(d.glide(n, root / 4.0, max(root / 2.0 ** (octaves + 2), 28.0), 0.7)) * (1.0 - x) ** 1.2
    dry = d.layer([(air_l, 0, -4 + 8 * (air - 0.5)), (tone_l, 0, -6 + 10 * (tone - 0.5)), (sub, 0, -8)])
    return d.finish(d.reverb(dry, t60=2.2, mix=0.3, bright=0.4, seed=int(rng.integers(1 << 30))), fade_in=0.004, fade_out=0.3)


@recipe("impact", "A cinematic hit: a deep sub, a thump, a soft knock and a dark tail; a crack on top if wanted.",
        "On the cut: a title landing, a reveal, the end of a riser. The one big sound of a video; use it once or twice. "
        "Shorten the tail and lower the weight for a 'thud' under a graphic. Keep the sub: it is what feels big.",
        weight=(0.8, "size of the low end (0 = small thud, 1 = trailer boom)"),
        bright=(0.1, "brightness of the crack and tail (0 = dull and distant, 1 = sharp and close); above 0.3 it turns thin and toy-like"),
        punch=(0.1, "level of the attack against the body (0 soft, 1 hard)"),
        tail=(1.0, "reverb length in seconds (0.3 tight, 4 huge)"),
        root=(38.0, "pitch the sub lands on, Hz or note; tune to the key if music is playing (35-70)"),
        boom=(0.0, "0 = a struck hit (the pitch drops fast, with a knock); 1 = a slam: a held low rumble, little pitch drop, no knock"))
def impact(rng, weight, bright, punch, tail, root, boom):
    n = secs(0.9 + 1.4 * weight)
    tt = np.arange(n) / SR
    sub = d.sine(root * (1.0 + (2.4 - 1.7 * boom) * np.exp(-tt / 0.035))) * d.perc(n, 0.001, 0.5 + 1.3 * weight)
    sub = d.saturate(sub, 1.2 + 2.0 * weight)
    thump = d.lp(d.noise(n, rng, "brown"), 160 + 320 * bright, 4) * d.perc(n, 0.002, 0.3 + 0.3 * weight)
    k = root * rng.uniform(2.6, 3.4)
    knock = d.modal([k, k * 1.71, k * 2.83, k * 4.1], [0.28, 0.2, 0.12, 0.08], [1.0, 0.6, 0.4, 0.25], n, rng, hardness=0.35)
    crack = d.hp(d.noise(n, rng, "white"), 1200 + 3000 * bright) * d.perc(n, 0.0004, 0.04 + 0.1 * bright)
    slam = d.bp(d.noise(n, rng, "pink"), 180, 1500 + 3500 * bright) * d.perc(n, 0.001, 0.25 + 0.5 * weight)   # the body a phone can play
    top = d.layer([(thump, 0, -5), (slam, 0, -3), (knock * (1.0 - boom), 0, -4), (crack, 0, -8 + 10 * punch)])
    top = d.transient(top, 1.0 + punch, 1.0)
    wet = d.reverb(d.lp(top, 2500 + 6000 * bright), t60=tail, mix=1.0, bright=0.3 + 0.4 * bright,
                   pre_delay=0.02, seed=int(rng.integers(1 << 30)))
    parts = [(sub, 0, -6 + 6 * weight), (top, 0, 0), (wet, 0, -2 + 3 * weight)]
    if boom > 0:                                              # the held low-mid body of a slam: what stays loud after the attack
        m = secs(1.2 + 2.0 * weight)
        rumble = d.bp(d.noise(m, rng, "pink"), 60, 170, 2) * d.perc(m, 0.003, 1.5 + 2.5 * weight)
        rumble = d.saturate(rumble / np.max(np.abs(rumble)), 2.0)
        parts[0] = (sub, 0, -6 + 6 * weight - 6 * boom)       # the rumble takes over from the sub
        parts.append((d.widen(rumble, rng, 0.3), 0, -8 + 8 * boom))
    return d.finish(d.trim(d.layer(parts), -66, keep=0.05), fade_out=min(0.4, tail * 0.3))


@recipe("impact", "A pure low-end drop: a sine that glides down and fades. No attack, all weight.",
        "Under a slow-motion moment, a logo, a scene going dark, or layered beneath an impact. Inaudible on phone speakers, "
        "so never let it carry meaning alone.",
        seconds=(1.8, "length (0.6-4)"),
        start=(110.0, "starting pitch in Hz or a note"),
        end=(32.0, "final pitch; below 30 Hz most systems reproduce nothing"),
        grit=(0.3, "saturation (0 clean, 1 growl); grit adds harmonics that small speakers can play"))
def sub_drop(rng, seconds, start, end, grit):
    n = secs(seconds)
    s = d.sine(d.glide(n, start, end, 0.6)) * d.perc(n, 0.01, seconds * 1.1)
    s = d.saturate(s, 1.0 + 4.0 * grit)
    rumble = d.lp(d.noise(n, rng, "brown"), 90, 4) * d.perc(n, 0.02, seconds * 0.6)
    return d.finish(d.layer([(s, 0, 0), (rumble, 0, -14)]), fade_in=0.004, fade_out=0.15)


@recipe("transition", "Air moving past: a band of noise that swells, sweeps and crosses the stereo field.",
        "On movement: a cut, a text or graphic flying in, a camera whip, a swipe. The peak belongs on the frame the motion "
        "lands. Short (0.2-0.5 s) for UI and text, longer (0.6-1.5 s) for scene transitions. The most reusable sound there is.",
        seconds=(0.5, "length (0.15-2.5)"),
        peak=(0.55, "where the loudest point falls (0-1); late = builds into the cut, early = something flying away"),
        lo=(150.0, "lowest centre frequency; lower = heavier object"),
        hi=(1600.0, "highest centre frequency at the peak; higher = faster and thinner (1500 heavy, 5000 a thin swish). Above 2500 it gets hissy"),
        body=(0.9, "low-end weight (0 = airy swish, 1 = heavy pass-by)"),
        travel=(1.0, "stereo movement: 1 left-to-right, -1 right-to-left, 0 stays centred"),
        sharp=(0.2, "resonance of the sweep (0 = soft wind, 1 = whistling, sword-like)"),
        sync=("the middle of the move", "The loudest point is the `peak` mark. Start the file at (time of the middle of the move) minus that mark. "
              "For something flying in and stopping, use peak=0.8 and put the mark on the frame it stops."))
def whoosh(rng, seconds, peak, lo, hi, body, travel, sharp):
    n = secs(seconds * 0.9)                                   # the short room tail fills the rest
    shape = d.bell_curve(n, peak, 0.17, skew=1.35)
    fc = lo * (hi / lo) ** shape
    q = 0.8 + 4.0 * sharp
    mid = d.sweep(d.noise(n, rng, "pink"), "bp", fc, q=q)
    air_l = d.sweep(d.noise(n, rng, "pink"), "bp", fc * 2.0, q=0.9)
    low = d.hp(d.sweep(d.noise(n, rng, "pink"), "lp", fc * 0.45, q=0.8), 90, 2)   # weight without sub rumble
    flutter = 1.0 + 0.12 * d.lp(rng.standard_normal(n), 25, 2) * 8.0     # real air is never perfectly smooth
    m = d.lp(mid + 0.35 * air_l + (0.1 + 0.5 * body) * low, 10000, 2) * shape ** 1.4 * flutter
    position = travel * np.tanh(3.0 * (np.linspace(0, 1, n) - peak)) / np.tanh(1.5)
    out = d.pan(m, np.clip(position, -1, 1)) * 0.8 + d.widen(m, rng, 0.4) * 0.35
    wet = d.reverb(out, t60=0.25, mix=0.08, bright=0.5, seed=int(rng.integers(1 << 30)))
    return d.finish(wet[:secs(seconds)], fade_in=0.01, fade_out=min(0.08, seconds * 0.2), tail_db=-50.0), {"peak": float(np.argmax(shape)) / SR}


@recipe("transition", "A short musical hit: a low thump under a sustained chord that swells and fades.",
        "A dramatic beat, a warning, a chapter card, a 'dun' moment. minor = tension, major = triumph, fifth = neutral and "
        "safest over music. Tune root to the music.",
        root=(110.0, "root note in Hz or a note name"),
        chord=("minor", "minor, major, fifth, dim (most tense) or octave"),
        seconds=(1.8, "length of the chord (0.8-4)"),
        bright=(0.5, "how open the filter gets (0 dark, 1 brassy)"),
        hit=(0.6, "level of the thump at the start (0 none, 1 strong)"))
def stinger(rng, root, chord, seconds, bright, hit):
    steps = {"minor": (0, 3, 7, 12), "major": (0, 4, 7, 12), "fifth": (0, 7, 12), "dim": (0, 3, 6, 9), "octave": (0, 12, 24)}
    if chord not in steps:
        raise ValueError(f"chord must be one of {sorted(steps)}")
    n = secs(seconds)
    tt = np.arange(n) / SR
    v = np.zeros(n)
    for s in steps[chord]:
        for cents in (-8, 0, 7):
            v += d.saw(np.full(n, root * 2.0 ** (s / 12.0 + cents / 1200.0)), phase=rng.random())
    cutoff = 300 + (1500 + 6000 * bright) * np.exp(-tt / (0.25 + 0.5 * seconds)) * (1 - np.exp(-tt / 0.02))
    pad = d.sweep(v / 9.0, "lp", cutoff, q=1.2) * d.perc(n, 0.012, seconds * 1.3)
    thump, _, _ = render("impact", seed=int(rng.integers(1 << 30)), weight=0.5, bright=0.3, tail=0.8, root=root / 2.0 if root > 80 else root)
    out = d.layer([(d.widen(pad, rng, 0.5), 0, -4), (thump, 0, -30 + 26 * hit)])
    return d.finish(d.reverb(out, t60=1.6, mix=0.2, bright=0.5, seed=int(rng.integers(1 << 30))), fade_out=0.4)


@recipe("transition", "Sped-up motion: a pitch that winds up with a fast flutter, like tape on fast-forward.",
        "Time skips, 'meanwhile', a process running fast, rewinds (direction=-1). Keep it under the picture's sped-up section.",
        seconds=(1.0, "length (0.3-3)"),
        lo=(180.0, "starting pitch"),
        hi=(1400.0, "ending pitch"),
        flutter=(28.0, "flutter rate in Hz (15 = chunky, 40 = buzzy)"),
        direction=(1.0, "1 winds up (forward), -1 winds down (rewind or power-down)"))
def whir(rng, seconds, lo, hi, flutter, direction):
    n = secs(seconds)
    f = d.glide(n, lo, hi, 0.8) if direction >= 0 else d.glide(n, hi, lo, 1.2)
    tone = d.sweep(d.saw(f) * 0.6 + d.triangle(f * 2.01), "lp", f * 4.0, q=1.0)
    chop = 0.55 + 0.45 * np.sign(np.sin(2 * np.pi * np.cumsum(flutter * f / f.mean()) / SR))
    chop = d.lp(chop, 400, 1)
    hiss = d.sweep(d.noise(n, rng, "pink"), "bp", f * 5.0, q=1.5)
    m = (tone + 0.5 * hiss) * chop * d.bell_curve(n, 0.5, 0.45)
    return d.finish(d.widen(m, rng, 0.4), fade_in=0.01, fade_out=0.03)


# ================================================================ interface and feedback
@recipe("ui", "A tiny tick: a few very short ringing partials with a soft thock underneath.",
        "Mouse clicks, button presses, toggles, on-screen cursor clicks in a tutorial. Keep it 15-20 dB under the voice. "
        "Use one click sound for one kind of action, everywhere.",
        pitch=(1600.0, "main ring in Hz (1500 = plastic and warm, 4000 = glassy)"),
        soft=(0.6, "0 = sharp and mechanical, 1 = soft and rounded"),
        body=(0.7, "level of the low thock (0 = thin tick, 1 = chunky button)"))
def click(rng, pitch, soft, body):
    n = secs(0.09)
    ring = d.modal([pitch, pitch * 1.52, pitch * 2.71], [0.012 * (1 + soft), 0.009 * (1 + soft), 0.006],
                   [1.0, 0.5, 0.3], n, rng, hardness=1.0 - soft)
    thock = d.modal([pitch * 0.105, pitch * 0.19], [0.035, 0.02], [1.0, 0.5], n, rng, hardness=0.3)
    snap = d.hp(d.noise(n, rng, "white"), 3500) * d.perc(n, 0.0002, 0.006)
    return d.finish(d.layer([(ring, 0, 0), (thock, 0, -14 + 14 * body), (snap, 0, -10 - 14 * soft)]), fade_out=0.01)


@recipe("ui", "A low wooden-plastic thock with a small click: one key of a keyboard.",
        "Typing on screen, text appearing letter by letter, a counter ticking. Render 5-8 variations and rotate them, "
        "with slightly uneven timing; one repeated sample sounds like a machine gun.",
        pitch=(650.0, "thock pitch in Hz (350 deep mechanical, 900 thin laptop)"),
        clack=(0.6, "level of the high click (0 = muted thud, 1 = clacky)"))
def tick(rng, pitch, clack):
    n = secs(0.07)
    p = pitch * rng.uniform(0.92, 1.08)
    thock = d.modal([p, p * 2.3, p * 3.9], [0.03, 0.018, 0.01], [1.0, 0.5, 0.3], n, rng, hardness=0.45)
    top = d.bp(d.noise(n, rng, "white"), 2500, 7000) * d.perc(n, 0.0002, rng.uniform(0.004, 0.008))
    return d.finish(d.layer([(thock, 0, 0), (top, 0, -18 + 14 * clack)]), fade_out=0.008)


@recipe("ui", "A round bubble pop: a sine whose pitch flicks up (or down) in a few hundredths of a second.",
        "Something appearing: a text box, an icon, a tooltip, a list item. Pitch up = appear, down = disappear. "
        "Raise the pitch a step per item for lists.",
        pitch=(520.0, "starting pitch in Hz or a note (300 big, 900 tiny)"),
        direction=(1.0, "1 = pitch rises (appear), -1 = falls (disappear)"),
        seconds=(0.09, "length (0.05-0.2)"))
def pop(rng, pitch, direction, seconds):
    n = secs(seconds)
    f = d.glide(n, pitch, pitch * (1.9 if direction >= 0 else 0.55), 0.6)
    body = d.sine(f) * d.perc(n, 0.002, seconds * 0.8)
    air = d.bp(d.noise(n, rng, "white"), 1500, 6000) * d.perc(n, 0.0003, 0.008)
    return d.finish(d.layer([(body, 0, 0), (air, 0, -20)]), fade_out=0.01)


@recipe("ui", "Two or three bell notes rising: the sound of something done right.",
        "Success, step complete, payment accepted, correct answer, a reveal in a tutorial. Tune root to the music's key. "
        "major = plain success, fifth = neutral confirm, octave = short tick-off, arp = bigger win.",
        root=(880.0, "first note in Hz or a note name (A5 = 880)"),
        pattern=("major", "major (root, third, fifth), fifth (two notes), octave, or arp (four notes)"),
        gap=(0.09, "seconds between notes (0.06 quick, 0.15 relaxed)"),
        ring=(0.55, "how long each note rings, in seconds (0.3 tight UI, 1.2 lingering)"),
        bright=(0.5, "0 = soft and mellow, 1 = glassy"))
def chime(rng, root, pattern, gap, ring, bright):
    steps = {"major": (0, 4, 7), "fifth": (0, 7), "octave": (0, 12), "arp": (0, 4, 7, 12)}
    if pattern not in steps:
        raise ValueError(f"pattern must be one of {sorted(steps)}")
    parts = []
    for i, s in enumerate(steps[pattern]):
        f = root * 2.0 ** (s / 12.0)
        n = secs(ring * 1.2)
        ratios = [1.0, 2.0, 3.01, 4.18, 5.43, 6.8]
        amps = [1.0, 0.45, 0.2 + 0.3 * bright, 0.25 * bright, 0.2 * bright, 0.12 * bright]
        note = d.modal([f * r for r in ratios], [ring / (1.0 + 0.9 * k) for k in range(6)], amps, n, rng, hardness=0.4 + 0.5 * bright)
        parts.append((d.pan(note, (i - (len(steps[pattern]) - 1) / 2.0) * 0.25), i * gap, 0 if i == len(steps[pattern]) - 1 else -2))
    return d.finish(d.reverb(d.layer(parts), t60=0.4 + ring, mix=0.14, bright=0.7, seed=int(rng.integers(1 << 30))), fade_out=0.15, tail_db=-50.0)


@recipe("ui", "Two soft mallet notes: a wooden, friendly ping.",
        "A message arriving, a gentle alert, a reminder, a tooltip. Softer and less triumphant than chime. "
        "up = something arrived, down = something left or closed.",
        root=(660.0, "first note in Hz or a note name"),
        direction=(1.0, "1 = second note higher, -1 = lower"),
        gap=(0.13, "seconds between the notes"))
def notify(rng, root, direction, gap):
    parts = []
    for i, f in enumerate((root, root * (1.5 if direction >= 0 else 0.75))):
        n = secs(0.7)
        note = d.modal([f, f * 3.93, f * 9.2], [0.45, 0.12, 0.05], [1.0, 0.3, 0.1], n, rng, hardness=0.3)
        parts.append((note, i * gap, 0))
    return d.finish(d.reverb(d.layer(parts), t60=0.5, mix=0.1, bright=0.5, seed=int(rng.integers(1 << 30))), fade_out=0.12, tail_db=-50.0)


@recipe("ui", "A dull double buzz that steps down: a muted 'no'.",
        "Errors, invalid input, a wrong answer, a blocked action. Kept dull on purpose: a harsh buzzer punishes the viewer. "
        "Use sparingly.",
        pitch=(280.0, "pitch of the first buzz in Hz or a note (under 200 vanishes on phone speakers)"),
        pulses=(2, "number of buzzes (1-3)"),
        rough=(0.5, "0 = soft and round, 1 = buzzy"))
def error(rng, pitch, pulses, rough):
    parts = []
    for i in range(int(pulses)):
        n = secs(0.13)
        f = pitch * 2.0 ** (-3 * i / 12.0) * d.line(n, 1.0, 0.97)
        b = d.square(f) * 0.5 + d.square(f * 1.059) * 0.5
        b = d.lp(b, 900 + 2500 * rough, 2) * d.perc(n, 0.004, 0.22)
        parts.append((d.fade(b, 0, 0.02), i * 0.15, 0))
    return d.finish(d.layer(parts), fade_out=0.02)


@recipe("ui", "A scatter of tiny high bells that thins out: glitter.",
        "Magic, a reward, something new or premium, a 'ta-da' reveal layered over a chime. Easy to overuse; it reads as "
        "sweet. Tune root to the key.",
        seconds=(1.2, "length (0.5-3)"),
        root=(2093.0, "lowest bell in Hz or a note name (C7 = 2093)"),
        density=(22.0, "pings per second at the start"),
        rise=(0.0, "pitch drift: 1 = pings climb over time, -1 = fall, 0 = random"))
def sparkle(rng, seconds, root, density, rise):
    scale = [0, 2, 4, 7, 9, 12, 14, 16, 19, 21, 24]
    n = secs(seconds)
    out = np.zeros((n + secs(0.6), 2))
    for _ in range(int(density * seconds)):
        at = rng.beta(1.0, 2.2) * seconds * 0.8              # most pings early, then they thin out
        pos = at / seconds
        idx = rng.integers(0, len(scale))
        if rise:
            idx = int(np.clip(round((pos if rise > 0 else 1 - pos) * (len(scale) - 1) + rng.normal(0, 1.5)), 0, len(scale) - 1))
        f = root * 2.0 ** (scale[idx] / 12.0)
        m = secs(rng.uniform(0.15, 0.45))
        ping = d.modal([f, f * 2.76, f * 5.4], [m / SR, m / SR * 0.5, m / SR * 0.3], [1.0, 0.3, 0.12], m, rng, hardness=0.9)
        i = secs(at)
        out[i:i + m] += d.pan(ping * rng.uniform(0.3, 1.0), rng.uniform(-0.9, 0.9))[:len(out) - i]
    wet = d.reverb(out, t60=0.9, mix=0.22, bright=0.9, seed=int(rng.integers(1 << 30)))
    return d.finish(wet[:secs(seconds * 1.25)], fade_out=min(0.3, seconds * 0.25), tail_db=-50.0)


# ================================================================ retro game
@recipe("retro", "8-bit game sounds: square waves and noise with stepped pitch, in the sfxr tradition.",
        "Pixel-art games, playful UI, nostalgic jokes in a video. They cut through any mix, so keep them quiet. "
        "coin = pickup or point, jump, laser = shoot or zap, hit = damage, powerup, explode, blip = menu move.",
        kind=("coin", "coin, jump, laser, hit, powerup, explode or blip"),
        pitch=(1.0, "pitch multiplier (0.5 an octave down, 2 an octave up)"),
        crush=(0.5, "bit-crush amount (0 clean, 1 very lo-fi)"))
def retro(rng, kind, pitch, crush):
    def sq(f, width=0.5):
        return d.square(np.asarray(f) * pitch, width=width)
    if kind == "coin":
        a, b = secs(0.07), secs(0.35)
        y = np.concatenate([sq(np.full(a, 988.0)), sq(np.full(b, 1319.0)) * d.perc(b, 0.001, 0.35)])
    elif kind == "jump":
        n = secs(0.22)
        y = sq(d.glide(n, 220, 660, 0.7), 0.25) * d.perc(n, 0.002, 0.3)
    elif kind == "laser":
        n = secs(0.2)
        y = sq(d.glide(n, 1800, 180, 0.5), 0.3) * d.perc(n, 0.001, 0.22)
    elif kind == "hit":
        n = secs(0.16)
        y = (sq(d.glide(n, 400, 70, 0.5)) * 0.6 + d.noise(n, rng) * 1.2) * d.perc(n, 0.001, 0.14)
    elif kind == "powerup":
        n, steps = secs(0.5), 10
        f = 330.0 * 2.0 ** (np.floor(np.linspace(0, steps, n, endpoint=False)) * 2 / 12.0)
        y = sq(f, 0.35) * d.perc(n, 0.002, 0.9)
    elif kind == "explode":
        n = secs(0.7)
        hold = np.maximum(1, (d.line(n, 6, 60, 1.5)).astype(int))   # noise sampled slower and slower: the pitch of the rumble falls
        w = rng.uniform(-1, 1, n)
        idx = np.arange(n)
        y = w[idx - idx % hold] * d.perc(n, 0.001, 0.6)
    elif kind == "blip":
        n = secs(0.06)
        y = sq(np.full(n, 660.0)) * d.perc(n, 0.001, 0.08)
    else:
        raise ValueError("kind must be coin, jump, laser, hit, powerup, explode or blip")
    if crush > 0:
        levels = 2.0 ** (8 - 5 * crush)
        y = np.round(y * levels) / levels
        y = d.lp(y, 14000 - 8000 * crush, 2)
    return d.finish(y, fade_out=0.01)
