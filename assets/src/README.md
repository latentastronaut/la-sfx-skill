# The repo's pictures

`draw.html` draws the three pictures in `assets/` with code, so they can be made again when something changes (the recipe count is `RECIPES` at the top of its script).

| Picture | Open | Size | Used for |
|---|---|---|---|
| `../banner.png` | `draw.html?v=banner` | 1680x420 | the top of the README |
| `../social-preview.png` | `draw.html?v=social` | 1280x640 | GitHub's social preview (uploaded by hand in the repo's settings) |
| `../icon.png` | `draw.html?v=icon` | 512x512 | anywhere a square is needed |

To export one, take a screenshot of the page at its exact size with a headless browser, for example:

```
google-chrome --headless --allow-file-access-from-files --hide-scrollbars --window-size=1680,420 --virtual-time-budget=5000 --screenshot=banner.png "file://$PWD/draw.html?v=banner"
```

The page's two fonts are in `fonts/` (Anton and Geist Mono, both SIL Open Font License; the licence is `fonts/OFL.txt`), so it needs no network. Chrome needs `--allow-file-access-from-files` to read them from disk. Save the result without metadata before committing it.
