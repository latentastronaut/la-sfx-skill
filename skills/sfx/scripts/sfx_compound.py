"""Compound sounds: several recipes laid on one timeline, built around a single sync point.

A riser means little without the hit it leads to, and the two only work when the hit lands on the frame. A compound
takes the time before the sync point as a parameter (`lead`) and returns marks that say exactly where each event is
in the file, so the caller can place it without measuring: file start = event time on screen - mark.

Each part is rendered at its own mix level (sfx_recipes.LEVELS), so the balance inside a compound is the same as if
the parts had been placed one by one.
"""
import numpy as np

import sfx_dsp as d
import sfx_ambience  # noqa: F401  (registers rain, fire, wind, room)
import sfx_events  # noqa: F401  (registers thunder, explosion)
import sfx_cinematic  # noqa: F401  (registers braam, pass_by)
import sfx_world  # noqa: F401  (registers spark, crickets, ocean)
import sfx_more  # noqa: F401  (registers arc, pour, vinyl)
import sfx_measured  # noqa: F401  (registers footsteps, stream)
import sfx_signals  # noqa: F401  (compounds below use its recipes)
from sfx_dsp import SR, secs
from sfx_recipes import LEVELS, part, recipe

LEVELS.update({"riser_hit": -18.0, "riser_drop": -20.0, "whoosh_hit": -18.0, "swish_pop": -22.0, "swell_hit": -18.0,
               "reveal": -21.0, "glitch_cut": -20.0, "rewind": -21.0, "time_skip": -21.0, "logo_sting": -19.0, "pop_run": -22.0, "typing": -27.0, "count_up": -22.0})

ON_MARK = "Start the file at (time of the event on screen) minus the first mark, so the mark lands on the frame. " \
          "Set `lead` to the time you have before the event; the mark is then exactly `lead`."


def _low(root, top):
    """The same note, dropped by octaves until it is at or under `top` Hz."""
    f = float(root)
    while f > top:
        f /= 2.0
    return f


def _ending_at(x, at):
    """A layer placed so its last sample falls just before `at` seconds. Cuts the head if it is too long."""
    start = secs(at) - len(x) if at > 0 else -len(x)
    if start < 0:
        x, start = d.fade(x[-start:], 0.01, 0), 0
    return x, start / SR


def _need(lead, least, name):
    if lead < least:
        raise ValueError(f"{name}: lead must be at least {least} s")


def _build(rng, lead, air=0.7, tone=0.45, root=110.0):
    """A riser that stops dead `lead` seconds in."""
    r, _ = part("riser", rng, seconds=lead, root=root, tail=0.0, air=air, tone=tone)
    return _ending_at(r, lead)


# ================================================================ build and payoff
@recipe("compound", "A riser that stops dead and an impact on the same sample: the build and the payoff as one file.",
        "The one big moment: a title card, a reveal, a before/after, the start of the main section. Once or twice per video. "
        "`gap` leaves a beat of silence before the hit, which makes it land harder.",
        sync=("the cut or the frame the title lands", ON_MARK),
        lead=(2.0, "seconds of build before the hit (0.6-8); the hit is at exactly this time in the file"),
        root=(110.0, "pitch of the riser's tone in Hz or a note; the hit's sub is tuned to the same note"),
        weight=(0.7, "size of the hit (0 = thud, 1 = trailer boom)"),
        tail=(2.0, "seconds of reverb after the hit (0.4 tight, 4 huge)"),
        gap=(0.0, "seconds of silence between the end of the riser and the hit (0-0.2); 0.08 is about two frames"),
        air=(0.7, "noise in the riser (0-1)"),
        tone=(0.45, "pitched layer in the riser (0-1); 0 is safe over any music"),
        bright=(0.1, "brightness of the hit (0 dull, 1 sharp)"),
        punch=(0.1, "attack of the hit (0 soft, 1 hard)"),
        boom=(1.0, "1 = a slam with a held low rumble; lower lets in a pitch-dropping thump, which after a riser was heard as a goofy tom"))
