# Troubleshooting

## "No face detected in reference image"

Foto referensi tidak mengandung wajah yang dikenali insightface. Pastikan foto jelas, tidak blur, dan wajah menghadap depan. Berlaku juga untuk foto target di `compare` dan foto profil yang diunduh saat search.

## Rate limit (429) / proses terasa "hang"

Bila proses berhenti lama tanpa output, biasanya itu **backoff 429**, bukan bug — `_goto_with_retry` sedang menunggu (exponential backoff cap 30s) sebelum retry.

Solusi:

- Tunggu 15–30 menit.
- Turunkan `--workers` (pakai 2 atau 1) untuk mengurangi tekanan.
- Ganti cookie dari session berbeda.
- Kurangi `--depth`.

Lihat [keamanan-dan-rate-limit.md](keamanan-dan-rate-limit.md) — rate-limit adalah sifat bawaan tool ini, bukan sekadar error sesekali.

## "403" saat download foto profil

Cookie sudah expired. Ambil cookie baru dari browser (lihat [instalasi.md](instalasi.md)).

## Cookie tidak terbaca / selalu kena login

- Pastikan flag cookie global diletakkan **sebelum** subcommand (`./face-osint --cookie "..." search ...`).
- Cek urutan resolusi: `--cookies` > `--cookie` > `$IG_COOKIE` > `config.COOKIE_STRING`.
- Pastikan string cookie lengkap (mengandung `sessionid`, `csrftoken`, `ds_user_id`).

## File cache/hasil tidak ketemu di root

Output tidak mendarat di `data/`/`results/` root. `config.py` menaruhnya relatif ke folder `modules/`:

- Cache: `modules/data/`
- Hasil: `modules/results/face_search_result.json`

## Virtual environment error

```bash
source .venv/bin/activate      # Linux/Mac
.venv\Scripts\activate         # Windows
```

Pastikan `.venv` sudah dibuat dan dependency terpasang (lihat [instalasi.md](instalasi.md)).

## Playwright: browser tidak ditemukan

Jalankan `python3 -m playwright install chromium`. Scraping butuh Chromium headless; tanpa ini, semua command jaringan gagal saat launch browser.
