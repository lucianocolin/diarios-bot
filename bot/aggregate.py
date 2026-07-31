"""Junta las notas de todos los diarios y arma el digest."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from .sources import DIARIOS, SUPLENTES, Articulo, _canonical

log = logging.getLogger(__name__)

TZ = ZoneInfo("America/Argentina/Buenos_Aires")
POR_DIARIO = 5
# Se deriva de la cantidad de diarios: si el total quedara fijo, sumar un medio
# nuevo lo dejaría afuera por el recorte final, y encima en silencio.
TOTAL_OBJETIVO = len(DIARIOS) * POR_DIARIO
# Cuánto de más se le puede pedir a un diario para tapar el hueco de otro.
TOPE_POR_DIARIO = 10


@dataclass
class Digest:
    generado: datetime
    articulos: list[Articulo]
    fallidos: dict[str, str] = field(default_factory=dict)

    @property
    def por_medio(self) -> dict[str, list[Articulo]]:
        agrupado: dict[str, list[Articulo]] = {}
        for a in self.articulos:
            agrupado.setdefault(a.medio, []).append(a)
        return agrupado

    @property
    def medios_con_ranking_real(self) -> list[str]:
        return sorted({a.medio for a in self.articulos if a.ranking == "real"})


def _traer(nombre: str, fn, limite: int) -> tuple[str, list[Articulo] | Exception]:
    try:
        return nombre, fn(limite)
    except Exception as e:  # noqa: BLE001 - un diario caído no debe voltear el envío
        log.warning("%s falló: %s", nombre, e)
        return nombre, e


def recolectar(por_diario: int = POR_DIARIO, objetivo: int | None = None) -> Digest:
    """Trae `por_diario` notas de cada medio y completa hasta `objetivo`.

    Si un diario devuelve menos de lo pedido (o se cae), se le piden notas extra
    a los que sí respondieron, para no bajar del total. Los medios suplentes solo
    entran si sigue faltando.
    """
    objetivo = objetivo or TOTAL_OBJETIVO
    resultados: dict[str, list[Articulo]] = {}
    fallidos: dict[str, str] = {}

    with ThreadPoolExecutor(max_workers=len(DIARIOS)) as pool:
        futuros = [
            pool.submit(_traer, nombre, fn, por_diario) for nombre, fn in DIARIOS.items()
        ]
        for f in futuros:
            nombre, res = f.result()
            if isinstance(res, Exception):
                fallidos[nombre] = f"{type(res).__name__}: {res}"
            else:
                resultados[nombre] = res

    faltan = objetivo - sum(len(v) for v in resultados.values())

    # 1) Ampliar los diarios que sí respondieron.
    if faltan > 0:
        ampliables = [n for n in DIARIOS if n in resultados]
        pedido = por_diario
        while faltan > 0 and pedido < TOPE_POR_DIARIO:
            pedido += 1
            for nombre in ampliables:
                if faltan <= 0:
                    break
                _, res = _traer(nombre, DIARIOS[nombre], pedido)
                if isinstance(res, Exception) or len(res) <= len(resultados[nombre]):
                    continue
                nuevos = len(res) - len(resultados[nombre])
                resultados[nombre] = res[: len(resultados[nombre]) + min(nuevos, faltan)]
                faltan -= min(nuevos, faltan)

    # 2) Si todavía falta, entran los suplentes.
    if faltan > 0:
        for nombre, fn in SUPLENTES.items():
            if faltan <= 0:
                break
            _, res = _traer(nombre, fn, faltan)
            if not isinstance(res, Exception):
                resultados[nombre] = res
                faltan -= len(res)

    # Orden estable: el de DIARIOS, con los suplentes al final.
    orden = list(DIARIOS) + list(SUPLENTES)
    articulos: list[Articulo] = []
    vistos: set[str] = set()
    for nombre in orden:
        for a in resultados.get(nombre, []):
            clave = _canonical(a.url)
            if clave in vistos:  # la misma nota sindicada en dos medios
                continue
            vistos.add(clave)
            articulos.append(a)

    return Digest(datetime.now(TZ), articulos[:objetivo], fallidos)
