#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy"]
# ///
"""Make and reshape sound effects with code. No keys, no models, no network.

  uv run sfx.py list                               every recipe and transform, with when to use it
  uv run sfx.py list riser                         one entry in full, with its parameters
  uv run sfx.py make riser seconds=2 root=A2       render a recipe (parameters as name=value)
  uv run sfx.py make tick --variations 6 --vary 0.15   six different takes of the same sound
  uv run sfx.py make riser_hit lead=1.5            a compound: the hit is exactly 1.5 s into the file
  uv run sfx.py lay cues.json                      put sounds on a timeline, each sync point on its event
  uv run sfx.py fx boom_from door.wav drop=-18     transform any sound file
  uv run sfx.py check sfx/*.wav                    measurements and flags, no listening needed
  uv run sfx.py spec sfx/riser_v001.wav            a spectrogram picture an agent can read
  uv run sfx.py compare mine.wav real.mp3           how a made texture differs from a real recording
  uv run sfx.py audition sfx/                      a local page to listen, keep and kill
  uv run sfx.py find door slam                     free sounds on the web (no key): a CC0 kit and Wikimedia Commons
  uv run sfx.py fetch kit:whoosh-fast-hard         download one, with its source and licence in a sidecar

Output goes to ./sfx/ (or --out) as name_v001.wav with a name_v001.json sidecar. Nothing is ever overwritten.
"""
import os

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):   # one thread: the maths here is small, and threads made it
    os.environ.setdefault(_v, "1")                                          # 4x slower while using every core of a shared machine
import sys

sys.dont_write_bytecode = True

import argparse  # noqa: E402
import base64  # noqa: E402
import html  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sfx_check  # noqa: E402
import sfx_compound  # noqa: E402,F401  (registers the compound recipes)
import sfx_dsp as d  # noqa: E402
import sfx_fx  # noqa: E402
import sfx_recipes  # noqa: E402
import sfx_sources  # noqa: E402

VERSION = "0.2"
TIMING = {"seconds", "lead", "gap", "peak", "drop", "after", "bpm", "slide"}   # --vary never touches these: a take must keep its timing


def die(msg):
    sys.exit(f"sfx: {msg}")


def params(pairs):
    out = {}
    for p in pairs:
        if "=" not in p:
            die(f"parameters are written name=value; got {p!r}")
        k, v = p.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def next_path(out_dir, name):
    out_dir.mkdir(parents=True, exist_ok=True)
    used = [int(m[1]) for f in out_dir.glob(f"{name}_v*.wav") if (m := re.fullmatch(rf"{re.escape(name)}_v(\d+)", f.stem))]
    return out_dir / f"{name}_v{max(used, default=0) + 1:03d}.wav"


def save(x, out_dir, name, info, args):
    if args.mono:
        x = d.mono(x)
    own = info.pop("_level", None)
    target = own if args.level is None else (None if args.level == "peak" else float(args.level))
    if target is not None:
        x = x * d.db(target - d.loudest(x))                   # level by how loud it hits, so sounds sit together
    tp = d.true_peak_db(x)
    if target is None or tp > args.peak:
        x = x * d.db(args.peak - tp)                          # never above the true-peak ceiling
    path = next_path(out_dir, name)
    d.write_wav(path, x, args.bits)
    m = sfx_check.measure(x)
    if info.get("loops"):                                     # a loop starts and ends mid-sound on purpose; what matters is the seam
        m["flags"] = [f for f in m["flags"] if not f.startswith(("CUT_HEAD", "CUT_TAIL"))]
        m.update(sfx_check.seam(x))
    if args.group:
        info = {**info, "group": args.group}
    side = {"file": path.name, **info, "made": datetime.now(timezone.utc).isoformat(timespec="seconds"), "tool": f"sfx {VERSION}", "check": m}
    with open(path.with_suffix(".json"), "x") as fh:
        json.dump(side, fh, indent=1)
    if args.spec:
        sfx_check.spectrogram(x, path.with_suffix(".spec.png"))
    print(f"{path}  {m['seconds']} s  level {m['level']} LUFS  true peak {m['true_peak_db']} dB  centroid {m['centroid_hz']} Hz")
    if "sync" in info:
        others = "".join(f", {k} {v:.3f}" for k, v in list(info["marks"].items())[1:])
        print(f"  sync: {info['sync']['at']:.3f} s into the file meets {info['sync']['meets']}{others}")
    for f in m["flags"]:
        print(f"  ! {f}")
    return path


