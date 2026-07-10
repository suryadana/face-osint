# Design Spec — Face-Compare dari Postingan

- **Tanggal:** 2026-07-10
- **Status:** Draft untuk review
- **Topik:** Naikkan recall + precision face-search dengan agregasi wajah dari profile pic **dan** postingan terbaru.

## 1. Tujuan

Sekarang match hanya dari **profile pic** (1 gambar, `faces[0]`). Banyak akun punya profile pic non-wajah (logo/grup/low-res/kosong), dan 1 gambar mudah menghasilkan false positive. Fitur ini mengagregasi wajah dari **profile pic + N post terbaru** untuk sekaligus menaikkan **recall** (menemukan match yang kelewat) dan **precision** (mengurangi salah tebak).

## 2. Keputusan desain (hasil brainstorming)

1. **Robust** — agregasi profile + posts (bukan salah satu).
2. **Hybrid sampling** — untuk tiap akun yang dicek, selalu sampel hingga **N** post terbaru + profile pic. `N` configurable (default 3). Ini otomatis meng-cover kasus fallback (profile pic tak berwajah) tanpa cabang khusus.
3. **Per-gambar: max across semua wajah** — skor sebuah gambar = cosine similarity tertinggi di antara SEMUA wajah yang terdeteksi di gambar itu (bukan `faces[0]`). Menangani post rame-orang.
4. **Ranking pakai max** — `account_score = max` skor seluruh gambar (profile + posts). Dipakai untuk top-list.
5. **Auto-stop (FOUND) pakai konsensus** — hentikan pencarian hanya jika **≥ `CONSENSUS_MIN`** (default 2) gambar berbeda punya skor ≥ `SIM_THRESHOLD`. Guard precision terhadap satu foto lookalike.
6. **Early-stop download** — berhenti men-download post lebih lanjut untuk sebuah akun begitu konsensus tercapai (hemat request).
7. **URL post gratis** — diambil dari respons `web_profile_info` (`edge_owner_to_timeline_media`) yang **sudah dipanggil** di jalur profile pic. Tidak ada API call tambahan; hanya download gambar yang menambah request.

## 3. Constraint

- **Scraping tetap Playwright** — download post via `page.request.get` di dalam browser context.
- **Depend pada branch rate-limit hardening** (`feat/rate-limit-hardening`) — tiap download post/profil harus lewat `RateLimiter` + `RequestBudget` dari branch itu. Fitur ini di-*rebase*/dibangun di atasnya.
- **Python 3.9 compatible.**
- **Backward compatible** — `N=0` mengembalikan perilaku lama (profile-pic-only). `compare`/`pic`/`scrape` tidak berubah.
- Bahasa string user-facing campur ID/EN mengikuti kode.

## 4. Tension rate-limit (wajib jujur)

Fitur ini **menaikkan volume image-download ×(1+N)** per akun (default N=3 ≈ 4 download/akun, dari 1). Ini berlawanan arah dengan kerja hardening. Peredam:

- URL post gratis (tak menambah API call).
- Tiap download tunduk pada `RateLimiter` + `RequestBudget`.
- Early-stop begitu konsensus tercapai.

Model volume di `docs/keamanan-dan-rate-limit.md` **harus diperbarui**: biaya per-akun-dicek naik dari ~3 request jadi ~3 + (1..N) request.

## 5. Arsitektur & unit

### `modules/face.py` — FaceEngine (tambah)
- `all_embeddings(img_bytes) -> list` — embedding SEMUA wajah (kosong bila tak ada).
- Free function `max_similarity(embeddings, ref_emb) -> float | None` — pure, max cosine; `None` bila list kosong.
- `max_similarity_to_ref(img_bytes, ref_emb) -> float | None` — `max_similarity(all_embeddings(bytes), ref_emb)`.
- Method lama (`get_embedding`, `compare`, dll.) tetap.