def riser_hit(rng, lead, root, weight, tail, gap, air, tone, bright, punch, boom):
    _need(lead - gap, 0.4, "riser_hit")
    r, at = _build(rng, lead - gap, air, tone, root)
    h, _ = part("impact", rng, weight=weight, tail=tail, root=_low(root, 62.0), bright=bright, punch=punch, boom=boom)
    out = d.layer([(r, at, 0), (h, lead, 0)])
    return d.finish(out, fade_in=0.005, fade_out=min(0.4, tail * 0.3)), {"hit": lead, "riser_end": lead - gap}


@recipe("compound", "A riser capped by a sub drop: the build cuts out and the floor falls away.",
        "A reveal that should feel like a drop, not a bang: slow motion, a dark or serious turn, a logo. "
        "`thud` adds a soft knock so the moment is still heard on a phone, where the sub is silent.",
        sync=("the cut", ON_MARK),
        lead=(2.0, "seconds of build before the drop (0.6-8)"),
        root=(110.0, "pitch of the riser's tone; the drop starts from the same note"),
        drop=(1.8, "length of the sub drop in seconds (0.8-4)"),
        thud=(0.4, "level of the soft knock on the drop (0 = sub only, 1 = clear thud)"),
        gap=(0.0, "seconds of silence before the drop (0-0.2)"),
        air=(0.7, "noise in the riser (0-1)"),
        tone=(0.45, "pitched layer in the riser (0-1)"))
def riser_drop(rng, lead, root, drop, thud, gap, air, tone):
    _need(lead - gap, 0.4, "riser_drop")
    r, at = _build(rng, lead - gap, air, tone, root)
    s, _ = part("sub_drop", rng, seconds=drop, start=_low(root, 120.0), end=32.0, grit=0.4)
    parts = [(r, at, 0), (s, lead, 2)]
    if thud > 0:
        k, _ = part("impact", rng, weight=0.25, bright=0.3, punch=0.3, tail=0.5, root=_low(root, 62.0))
        parts.append((k, lead, -16 + 12 * thud))
    return d.finish(d.layer(parts), fade_in=0.005, fade_out=0.15), {"drop": lead, "riser_end": lead - gap}


@recipe("compound", "A whoosh whose loudest point is a thud: something flies in and lands.",
        "A title or graphic slamming into place, a card dropping in, a punch-in zoom that stops hard. "
        "Short lead (0.2-0.4) for text, longer (0.5-1) for a full-screen move.",
        sync=("the frame the thing stops moving", ON_MARK),
        lead=(0.4, "seconds of whoosh before the landing (0.15-1.5); match the length of the move on screen"),
        weight=(0.35, "size of the landing (0 = tap, 1 = boom)"),
        tail=(0.6, "seconds of reverb after the landing"),
        hi=(1600.0, "top of the whoosh sweep in Hz (1500 heavy, 5000 thin)"),
        travel=(1.0, "stereo movement of the whoosh: 1 left to right, -1 right to left, 0 centred"),
        root=(50.0, "pitch of the landing's sub (35-70)"))
def whoosh_hit(rng, lead, weight, tail, hi, travel, root):
    _need(lead, 0.12, "whoosh_hit")
    w, at = _whoosh_to(rng, lead, hi=hi, travel=travel, body=0.3 + 0.5 * weight)
    h, _ = part("impact", rng, weight=weight, tail=tail, punch=0.1, root=root, boom=1.0)
    return d.finish(d.layer([(w, at, -2), (h, lead, 0)]), fade_in=0.005, fade_out=min(0.3, tail * 0.3)), {"hit": lead}


@recipe("compound", "A quick swish that ends in a pop: something small slides in and settles.",
        "Text, icons, list items, lower thirds and stickers that move into place. The lighter cousin of whoosh_hit; "
        "safe to use many times in a video.",
        sync=("the frame the thing settles", ON_MARK),
        lead=(0.22, "seconds of swish before the pop (0.1-0.6); match the move on screen"),
        pitch=(520.0, "pitch of the pop in Hz or a note (300 big, 900 tiny)"),
        swish=(0.5, "level of the swish against the pop (0 = nearly just a pop, 1 = airy)"),
        travel=(1.0, "stereo movement: 1 left to right, -1 right to left, 0 centred"))