def vary(spec_params, given, frac, rng):
    """Nudge every numeric parameter the caller did not set, so each variation is a different take, not a copy."""
    out = dict(given)
    for k, (default, _) in spec_params.items():
        if k not in given and k not in TIMING and isinstance(default, float) and default != 0:
            out[k] = default * (1.0 + rng.uniform(-frac, frac))
    return out


def cmd_list(args):
    reg = {**{k: ("recipe", v) for k, v in sfx_recipes.RECIPES.items()}, **{k: ("transform", v) for k, v in sfx_fx.TRANSFORMS.items()}}
    if args.name:
        if args.name not in reg:
            die(f"nothing named {args.name!r}")
        kind, s = reg[args.name]
        lv = f"  Level: {s['level']} LUFS (loudest 150 ms)\n" if s.get("level") is not None else "  Level: keeps the loudness of its input\n"
        sy = f"  Sync: meets {s['sync']['meets']}. {s['sync']['how']}\n" if "sync" in s else ""
        print(f"{args.name}  ({kind}{', ' + s['family'] if 'family' in s else ''})\n  {s['about']}\n  Use: {s['use']}\n{sy}{lv}  Parameters:")
        for k, (default, what) in s["params"].items():
            print(f"    {k}={default!r}  {what}")
        return
    if args.json:
        print(json.dumps({k: {"kind": kind, **{a: b for a, b in s.items() if a != "fn"}} for k, (kind, s) in reg.items()}, indent=1))
        return
    for title, pick in (("RECIPES (make)", lambda kd, s: kd == "recipe" and s["family"] != "compound"),
                        ("COMPOUNDS (make): several sounds on one timeline, built around a sync point", lambda kd, s: s.get("family") == "compound"),
                        ("TRANSFORMS (fx)", lambda kd, s: kd == "transform")):
        print(title)
        for k, (kd, s) in reg.items():
            if pick(kd, s):
                print(f"  {k:<13} {s['about']}")
    print("\n`sfx.py list <name>` shows when to use it and its parameters.")


def cmd_make(args):
    if args.recipe not in sfx_recipes.RECIPES:
        die(f"no recipe named {args.recipe!r}; run `sfx.py list`")
    spec, given = sfx_recipes.RECIPES[args.recipe], params(args.params)
    for i in range(args.variations):
        seed = args.seed + i
        p = vary(spec["params"], given, args.vary, np.random.default_rng(seed + 7919)) if args.vary and i > 0 else given
        try:
            x, used, marks, events = sfx_recipes.render_events(args.recipe, seed=seed, **p)
        except (KeyError, ValueError) as e:
            die(str(e).strip("'\""))
        sync = {"at": next(iter(marks.values())), **spec["sync"]}
        save(x, Path(args.out), args.name or args.recipe,
             {"recipe": args.recipe, "params": used, "seed": seed, "sync": sync, "marks": marks, "_level": spec["level"],
              **({"loops": True} if spec["family"] == "bed" else {}), **({"events": events} if args.events else {})}, args)


