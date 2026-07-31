"""Tendencias de X (Twitter) en Argentina, para buscar videos virales.

X dejó de tener tier gratis en febrero de 2026: leer posts por la API oficial se
paga por uso. Pero las tendencias las publican agregadores públicos, y con el
tema en la mano se puede armar el link a la búsqueda de X. El bot no consulta la
API de X ni scrapea x.com: solo arma la URL, y el que hace la búsqueda es quien
toca el link.

Fuente principal trends24, con getdaytrends de respaldo: si una cambia el HTML,
la otra suele seguir andando.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

from .sources import HEADERS, TIMEOUT, SinResultados

log = logging.getLogger(__name__)

# La búsqueda pelada, sin filtros ni parámetros: X abre la pestaña "Top" por
# defecto y muestra lo más relevante del tema. Se probó con `filter:videos` y
# `f=top` y los links no abrían bien desde el celular.
BUSQUEDA = "https://x.com/search?q={q}"


@dataclass
class Tendencia:
    posicion: int
    termino: str
    url: str

    def dict(self) -> dict:
        return asdict(self)


def _link(termino: str) -> str:
    return BUSQUEDA.format(q=quote(termino))


def _trends24(limite: int) -> list[str]:
    r = requests.get("https://trends24.in/argentina/", headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    # La página trae 24 listas, una por hora. La primera es la más reciente.
    lista = soup.select_one("ol.trend-card__list")
    if lista is None:
        raise SinResultados("trends24: no apareció la lista de tendencias")
    return [a.get_text(strip=True) for a in lista.select("li a")][:limite]


def _getdaytrends(limite: int) -> list[str]:
    r = requests.get("https://getdaytrends.com/argentina/", headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    return [a.get_text(strip=True) for a in soup.select("td.main a")][:limite]


def tendencias_ar(limite: int = 10) -> list[Tendencia]:
    """Tendencias de X en Argentina, cada una con su link de búsqueda de videos."""
    terminos: list[str] = []
    for fuente in (_trends24, _getdaytrends):
        try:
            terminos = [t for t in fuente(limite) if t.strip()]
            if terminos:
                break
        except Exception as e:  # noqa: BLE001 - que falten tendencias no voltea el digest
            log.warning("Tendencias: %s falló (%s)", fuente.__name__, e)

    if not terminos:
        raise SinResultados("Tendencias: ninguna fuente respondió")

    vistos: set[str] = set()
    out: list[Tendencia] = []
    for t in terminos:
        clave = t.casefold()
        if clave in vistos:
            continue
        vistos.add(clave)
        out.append(Tendencia(len(out) + 1, t, _link(t)))
    return out
