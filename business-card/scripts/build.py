"""Build the digital business card from card.json.

Generates the QR code, the static site (site/), the print layout and the
share-image HTML. Run render.cjs afterwards to produce PNG/PDF outputs.

    pip install segno
    python3 business-card/scripts/build.py
"""
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import segno

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SITE = ROOT / "site"
PRINT = ROOT / "print"
QR_DIR = ROOT / "qr"
BUILD = ROOT / ".build"

QR_DARK = "#123d38"
VCF_FILE = "kimmuyong.vcf"

ICONS = {
    "heart": '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/><path d="M3.22 12H9.5l.5-1 2 4.5 2-7 1.5 3.5h5.27"/>',
    "teach": '<path d="M2 3h20"/><path d="M21 3v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V3"/><path d="m7 21 5-5 5 5"/>',
    "spark": '<path d="M9.94 15.5A2 2 0 0 0 8.5 14.06l-6.14-1.58a.5.5 0 0 1 0-.96L8.5 9.94A2 2 0 0 0 9.94 8.5l1.58-6.14a.5.5 0 0 1 .96 0L14.06 8.5A2 2 0 0 0 15.5 9.94l6.14 1.58a.5.5 0 0 1 0 .96L15.5 14.06a2 2 0 0 0-1.44 1.44l-1.58 6.14a.5.5 0 0 1-.96 0z"/><path d="M20 3v4M22 5h-4"/>',
}


def fill(template: str, values: dict) -> str:
    out = template
    for key, val in values.items():
        out = out.replace("{{" + key + "}}", val)
    leftover = re.findall(r"\{\{[A-Z_]+\}\}", out)
    if leftover:
        raise SystemExit(f"unfilled placeholders: {leftover}")
    return out


def vcard(c: dict) -> str:
    def esc(s: str) -> str:
        return s.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;")

    title = " · ".join(
        f"{r['title']}(RN)" if r["icon"] == "heart" else r["title"] for r in c["roles"]
    )
    lines = [
        "BEGIN:VCARD",
        "VERSION:3.0",
        f"N:{esc(c['familyName'])};{esc(c['givenName'])};;;",
        f"FN:{esc(c['nameKo'])}",
        f"TITLE:{esc(title)}",
        f"TEL;TYPE=CELL,VOICE:{c['phone']}",
        f"EMAIL;TYPE=INTERNET:{c['email']}",
        f"URL:{c['siteUrl']}",
        "END:VCARD",
    ]
    return "\r\n".join(lines) + "\r\n"


def main() -> None:
    c = json.loads((HERE / "card.json").read_text(encoding="utf-8"))
    site_url = c["siteUrl"]
    for d in (SITE, PRINT, QR_DIR, BUILD):
        d.mkdir(parents=True, exist_ok=True)

    # QR code -> the card's web address
    qr = segno.make(site_url, error="q", micro=False)
    qr_svg = qr.svg_inline(dark=QR_DARK, light="#ffffff", border=2, omitsize=True)
    qr.save(QR_DIR / "kimmuyong-card-qr.svg", dark=QR_DARK, light="#ffffff", border=4, scale=10)
    qr.save(QR_DIR / "kimmuyong-card-qr.png", dark=QR_DARK, light="#ffffff", border=4, scale=48)
    qr.save(QR_DIR / "kimmuyong-card-qr-black.png", dark="#000000", light="#ffffff", border=4, scale=48)

    roles_html = "\n".join(
        '      <li><span class="ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        f'{ICONS[r["icon"]]}</svg></span><div><strong>{r["title"]}</strong>'
        + (f'<small>{r["detail"]}</small>' if r["detail"] else "")
        + "</div></li>"
        for r in c["roles"]
    )
    roles_print = "\n".join(
        f"        <li>{r['title']}{' (RN)' if r['icon'] == 'heart' else ''}</li>" for r in c["roles"]
    )
    roles_text = " · ".join(
        f"{r['title']}(RN)" if r["icon"] == "heart" else r["title"] for r in c["roles"]
    )

    common = {
        "NAME_KO": c["nameKo"],
        "NAME_EN": c["nameEn"],
        "PHONE": c["phone"],
        "PHONE_DIGITS": re.sub(r"\D", "", c["phone"]),
        "EMAIL": c["email"],
        "SITE_URL": site_url,
        "SITE_HOST": urlparse(site_url).netloc,
        "ROLES_TEXT": roles_text,
        "QR_SVG": qr_svg,
        "ROLES": roles_html,
        "ROLES_PRINT": roles_print,
        "VCF_FILE": VCF_FILE,
    }

    tpl = lambda name: (HERE / name).read_text(encoding="utf-8")
    (SITE / "index.html").write_text(fill(tpl("index.template.html"), common), encoding="utf-8")
    (SITE / VCF_FILE).write_bytes(vcard(c).encode("utf-8"))
    (SITE / "favicon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        '<rect width="64" height="64" rx="14" fill="#1d5c55"/>'
        '<text x="32" y="44" text-anchor="middle" font-family="Pretendard, Apple SD Gothic Neo, Noto Sans KR, sans-serif" '
        f'font-size="34" font-weight="800" fill="#fff">{c["nameKo"][0]}</text></svg>\n',
        encoding="utf-8",
    )
    (SITE / "vercel.json").write_text(
        json.dumps(
            {
                "headers": [
                    {
                        "source": f"/{VCF_FILE}",
                        "headers": [
                            {"key": "Content-Type", "value": "text/vcard; charset=utf-8"},
                            {"key": "Content-Disposition", "value": f'attachment; filename="{VCF_FILE}"'},
                        ],
                    }
                ]
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print_tpl = tpl("print.template.html")
    (PRINT / "card.html").write_text(fill(print_tpl, {**common, "BLEED": "0"}), encoding="utf-8")
    (BUILD / "card-bleed.html").write_text(fill(print_tpl, {**common, "BLEED": "1"}), encoding="utf-8")
    (BUILD / "og.html").write_text(fill(tpl("og.template.html"), common), encoding="utf-8")
    (BUILD / "icon.html").write_text(
        '<!doctype html><meta charset="utf-8"><body style="margin:0;width:180px;height:180px;'
        'display:grid;place-items:center;background:linear-gradient(160deg,#1d5c55,#123d38);'
        'font-family:Pretendard,sans-serif;color:#fff;font-size:96px;font-weight:800">'
        f'{c["nameKo"][0]}</body>',
        encoding="utf-8",
    )
    print(f"QR -> {site_url}  (version {qr.version}, error {qr.error})")


if __name__ == "__main__":
    main()
