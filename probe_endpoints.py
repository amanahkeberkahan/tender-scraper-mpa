#!/usr/bin/env python3
"""
PROBE ENDPOINT LPSE — Tender Scraper MPA
==========================================

TUJUAN
------
MVP Google Apps Script gagal karena endpoint AJAX `/dt/lelang` yang diasumsikan
(format DataTables server-side lama) ternyata tidak menghasilkan JSON yang valid
di portal SPSE saat ini. Skrip ini TIDAK menebak lagi satu pola — ia mencoba
SEMUA kandidat pola endpoint yang pernah dipakai berbagai versi SPSE (LKPP),
plus HTML halaman aslinya, lalu mencatat persis apa yang terjadi untuk tiap
kombinasi (status code, content-type, apakah JSON valid, cuplikan isi).

Jalankan skrip ini di komputer/lingkungan yang PUNYA akses internet (bukan di
sandbox Claude Code on the web ini — sandbox itu diblokir egress-nya).

CARA PAKAI
----------
    pip install -r requirements.txt
    python probe_endpoints.py

Hasil:
    - Ditampilkan ringkas di terminal.
    - Laporan lengkap tersimpan di `probe_report.md` dan `probe_report.json`.

Setelah dapat laporan ini, kirim balik `probe_report.md` (atau isinya) ke
Claude Code — dari situ modul fetcher produksi (`fetcher.py`) akan dibangun
berdasarkan pola yang TERBUKTI jalan, bukan asumsi.
"""

import json
import re
import time
from dataclasses import dataclass, field
from datetime import datetime

import requests

# ─────────────────────────────────────────────────────────────────────────
# KONFIGURASI
# ─────────────────────────────────────────────────────────────────────────

PORTAL_LIST = [
    {"nama": "LPSE Kota Surabaya", "kode": "surabaya"},
    {"nama": "LPSE Provinsi Jawa Timur", "kode": "jatimprov"},
    {"nama": "LPSE Kementerian PU", "kode": "pu"},
    {"nama": "LPSE LKPP", "kode": "lkpp"},
]

TAHUN_ANGGARAN = 2026
JEDA_ANTAR_REQUEST_DETIK = 1.5  # sopan ke server, hindari dianggap serangan

HEADERS_BASE = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

# Pola-pola endpoint AJAX yang pernah/masih dipakai berbagai versi SPSE.
# {base} akan diganti https://spse.inaproc.id/<kode>
CANDIDATE_PATHS = [
    "/dt/lelang",
    "/lelang/dt",
    "/dt/lelang/tahapan/semua",
    "/dt/nonlelang",
    "/lelang",  # halaman HTML asli, untuk cari petunjuk di inline script
    "/eproc/lelang",
    "/tender/list",
    "/tender/dt",
    "/lelang/list",
    "/spse/lelang",
]

# ─────────────────────────────────────────────────────────────────────────
# STRUKTUR HASIL
# ─────────────────────────────────────────────────────────────────────────


@dataclass
class ProbeResult:
    portal: str
    kode: str
    method: str
    url: str
    payload_desc: str
    status_code: int | None = None
    content_type: str = ""
    content_length: int = 0
    is_json: bool = False
    json_top_level_keys: list = field(default_factory=list)
    json_record_count: int | None = None
    snippet: str = ""
    hint_found: list = field(default_factory=list)
    error: str = ""


RESULTS: list[ProbeResult] = []


# ─────────────────────────────────────────────────────────────────────────
# PEMBANTU
# ─────────────────────────────────────────────────────────────────────────


def cari_petunjuk_ajax_di_html(html: str) -> list:
    """Cari jejak konfigurasi DataTables / AJAX di inline <script> halaman HTML.

    Ini menggantikan langkah manual 'inspect Network tab' — kita cari langsung
    string kunci yang biasanya membocorkan URL endpoint sesungguhnya.
    """
    petunjuk = []
    pola_dicari = [
        r'ajax\s*:\s*[\'"{][^,}]{0,200}',
        r'url\s*:\s*[\'"]([^\'"]+)[\'"]',
        r'\.DataTable\s*\(\s*\{[^}]{0,400}',
        r'action=[\'"]([^\'"]*lelang[^\'"]*)[\'"]',
        r'csrf[_-]?token[\'"]?\s*[:=]\s*[\'"]([^\'"]+)[\'"]',
        r'/dt/[a-zA-Z_/]+',
        r'fetch\(\s*[\'"]([^\'"]+)[\'"]',
    ]
    for pola in pola_dicari:
        for m in re.finditer(pola, html, re.IGNORECASE):
            potongan = m.group(0)
            if potongan not in petunjuk:
                petunjuk.append(potongan[:200])
    return petunjuk[:25]


