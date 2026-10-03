"""Proveedor Ollama: IA local, gratuita y privada. La búsqueda web se hace con DuckDuckGo."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse

import ollama

from posteos import busqueda, prompts
from posteos.ia.base import (
    ErrorIA,
    PedidoAnalisis,
    Progreso,
    Proveedor,
    ResultadoPosts,
    SolicitudPost,
    con_fuentes,
    validar_resultado,
)
from posteos.media import Adjunto, describir_adjunto, imagen_a_jpeg, repartir_imagenes
from posteos.opciones import REDES

URL_POR_DEFECTO = "http://localhost:11434"
CONTEXTO = 16384  # tokens de contexto (Ollama usa por defecto un valor menor)

SIN_HERRAMIENTAS = (
    "\n\nImportante: no tienes herramientas de búsqueda ni de navegación. Se te entregan resultados de una "
    "búsqueda web y el texto de algunas páginas: básate en ellos y en tu conocimiento, y cita las fuentes "
    "por su URL. Indica con claridad lo que no esté respaldado por esos resultados."
)


class ProveedorOllama(Proveedor):
    nombre = "Ollama"

    def __init__(
        self,
        url: str = URL_POR_DEFECTO,
        modelo: str = "gemma3:12b",
        progreso: Progreso | None = None,
        texto_parcial: Progreso | None = None,
        cliente: ollama.Client | None = None,
        region_busqueda: str = "xl-es",
    ) -> None:
        if not modelo.strip():
            raise ErrorIA("Elija un modelo de Ollama en la pestaña «Configuración».")
        super().__init__(modelo.strip(), progreso, texto_parcial)
        self.url = url or URL_POR_DEFECTO
        self.cliente = cliente or ollama.Client(host=self.url, timeout=900)
        self.region_busqueda = region_busqueda

    def es_error_de_credenciales(self, error: Exception) -> bool:
        # Si Ollama no está abierto o falta el modelo, no tiene sentido seguir con la redacción.
        return isinstance(error, (ConnectionError, ollama.ResponseError))

    # --- Operaciones ----------------------------------------------------------

    def _analizar(self, pedido: PedidoAnalisis) -> str:
        consultas = consultas_de_cuenta(pedido.url, pedido.red)
        resultados = busqueda.investigar(
            consultas, self.region_busqueda, self._progreso, self._verificar_cancelacion, paginas_por_consulta=1
        )
        self._progreso("Leyendo la página de la cuenta…")
        pagina = busqueda.texto_de_pagina(pedido.url, 6000)
        texto = pedido.texto
        if pagina:
            texto += f"\n\nTexto visible de la página {pedido.url}:\n{pagina}"
        texto += "\n\nResultados de búsqueda web sobre la cuenta:\n" + (busqueda.como_texto(resultados) or "(sin resultados)")
        texto_imagenes, imagenes = imagenes_de_adjuntos(pedido.capturas)
        self._progreso(f"Analizando con el modelo local {self.modelo} (puede tardar varios minutos)…")
        informe = self._conversar(prompts.SISTEMA_ANALISIS + SIN_HERRAMIENTAS, texto + texto_imagenes, imagenes, transmitir=True)
        return con_fuentes(informe, [(r.url, r.titulo) for r in resultados])

    def _investigar(self, solicitud: SolicitudPost, texto: str) -> str:
        resultados = busqueda.investigar(
            consultas_de_horarios(solicitud), busqueda.region_de(solicitud.pais), self._progreso, self._verificar_cancelacion
        )
        if not resultados:
            raise ErrorIA("la búsqueda web no devolvió resultados")
        texto += "\n\nResultados de búsqueda web:\n" + busqueda.como_texto(resultados)
        self._progreso(f"Resumiendo la investigación con el modelo local {self.modelo}…")
        notas = self._conversar(prompts.SISTEMA_INVESTIGACION + SIN_HERRAMIENTAS, texto)
        return con_fuentes(notas, [(r.url, r.titulo) for r in resultados])

    def _generar(self, solicitud: SolicitudPost, pedido: str) -> tuple[ResultadoPosts, str]:
        texto_imagenes, imagenes = imagenes_de_adjuntos(solicitud.adjuntos)
        self._progreso(f"Redactando con el modelo local {self.modelo} (puede tardar varios minutos)…")
        respuesta = self._conversar(
            prompts.SISTEMA_GENERACION, pedido + texto_imagenes, imagenes, formato=ResultadoPosts.model_json_schema()
        )
        return validar_resultado(respuesta), self.modelo

    # --- Llamada a Ollama -------------------------------------------------------

    def _conversar(
        self, sistema: str, texto: str, imagenes: list[bytes] | None = None, formato: dict | None = None, transmitir: bool = False
    ) -> str:
        mensaje: dict = {"role": "user", "content": texto}
        if imagenes:
            mensaje["images"] = imagenes
        partes: list[str] = []
        flujo = self.cliente.chat(
            model=self.modelo,
            messages=[{"role": "system", "content": sistema}, mensaje],
            stream=True,
            format=formato,
            options={"num_ctx": CONTEXTO},
        )
        for fragmento in flujo:
            self._verificar_cancelacion()
            contenido = fragmento.message.content or ""
            if contenido:
                partes.append(contenido)
                if transmitir and self._texto_parcial:
                    self._texto_parcial(contenido)
            if fragmento.done and fragmento.done_reason == "length":
                raise ErrorIA("La respuesta quedó incompleta. Pruebe con menos redes a la vez o con un modelo más grande.")
        return "".join(partes).strip()


def imagenes_de_adjuntos(adjuntos: list[Adjunto]) -> tuple[str, list[bytes]]:
    """Ollama recibe las imágenes al final del mensaje: se describe su orden en el texto."""
    if not adjuntos:
        return "", []
    lineas = ["\n\nLas imágenes adjuntas a este mensaje, en orden, corresponden a:"]
    imagenes: list[bytes] = []
    for numero, (adjunto, cuadros) in enumerate(repartir_imagenes(adjuntos), start=1):
        desde = len(imagenes) + 1
        imagenes.extend(imagen_a_jpeg(c) for c in cuadros)
        rango = f"imagen {desde}" if len(cuadros) == 1 else f"imágenes {desde} a {len(imagenes)}"
        detalle = " (fotogramas en orden cronológico)" if adjunto.tipo == "video" else ""
        lineas.append(f"- {rango}{detalle}: {describir_adjunto(numero, adjunto)}")
    return "\n".join(lineas), imagenes


def consultas_de_horarios(solicitud: SolicitudPost) -> list[str]:
    anio = datetime.now().year
    consultas = [f"mejor horario para publicar en {REDES[r].nombre} {solicitud.pais} {anio}" for r in solicitud.redes[:4]]
    if solicitud.marca.strip():
        sector = solicitud.marca.splitlines()[0].split(":", 1)[-1].strip()[:60]
        consultas.append(f"mejores días y horas para publicar en redes sociales {sector} {anio}")
    else:
        consultas.append(f"mejores días y horas para publicar en redes sociales {anio} estudio")
    return consultas


def consultas_de_cuenta(url: str, red: str | None) -> list[str]:
    segmentos = [s for s in urlparse(url).path.split("/") if s and s not in ("in", "company", "channel", "c", "user")]
    usuario = segmentos[0].lstrip("@") if segmentos else urlparse(url).netloc
    nombre_red = REDES[red].nombre if red else ""
    return [f"{usuario} {nombre_red}".strip(), f'"{usuario}" redes sociales']


def listar_modelos(url: str = URL_POR_DEFECTO) -> list[str]:
    respuesta = ollama.Client(host=url or URL_POR_DEFECTO, timeout=10).list()
    return sorted(m.model for m in respuesta.models if m.model)


def probar_conexion(url: str, modelo: str) -> str:
    instalados = listar_modelos(url)
    if not instalados:
        raise ErrorIA("Ollama está funcionando pero no tiene modelos. Descargue uno, por ejemplo: ollama pull gemma3:12b")
    if modelo not in instalados and f"{modelo}:latest" not in instalados:
        raise ErrorIA(
            f"Ollama está funcionando, pero el modelo «{modelo}» no está instalado. "
            f"Ejecute en una terminal: ollama pull {modelo}\n\nModelos instalados: {', '.join(instalados)}"
        )
    return f"{modelo} (Ollama local)"