def swish_pop(rng, lead, pitch, swish, travel):
    _need(lead, 0.08, "swish_pop")
    w, at = _whoosh_to(rng, lead, lo=300.0, hi=4500.0, travel=travel, body=0.15, sharp=0.35)
    p, _ = part("pop", rng, pitch=pitch)
    return d.finish(d.layer([(w, at, -16 + 12 * swish), (p, lead, 0)]), fade_in=0.004, fade_out=0.02), {"pop": lead}


def _whoosh_to(rng, lead, **p):
    """A whoosh whose loudest point is `lead` seconds in."""
    peak = 0.78
    seconds = lead / (0.9 * peak)                              # the whoosh recipe puts its loudest point at 0.9 * peak * seconds
    w, marks = part("whoosh", rng, seconds=seconds, peak=peak, **p)
    shift = secs(lead) - secs(marks["peak"])
    if shift < 0:
        return d.fade(w[-shift:], 0.004, 0), 0.0
    return w, shift / SR


@recipe("compound", "The hit's own tail played backwards, sucking in to the hit itself.",
        "A harder, more unnatural lead-in than a riser: horror, tech, trailers, a dramatic word on screen. "
        "Short lead (0.3-0.6) reads as a 'suck-in'; long (1-2 s) as a swell.",
        sync=("the cut or the frame the thing lands", ON_MARK),
        lead=(0.8, "seconds of reverse swell before the hit (0.2-3)"),
        weight=(0.7, "size of the hit (0-1)"),
        tail=(2.0, "seconds of reverb after the hit"),
        bright=(0.5, "brightness of the hit and the swell (0 dull, 1 sharp)"),
        root=(45.0, "pitch of the sub (35-70)"),
        boom=(1.0, "1 = a slam with a held low rumble; 0 = a struck hit with a pitch drop"))
def swell_hit(rng, lead, weight, tail, bright, root, boom):
    _need(lead, 0.15, "swell_hit")
    h, _ = part("impact", rng, weight=weight, tail=tail, bright=bright, punch=0.6, root=root, boom=boom)
    src, _ = part("impact", rng, weight=weight, tail=max(tail, lead * 1.6, 1.0), bright=bright, punch=0.6, root=root, boom=boom)
    back = d.hp(src[secs(0.03):secs(0.03) + secs(lead)][::-1], 110, 2)        # skip the attack; keep the sub out of the swell
    m = len(back)
    back = d.fade(back * (np.linspace(0.0, 1.0, m) ** 1.5)[:, None], 0.02, 0.003)
    back, at = _ending_at(back * d.db(LEVELS["impact"] - 4.0 - d.loudest(back)), lead)
    return d.finish(d.layer([(back, at, 0), (h, lead, 0)]), fade_in=0.005, fade_out=min(0.4, tail * 0.3)), {"hit": lead}


@recipe("compound", "A rising chime with a little sparkle, and a soft thud under it if wanted: 'here it is'.",
        "The result, the finished thing, a before/after, a prize. Friendlier than an impact. `lead` adds a short airy "
        "swell before it. Tune root to the music.",
        sync=("the first frame the result is visible", ON_MARK + " With lead=0 the mark is the start of the file."),
        lead=(0.0, "seconds of airy swell before the reveal (0 = none, 0.4-1.5)"),
        root=(880.0, "first note of the chime in Hz or a note name"),
        pattern=("fifth", "the chime: major, fifth, octave or arp"),
        weight=(0.0, "size of the thud under it (0 = none, 1 = big)"),
        glitter=(0.3, "level of the sparkle (0 = none, 1 = lots)"),
        seconds=(1.4, "how long the sparkle lasts"))
