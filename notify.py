"""
NOTIFY — Tender Scraper MPA

Modul notifikasi (Email via SMTP Gmail, Telegram opsional). Dipisah dari
fetcher.py & storage.py -- kalau nanti mau ganti/tambah channel (WhatsApp,
Slack, dll), cukup ubah file ini.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import requests

import config


def _format_rupiah(n: int) -> str:
    return f"Rp {n:,}".replace(",", ".")


def _susun_pesan(tender_list: list) -> tuple:
    jml = len(tender_list)
    judul = f"🏗️ {jml} Tender Baru Relevan untuk MPA"

    teks = f"{judul}\nDitemukan {jml} tender baru yang cocok dengan lini bisnis MPA:\n\n"
    html = f'<h2 style="color:#1a3c5e">{judul}</h2><p>Ditemukan <b>{jml}</b> tender baru yang relevan:</p>'

    for i, t in enumerate(tender_list[:20], 1):
        hps_str = _format_rupiah(t.hps) if t.hps > 0 else "-"
        teks += (
            f"{i}. {t.nama_paket}\n"
            f"   Instansi : {t.instansi}\n"
            f"   HPS      : {hps_str}\n"
            f"   Tahapan  : {t.tahapan}\n"
            f"   Link     : {t.link}\n\n"
        )
        html += (
            '<div style="border-left:4px solid #1a3c5e;padding:8px 12px;margin:10px 0;background:#f5f8fb">'
            f"<b>{i}. {t.nama_paket}</b><br>"
            f"Instansi: {t.instansi}<br>"
            f"HPS: <b>{hps_str}</b> &nbsp;|&nbsp; Tahapan: {t.tahapan}<br>"
            f'<a href="{t.link}">🔗 Buka pengumuman tender</a></div>'
        )

    if jml > 20:
        teks += f"...dan {jml - 20} tender lainnya.\n"
        html += f"<p><i>...dan {jml - 20} tender lainnya.</i></p>"

    return judul, teks, html


def kirim_email(judul: str, teks: str, html: str):
    if not config.EMAIL_PENGIRIM or not config.EMAIL_APP_PASSWORD:
        print("[NOTIFY] Email dilewati: EMAIL_PENGIRIM / EMAIL_APP_PASSWORD belum diset.")
        return
    try:
        pesan = MIMEMultipart("alternative")
        pesan["Subject"] = judul
        pesan["From"] = config.EMAIL_PENGIRIM
        pesan["To"] = config.EMAIL_TUJUAN
        if config.EMAIL_CC:
            pesan["Cc"] = config.EMAIL_CC
        pesan.attach(MIMEText(teks, "plain"))
        pesan.attach(MIMEText(html, "html"))

        penerima = config.EMAIL_TUJUAN.split(",") + (config.EMAIL_CC.split(",") if config.EMAIL_CC else [])
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(config.EMAIL_PENGIRIM, config.EMAIL_APP_PASSWORD)
            server.sendmail(config.EMAIL_PENGIRIM, penerima, pesan.as_string())
        print(f"[NOTIFY] Email terkirim ke {config.EMAIL_TUJUAN} (Cc: {config.EMAIL_CC or '-'})")
    except smtplib.SMTPException as e:
        print(f"[NOTIFY] Email GAGAL: {e}")


def kirim_telegram(teks: str):
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("[NOTIFY] Telegram dilewati: TOKEN/CHAT_ID belum diset.")
        return
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        potong = teks[:3900] + "\n...(dipotong)" if len(teks) > 4000 else teks
        resp = requests.post(url, data={
            "chat_id": config.TELEGRAM_CHAT_ID, "text": potong,
            "disable_web_page_preview": True,
        }, timeout=15)
        if resp.status_code == 200:
            print("[NOTIFY] Telegram terkirim.")
        else:
            print(f"[NOTIFY] Telegram GAGAL: HTTP {resp.status_code} - {resp.text[:150]}")
    except requests.exceptions.RequestException as e:
        print(f"[NOTIFY] Telegram GAGAL: {e}")


def kirim_notifikasi(tender_list: list):
    if not tender_list:
        return
    judul, teks, html = _susun_pesan(tender_list)
    if config.EMAIL_AKTIF:
        kirim_email(judul, teks, html)
    if config.TELEGRAM_AKTIF:
        kirim_telegram(teks)


if __name__ == "__main__":
    # Tes cepat kirim notifikasi tanpa perlu ada tender baru sungguhan.
    # Jalankan: python notify.py
    from fetcher import Tender

    contoh = [Tender(
        id_unik="tes-001", kode="TES001",
        nama_paket="CONTOH: Pembangunan Gedung Kantor 3 Lantai",
        instansi="Dinas Contoh Provinsi", tahapan="Pengumuman",
        hps=4_500_000_000, jadwal="Pekerjaan Konstruksi - TA 2027",
        link="https://spse.inaproc.id/surabaya/lelang", relevan=True,
    )]
    print("Mengirim notifikasi TES...")
    kirim_notifikasi(contoh)
    print("Selesai. Cek EMAIL_TUJUAN di config.py untuk lihat hasilnya.")
