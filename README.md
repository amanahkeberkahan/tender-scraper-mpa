# Tender Scraper MPA — Tahap Investigasi Endpoint

## Kenapa ada folder ini

Sesi Claude Code yang mengerjakan ini berjalan di sandbox tanpa akses internet
publik (hanya whitelist npm/pypi/GitHub/dll), jadi langkah "inspect Network
tab di browser" dari brief tidak bisa dijalankan langsung oleh Claude. Sebagai
gantinya, dibuat `probe_endpoints.py` — skrip yang menggantikan proses inspeksi
manual itu, dijalankan otomatis dari mesin yang PUNYA akses internet.

## Langkah selanjutnya (Pak Mario)

1. Jalankan di komputer / server / Codespace yang punya akses internet:
   ```bash
   cd tender-scraper-mpa
   pip install -r requirements.txt
   python probe_endpoints.py
   ```
2. Skrip akan mencoba ~20 kombinasi pola endpoint x metode (GET/POST) untuk
   4 portal (Surabaya, Jatim Prov, PU, LKPP), plus membaca inline JavaScript
   di halaman HTML asli untuk mencari petunjuk endpoint sesungguhnya.
3. Kirim balik isi file `probe_report.md` yang dihasilkan (atau upload filenya)
   ke sesi Claude Code ini / sesi lanjutan.
4. Dari situ modul fetcher produksi (`fetcher.py`, Python) akan dibangun
   berdasarkan pola endpoint yang TERBUKTI jalan — bukan asumsi lagi.

## Yang sudah disiapkan sambil menunggu hasil probe

- `probe_endpoints.py` — skrip diagnostic (siap jalan, hanya butuh `requests`).
- Daftar portal & filter kata kunci relevansi sudah dipindah dari MVP
  `TenderScraper_MPA_FINAL.gs` sebagai referensi konfigurasi arsitektur baru.

## Yang BELUM dibangun (menunggu hasil probe)

- `fetcher.py` — modul tarik data produksi.
- `storage.py` — lapisan SQLite (ganti Google Sheet), dedup by ID tender.
- `notify.py` — Email/Telegram/WhatsApp (logika bisa direplikasi dari MVP).
- `scheduler` — cron / GitHub Actions.
- Dashboard web (opsional, fase berikut).

Arsitektur tetap modular sesuai keputusan di brief: fetcher terpisah dari
storage & notifikasi, supaya nanti gampang beralih dari Jalur B (scraping)
ke Jalur A (API resmi LKPP Data Integrator) tanpa bongkar semua.