def cmd_lay(args):
    """Put sounds on one timeline so that each one's sync point lands on its event, and write the result as one file."""
    sheet_path = Path(args.sheet)
    try:
        sheet = json.loads(sheet_path.read_text())
    except (OSError, json.JSONDecodeError) as e:
        die(f"cannot read the cue sheet: {e}")
    fps, cues = sheet.get("fps"), sheet.get("cues") or []
    if not cues:
        die('the cue sheet has no "cues"')
    placed = []
    for i, c in enumerate(cues, 1):
        unknown = set(c) - {"file", "at", "frame", "mark", "gain", "note"}
        if unknown or "file" not in c or ("at" in c) == ("frame" in c):
            die(f'cue {i}: needs "file" and one of "at" (seconds) or "frame"; optional "mark", "gain", "note"' + (f"; unknown {sorted(unknown)}" if unknown else ""))
        if "frame" in c and not fps:
            die(f'cue {i}: "frame" needs "fps" at the top of the sheet')
        f = (sheet_path.parent / c["file"]).resolve()
        try:
            x = d.stereo(d.read_audio(f))
        except (FileNotFoundError, RuntimeError) as e:
            die(f"cue {i}: {e}")
        side = json.loads(f.with_suffix(".json").read_text()) if f.with_suffix(".json").exists() else {}
        marks = side.get("marks", {})
        if "mark" in c:
            if c["mark"] not in marks:
                die(f"cue {i}: {f.name} has no mark {c['mark']!r}; it has {sorted(marks) or 'none'}")
            name, m = c["mark"], marks[c["mark"]]
        elif "sync" in side and "at" in side["sync"]:
            name, m = next(iter(marks), "sync"), side["sync"]["at"]
        else:
            name, m = "start (no sync point recorded)", 0.0
        at = c["frame"] / fps if "frame" in c else float(c["at"])
        start = at - m
        if start < -0.5 / d.SR:
            die(f"cue {i}: {f.name} would have to start {-start:.3f} s before the timeline does (its {name} is {m:.3f} s in, "
                f"the event is at {at:.3f} s). Render it with a shorter lead.")
        placed.append({"file": c["file"], "mark": name, "mark_at": round(m, 6), "event_at": round(at, 6), "starts": round(max(start, 0.0), 6),
                       "ends": round(max(start, 0.0) + len(x) / d.SR, 6), "gain": float(c.get("gain", 0.0)), "note": c.get("note", ""), "_x": x})
    out = d.layer([(p["_x"], p["starts"], p["gain"]) for p in placed])
    if sheet.get("seconds"):
        want = d.secs(float(sheet["seconds"]))
        if want < len(out):
            die(f"the sheet says the piece is {sheet['seconds']} s, but the sounds run to {len(out) / d.SR:.3f} s")
        out = np.concatenate([out, np.zeros((want - len(out), 2))])
    tp = d.true_peak_db(out)
    lowered = 0.0
    if tp > args.peak:                                       # sounds stacked on the same moment can add up past the ceiling
        lowered = args.peak - tp
        out = out * d.db(lowered)
    path = next_path(Path(args.out), args.name or sheet_path.stem)
    d.write_wav(path, out, args.bits)
    for p in placed:
        del p["_x"]
    with open(path.with_suffix(".json"), "x") as fh:
        json.dump({"file": path.name, "sheet": str(sheet_path), "fps": fps, "seconds": round(len(out) / d.SR, 6), "lowered_db": round(lowered, 2),
                   "cues": placed, "made": datetime.now(timezone.utc).isoformat(timespec="seconds"), "tool": f"sfx {VERSION}"}, fh, indent=1)
    print(f"{path}  {len(out) / d.SR:.3f} s  put it at 0:00 on the timeline")
    for p in sorted(placed, key=lambda p: p["event_at"]):
        fr = f" (frame {p['event_at'] * fps:.2f})" if fps else ""
        print(f"  {p['event_at']:8.3f} s{fr}  {p['mark']} of {p['file']}  file starts {p['starts']:.3f}, ends {p['ends']:.3f}  {p['note']}")
        if fps and abs(p["event_at"] * fps - round(p["event_at"] * fps)) > 0.02:
            print(f"    ! not on a frame at {fps} fps; the nearest frames are {int(p['event_at'] * fps) / fps:.3f} and {(int(p['event_at'] * fps) + 1) / fps:.3f} s")
    if lowered:
        print(f"  ! the whole track was lowered {-lowered:.1f} dB to stay under the {args.peak} dB ceiling; sounds are stacked somewhere")


