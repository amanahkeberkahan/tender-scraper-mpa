#!/usr/bin/env python3
"""
IAPRO INJOURNEY AIRPORTS — Tender Scraper MPA
==============================================

Portal procurement InJourney Airports (eks Angkasa Pura I & II, grup BUMN
Danantara). Seperti Zinit: bukan daftar tender publik, tapi UNDANGAN TENDER
privat yang ditujukan ke akun vendor MPA yang sudah terdaftar.

Jauh lebih simpel dari Zinit -- tidak perlu Playwright/browser otomatis,
cukup `requests` biasa:
  1. POST /v1/api/login dengan {username, password} -> dapat `sso_token`
     (format Laravel Sanctum "id|hash") dan `groupId` dari user yang login.
  2. GET /v1/api/rekanan/packet-invitation-list dengan header
     `Authorization: Bearer <sso_token>` + `Groupid: <groupId>`.

Catatan: situs ini mendeteksi & memblokir DevTools lewat JS (overlay
"Developer Tools terdeteksi! Akses diblokir.") -- tidak relevan untuk
scraper (kita bukan browser), cuma catatan kalau nanti perlu investigasi
ulang manual via DevTools (buka DevTools SEBELUM halaman dimuat).
"""

import time

import requests

from fetcher import Tender, cek_relevan

BASE_URL = "https://iaproc.injourneyairports.id"
LOGIN_URL = f"{BASE_URL}/v1/api/login"
UNDANGAN_URL = f"{BASE_URL}/v1/api/rekanan/packet-invitation-list"


class IaproLoginGagal(Exception):
    """Login ke IAPRO InJourney Airports gagal -- cek username/password,
    atau situs mengubah struktur endpoint login-nya."""


def login(username: str, password: str) -> tuple:
    """Login, return (sso_token, group_id)."""
    resp = requests.post(
        LOGIN_URL, json={"username": username, "password": password},
        headers={"Accept": "application/json"}, timeout=30,
    )
    if resp.status_code != 200:
        raise IaproLoginGagal(f"Login gagal: HTTP {resp.status_code} - {resp.text[:200]}")

    data = resp.json()
    if not data.get("data", {}).get("sso_token"):
        raise IaproLoginGagal(f"Login gagal: respons tidak ada sso_token -- {data.get('message', '')}")

    sso_token = data["data"]["sso_token"]
    group_id = data["data"].get("user", {}).get("groupId", "")
    return sso_token, group_id


def tarik_undangan_tender(sso_token: str, group_id, kata_kunci_relevan: list,
                            maks_halaman: int = 10, limit: int = 50) -> list:
    """Tarik semua undangan tender dari akun yang login. Return list[Tender]."""
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {sso_token}",
        "Groupid": str(group_id),
        "Accept": "application/json",
    })

    hasil = []
    halaman = 1
    while halaman <= maks_halaman:
        resp = session.get(
            UNDANGAN_URL, params={"page": halaman, "limit": limit}, timeout=30,
        )
        if resp.status_code == 401:
            raise IaproLoginGagal("Token ditolak (401) -- kemungkinan sudah expired, perlu login ulang.")
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", {}).get("data", [])
        meta = data.get("data", {}).get("meta", {})
        last_page = meta.get("last_page", 1)

        for item in items:
            item_id = item.get("id")
            kode = item.get("code") or str(item_id)
            # "title" biasanya lebih deskriptif ("PENGUMUMAN TENDER ...") daripada
            # "name" (nama paket singkat) -- pakai title kalau ada, fallback ke name.
            nama = item.get("title") or item.get("name") or ""
            tanggal = item.get("announcement_date") or ""

            if not nama:
                continue

            hasil.append(Tender(
                id_unik=f"iaproc-{item_id}",
                kode=str(kode),
                nama_paket=nama,
                instansi="InJourney Airports",
                tahapan="Undangan Tender",
                hps=0,  # tidak tersedia di list undangan
                jadwal=f"Pengumuman: {tanggal}",
                link=item.get("file_path") or f"{BASE_URL}/vms/vendor/undangan-tender",
                relevan=cek_relevan(nama, kata_kunci_relevan),
            ))

        if not items or halaman >= last_page:
            break
        halaman += 1
        time.sleep(1)

    return hasil


if __name__ == "__main__":
    # Uji cepat manual: python iaproc.py <username> <password>
    import sys

    import config

    if len(sys.argv) >= 3:
        _username, _password = sys.argv[1], sys.argv[2]
    else:
        _username, _password = config.IAPROC_USERNAME, config.IAPROC_PASSWORD

    print("Login ke IAPRO InJourney Airports...")
    try:
        _token, _group_id = login(_username, _password)
        print(f"Login berhasil, token didapat (groupId={_group_id}).")
        daftar = tarik_undangan_tender(_token, _group_id, config.KATA_KUNCI_RELEVAN)
        print(f"\n{len(daftar)} undangan tender ditemukan.")
        relevan = [t for t in daftar if t.relevan]
        print(f"Relevan untuk MPA: {len(relevan)}\n")
        for t in daftar[:10]:
            tanda = "V" if t.relevan else " "
            print(f"[{tanda}] {t.nama_paket[:80]}")
            print(f"      {t.jadwal} | {t.link}")
    except IaproLoginGagal as e:
        print(f"\nGAGAL: {e}")
