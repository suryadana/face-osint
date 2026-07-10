# Dokumentasi face-osint

face-osint adalah CLI OSINT toolkit yang mencari sebuah wajah target di seluruh **social graph Instagram**. Diberi foto referensi dan sebuah username awal, tool ini melakukan scraping followers/following, mengunduh foto profil, dan menjalankan face comparison secara rekursif (BFS) sampai menemukan match di atas ambang kemiripan.

> ⚠️ **PERINGATAN — BACA DULU**
>
> - **Risiko ban akun tinggi.** Pola akses tool ini (enumerasi follower-list + bulk profile view dari satu session) adalah pola yang paling gampang di-flag Instagram. Akun yang dipakai bisa kena throttle → challenge → **disable permanen**, dan IP rumah bisa ikut kena. **Jangan pakai akun utama/pribadi.**
> - **Melanggar Terms of Use Instagram.** Automated data collection tanpa izin tertulis dilarang oleh ToU Meta.
> - **Dimensi etika.** Tool ini melakukan face-recognition terhadap orang tanpa consent. Tanggung jawab dan konsekuensi hukum sepenuhnya ada di pemakai. Gunakan hanya untuk konteks yang sah/berizin.
>
> Detail lengkap + cara pakai seaman mungkin: **[keamanan-dan-rate-limit.md](keamanan-dan-rate-limit.md)**.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m playwright install chromium        # wajib — scraping pakai Chromium
./face-osint search ref.jpg <username> --depth 1
```

## Daftar isi

| Dokumen | Isi |
|---|---|
| [instalasi.md](instalasi.md) | Setup environment, dependency, model, dan cookie Instagram |
| [penggunaan.md](penggunaan.md) | Referensi semua command (`compare`, `pic`, `scrape`, `search`, `list`) + opsi |
| [arsitektur.md](arsitektur.md) | Cara kerja internal: 4 modul, alur BFS, diagram (untuk developer) |
| [keamanan-dan-rate-limit.md](keamanan-dan-rate-limit.md) | ⭐ Risiko ban, model volume request, playbook pakai aman |
| [troubleshooting.md](troubleshooting.md) | Solusi error umum (429, no-face, cookie expired, dll.) |

## Ringkas

- **Scraping engine:** Playwright (headless Chromium) — semua request lewat browser context, bukan raw HTTP.
- **Face recognition:** insightface `buffalo_l` (cosine similarity).
- **Mesin pencarian:** BFS rekursif di social graph, berhenti otomatis saat match ditemukan.
- **Rate-limit-bound:** kalau terasa "hang", biasanya itu backoff 429, bukan bug.