### `modules/instagram.py` — Instagram (tambah)
- Free function `parse_profile_media(api_json) -> dict` — pure; ekstrak `{"profile_pic_url": str|None, "post_urls": [str,...]}` dari struktur `web_profile_info` (`data.user.hd_profile_pic_url_info.url`/`profile_pic_url` + `data.user.edge_owner_to_timeline_media.edges[].node.display_url`).
- `get_profile_media(username) -> dict` — satu in-page `fetch` ke `web_profile_info`, kembalikan hasil `parse_profile_media`. `get_profile_pic` di-refactor tipis untuk mengonsumsi ini (tetap kembalikan `(url, bytes)` seperti sekarang).
- `download_image(url) -> bytes | None` — via `page.request.get`, lewat rate-limiter/budget.

### `modules/search.py` — BFSSearch (perluas)
- Free function `decide_account(image_scores, threshold, consensus_min) -> dict` — pure; input list skor per-gambar (float, boleh `None`→di-skip), output `{"score": float|None, "matched": int, "is_match": bool}`. `score`=max; `matched`=jumlah skor≥threshold; `is_match`=`matched >= consensus_min`.
- `_check_one` diperluas: `get_profile_media` → download profile pic + hingga N post (early-stop saat `matched >= consensus_min`) → kumpulkan skor per-gambar → `decide_account` → `results.append((username, score))`; set `found` bila `is_match`.

### `modules/config.py`
- `POST_SAMPLE_N = 3`, `CONSENSUS_MIN = 2`.

### `face-osint`
- Flag `--posts N` (override `POST_SAMPLE_N`) untuk `search`; teruskan ke `BFSSearch`.

## 6. Data flow (per akun dicek)

```
get_profile_media (1 API call, sudah ada)
  -> profile_pic_url + post_urls[:N]
download profile pic (1 req)          -> max_similarity_to_ref -> skor[0]
for url in post_urls[:N]:             (early-stop bila matched>=CONSENSUS_MIN)
  download (1 req, limiter+budget)    -> max_similarity_to_ref -> skor[i]
decide_account(skor, SIM_THRESHOLD, CONSENSUS_MIN)
  -> account_score (ranking) + is_match (found)
```

## 7. Error handling

- Download gagal / gambar tak ada wajah → skor gambar itu di-skip (bukan error fatal).
- `SoftBlockError`/`BudgetExceeded` dari download → propagate (graceful stop dari hardening).
- Profile pic tak ada + tak ada post → akun di-skip seperti sekarang.

## 8. Testing

Fokus pada **logika murni** (tanpa model/jaringan):
- `max_similarity(embeddings, ref_emb)` — max & empty→None.
- `parse_profile_media(api_json)` — ekstraksi URL profil + post dari JSON contoh, termasuk field hilang.
- `decide_account(scores, threshold, consensus)` — max ranking, hitung matched, konsensus (`None` di-skip, di bawah/atas threshold, tepat di batas).
Wiring `_check_one` + download diverifikasi manual (run nyata volume kecil) dan/atau fake page object.

## 9. Success criteria

- `all_embeddings`/`max_similarity_to_ref` mengembalikan max lintas semua wajah.
- Post URL diambil dari respons `web_profile_info` yang sudah ada (0 API call ekstra).
- `search` mengagregasi profile + hingga N post; ranking=max; found butuh konsensus ≥ CONSENSUS_MIN; early-stop aktif.
- `N=0` = perilaku lama.
- Download post lewat limiter/budget hardening.
- `docs/keamanan-dan-rate-limit.md` model volume diperbarui untuk biaya ×(1+N).

## 10. Out of scope (YAGNI)

- Paginasi > ~12 post / GraphQL terpisah (pendekatan B).
- Cache embedding per-wajah lintas run.
- Deteksi wajah pada video/reels.
- Perubahan pada `compare`/`pic`/`scrape`.

## 11. Langkah berikut

Setelah approve → writing-plans untuk rencana implementasi. **Urutan:** dikerjakan setelah branch `feat/rate-limit-hardening` selesai/merge (butuh limiter+budget-nya).
