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

=== POSTS FEATURE (branch feat/face-compare-posts, base c8ffbae) ===
Plan: docs/superpowers/plans/2026-07-10-face-compare-posts.md
Co-author trailer: I Komang Suryadana <suryadana80@gmail.com> (NOT Claude). Tests: .venv/bin/pytest.
POSTS Task 1-3: complete (commits c8ffbae..3dc3701, review Approved, 24/24, co-author=user). minors: no zero-norm guard (consistent w/ existing), no decide_account ==threshold boundary test, username unescaped in get_profile_media JS (untested, low risk).
POSTS Task 4: review NEEDS FIXES. Important #1 (--posts 0 can never match: cap consensus=min(CONSENSUS_MIN,1+post_n)). Important #2 (get_profile_media+download_image bypass pacing/budget/soft-block). Minor: no Posts: startup line. Dispatching fix.
POSTS Task 4: complete after fix (commit 97f7feb, re-review Approved, 26/26). Both Important resolved. carry minors: username unescaped in get_profile_media JS; in-page fetch swallows non-2xx (consistent w/ get_profile_pic); no Posts: startup line; single-image accounts never auto-stop unless post_n=0.
POSTS FINAL REVIEW (opus): Ready for PR WITH FIXES. No Critical. Important #1 (recall change - lone profile-pic no auto-stop: doc note + --posts 0). Important #2 (web_profile_info soft-block swallowed -> escalates at depth>=2: surface status+detect_soft_block). Minor #4 Posts banner. Follow-ups: username escaping, strong-single-hit override, zero-norm, depth-0 --posts. Dispatching fix.
POSTS fix2: complete (commit 78b4701, 27/27, co-author=user). Both final-review Important resolved (+regression test). FEATURE COMPLETE, PR-ready. Base c8ffbae (stacked on hardening).
