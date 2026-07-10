# Keamanan & Rate-Limit

## TL;DR — tool ini TIDAK aman dari rate-limit

face-osint sangat terekspos rate-limit dan ban Instagram. Traversal follower-graph secara bulk dari satu session yang login adalah **persis pola yang di-flag Instagram sebagai bot**. Kodenya sendiri sudah berasumsi rate-limit pasti kena (ada exponential backoff + peringatan di README).

**Jangan pernah menjalankan tool ini dengan akun Instagram pribadi/utama.**

## "Pakai Playwright" ≠ "aman dari rate-limit"

Project ini memang sudah memakai Playwright (browser asli). Itu menyelesaikan **satu** lapisan deteksi saja. Instagram mendeteksi di tiga lapisan:

| Lapisan | Playwright menolong? | Alasan |
|---|---|---|
| **Transport / fingerprint** (TLS/JA3, urutan header) | ✅ Ya | Browser asli = handshake asli. Ini yang membuat client HTTP Python (`requests`/`httpx`) diblok instan. Playwright lolos. |
| **IP** (reputasi, ASN, volume) | ❌ Tidak | Semua traffic tetap keluar dari satu IP. Datacenter IP diblok di request pertama; IP rumah kena throttle saat volume tinggi. |
| **Akun / perilaku** (trust-score, pola baca) | ❌ Tidak | Ini pembunuh sebenarnya. Enumerasi follower-list linier lintas banyak node = pola bot. Yang kena flag adalah `sessionid`-mu, bukan browsernya. |

**Rate-limit itu berbasis perilaku + akun + IP, bukan berbasis alat.** Playwright mengangkat kualitas transport ke level browser asli (itu sebabnya arsitektur ini "benar"), tapi tidak menyentuh sama sekali risiko trust-akun.

## Model volume request

Per akun yang **dicek**: konteks browser baru + navigasi ke `/` + XHR `web_profile_info` + fetch gambar ≈ **3 request/akun**. Per akun yang **di-expand**: ~2 navigasi + puluhan XHR list.

Dengan followers cap 100, following cap 500, workers 3:

| Depth | Estimasi request | Kenapa |
|---|---|---|
| **1** | **~10³** | Hanya layer-0; Phase 2 di-skip (`search.py`, `depth <= 1`). |
| **2** | **~10⁵** | **Setiap akun non-match di-expand** — fan-out ~600/akun. |
| **3** | **~10⁶–10⁷** | Dua generasi expansion, tanpa cap dan tanpa budget. Praktis unbounded. |

Instagram meng-action-block klien tidak resmi jauh di bawah ~1.000 hit profil/graph per hari. **Bahkan depth 1 sudah melewati garis aman; depth 2–3 katastrofik.**

## Mitigasi yang sudah ada

Sejak rate-limit hardening (`modules/ratelimit.py`, wired ke `instagram.py`/`search.py`/CLI), tool ini punya pertahanan di **laju** dan **berhenti otomatis**, bukan cuma pengurangan jumlah:

- **Global rate limiter** (`RateLimiter`, flag `--rate`, default 20 req/menit, `0`=mati) — memaksa jarak minimum antar-request di seluruh run, bukan cuma per-worker.
- **Jitter delay acak** (`jittered_delay`, flag `--delay-min`/`--delay-max`, default 1.0–3.0s) — menggantikan delay fixed lama; laju tidak lagi teratur secara mencolok.
- **Deteksi soft-block + hard-stop** (`detect_soft_block`/`SoftBlockError`) — login-redirect, `checkpoint_required`, `challenge_required`, `feedback_required` di body langsung menghentikan search (tidak retry-loop). Muncul di CLI sebagai `STOPPED early (safety): ...`.
- **Request budget per-run** (`RequestBudget`, flag `--max-requests`, default 800) — search berhenti otomatis begitu total request lintas semua worker melampaui budget.
- **Expansion cap per layer** (`cap_expansions`, flag `--max-expand`, default 15) — fan-out BFS di-cap per layer, bukan lagi unbounded.
- **Adaptive backoff cap 300s** (`backoff_delay`, `config.BACKOFF_CAP`) pada 429 — naik dari cap 30s lama yang terlalu rendah untuk cooldown IG (bisa menit–jam).
- Cache disk followers/following + `--no-cache` untuk memaksa re-scrape.
- Set dedup `checked_users` / `checked_urls` / `expanded_users`.
- Early-stop saat match (cancel semua task in-flight).
- `skip_home` di jalur hot.
- Page-size 50 (minimum jumlah request untuk list tertentu).

Catatan: default `--rate`/`--max-requests`/`--max-expand` mengurangi risiko secara signifikan dibanding sebelum hardening, tapi **tidak menghilangkan** risiko ban — lihat "Faktor risiko" dan "Playbook" di bawah untuk apa yang masih harus dilakukan manual (akun burner, IP residensial, dst).

Lingkup: limiter/budget/soft-block-stop di atas mengatur seluruh jalur perintah `search` (termasuk seed-scrape layer-0 dan `--depth 0`, sejak semuanya berbagi `limiter`/`budget` yang sama). Perintah `pic`/`scrape` yang dijalankan berdiri sendiri (di luar `search`) tetap tidak diatur budget/limiter — volumenya rendah (satu-dua request per invocation) sehingga dianggap di luar scope hardening ini.

