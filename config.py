"""
KONFIGURASI — Tender Scraper MPA

Kredensial (password email, token bot) TIDAK ditaruh di sini -- diambil dari
environment variable / file .env, supaya tidak ke-commit ke GitHub (repo
publik/private tetap sebaiknya bebas dari secret).
"""

import os

PORTAL_LPSE = [
    {"nama": "LPSE Kota Surabaya", "kode": "surabaya"},
    {"nama": "LPSE Provinsi Jawa Timur", "kode": "jatimprov"},
    {"nama": "LPSE Kementerian PU", "kode": "pu"},
    {"nama": "LPSE LKPP", "kode": "lkpp"},
    # --- Ditambahkan atas permintaan, kode BELUM diverifikasi langsung
    # (sandbox tidak bisa akses internet) -- tes dulu satu-satu pakai
    # `python fetcher.py <kode>` sebelum diandalkan penuh. Kalau salah,
    # main.py cuma akan cetak "GAGAL" untuk portal itu tanpa mengganggu
    # portal lain, jadi aman dicoba.
    {"nama": "LPSE Kabupaten Sidoarjo", "kode": "sidoarjokab"},
    {"nama": "LPSE Kabupaten Gresik", "kode": "gresikkab"},
    {"nama": "LPSE Kota Malang", "kode": "malangkota"},
    # Kementerian Pariwisata -- banyak tender event/pameran/booth/dekorasi,
    # relevan untuk lini bisnis event management MPA.
    {"nama": "LPSE Kementerian Pariwisata", "kode": "kemenpar"},
]

KATA_KUNCI_RELEVAN = [
    "konstruksi", "bangunan", "gedung", "renovasi", "rehabilitasi",
    "interior", "fit out", "fitting out", "furniture", "mebel", "meubelair",
    "pembangunan", "pemeliharaan gedung", "finishing", "partisi",
    "event", "pameran", "booth", "dekorasi", "panggung",
    "mekanikal", "elektrikal", "plumbing", "hvac",
    # Istilah event/pameran internasional (banyak dipakai Kemenpar,
    # Kemendag, dan kementerian lain untuk tender expo luar negeri)
    "fair", "expo", "exhibition", "pavilion", "paviliun",
    "konvensi", "convention", "gala", "seremoni",
]

HPS_MINIMUM = 0  # 0 = tampilkan semua. Contoh: 200_000_000 = hanya >= 200 juta.

MAKS_BARIS_PER_PORTAL = 300
JEDA_ANTAR_PORTAL_DETIK = 2.0

DB_PATH = os.path.join(os.path.dirname(__file__), "tender.db")

# ---- EMAIL (SMTP Gmail) ----
EMAIL_AKTIF = os.environ.get("EMAIL_AKTIF", "true").lower() == "true"
EMAIL_PENGIRIM = os.environ.get("EMAIL_PENGIRIM", "")       # alamat Gmail pengirim
EMAIL_APP_PASSWORD = os.environ.get("EMAIL_APP_PASSWORD", "")  # App Password Gmail (bukan password login biasa)
EMAIL_TUJUAN = os.environ.get("EMAIL_TUJUAN", "multipowerabadi@gmail.com")
EMAIL_CC = os.environ.get("EMAIL_CC", "sekre.multipowerabadi@gmail.com")

# ---- TELEGRAM (opsional) ----
TELEGRAM_AKTIF = os.environ.get("TELEGRAM_AKTIF", "false").lower() == "true"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# ---- DASHBOARD ProjectFlow (project.multipowerabadi.co.id) ----
DASHBOARD_AKTIF = os.environ.get("DASHBOARD_AKTIF", "true").lower() == "true"
DASHBOARD_API_URL = os.environ.get(
    "DASHBOARD_API_URL", "https://project.multipowerabadi.co.id/tender_import.php"
)
DASHBOARD_API_KEY = os.environ.get("DASHBOARD_API_KEY", "")
