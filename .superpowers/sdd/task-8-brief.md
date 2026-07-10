### Task 8: CLI flags + docs

**Files:**
- Modify: `face-osint` (`cmd_search` arg parse `:169-181`, help `:150-158`, `BFSSearch(...)` `:222`, `_scrape_user`/`Instagram(...)` sites)
- Modify: `docs/penggunaan.md`, `docs/keamanan-dan-rate-limit.md`

**Interfaces:**
- Consumes: `RateLimiter`, `RequestBudget` from `modules.ratelimit`, `config.*` defaults.
- Produces: CLI flags `--rate N`, `--max-requests N`, `--max-expand N`, `--delay-min X`, `--delay-max X`; builds one `RateLimiter` + one `RequestBudget` and passes into `BFSSearch`.

- [ ] **Step 1: Parse new flags in `cmd_search`**

In `cmd_search` arg loop (`:169-181`), add before the `else:` branch:
```python
        elif args[i] == "--rate" and i + 1 < len(args):
            rate = int(args[i + 1]); i += 2
        elif args[i] == "--max-requests" and i + 1 < len(args):
            max_requests = int(args[i + 1]); i += 2
        elif args[i] == "--max-expand" and i + 1 < len(args):
            max_expand = int(args[i + 1]); i += 2
        elif args[i] == "--delay-min" and i + 1 < len(args):
            delay_min = float(args[i + 1]); i += 2
        elif args[i] == "--delay-max" and i + 1 < len(args):
            delay_max = float(args[i + 1]); i += 2
```
Initialize defaults just above the loop (near `depth = 1`):
```python
    rate = config.RATE_PER_MIN
    max_requests = config.MAX_REQUESTS
    max_expand = config.MAX_EXPANSIONS_PER_LAYER
    delay_min, delay_max = config.DELAY_RANGE
```

- [ ] **Step 2: Build limiter/budget and pass to BFSSearch**

At top of `face-osint`, add: `from modules.ratelimit import RateLimiter, RequestBudget`.
Before constructing `BFSSearch` (`:222`), add:
```python
    limiter = RateLimiter(rate, jitter_range=(delay_min, delay_max))
    budget = RequestBudget(max_requests)
    config.MAX_EXPANSIONS_PER_LAYER = max_expand   # honor CLI override
```
Change the constructor call to:
```python
    searcher = BFSSearch(ref_path, cookie_string=cookie, workers=workers,
                         face_engine=engine, ref_emb=ref_emb,
                         rate_limiter=limiter, budget=budget)
```
After `search(...)` returns, if `searcher.stop_reason`, print it:
```python
    if searcher.stop_reason:
        print(f"\n  STOPPED early (safety): {searcher.stop_reason}")
```

- [ ] **Step 3: Update help text**

In `cmd_search` usage block (`:150-158`), add lines:
```python
        print("  --rate N        Global read pace, requests/min (default 20; 0=off)")
        print("  --max-requests N  Per-run request budget (default 800)")
        print("  --max-expand N  Max accounts expanded per layer (default 15)")
        print("  --delay-min X / --delay-max X  Jittered inter-action delay seconds")
```

- [ ] **Step 4: Manual verification (real run, low volume)**

Run:
```bash
./face-osint --cookie "sessionid=..." search ref.jpg <username> --depth 1 --rate 20 --max-requests 60
```
Expected: run paces requests (visible spacing), stops with `STOPPED early (safety): request budget exceeded: 61 > 60` once budget hit, and never retry-loops on a soft-block.

- [ ] **Step 5: Update docs**

In `docs/penggunaan.md` options table for `search`, add rows for `--rate`, `--max-requests`, `--max-expand`, `--delay-min/max` with the defaults above. In `docs/keamanan-dan-rate-limit.md` "Mitigasi" section, replace the "hanya menurunkan volume" caveats that are now fixed and note the new global limiter, jitter, soft-block hard-stop, and budget/cap as implemented mitigations.

- [ ] **Step 6: Commit**

```bash
git add face-osint docs/penggunaan.md docs/keamanan-dan-rate-limit.md
git commit -m "feat(cli): expose rate/budget/expand/delay flags + document"
```

---

## Self-Review

**Spec coverage (scope A, item 1–5):**
- Item 1 global rate limiter → Task 2 (`RateLimiter`) + wired Task 6/8. ✓
- Item 2 jitter delays → Task 1 (`jittered_delay`) + wired Task 6. ✓
- Item 3 soft-block detection + hard-stop → Task 4 (`detect_soft_block`) + Task 6 (raise) + Task 7 (graceful stop). ✓
- Item 4 budget + expansion cap → Task 3 (`RequestBudget`) + Task 7 (`cap_expansions`). ✓
- Item 5 global adaptive backoff → Task 1 (`backoff_delay` cap) + Task 6 (`BACKOFF_CAP`, applies on 429). Note: "pause ALL workers" is partially covered (each worker backs off on its own 429; a shared cross-worker pause is deferred as follow-up to keep Task 6 in-place and low-risk). ✓ (documented limitation)

**Placeholder scan:** none — every code step shows concrete code.

**Type consistency:** `rate_limiter`/`budget` kwargs consistent across `Instagram` (Task 6), `BFSSearch` (Task 7), and construction (Task 8). `detect_soft_block(status, url, body_text)` signature identical in Task 4 def and Task 6 calls. `cap_expansions(candidates, max_per_layer)` identical Task 7 def/use.

**Known limitation (deferred, not in scope A):** cross-worker global throttle pause and proxy support are items 6–7 (scope B) — intentionally out of this plan.
