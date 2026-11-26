# Free sounds with no key

Tested live on 2026-11-24 with plain HTTP requests, a generic User-Agent and no account. "Built in" means `sfx.py find` and `fetch` handle it, and those two were exercised through the script. The rest come from one research pass with curl (a search and a small download each); re-test before relying on them.

## Built in

### wyzowl/sfx-kit (id prefix `kit:`)

- 320 original sounds for video, animation and interfaces: whooshes, swipes, pops, risers and fallers, impacts, cinematic hits, booms and bass, logo stings, shimmers, notifications, interface clicks, keyboard, writing and drawing, data, money, phone, time, mechanical, foley, everyday props and more. `sfx.py find --categories` lists them.
- **Licence: CC0 1.0** (public domain). Credit is not required. Read at the repo's `LICENSE` and the `license` field of `sounds.json`.
- WAV, 24-bit, 48 kHz. Each sound has a description, what to use it for, what to avoid it for, tags, length, a sync point and a level. `fetch` copies these into the sidecar.
- Served from `raw.githubusercontent.com`. The catalogue (`sounds.json`) is cached beside the fetched sounds on first use, so later searches are offline.
- Levels follow a tiered scale (loudest 150 ms, true peak at or under -3 dB). The recipes in this skill are levelled to the same scale.

### Wikimedia Commons (id prefix `commons:`)

- Recordings of real things. Coverage is uneven: good for doors, glass, footsteps, animals, machines, instruments; thin for anything abstract. One uploader, Gravity Sound, has many clean effects (CC BY 4.0).
- **Licence is per file**: CC0, public domain, CC BY or CC BY-SA. `find` shows it; `fetch` writes the licence, its URL, the author and `attribution_required` into the sidecar. `--free-only` limits a search to CC0 and public domain.
- Search is noisy. Commons holds hundreds of thousands of spoken-word pronunciation clips; `find` excludes them (`-intitle:"LL-Q" -pronunciation`) and anything over `--max-seconds` (default 30). Use plain nouns ("glass breaking", "footsteps gravel"), not descriptions of a feeling.
- **Rate limits are tight for anonymous tools.** About ten quick requests brought a 429 on both the search API and the file host. Search a few times a minute, fetch only what you will use, and wait a minute after a 429. The script backs off and retries three times, then stops with a message.
- Files are WAV, OGG, FLAC or MP3. Non-WAV files need ffmpeg to be read by `fx` and `check`.

## Works, not built in

| Source | What | Licence | How |
|---|---|---|---|
| Internet Archive | Field recordings: items named `aporee_*` (radio aporee) are located ambiences (rain, fire, wind, streets), many public domain; the search API and downloads worked with no key and no rate trouble on 2026-11-24, when Commons refused three downloads in a row with 429. Also mixed uploads. Items checked: `book-sound-effects` (page turns), `various-sound-effects` (knocks, doors), `slack_sfx` (UI sounds), `bbt_sfx` (short game sounds) | Per item, in `metadata.licenseurl`. The field is whatever the uploader chose: commercial libraries appear tagged public domain. Trust named items, not open search. | `https://archive.org/metadata/<id>` lists files; `https://archive.org/download/<id>/<file>` (follow redirects) |
| GitHub mirrors of Kenney packs | `Calinou/kenney-interface-sounds` (100 UI sounds, WAV), `Boyquotes/kenney-impact-sounds-for-godot` (130, OGG), `Boyquotes/kenney-sci-fi-sounds-for-godot` (73, OGG) | CC0 | Raw file URLs; list a repo with the GitHub trees API |
| `facebookincubator/Meta-open-sound` | Footsteps, UI, doors, foley (1,583 files, OGG) | CC BY 4.0 for the pack, per `catalog.json` | Raw file URLs |
| Mixkit | Designed effects | Mixkit free licence: free in projects, no redistribution of the files themselves | HTML scraping of tag pages; direct MP3 and WAV URLs |
| BBC Sound Effects | A very large archive of real recordings | RemArc: personal, educational and research use; the site says commercial use is not allowed | An undocumented JSON search endpoint and direct MP3 URLs |
| SoundBible | Small, mixed | Per sound, as text on the page | HTML scraping |

## Does not work without a key or a person

- **Freesound**: every API call needs a token (401 without one), and its robots.txt disallows the API and search for crawlers. The best free library, but it needs the user's own key.
- **Kenney (kenney.nl)**: robots.txt disallows the asset and download paths and blocks AI agents by name; downloads use signed, short-lived links. Use the GitHub mirrors above.
- **OpenGameArt**: robots.txt blocks AI agents by name. Not tested further.
- **BigSoundBank**: CC0 and searchable, but downloads sit behind an anti-bot form.
- **Pixabay**: the API needs a key and the pages return 403.
- **ZapSplat, Sonniss**: Cloudflare challenge.
- **99Sounds**: downloads go through a checkout page.

When a site blocks automated requests, that is the answer. Don't work around it; tell the user the sound is there and let them download it by hand if they want it.

## Adding a source

A source earns a place in `sfx_sources.py` when it has a search an agent can use, direct file URLs, a licence the script can read per file, and no key. Add a `<name>_find` and a fetch branch, record the same sidecar fields, and add a test that runs offline from a saved response.
