#!/usr/bin/env python3
"""
MAIN — Tender Scraper MPA

Orkestrator: tarik semua portal -> filter yang baru & relevan -> simpan ke
SQLite -> kirim notifikasi. Ini yang dipanggil terjadwal (Windows Task
Scheduler / cron), padanan `cekTenderSekarang()` di MVP Google Apps Script.

WAJIB dijalankan dari jaringan residensial (bukan cloud/VPS/CI) -- LPSE
memblokir IP cloud lewat Cloudflare (sudah dikonfirmasi lewat investigasi).
"""

import time
from datetime import datetime

import config
import dashboard
import notify
import storage
from fetcher import EndpointTidakDitemukan, tarik_tender_portal

import requests


def tahapan_selesai(tahapan: str) -> bool:
    """Sama logikanya seperti dashboard (app.js tenderTahapanSelesai) --
    tender yang tahapannya mengandung 'selesai'/'gagal'/'batal' berarti
    prosesnya sudah tutup, tidak bisa diikuti lagi. Tidak perlu bikin
    tim ribut soal tender yang sudah lewat."""
    t = (tahapan or "").lower()
    return "selesai" in t or "gagal" in t or "batal" in t


def main():
    mulai = time.time()
    print(f"=== Tender Scraper MPA -- {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")

    conn = storage.buka_koneksi(config.DB_PATH)
    id_tersimpan = storage.ambil_id_tersimpan(conn)

    total_baru = 0
    tender_baru_relevan = []

    for portal in config.PORTAL_LPSE:
        print(f"\n[{portal['nama']}] menarik data...")
        try:
            daftar = tarik_tender_portal(
                portal["kode"], config.KATA_KUNCI_RELEVAN,
                maks_baris=config.MAKS_BARIS_PER_PORTAL,
            )
            print(f"[{portal['nama']}] {len(daftar)} tender diterima dari server.")

            baru_di_portal_ini = 0
            tender_baru_portal_ini = []
            waktu_temu = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for t in daftar:
                if t.id_unik in id_tersimpan:
                    continue
                if config.HPS_MINIMUM > 0 and t.hps > 0 and t.hps < config.HPS_MINIMUM:
                    continue

                id_tersimpan.add(t.id_unik)
                storage.simpan_tender(conn, t, portal["nama"])
                total_baru += 1
                baru_di_portal_ini += 1
                tender_baru_portal_ini.append(t)
                if t.relevan:
                    tender_baru_relevan.append(t)

            print(f"[{portal['nama']}] {baru_di_portal_ini} tender BARU disimpan.")

            dashboard.kirim_ke_dashboard(tender_baru_portal_ini, portal["nama"], waktu_temu)

        except EndpointTidakDitemukan as e:
            print(f"[{portal['nama']}] GAGAL -- struktur endpoint berubah: {e}")
        except requests.exceptions.RequestException as e:
            print(f"[{portal['nama']}] GAGAL koneksi: {e}")
        except (ValueError, KeyError) as e:
            print(f"[{portal['nama']}] GAGAL parsing respons: {e}")

        time.sleep(config.JEDA_ANTAR_PORTAL_DETIK)

    tender_untuk_email = [t for t in tender_baru_relevan if not tahapan_selesai(t.tahapan)]
    if tender_untuk_email:
        dilewati = len(tender_baru_relevan) - len(tender_untuk_email)
        print(f"\nMengirim notifikasi untuk {len(tender_untuk_email)} tender relevan & masih aktif "
              f"({dilewati} dilewati karena sudah selesai/gagal)...")
        notify.kirim_notifikasi(tender_untuk_email)

    conn.close()
    durasi = time.time() - mulai
    print(f"\n=== Selesai. Total baru: {total_baru} (relevan: {len(tender_baru_relevan)}). "
          f"Durasi: {durasi:.1f}s ===")


if __name__ == "__main__":
    main()
