# Design Spec — Dokumentasi Menyeluruh face-osint

- **Tanggal:** 2026-07-10
- **Status:** Draft untuk review
- **Topik:** Dokumentasi project menyeluruh (`docs/` multi-file)

## 1. Tujuan

Menyediakan dokumentasi lengkap face-osint untuk **dua audiens** (pengguna akhir + developer/kontributor), dalam **Bahasa Indonesia** (istilah teknis dibiarkan English, mengikuti gaya `README.md` + `CLAUDE.md`), tersusun sebagai **folder `docs/` multi-file**. Dokumentasi harus jujur soal risiko rate-limit/ban dan batas keamanan tool ini.

## 2. Scope

**Termasuk:**
- Instalasi, konfigurasi cookie, referensi semua command.
- Arsitektur internal (4 modul + entrypoint), alur BFS, diagram.
- Bab keamanan & rate-limit lengkap (risiko ban, model volume, playbook aman) berbasis riset multi-agent 2026-07-10.
- Troubleshooting.

**Di luar scope (YAGNI):**
- Perubahan kode / hardening (itu spec terpisah nanti).
- Site generator (mkdocs/docsify) — cukup Markdown polos.
- Versi bilingual — cukup Bahasa Indonesia.
- Menulis ulang `README.md` root secara total — README tetap, hanya menunjuk ke `docs/`.

## 3. Prinsip desain & constraint

1. **Scraping WAJIB pakai Playwright** (headless Chromium, semua request lewat browser context). Jangan dokumentasikan/anjurkan jalur raw-HTTP (`requests`/`httpx`) untuk scraping. Dokumentasi harus menyatakan constraint ini eksplisit.
2. **Jujur soal risiko** — dokumentasi tidak boleh mengesankan tool ini "aman". Bab keamanan wajib menonjol dan ditautkan dari README.
3. **Satu file = satu tujuan** — tiap file fokus, mudah dirawat.
4. **Akurasi teknis** — fakta harus cocok dengan kode aktual (path, opsi, coupling threshold). Nilai-nilai spesifik dikutip dari kode.
5. **Mermaid** untuk diagram (render di GitHub, tanpa dependency).

## 4. Struktur file

```
docs/
  README.md                     # indeks + quickstart + peringatan ban/legal
  instalasi.md                  # venv, deps, playwright, model, cookie IG
  penggunaan.md                 # semua command + opsi + contoh + lokasi output
  arsitektur.md                 # 4 modul, alur BFS, diagram Mermaid (dev)
  keamanan-dan-rate-limit.md    # risiko ban, model volume, playbook aman, ringkas riset
  troubleshooting.md            # 429, no-face, cookie expired, venv, "hang"=backoff
```

## 5. Outline isi tiap file

### 5.1 `docs/README.md` (indeks)
- 1 paragraf: apa itu face-osint (OSINT face-search di social graph Instagram via BFS).
- **Kotak peringatan mencolok**: risiko ban akun IG, langgar ToU Instagram, dimensi etika face-recognition orang. Tautkan ke `keamanan-dan-rate-limit.md`.
- Quickstart 4 baris (venv → install → playwright install → contoh `search`).
- Daftar isi dengan link ke tiap file `docs/`.

### 5.2 `docs/instalasi.md`
- Prasyarat: Python 3, virtualenv.
- `python3 -m venv .venv` → `source .venv/bin/activate` → `pip install -r requirements.txt`.
- `python3 -m playwright install chromium` (wajib — scraping butuh Chromium).
- Catatan: model insightface `buffalo_l` ~150MB, ke-download otomatis first-run, jalan di CPU (`ctx_id=0`).
- Cookie Instagram:
  - Kenapa wajib (tanpa cookie: 429 / redirect login).
  - Cara ambil cookie dari browser (DevTools → Network → header Cookie).
  - Urutan resolusi (dari `resolve_cookie()`): `--cookies <file>` > `--cookie "<str>"` > `$IG_COOKIE` > `config.COOKIE_STRING`.
  - **Jebakan**: flag cookie global harus **sebelum** subcommand (di-strip dari `sys.argv` lebih awal).

### 5.3 `docs/penggunaan.md`
- Per command (`compare`, `pic`, `scrape`, `search`, `list`): sintaks, contoh, output nyata.
- Opsi `search`: `--depth N` (default 1), `--workers N` (default 3), `--threshold X` (default 0.35), `--no-cache`.
- **Jebakan threshold coupling**: `--threshold` CLI hanya memengaruhi print summary/marker `<<<`; yang benar-benar menghentikan search adalah `config.SIM_THRESHOLD`. Untuk ubah cutoff nyata, ubah `config.SIM_THRESHOLD` (atau wire CLI ke `BFSSearch`).
- **Lokasi output nyata**: `modules/data/` (cache followers/following, profile pic) & `modules/results/` (`face_search_result.json`) — bukan `data/`/`results/` di root seperti kesan README lama.
- Referensi silang ke bab keamanan sebelum menyarankan `--depth 2+`.

