# Tender Scraper MPA

Sistem pemantau tender LPSE untuk PT Multi Power Abadi. Menarik data dari
beberapa portal LPSE (SPSE/INAPROC), menyaring yang relevan dengan lini
bisnis MPA (konstruksi, interior, renovasi, event), simpan ke database lokal
(dedup otomatis), dan kirim notifikasi email saat ada tender baru relevan.

## Temuan penting (jangan dilupakan saat develop lanjut)

1. **LPSE (`spse.inaproc.id`) memblokir IP cloud/datacenter lewat Cloudflare.**
   Dikonfirmasi: request dari GitHub Codespaces selalu 403 (bahkan halaman
   HTML biasa), tapi dari IP residensial (laptop/kantor biasa) normal.
   **Konsekuensi: skrip ini WAJIB dijalankan dari jaringan residensial** --
   bukan GitHub Actions, bukan VPS biasa, bukan Codespaces. Untuk sekarang
   dijalankan dari laptop pribadi Pak Mario via Windows Task Scheduler.
   Opsi jangka panjang (mini PC kantor / proxy residential) didiskusikan
   terpisah kalau mau full-otomatis tanpa tergantung laptop pribadi.

2. **Endpoint asli**: `POST https://spse.inaproc.id/<kode>/dt/lelang?tahun=<tahun>`,
   format DataTables server-side. Butuh `authenticityToken` yang diambil
   ulang dari halaman `/<kode>/lelang` setiap kali jalan (bukan statis) --
   lihat `fetcher.py::_ambil_konfigurasi_ajax`. Tahun anggaran juga tidak
   di-hardcode, diambil dari halaman saat runtime (beda portal bisa beda
   tahun aktif).

3. **Struktur kolom respons** (dikonfirmasi lewat `python fetcher.py <kode> --debug`):
   `0`=kode tender, `1`=nama paket, `2`=instansi, `3`=tahapan,
   `4`=HPS dibulatkan (JANGAN dipakai, mis. "60,2 M"), `8`=kategori+tahun
   anggaran, `10`=**HPS presisi penuh** (format `Rp. 57.446.418.426,00` --
   titik=ribuan, koma=desimal, kebalikan format Inggris).

## Struktur file

- `fetcher.py` — tarik data dari 1 portal (bisa dites langsung: `python fetcher.py surabaya`)
- `storage.py` — simpan ke SQLite (`tender.db`), dedup by ID tender
- `notify.py` — kirim email (+ Telegram opsional) saat ada tender baru relevan
- `config.py` — daftar portal, kata kunci relevansi, baca kredensial dari env var
- `main.py` — orkestrator, ini yang dijadwalkan jalan otomatis
- `probe_endpoints.py` — skrip diagnostic (sudah tidak perlu dipakai lagi kecuali LPSE ganti struktur lagi)

## Setup

### 1. Install dependency
```
pip install -r requirements.txt
```

### 2. Setup kredensial email (App Password Gmail, BUKAN password login biasa)
1. Buka https://myaccount.google.com/apppasswords (butuh 2FA aktif di akun Gmail pengirim)
2. Buat App Password baru, nama bebas (mis. "Tender Scraper MPA")
3. Copy 16 digit password yang muncul
4. Set sebagai environment variable (Command Prompt):
   ```
   setx EMAIL_PENGIRIM "alamat-pengirim@gmail.com"
   setx EMAIL_APP_PASSWORD "16digitapppassword"
   ```
   (`setx` menyimpan permanen, tapi baru berlaku di Command Prompt yang dibuka SETELAHNYA)

### 3. Tes jalan manual
```
python main.py
```

### 4. Jadwalkan otomatis (Windows Task Scheduler)
1. Buka **Task Scheduler** (cari lewat Start Menu)
2. **Create Task** > kasih nama "Tender Scraper MPA"
3. Tab **Triggers** > New > Daily, atur jam 08:00 (buat trigger kedua untuk 17:00)
4. Tab **Actions** > New > Program: `python`, Arguments: `main.py`,
   Start in: folder tempat `tender-scraper-mpa` berada
5. Tab **Conditions**: uncheck "Start the task only if the computer is on AC power"
   kalau laptop sering pakai baterai
6. Save

## Belum dibangun (fase berikutnya)

- Dashboard web (opsional -- untuk sekarang bisa query `tender.db` langsung,
  atau pakai DB Browser for SQLite untuk lihat isinya)
- Kolom pipeline (status Minat/Ikut/Lewati, PIC, deadline) -- skema sudah
  disiapkan di `storage.py` (`update_status()`), tinggal UI-nya
- Jalur A resmi (API LKPP Data Integrator) -- proses administrasi terpisah,
  lihat brief awal
