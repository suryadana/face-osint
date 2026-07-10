# Instalasi & Konfigurasi

## Prasyarat

- Python 3 (disarankan 3.9+).
- `git`, koneksi internet (first-run mengunduh model ~150MB).
- Akun Instagram untuk mengambil cookie session — **gunakan akun burner, bukan akun pribadi** (lihat [keamanan-dan-rate-limit.md](keamanan-dan-rate-limit.md)).

## Langkah setup

```bash
python3 -m venv .venv
source .venv/bin/activate                 # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python3 -m playwright install chromium     # WAJIB — scraping butuh Chromium
```

Entry point-nya adalah script executable `face-osint` (bukan package terpasang — jalankan langsung):

```bash
./face-osint --help
```

## Model face recognition

- Memakai insightface `buffalo_l`.
- Ukuran ~150MB, **ke-download otomatis pada run pertama**.
- Berjalan di CPU (`ctx_id=0`) — tidak butuh GPU.
- Model di-load sekali per proses dan dipakai ulang oleh semua worker.

## Cookie Instagram (wajib untuk scraping)

Semua command yang menyentuh jaringan (`search`, `scrape`, `pic`) butuh **cookie session Instagram yang valid**. Tanpa cookie, request akan kena 429 (rate-limited) atau redirect ke halaman login.

### Cara mengambil cookie

1. Login ke `instagram.com` di browser.
2. Buka DevTools (F12) → tab **Network**.
3. Refresh halaman, klik request pertama.
4. Di **Request Headers**, cari header `Cookie`.
5. Copy seluruh string-nya (mulai `datr=...` sampai akhir).

Alternatif: ekstensi export cookie (mis. EditThisCookie).

### Urutan resolusi cookie

Ditangani oleh `resolve_cookie()` di script `face-osint`, prioritas dari atas:

| Prioritas | Metode | Contoh |
|---|---|---|
| 1 | File eksternal | `--cookies cookies.txt` |
| 2 | Argumen CLI | `--cookie "datr=...; sessionid=..."` |
| 3 | Environment variable | `export IG_COOKIE="datr=...; sessionid=..."` |
| 4 | Default di config | edit `modules/config.py` → `COOKIE_STRING` |

### ⚠️ Jebakan: posisi flag cookie

Flag cookie global (`--cookies` / `--cookie`) **harus diletakkan SEBELUM subcommand** — keduanya di-strip dari `sys.argv` lebih awal oleh `resolve_cookie()`.

```bash
# BENAR
./face-osint --cookie "sessionid=..." search ref.jpg target --depth 1

# SALAH (flag setelah subcommand tidak terbaca sebagai cookie global)
./face-osint search ref.jpg target --cookie "sessionid=..."
```

### Masa berlaku

Cookie Instagram expired dalam hitungan jam sampai beberapa hari. Kalau muncul 403/redirect login, ambil cookie baru.