## Faktor risiko (kritis)

- **Single sessionid/cookie** untuk seluruh burst — satu identitas menyerap semua traffic. *(belum dimitigasi — di luar scope hardening ini; butuh multi-akun/proxy, lihat playbook)*
- **Tanpa proxy / IP rotation** di mana pun. *(belum dimitigasi — deferred, lihat "Known limitation" di bawah)*
- **Global adaptive backoff belum cross-worker** — tiap worker mundur sendiri-sendiri saat 429; belum ada jeda bersama lintas-worker (deferred, scope B).
- Dead code `_api_followers`/`_api_following`; knob `PAGE_WAIT` didefinisikan tapi tak dipakai.

~~BFS expansion unbounded~~, ~~delay fixed~~, dan ~~hanya HTTP 429 dianggap throttle~~ — **sudah diperbaiki** oleh expansion cap, jitter delay, dan `detect_soft_block` di atas.

## Realita Instagram (2024–2026)

> Instagram/Meta tidak mem-publish angka resmi untuk private endpoint ini. Angka di bawah = observasi vendor / kode library / laporan komunitas. Arahnya high-confidence walau angkanya perkiraan.

- Throttling saat login = gabungan **akun + session + IP**, bukan satu sumbu.
- **Enumerasi daftar follower/following = read dengan toleransi paling rendah.** Pola BFS tool ini menghantam persis endpoint itu.
- Meta **secara resmi men-disable akun** karena scraping ("disabling accounts… blocked billions of suspected unauthorized scraping actions per day").
- Laporan first-person: ban setelah **~20–47 profil** di beberapa kasus; enumerasi ~110k follower → checkpoint + paksa reset password.
- Escalation umum: `429 ClientThrottledError` → `PleaseWaitFewMinutes` → `feedback_required` (cooldown 24–72 jam) → `challenge_required`/`checkpoint_required` (verifikasi/reset) → disable.
- Putusan *Meta v. Bright Data* (2024) hanya melindungi scraping **logged-out** yang publik — tool ini logged-in, **tidak** terlindungi.

**Sumber utama:**

- OFFICIAL — Meta: <https://www.meta.com/actions/privacy-progress/>
- CREDIBLE — HikerAPI (limit per-endpoint, ekonomi burner): <https://hikerapi.com/help/instagram-scraping-without-getting-blocked>
- CREDIBLE — Scrapfly (threshold, fingerprint): <https://scrapfly.io/blog/posts/how-to-scrape-instagram>
- COMMUNITY — instaloader #2512 (ban dari enumerasi follower): <https://github.com/instaloader/instaloader/issues/2512>

## Playbook pakai (se-)aman(-mungkin)

Kalau tool ini tetap harus dijalankan:

1. **Akun burner khusus** — jangan akun pribadi/utama. Anggap barang habis pakai (vendor melaporkan 5–15% kehilangan akun/minggu bahkan saat hati-hati). *(manual — di luar scope tool)*
2. **IP residensial per akun** — bukan datacenter IP (diblok request pertama). Jangan berbagi satu IP untuk banyak akun ("chain ban"). *(manual — belum ada dukungan proxy di tool)*
3. **Delay acak 1–3s+** antar aksi, bukan delay fixed. ✅ **Sudah default** (`--delay-min`/`--delay-max`, default 1.0–3.0s) + global pacing `--rate` (default 20/menit).
4. **Budget < ~150 read/jam**, dijauhkan dari paginasi follower-list; jalankan dengan jeda (bukan kontinu). Sebagian termitigasi oleh `--max-requests` (default 800/run) — tapi itu budget per-run, bukan per-jam; tetap atur jeda antar-run secara manual.
5. **Hard-stop pada `PleaseWaitFewMinutes` / `feedback_required`** — jangan retry-loop. ✅ **Sudah default**: `detect_soft_block` + `SoftBlockError` menghentikan search seketika (`STOPPED early (safety): ...`), tidak pernah retry-loop menembus soft-block.
6. **Batasi jumlah expansion per layer** dan hindari `--depth` tinggi. ✅ **Sudah default** (`--max-expand`, default 15/layer). Depth 1 saja tetap paling aman — cap ini mengurangi fan-out di depth ≥2, bukan menghilangkan risikonya.
7. **Pertahankan Playwright** — transport browser asli menghindari blok instan berbasis fingerprint (satu-satunya keunggulan yang sudah dimiliki tool ini). Jangan turunkan ke raw HTTP. *(tidak berubah — tetap wajib)*

## Etika & legal

Tool ini melakukan **scraping** (melanggar ToU Instagram) dan **face-recognition terhadap orang tanpa consent**. Konsekuensi hukum, privasi, dan etika sepenuhnya menjadi tanggung jawab pemakai. Gunakan hanya dalam konteks yang sah dan berizin.

---

*Ringkasan riset ini berasal dari investigasi multi-agent 2026-07-10 (kode + riset eksternal). Catatan tersimpan di memory project `rate-limit-analysis`.*
