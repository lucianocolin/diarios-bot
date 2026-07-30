"""Envío por Telegram Bot API.

A diferencia de WhatsApp, Telegram no tiene plantillas ni ventana de 24 h: el bot
puede escribir cuando quiera, siempre que la persona le haya dado /start alguna
vez. El tope es de 4096 caracteres por mensaje, así que el digest entero (unos
12.000) sale partido en 3 o 4 mensajes, con los títulos y los links adentro.

Se manda con `parse_mode=HTML` y todo el contenido escapado: los títulos de
diarios traen comillas y guiones bajos que romperían el parser de Markdown, y
las URLs suelen tener `&` en el query string.
"""

from __future__ import annotations

import logging

import requests

from .config import ErrorDeEnvio, cfg

log = logging.getLogger(__name__)

API = "https://api.telegram.org"
TIMEOUT = 30
LIMITE = 4096


def _post(metodo: str, payload: dict) -> dict:
    token = cfg("TELEGRAM_TOKEN")
    r = requests.post(f"{API}/bot{token}/{metodo}", json=payload, timeout=TIMEOUT)
    if r.status_code >= 400:
        raise ErrorDeEnvio(f"HTTP {r.status_code}: {r.text[:400]}")
    datos = r.json()
    if not datos.get("ok"):
        raise ErrorDeEnvio(f"Telegram respondió ok=false: {str(datos)[:400]}")
    return datos["result"]


def enviar(destino: str, trozos: list[str]) -> list[dict]:
    """Manda el digest completo, un mensaje por trozo.

    `disable_web_page_preview` es importante: sin eso Telegram intentaría armar
    una tarjeta de vista previa por cada uno de los 50 links.
    """
    respuestas = []
    for i, trozo in enumerate(trozos, 1):
        if len(trozo) > LIMITE:
            raise ErrorDeEnvio(
                f"El trozo {i} tiene {len(trozo)} caracteres y el tope es {LIMITE}"
            )
        respuestas.append(
            _post(
                "sendMessage",
                {
                    "chat_id": destino,
                    "text": trozo,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
            )
        )
    return respuestas


def quien_soy() -> dict:
    """Devuelve los datos del bot. Sirve para validar el token sin mandar nada."""
    return _post("getMe", {})


def chats_recientes() -> list[dict]:
    """Chats que le escribieron al bot, para averiguar el chat_id de destino.

    Solo funciona si no hay un webhook configurado y el mensaje es de las últimas
    24 h, que es el caso típico cuando recién se hace /start.
    """
    vistos, chats = set(), []
    for u in _post("getUpdates", {}):
        chat = (u.get("message") or u.get("channel_post") or {}).get("chat")
        if chat and chat["id"] not in vistos:
            vistos.add(chat["id"])
            chats.append(chat)
    return chats