def reveal(rng, lead, root, pattern, weight, glitter, seconds):
    parts = []
    if lead > 0:
        _need(lead, 0.3, "reveal")
        r, at = _build(rng, lead, air=0.8, tone=0.0)
        parts.append((r, at, -8))
    c, _ = part("chime", rng, root=root, pattern=pattern)
    parts.append((c, lead, 0))
    if weight > 0:
        k, _ = part("impact", rng, weight=weight, bright=0.35, punch=0.35, tail=0.7)
        parts.append((k, lead, -14 + 8 * weight))
    if glitter > 0:
        s, _ = part("sparkle", rng, seconds=seconds, root=_low(root * 4.0, 2400.0))
        parts.append((s, lead + 0.04, -14 + 12 * glitter))
    return d.finish(d.layer(parts), fade_in=0.004, fade_out=0.25, tail_db=-50.0), {"reveal": lead}


@recipe("compound", "A logo sting: a short swell into a chord with a sub under it; sparkle on top if wanted.",
        "The channel or brand ident, the same file in every video. Tune root and chord to the brand's music. "
        "The logo should finish forming on the mark.",
        sync=("the frame the logo is fully formed", ON_MARK),
        lead=(0.5, "seconds of swell before the chord (0 = none, 0.3-1.5); match the logo's animation"),
        root=(110.0, "root note in Hz or a note name"),
        chord=("minor", "minor, major, fifth, dim or octave"),
        seconds=(2.2, "length of the chord"),
        sub=(0.8, "level of the sub drop under the chord (0 = none, 1 = heavy)"),
        glitter=(0.0, "level of the sparkle (0 = none, 1 = lots)"))
def logo_sting(rng, lead, root, chord, seconds, sub, glitter):
    parts = []
    if lead > 0:
        _need(lead, 0.3, "logo_sting")
        r, at = _build(rng, lead, air=0.6, tone=0.3, root=root)
        parts.append((r, at, -6))
    c, _ = part("stinger", rng, root=root, chord=chord, seconds=seconds)
    parts.append((c, lead, 0))
    if sub > 0:
        s, _ = part("sub_drop", rng, seconds=min(seconds, 1.8), start=_low(root, 110.0), end=_low(root, 45.0))
        parts.append((s, lead, -12 + 12 * sub))
    if glitter > 0:
        g, _ = part("sparkle", rng, seconds=min(seconds * 0.6, 1.5), root=_low(root * 16.0, 2400.0))
        parts.append((g, lead + 0.03, -16 + 12 * glitter))
    return d.finish(d.layer(parts), fade_in=0.004, fade_out=0.4), {"hit": lead}


# ================================================================ runs: many small sounds on exact times
def _times(text, count, gap):
    if not str(text).strip():
        return [i * gap for i in range(int(count))]
    try:
        t = sorted(float(v) for v in str(text).split(","))
    except ValueError:
        raise ValueError("times is a comma-separated list of seconds, e.g. times=0,0.4,0.95") from None
    return [v - t[0] for v in t]


@recipe("compound", "A run of pops, each a step higher: one per item, on exact times.",
        "List items, bullet points, icons or steps appearing one after another. Give `times` the moment each item appears "
        "(seconds, as they are on the timeline) and every pop lands on its item; the first pop is the sync point.",
        sync=("the first frame the first item is visible", "Start the file on the first item. Every later pop is at its own mark "
              "(pop2, pop3, ...), the same distance after the first as the items are on screen."),
        count=(3, "number of pops, when `times` is not given"),
        gap=(0.3, "seconds between pops, when `times` is not given"),
        times=("", "exact times of the items, comma-separated seconds (e.g. times=4.2,4.7,5.1,6.0); overrides count and gap"),
        pitch=(440.0, "pitch of the first pop in Hz or a note"),
        step=(2.0, "semitones each pop rises above the last (0 = all the same, 2 = a scale, 4 or 5 = bigger steps)"))
def pop_run(rng, count, gap, times, pitch, step):
    at = _times(times, count, gap)
    if not at:
        raise ValueError("pop_run: nothing to play")
    parts = [(part("pop", rng, pitch=pitch * 2.0 ** (i * step / 12.0))[0], t, 0) for i, t in enumerate(at)]
    return d.finish(d.layer(parts), fade_out=0.01), {f"pop{i + 1}": t for i, t in enumerate(at)}


