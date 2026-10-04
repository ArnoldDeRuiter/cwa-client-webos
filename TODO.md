# TODO

- Login autofill, same as family7-webos / f1tv-webos: add `loginfill.py` +
  `start-loginfill.sh` (chained from `index.html`'s exec-bridge call), reading
  a `"cwa"` key from `/var/lib/webosbrew/tv-credentials.json`. Fill only,
  never submit; skip if a valid CWA session cookie already exists. Check
  `../pikvm-playbook` for which CWA user the TV should use (read-only one).
- Direct-to-TV install without a GitHub release / Homebrew Channel repo:
  script that runs `build.sh`, `scp`s the ipk to `tvtje:/tmp/`, and installs
  it over SSH (e.g. `luna-send` to `com.webos.appInstallService` or
  Homebrew Channel's install service), then relaunches the app.
