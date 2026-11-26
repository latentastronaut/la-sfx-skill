# Ambiences and real-world textures

How `rain`, `fire`, `wind` and `room` are built, why the first three attempts failed, and how to build the next texture (ocean, stream, crowd, traffic) without guessing.

## The method: fit to a recording, then listen

Three rounds of tuning filtered noise by reasoning alone were all rejected by ear. The fourth was fitted to field recordings with `compare` and matched them on every measure before anyone listened. Do it that way:

1. **Get a real recording** of the thing. The Internet Archive needs no key: `https://archive.org/advancedsearch.php?q=(<words>) AND mediatype:audio&fl[]=identifier&fl[]=title&fl[]=licenseurl&rows=8&output=json`, then `https://archive.org/metadata/<id>` for the files and `https://archive.org/download/<id>/<file>`. Items named `aporee_*` are located field recordings, often public domain. Record the item URL and licence.
2. **Measure it**: `sfx.py compare mine.wav real.mp3 --ref-at 60`. Per octave band it gives the level, how spiky the band is (steady noise against separate events), how sparse, and how much of its movement is slow.
3. **Build to the numbers.** Copy the band levels (`tint` in `sfx_ambience.py` makes noise with a given set of band levels). Where the recording is spiky, that band is made of events: synthesize events there, not noise. Where it moves slowly, drive it from a slow random curve.
4. **Compare again** until no notes remain, then build an audition page with the real recording first in each group, so the user judges the synthesis against the real thing.

`compare` finding no differences is not proof the sound is right; it removes the gross errors so the user's listening is spent on taste.

## What the recordings showed

- **Rain** (a courtyard in summer rain) is brightest at 2 to 4 kHz, with a lot of body from 60 Hz to 1 kHz only 4 to 6 dB under that, and little above 10 kHz. It is close to steady noise, slightly sparse in the top bands. The rejected versions were all highs (harsh static) or all lows.
- **A campfire** from a few metres is a low rumble under 300 Hz, almost nothing from 500 Hz to 2 kHz, and sparse, very bright clicks above 4 kHz that are the same click in every band. The rejected version put its crackle at 500 Hz to 4 kHz with nothing above 8 kHz, over a steady slope of noise (heard as static, not realistic).
- **Flames close up** are the opposite: dense crackle from 300 Hz to 4 kHz, peaking near 2 kHz, little rumble.
- **Wind** in trees is flat from 125 Hz to 2 kHz and falls away above; its top bands swell slowly with the gusts (a gust is brighter, not only louder). A howl round a building is one narrow band near 250 Hz that rises and falls slowly.

## Rules from other people's listening

These come from the change log of the SleepSounds project (an open-source ambience generator whose author logged each listener complaint, its cause and the fix) and from Andy Farnell's *Designing Sound*. They matched this project's own rejections.

- **Events lead, the bed follows.** "Environmental sounds are identified from temporal events, not static spectra." A steady band of noise above about 2 kHz at a fixed level is heard as static however it is filtered. Delete it, darken it, or make its level follow the thing that drives it.
- **No pitch in a short event.** A narrow filter or a sine in a drop or crackle makes it a beep, a bubble, a laser or a wind chime. Use wide filters (quality under 1), mostly noise; any tone is rare, short and faint.
- **Soft starts.** A burst of noise that begins at full level is a keyboard click. Give it 1 to 2 ms of raised-cosine attack.
- **No fixed-rate wobble.** A sine LFO is heard as a cycle within a minute. Use random targets held for random times and eased between (`wander`).
- **Give every event its own place.** In a real fire the crackles go off across the whole width and at different depths. Pan each event on its own, and make far ones quieter, duller and wetter. Events that share one position sound like one thing ticking.
- **No patterns.** Groups of events need a random count, uneven gaps and a different tone each time; three equal knocks are heard as triplets. Evenly spaced surges in thunder are heard as a clock.
- **Cluster and rest.** Crackles and drops come in runs with gaps; a constant spray of grains is heard as static.
- **Lows in the middle.** Spread only the highs (`spread`); spreading the whole band sounds like two machines. Steady, compact sources (a fan, a hum, room tone) stay mono.
- **Quiet is the point of room tone.** It is levelled 14 dB under the other beds. A room tone made of low rumble and levelled like the others was rejected as too aggressive.
- **Level traps.** Loudness measures discount low frequencies, so a rumble levelled to a loudness target comes out far too strong. Brown noise is nearly all below 60 Hz unless it is high-passed.

## Thunder and explosions

The first versions followed published designs and were still rejected; measuring real recordings over time (level in four bands, second by second) showed why.

- **Thunder** is nearly all below 120 Hz; the 120 to 500 Hz band sits 5 to 9 dB under that and 500 Hz to 2 kHz about 20 dB under. After the first surge it stays within 10 to 15 dB for 14 seconds or more, in irregular bumps. `thunder` is a handful of overlapping low surges at random, uneven times (evenly spaced surges were heard as "a clock"), each a few swells of low-passed noise, under a long dark reverb. There is no separate crack: a crack built from bright ticks was heard as a different, close-up sound.
- **An explosion** (measured on a real cannon shot) is equally loud in every band for the first quarter second, loses about 15 dB in three quarters of a second, and then lingers for seconds as an echo in the middle of the range. `explosion` is a full-range noise bang, a low body and a sinking "fireball" under it, and the bang's own echo. A version that was mostly low rumble with a thin crackle on top was heard as hollow.

## Sources

- Andy Farnell, *Designing Sound* (MIT Press): fire as hissing + crackling + lapping; wind as noise driven by one wind-speed signal with gusts and squalls; the patches are shown at `https://mitp-content-server.mit.edu/books/content/sectbyfn/books_pres_0/8375/designing_sound.zip/index.html`. SuperCollider versions: `https://en.wikibooks.org/wiki/Designing_Sound_in_SuperCollider`.
- SleepSounds: `https://github.com/HamzaAnjum96/SleepSounds` (`CHANGELOG.md`, `src/audio/generators.ts`, `public/worklets/`). The layer lists for fire and room tone, the three-distance drop scheme and the early reflections for rain come from here.
- McDermott and Simoncelli, "Sound texture perception via statistics of the auditory periphery" (2011): the idea that a texture is recognised from per-band envelope statistics, which is what `compare` measures.
- Reference recordings used for the fit (Internet Archive): `aporee_2104_66430` (rain, CC BY-SA 3.0), `aporee_40321_46050` (campfire, public domain), `Red_Library_Fire` (flames, CC0), `aporee_73492_85897` (gusts, public domain), `aporee_22846_26515` (howling wind, CC BY-SA 3.0). Only their measurements are in the code.
