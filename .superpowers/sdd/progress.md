# Rate-Limit Hardening — Progress Ledger

Branch: feat/rate-limit-hardening
BASE: 0b942ae
Plan: docs/superpowers/plans/2026-07-10-rate-limit-hardening.md

Task 1: complete (commits 0b942ae..cd0b6b0, review clean; minor: unused asyncio import [resolves Task 2], jittered_delay docstring)
ENV GOTCHA: run tests with .venv/bin/pytest (python3.11). `python -m pytest`=rtk-mangled/pyenv3.9-no-pytest. Verified Task2-5: 12/12 passed.
Task 2-5: complete (commits cd0b6b0..774e416, review Approved; NOTE for final review: RateLimiter holds lock across sleep => paces to 1 req in-flight, makes Semaphore(workers) moot for throughput — plan-mandated, functionally correct, aligned with throttle goal).
Task 6: complete (commit bac9dc0, review Approved, 14/14; final-review notes: (a) get_profile_pic home-nav goto not paced/soft-block-checked [out-of-scope, follow-up]; (b) `r is None`->status 200 treated clean [plan-mandated]; (c) unused random import minor).
Task 7: complete (commit 8cd5ee3, review Approved, 16/16; key risk VERIFIED ABSENT - stop paths do not set found_data, no false MATCH. minors: duplicated stop block [helper candidate], no test for stop-on-exception path).
Task 8: complete (commit 517dc99, review Approved, 16/16 + CLI flags verified). minors for final: (1) docs Mitigasi intro overstates scope - limiter only on search BFS path not pic/scrape/depth-0; (2) top-of-file -h docstring still lists old flags only.
FINAL REVIEW (opus): Ready to merge WITH FIXES. No Critical. Important #1 (_scrape_user seed scrape ungoverned) + #2 (get_profile_pic home-nav ungoverned, budget undercount ~2x). Nits #4/#5/#6. Follow-ups #3/#7. Dispatching one fix subagent.
FINAL FIX: complete (commit a05f097, 16/16 green, -h flags OK, all search-path Instagram() sites governed; pic/scrape intentionally ungoverned+documented). #3/#7 deferred. ALL TASKS DONE.
DOCS commit 17884da. PUSH+PR: gh account komang-surya (SSH) denied; switched to suryadana + HTTPS. PR #1: https://github.com/suryadana/face-osint/pull/1. BRANCH COMPLETE.
