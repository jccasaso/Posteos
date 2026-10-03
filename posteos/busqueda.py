"""Búsqueda web gratuita (DuckDuckGo) para los proveedores sin búsqueda integrada, como Ollama."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from posteos.social import descargar_html, extraer_texto

# Región de DuckDuckGo por país (los demás usan «Latinoamérica»).
REGIONES = {
    "Argentina": "ar-es",
    "Chile": "cl-es",
    "Colombia": "co-es",
    "España": "es-es",
    "México": "mx-es",
    "Perú": "pe-es",
    "Estados Unidos (hora del Este)": "us-es",
    "Estados Unidos (hora del Pacífico)": "us-es",
    "Internacional (varios países)": "wt-wt",
}


def region_de(pais: str) -> str:
    return REGIONES.get(pais, "xl-es")


@dataclass
class ResultadoBusqueda:
    titulo: str
    url: str
    resumen: str
    contenido: str = ""


def buscar(consulta: str, region: str = "xl-es", cantidad: int = 5) -> list[ResultadoBusqueda]:
    from ddgs import DDGS

    resultados = DDGS().text(consulta, region=region, max_results=cantidad)
    return [
        ResultadoBusqueda(titulo=r.get("title", ""), url=r.get("href", ""), resumen=r.get("body", ""))
        for r in resultados or []
        if r.get("href")
    ]


def texto_de_pagina(url: str, max_caracteres: int = 3500) -> str:
    try:
        html, _, _ = descargar_html(url, timeout=10.0)
    except Exception:
        return ""
    return extraer_texto(html, max_caracteres)


def investigar(
    consultas: list[str],
    region: str,
    progreso: Callable[[str], None] = lambda _m: None,
    verificar: Callable[[], None] = lambda: None,
    paginas_por_consulta: int = 2,
) -> list[ResultadoBusqueda]:
    """Ejecuta varias búsquedas y lee el texto de las primeras páginas de cada una."""
    vistos: set[str] = set()
    encontrados: list[ResultadoBusqueda] = []
    for consulta in consultas:
        verificar()
        progreso(f"Buscando en la web: «{consulta}»")
        try:
            resultados = buscar(consulta, region)
        except Exception:
            continue  # sin conexión o búsqueda limitada: se sigue con las demás
        leidas = 0
        for resultado in resultados:
            if resultado.url in vistos:
                continue
            vistos.add(resultado.url)
            if leidas < paginas_por_consulta:
                verificar()
                progreso(f"Leyendo la página: {resultado.url}")
                resultado.contenido = texto_de_pagina(resultado.url)
                leidas += 1
            encontrados.append(resultado)
    return encontrados


def como_texto(resultados: list[ResultadoBusqueda]) -> str:
    bloques = []
    for numero, r in enumerate(resultados, start=1):
        bloque = f"[{numero}] {r.titulo}\nURL: {r.url}\nResumen: {r.resumen}"
        if r.contenido:
            bloque += f"\nContenido de la página:\n{r.contenido}"
        bloques.append(bloque)
    return "\n\n".join(bloques)
