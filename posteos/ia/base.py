"""Piezas comunes a todos los proveedores de IA: estructuras de datos, pedidos y orquestación."""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Literal

from pydantic import BaseModel

from posteos.config import PerfilAnalizado
from posteos.media import Adjunto
from posteos.opciones import REDES, zona_horaria

DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")

Progreso = Callable[[str], None]


class ErrorIA(Exception):
    pass


class Cancelado(Exception):
    pass


# --- Estructura de la respuesta de generación ---------------------------------

ClaveRed = Literal["linkedin", "instagram", "facebook", "x", "whatsapp", "tiktok", "threads", "youtube"]


class PostRed(BaseModel):
    red: ClaveRed
    formato_recomendado: str
    gancho: str
    texto: str
    hashtags: list[str]
    llamada_a_la_accion: str
    mejor_dia: str
    mejor_horario: str
    justificacion_horario: str
    como_usar_el_material: str
    texto_alternativo_imagen: str
    variante_ab: str
    consejos: list[str]


class IdeaAudiovisual(BaseModel):
    tipo: str
    titulo: str
    descripcion: str
    redes: list[str]
    estructura: list[str]
    duracion_sugerida: str


class EntradaCalendario(BaseModel):
    red: str
    dia: str
    horario: str
    accion: str


class ResultadoPosts(BaseModel):
    resumen_estrategia: str
    analisis_del_material: str
    posts: list[PostRed]
    ideas_audiovisuales: list[IdeaAudiovisual]
    calendario: list[EntradaCalendario]
    advertencias: list[str]


@dataclass
class SolicitudPost:
    idea: str
    redes: list[str]
    objetivo: str
    tono: str
    publico: str
    variante: str
    longitud: str
    emojis: str
    hashtags: str
    llamada_a_la_accion: str
    pais: str
    marca: str = ""
    adjuntos: list[Adjunto] = field(default_factory=list)
    perfil: PerfilAnalizado | None = None
    investigar_web: bool = True
    instrucciones_extra: str = ""


@dataclass
class ResultadoGeneracion:
    posts: ResultadoPosts
    investigacion: str = ""
    modelo: str = ""


@dataclass
class PedidoAnalisis:
    url: str
    red: str | None
    texto: str
    capturas: list[Adjunto] = field(default_factory=list)


# --- Proveedor base -------------------------------------------------------------


class Proveedor(ABC):
    """Interfaz común. Cada proveedor implementa las tres llamadas a su IA."""

    nombre = ""

    def __init__(self, modelo: str, progreso: Progreso | None = None, texto_parcial: Progreso | None = None) -> None:
        self.modelo = modelo
        self._progreso = progreso or (lambda _m: None)
        self._texto_parcial = texto_parcial
        self._cancelado = threading.Event()

    def cancelar(self) -> None:
        self._cancelado.set()

    def _verificar_cancelacion(self) -> None:
        if self._cancelado.is_set():
            raise Cancelado()

    # Cada proveedor implementa estas tres operaciones.

    @abstractmethod
    def _analizar(self, pedido: PedidoAnalisis) -> str:
        """Devuelve el informe en Markdown (con fuentes si las hay)."""

    @abstractmethod
    def _investigar(self, solicitud: SolicitudPost, texto: str) -> str:
        """Devuelve notas en Markdown sobre horarios y formatos (con fuentes si las hay)."""

    @abstractmethod
    def _generar(self, solicitud: SolicitudPost, pedido: str) -> tuple[ResultadoPosts, str]:
        """Devuelve las publicaciones y el nombre del modelo que respondió."""

    def es_error_de_credenciales(self, error: Exception) -> bool:
        return False

    # Operaciones públicas, iguales para todos los proveedores.

    def analizar_cuenta(
        self,
        url: str,
        red: str | None,
        metadatos: str,
        texto_pegado: str = "",
        notas: str = "",
        capturas: list[Adjunto] | None = None,
    ) -> str:
        texto = pedido_analisis(url, red, metadatos, texto_pegado, notas, len(capturas or []))
        self._progreso("Analizando la cuenta con IA…")
        self._verificar_cancelacion()
        return self._analizar(PedidoAnalisis(url=url, red=red, texto=texto, capturas=list(capturas or [])))

    def investigar_estrategia(self, solicitud: SolicitudPost) -> str:
        self._progreso("Investigando en la web los mejores días, horarios y formatos…")
        self._verificar_cancelacion()
        return self._investigar(solicitud, pedido_investigacion(solicitud))

    def generar_posts(self, solicitud: SolicitudPost) -> ResultadoGeneracion:
        if not solicitud.idea.strip() and not solicitud.adjuntos:
            raise ErrorIA("Escriba una idea o adjunte una imagen o un video.")
        if not solicitud.redes:
            raise ErrorIA("Seleccione al menos una red social.")

        investigacion = ""
        if solicitud.investigar_web:
            try:
                investigacion = self.investigar_estrategia(solicitud)
            except Cancelado:
                raise
            except Exception as e:
                if self.es_error_de_credenciales(e):
                    raise
                from posteos.ia.errores import describir_error

                self._progreso(f"No se pudo completar la investigación web ({describir_error(e)}). Se continúa sin ella.")

        self._progreso("Redactando las publicaciones…")
        self._verificar_cancelacion()
        posts, modelo = self._generar(solicitud, construir_pedido(solicitud, investigacion))
        return ResultadoGeneracion(posts=posts, investigacion=investigacion, modelo=modelo)


