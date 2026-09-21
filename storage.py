"""
STORAGE — Tender Scraper MPA

Lapisan penyimpanan SQLite, gantinya Google Sheet di MVP. Tanggung jawab
tunggal: simpan & cek dedup by ID tender. Terpisah dari fetcher.py dan
notify.py supaya nanti gampang diganti (mis. ke PostgreSQL) tanpa bongkar
modul lain.
"""

import sqlite3
from datetime import datetime

SKEMA = """
CREATE TABLE IF NOT EXISTS tender (
    id_unik      TEXT PRIMARY KEY,
    portal       TEXT NOT NULL,
    kode         TEXT,
    nama_paket   TEXT NOT NULL,
    instansi     TEXT,
    tahapan      TEXT,
    hps          INTEGER,
    jadwal       TEXT,
    link         TEXT,
    relevan      INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'baru',
    pic          TEXT,
    catatan      TEXT,
    ditemukan_pada TEXT NOT NULL
);
"""


def buka_koneksi(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(SKEMA)
    conn.commit()
    return conn


def ambil_id_tersimpan(conn: sqlite3.Connection) -> set:
    return {row[0] for row in conn.execute("SELECT id_unik FROM tender")}


def simpan_tender(conn: sqlite3.Connection, tender, portal_nama: str):
    conn.execute(
        """INSERT OR IGNORE INTO tender
           (id_unik, portal, kode, nama_paket, instansi, tahapan, hps, jadwal,
            link, relevan, ditemukan_pada)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (tender.id_unik, portal_nama, tender.kode, tender.nama_paket,
         tender.instansi, tender.tahapan, tender.hps, tender.jadwal,
         tender.link, int(tender.relevan),
         datetime.now().strftime("%Y-%m-%d %H:%M")),
    )
    conn.commit()


def update_status(conn: sqlite3.Connection, id_unik: str, status: str = None,
                   pic: str = None, catatan: str = None):
    """Untuk kolom pipeline keputusan (Minat/Ikut/Lewati, PIC, catatan) --
    dipanggil dari dashboard, bukan dari fetcher."""
    kolom, nilai = [], []
    if status is not None:
        kolom.append("status = ?"); nilai.append(status)
    if pic is not None:
        kolom.append("pic = ?"); nilai.append(pic)
    if catatan is not None:
        kolom.append("catatan = ?"); nilai.append(catatan)
    if not kolom:
        return
    nilai.append(id_unik)
    conn.execute(f"UPDATE tender SET {', '.join(kolom)} WHERE id_unik = ?", nilai)
    conn.commit()
