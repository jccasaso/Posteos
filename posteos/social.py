"""Detección de redes sociales a partir de enlaces y lectura de metadatos públicos."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urlparse

from posteos.opciones import REDES

AGENTE = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
MAX_BYTES = 2_000_000
META_INTERESANTES = {
    "description", "keywords", "author",
    "og:title", "og:description", "og:type", "og:site_name", "og:url", "og:image",
    "twitter:title", "twitter:description", "twitter:creator", "twitter:site",
    "profile:username", "video:duration", "article:published_time",
}


class ErrorEnlace(ValueError):
    pass


def normalizar_url(texto: str) -> str:
    url = texto.strip()
    if not url:
        raise ErrorEnlace("Ingrese un enlace.")
    if "://" not in url:
        url = "https://" + url
    partes = urlparse(url)
    if partes.scheme not in ("http", "https") or not partes.netloc or "." not in partes.netloc:
        raise ErrorEnlace("El enlace no es válido. Ejemplo: https://www.instagram.com/usuario")
    return url


def detectar_red(url: str) -> str | None:
    host = urlparse(url if "://" in url else "https://" + url).netloc.lower().split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    for clave, red in REDES.items():
        for dominio in red.dominios:
            if host == dominio or host.endswith("." + dominio):
                return clave
    return None


def nombre_sugerido(url: str) -> str:
    """Nombre corto para guardar el perfil (por ejemplo «@usuario · Instagram»)."""
    partes = urlparse(url)
    segmentos = [s for s in partes.path.split("/") if s]
    genericos = {"in", "company", "channel", "c", "user", "profile.php", "pages", "@", "channel", "school", "showcase"}
    usuario = next((s for s in segmentos if s.lower() not in genericos), "")
    red = detectar_red(url)
    etiqueta = REDES[red].nombre if red else partes.netloc
    if usuario:
        usuario = usuario if usuario.startswith("@") else "@" + usuario
        return f"{usuario} · {etiqueta}"
    return etiqueta


@dataclass
class MetadatosPagina:
    url_final: str = ""
    estado: int | None = None
    titulo: str = ""
    meta: dict[str, str] = field(default_factory=dict)
    datos_estructurados: list[str] = field(default_factory=list)
    error: str = ""

    def como_texto(self) -> str:
        if self.error and not (self.titulo or self.meta):
            return f"No se pudo leer la página directamente desde este equipo: {self.error}"
        lineas = [f"URL final: {self.url_final}", f"Código HTTP: {self.estado}"]
        if self.titulo:
            lineas.append(f"Título: {self.titulo}")
        for clave, valor in self.meta.items():
            lineas.append(f"{clave}: {valor}")
        for bloque in self.datos_estructurados:
            lineas.append(f"Datos estructurados (JSON-LD): {bloque}")
        return "\n".join(lineas)


class _LectorHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.titulo = ""
        self.meta: dict[str, str] = {}
        self.json_ld: list[str] = []
        self._en_titulo = False
        self._en_json_ld = False
        self._buffer: list[str] = []

    def handle_starttag(self, tag, attrs):
        atributos = {k.lower(): (v or "") for k, v in attrs}
        if tag == "title":
            self._en_titulo = True
        elif tag == "meta":
            clave = (atributos.get("property") or atributos.get("name") or "").lower()
            contenido = atributos.get("content", "").strip()
            if clave in META_INTERESANTES and contenido and clave not in self.meta:
                self.meta[clave] = contenido[:1000]
        elif tag == "script" and atributos.get("type", "").lower() == "application/ld+json":
            self._en_json_ld = True
            self._buffer = []

    def handle_endtag(self, tag):
        if tag == "title":
            self._en_titulo = False
        elif tag == "script" and self._en_json_ld:
            self._en_json_ld = False
            texto = "".join(self._buffer).strip()
            if texto and len(self.json_ld) < 3:
                try:
                    texto = json.dumps(json.loads(texto), ensure_ascii=False)
                except ValueError:
                    pass
                self.json_ld.append(texto[:3000])

    def handle_data(self, data):
        if self._en_titulo and not self.titulo:
            self.titulo = data.strip()[:300]
        elif self._en_json_ld:
            self._buffer.append(data)


def descargar_html(url: str, timeout: float = 12.0) -> tuple[str, int, str]:
    """Descarga una página (hasta 2 MB). Devuelve (html, código HTTP, url final). Lanza las excepciones de urllib."""
    peticion = urllib.request.Request(
        url,
        headers={
            "User-Agent": AGENTE,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.6",
        },
    )
    with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
        codificacion = respuesta.headers.get_content_charset() or "utf-8"
        contenido = respuesta.read(MAX_BYTES).decode(codificacion, errors="replace")
        return contenido, respuesta.status, respuesta.geturl()


def obtener_metadatos(url: str, timeout: float = 12.0) -> MetadatosPagina:
    """Lee los metadatos públicos (título, Open Graph, JSON-LD) de una página."""
    resultado = MetadatosPagina(url_final=url)
    try:
        contenido, resultado.estado, resultado.url_final = descargar_html(url, timeout)
    except urllib.error.HTTPError as e:
        resultado.estado = e.code
        resultado.error = f"el sitio respondió con el código {e.code}"
        return resultado
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        resultado.error = str(getattr(e, "reason", e))
        return resultado

    lector = _LectorHTML()
    try:
        lector.feed(contenido)
    except Exception as e:  # HTML mal formado: se conserva lo que se haya leído
        resultado.error = f"HTML parcialmente legible ({e})"
    resultado.titulo = lector.titulo
    resultado.meta = lector.meta
    resultado.datos_estructurados = lector.json_ld
    return resultado


class _ExtractorTexto(HTMLParser):
    IGNORAR = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "iframe", "template"}
    BLOQUES = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []
        self._ignorando = 0

    def handle_starttag(self, tag, attrs):
        if tag in self.IGNORAR:
            self._ignorando += 1
        elif tag in self.BLOQUES:
            self.partes.append("\n")

    def handle_endtag(self, tag):
        if tag in self.IGNORAR and self._ignorando:
            self._ignorando -= 1

    def handle_data(self, data):
        if not self._ignorando:
            self.partes.append(data)


def extraer_texto(html: str, max_caracteres: int = 4000) -> str:
    """Texto legible de una página HTML, sin scripts ni menús, recortado."""
    extractor = _ExtractorTexto()
    try:
        extractor.feed(html)
    except Exception:
        pass
    lineas = (" ".join(linea.split()) for linea in "".join(extractor.partes).splitlines())
    texto = "\n".join(linea for linea in lineas if len(linea) > 1)
    return texto[:max_caracteres]
