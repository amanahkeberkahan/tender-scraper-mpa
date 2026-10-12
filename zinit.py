#!/usr/bin/env python3
"""
ZINIT — Tender Scraper MPA
==========================

Beda arsitektur dari fetcher.py (LPSE): Zinit (app.zinit.id) bukan daftar
tender publik, tapi platform B2B yang mengirim UNDANGAN RFP privat ke akun
vendor yang sudah terdaftar (MPA). Jadi scraper ini tidak "mencari tender
baru di luar" -- tapi "jangan sampai ada undangan RFP yang terlewat".

Autentikasi pakai JWT (header `Authorization: JWT <token>`), token disimpan
browser di localStorage. Tidak ada endpoint refresh-token yang terkonfirmasi,
jadi login dilakukan ulang tiap run lewat form email->password (pakai
Playwright, browser otomatis headless) -- notifikasi RFP ini cuma 2x sehari,
jadi ini aman dan simpel dibanding reverse-engineering endpoint refresh.

WAJIB: `pip install playwright` lalu `playwright install chromium` sekali di
laptop sebelum modul ini dipakai.
"""

import re
import time

import requests

from fetcher import Tender, cek_relevan

BASE_URL = "https://app.zinit.id"
LOGIN_URL = f"{BASE_URL}/register"
API_REQUESTS_URL = f"{BASE_URL}/api/v1/requests/"

# status numerik dari API -> label (dikonfirmasi lewat tampilan UI: sidebar
# filter "Proses Pengumpulan, Penawaran Sedang Berlangsung, Evaluasi
# Penawaran, Selesai" cocok urut dengan status 1-4 yang diamati).
STATUS_LABEL = {
    1: "Proses Pengumpulan",
    2: "Penawaran Sedang Berlangsung",
    3: "Evaluasi Penawaran",
    4: "Selesai",
}


class ZinitLoginGagal(Exception):
    """Login otomatis ke Zinit gagal -- cek kredensial, atau Zinit mengubah
    struktur halaman login-nya (perlu re-investigasi lewat DevTools lagi)."""


