#!/usr/bin/env python3
"""
FETCHER — Tender Scraper MPA
==============================

Modul tarik data produksi, dibangun berdasarkan temuan probe_endpoints.py:

  - Endpoint asli   : POST https://spse.inaproc.id/<kode>/dt/lelang?tahun=<tahun>
  - Format          : DataTables server-side (respons JSON: draw, recordsTotal,
                       recordsFiltered, data: [...]).
  - Wajib           : token keamanan (`authenticityToken`) yang di-generate ulang
                       tiap kali halaman /<kode>/lelang dimuat, dan cookie sesi
                       dari GET awal itu.
  - Tahun anggaran  : TIDAK di-hardcode. Diambil langsung dari inline JavaScript
                       halaman saat itu juga (portal berbeda bisa beda tahun
                       aktif -- contoh: Surabaya 2027, LKPP 2026 -- lihat hasil
                       probe_report.md).
  - WAJIB dijalankan dari IP residensial (bukan cloud/datacenter) -- LPSE
    memblokir IP cloud lewat Cloudflare, sudah dikonfirmasi lewat probe.

Modul ini HANYA bertugas menarik & membersihkan data (single responsibility),
supaya nanti gampang ditukar/di-upgrade tanpa mengubah storage.py atau notify.py.
"""

import re
import time
from dataclasses import dataclass

import requests

HEADERS_BASE = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Pola regex untuk menangkap konfigurasi AJAX dari inline <script> halaman /lelang.
POLA_AJAX_URL = re.compile(r'ajax\s*:\s*\{\s*url\s*:\s*[\'"]([^\'"]+)[\'"]', re.IGNORECASE)
POLA_TOKEN = re.compile(r'authenticityToken\s*=\s*[\'"]([a-fA-F0-9]+)[\'"]')
POLA_TAG_HTML = re.compile(r'<[^>]*>')


class EndpointTidakDitemukan(Exception):
    """Halaman /lelang tidak lagi memuat pola AJAX yang dikenali -- LPSE mungkin
    sudah mengubah struktur halamannya lagi. Perlu investigasi ulang manual."""


@dataclass
class Tender:
    id_unik: str
    kode: str
    nama_paket: str
    instansi: str
    tahapan: str
    hps: int
    jadwal: str
    link: str
    relevan: bool


def bersih(v) -> str:
    if v is None:
        return ""
    return POLA_TAG_HTML.sub(" ", str(v)).replace("&nbsp;", " ").strip()


def parse_rupiah(v) -> int:
    """Parse format Rupiah Indonesia: 'Rp. 57.446.418.426,00'
    -> titik = pemisah ribuan, koma = pemisah desimal (KEBALIKAN dari format Inggris)."""
    if v is None:
        return 0
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip()
    if not s or s.lower() == "none":
        return 0
    s = re.sub(r"[^\d,.\-]", "", s)  # buang "Rp.", spasi, dll -- sisakan angka+pemisah
    bagian_rupiah = s.split(",")[0] if "," in s else s
    bagian_rupiah = bagian_rupiah.replace(".", "")
    return int(bagian_rupiah) if bagian_rupiah.isdigit() else 0


POLA_RUPIAH_SINGKAT = re.compile(r"([\d.,]+)\s*(jt|m|t)\b", re.IGNORECASE)


def parse_rupiah_singkat(v) -> int:
    """Parse format HPS singkat ala LPSE: '541,3 Jt' -> 541.300.000,
    '60,2 M' -> 60.200.000.000. Jt=juta, M=miliar, T=triliun.
    Koma di sini adalah desimal (bukan pemisah ribuan)."""
    if v is None:
        return 0
    if isinstance(v, (int, float)):
        return int(v)
    s = str(v).strip()
    if not s or s.lower() == "none":
        return 0
    m = POLA_RUPIAH_SINGKAT.search(s)
    if not m:
        return parse_rupiah(v)  # fallback: mungkin sudah format penuh
    angka = float(m.group(1).replace(".", "").replace(",", "."))
    satuan = m.group(2).lower()
    pengali = {"jt": 1_000_000, "m": 1_000_000_000, "t": 1_000_000_000_000}[satuan]
    return int(angka * pengali)


def cek_relevan(nama_paket: str, kata_kunci: list) -> bool:
    n = nama_paket.lower()
    return any(k.lower() in n for k in kata_kunci)


def _ambil_konfigurasi_ajax(session: requests.Session, base_url: str) -> tuple:
    """GET halaman /lelang, ekstrak (url_ajax_relatif, token) dari inline JS.

    Ini juga otomatis mengisi cookie sesi di `session` -- dipakai lagi saat POST.
    """
    resp = session.get(
        f"{base_url}/lelang", timeout=20,
        headers={**HEADERS_BASE, "Accept": "text/html,application/xhtml+xml"},
    )
    resp.raise_for_status()
    html = resp.text

    m_url = POLA_AJAX_URL.search(html)
    m_token = POLA_TOKEN.search(html)
    if not m_url or not m_token:
        raise EndpointTidakDitemukan(
            f"Pola AJAX/token tidak ditemukan di {base_url}/lelang. "
            "Kemungkinan LPSE mengubah struktur halaman -- perlu re-investigasi "
            "seperti probe_endpoints.py."
        )
    return m_url.group(1), m_token.group(1)


