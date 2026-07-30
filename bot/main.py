"""Punto de entrada: arma el digest, publica la página y la manda por Telegram.

Uso:
    python -m bot.main --dry-run                  # no envía, deja la página en out/
    python -m bot.main                            # digest completo por Telegram
    python -m bot.main --canal whatsapp           # plantilla de Meta (ver README)
    python -m bot.main --canal whatsapp --modo libre

Telegram es el canal por defecto porque es el único donde el digest entero entra
en el mensaje: WhatsApp topea las plantillas en 1024 caracteres y el digest ronda
los 12.000.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import pathlib
import sys

from datetime import datetime

from . import render, telegram, whatsapp
from .aggregate import Digest, recolectar
from .config import ConfigFaltante, ErrorDeEnvio, cfg
from .sources import Articulo

log = logging.getLogger("diarios-bot")

SALIDA = pathlib.Path(os.environ.get("SALIDA_DIR", "out"))


def _digest_desde_json() -> Digest:
    """Reconstruye el digest ya generado, para no scrapear dos veces.

    Lo usa el workflow: primero genera y publica la página, después manda el
    mensaje a partir de este mismo JSON, así los números coinciden.
    """
    datos = json.loads((SALIDA / "digest.json").read_text(encoding="utf-8"))
    return Digest(
        generado=datetime.fromisoformat(datos["generado"]),
        articulos=[Articulo(**a) for a in datos["articulos"]],
        fallidos=datos.get("fallidos") or {},
    )


def _enviar(digest: Digest, args) -> None:
    """Manda el digest por el canal elegido."""
    if args.canal == "telegram":
        destino = cfg("TELEGRAM_CHAT_ID")
        cfg("TELEGRAM_TOKEN")  # falla acá y no a mitad del envío
        trozos = render.trozos(render.texto_telegram(digest), limite=telegram.LIMITE - 96)
        log.info("Enviando %d mensajes por Telegram...", len(trozos))
        telegram.enviar(destino, trozos)
        return

    destino = cfg("WHATSAPP_DESTINO")
    if args.modo == "libre":
        trozos = render.trozos(render.texto(digest))
        log.info("Enviando %d mensajes de texto libre por WhatsApp...", len(trozos))
        whatsapp.enviar_texto_libre(destino, trozos)
    else:
        franja = "mediodía" if digest.generado.hour < 18 else "noche"
        whatsapp.enviar_plantilla(
            destino,
            nombre_plantilla=cfg("WHATSAPP_PLANTILLA"),
            idioma=os.environ.get("WHATSAPP_IDIOMA", "es_AR"),
            parametros=[
                franja,
                str(len(digest.articulos)),
                str(len(digest.por_medio)),
            ],
            sufijo_url=os.environ.get("PAGINA_SUFIJO") or None,
        )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Digest de diarios argentinos")
    p.add_argument("--dry-run", action="store_true", help="no envía, solo genera archivos")
    p.add_argument(
        "--canal",
        choices=["telegram", "whatsapp"],
        default=os.environ.get("CANAL", "telegram"),
        help="telegram manda el digest completo; whatsapp requiere plantilla aprobada",
    )
    p.add_argument(
        "--modo",
        choices=["plantilla", "libre"],
        default=os.environ.get("MODO_ENVIO", "plantilla"),
        help="solo para --canal whatsapp: libre requiere ventana de 24 h abierta",
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
        ruta = SALIDA / "digest.json"
        if not ruta.exists():
            log.error("No existe %s; corré primero la generación.", ruta)
            return 1
        digest = _digest_desde_json()
        if args.dry_run:
            log.info("Dry-run: no se envía nada.")
            return 0
        _enviar(digest, args)
        log.info("Enviado por %s (%d notas).", args.canal, len(digest.articulos))
        return 0

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

    _enviar(digest, args)
    log.info("Enviado por %s (%d notas).", args.canal, len(digest.articulos))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ConfigFaltante as e:
        log.error("%s. Ver el README para el alta de credenciales.", e)
        sys.exit(2)
    except ErrorDeEnvio as e:
        log.error("El envío fue rechazado. %s", e)
        sys.exit(3)
