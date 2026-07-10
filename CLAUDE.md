# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A CLI OSINT toolkit that finds a target face across an Instagram social graph. Given a reference photo and a starting username, it scrapes followers/following, downloads profile pictures, and runs face comparison recursively (BFS) until it finds a match at or above a similarity threshold.

## Setup & commands

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m playwright install chromium   # required — scraping uses headless Chromium
```

The entry point is the executable `face-osint` (a Python script, not packaged — run it directly):

```bash
./face-osint compare <ref.jpg> <target.jpg>              # cosine similarity of two face images
./face-osint pic <username>                              # download profile pic
./face-osint scrape <username>                           # save followers/following JSON
./face-osint search <ref.jpg> <username> [options]       # the core BFS face search
./face-osint list [results.json]                         # print a saved search result
```

`search` options: `--depth N` (default 1), `--workers N` (default 3), `--threshold X` (0–1, default 0.35), `--no-cache`.

There is **no build, lint, or test suite** — this is a small script-based tool. Verify changes by running the CLI directly against real accounts.

### Instagram cookie (required for scraping)

All network commands (`search`, `scrape`, `pic`) need a valid Instagram session cookie or they hit 429/login redirects. Resolution order (see `resolve_cookie()` in `face-osint`): `--cookies <file>` → `--cookie "<string>"` → `$IG_COOKIE` → `config.COOKIE_STRING`. Global cookie flags must come **before** the subcommand (they are stripped from `sys.argv` early).

## Architecture

Four modules under `modules/`, orchestrated by the top-level `face-osint` script which handles arg parsing and the async event loop (`asyncio.run`).

- **`face.py` — `FaceEngine`**: wraps insightface `buffalo_l`. Loads the model once (~150MB first-run download, CPU via `ctx_id=0`). Produces embeddings from bytes or file paths; `compare()` is cosine similarity. The engine is instantiated once and passed into `BFSSearch` so the model isn't reloaded per worker.

- **`instagram.py` — `Instagram`**: Playwright async scraper, used as an async context manager (`async with Instagram(cookie) as ig:`). Key design points:
  - A **single shared browser** across all `Instagram` instances (module-level `_browser`/`_pw`, guarded by `ensure_browser()`). Each `Instagram` opens its own context+page. **Callers must call `close_shared_browser()` once at the end** — every command does this before returning.
  - Follower/following scraping is **DOM-modal-based** (`_scrape_modal` scrolls the followers dialog), *not* the private API. The `_api_followers`/`_api_following` methods exist but `get_followers`/`get_following` currently route to the page-based `_page_*` scrapers. Modal scraping caps at 100 followers / 500 following and stops early on stall or a "Suggested for you" section.
  - Profile pics come from `web_profile_info` API via in-page `fetch()` with the CSRF token pulled from cookies.
  - `_goto_with_retry` does exponential backoff on 429. `skip_home=True` avoids the initial homepage navigation (used by search workers to save time).

- **`search.py` — `BFSSearch`**: the recursive engine. Layer 0 = the target's followers+following (deduped). Each layer:
  1. **Phase 1**: check every account's profile pic against the reference concurrently, bounded by a `Semaphore(workers)`. Dedup via `checked_users`/`checked_urls` sets under an `asyncio.Lock`. First account at/above `SIM_THRESHOLD` sets `self.found` and short-circuits everything.
  2. **Phase 2** (only if `depth > 1`): accounts that *didn't* match become expand candidates — fetch *their* followers/following and recurse at `depth-1`. `expanded_users` prevents re-expanding.
  - **Note the threshold coupling**: the match cutoff during search is `config.SIM_THRESHOLD`, *not* the `--threshold` CLI value. `--threshold` only affects the summary printout / `<<<` markers in `face-osint`. To change what actually stops the search, change `config.SIM_THRESHOLD` (or wire the CLI value into `BFSSearch`).
  - Results (all detected faces + top-50) are written to `RESULTS_DIR/face_search_result.json`.

- **`config.py`**: constants (`MODEL_NAME`, `SIM_THRESHOLD`, `WORKERS`, timeouts) and `COOKIE_STRING`. It also creates and defines `DATA_DIR`/`RESULTS_DIR`.

### Path gotcha

`config.py` computes `DATA_DIR` and `RESULTS_DIR` relative to the **`modules/` directory** (`CONFIG_DIR = dirname(config.py)`), so scrape output and results actually land in `modules/data/` and `modules/results/` — not the repo-root `data/`/`results/` the README shows. Both are gitignored. Keep this in mind when looking for cached JSON or wiring new paths.

### Caching behavior

`search` reuses `{username}_followers.json` / `{username}_following.json` from `DATA_DIR` unless `--no-cache` is passed. Within a run, `checked_users`/`checked_urls`/`expanded_users` prevent re-checking accounts across depths.

## Git & PR workflow

- **New feature → new branch.** Never commit a feature straight to `main`/`dev`. Branch off the appropriate base (`git checkout -b <feature> dev`).
- **PRs target the `dev` branch, not `main`.** `dev` is the integration branch on `origin`; `gh pr create --base dev --head <feature>`.
- **Do NOT push or open PRs as Claude.** The machine's SSH key authenticates as a GitHub account without write access; the only account with access (`suryadana`) is the user's personal account and must not be used by the agent. Prepare the branch, commits, and PR title/body locally, then **let the user run the actual `git push` / `gh pr create`** (e.g. suggest `! git push ...`).
- **Commit co-author trailer:** end commits with `Co-Authored-By: I Komang Suryadana <suryadana80@gmail.com>` — **do NOT** add the `Co-Authored-By: Claude ...` trailer (overrides the global default). Same for PR bodies: no "Generated with Claude Code" line.
- **Ship `.superpowers/` and `.serena/`:** on every feature branch, commit the `.superpowers/` SDD artifacts (ledger, task briefs, reports, review-package diffs) and the `.serena/` project memory so they go out with the PR. `.superpowers/sdd/.gitignore` ignores them by default — force them in with `git add -f .superpowers/`.

## Notes

- Language of user-facing strings is mixed Indonesian/English (README is Indonesian); match the surrounding style when editing output.
- The whole thing is rate-limit-bound. When something "hangs" it's usually 429 backoff, not a bug. Lower `--workers` to reduce pressure.
