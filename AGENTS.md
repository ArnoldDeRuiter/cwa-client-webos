# AGENTS.md

Read `~/git/personal/slopbro/TV-HANDOVER.md` first for the TV's IP/SSH
access, CDP, root exec bridge, and standing rules. This file covers what's
specific to this repo.

## What this is

`type: web` Homebrew app (`nl.arnolderuiter.cwa`) — full-screen wrapper
around `https://cwa.1701.nl/` (Calibre-Web Automated, hosted on the pikvm,
see `../pikvm-playbook`). Two background daemons started via the root exec
bridge from `index.html`:

- `readerfix.py` — CDP-injected keydown handler: ArrowLeft/ArrowRight
  dispatch pointer/mouse/click events at 50px from the left/right edge,
  mid-height, descending into same-origin iframes (epub reader).
  ArrowUp goes to `/book/<id>` from `/read/<id>/...`, else `/`; ArrowDown
  (reader only) cycles `reader.rendition.themes.fontSize` 200..75.
  On `/read/*` pages it also presets `localStorage` `calibre.reader.theme`
  = `blackTheme` (text overridden to warm grey `#c8b896` via
  `rendition.themes.override`, black theme only) and `calibre.reader.fontSize` = `200` (read by CWA's reader
  at startup) and sets `.arrow` / `#titlebar` to `opacity: 0` (OLED burn-in).
- `loginfill.py` — fills `form.cwa-login-form` `username`/`password` from
  the `"cwa"` key in `/var/lib/webosbrew/tv-credentials.json`, never submits.
  Skips when the Flask-Login `remember_token` cookie exists.

## Build

```sh
sh build.sh
```

Hand-rolled `.ipk`, version from `appinfo.json`. **Don't hand-bump the
version** — CI derives it from the release tag.

## Testing changes live (do this before committing anything TV-facing)

```sh
scp index.html readerfix.py start-readerfix.sh loginfill.py start-loginfill.sh \
  tvtje:/media/developer/apps/usr/palm/applications/nl.arnolderuiter.cwa/
```

Relaunch on the TV, check `/tmp/cwa-readerfix.log` / `/tmp/cwa-loginfill.log` over SSH.

## Direct install (no release)

```sh
./build.sh && scp nl.arnolderuiter.cwa_*_all.ipk tvtje:/tmp/
ssh -tt tvtje 'luna-send -w 60000 -n 8 luna://com.webos.appInstallService/dev/install "{\"id\":\"com.ares.defaultName\",\"ipkUrl\":\"/tmp/nl.arnolderuiter.cwa_0.1.0_all.ipk\",\"subscribe\":true}"'
```

`luna-send` prints nothing over SSH without a TTY — always `ssh -tt`.

## Rules

- Never `git push` — Captain pushes himself.