# --- Textos de los pedidos -------------------------------------------------------


def fecha_actual() -> str:
    hoy = datetime.now()
    return f"{DIAS[hoy.weekday()]} {hoy:%d/%m/%Y}"


def pedido_analisis(url: str, red: str | None, metadatos: str, texto_pegado: str, notas: str, capturas: int) -> str:
    nombre_red = REDES[red].nombre if red else "no identificada"
    partes = [
        f"Fecha de hoy: {fecha_actual()}.",
        f"Enlace a analizar: {url}",
        f"Red social detectada: {nombre_red}.",
        "Metadatos públicos leídos desde el equipo del usuario:\n" + (metadatos or "(sin datos)"),
    ]
    if texto_pegado.strip():
        partes.append("Texto de publicaciones de la cuenta, pegado por el usuario:\n" + texto_pegado.strip())
    if notas.strip():
        partes.append("Qué le interesa saber al usuario:\n" + notas.strip())
    if capturas:
        partes.append(f"Se adjuntan {capturas} capturas o archivos de la cuenta para analizar.")
    partes.append("Lee el enlace, complementa con búsquedas y entrega el informe completo.")
    return "\n\n".join(partes)


def pedido_investigacion(solicitud: SolicitudPost) -> str:
    redes = ", ".join(REDES[r].nombre for r in solicitud.redes)
    return (
        f"Fecha de hoy: {fecha_actual()}.\n"
        f"Redes sociales: {redes}.\n"
        f"País: {solicitud.pais} (zona horaria {zona_horaria(solicitud.pais)}).\n"
        f"Sector o marca: {solicitud.marca or 'no especificado'}.\n"
        f"Público: {solicitud.publico}.\n"
        f"Objetivo de la publicación: {solicitud.objetivo}.\n"
        f"Material disponible: {resumen_material(solicitud.adjuntos)}.\n"
        f"Tema de la publicación: {solicitud.idea[:500]}\n\n"
        "Investiga los mejores días, horarios y formatos para publicar en cada una de esas redes."
    )


