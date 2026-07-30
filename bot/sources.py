"""Extractores de "más leídas" por diario.

Cada extractor devuelve una lista ordenada de Articulo. El campo `ranking` dice
si el orden es el ranking real de lecturas que publica el medio ("real") o si es
un proxy basado en la prominencia en portada ("portada"), porque no todos los
diarios exponen sus métricas de audiencia.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, asdict
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": UA, "Accept-Language": "es-AR,es;q=0.9"}
TIMEOUT = 25


@dataclass
class Articulo:
    medio: str
    titulo: str
    url: str
    posicion: int
    ranking: str  # "real" | "portada"

    def dict(self) -> dict:
        return asdict(self)


class SinResultados(Exception):
    """El extractor corrió pero no encontró notas."""


def _get(url: str, **kw) -> requests.Response:
    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, **kw)
    r.raise_for_status()
    return r


def _soup(url: str) -> BeautifulSoup:
    return BeautifulSoup(_get(url).text, "lxml")


def _cuerpo(soup: BeautifulSoup, quitar=("nav", "header", "footer", "aside")) -> BeautifulSoup:
    """Portada sin navegación: los menús y los 'temas del día' ensucian el orden."""
    raiz = soup.find("main") or soup.body
    for tag in raiz.find_all(list(quitar)):
        tag.decompose()
    return raiz


_PREFIJOS_RUIDO = re.compile(
    r"^(?:"
    r"\d{1,2}\s+"                        # numeración del ranking (Perfil)
    r"|hace\s+\d+\s+\w+\s*"              # "Hace 36 minutos" (La Voz)
    r"|en\s+vivo\s*"
    r"|🔴\s*"
    r")+",
    re.I,
)


def _limpiar_titulo(texto: str) -> str:
    t = re.sub(r"\s+", " ", texto or "").strip()
    t = _PREFIJOS_RUIDO.sub("", t).strip()
    # Varios medios anteponen una volanta corta seguida de punto; se conserva
    # porque suele aportar contexto ("Anuncio BCRA. Cómo será...").
    return t


def _titulo_de(a) -> str:
    """Título de un enlace de portada.

    Muchos medios meten titular y bajada dentro del mismo <a>; si hay un heading
    adentro, ese es el titular y el resto es resumen que no queremos arrastrar.
    """
    heading = a.find(["h1", "h2", "h3", "h4"])
    if heading:
        t = _limpiar_titulo(heading.get_text(" ", strip=True))
        if len(t) >= 28:
            return t
    t = _limpiar_titulo(a.get("title", ""))
    if len(t) >= 28:
        return t
    return _limpiar_titulo(a.get_text(" ", strip=True))


def _canonical(url: str) -> str:
    """Normaliza para deduplicar: sin querystring, sin barra final, sin esquema."""
    p = urlparse(url)
    path = p.path.rstrip("/")
    return urlunparse(("https", p.netloc.replace("www.", ""), path, "", "", ""))


def _es_nota(url: str, base: str) -> bool:
    """Filtra links que no son notas (secciones, tags, home, multimedia)."""
    p = urlparse(url)
    if p.netloc and urlparse(base).netloc.replace("www.", "") not in p.netloc.replace("www.", ""):
        return False
    path = p.path.strip("/")
    if not path or path.count("/") < 1:
        return False
    basura = (
        "/tema/", "/tags/", "/tag/", "/autor/", "/seccion/", "/video/", "/videos/",
        "/fotogaleria/", "/suscripcion", "/newsletter", "/podcast", "/en-vivo",
    )
    return not any(b in p.path for b in basura)


def _recolectar(
    contenedor,
    base: str,
    medio: str,
    ranking: str,
    limite: int,
    patron_nota: re.Pattern | None = None,
) -> list[Articulo]:
    """Saca (titulo, url) de los <a> de un contenedor, en orden de aparición.

    `patron_nota` permite exigir además un formato de URL propio del medio,
    útil donde la portada mezcla notas con widgets (cotizaciones, calculadoras).
    """
    vistos: set[str] = set()
    out: list[Articulo] = []
    for a in contenedor.find_all("a", href=True):
        url = urljoin(base, a["href"])
        if not _es_nota(url, base):
            continue
        if patron_nota and not patron_nota.search(url):
            continue
        clave = _canonical(url)
        if clave in vistos:
            continue
        titulo = _titulo_de(a)
        if len(titulo) < 28:
            continue
        vistos.add(clave)
        out.append(Articulo(medio, titulo, url, len(out) + 1, ranking))
        if len(out) >= limite:
            break
    return out


def _desde_rss(url: str, medio: str, limite: int, ranking: str = "portada") -> list[Articulo]:
    soup = BeautifulSoup(_get(url).text, "xml")
    out: list[Articulo] = []
    for item in soup.find_all("item"):
        link = item.find("link")
        title = item.find("title")
        if not link or not title:
            continue
        href = (link.text or "").strip()
        titulo = _limpiar_titulo(title.text)
        if not href or len(titulo) < 20:
            continue
        out.append(Articulo(medio, titulo, href, len(out) + 1, ranking))
        if len(out) >= limite:
            break
    if not out:
        raise SinResultados(f"{medio}: RSS sin items usables")
    return out


# --------------------------------------------------------------------------
# Extractores con ranking REAL (el medio publica su propio "más leídas")
# --------------------------------------------------------------------------


def lanacion(limite: int) -> list[Articulo]:
    soup = _soup("https://www.lanacion.com.ar/")
    encabezado = soup.find(
        lambda t: t.name in ("h2", "h3")
        and "más leídas" in t.get_text(strip=True).lower()
    )
    if not encabezado:
        raise SinResultados("La Nación: no apareció el módulo 'Más leídas'")
    caja = encabezado.find_next(class_=re.compile(r"ln-caja-ranking"))
    if caja is None:
        raise SinResultados("La Nación: no se encontró el contenedor del ranking")
    arts = _recolectar(caja, "https://www.lanacion.com.ar/", "La Nación", "real", limite)
    if not arts:
        raise SinResultados("La Nación: contenedor vacío")
    return arts


def ambito(limite: int) -> list[Articulo]:
    soup = _soup("https://www.ambito.com/")
    enlaces = soup.find_all("a", class_=re.compile(r"amb-masleidas-link"))
    if not enlaces:
        raise SinResultados("Ámbito: no apareció el módulo de más leídas")
    out: list[Articulo] = []
    vistos: set[str] = set()
    for a in enlaces:
        url = urljoin("https://www.ambito.com/", a.get("href", ""))
        titulo = _limpiar_titulo(a.get_text(" ", strip=True))
        clave = _canonical(url)
        if not titulo or clave in vistos:
            continue
        vistos.add(clave)
        out.append(Articulo("Ámbito", titulo, url, len(out) + 1, "real"))
        if len(out) >= limite:
            break
    return out


def perfil(limite: int) -> list[Articulo]:
    soup = _soup("https://www.perfil.com/mas-leidas")
    cuerpo = _cuerpo(soup)
    arts = _recolectar(cuerpo, "https://www.perfil.com/", "Perfil", "real", limite)
    if not arts:
        raise SinResultados("Perfil: la página de más leídas no devolvió notas")
    return arts


def minutouno(limite: int) -> list[Articulo]:
    soup = _soup("https://www.minutouno.com/")
    caja = soup.find(class_=re.compile(r"(m1-mas-leidas|most-read)"))
    if caja is None:
        raise SinResultados("Minuto Uno: no apareció el módulo de más leídas")
    arts = _recolectar(caja, "https://www.minutouno.com/", "Minuto Uno", "real", limite)
    if not arts:
        raise SinResultados("Minuto Uno: contenedor vacío")
    return arts


# --------------------------------------------------------------------------
# Extractores con proxy de PORTADA (el medio no publica su ranking)
# --------------------------------------------------------------------------


def infobae(limite: int) -> list[Articulo]:
    # El RSS de Infobae es "lo último" y se llena de cables menores; la portada
    # refleja mucho mejor qué está traccionando lecturas.
    soup = _soup("https://www.infobae.com/")
    cuerpo = _cuerpo(soup)
    arts = _recolectar(cuerpo, "https://www.infobae.com/", "Infobae", "portada", limite)
    if not arts:
        raise SinResultados("Infobae: portada sin notas detectables")
    return arts


# Las notas de Clarín siempre terminan en _0_<id>.html; el resto de los links de
# portada son calculadoras, cotizaciones y páginas de tema.
_CLARIN_NOTA = re.compile(r"_0_[A-Za-z0-9_-]+\.html$")


def clarin(limite: int) -> list[Articulo]:
    soup = _soup("https://www.clarin.com/")
    cuerpo = _cuerpo(soup)
    arts = _recolectar(
        cuerpo, "https://www.clarin.com/", "Clarín", "portada", limite, _CLARIN_NOTA
    )
    if not arts:
        raise SinResultados("Clarín: portada sin notas detectables")
    return arts


def tn(limite: int) -> list[Articulo]:
    soup = _soup("https://tn.com.ar/")
    cuerpo = _cuerpo(soup)
    arts = _recolectar(cuerpo, "https://tn.com.ar/", "TN", "portada", limite)
    if not arts:
        raise SinResultados("TN: portada sin notas detectables")
    return arts


def pagina12(limite: int) -> list[Articulo]:
    soup = _soup("https://www.pagina12.com.ar/")
    cuerpo = _cuerpo(soup)
    arts = _recolectar(cuerpo, "https://www.pagina12.com.ar/", "Página/12", "portada", limite)
    if not arts:
        raise SinResultados("Página/12: portada sin notas detectables")
    return arts


def cronista(limite: int) -> list[Articulo]:
    soup = _soup("https://www.cronista.com/")
    cuerpo = _cuerpo(soup)
    arts = _recolectar(cuerpo, "https://www.cronista.com/", "El Cronista", "portada", limite)
    if not arts:
        raise SinResultados("El Cronista: portada sin notas detectables")
    return arts


def c5n(limite: int) -> list[Articulo]:
    soup = _soup("https://www.c5n.com/")
    cuerpo = _cuerpo(soup)
    arts = _recolectar(cuerpo, "https://www.c5n.com/", "C5N", "portada", limite)
    if not arts:
        raise SinResultados("C5N: portada sin notas detectables")
    return arts


def lavoz(limite: int) -> list[Articulo]:
    # La Voz arma la portada dentro de <aside>, así que ahí no se puede podar;
    # sus feeds RSS además responden 403 detrás de Cloudflare.
    soup = _soup("https://www.lavoz.com.ar/")
    cuerpo = _cuerpo(soup, quitar=("nav", "header", "footer"))
    arts = _recolectar(cuerpo, "https://www.lavoz.com.ar/", "La Voz", "portada", limite)
    if not arts:
        raise SinResultados("La Voz: portada sin notas detectables")
    return arts


# Orden = orden en que aparecen en el digest.
DIARIOS: dict[str, callable] = {
    "infobae": infobae,
    "clarin": clarin,
    "lanacion": lanacion,
    "tn": tn,
    "pagina12": pagina12,
    "perfil": perfil,
    "ambito": ambito,
    "lavoz": lavoz,
    "cronista": cronista,
    "c5n": c5n,
}

# Suplentes para cubrir un medio caído sin bajar de 50 notas.
SUPLENTES: dict[str, callable] = {
    "minutouno": minutouno,
}
