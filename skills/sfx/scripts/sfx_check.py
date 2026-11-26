"""Checks an agent can run without hearing: measurements, flags and a spectrogram picture.

A flag never rejects a sound. It says "a person should listen to this for X". Taste is not measured here.
"""
import struct
import zlib

import numpy as np
from scipy import signal

import sfx_dsp as d
from sfx_dsp import SR, secs

BANDS = (("sub", 20, 60), ("low", 60, 250), ("mid", 250, 2000), ("high", 2000, 8000), ("air", 8000, 20000))


def measure(x):
    """Numbers that describe a sound, plus flags for things worth a listen."""
    xs = d.stereo(x).astype(float)
    n = len(xs)
    m = d.mono(xs)
    peak = float(np.max(np.abs(xs))) if n else 0.0
    out = {"seconds": round(n / SR, 3), "peak_db": round(float(d.to_db(peak)), 2), "true_peak_db": round(d.true_peak_db(xs), 2),
           "level": round(d.loudest(xs), 1), "lufs": round(d.lufs(xs), 1), "rms_db": round(float(d.to_db(np.sqrt(np.mean(m * m) + 1e-20))), 1)}
    out["crest_db"] = round(out["peak_db"] - out["rms_db"], 1)              # high = spiky and percussive, low = dense
    nf = max(n, 4096)                                      # no window: a window would erase the attack of a short sound
    spec = np.abs(np.fft.rfft(m, nf)) ** 2
    f = np.fft.rfftfreq(nf, 1.0 / SR)
    total = spec.sum() + 1e-20
    out["centroid_hz"] = int(round(float((f * spec).sum() / total)))        # the 'centre of brightness'
    out["bands_pct"] = {name: round(100.0 * float(spec[(f >= lo) & (f < hi)].sum() / total), 1) for name, lo, hi in BANDS}
    if xs.shape[1] == 2 and np.std(xs[:, 0]) > 1e-9 and np.std(xs[:, 1]) > 1e-9:
        out["stereo_corr"] = round(float(np.corrcoef(xs[:, 0], xs[:, 1])[0, 1]), 2)   # 1 = mono, 0 = wide, <0 = cancels in mono
    else:
        out["stereo_corr"] = 1.0
    env = np.abs(xs).max(axis=1)                           # per channel, so out-of-phase stereo still has a shape
    if peak > 0:
        loud = np.nonzero(env > peak * d.db(-60))[0]
        out["lead_silence"] = round(loud[0] / SR, 3)
        out["tail_silence"] = round((n - 1 - loud[-1]) / SR, 3)
        hit = np.nonzero(env >= peak * 0.5)[0][0]
        out["attack_ms"] = round(1000.0 * (hit - loud[0]) / SR, 1)          # time from first sound to half of full level
        out["peak_at"] = round(float(np.argmax(env)) / max(n - 1, 1), 2)    # 0 = front-loaded hit, 1 = builds to the end

    flags = []
    if peak >= 0.999:
        runs = int(np.sum(np.abs(xs) >= 0.999))
        flags.append(f"CLIP: {runs} samples at full scale; lower the level")
    elif out["true_peak_db"] > -0.3:
        flags.append(f"NO_HEADROOM: true peak {out['true_peak_db']} dB; lossy encoders can clip it, aim for -1 dB")
    if peak == 0:
        flags.append("SILENT: the file is all zeros")
        out["flags"] = flags
        return out
    dc = float(np.max(np.abs(xs.mean(axis=0))))
    if dc > d.db(-50) and n > secs(0.25):                    # over a very short sound a mean is not an offset
        flags.append(f"DC: offset {d.to_db(dc):.0f} dB; it wastes headroom and thumps at edits")
    if np.max(np.abs(xs[0])) > peak * d.db(-40):
        flags.append("CUT_HEAD: the first sample is not at zero; it will click")
    if np.max(np.abs(xs[-1])) > peak * d.db(-40):
        flags.append("CUT_TAIL: the last sample is not at zero; it will click unless another sound covers it")
    if out.get("lead_silence", 0) > 0.03 and out.get("attack_ms", 99) < 30:   # only matters for a hit; a swell is synced by its peak
        flags.append(f"LEAD_SILENCE: {out['lead_silence']} s of silence before the sound; it will feel late against picture")
    jump = np.abs(np.diff(m))
    if len(jump) > secs(0.02):
        local = signal.fftconvolve(jump, np.ones(secs(0.01)) / secs(0.01), mode="same")   # the usual step size nearby
        inner = slice(secs(0.01), len(jump) - secs(0.01))
        ratio = jump[inner] / (local[inner] + peak * 0.005)
        if len(ratio) and ratio.max() > 12.0 and jump[inner][int(np.argmax(ratio))] > peak * 0.2:
            at = (int(np.argmax(ratio)) + secs(0.01)) / SR
            flags.append(f"CLICK: a sudden jump at {at:.3f} s; listen for a tick there")
    if out["stereo_corr"] < -0.2:
        flags.append(f"PHASE: left and right are out of phase ({out['stereo_corr']}); it will thin out or vanish on a phone speaker")
    b = out["bands_pct"]
    if b["sub"] + b["low"] > 97:
        flags.append("ALL_LOW: almost everything is under 250 Hz; laptops and phones will play close to nothing")
    out["flags"] = flags
    return out