@recipe("compound", "A burst of typing: key ticks with human timing, ending on a heavier key.",
        "Text typing itself onto the screen, a search box, a terminal, a chat message. Set `seconds` to how long the text "
        "takes to appear, so the sound stops when the text does; the last key is the 'enter'.",
        sync=("the first character appearing", "Start the file on the first character. The `enter` mark is the last key: put the text's "
              "last character (or the result appearing) there. Set seconds = that time minus the first character's time."),
        seconds=(1.5, "time from the first key to the last, exactly"),
        keys=(0, "number of key presses; 0 = work it out from `rate`. Use the number of characters for short text"),
        rate=(16.0, "keys per second when `keys` is 0 (7 careful, 11 fluent, 16 very fast)"),
        human=(0.5, "unevenness of the timing (0 = machine, 1 = hesitant)"),
        enter=(False, "end on a lower, heavier key"),
        pitch=(850.0, "thock pitch (350 deep mechanical keyboard, 900 thin laptop)"))
def typing(rng, seconds, keys, rate, human, enter, pitch):
    n = int(keys) if keys else max(2, int(round(rate * seconds)))
    if n < 2:
        raise ValueError("typing: needs at least 2 keys")
    slots = rng.uniform(1.0 - 0.6 * human, 1.0 + 0.6 * human, n - 1)
    slots[rng.random(n - 1) < 0.14 * human] *= 2.2                       # the odd hesitation between words
    at = np.concatenate([[0.0], np.cumsum(slots)])
    at = at / at[-1] * seconds                                           # first key at 0, last key exactly at `seconds`
    parts = []
    for i, t in enumerate(at):
        last = enter and i == n - 1
        k, _ = part("tick", rng, pitch=pitch * (0.62 if last else 1.0), clack=0.8 if last else rng.uniform(0.4, 0.75))
        parts.append((d.pan(d.mono(k), rng.uniform(-0.25, 0.25)), float(t), 3.0 if last else rng.uniform(-5.0, 0.0)))
    return d.finish(d.layer(parts), fade_out=0.008), {"start": 0.0, "enter": float(seconds)}


@recipe("compound", "Blips that speed up and climb, landing on a chime: a number counting up to its result.",
        "A counter, a price, a score or a progress bar running up to its final value. The chime is the number stopping.",
        sync=("the frame the number stops", "The `land` mark is the chime. Start the file when the number starts counting and set "
              "`seconds` to how long it counts, so the chime lands on the final value."),
        seconds=(1.5, "time the count runs before it lands, exactly"),
        root=(440.0, "pitch of the first blip in Hz or a note; the chime lands an octave up, in the same key"),
        rate=(12.0, "blips per second at the start; it doubles by the end"),
        climb=(12.0, "semitones the blips rise over the count"),
        land=("fifth", "the chime it lands on: major, fifth, octave or arp; 'none' for no chime"))
def count_up(rng, seconds, root, rate, climb, land):
    _need(seconds, 0.3, "count_up")
    at, t = [], 0.0
    while t < seconds - 0.04:
        at.append(t)
        t += 1.0 / (rate * (1.0 + t / seconds))
    parts = [(part("pop", rng, pitch=root * 2.0 ** (climb * t / seconds / 12.0), seconds=0.045)[0], t, -6 + 4 * t / seconds) for t in at]
    if land != "none":
        parts.append((part("chime", rng, root=root * 2.0, pattern=land, ring=0.5)[0], seconds, 0))
    return d.finish(d.layer(parts), fade_out=0.05, tail_db=-50.0), {"land": float(seconds), "start": 0.0}


