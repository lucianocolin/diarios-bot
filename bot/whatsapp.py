"""Envío por WhatsApp Cloud API (Meta).

Meta no deja mandar texto libre fuera de la ventana de 24 h desde el último
mensaje de la persona, así que un push programado a las 14 y a las 21 tiene que
salir como *plantilla aprobada*. Y los parámetros de plantilla no admiten saltos
de línea, por lo que las 50 notas no entran en el mensaje: la plantilla lleva un
resumen corto y un botón que abre la página con el listado completo.

Si ella ya escribió al bot en las últimas 24 h, `enviar_texto_libre` manda el
digest completo como mensaje común (útil para probar sin esperar aprobación).
"""

from __future__ import annotations

import logging

import requests

# Se reexportan para no romper a quien los importe desde acá.
from .config import ConfigFaltante, ErrorDeEnvio, cfg as _cfg  # noqa: F401

log = logging.getLogger(__name__)

API = "https://graph.facebook.com/v21.0"
TIMEOUT = 30


def _post(payload: dict) -> dict:
    phone_id = _cfg("WHATSAPP_PHONE_NUMBER_ID")
    token = _cfg("WHATSAPP_TOKEN")
    r = requests.post(
        f"{API}/{phone_id}/messages",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=TIMEOUT,
    )
    if r.status_code >= 400:
        raise ErrorDeEnvio(f"HTTP {r.status_code}: {r.text[:400]}")
    return r.json()


def enviar_plantilla(
    destino: str,
    *,
    nombre_plantilla: str,
    idioma: str,
    parametros: list[str],
    sufijo_url: str | None = None,
) -> dict:
    """Manda la plantilla aprobada. Es el camino normal del envío programado."""
    componentes: list[dict] = [
        {
            "type": "body",
            "parameters": [{"type": "text", "text": p} for p in parametros],
        }
    ]
    if sufijo_url is not None:
        # Botón de tipo URL dinámica: Meta concatena este sufijo a la base
        # configurada en la plantilla.
        componentes.append(
            {
                "type": "button",
                "sub_type": "url",
                "index": "0",
                "parameters": [{"type": "text", "text": sufijo_url}],
            }
        )
    return _post(
        {
            "messaging_product": "whatsapp",
            "to": destino,
            "type": "template",
            "template": {
                "name": nombre_plantilla,
                "language": {"code": idioma},
                "components": componentes,
            },
        }
    )


def enviar_texto_libre(destino: str, trozos: list[str]) -> list[dict]:
    """Manda el digest completo. Solo funciona dentro de la ventana de 24 h."""
    respuestas = []
    for trozo in trozos:
        respuestas.append(
            _post(
                {
                    "messaging_product": "whatsapp",
                    "to": destino,
                    "type": "text",
                    "text": {"body": trozo, "preview_url": False},
                }
            )
        )
    return respuestas