def cmd_fx(args):
    src = Path(args.input)
    try:
        x = d.read_audio(src)
    except (FileNotFoundError, RuntimeError) as e:
        die(str(e))
    given = params(args.params)
    for i in range(args.variations):
        try:
            y, used = sfx_fx.apply(args.transform, x, seed=args.seed + i, **given)
        except (KeyError, ValueError, FileNotFoundError, RuntimeError) as e:
            die(str(e).strip("'\""))
        stem = re.sub(r"_v\d+$", "", src.stem)
        level = sfx_fx.TRANSFORMS[args.transform]["level"]
        save(y, Path(args.out), args.name or f"{stem}_{args.transform}",
             {"transform": args.transform, "params": used, "seed": args.seed + i, "source": str(src),
              "_level": level if level is not None else d.loudest(x)}, args)


def cmd_check(args):
    for f in args.files:
        try:
            x = d.read_audio(f)
        except (FileNotFoundError, RuntimeError) as e:
            die(str(e))
        m = sfx_check.measure(x)
        if args.loop:
            m.update(sfx_check.seam(x))
        flags = m.pop("flags")
        print(f"{f}\n  {json.dumps(m)}")
        for fl in flags:
            print(f"  ! {fl}")


def cmd_compare(args):
    try:
        mine, ref = d.read_audio(args.mine), d.read_audio(args.reference)
        r = sfx_check.compare(mine[d.secs(args.at):], ref[d.secs(args.ref_at):])
    except (FileNotFoundError, RuntimeError, ValueError) as e:
        die(str(e))
    if args.json:
        print(json.dumps(r))
        return
    print(f"{'band':>6}   level dB (mine / ref)   spiky (mine / ref)   skew (mine / ref)   slow (mine / ref)")
    for a, b in zip(r["mine"], r["reference"]):
        print(f"{a['hz']:>6}   {a['level']:>8} / {b['level']:<8}    {a['spiky']:>6} / {b['spiky']:<6}     {a['skew']:>6} / {b['skew']:<6}    {a['slow']:>5} / {b['slow']:<5}")
    print("spiky: 0.5 = steady noise, 1+ = separate events.  skew: under 1.5 = steady, 5+ = sparse clicks.  slow: share of movement under 2 Hz.")
    for n in r["notes"]:
        print(f"  ! {n}")
    if not r["notes"]:
        print("  no large differences in these measures (this is not proof it sounds right: a person still has to listen)")


def cmd_spec(args):
    for f in args.files:
        out = Path(args.out) if args.out else Path(f).with_suffix(".spec.png")
        print(f"{out}\n  {sfx_check.spectrogram(d.read_audio(f), out)}")