def construir_pedido(solicitud: SolicitudPost, investigacion: str) -> str:
    zona = zona_horaria(solicitud.pais)
    secciones = [f"Fecha de hoy: {fecha_actual()}."]
    secciones.append("## Idea para publicar\n" + (solicitud.idea.strip() or "(Sin texto: basarse en el material adjunto.)"))

    preferencias = [
        f"- Objetivo: {solicitud.objetivo}",
        f"- Tono: {solicitud.tono}",
        f"- Público objetivo: {solicitud.publico}",
        f"- Variante del español: {solicitud.variante}",
        f"- Longitud: {solicitud.longitud}",
        f"- Emojis: {solicitud.emojis}",
        f"- Hashtags: {solicitud.hashtags}",
        f"- Llamada a la acción: {solicitud.llamada_a_la_accion}",
        f"- País y zona horaria para los horarios: {solicitud.pais} ({zona})",
    ]
    secciones.append("## Preferencias\n" + "\n".join(preferencias))
    if solicitud.marca.strip():
        secciones.append("## Sobre la marca o persona que publica\n" + solicitud.marca.strip())
    if solicitud.instrucciones_extra.strip():
        secciones.append("## Indicaciones adicionales del usuario\n" + solicitud.instrucciones_extra.strip())

    redes = []
    for clave in solicitud.redes:
        red = REDES[clave]
        practicas = "\n".join(f"  - {p}" for p in red.buenas_practicas)
        redes.append(
            f"### {red.nombre} (clave: {clave})\n"
            f"- Límite de caracteres: {red.limite_caracteres}; visibles antes de «ver más»: {red.caracteres_visibles}\n"
            f"- Formatos posibles: {', '.join(red.formatos)}\n"
            f"- Buenas prácticas:\n{practicas}"
        )
    secciones.append("## Redes de destino (una publicación por cada una)\n" + "\n\n".join(redes))

    if solicitud.perfil:
        secciones.append(
            f"## Cuenta de referencia analizada: {solicitud.perfil.nombre} ({solicitud.perfil.url})\n"
            "Imita su estilo y estructura según este análisis:\n\n" + solicitud.perfil.analisis
        )
    if investigacion:
        secciones.append("## Investigación web sobre horarios y formatos\n" + investigacion)
    else:
        secciones.append(
            "## Investigación web\nNo se realizó. Recomienda días y horarios según tu conocimiento y acláralo."
        )
    if solicitud.adjuntos:
        secciones.append(
            "## Material adjunto\nA continuación van las imágenes y los videos (o sus fotogramas). "
            "Analízalos y construye las publicaciones alrededor de ellos."
        )
    return "\n\n".join(secciones)


def resumen_material(adjuntos: list[Adjunto]) -> str:
    if not adjuntos:
        return "solo texto"
    imagenes = sum(1 for a in adjuntos if a.tipo == "imagen")
    videos = sum(1 for a in adjuntos if a.tipo == "video")
    partes = []
    if imagenes:
        partes.append(f"{imagenes} imagen(es)")
    if videos:
        partes.append(f"{videos} video(s)")
    return " y ".join(partes)


def con_fuentes(texto: str, fuentes: list[tuple[str, str]]) -> str:
    """Agrega al final la lista de fuentes (url, título) sin repetir."""
    unicas: dict[str, str] = {}
    for url, titulo in fuentes:
        if url and url not in unicas:
            unicas[url] = titulo or url
    if not unicas:
        return texto
    lista = "\n".join(f"- [{titulo}]({url})" for url, titulo in list(unicas.items())[:25])
    return f"{texto}\n\n---\n**Fuentes consultadas**\n\n{lista}"


def validar_resultado(texto: str) -> ResultadoPosts:
    """Convierte el JSON devuelto por la IA en ResultadoPosts, tolerando texto alrededor."""
    from pydantic import ValidationError

    limpio = texto.strip()
    if not limpio.startswith("{"):
        inicio, fin = limpio.find("{"), limpio.rfind("}")
        if inicio >= 0 and fin > inicio:
            limpio = limpio[inicio : fin + 1]
    try:
        return ResultadoPosts.model_validate_json(limpio)
    except (ValidationError, ValueError) as e:
        raise ErrorIA("La respuesta de la IA no tuvo el formato esperado. Intente de nuevo.") from e
