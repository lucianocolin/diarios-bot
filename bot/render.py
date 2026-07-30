"""Render del digest: texto plano para WhatsApp y una página HTML."""

from __future__ import annotations

import html
from .aggregate import Digest

SALUDO = {"tarde": "Resumen del mediodía", "noche": "Resumen de la noche"}


def _franja(digest: Digest) -> str:
    return "tarde" if digest.generado.hour < 18 else "noche"


def _fecha_larga(digest: Digest) -> str:
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]
    d = digest.generado
    return f"{dias[d.weekday()]} {d.day} de {meses[d.month - 1]}"


def texto(digest: Digest) -> str:
    """Digest completo en texto. Sirve para mensajes libres y para el log."""
    partes = [
        f"*{SALUDO[_franja(digest)]}* — {_fecha_larga(digest)}",
        f"_{len(digest.articulos)} notas de {len(digest.por_medio)} diarios_",
        "",
    ]
    for medio, notas in digest.por_medio.items():
        marca = "" if notas[0].ranking == "real" else " (portada)"
        partes.append(f"*{medio}*{marca}")
        for i, a in enumerate(notas, 1):
            partes.append(f"{i}. {a.titulo}\n{a.url}")
        partes.append("")
    if digest.fallidos:
        partes.append(f"_Sin datos: {', '.join(digest.fallidos)}_")
    return "\n".join(partes).strip()


def texto_telegram(digest: Digest) -> str:
    """Mismo digest, con el markup HTML que entiende Telegram.

    Va todo escapado: los títulos traen comillas y las URLs traen `&` en el
    query string, que con `parse_mode=HTML` Telegram interpretaría como entidad.
    """
    e = html.escape
    partes = [
        f"<b>{e(SALUDO[_franja(digest)])}</b> — {e(_fecha_larga(digest))}",
        f"<i>{len(digest.articulos)} notas de {len(digest.por_medio)} diarios</i>",
        "",
    ]
    for medio, notas in digest.por_medio.items():
        marca = "" if notas[0].ranking == "real" else " (portada)"
        partes.append(f"<b>{e(medio)}</b>{e(marca)}")
        for i, a in enumerate(notas, 1):
            partes.append(f"{i}. {e(a.titulo)}\n{e(a.url)}")
        partes.append("")
    if digest.fallidos:
        partes.append(f"<i>Sin datos: {e(', '.join(digest.fallidos))}</i>")
    return "\n".join(partes).strip()


def trozos(texto_completo: str, limite: int = 4000) -> list[str]:
    """Parte el texto en mensajes que entren en el límite del canal.

    Corta entre bloques (párrafo vacío) para no partir una nota al medio.
    WhatsApp y Telegram topean los dos en 4096; se deja margen.
    """
    salida, actual = [], ""
    for bloque in texto_completo.split("\n\n"):
        if len(actual) + len(bloque) + 2 > limite:
            if actual:
                salida.append(actual.strip())
            actual = ""
        actual += bloque + "\n\n"
    if actual.strip():
        salida.append(actual.strip())
    return salida


# El nombre viejo, para no romper nada que lo importe.
trozos_whatsapp = trozos


def pagina_html(digest: Digest) -> str:
    """Página estática con las 50 notas, para linkear desde la plantilla."""
    e = html.escape
    filas = []
    for medio, notas in digest.por_medio.items():
        real = notas[0].ranking == "real"
        etiqueta = (
            '<span class="tag real">ranking del diario</span>'
            if real
            else '<span class="tag proxy">orden de portada</span>'
        )
        items = "\n".join(
            f'<li><a href="{e(a.url)}" target="_blank" rel="noopener">{e(a.titulo)}</a></li>'
            for a in notas
        )
        filas.append(
            f'<section><h2>{e(medio)} {etiqueta}</h2><ol>{items}</ol></section>'
        )

    faltantes = (
        f'<p class="nota">Sin datos en esta corrida: {e(", ".join(digest.fallidos))}.</p>'
        if digest.fallidos
        else ""
    )

    return f"""<!doctype html>
<html lang="es"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(SALUDO[_franja(digest)])} — {e(_fecha_larga(digest))}</title>
<style>
  :root {{ color-scheme: light dark; --fg:#16181d; --bg:#fff; --muted:#5b6472; --line:#e3e6ea; --link:#0b57d0; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --fg:#e8eaed; --bg:#14161a; --muted:#9aa4b2; --line:#2a2e35; --link:#8ab4f8; }}
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; padding:1.5rem 1rem 4rem; background:var(--bg); color:var(--fg);
    font:16px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    max-width:44rem; margin-inline:auto; }}
  h1 {{ font-size:1.5rem; margin:0 0 .25rem; }}
  .sub {{ color:var(--muted); margin:0 0 2rem; font-size:.95rem; }}
  section {{ border-top:1px solid var(--line); padding-top:1.25rem; margin-top:1.75rem; }}
  h2 {{ font-size:1.05rem; margin:0 0 .75rem; display:flex; flex-wrap:wrap; gap:.5rem; align-items:center; }}
  .tag {{ font-size:.7rem; font-weight:600; text-transform:uppercase; letter-spacing:.04em;
    padding:.15rem .5rem; border-radius:999px; }}
  .tag.real {{ background:#e6f4ea; color:#137333; }}
  .tag.proxy {{ background:#fef7e0; color:#8a6100; }}
  @media (prefers-color-scheme: dark) {{
    .tag.real {{ background:#0f2a18; color:#7ee2a8; }}
    .tag.proxy {{ background:#2e2510; color:#f5c765; }}
  }}
  ol {{ margin:0; padding-left:1.35rem; }}
  li {{ margin-bottom:.6rem; }}
  a {{ color:var(--link); text-decoration:none; }}
  a:hover {{ text-decoration:underline; }}
  .nota {{ color:var(--muted); font-size:.85rem; margin-top:2.5rem; }}
</style></head><body>
<h1>{e(SALUDO[_franja(digest)])}</h1>
<p class="sub">{e(_fecha_larga(digest))} · {len(digest.articulos)} notas de {len(digest.por_medio)} diarios
· actualizado {digest.generado:%H:%M}</p>
{"".join(filas)}
{faltantes}
<p class="nota">Los diarios marcados como <em>orden de portada</em> no publican su ranking
de lecturas; en esos casos el orden refleja la jerarquía que les da la portada.</p>
</body></html>"""
