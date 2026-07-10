# Penggunaan

Semua command dijalankan lewat script `face-osint`. Flag cookie global (jika dipakai) diletakkan **sebelum** subcommand — lihat [instalasi.md](instalasi.md).

```
./face-osint <command> [args] [options]
```

| Command | Fungsi |
|---|---|
| `compare` | Bandingkan dua gambar wajah (cosine similarity) |
| `pic` | Download foto profil sebuah username |
| `scrape` | Simpan daftar followers/following ke JSON |
| `search` | Face search BFS (inti tool) |
| `list` | Tampilkan hasil search yang tersimpan |

---

## `compare` — bandingkan dua wajah

```bash
./face-osint compare ref.jpg target.jpg
```

Output:

```
  Reference: ref.jpg
  Target:    target.jpg
  Similarity: 44.65%
  Threshold:  35%
  Match:      YES
```

Tidak butuh cookie/jaringan. Kalau salah satu gambar tidak mengandung wajah yang terdeteksi, keluar dengan error "No face detected".

---

## `pic` — download foto profil

```bash
./face-osint pic <username>
./face-osint --cookie "sessionid=..." pic <username>
```

Foto tersimpan di `modules/data/<username>_profile.jpg` (lihat catatan lokasi output di bawah).

---

## `scrape` — followers/following

```bash
./face-osint scrape <username>
```

Tersimpan sebagai:

- `modules/data/<username>_followers.json`
- `modules/data/<username>_following.json`

Scraping dilakukan dengan men-scroll modal followers/following di halaman (via Playwright), dengan cap **100 followers / 500 following**. Kalau kena rate-limit, tunggu atau ganti session.

---

## `search` — face search BFS (inti)

```bash
./face-osint search <ref_image> <username> [options]
```

### Opsi

| Opsi | Default | Keterangan |
|---|---|---|
| `--depth N` | `1` | Kedalaman graph. 1 = followers/following target; 2 = plus teman-temannya; dst. |
| `--workers N` | `3` | Jumlah worker paralel untuk face comparison |
| `--threshold X` | `0.35` | Ambang kemiripan 0–1 (**lihat jebakan di bawah**) |
| `--no-cache` | — | Abaikan cache, scrape ulang followers/following |
| `--posts N` | `3` | Jumlah post terbaru yang di-sample per akun selain foto profil (`0` = foto profil saja) |
| `--rate N` | `20` | Global read pace, request/menit. `0` = mati (tanpa pacing) |
| `--max-requests N` | `800` | Budget request per-run. Search berhenti otomatis (`STOPPED early`) begitu terlampaui |
| `--max-expand N` | `15` | Maksimum akun yang di-expand per layer BFS (cap fan-out) |
| `--delay-min X` / `--delay-max X` | `1.0` / `3.0` | Rentang delay jitter (detik) antar aksi, di atas pacing `--rate` |

### Contoh

```bash
# Depth 1 — cek followers/following target saja
./face-osint search ref.jpg target --depth 1 --workers 4

# Depth 2 — plus followers/following dari akun non-match
./face-osint search ref.jpg target --depth 2

# Dengan cookie custom
./face-osint --cookie "sessionid=..." search ref.jpg target --depth 2

# Dengan rate-limit hardening custom (pace lebih pelan, budget lebih kecil)
./face-osint search ref.jpg target --depth 1 --rate 10 --max-requests 300 --max-expand 5
```

Saat sebuah akun mencapai ambang match, proses **berhenti otomatis**:

```
  FOUND! @username  |  40.89%
  https://instagram.com/username
```

Proses juga bisa **berhenti otomatis demi keamanan** (bukan karena match) kalau budget request habis atau Instagram mengembalikan soft-block (checkpoint/challenge/login-redirect). Dalam kasus ini tidak ada retry-loop — search langsung berhenti dan mencetak:

```
  STOPPED early (safety): request budget exceeded: 801 > 800
```

> ⚠️ **Baca [keamanan-dan-rate-limit.md](keamanan-dan-rate-limit.md) sebelum memakai `--depth 2` atau lebih.** Volume request meledak secara eksponensial dan hampir pasti berujung ban akun. `--rate`/`--max-requests`/`--max-expand` mengurangi risiko tapi tidak menghilangkannya.

### ⚠️ Jebakan: `--threshold` tidak menghentikan search

Nilai `--threshold` di CLI **hanya** memengaruhi print summary dan marker `<<<` pada output. Yang benar-benar menghentikan pencarian saat match adalah konstanta `config.SIM_THRESHOLD` (default `0.35`).

Untuk mengubah cutoff match yang sebenarnya, ubah `config.SIM_THRESHOLD` di `modules/config.py` (atau wire nilai CLI ke `BFSSearch`).

### Agregasi profil + post (`--posts`)

Tiap akun dicek dengan foto profil **plus** hingga `--posts N` post terbaru (default 3). Skor per-gambar diambil dari wajah dengan similarity tertinggi di gambar itu (`max_similarity_to_ref`), lalu di-agregasi lintas gambar:

- **Ranking** memakai skor **maksimum** di antara semua gambar yang dicek (foto profil + post).
- **Auto-stop match** memakai **konsensus**: butuh minimal `config.CONSENSUS_MIN` (default 2) gambar berbeda yang similarity-nya ≥ `config.SIM_THRESHOLD`, bukan cuma satu gambar.
- Sampling **berhenti lebih awal** begitu konsensus tercapai — post berikutnya tidak diunduh/dicek lagi untuk akun itu.
- `--posts 0` mengembalikan ke perilaku lama (cuma foto profil, back-compat).

---

## `list` — lihat hasil search

```bash
./face-osint list
./face-osint list path/ke/face_search_result.json
```

Tanpa argumen, membaca `modules/results/face_search_result.json`. Menampilkan total akun dicek, jumlah wajah terdeteksi, status match, dan top matches.

---

## Catatan lokasi output (penting)

`config.py` menghitung `DATA_DIR` dan `RESULTS_DIR` relatif terhadap folder **`modules/`**, jadi output nyata mendarat di:

- `modules/data/` — cache followers/following + foto profil
- `modules/results/` — `face_search_result.json`

**Bukan** `data/`/`results/` di root repo. Keduanya di-gitignore. Ingat ini saat mencari file cache/hasil.

## Caching

`search` memakai ulang `<username>_followers.json` / `<username>_following.json` dari `modules/data/` kecuali `--no-cache` diberikan. Di dalam satu run, set `checked_users` / `checked_urls` / `expanded_users` mencegah pengecekan ulang akun antar-depth.