def tarik_tender_portal(kode_portal: str, kata_kunci_relevan: list,
                          maks_baris: int = 300, jeda_detik: float = 1.5,
                          debug: bool = False) -> list:
    """Tarik semua tender dari satu portal LPSE. Return list[Tender]."""
    base_url = f"https://spse.inaproc.id/{kode_portal}"
    session = requests.Session()
    session.headers.update(HEADERS_BASE)

    url_ajax_relatif, token = _ambil_konfigurasi_ajax(session, base_url)
    time.sleep(jeda_detik)

    url_post = f"https://spse.inaproc.id{url_ajax_relatif}" if url_ajax_relatif.startswith("/") \
        else f"{base_url}/{url_ajax_relatif}"

    payload = {
        "draw": "1", "start": "0", "length": str(maks_baris),
        "search[value]": "", "search[regex]": "false",
        "order[0][column]": "0", "order[0][dir]": "desc",
        "authenticityToken": token,
    }
    for i in range(8):
        payload[f"columns[{i}][data]"] = str(i)
        payload[f"columns[{i}][searchable]"] = "true"
        payload[f"columns[{i}][orderable]"] = "true"
        payload[f"columns[{i}][search][value]"] = ""
        payload[f"columns[{i}][search][regex]"] = "false"

    resp = session.post(
        url_post, data=payload, timeout=30,
        headers={
            **HEADERS_BASE,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": f"{base_url}/lelang",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        },
    )
    resp.raise_for_status()
    data_json = resp.json()
    baris_data = data_json.get("data", [])

    if debug and baris_data:
        print(f"\n--- DEBUG: {len(baris_data)} baris mentah dari server, contoh baris pertama ---")
        contoh = baris_data[0]
        if isinstance(contoh, dict):
            for k, v in contoh.items():
                print(f"  key={k!r:20} -> {str(v)[:150]!r}")
        else:
            for i, v in enumerate(contoh):
                print(f"  index={i:2} -> {str(v)[:150]!r}")
        print("--- akhir DEBUG ---\n")

    hasil = []
    for r in baris_data:
        # DataTables bisa balikin list-of-list ATAU list-of-dict tergantung
        # aoColumnDefs server -- tangani dua-duanya.
        if isinstance(r, dict):
            nilai = list(r.values())
        else:
            nilai = list(r)

        if len(nilai) < 11:
            continue  # baris tidak lengkap, lewati

        # Pemetaan kolom dikonfirmasi dari data mentah asli server (lihat --debug),
        # BUKAN tebakan dari struktur MVP lama:
        #   0=kode  1=nama paket  2=instansi  3=tahapan
        #   4=HPS PERKIRAAN (SEBELUM tender), format singkat mis. "60,2 M"/"541,3 Jt"
        #       -- INI yang dipakai, karena berguna untuk menilai besar proyek
        #       SEBELUM ikut lelang (tender yang masih berjalan/relevan diikuti).
        #   5=metode kualifikasi  6=jenis  7=metode evaluasi
        #   8=kategori + tahun anggaran (mis. "Pekerjaan Konstruksi - TA 2026,2027")
        #   9=jumlah peserta
        #   10=NILAI KONTRAK FINAL (baru terisi SETELAH tender selesai & pemenang
        #       ditentukan -- untuk tender yang masih berjalan isinya literal teks
        #       "Nilai Kontrak belum dibuat", BUKAN HPS -- jangan dipakai sebagai HPS).
        kode_tender = bersih(nilai[0])
        nama = bersih(nilai[1])
        instansi = bersih(nilai[2])
        tahapan = bersih(nilai[3])
        kategori_tahun = bersih(nilai[8])
        hps_raw = nilai[4]

        if not nama:
            continue

        kode_angka_match = re.search(r"\d{5,}", str(kode_tender))
        kode_angka = kode_angka_match.group(0) if kode_angka_match else ""
        link = f"{base_url}/lelang/{kode_angka}/pengumumanlelang" if kode_angka \
            else f"{base_url}/lelang"
        id_unik = f"{kode_portal}-{kode_angka or hash(nama + instansi)}"

        hasil.append(Tender(
            id_unik=id_unik, kode=kode_angka or kode_tender, nama_paket=nama,
            instansi=instansi, tahapan=tahapan, hps=parse_rupiah_singkat(hps_raw),
            jadwal=kategori_tahun, link=link,
            relevan=cek_relevan(nama, kata_kunci_relevan),
        ))

    return hasil


if __name__ == "__main__":
    # Uji cepat manual: tarik 1 portal, tampilkan ringkasan ke terminal.
    # Contoh: python fetcher.py surabaya
    import sys

    kode = sys.argv[1] if len(sys.argv) > 1 else "surabaya"
    mode_debug = "--debug" in sys.argv
    kata_kunci = [
        "konstruksi", "bangunan", "gedung", "renovasi", "rehabilitasi",
        "interior", "fit out", "furniture", "mebel", "meubelair",
        "pembangunan", "finishing", "partisi", "event", "pameran",
        "booth", "dekorasi", "panggung", "mekanikal", "elektrikal",
        "plumbing", "hvac",
    ]

    print(f"Menarik data dari portal '{kode}'...")
    try:
        daftar = tarik_tender_portal(kode, kata_kunci, debug=mode_debug)
        print(f"\nBerhasil! {len(daftar)} tender ditemukan.")
        relevan = [t for t in daftar if t.relevan]
        print(f"Relevan untuk MPA: {len(relevan)}\n")
        for t in daftar[:10]:
            tanda = "✅" if t.relevan else "  "
            print(f"{tanda} [{t.tahapan}] {t.nama_paket[:70]}")
            print(f"     Instansi: {t.instansi} | HPS: Rp {t.hps:,}".replace(",", "."))
        if len(daftar) > 10:
            print(f"\n...dan {len(daftar) - 10} lainnya.")
    except EndpointTidakDitemukan as e:
        print(f"\nGAGAL: {e}")
    except requests.exceptions.RequestException as e:
        print(f"\nGAGAL koneksi: {e}")
    except (ValueError, KeyError) as e:
        print(f"\nGAGAL parsing respons (mungkin bukan JSON, atau struktur berubah): {e}")