# ================================================================ more moments
@recipe("compound", "A glitch that runs up to a cut and stops dead on it.",
        "A hard, digital scene change; tech, AI and gaming videos; a 'system error' moment. Keep it short: "
        "three or four frames. The silence after the cut is part of the effect; a stutter after it was rejected by ear.",
        sync=("the cut", ON_MARK),
        lead=(0.12, "seconds of glitch before the cut (0.05-0.4)"),
        pitch=(440.0, "centre pitch of the glitch tones in Hz or a note"),
        crush=(0.6, "bit-crush amount (0 clean, 1 very lo-fi)"))
def glitch_cut(rng, lead, pitch, crush):
    _need(lead, 0.03, "glitch_cut")
    g, _ = part("glitch", rng, seconds=lead, pitch=pitch, crush=crush)
    g, at = _ending_at(g, lead)
    return d.finish(d.pad_to(d.layer([(g, at, 0)]), secs(lead)), fade_in=0.001, fade_out=0.002, tail_db=None), {"cut": lead}


@recipe("compound", "A rewind: pitch winding down fast to a dead stop, with a dull tape-deck clack on the stop if wanted.",
        "'Let's go back', replaying a moment, undoing a mistake, a flashback. The stop is where the picture freezes or the "
        "earlier moment starts playing.",
        sync=("the frame the rewinding stops", ON_MARK),
        lead=(0.8, "seconds of rewind before the stop (0.3-2.5); match the rewinding picture"),
        flutter=(28.0, "flutter rate of the tape in Hz (15 chunky, 40 buzzy)"),
        stop=(0.0, "level of the clack on the stop (0 = none, 1 = heavy)"))
def rewind(rng, lead, flutter, stop):
    _need(lead, 0.2, "rewind")
    w, _ = part("whir", rng, seconds=lead, direction=-1.0, flutter=flutter)
    w, at = _ending_at(w, lead)
    parts = [(w, at, 0)]
    if stop > 0:
        m = secs(0.09)                                        # unpitched on purpose: a pitched knock here sounded like a toy drum
        clack = d.bp(d.noise(m, rng, "white"), 500, 3200, 2) * d.perc(m, 0.0005, 0.035) \
            + d.lp(d.noise(m, rng, "brown"), 140, 2) * d.perc(m, 0.002, 0.08) * 2.0
        parts.append((d.stereo(clack) * d.db(LEVELS["tick"] - d.loudest(d.stereo(clack))), lead, -6 + 10 * stop))
    out = d.pad_to(d.layer(parts), secs(lead))                 # with no clack the file ends exactly on the stop
    return d.finish(out, fade_in=0.005, fade_out=0.03 if stop > 0 else 0.004, tail_db=-50.0 if stop > 0 else None), {"stop": lead}


@recipe("compound", "A time skip: a whir winding up with a clock ticking faster and faster, landing on a pop.",
        "'Two hours later', a sped-up process, skipping the boring part. The pop is normal speed resuming.",
        sync=("the frame normal speed resumes", "The `land` mark is the pop. Start the file where the sped-up footage starts and set "
              "`seconds` to its length."),
        seconds=(1.2, "length of the sped-up section, exactly (0.5-4)"),
        ticks=(0.6, "level of the accelerating clock ticks (0 = none, 1 = loud)"),
        land=(True, "end on a pop"))
def time_skip(rng, seconds, ticks, land):
    _need(seconds, 0.3, "time_skip")
    w, _ = part("whir", rng, seconds=seconds, direction=1.0)
    w, at = _ending_at(w, seconds)
    parts = [(w, at, 0)]
    t, i = 0.0, 0
    while ticks > 0 and t < seconds - 0.05:
        f = 1800.0 * (1.0 if i % 2 == 0 else 0.8)
        m = secs(0.05)
        parts.append((d.modal([f, f * 2.4], [0.018, 0.01], [1.0, 0.5], m, rng, hardness=0.9) * d.db(-30 + 14 * ticks), t, 0))
        t += max(0.03, 0.22 * (1.0 - t / seconds) ** 1.5)
        i += 1
    if land:
        parts.append((part("pop", rng, pitch=660.0)[0], seconds, 2))
    return d.finish(d.layer(parts), fade_in=0.005, fade_out=0.02, tail_db=-50.0), {"land": float(seconds), "start": 0.0}