def coba_parse_json(teks: str):
    try:
        data = json.loads(teks)
        return True, data
    except (json.JSONDecodeError, ValueError):
        return False, None


def catat(session: requests.Session, portal: dict, method: str, url: str,
          payload_desc: str, **request_kwargs) -> ProbeResult:
    r = ProbeResult(portal=portal["nama"], kode=portal["kode"], method=method,
                     url=url, payload_desc=payload_desc)
    try:
        resp = session.request(method, url, timeout=20, **request_kwargs)
        r.status_code = resp.status_code
        r.content_type = resp.headers.get("Content-Type", "")
        r.content_length = len(resp.content)
        teks = resp.text
        r.snippet = teks[:400].replace("\n", " ")

        ok, data = coba_parse_json(teks)
        r.is_json = ok
        if ok and isinstance(data, dict):
            r.json_top_level_keys = list(data.keys())[:15]
            for kemungkinan_kunci in ("data", "aaData", "rows", "items", "records", "result"):
                if kemungkinan_kunci in data and isinstance(data[kemungkinan_kunci], list):
                    r.json_record_count = len(data[kemungkinan_kunci])
                    break
        elif ok and isinstance(data, list):
            r.json_record_count = len(data)

        if "html" in r.content_type or "<html" in teks.lower()[:200]:
            r.hint_found = cari_petunjuk_ajax_di_html(teks)

    except requests.exceptions.RequestException as e:
        r.error = f"{type(e).__name__}: {e}"

    RESULTS.append(r)
    return r


# ─────────────────────────────────────────────────────────────────────────
# PROBE UTAMA
# ─────────────────────────────────────────────────────────────────────────


def probe_portal(portal: dict):
    kode = portal["kode"]
    base = f"https://spse.inaproc.id/{kode}"
    print(f"\n{'=' * 70}\nPORTAL: {portal['nama']}  ({base})\n{'=' * 70}")

    session = requests.Session()
    session.headers.update(HEADERS_BASE)

    # 1) GET halaman HTML utama dulu — ini juga mengisi cookie sesi (PHPSESSID)
    #    yang mungkin disyaratkan sebelum endpoint AJAX mau merespons data asli.
    hasil_awal = catat(
        session, portal, "GET", f"{base}/lelang", "Halaman HTML awal (isi cookie sesi + cari petunjuk inline JS)",
        headers={"Accept": "text/html,application/xhtml+xml"},
    )
    status = hasil_awal.status_code
    print(f"  [HTML awal] {base}/lelang -> HTTP {status}"
          + (f" | petunjuk: {hasil_awal.hint_found[:3]}" if hasil_awal.hint_found else " | tidak ada petunjuk jelas di HTML"))
    time.sleep(JEDA_ANTAR_REQUEST_DETIK)

    ajax_headers = {
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": f"{base}/lelang",
    }

    for path in CANDIDATE_PATHS:
        url = f"{base}{path}"

        # (a) GET dengan parameter gaya DataTables lama (seperti MVP)
        params_get = {
            "rekanan": "", "kategori": "", "instansi": "", "kualifikasi": "",
            "nama": "", "tahun": TAHUN_ANGGARAN, "draw": 1, "start": 0,
            "length": 25, "order[0][column]": 5, "order[0][dir]": "desc",
        }
        r1 = catat(session, portal, "GET", url, "GET query-string ala DataTables lama",
                   headers=ajax_headers, params=params_get)
        time.sleep(JEDA_ANTAR_REQUEST_DETIK)

        # (b) POST form-encoded gaya DataTables server-side resmi (jQuery DataTables
        #     default memang mengirim POST, bukan GET — ini kemungkinan besar akar masalah MVP).
        payload_post = {
            "draw": "1", "start": "0", "length": "25",
            "search[value]": "", "search[regex]": "false",
            "order[0][column]": "5", "order[0][dir]": "desc",
            "tahun": str(TAHUN_ANGGARAN),
        }
        for i in range(7):
            payload_post[f"columns[{i}][data]"] = str(i)
            payload_post[f"columns[{i}][searchable]"] = "true"
            payload_post[f"columns[{i}][orderable]"] = "true"
            payload_post[f"columns[{i}][search][value]"] = ""
            payload_post[f"columns[{i}][search][regex]"] = "false"

        r2 = catat(session, portal, "POST", url, "POST form-encoded ala DataTables server-side resmi",
                   headers=ajax_headers, data=payload_post)
        time.sleep(JEDA_ANTAR_REQUEST_DETIK)

        for label, r in (("GET", r1), ("POST", r2)):
            tanda = "✅ JSON!" if r.is_json else ("⚠️" if r.status_code == 200 else "❌")
            jml = f" ({r.json_record_count} baris)" if r.json_record_count is not None else ""
            print(f"  [{label:4}] {path:30} -> HTTP {r.status_code}  {tanda}{jml}")

    print(f"\n  Selesai portal {portal['nama']}.")


