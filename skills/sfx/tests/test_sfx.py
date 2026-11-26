#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["numpy", "scipy"]
# ///
"""Fast tests of the sfx suite: no network, no listening. About 20 seconds.

  uv run tests/test_sfx.py"""
import os

for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):   # one thread: the maths here is small, and threads made it
    os.environ.setdefault(_v, "1")                                          # 4x slower while using every core of a shared machine
import sys

sys.dont_write_bytecode = True

import json  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import unittest  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import sfx_check  # noqa: E402
import sfx_compound  # noqa: E402,F401
import sfx_dsp as d  # noqa: E402
import sfx_fx  # noqa: E402
import sfx_recipes  # noqa: E402
import sfx_sources  # noqa: E402

BAD = ("CLIP", "SILENT", "CUT_HEAD", "CUT_TAIL", "DC", "PHASE")


def tone(seconds=0.5, hz=440.0, amp=0.5):
    return d.fade(d.sine(hz, d.secs(seconds)) * amp, 0.01, 0.01)


class Recipes(unittest.TestCase):
    def test_every_recipe_renders_clean_with_its_defaults(self):
        for name in sfx_recipes.RECIPES:
            with self.subTest(name):
                x, p, _ = sfx_recipes.render(name, seed=1)
                self.assertEqual(x.ndim, 2)
                self.assertEqual(x.shape[1], 2)
                self.assertTrue(np.all(np.isfinite(x)))
                self.assertLessEqual(np.max(np.abs(x)), 1.0)
                loop = sfx_recipes.RECIPES[name]["family"] == "bed"       # a loop starts and ends mid-sound on purpose
                flags = [f for f in sfx_check.measure(x)["flags"] if f.split(":")[0] in BAD and not (loop and f.startswith("CUT_"))]
                self.assertEqual(flags, [])

    def test_every_kind_of_a_many_kind_recipe_renders(self):
        kinds = {"alarm": "beep siren two_tone klaxon", "phone": "dial ring busy digits", "scifi": "zap teleport scan power_up power_down",
                 "cartoon": "boing slide_down bonk", "bed": "hum", "retro": "coin jump laser hit powerup explode blip"}
        for name, ks in kinds.items():
            for k in ks.split():
                with self.subTest(f"{name} {k}"):
                    x, _, _ = sfx_recipes.render(name, kind=k, **({"seconds": 2.0} if name == "bed" else {}))
                    self.assertTrue(np.all(np.isfinite(x)) and np.abs(x).max() > 0.1)
            with self.assertRaises(ValueError):
                sfx_recipes.render(name, kind="nope")

    def test_compare_tells_steady_noise_from_separate_events(self):
        rng = np.random.default_rng(3)
        n = d.secs(6.0)
        steady = d.hp(rng.standard_normal(n), 3000)
        clicks = np.zeros(n)
        clicks[rng.integers(0, n - 100, 40)] = 1.0
        clicks = d.hp(np.convolve(clicks, rng.standard_normal(60), mode="same"), 3000)
        t = {r["hz"]: r for r in sfx_check.texture(clicks)}
        self.assertGreater(t[8000]["spiky"], 1.5)
        self.assertLess({r["hz"]: r for r in sfx_check.texture(steady)}[8000]["spiky"], 0.7)
        notes = sfx_check.compare(steady, clicks)["notes"]
        self.assertTrue(any("static" in note for note in notes), notes)
        self.assertEqual(sfx_check.compare(steady, steady)["notes"], [])

    def test_footsteps_have_a_mark_per_step_and_refuse_unapproved_surfaces(self):
        for surface in ("wood", "concrete", "dirt"):
            x, _, marks = sfx_recipes.render("footsteps", surface=surface, steps=4)
            self.assertEqual(len(marks), 4, surface)
            self.assertGreater(np.abs(x).max(), 0.1)
        a, _, _ = sfx_recipes.render("footsteps", seed=1)
        b, _, _ = sfx_recipes.render("footsteps", seed=2)
        self.assertFalse(np.array_equal(a[:min(len(a), len(b))], b[:min(len(a), len(b))]))
        with self.assertRaises(ValueError):
            sfx_recipes.render("footsteps", surface="snow")

    def test_beds_loop_without_a_jump(self):
        for k in ("bed", "rain", "fire", "wind", "room", "crickets", "ocean", "vinyl", "stream"):
            x, _, _ = sfx_recipes.render(k, seconds=3.0)
            self.assertEqual(len(x), d.secs(3.0), k)
            typical = np.percentile(np.abs(np.diff(x[:, 0])), 99.9)
            self.assertLessEqual(abs(x[0, 0] - x[-1, 0]), 2.0 * typical + 1e-4, k)   # the step across the seam is an ordinary step

    def test_same_seed_same_sound_and_a_new_seed_differs(self):
        for name in ("riser", "impact", "whoosh", "tick", "sparkle"):
            a, _, _ = sfx_recipes.render(name, seed=5)
            b, _, _ = sfx_recipes.render(name, seed=5)
            c, _, _ = sfx_recipes.render(name, seed=6)
            self.assertTrue(np.array_equal(a, b), name)
            self.assertFalse(a.shape == c.shape and np.allclose(a, c), name)

    def test_parameters_change_the_sound_and_typos_are_errors(self):
        short, _, _ = sfx_recipes.render("riser", seconds=1.0, tail=0)
        self.assertEqual(len(short), d.SR)                    # tail=0 ends exactly on time, for a cut
        with self.assertRaises(KeyError) as e:
            sfx_recipes.render("riser", secnods=2)
        self.assertIn("secnods", str(e.exception))
        with self.assertRaises(KeyError):
            sfx_recipes.render("no_such_sound")
        with self.assertRaises(ValueError):
            sfx_recipes.render("chime", pattern="jazz")

    def test_pitches_take_note_names(self):
        self.assertAlmostEqual(sfx_recipes.hz("A4"), 440.0)
        self.assertAlmostEqual(sfx_recipes.hz("C#3"), 138.591, places=2)
        self.assertAlmostEqual(sfx_recipes.hz("Eb5"), 622.254, places=2)
        self.assertEqual(sfx_recipes.coerce(110.0, "A2"), 110.0)
        self.assertEqual(sfx_recipes.coerce(2, "3"), 3)
        a, _, _ = sfx_recipes.render("chime", root="C6")
        b, _, _ = sfx_recipes.render("chime", root=1046.502)
        self.assertTrue(np.allclose(a, b, atol=1e-4))

    def test_every_recipe_says_what_it_is_for_and_how_loud_it_sits(self):
        for name, spec in sfx_recipes.RECIPES.items():
            self.assertGreater(len(spec["use"]), 40, name)
            self.assertIsInstance(spec["level"], float, name)
            for k, v in spec["params"].items():
                self.assertEqual(len(v), 2, f"{name}.{k}")


