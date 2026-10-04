# CWA Reader (webOS)

Unofficial Calibre-Web Automated wrapper for rooted LG webOS TVs, built as a
Homebrew Channel app. Opens `https://cwa.1701.nl/` full-screen in webOS's own
browser engine, same one-line-redirect technique as
[f1tv-webos](https://github.com/ArnoldDeRuiter/f1tv-webos).

## Remote controls

- **D-pad left / right**: clicks the page at 50px from the left / right edge,
  vertically centered — turns pages in CWA's web reader. Ignored while a text
  field is focused.
- Everything else: Magic Remote pointer and scroll wheel.

The D-pad mapping is a small background daemon (`readerfix.py`, started at
launch via the Homebrew Channel root exec bridge) that injects a key handler
into the app's page over the on-device Chrome DevTools Protocol. It exits
when the app closes.

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
