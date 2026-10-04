# AGENTS.md

Read `~/git/personal/slopbro/TV-HANDOVER.md` first for the TV's IP/SSH
access, CDP, root exec bridge, and standing rules. This file covers what's
specific to this repo.

## What this is

`type: web` Homebrew app (`nl.arnolderuiter.cwa`) — full-screen wrapper
around `https://cwa.1701.nl/` (Calibre-Web Automated, hosted on the pikvm,
see `../pikvm-playbook`). One background daemon started via the root exec
bridge from `index.html`:

- `dpadclick.py` — CDP-injected keydown handler: ArrowLeft/ArrowRight
  dispatch pointer/mouse/click events at 50px from the left/right edge,
  mid-height, descending into same-origin iframes (epub reader).

## Build

```sh
sh build.sh
```

Hand-rolled `.ipk`, version from `appinfo.json`. **Don't hand-bump the
version** — CI derives it from the release tag.

## Testing changes live (do this before committing anything TV-facing)

```sh
scp index.html dpadclick.py start-dpadclick.sh \
  tvtje:/media/developer/apps/usr/palm/applications/nl.arnolderuiter.cwa/
```

Relaunch on the TV, check `/tmp/cwa-dpadclick.log` over SSH.

## Rules

- Never `git push` — Captain pushes himself.