class Transforms(unittest.TestCase):
    def test_every_transform_runs_on_a_plain_sound(self):
        src, _, _ = sfx_recipes.render("impact", seed=2, tail=0.5)
        with tempfile.TemporaryDirectory() as tmp:
            stamp = Path(tmp) / "stamp.wav"
            d.write_wav(stamp, sfx_recipes.render("click")[0])
            for name in sfx_fx.TRANSFORMS:
                with self.subTest(name):
                    extra = {"stamp": str(stamp)} if name == "stamp" else {}
                    if name in ("drone_from", "cloud"):
                        extra["seconds"] = 1.5
                    y, _ = sfx_fx.apply(name, src, seed=1, **extra)
                    self.assertEqual(y.ndim, 2)
                    self.assertTrue(np.all(np.isfinite(y)))
                    self.assertGreater(np.max(np.abs(y)), 0.01)

    def test_reverse_and_pitch_do_what_they_say(self):
        x = np.concatenate([tone(0.2, 440), np.zeros(d.secs(0.2))])
        r, _ = sfx_fx.apply("reverse", x)
        self.assertGreater(np.argmax(np.abs(d.mono(r))), len(r) // 2)        # the sound is now at the end
        down, _ = sfx_fx.apply("pitch", tone(0.5, 880), semitones=-12)
        self.assertAlmostEqual(len(down) / d.secs(0.5), 2.0, delta=0.05)     # an octave down is twice as long
        self.assertAlmostEqual(sfx_check.measure(down)["centroid_hz"], 440, delta=25)

    def test_a_riser_made_from_a_hit_still_builds_to_the_end(self):
        hit, _, _ = sfx_recipes.render("impact", seed=3, tail=0.4)
        y, _ = sfx_fx.apply("riser_from", hit, seconds=1.5)
        self.assertGreater(sfx_check.measure(y)["peak_at"], 0.8)

    def test_loop_removes_the_seam(self):
        x = d.noise(d.secs(2.0), np.random.default_rng(1), "pink") * np.linspace(0.2, 1.0, d.secs(2.0))
        before = sfx_check.seam(x)["level_step_db"]
        y, _ = sfx_fx.apply("loop", x, crossfade=0.5)
        self.assertGreater(abs(before), 6.0)
        self.assertLess(abs(sfx_check.seam(y)["level_step_db"]), 3.0)

    def test_stamp_without_a_file_is_an_error(self):
        with self.assertRaises(ValueError):
            sfx_fx.apply("stamp", tone())


class Levels(unittest.TestCase):
    def test_loudness_matches_the_standard(self):
        x = d.stereo(d.sine(997.0, d.secs(3.0)) * 0.1)        # -20 dBFS in both channels reads about -20 LUFS
        self.assertAlmostEqual(d.lufs(x), -20.0, delta=0.4)
        self.assertAlmostEqual(d.loudest(x), -20.0, delta=0.4)

    def test_loudest_150_ms_ignores_the_silence_around_a_short_sound(self):
        hit = d.stereo(d.sine(997.0, d.secs(0.15)) * 0.1)
        padded = np.concatenate([np.zeros((d.secs(1.0), 2)), hit, np.zeros((d.secs(1.0), 2))])
        self.assertAlmostEqual(d.loudest(padded), d.loudest(hit), delta=0.5)
        self.assertLess(d.lufs(padded), -10.0)


class Checks(unittest.TestCase):
    def test_flags_point_at_real_faults(self):
        clipped = np.clip(tone(0.5, 200, 1.0) * 3.0, -1, 1)
        self.assertTrue(any(f.startswith("CLIP") for f in sfx_check.measure(clipped)["flags"]))
        chopped = d.sine(200.0, d.secs(0.5))[:d.secs(0.4) + 60] * 0.5      # stops mid-wave
        self.assertTrue(any(f.startswith("CUT_TAIL") for f in sfx_check.measure(chopped)["flags"]))
        self.assertTrue(any(f.startswith("SILENT") for f in sfx_check.measure(np.zeros(1000))["flags"]))
        late = np.concatenate([np.zeros(d.secs(0.2)), sfx_recipes.render("click")[0][:, 0]])
        self.assertTrue(any(f.startswith("LEAD_SILENCE") for f in sfx_check.measure(late)["flags"]))
        flipped = np.stack([tone(), -tone()], axis=1)
        self.assertTrue(any(f.startswith("PHASE") for f in sfx_check.measure(flipped)["flags"]))
        self.assertEqual(sfx_check.measure(d.stereo(tone()))["flags"], [])

    def test_a_short_bright_click_measures_bright(self):
        m = sfx_check.measure(sfx_recipes.render("click", pitch=3000.0, soft=0.3, body=0.4)[0])
        self.assertGreater(m["centroid_hz"], 1200)             # the attack counts, not only the tail
        self.assertLess(m["seconds"], 0.1)

    def test_spectrogram_writes_a_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "s.png"
            legend = sfx_check.spectrogram(sfx_recipes.render("whoosh")[0], out)
            self.assertEqual(out.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
            self.assertIn("1 kHz", legend)


class Timing(unittest.TestCase):
    """The sync point of a sound is where its marks say it is, to the sample."""

    def env(self, x):
        return np.abs(x).max(axis=1)

    def test_every_recipe_declares_a_sync_point_inside_the_sound(self):
        for name, spec in sfx_recipes.RECIPES.items():
            x, _, marks = sfx_recipes.render(name, seed=2)
            self.assertTrue(spec["sync"]["meets"] and spec["sync"]["how"], name)
            for k, v in marks.items():
                self.assertTrue(0.0 <= v <= len(x) / d.SR, f"{name} {k}")

    def test_riser_peak_is_its_last_sample_and_whoosh_peak_is_its_loudest_point(self):
        x, _, marks = sfx_recipes.render("riser", seconds=1.25, tail=0)
        self.assertEqual(len(x), d.secs(1.25))
        self.assertAlmostEqual(marks["peak"], 1.25, places=4)
        w, _, marks = sfx_recipes.render("whoosh", seconds=1.0, peak=0.7)
        smooth = d.lp(self.env(w), 20, 2)
        self.assertAlmostEqual(np.argmax(smooth) / d.SR, marks["peak"], delta=0.06)

    def test_compound_hit_lands_on_the_mark_after_silence(self):
        for name, mark in (("riser_hit", "hit"), ("riser_drop", "drop")):
            x, _, marks = sfx_recipes.render(name, lead=1.0, gap=0.1)
            self.assertEqual(marks[mark], 1.0)
            e, i = self.env(x), d.secs(1.0)
            quiet = e[i - d.secs(0.08):i - 8].max()
            self.assertLess(quiet, 0.01 * e.max(), name)                 # the gap really is silent
            self.assertGreater(e[i:i + d.secs(0.03)].max(), 20 * quiet, name)   # and the hit starts on the mark

    def test_lead_moves_the_mark_exactly(self):
        for name in ("whoosh_hit", "swish_pop", "swell_hit", "logo_sting", "reveal"):
            for lead in (0.35, 0.9):
                _, _, marks = sfx_recipes.render(name, lead=lead)
                self.assertEqual(next(iter(marks.values())), lead, name)
        with self.assertRaises(ValueError):
            sfx_recipes.render("riser_hit", lead=0.2)

    def test_runs_put_each_sound_on_its_time(self):
        x, _, marks = sfx_recipes.render("pop_run", times="4.2,4.7,5.6")
        self.assertEqual([round(v, 3) for v in marks.values()], [0.0, 0.5, 1.4])
        e = self.env(x)
        for v in list(marks.values())[1:]:
            i = d.secs(v)
            self.assertGreater(e[i:i + d.secs(0.01)].max(), 10 * e[i - d.secs(0.02):i - 4].max())
        _, _, marks = sfx_recipes.render("typing", seconds=2.0, keys=9)
        self.assertEqual(marks["enter"], 2.0)
        _, _, marks = sfx_recipes.render("count_up", seconds=1.2)
        self.assertEqual(marks["land"], 1.2)
        x, _, marks = sfx_recipes.render("countdown", count=3, gap=0.5)
        self.assertEqual((marks["go"], marks["beep2"]), (1.5, 0.5))
        e, i = self.env(x), d.secs(1.5)
        self.assertGreater(e[i:i + d.secs(0.02)].max(), 5 * e[i - d.secs(0.05):i - 4].max())
        _, _, marks = sfx_recipes.render("heartbeat", bpm=120.0, beats=3)
        self.assertEqual(list(marks.values()), [0.0, 0.5, 1.0])
        _, _, marks = sfx_recipes.render("clock", count=3, gap=0.75)
        self.assertEqual(marks["tick3"], 1.5)
        _, _, marks = sfx_recipes.render("phone", kind="digits", digits="911", gap=0.2)
        self.assertEqual(list(marks.values()), [0.0, 0.2, 0.4])
        x, _, _ = sfx_recipes.render("glitch", seconds=0.2)
        self.assertEqual(len(x), d.secs(0.2))
        for name, mark in (("glitch_cut", "cut"), ("rewind", "stop")):
            _, _, marks = sfx_recipes.render(name, lead=0.3)
            self.assertEqual(marks[mark], 0.3)
        _, _, marks = sfx_recipes.render("time_skip", seconds=0.9)
        self.assertEqual(marks["land"], 0.9)

    def test_lay_puts_sync_points_on_events_and_refuses_what_cannot_fit(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = lambda *a: subprocess.run([sys.executable, str(SCRIPTS / "sfx.py"), *a], capture_output=True, text=True, cwd=tmp)  # noqa: E731
            self.assertEqual(run("make", "riser_hit", "lead=1.0", "gap=0.1").returncode, 0)
            self.assertEqual(run("make", "click", "--variations", "2", "--vary", "0.3").returncode, 0)
            side = json.loads((Path(tmp) / "sfx" / "riser_hit_v001.json").read_text())
            self.assertEqual((side["sync"]["at"], side["marks"]["hit"]), (1.0, 1.0))
            sheet = {"fps": 24, "seconds": 6, "cues": [{"file": "sfx/riser_hit_v001.wav", "frame": 48}, {"file": "sfx/click_v001.wav", "at": 0.5}]}
            (Path(tmp) / "cues.json").write_text(json.dumps(sheet))
            r = run("lay", "cues.json")
            self.assertEqual(r.returncode, 0, r.stderr)
            x = d.read_audio(Path(tmp) / "sfx" / "cues_v001.wav")
            self.assertEqual(len(x), d.secs(6))
            e, i = self.env(x), d.secs(2.0)
            self.assertGreater(e[i:i + d.secs(0.03)].max(), 20 * e[i - d.secs(0.08):i - 8].max())
            self.assertEqual(e[:d.secs(0.5) - 1].max(), 0.0)
            self.assertGreater(e[d.secs(0.5):d.secs(0.51)].max(), 0.0)
            sheet["cues"][0]["frame"] = 12                                # the hit at 0.5 s, but the riser needs 1 s before it
            (Path(tmp) / "early.json").write_text(json.dumps(sheet))
            bad = run("lay", "early.json")
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("shorter lead", bad.stderr)

    def test_vary_never_changes_timing(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = lambda *a: subprocess.run([sys.executable, str(SCRIPTS / "sfx.py"), *a], capture_output=True, text=True, cwd=tmp)  # noqa: E731
            self.assertEqual(run("make", "whoosh_hit", "--variations", "3", "--vary", "0.3").returncode, 0)
            sides = [json.loads(p.read_text()) for p in sorted((Path(tmp) / "sfx").glob("whoosh_hit_v*.json"))]
            self.assertEqual({s["sync"]["at"] for s in sides}, {0.4})
            self.assertEqual(len({s["params"]["weight"] for s in sides}), 3)


class Files(unittest.TestCase):
    def test_wav_round_trip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "a.wav"
            x = d.stereo(tone())
            d.write_wav(p, x)
            self.assertTrue(np.allclose(d.read_audio(p), x, atol=1e-5))
            with self.assertRaises(FileExistsError):
                d.write_wav(p, x)
            with self.assertRaises(FileNotFoundError):
                d.read_audio(Path(tmp) / "missing.wav")

    def test_command_line_writes_versions_and_sidecars_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = lambda *a: subprocess.run([sys.executable, str(SCRIPTS / "sfx.py"), *a], capture_output=True, text=True, cwd=tmp)  # noqa: E731
            self.assertEqual(run("make", "pop").returncode, 0)
            self.assertEqual(run("make", "pop", "pitch=A5", "--variations", "2", "--vary", "0.1").returncode, 0)
            made = sorted(p.name for p in (Path(tmp) / "sfx").glob("pop_v*.wav"))
            self.assertEqual(made, ["pop_v001.wav", "pop_v002.wav", "pop_v003.wav"])
            side = json.loads((Path(tmp) / "sfx" / "pop_v002.json").read_text())
            self.assertEqual((side["recipe"], side["params"]["pitch"], side["seed"]), ("pop", 880.0, 1))
            self.assertAlmostEqual(side["check"]["level"], sfx_recipes.LEVELS["pop"], delta=0.3)
            self.assertNotIn("_level", side)
            r = run("fx", "boom_from", "sfx/pop_v001.wav", "--level", "peak")
            self.assertEqual(r.returncode, 0, r.stderr)
            boom = json.loads((Path(tmp) / "sfx" / "pop_boom_from_v001.json").read_text())
            self.assertAlmostEqual(boom["check"]["true_peak_db"], -1.0, delta=0.2)
            bad = run("make", "pop", "ptich=3")
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("ptich", bad.stderr)
            self.assertEqual(run("audition", "sfx").returncode, 0)
            self.assertIn("pop_v003.wav", (Path(tmp) / "sfx" / "audition.html").read_text())
            self.assertIn("riser", run("list").stdout)
            self.assertIn("seconds=", run("list", "riser").stdout)


class Events(unittest.TestCase):
    def test_a_recipe_reports_where_its_events_are_and_recording_changes_nothing(self):
        plain, _, _ = sfx_recipes.render("crickets", seed=3, seconds=8.0, count=1)
        x, _, _, ev = sfx_recipes.render_events("crickets", seed=3, seconds=8.0, count=1)
        self.assertTrue(np.array_equal(plain, x))
        self.assertGreater(len(ev), 40)
        self.assertTrue(all(0.0 <= e["t"] < 8.0 and 0.0 <= e["gain"] <= 1.0 for e in ev))
        self.assertEqual([e["t"] for e in ev], sorted(e["t"] for e in ev))
        mono = np.abs(x).sum(axis=1)                             # a loud event's time is where the sound is
        loud = max((e for e in ev if 0.5 < e["t"] < 7.5), key=lambda e: e["gain"])
        a = d.secs(loud["t"])
        self.assertGreater(mono[a:a + d.secs(0.02)].max(), 4 * np.median(mono))
        self.assertEqual(sfx_recipes.render_events("click", seed=1)[3], [])
        self.assertIsNone(sfx_recipes.EVENTS)


class Sources(unittest.TestCase):
    def test_kit_search_works_offline_from_the_cached_catalogue(self):
        with tempfile.TemporaryDirectory() as tmp:
            cat = {"sounds": [
                {"id": "whoosh-fast", "name": "Whoosh, fast", "category": "whooshes", "file": "sounds/w.wav", "description": "A fast whip of air.",
                 "tags": ["whoosh", "air"], "use_for": ["Whip pans"], "duration": 0.25},
                {"id": "pop-small", "name": "Pop, small", "category": "pops", "file": "sounds/p.wav", "description": "A small pop.",
                 "tags": ["pop"], "use_for": ["Text appearing"], "duration": 0.05}]}
            (Path(tmp) / "kit-sounds.json").write_text(json.dumps(cat))
            hits = sfx_sources.kit_find(["whip", "air"], tmp)
            self.assertEqual([h["id"] for h in hits], ["kit:whoosh-fast"])
            self.assertEqual(hits[0]["licence"], "CC0-1.0")
            self.assertEqual(sfx_sources.kit_categories(tmp), {"whooshes": 1, "pops": 1})
            self.assertEqual(len(sfx_sources.kit_find([], tmp, category="pops")), 1)
            with self.assertRaises(RuntimeError):
                sfx_sources.fetch("kit:nope", tmp)
            with self.assertRaises(RuntimeError):
                sfx_sources.fetch("https://example.com/x.wav", tmp)


if __name__ == "__main__":
    unittest.main(verbosity=1)