def main():
    print("PROBE ENDPOINT LPSE — Tender Scraper MPA")
    print(f"Waktu mulai: {datetime.now().isoformat()}")
    print("Mencoba semua kombinasi pola endpoint untuk tiap portal...\n")

    for portal in PORTAL_LIST:
        try:
            probe_portal(portal)
        except Exception as e:
            print(f"  !! Gagal total untuk portal {portal['nama']}: {e}")
        time.sleep(JEDA_ANTAR_REQUEST_DETIK)

    tulis_laporan()
    print("\n\nSELESAI. Laporan lengkap: probe_report.md dan probe_report.json")
    print("Kirim isi probe_report.md balik ke Claude Code untuk membangun fetcher produksi.")


def tulis_laporan():
    with open("probe_report.json", "w", encoding="utf-8") as f:
        json.dump([r.__dict__ for r in RESULTS], f, ensure_ascii=False, indent=2)

    kandidat_sukses = [r for r in RESULTS if r.is_json and r.json_record_count]

    with open("probe_report.md", "w", encoding="utf-8") as f:
        f.write(f"# Laporan Probe Endpoint LPSE\n\nWaktu: {datetime.now().isoformat()}\n\n")

        f.write("## Ringkasan Kandidat yang Menghasilkan JSON Berisi Data\n\n")
        if kandidat_sukses:
            for r in kandidat_sukses:
                f.write(f"- **{r.portal}** — `{r.method} {r.url}` "
                        f"({r.payload_desc}) -> {r.json_record_count} baris, "
                        f"kunci JSON: {r.json_top_level_keys}\n")
        else:
            f.write("_Tidak ada kandidat yang langsung menghasilkan JSON berisi data. "
                    "Lihat detail per-portal di bawah, terutama 'petunjuk inline JS' "
                    "dari halaman HTML awal — itu kemungkinan menunjukkan endpoint asli._\n")

        f.write("\n## Detail Lengkap per Percobaan\n\n")
        for r in RESULTS:
            f.write(f"### {r.portal} — {r.method} `{r.url}`\n")
            f.write(f"- Deskripsi: {r.payload_desc}\n")
            f.write(f"- Status: {r.status_code}  | Content-Type: `{r.content_type}`  | Panjang: {r.content_length}\n")
            f.write(f"- JSON valid: {r.is_json}")
            if r.json_record_count is not None:
                f.write(f" (jumlah baris data: {r.json_record_count})")
            f.write("\n")
            if r.json_top_level_keys:
                f.write(f"- Kunci JSON level atas: {r.json_top_level_keys}\n")
            if r.hint_found:
                f.write(f"- Petunjuk ditemukan di HTML/JS:\n")
                for h in r.hint_found:
                    f.write(f"  - `{h}`\n")
            if r.error:
                f.write(f"- ERROR: {r.error}\n")
            f.write(f"- Cuplikan respons: `{r.snippet}`\n\n")


if __name__ == "__main__":
    main()