### 5.4 `docs/arsitektur.md` (developer)
- Overview: entrypoint `face-osint` (arg parsing + `asyncio.run`) mengorkestrasi 4 modul di `modules/`.
- Diagram Mermaid: `CLI → FaceEngine` + `Instagram (Playwright)` + `BFSSearch`, dan alur data ref-embedding + profile pic.
- **`face.py` — FaceEngine**: wrap insightface buffalo_l, embedding dari bytes/path, `compare()` = cosine similarity; engine di-load sekali, dioper ke `BFSSearch`.
- **`instagram.py` — Instagram** (tegaskan **Playwright**):
  - Shared browser module-level (`_browser`/`_pw`, `ensure_browser()`), tiap instance punya context+page sendiri; caller wajib `close_shared_browser()` di akhir.
  - Followers/following = scrape modal DOM (`_scrape_modal`), bukan private API. `_api_followers`/`_api_following` = **dead code** (`get_followers`/`get_following` route ke `_page_*`). Cap 100 followers / 500 following.
  - Profile pic via `web_profile_info` (in-page `fetch()` + CSRF dari cookie), download via `page.request.get()`.
  - `_goto_with_retry` = exponential backoff pada 429; `skip_home=True` skip navigasi homepage.
- **`search.py` — BFSSearch**: layer 0 = followers+following (dedup); Phase 1 cek semua profile pic paralel (`Semaphore(workers)`, dedup `checked_users`/`checked_urls`); Phase 2 (depth>1) expand akun non-match (`expanded_users`); short-circuit via `found` event; hasil ke `RESULTS_DIR/face_search_result.json`.
- **`config.py`**: konstanta + `COOKIE_STRING`; **path gotcha** (`DATA_DIR`/`RESULTS_DIR` relatif ke `modules/`).
- Catatan caching: reuse `{username}_followers.json`/`_following.json` kecuali `--no-cache`; dedup set lintas-depth.

### 5.5 `docs/keamanan-dan-rate-limit.md` (⭐ utama)
- **TL;DR: tool ini TIDAK aman dari rate-limit.** Kodenya sendiri berasumsi rate-limit pasti kena (ada backoff + peringatan README).
- **Playwright ≠ aman**: tabel 3 lapisan deteksi (transport/fingerprint = Playwright menang; IP = tidak; akun/perilaku = tidak). "Rate-limit berbasis perilaku+akun+IP, bukan alat."
- **Model volume request** (followers cap 100, following cap 500, workers=3): depth 1 ≈ 10³; depth 2 ≈ 10⁵; depth 3 ≈ 10⁶–10⁷ (karena tiap akun non-match di-expand, unbounded, tanpa budget). Phase 2 di-skip saat depth≤1.
- **Mitigasi yang ada (volume-only, lemah di rate)**: backoff+jitter cap 30s; cache disk; dedup set; early-stop; `skip_home`; page-size 50.
- **Faktor risiko (kritis)**: single sessionid untuk seluruh burst; no proxy/IP rotation; BFS expansion unbounded; delay fixed 0.5s/0.7s (fingerprint bot); hanya 429 dianggap throttle (soft-block 200-JSON/`feedback_required`/checkpoint tak terdeteksi); dead code `_api_*`; `PAGE_WAIT` tak dipakai.
- **Realita Instagram (2024–2026)**: throttle logged-in = akun+session+IP; enumerasi follower-list = read toleransi paling rendah; Meta resmi disable akun untuk scraping; laporan ban setelah ~20–47 profil; putusan Bright Data hanya lindungi logged-out. Cantumkan sumber utama (label OFFICIAL/CREDIBLE/COMMUNITY): meta.com/actions/privacy-progress, instaloader #2512, hikerapi.com, scrapfly.io.
- **Playbook pakai aman** (kalau tetap jalan): akun burner (jangan primary), IP residensial per akun, delay acak 1–3s+, budget < ~150 read/jam jauh dari paginasi follower-list, hard-stop pada `PleaseWaitFewMinutes`/`feedback_required` (jangan retry-loop), batasi jumlah expansion per layer, anggap burner barang habis pakai.
- **Etika & legal**: tool melakukan scraping (langgar ToU IG) + face-recognition orang tanpa consent. Tanggung jawab & konsekuensi hukum ada di pemakai. Hanya untuk konteks yang sah/berizin.
- Tautkan ke memory riset (`rate-limit-analysis`).

### 5.6 `docs/troubleshooting.md`
- "No face detected in reference image" — foto tak ada wajah dikenali; pastikan jelas/menghadap depan.
- 429 / rate limit — tunggu, ganti session, turunkan `--workers`; "hang" biasanya backoff 429, bukan bug.
- "403" saat download pic — cookie expired, ambil baru.
- Virtual env error — aktivasi `.venv`.

## 6. Success criteria

- 6 file `docs/` ada dan saling tertaut dari `docs/README.md`.
- Semua fakta teknis cocok dengan kode (path, opsi, coupling threshold, dead code).
- Constraint Playwright dinyatakan eksplisit di `arsitektur.md` + `keamanan-dan-rate-limit.md`.
- Bab keamanan menonjol, jujur, bersumber.
- Ada minimal 1 diagram Mermaid di `arsitektur.md`.
- Gaya bahasa konsisten dengan README/CLAUDE.md (ID + istilah teknis EN).

## 7. Langkah berikut

Setelah spec ini di-approve: lanjut ke skill **writing-plans** untuk memecah penulisan tiap file jadi rencana implementasi.
