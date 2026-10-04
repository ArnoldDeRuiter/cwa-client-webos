# TODO

- Wrap the direct install (see AGENTS.md "Direct install") in a script:
  build, scp, install, relaunch via
  `luna://com.webos.applicationManager/launch`.
- Add `cwa` credentials to `../lgtv` Ansible vault + `site.yml` template —
  that task rewrites `tv-credentials.json` with only `f1tv`/`family7`, so a
  playbook run currently drops the `cwa` key.
