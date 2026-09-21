"""
DASHBOARD — Tender Scraper MPA

Kirim data tender ke dashboard web ProjectFlow (project.multipowerabadi.co.id)
lewat endpoint tender_import.php. Terpisah dari notify.py -- ini "menulis ke
database pusat", bukan notifikasi ke manusia.
"""

import requests

import config


def kirim_ke_dashboard(tender_list: list, portal_nama: str, ditemukan_pada: str) -> None:
    """tender_list: list[fetcher.Tender]. Dikirim per-portal karena Tender
    tidak membawa nama portal di dalam dirinya sendiri (lihat fetcher.py)."""
    if not config.DASHBOARD_AKTIF:
        return
    if not tender_list:
        return
    if not config.DASHBOARD_API_URL or not config.DASHBOARD_API_KEY:
        print("[DASHBOARD] Dilewati: DASHBOARD_API_URL / DASHBOARD_API_KEY belum diset.")
        return

    payload = [
        {
            "id_unik": t.id_unik,
            "portal": portal_nama,
            "kode": t.kode,
            "nama_paket": t.nama_paket,
            "instansi": t.instansi,
            "tahapan": t.tahapan,
            "hps": t.hps,
            "info_tambahan": t.jadwal,
            "link": t.link,
            "relevan": t.relevan,
            "ditemukan_pada": ditemukan_pada,
        }
        for t in tender_list
    ]

    try:
        resp = requests.post(
            config.DASHBOARD_API_URL,
            json=payload,
            headers={"X-API-Key": config.DASHBOARD_API_KEY, "Content-Type": "application/json"},
            timeout=30,
        )
        try:
            data = resp.json()
        except ValueError:
            print(f"[DASHBOARD] GAGAL: respons bukan JSON valid (HTTP {resp.status_code}) - {resp.text[:150]}")
            return

        if resp.status_code == 200 and data.get("berhasil"):
            print(f"[DASHBOARD] {portal_nama}: {data.get('disimpan', 0)} baru, "
                  f"{data.get('diperbarui', 0)} diperbarui, {data.get('dilewati', 0)} dilewati.")
        else:
            print(f"[DASHBOARD] GAGAL ({portal_nama}): HTTP {resp.status_code} - {data.get('pesan', '')}")
    except requests.exceptions.RequestException as e:
        print(f"[DASHBOARD] GAGAL koneksi ({portal_nama}): {e}")