def cmd_audition(args):
    folder = Path(args.folder)
    wavs = sorted(folder.glob("*.wav"))
    if not wavs:
        die(f"no .wav files in {folder}")
    rows = []
    for w in wavs:
        side = json.loads(w.with_suffix(".json").read_text()) if w.with_suffix(".json").exists() else {}
        png = w.with_suffix(".spec.png")
        if not png.exists():
            sfx_check.spectrogram(d.read_audio(w), png)
        group = side.get("group") or side.get("recipe") or side.get("transform") or side.get("source") or "other"
        chk = side.get("check", {})
        if "licence" in side:                                 # a fetched sound
            ps = side.get("about", "")
            meta = f"{side.get('seconds', '?')} s · {side.get('source')} · {side.get('licence')}"
        else:
            how = side.get("recipe") or side.get("transform") or ""
            ps = how + ": " + ", ".join(f"{k}={round(v, 3) if isinstance(v, float) else v}" for k, v in side.get("params", {}).items())
            meta = f"{chk.get('seconds', '?')} s · seed {side.get('seed', '?')}" + (f" · made from {Path(side['source']).name}" if side.get("source") else "")
        what = (sfx_recipes.RECIPES.get(how) or sfx_fx.TRANSFORMS.get(how) or {}).get("about", "") if "licence" not in side else ""
        if side.get("sync", {}).get("at") is not None:        # say what the sound is and where it must land, so the listener knows what to judge
            marks = ", ".join(f"{k} at {v:.2f} s" for k, v in side.get("marks", {}).items()) or f"sync point at {side['sync']['at']:.2f} s"
            what += f" Timing: {marks}; meets {side['sync'].get('meets', '')}."
        rows.append((group, w.name, png.name, ps, meta, chk.get("flags", []), what.strip()))
    font = base64.b64encode((HERE / "static" / "Geist_wght.ttf").read_bytes()).decode()
    body = []
    for group in dict.fromkeys(r[0] for r in rows):
        body.append(f"<h2>{html.escape(group)}</h2>")
        for _, name, png, ps, meta, flags, what in (r for r in rows if r[0] == group):
            fl = "".join(f"<div class=flag>{html.escape(f)}</div>" for f in flags)
            body.append(f"""<div class=row data-name="{html.escape(name)}"><div class=head><b>{html.escape(name)}</b><span class=meta>{html.escape(meta)}</span>
<span class=btns><button data-v=keep>Keep (K)</button><button data-v=maybe>Maybe (M)</button><button data-v=kill>Kill (X)</button></span></div>
<div class=what>{html.escape(what)}</div><div class=ps>{html.escape(ps)}</div>{fl}<audio controls preload=auto src="{html.escape(name)}"></audio>
<img loading=lazy src="{html.escape(png)}"><input class=note placeholder="note (optional)"></div>""")
    page = _PAGE.replace("__FONT__", font).replace("__TITLE__", html.escape(args.title or folder.resolve().name)).replace("__BODY__", "\n".join(body))
    out = folder / "audition.html"
    out.write_text(page)
    print(f"file://{out.resolve()}")


def cmd_find(args):
    out = []
    try:
        if args.categories:
            for k, v in sorted(sfx_sources.kit_categories(args.dir).items()):
                print(f"{k:<24} {v}")
            return
        if args.source in ("kit", "all"):
            out += sfx_sources.kit_find(args.words, args.dir, args.category)[:args.limit]
        if args.source in ("commons", "all") and args.words and not args.category:
            out += sfx_sources.commons_find(args.words, args.limit, args.max_seconds, args.free_only)
    except RuntimeError as e:
        die(str(e))
    if args.json:
        print(json.dumps(out, indent=1))
        return
    for r in out:
        print(f"{r['id']}\n    {r.get('seconds', '?')} s · {r['licence']} · {r.get('about') or r['name']}")
        if r.get("use_for"):
            print(f"    use for: {'; '.join(r['use_for'])}")
    if not out:
        print("nothing found; try other words, or `sfx.py find --categories` for what the kit holds")


def cmd_fetch(args):
    for ref in args.ids:
        try:
            path, info, new = sfx_sources.fetch(ref, args.dir, args.group)
        except RuntimeError as e:
            die(str(e))
        print(f"{path}  {'fetched' if new else 'already here'} · {info['licence']} · {info.get('author', '')} · {info['page']}")


