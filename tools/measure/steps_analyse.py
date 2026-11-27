# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "scipy"]
# ///
"""Measure footsteps in reference sounds: find each step and store its loudness in 32 bands every 2.5 ms.

  uv run tools/measure/steps_analyse.py out.npz wood=walk1.wav,walk2.wav concrete=walk3.wav

Each name gets three arrays in out.npz: `name` (steps x 32 bands x time, the background removed), `name_gap` (the median
time between steps, in seconds) and `name_floor` (the level of the background in each band). `edges` holds the 33 band
edges in Hz. No audio is stored: only how loud each band is over time.
"""
import os, sys
for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"): os.environ.setdefault(k, "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "skills", "sfx", "scripts"))
import numpy as np
from scipy import signal
import sfx_dsp as d

SR, HOP = d.SR, 120                                  # an envelope value every 2.5 ms
EDGES = np.geomspace(45.0, 18000.0, 33)             # 32 bands


def bands(x):
    """Loudness of each band over time: band-pass, take the envelope, smooth it only as much as the band's pitch needs."""
    rows = []
    for a, b in zip(EDGES[:-1], EDGES[1:]):
        y = d.bp(x, a, b, 2)
        e = np.abs(signal.hilbert(y))
        e = d.lp(e, min(180.0, max(a / 2.0, 25.0)), 1)
        rows.append(np.maximum(e[::HOP], 0.0))
    return np.stack(rows), None


out, store = sys.argv[1], {}
for spec in sys.argv[2:]:
    name, files = spec.split("=")
    steps, gaps, floors = [], [], []
    for path in files.split(","):
        x = d.mono(d.read_audio(path))
        x = x / (np.abs(x).max() + 1e-9)
        e = d.lp(np.abs(signal.hilbert(d.hp(x, 80, 2))), 20, 2)
        floor = np.percentile(e, 20)
        pk, _ = signal.find_peaks(e, height=floor + 0.25 * (e.max() - floor), distance=int(0.3 * SR), prominence=0.15 * (e.max() - floor))
        # the onset is where the envelope first climbs out of the floor before each peak
        ons = []
        for p in pk:
            i = p
            while i > 0 and e[i] > floor + 0.08 * (e[p] - floor) and p - i < int(0.25 * SR):
                i -= 1
            ons.append(i)
        gaps += list(np.diff(ons) / SR)
        floor_b = np.percentile(bands(x)[0], 15, axis=1)
        for a, b in zip(ons, ons[1:] + [len(x)]):
            seg = x[max(a - int(0.02 * SR), 0):min(b - int(0.02 * SR), a + int(0.75 * SR))]
            if len(seg) < int(0.12 * SR):
                continue
            B, _ = bands(seg)
            steps.append(np.maximum(B - floor_b[:, None], 0.0))             # the steady background is stored separately, below
        floors.append(floor_b)
    n = max(s.shape[1] for s in steps)
    arr = np.zeros((len(steps), 32, n), dtype=np.float32)
    for i, s in enumerate(steps):
        arr[i, :, :s.shape[1]] = s
    store[name] = arr
    store[name + "_gap"] = np.array([np.median(gaps)], dtype=np.float32)
    store[name + "_floor"] = np.mean(floors, axis=0).astype(np.float32)     # the place the steps were recorded in: level per band
    arr = arr.astype(np.float16); store[name] = arr
    print(f"{name}: {len(steps)} steps, up to {n * HOP / SR * 1000:.0f} ms, median gap {np.median(gaps) * 1000:.0f} ms")
np.savez_compressed(out, edges=EDGES.astype(np.float32), **store)
print("wrote", out, os.path.getsize(out), "bytes")