def login_dan_ambil_token(email: str, password: str, headless: bool = True,
                            percobaan: int = 3) -> str:
    """Login ke Zinit lewat browser otomatis (Playwright), ambil JWT access
    token dari localStorage setelah berhasil masuk. Retry beberapa kali --
    endpoint login Zinit pernah terpantau 504 Gateway Timeout sesekali."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise ZinitLoginGagal(
            "Package 'playwright' belum terpasang. Jalankan:\n"
            "  pip install playwright\n  playwright install chromium"
        ) from e

    # Form login Zinit bergaya komponen auth pihak ketiga (mis. Clerk) --
    # field email tidak selalu type="email", kadang type="text" dengan
    # name/id "identifier". Coba beberapa kemungkinan selector berurutan,
    # pakai yang pertama ketemu & kelihatan (visible).
    SELECTOR_EMAIL = (
        'input[name="identifier"], input[type="email"], '
        'input[autocomplete="email"], input[autocomplete="username"]'
    )
    SELECTOR_PASSWORD = 'input[type="password"], input[name="password"]'

    error_terakhir = None
    for i in range(percobaan):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=headless)
                page = browser.new_page()
                page.goto(LOGIN_URL, timeout=30000)
                page.wait_for_load_state("networkidle", timeout=20000)

                kolom_email = page.locator(SELECTOR_EMAIL).first
                kolom_email.wait_for(state="visible", timeout=20000)
                kolom_email.fill(email)
                page.keyboard.press("Enter")

                kolom_password = page.locator(SELECTOR_PASSWORD).first
                kolom_password.wait_for(state="visible", timeout=20000)
                kolom_password.fill(password)
                page.keyboard.press("Enter")

                # Setelah login, akun bisa diarahkan ke /companies dulu
                # (pilih perusahaan) sebelum masuk ke /requests -- akun MPA
                # cuma terhubung ke 1 perusahaan ("Multi Power Abadi"), jadi
                # langsung klik itu kalau mendarat di halaman pilih perusahaan.
                page.wait_for_url(re.compile(r"/(requests|companies)"), timeout=30000)
                if "/companies" in page.url:
                    page.locator("text=Multi Power Abadi").first.click(timeout=15000)
                    page.wait_for_url(re.compile(r"/requests"), timeout=30000)
                page.wait_for_timeout(1000)

                token = page.evaluate("() => window.localStorage.getItem('access')")

                if not headless:
                    page.wait_for_timeout(2000)
                browser.close()

                if not token:
                    raise ZinitLoginGagal("Login sukses tapi token 'access' tidak ketemu di localStorage.")
                return token
        except Exception as e:  # noqa: BLE001 -- sengaja luas, banyak jenis error Playwright
            error_terakhir = e
            if i < percobaan - 1:
                time.sleep(5)
    raise ZinitLoginGagal(f"Login ke Zinit gagal setelah {percobaan}x percobaan: {error_terakhir}")


def _nama_perusahaan(item: dict) -> str:
    perusahaan = item.get("company") or item.get("organizer") or {}
    if isinstance(perusahaan, dict):
        return perusahaan.get("name") or perusahaan.get("legal_name") or "-"
    return "-"


def tarik_rfp_zinit(token: str, kata_kunci_relevan: list, maks_halaman: int = 10,
                      page_size: int = 100) -> list:
    """Tarik semua RFP (undangan + penawaran) dari akun Zinit yang login.
    Return list[Tender] -- field dipetakan semirip mungkin ke LPSE supaya
    bisa dipakai ulang di storage.py/dashboard.py/notify.py tanpa diubah."""
    session = requests.Session()
    session.headers.update({
        "Authorization": f"JWT {token}",
        "Accept": "application/json",
    })

    hasil = []
    halaman = 1
    while halaman <= maks_halaman:
        resp = session.get(
            API_REQUESTS_URL,
            params={"sorting": "-created_at", "page": halaman, "page_size": page_size},
            timeout=30,
        )
        if resp.status_code == 401:
            raise ZinitLoginGagal("Token ditolak (401) -- kemungkinan sudah expired, perlu login ulang.")
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        total_count = data.get("page_info", {}).get("total_count", len(items))

        for item in items:
            rfp_id = item.get("id")
            kode = item.get("code") or str(rfp_id)
            nama = item.get("name") or ""
            status_angka = item.get("status")
            tahapan = STATUS_LABEL.get(status_angka, f"Status {status_angka}")
            dikirim = item.get("published_at") or item.get("created_at") or ""
            ditutup = item.get("status_changed_at") or ""
            instansi = _nama_perusahaan(item)

            if not nama:
                continue

            hasil.append(Tender(
                id_unik=f"zinit-{rfp_id}",
                kode=str(kode),
                nama_paket=nama,
                instansi=instansi,
                tahapan=tahapan,
                hps=0,  # Zinit tidak menyediakan estimasi nilai di list RFP
                jadwal=f"Dikirim: {dikirim[:16]} | Ditutup: {ditutup[:16]}",
                link=f"{BASE_URL}/requests/{rfp_id}",
                relevan=cek_relevan(nama, kata_kunci_relevan),
            ))

        if not items or len(hasil) >= total_count:
            break
        halaman += 1
        time.sleep(1)

    return hasil


if __name__ == "__main__":
    # Uji cepat manual: python zinit.py <email> <password>
    import sys

    import config

    if len(sys.argv) >= 3:
        _email, _password = sys.argv[1], sys.argv[2]
    else:
        _email, _password = config.ZINIT_EMAIL, config.ZINIT_PASSWORD

    print("Login ke Zinit...")
    try:
        _token = login_dan_ambil_token(_email, _password, headless=False)
        print("Login berhasil, token didapat.")
        daftar = tarik_rfp_zinit(_token, config.KATA_KUNCI_RELEVAN)
        print(f"\n{len(daftar)} RFP ditemukan.")
        relevan = [t for t in daftar if t.relevan]
        print(f"Relevan untuk MPA: {len(relevan)}\n")
        for t in daftar[:10]:
            tanda = "✅" if t.relevan else "  "
            print(f"{tanda} [{t.tahapan}] {t.nama_paket[:70]}")
            print(f"     Penyelenggara: {t.instansi} | {t.jadwal}")
    except ZinitLoginGagal as e:
        print(f"\nGAGAL: {e}")