_PAGE = """<!doctype html><meta charset=utf-8><title>__TITLE__ · audition</title>
<style>@font-face{font-family:Geist;src:url(data:font/ttf;base64,__FONT__);font-weight:100 900}
body{font-family:Geist,system-ui,sans-serif;background:#101114;color:#e6e6ea;max-width:980px;margin:24px auto;padding:0 16px 120px}
h1{font-size:20px;font-weight:600}h2{font-size:14px;letter-spacing:.08em;text-transform:uppercase;color:#8b8fa3;margin:28px 0 8px}
.row{border:1px solid #26282f;border-radius:10px;padding:12px;margin:10px 0;background:#16171c}.row.sel{border-color:#6ea8ff}
.row.keep{background:#12241a}.row.kill{background:#2a1517;opacity:.6}.row.maybe{background:#262112}
.head{display:flex;gap:12px;align-items:baseline}.meta{color:#8b8fa3;font-size:13px}.btns{margin-left:auto}
button{font:inherit;font-size:13px;background:#23252d;color:inherit;border:1px solid #343743;border-radius:6px;padding:4px 10px;cursor:pointer}
.ps{color:#8b8fa3;font-size:12px;margin:4px 0}.what{font-size:14px;margin:6px 0 2px}.flag{color:#ffb86b;font-size:13px}audio{width:100%;margin:8px 0;height:36px}
img{width:100%;border-radius:6px;display:block}.note{width:100%;box-sizing:border-box;margin-top:8px;background:#0c0d10;color:inherit;border:1px solid #26282f;border-radius:6px;padding:6px 8px;font:inherit;font-size:13px}
#bar{position:fixed;left:0;right:0;bottom:0;background:#0c0d10;border-top:1px solid #26282f;padding:10px 16px;display:flex;gap:12px;align-items:center;font-size:13px}
#help{color:#8b8fa3}</style>
<h1>__TITLE__</h1><div id=help>Space plays the selected sound. Up / Down moves. K keep, M maybe, X kill. Choices are remembered in this browser.</div>
__BODY__
<div id=bar><button id=copy>Copy verdicts</button><span id=count></span></div>
<script>
const rows=[...document.querySelectorAll('.row')],key='sfx-audition:'+location.pathname;let st={},sel=0;
try{st=JSON.parse(localStorage.getItem(key)||'{}')}catch(e){}
function save(){try{localStorage.setItem(key,JSON.stringify(st))}catch(e){}}
function paint(){rows.forEach((r,i)=>{const s=st[r.dataset.name]||{};r.className='row '+(s.v||'')+(i===sel?' sel':'');r.querySelector('.note').value=s.n||''});
const c={keep:0,maybe:0,kill:0};Object.values(st).forEach(s=>{if(s.v)c[s.v]++});count.textContent=`${c.keep} keep · ${c.maybe} maybe · ${c.kill} kill · ${rows.length} sounds`}
function set(i,v){const n=rows[i].dataset.name;st[n]=Object.assign(st[n]||{},{v:(st[n]||{}).v===v?'':v});save();paint()}
function play(i){document.querySelectorAll('audio').forEach(a=>{a.pause()});const a=rows[i].querySelector('audio');a.currentTime=0;a.play()}
function go(i){sel=Math.max(0,Math.min(rows.length-1,i));paint();rows[sel].scrollIntoView({block:'center',behavior:'smooth'})}
rows.forEach((r,i)=>{r.addEventListener('click',()=>{sel=i;paint()});r.querySelectorAll('button').forEach(b=>b.onclick=e=>{e.stopPropagation();set(i,b.dataset.v)});
r.querySelector('.note').oninput=e=>{const n=r.dataset.name;st[n]=Object.assign(st[n]||{},{n:e.target.value});save()}});
document.addEventListener('keydown',e=>{if(e.target.classList.contains('note'))return;
if(e.code==='Space'){e.preventDefault();play(sel)}else if(e.key==='ArrowDown'){e.preventDefault();go(sel+1);play(sel)}else if(e.key==='ArrowUp'){e.preventDefault();go(sel-1);play(sel)}
else if(e.key==='k')set(sel,'keep');else if(e.key==='m')set(sel,'maybe');else if(e.key==='x')set(sel,'kill')});
copy.onclick=()=>{const t=rows.map(r=>{const s=st[r.dataset.name]||{};return `${s.v||'unrated'}\\t${r.dataset.name}${s.n?'\\t'+s.n:''}`}).join('\\n');navigator.clipboard.writeText(t);copy.textContent='Copied'};
paint();
</script>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("params", nargs="*", help="name=value pairs")
        p.add_argument("--seed", type=int, default=1, help="same seed + same parameters = the same sound")
        p.add_argument("--variations", type=int, default=1, help="render this many takes (seed, seed+1, ...)")
        p.add_argument("--out", default="sfx", help="output folder (default ./sfx)")
        p.add_argument("--name", help="file name stem (default: the recipe name)")
        p.add_argument("--level", help="loudness of the loudest 150 ms in LUFS, or 'peak' for as loud as the ceiling allows "
                                       "(default: each recipe's own mix-ready level; transforms keep their input's loudness)")
        p.add_argument("--peak", type=float, default=-1.0, help="true-peak ceiling in dB (default -1)")
        p.add_argument("--mono", action="store_true", help="write mono (games often want mono for positioned sounds)")
        p.add_argument("--bits", type=int, default=24, choices=(16, 24))
        p.add_argument("--spec", action="store_true", help="also write a spectrogram picture")
        p.add_argument("--group", help="a heading for the audition page (e.g. the kind of sound being compared)")

    p = sub.add_parser("list"); p.add_argument("name", nargs="?"); p.add_argument("--json", action="store_true"); p.set_defaults(fn=cmd_list)
    p = sub.add_parser("make"); p.add_argument("recipe"); common(p)
    p.add_argument("--events", action="store_true", help="list every separate event inside the sound (each drop, crackle, chirp, pop) in the "
                   "sidecar, with its time, so a picture can be drawn to them")
    p.add_argument("--vary", type=float, default=0.0, help="with --variations: nudge unset parameters by up to this fraction (0.15 = 15%%)")
    p.set_defaults(fn=cmd_make)
    p = sub.add_parser("lay", help="put sounds on a timeline by their sync points; see references/timing.md for the cue sheet")
    p.add_argument("sheet"); p.add_argument("--out", default="sfx"); p.add_argument("--name"); p.add_argument("--peak", type=float, default=-1.0)
    p.add_argument("--bits", type=int, default=24, choices=(16, 24)); p.set_defaults(fn=cmd_lay)
    p = sub.add_parser("fx"); p.add_argument("transform"); p.add_argument("input"); common(p); p.set_defaults(fn=cmd_fx)
    p = sub.add_parser("check"); p.add_argument("files", nargs="+"); p.add_argument("--loop", action="store_true", help="also measure the loop seam"); p.set_defaults(fn=cmd_check)
    p = sub.add_parser("compare", help="texture of a made sound beside a real recording: where they differ, in numbers and words")
    p.add_argument("mine"); p.add_argument("reference"); p.add_argument("--at", type=float, default=0.0, help="start in my file, seconds")
    p.add_argument("--ref-at", type=float, default=0.0, help="start in the reference, seconds (8 s are read)"); p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_compare)
    p = sub.add_parser("spec"); p.add_argument("files", nargs="+"); p.add_argument("--out"); p.set_defaults(fn=cmd_spec)
    p = sub.add_parser("find"); p.add_argument("words", nargs="*"); p.add_argument("--source", default="all", choices=("kit", "commons", "all"))
    p.add_argument("--category", help="a kit category (see --categories)"); p.add_argument("--categories", action="store_true", help="list the kit's categories")
    p.add_argument("--limit", type=int, default=8); p.add_argument("--max-seconds", type=float, default=30.0)
    p.add_argument("--free-only", action="store_true", help="Commons: only CC0 and public-domain files")
    p.add_argument("--dir", default="sfx/sources", help="where fetched sounds and the kit catalogue live"); p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_find)
    p = sub.add_parser("fetch"); p.add_argument("ids", nargs="+"); p.add_argument("--dir", default="sfx/sources"); p.add_argument("--group"); p.set_defaults(fn=cmd_fetch)
    p = sub.add_parser("audition"); p.add_argument("folder"); p.add_argument("--title"); p.set_defaults(fn=cmd_audition)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