def seam(x, crossfade=0.02):
    """For loops: how different the end is from the start. A big jump means a click or a bump at the loop point."""
    xs = d.stereo(x)
    k = secs(crossfade)
    step = float(np.max(np.abs(xs[0] - xs[-1])))
    a, b = np.sqrt(np.mean(xs[:k] ** 2)), np.sqrt(np.mean(xs[-k:] ** 2))
    return {"seam_jump_db": round(float(d.to_db(step)), 1), "level_step_db": round(float(d.to_db(b) - d.to_db(a)), 1)}


# ---------------------------------------------------------------- spectrogram picture
_MAP = np.array([[0, 0, 4], [40, 11, 84], [101, 21, 110], [159, 42, 99], [212, 72, 66], [245, 125, 21], [250, 193, 39], [252, 255, 164]], dtype=float)


TEX_BANDS = (63, 125, 250, 500, 1000, 2000, 4000, 8000, 14000)


def texture(x, start=0.0, length=8.0):
    """What makes a texture sound like itself, per octave band (after McDermott & Simoncelli 2011).

    level: the band's share of the energy, in dB. spiky: how much the band's loudness jumps about (about 0.5 for steady
    noise; 1 and over means separate events). skew: how far it is made of a few loud events over a quiet floor (under 1.5
    for steady noise; 5 and over means sparse clicks). slow: the share of the band's movement that is slower than 2 Hz
    (gusts, swells).
    """
    m = d.mono(x)[secs(start):secs(start + length)]
    if len(m) < secs(1.0):
        raise ValueError("texture: at least one second of sound is needed")
    m = m / (np.sqrt(np.mean(m ** 2)) + 1e-12)
    rows = []
    for c in TEX_BANDS:
        b = d.bp(m, c / 1.414, min(c * 1.414, SR * 0.45), 4)
        e = d.lp(np.abs(signal.hilbert(b)), 200, 2)[::SR // 1000]
        mean, sd = e.mean() + 1e-12, e.std() + 1e-12
        E = np.abs(np.fft.rfft((e - mean) * np.hanning(len(e)))) ** 2
        f = np.fft.rfftfreq(len(e), 1e-3)
        rows.append({"hz": c, "level": round(float(10 * np.log10(np.mean(b ** 2) + 1e-12)), 1), "spiky": round(float(sd / mean), 2),
                     "skew": round(float(((e - mean) ** 3).mean() / sd ** 3), 1),
                     "slow": round(float(E[(f >= 0.2) & (f < 2)].sum() / (E[f >= 0.2].sum() + 1e-20)), 2)})
    return rows


def compare(mine, ref):
    """Texture of `mine` beside a reference recording, with the differences that matter put in words."""
    a, b = texture(mine), texture(ref)
    notes = []
    for x, y in zip(a, b):
        hz, gap = x["hz"], x["level"] - y["level"]
        if max(x["level"], y["level"]) < -30:                 # too quiet in both to matter
            continue
        if abs(gap) >= 6:
            notes.append(f"{hz} Hz: {abs(gap):.0f} dB {'louder' if gap > 0 else 'quieter'} than the reference")
        if y["spiky"] >= 0.9 and x["spiky"] < 0.7:
            notes.append(f"{hz} Hz: the reference is made of separate events here; yours is steady, which is heard as static or hiss")
        if x["spiky"] >= 1.5 and y["spiky"] < 0.8:
            notes.append(f"{hz} Hz: yours is separate clicks; the reference is steady here")
        if y["slow"] - x["slow"] >= 0.25:
            notes.append(f"{hz} Hz: the reference swells slowly here (gusts); yours does not")
    return {"mine": a, "reference": b, "notes": notes}


def _png(path, rgb):
    h, w, _ = rgb.shape
    raw = b"".join(b"\x00" + rgb[r].tobytes() for r in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                 + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def spectrogram(x, path, width=900, height=320, floor_db=-80.0):
    """Write a picture of the sound: waveform on top, then frequency (low at the bottom, log scale 30 Hz-20 kHz) over time.

    Brighter = louder. Faint horizontal lines mark 100 Hz, 1 kHz and 10 kHz; faint vertical lines mark time
    (the returned legend says how far apart). Returns the legend text.
    """
    m = d.mono(d.stereo(x).astype(float))
    n = len(m)
    nfft = 2048 if n > secs(0.4) else 512
    hop = max(1, min(nfft // 4, n // width if n >= width else 1))
    m = np.concatenate([np.zeros(nfft // 2), m, np.zeros(nfft)])
    _, _, z = signal.stft(m, fs=SR, window="hann", nperseg=nfft, noverlap=nfft - hop, boundary=None, padded=False)
    mag = d.to_db(np.abs(z) + 1e-9)
    mag = mag[:, :max(1, n // hop)]
    mag -= mag.max()
    freqs = np.fft.rfftfreq(nfft, 1.0 / SR)
    rows = np.geomspace(30.0, 20000.0, height)[::-1]
    cols = np.linspace(0, mag.shape[1] - 1, width)
    by_f = np.stack([np.interp(rows, freqs, mag[:, c]) for c in range(mag.shape[1])], axis=1)
    img = np.stack([np.interp(cols, np.arange(mag.shape[1]), by_f[r]) for r in range(height)], axis=0)
    v = np.clip((img - floor_db) / -floor_db, 0.0, 1.0) * (len(_MAP) - 1)
    lo = np.floor(v).astype(int).clip(0, len(_MAP) - 2)
    rgb = _MAP[lo] + (_MAP[lo + 1] - _MAP[lo]) * (v - lo)[..., None]
    for hz in (100.0, 1000.0, 10000.0):
        r = int(np.argmin(np.abs(rows - hz)))
        rgb[r, ::4] = rgb[r, ::4] * 0.5 + 110
    seconds = n / SR
    step = next(s for s in (0.01, 0.02, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0) if seconds / s <= 12)
    for k in range(1, int(seconds / step) + 1):
        c = int(k * step / seconds * (width - 1))
        if c < width:
            rgb[::4, c] = rgb[::4, c] * 0.5 + 110
    wave_h = 70
    wav = np.full((wave_h, width, 3), 18.0)
    orig = d.mono(d.stereo(x).astype(float))
    edges = np.linspace(0, n, width + 1).astype(int)
    scale = (np.max(np.abs(orig)) + 1e-12)
    for c in range(width):
        seg = orig[edges[c]:max(edges[c + 1], edges[c] + 1)]
        a, b = seg.min() / scale, seg.max() / scale
        r0, r1 = int((1 - b) * 0.5 * (wave_h - 1)), int((1 - a) * 0.5 * (wave_h - 1))
        wav[r0:r1 + 1, c] = (120, 200, 255)
    _png(path, np.concatenate([wav, np.full((2, width, 3), 60.0), rgb]).clip(0, 255).astype(np.uint8))
    return (f"{seconds:.3f} s across {width} px; vertical lines every {step:g} s; top strip = waveform; "
            f"below: 30 Hz (bottom) to 20 kHz (top), log scale, dotted lines at 100 Hz, 1 kHz, 10 kHz; "
            f"colour = level, black {floor_db:.0f} dB to pale yellow 0 dB (relative to the loudest point)")
