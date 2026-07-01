# Face OSINT — Instagram Face Search Toolkit

Membandingkan wajah dari referensi foto dengan **seluruh jaringan sosial Instagram** secara rekursif (BFS) — otomatis scraping followers/following, download foto profil, dan face comparison.

---

## Instalasi

```bash
cd ~/Learn/face-osint
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m playwright install chromium
```

### Requirements

- `playwright` — browser automation
- `insightface` — face recognition (model: buffalo_l)
- `opencv-python` — image processing
- `numpy` — vector operations
- `requests` — image download

---

## 1. Persiapan Cookie Instagram

Tool ini **wajib pakai cookie session Instagram** yang valid. Tanpa cookie, API Instagram akan return 429 (rate-limited) atau redirect ke login.

### Cara dapat cookie

1. Buka Chrome/Firefox, login ke instagram.com
2. Buka DevTools (F12) → Tab Network
3. Refresh halaman, klik request pertama
4. Cari header `Cookie` di Request Headers
5. Copy seluruh string cookienya (mulai dari `datr=...` sampai `wd=...`)

Atau pakai cara cepat: ekstensi browser seperti **EditThisCookie** export.

### Cara pakai cookie (prioritas):

| Metode | Contoh |
|--------|--------|
| Argumen CLI | `--cookie "datr=...; sessionid=..."` |
| File eksternal | `--cookies cookies.txt` |
| Environment | `export IG_COOKIE="datr=...; sessionid=..."` |
| Default config | Edit `modules/config.py` → `COOKIE_STRING` |

---

## 2. Perintah

### `compare` — Bandingkan 2 gambar wajah

```bash
./face-osint compare foto1.jpg foto2.jpg
```

Output:
```
  Reference: /path/foto1.jpg
  Target:    /path/foto2.jpg
  Similarity: 44.65%
  Threshold:  35%
  Match:      YES
```

### `pic` — Download foto profil Instagram

```bash
./face-osint pic username
./face-osint --cookie "sessionid=..." pic username
```

Foto tersimpan di `data/username_profile.jpg`.

### `scrape` — Scrape daftar followers/following

```bash
./face-osint scrape username
```

Tersimpan di:
- `data/username_followers.json`
- `data/username_following.json`

> **Catatan:** Scrape via API Instagram. Kalau kena rate-limit (429), tunggu beberapa menit atau ganti session.

### `search` — Face search rekursif (inti)

```bash
./face-osint search <ref_image> <target_username> [options]
```

#### Options

| Option | Default | Deskripsi |
|--------|---------|-----------|
| `--depth N` | `1` | Kedalaman graph (0=user, 1=friends, 2=friends-of-friends, ...) |
| `--workers N` | `3` | Jumlah worker paralel untuk face comparison |
| `--threshold X` | `0.35` | Threshold kemiripan (0.0–1.0). 0.35 = 35% |

#### Alur kerja

```
Depth 1:  @target → followers/following → face compare
Depth 2:  @target → followers/following → face compare
                    ↓ (expand)
          followers dari akun dgn similarity tertinggi → face compare lagi
Depth 3:  ... dan seterusnya (BFS)
```

#### Contoh

```bash
# Depth 1: cek followers/following aja
./face-osint search ref.jpg jhonbinsualawu --depth 1 --workers 4

# Depth 2: cek followers, lalu followers-nya followers
./face-osint search ref.jpg target_user --depth 2

# Depth 3: lebih dalem
./face-osint search ref.jpg target_user --depth 3 --threshold 0.3

# Dengan cookie custom
./face-osint --cookie "sessionid=..." search ref.jpg target --depth 2
```

Saat match ditemukan (similarity ≥ threshold), proses **berhenti otomatis** dan menampilkan:
```
  FOUND! @username | 40.89%
  https://instagram.com/username
```

#### Caching

- Followers/following di-cache di `data/` — kalau sudah pernah di-scrape, tidak scrape ulang
- URL foto profil di-skip kalau sudah pernah di-download (hindari duplikasi)
- User yang sudah di-check tidak akan di-check ulang di depth berikutnya

### `list` — Lihat hasil search sebelumnya

```bash
./face-osint list
./face-osint list results/face_search_result.json
```

---

## 3. Threshold & Similarity

Hasil face comparison berupa **cosine similarity** antara 0.0–1.0:
- **0.35+ (35%)** — Match (default)
- **0.25–0.34** — Kemungkinan mirip
- **< 0.25** — Beda orang

Nilai negatif (misal `-3.2%`) berarti embedding vectors berlawanan arah — benar-benar beda.

### Rekomendasi threshold

| Threshold | Kegunaan |
|-----------|----------|
| `0.35` | Default — cukup ketat, minim false positive |
| `0.30` | Lebih longgar, cocok untuk depth 3+ |
| `0.25` | Sangat longgar, banyak false positive |
| `0.40` | Ketat — hampir pasti orang yang sama |

---

## 4. Struktur Tools

```
~/Learn/face-osint/
├── face-osint              # CLI entry point (chmod +x)
├── requirements.txt        # Python dependencies
├── .venv/                  # Virtual environment
├── modules/
│   ├── __init__.py
│   ├── config.py           # Konfigurasi (cookie, threshold, dll)
│   ├── instagram.py        # Instagram scraper (Playwright)
│   ├── face.py             # Face engine (insightface buffalo_l)
│   └── search.py           # BFS recursive search engine
├── data/                   # Hasil scrape & cache
│   ├── username_followers.json
│   ├── username_following.json
│   └── username_profile.jpg
└── results/                # Hasil face search
    └── face_search_result.json
```

---

## 5. Troubleshooting

### "No face detected in reference image"
Foto referensi tidak mengandung wajah yang dikenali insightface. Pastikan foto jelas, tidak blur, dan wajah menghadap depan.

### Instagram rate limit (429)
API Instagram punya rate limit. Solusi:
- Tunggu 15–30 menit
- Gunakan cookie dari session berbeda (akun IG lain)
- Kurangi `--workers` (pakai 2 atau 1)
- Fitur scrape via page navigation sudah built-in sebagai fallback

### "403" saat download foto
Cookie expired. Ambil cookie baru dari browser.

### Virtual environment error
```bash
source .venv/bin/activate   # Linux/Mac
# atau
.venv\Scripts\activate      # Windows
```

---

## 6. Contoh Lengkap

```bash
# Setup
cd ~/Learn/face-osint
source .venv/bin/activate

# 1. Cek 2 foto langsung
./face-osint compare ref.jpg suspect.jpg

# 2. Download foto profil seseorang
./face-osint pic target_user

# 3. Face search depth 2 dengan cookie
./face-osint --cookie "sessionid=..." search ref.jpg target_user \
  --depth 2 --workers 5 --threshold 0.3

# 4. Lihat hasil
./face-osint list
```

---

## 7. Notes

- **Model face recognition:** `buffalo_l` dari insightface (~150MB download pertama)
- **Cookies** expired dalam beberapa jam sampai beberapa hari
- **Tidak ada batasan jumlah expand** — semua akun baru di depth berikutnya akan dicek
- Proses bisa sangat lambat di depth tinggi (puluhan ribu akun)
- Tekan `Ctrl+C` kapan saja untuk menghentikan proses
