"""Build the one-page workshop handouts (docs/handout/handout-{en,es}.pdf).

Usage: python scripts/build_handout.py
Needs: qrcode, playwright (Chromium). Writes HTML and PDF next to each other.
"""
import base64
import io
from pathlib import Path

import qrcode
from playwright.sync_api import sync_playwright

URL = "https://who-really-sent-this.streamlit.app"
OUT = Path(__file__).resolve().parent.parent / "docs" / "handout"

TEXT = {
 "en": dict(
  title="Is this email real?", sub="Check it in 3 steps, for free",
  steps=["<b>Open</b> who-really-sent-this.streamlit.app <span class=m>(or scan the code)</span>",
         "<b>Copy the email's hidden lines (headers).</b><br><span class=m>Gmail: ⋮ → Show original · Outlook.com: … → View → View message source · Yahoo: … → View raw message</span>",
         "<b>Paste</b> them in the box and click <b>Check this email</b>."],
  results=[("✅","Checks out","Really from that address. If it asks for money or passwords, still check another way."),
           ("⚠️","Be careful","Something is wrong. Check with the sender another way first."),
           ("⛔","Likely a scam","Not from who it says. Do not click, reply or pay.")],
  signs_t="5 warning signs",
  signs=["<b>Hurry or fear:</b> “Your account closes today.”",
         "<b>Asks for</b> money, gift cards, passwords or codes.",
         "<b>Name and address don't match:</b> “Chase Bank” from a Gmail address.",
         "<b>Look-alike address:</b> paypa1.com, amaz0n-support.net",
         "<b>Replies go somewhere else</b> than the sender."],
  todo_t="If it looks like a scam",
  todo=["Do not click links or call numbers in the email.",
        "Go to the real website yourself, or call a number you trust (on your card or bill).",
        "Never send passwords, codes or bank details by email.",
        "Report it: <b>reportfraud.ftc.gov</b> and “Report phishing” in your mail app."],
  privacy="🔒 Nothing you paste is saved or sent anywhere. The tool never asks for a password.",
  limit="A ✅ means the owner of the address sent it, not that it is safe. A hacked account still passes.",
  foot="Who Really Sent This? · Free · English & Español · A ChiEAC fellowship project"),
 "es": dict(
  title="¿Es real este correo?", sub="Revíselo en 3 pasos, gratis",
  steps=["<b>Abra</b> who-really-sent-this.streamlit.app <span class=m>(o escanee el código)</span> y elija <b>Español</b>.",
         "<b>Copie las líneas ocultas del correo (encabezados).</b><br><span class=m>Gmail: ⋮ → Mostrar original · Outlook.com: … → Ver → Ver origen del mensaje · Yahoo: … → Ver mensaje sin formato</span>",
         "<b>Péguelas</b> en el cuadro y haga clic en <b>Revisar este correo</b>."],
  results=[("✅","Parece legítimo","Vino de esa dirección. Si pide dinero o contraseñas, confírmelo por otro medio."),
           ("⚠️","Tenga cuidado","Algo no está bien. Confírmelo primero por otro medio."),
           ("⛔","Probablemente es una estafa","No es de quien dice ser. No haga clic, no responda y no pague.")],
  signs_t="5 señales de alerta",
  signs=["<b>Prisa o miedo:</b> “Su cuenta se cierra hoy.”",
         "<b>Pide</b> dinero, tarjetas de regalo, contraseñas o códigos.",
         "<b>El nombre y la dirección no coinciden:</b> “Chase Bank” desde una dirección de Gmail.",
         "<b>Dirección parecida:</b> paypa1.com, amaz0n-support.net",
         "<b>Las respuestas van a otra dirección</b> distinta de la que lo envió."],
  todo_t="Si parece una estafa",
  todo=["No haga clic en los enlaces ni llame a los teléfonos del correo.",
        "Vaya usted mismo al sitio web real o llame a un número que ya conoce (de su tarjeta o factura).",
        "Nunca envíe contraseñas, códigos ni datos bancarios por correo.",
        "Repórtelo: <b>reportefraude.ftc.gov</b> y “Denunciar suplantación de identidad” en su aplicación de correo."],
  privacy="🔒 Nada de lo que pegue se guarda ni se envía. La herramienta nunca pide contraseñas.",
  limit="✅ significa que el dueño de la dirección lo envió, no que sea seguro. Una cuenta hackeada también pasa.",
  foot="¿Quién envió esto de verdad? · Gratis · Español e inglés · Un proyecto de la beca ChiEAC"),
}

CSS = """
@page{size:Letter;margin:0.5in}
*{box-sizing:border-box}
body{font-family:'DejaVu Sans',Arial,sans-serif;color:#1d2433;font-size:12.5pt;line-height:1.35;margin:0}
.top{display:flex;justify-content:space-between;align-items:center;border-bottom:4px solid #1F3864;padding-bottom:8px}
h1{font-size:30pt;margin:0;color:#1F3864} .sub{font-size:14pt;margin:2px 0 0}
.qr{text-align:center;font-size:8.5pt} .qr img{width:1.25in;height:1.25in;display:block}
h2{font-size:15pt;color:#1F3864;margin:14px 0 6px}
ol{margin:0;padding-left:1.4em} li{margin:0 0 5px}
.m{font-size:10pt;color:#4a5263}
.res{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:6px}
.res div{border:2px solid #d7dce6;border-radius:8px;padding:7px;font-size:10.5pt}
.res b{display:block;font-size:12.5pt;margin-bottom:2px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:18px}
ul{margin:0;padding-left:1.2em} ul li{margin-bottom:5px}
.note{background:#eef2f9;border-radius:8px;padding:8px 10px;margin-top:12px;font-size:11pt}
.foot{margin-top:12px;border-top:1px solid #d7dce6;padding-top:6px;font-size:9.5pt;color:#4a5263;text-align:center}
"""


def qr_data_uri() -> str:
    img = qrcode.make(URL, box_size=8, border=1)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def html(lang: str, qr: str) -> str:
    t = TEXT[lang]
    steps = "".join(f"<li>{s}</li>" for s in t["steps"])
    res = "".join(f"<div><b>{i} {h}</b>{d}</div>" for i, h, d in t["results"])
    signs = "".join(f"<li>{s}</li>" for s in t["signs"])
    todo = "".join(f"<li>{s}</li>" for s in t["todo"])
    return f"""<!DOCTYPE html><html lang="{lang}"><head><meta charset="utf-8"><title>{t['title']}</title>
<style>{CSS}</style></head><body>
<div class=top><div><h1>{t['title']}</h1><p class=sub>{t['sub']}</p></div>
<div class=qr><img src="{qr}" alt="QR code">{URL.replace('https://','')}</div></div>
<ol style="margin-top:12px">{steps}</ol>
<div class=res>{res}</div>
<div class=cols><div><h2>{t['signs_t']}</h2><ul>{signs}</ul></div>
<div><h2>{t['todo_t']}</h2><ul>{todo}</ul></div></div>
<div class=note>{t['privacy']}<br>{t['limit']}</div>
<div class=foot>{t['foot']}</div>
</body></html>"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    qr = qr_data_uri()
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        for lang in TEXT:
            doc = html(lang, qr)
            (OUT / f"handout-{lang}.html").write_text(doc, encoding="utf-8")
            page.set_content(doc)
            page.pdf(path=str(OUT / f"handout-{lang}.pdf"), format="Letter", print_background=True,
                     margin={"top": "0.5in", "bottom": "0.5in", "left": "0.5in", "right": "0.5in"})
        browser.close()


if __name__ == "__main__":
    main()
