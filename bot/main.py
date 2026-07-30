"""Punto de entrada: arma el digest, publica la página y lo manda por WhatsApp.

Uso:
    python -m bot.main --dry-run          # no envía nada, deja la página en out/
    python -m bot.main --modo libre       # texto completo (ventana de 24 h abierta)
    python -m bot.main                    # plantilla aprobada (envío programado)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import pathlib
import sys

from . import render, whatsapp
from .aggregate import recolectar

log = logging.getLogger("diarios-bot")

SALIDA = pathlib.Path(os.environ.get("SALIDA_DIR", "out"))


def _enviar_desde_json(args) -> int:
    """Avisa por WhatsApp usando el digest ya generado y publicado.

    Evita scrapear dos veces y garantiza que los números del mensaje coincidan
    con la página que ella va a abrir.
    """
    ruta = SALIDA / "digest.json"
    if not ruta.exists():
        log.error("No existe %s; corré primero la generación.", ruta)
        return 1
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    articulos = datos["articulos"]
    medios = {a["medio"] for a in articulos}
    hora = int(datos["generado"][11:13])
    franja = "mediodía" if hora < 18 else "noche"

    if args.dry_run:
        log.info("Dry-run: se habría avisado (%s, %d notas, %d diarios).",
                 franja, len(articulos), len(medios))
        return 0

    whatsapp.enviar_plantilla(
        whatsapp._cfg("WHATSAPP_DESTINO"),
        nombre_plantilla=whatsapp._cfg("WHATSAPP_PLANTILLA"),
        idioma=os.environ.get("WHATSAPP_IDIOMA", "es_AR"),
        parametros=[franja, str(len(articulos)), str(len(medios))],
        sufijo_url=os.environ.get("PAGINA_SUFIJO") or None,
    )
    log.info("Aviso enviado (%s, %d notas, %d diarios).", franja, len(articulos), len(medios))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Digest de diarios argentinos")
    p.add_argument("--dry-run", action="store_true", help="no envía, solo genera archivos")
    p.add_argument(
        "--modo",
        choices=["plantilla", "libre"],
        default=os.environ.get("MODO_ENVIO", "plantilla"),
        help="plantilla = envío programado; libre = requiere ventana de 24 h abierta",
    )
    p.add_argument("--notas", type=int, default=50, help="cantidad total de notas")
    p.add_argument(
        "--desde-json",
        action="store_true",
        help="no scrapea: envía a partir del digest.json ya generado",
    )
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )

    if args.desde_json:
        return _enviar_desde_json(args)

    digest = recolectar(objetivo=args.notas)
    log.info(
        "Recolectadas %d notas de %d diarios (%d con ranking real). Fallidos: %s",
        len(digest.articulos),
        len(digest.por_medio),
        len(digest.medios_con_ranking_real),
        ", ".join(digest.fallidos) or "ninguno",
    )

    if not digest.articulos:
        log.error("No se obtuvo ninguna nota; no se envía nada.")
        return 1

    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / "index.html").write_text(render.pagina_html(digest), encoding="utf-8")
    (SALIDA / "digest.txt").write_text(render.texto(digest), encoding="utf-8")
    (SALIDA / "digest.json").write_text(
        json.dumps(
            {
                "generado": digest.generado.isoformat(),
                "fallidos": digest.fallidos,
                "articulos": [a.dict() for a in digest.articulos],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    log.info("Archivos escritos en %s/", SALIDA)

    if args.dry_run:
        log.info("Dry-run: no se envía nada.")
        return 0

    destino = whatsapp._cfg("WHATSAPP_DESTINO")

    if args.modo == "libre":
        trozos = render.trozos_whatsapp(render.texto(digest))
        log.info("Enviando %d mensajes de texto libre...", len(trozos))
        whatsapp.enviar_texto_libre(destino, trozos)
    else:
        franja = "mediodía" if digest.generado.hour < 18 else "noche"
        whatsapp.enviar_plantilla(
            destino,
            nombre_plantilla=whatsapp._cfg("WHATSAPP_PLANTILLA"),
            idioma=os.environ.get("WHATSAPP_IDIOMA", "es_AR"),
            parametros=[
                franja,
                str(len(digest.articulos)),
                str(len(digest.por_medio)),
            ],
            sufijo_url=os.environ.get("PAGINA_SUFIJO") or None,
        )
    log.info("Enviado.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except whatsapp.ConfigFaltante as e:
        log.error("%s. Ver el README para el alta de credenciales.", e)
        sys.exit(2)
    except whatsapp.ErrorDeEnvio as e:
        log.error("WhatsApp rechazó el envío. %s", e)
        sys.exit(3)
