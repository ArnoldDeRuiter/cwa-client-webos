# CWA Reader (webOS)

Unofficial Calibre-Web Automated wrapper for rooted LG webOS TVs, built as a
Homebrew Channel app. Opens `https://cwa.1701.nl/` full-screen in webOS's own
browser engine, same one-line-redirect technique as
[f1tv-webos](https://github.com/ArnoldDeRuiter/f1tv-webos).

## Remote controls

| Button | Where | Action |
|---|---|---|
| D-pad left / right | everywhere | Click 50px from the left / right edge, vertically centered — turns pages in the reader |
| D-pad up | reader | Open the book's detail page |
| D-pad up | elsewhere | Go to the start page (`cwa.1701.nl`) |
| D-pad down | reader | Cycle font size 200 → 175 → 150 → 125 → 100 → 75 → 200% |
| Channel up | reader (Black theme) | Text one step brighter |
| Channel down | reader (Black theme) | Text one step dimmer |
| Pointer / scroll wheel | everywhere | Normal browser behaviour |

All of the above are ignored while a text field (search, login) is focused.

Text brightness steps, all warm-toned and at least 7:1 contrast on black:

| Step | Colour | Light vs white |
|---|---|---|
| 1 (dimmest) | `#a89a7e` | ~33% |
| 2 | `#b8a88a` | ~40% |
| 3 (default) | `#c8b896` | ~49% |
| 4 | `#d8cab0` | ~60% |
| 5 | `#e8dfcc` | ~74% |
| 6 (brightest) | `#ffffff` | 100% |

The chosen step is remembered across books and launches.

## Reader defaults (OLED)

The epub reader always opens in the **Black** theme at max font size (200%),
with warm grey text and the page arrows and title bar invisible (still
clickable) to avoid OLED burn-in. Switching to another theme in the reader
settings restores that theme's normal text colour.

All of this is a small background daemon (`readerfix.py`, started at launch
via the Homebrew Channel root exec bridge) that injects into the app's page
over the on-device Chrome DevTools Protocol. It exits when the app closes.

## Login autofill (optional)

Fills CWA's username/password fields on the login page, never submits.
Reads the `"cwa"` key from root-only `/var/lib/webosbrew/tv-credentials.json`
on the TV (same file as family7-webos / f1tv-webos):

```json
{"cwa": {"username": "your-username", "password": "your-password"}}
```

Skipped when a `remember_token` session cookie already exists; exits after
filling once.

## Installing

In Homebrew Channel, open **Add repository** and enter:

```
https://github.com/ArnoldDeRuiter/cwa-client-webos/releases/latest/download/repo.json
```

Or build and sideload yourself:

```sh
./build.sh
```

produces `nl.arnolderuiter.cwa_<version>_all.ipk`.

## License

MIT.
