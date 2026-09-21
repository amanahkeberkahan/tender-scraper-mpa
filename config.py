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
]

KATA_KUNCI_RELEVAN = [
    "konstruksi", "bangunan", "gedung", "renovasi", "rehabilitasi",
    "interior", "fit out", "fitting out", "furniture", "mebel", "meubelair",
    "pembangunan", "pemeliharaan gedung", "finishing", "partisi",
    "event", "pameran", "booth", "dekorasi", "panggung",
    "mekanikal", "elektrikal", "plumbing", "hvac",
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

# ---- TELEGRAM (opsional) ----
TELEGRAM_AKTIF = os.environ.get("TELEGRAM_AKTIF", "false").lower() == "true"
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
