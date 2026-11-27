# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "scipy"]
# ///
"""Measure a steady texture (a stream) in reference sounds: the loudness of 32 bands every 5 ms over each whole take.

  uv run tools/measure/texture_analyse.py out.npz stream=take1.wav,take2.wav,take3.wav

`name` in out.npz is takes x 32 bands x time, cut to the shortest take; `edges` holds the 33 band edges in Hz.
No audio is stored: only how loud each band is over time.
"""
import os, sys
for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"): os.environ.setdefault(k, "1")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "skills", "sfx", "scripts"))
import numpy as np
from scipy import signal
import sfx_dsp as d
SR, HOP = d.SR, 240
EDGES = np.geomspace(45.0, 18000.0, 33)
out, store = sys.argv[1], {}
for spec in sys.argv[2:]:
    name, files = spec.split("=")
    takes = []
    for path in files.split(","):
        x = d.mono(d.read_audio(path)); x = x / (np.sqrt(np.mean(x ** 2)) + 1e-9)
        rows = []
        for a, b in zip(EDGES[:-1], EDGES[1:]):
            e = d.lp(np.abs(signal.hilbert(d.bp(x, a, b, 2))), min(120.0, max(a / 2.0, 25.0)), 1)
            rows.append(np.maximum(e[::HOP], 0.0))
        takes.append(np.stack(rows)[:, 40:-40])
    n = min(t.shape[1] for t in takes)
    store[name] = np.stack([t[:, :n] for t in takes]).astype(np.float16)
    print(name, store[name].shape)
np.savez_compressed(out, edges=EDGES.astype(np.float32), **store)
print("wrote", out, os.path.getsize(out), "bytes")
