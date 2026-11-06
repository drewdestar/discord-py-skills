## Cross-platform and all-languages box

Honest status, not a promise:

- VERIFIED on this VM (Linux, Python 3.12.3): the stdlib demo
  server runs and serves `/health` and `/api/stats` (the tests
  boot it and hit it). The skill text follows the Agent Skills
  spec, so any spec-reading agent can load it.
- UNVERIFIED: macOS and Windows — no machine here to run them
  on. The demo makes no OS-specific calls (no systemd, no
  platform paths, no shell commands), so it is expected to run
  wherever Python 3.10+ runs, but that is an expectation, not a
  verification. The repo itself never tested Windows.
- UNVERIFIED: the FastAPI upgrade path. `pip install fastapi`
  could not run on this VM (system pip refuses without
  --break-system-packages, and a venv install timed out reaching
  PyPI). FastAPI + uvicorn is the production upgrade path
  documented in the research file — same endpoints, same
  database, same auth — but it was not run here, and the skill
  must not claim otherwise.
- UNVERIFIED: real-browser rendering. The demo was verified over
  HTTP, not in a browser. Check the page at 390/768/1280 in a
  real browser before calling it done, and say so when you have
  not.
- Languages: the skill text is English, per repo convention.
  The dashboard's user-facing strings must go through `i18n`
  locale tables; hardcoding English fails the bar.
