"""Conexión con la API de Claude: análisis de cuentas, investigación web y generación de posts."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Literal

import anthropic
from pydantic import BaseModel, ValidationError

from posteos import prompts
from posteos.config import PerfilAnalizado
from posteos.media import Adjunto, bloques_de_adjuntos
from posteos.opciones import REDES, zona_horaria

BETA_FALLBACK = "server-side-fallback-2026-07-01"
MAX_TOKENS = 64000
MAX_CONTINUACIONES = 5
BUSQUEDA_WEB = {"type": "web_search_20260209", "name": "web_search", "max_uses": 8}
LECTURA_WEB = {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 6}

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
class _Respuesta:
    texto: str
    fuentes: list[tuple[str, str]]
    parseado: object | None
    modelo: str


def fecha_actual() -> str:
    hoy = datetime.now()
    return f"{DIAS[hoy.weekday()]} {hoy:%d/%m/%Y}"


class MotorIA:
    def __init__(
        self,
        api_key: str,
        modelo: str = "claude-opus-5-5",
        esfuerzo: str = "high",
        progreso: Progreso | None = None,
        texto_parcial: Progreso | None = None,
        cliente: anthropic.Anthropic | None = None,
    ) -> None:
        if not api_key and cliente is None:
            raise ErrorIA("Falta la clave de API. Cárguela en la pestaña «Configuración».")
        self.cliente = cliente or anthropic.Anthropic(api_key=api_key, max_retries=3, timeout=900.0)
        self.modelo = modelo
        self.esfuerzo = esfuerzo
        self._progreso = progreso or (lambda _m: None)
        self._texto_parcial = texto_parcial
        self._cancelado = threading.Event()

    def cancelar(self) -> None:
        self._cancelado.set()

    # --- Tareas -------------------------------------------------------------

    def analizar_cuenta(
        self,
        url: str,
        red: str | None,
        metadatos: str,
        texto_pegado: str = "",
        notas: str = "",
        capturas: list[Adjunto] | None = None,
    ) -> str:
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
            partes.append(f"Se adjuntan {len(capturas)} capturas o archivos de la cuenta para analizar.")
        partes.append(
            "Lee el enlace con la herramienta web, complementa con búsquedas y entrega el informe completo."
        )
        contenido = [{"type": "text", "text": "\n\n".join(partes)}]
        if capturas:
            contenido.extend(bloques_de_adjuntos(capturas))

        self._progreso("Analizando la cuenta con IA…")
        respuesta = self._ejecutar(
            system=prompts.SISTEMA_ANALISIS,
            contenido=contenido,
            herramientas=[LECTURA_WEB, BUSQUEDA_WEB],
            transmitir_texto=True,
        )
        return _con_fuentes(respuesta.texto, respuesta.fuentes)

    def investigar_estrategia(self, solicitud: SolicitudPost) -> str:
        redes = ", ".join(REDES[r].nombre for r in solicitud.redes)
        zona = zona_horaria(solicitud.pais)
        tipo_material = _resumen_material(solicitud.adjuntos)
        texto = (
            f"Fecha de hoy: {fecha_actual()}.\n"
            f"Redes sociales: {redes}.\n"
            f"País: {solicitud.pais} (zona horaria {zona}).\n"
            f"Sector o marca: {solicitud.marca or 'no especificado'}.\n"
            f"Público: {solicitud.publico}.\n"
            f"Objetivo de la publicación: {solicitud.objetivo}.\n"
            f"Material disponible: {tipo_material}.\n"
            f"Tema de la publicación: {solicitud.idea[:500]}\n\n"
            "Investiga los mejores días, horarios y formatos para publicar en cada una de esas redes."
        )
        self._progreso("Investigando en la web los mejores días, horarios y formatos…")
        respuesta = self._ejecutar(
            system=prompts.SISTEMA_INVESTIGACION,
            contenido=[{"type": "text", "text": texto}],
            herramientas=[BUSQUEDA_WEB],
        )
        return _con_fuentes(respuesta.texto, respuesta.fuentes)

    def generar_posts(self, solicitud: SolicitudPost) -> ResultadoGeneracion:
        if not solicitud.idea.strip() and not solicitud.adjuntos:
            raise ErrorIA("Escriba una idea o adjunte una imagen o un video.")
        if not solicitud.redes:
            raise ErrorIA("Seleccione al menos una red social.")

        investigacion = ""
        if solicitud.investigar_web:
            try:
                investigacion = self.investigar_estrategia(solicitud)
            except (Cancelado, anthropic.AuthenticationError):
                raise
            except ErrorIA as e:
                self._progreso(f"No se pudo completar la investigación web ({e}). Se continúa sin ella.")
            except anthropic.APIError as e:
                self._progreso(f"No se pudo completar la investigación web ({describir_error(e)}). Se continúa sin ella.")

        contenido = [{"type": "text", "text": construir_pedido(solicitud, investigacion)}]
        contenido.extend(bloques_de_adjuntos(solicitud.adjuntos))

        self._progreso("Redactando las publicaciones…")
        respuesta = self._ejecutar(
            system=prompts.SISTEMA_GENERACION,
            contenido=contenido,
            output_format=ResultadoPosts,
        )
        posts = respuesta.parseado
        if not isinstance(posts, ResultadoPosts):
            try:
                posts = ResultadoPosts.model_validate(json.loads(respuesta.texto))
            except (ValueError, ValidationError) as e:
                raise ErrorIA("La respuesta de la IA no tuvo el formato esperado. Intente de nuevo.") from e
        return ResultadoGeneracion(posts=posts, investigacion=investigacion, modelo=respuesta.modelo)

    # --- Llamada a la API ---------------------------------------------------

    def _ejecutar(
        self,
        *,
        system: str,
        contenido: list[dict],
        herramientas: list[dict] | None = None,
        output_format: type[BaseModel] | None = None,
        transmitir_texto: bool = False,
    ) -> _Respuesta:
        mensajes: list[dict] = [{"role": "user", "content": contenido}]
        parametros: dict = {
            "model": self.modelo,
            "max_tokens": MAX_TOKENS,
            "system": system,
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": self.esfuerzo},
            # Si un filtro de seguridad rechaza la solicitud, la API reintenta con el modelo alternativo recomendado.
            "betas": [BETA_FALLBACK],
            "fallbacks": "default",
        }
        if herramientas:
            parametros["tools"] = herramientas
        if output_format is not None:
            parametros["output_format"] = output_format

        textos: list[str] = []
        fuentes: list[tuple[str, str]] = []
        final = None
        for _ in range(MAX_CONTINUACIONES):
            if self._cancelado.is_set():
                raise Cancelado()
            with self.cliente.beta.messages.stream(messages=mensajes, **parametros) as flujo:
                for evento in flujo:
                    if self._cancelado.is_set():
                        raise Cancelado()
                    self._informar(evento, transmitir_texto)
                final = flujo.get_final_message()
            for bloque in final.content:
                if bloque.type == "text":
                    textos.append(bloque.text)
                    for cita in bloque.citations or []:
                        url = getattr(cita, "url", None)
                        if url and url not in (u for u, _ in fuentes):
                            fuentes.append((url, getattr(cita, "title", None) or url))
            if final.stop_reason != "pause_turn":
                break
            # La búsqueda web alcanzó su límite de iteraciones: se reenvía el turno para que continúe.
            mensajes.append({"role": "assistant", "content": final.content})
        else:
            raise ErrorIA("La IA no terminó la tarea tras varios intentos.")

        if final.stop_reason == "refusal":
            raise ErrorIA("La IA rechazó esta solicitud por motivos de seguridad. Reformule la idea e intente de nuevo.")
        if final.stop_reason == "max_tokens":
            raise ErrorIA("La respuesta fue demasiado larga y quedó incompleta. Pruebe con menos redes a la vez.")
        return _Respuesta(
            texto="".join(textos).strip(),
            fuentes=fuentes,
            parseado=getattr(final, "parsed_output", None),
            modelo=final.model,
        )

    def _informar(self, evento, transmitir_texto: bool) -> None:
        tipo = evento.type
        if tipo == "content_block_start" and evento.content_block.type == "thinking":
            self._progreso("Pensando…")
        elif tipo == "content_block_stop" and evento.content_block.type == "server_tool_use":
            bloque = evento.content_block
            datos = bloque.input if isinstance(bloque.input, dict) else {}
            if bloque.name == "web_search":
                self._progreso(f"Buscando en la web: «{datos.get('query', '')}»")
            elif bloque.name == "web_fetch":
                self._progreso(f"Leyendo la página: {datos.get('url', '')}")
        elif tipo == "text" and transmitir_texto and self._texto_parcial:
            self._texto_parcial(evento.text)


# --- Utilidades ---------------------------------------------------------------


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
            "## Material adjunto\nA continuación van las imágenes y fotogramas de video. "
            "Analízalos y construye las publicaciones alrededor de ellos."
        )
    return "\n\n".join(secciones)


def _resumen_material(adjuntos: list[Adjunto]) -> str:
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


def _con_fuentes(texto: str, fuentes: list[tuple[str, str]]) -> str:
    if not fuentes:
        return texto
    lista = "\n".join(f"- [{titulo}]({url})" for url, titulo in fuentes[:25])
    return f"{texto}\n\n---\n**Fuentes citadas por la IA**\n\n{lista}"


def describir_error(error: Exception) -> str:
    """Mensaje claro en español para los errores más comunes de la API."""
    if isinstance(error, (ErrorIA, Cancelado)):
        return str(error) or "Operación cancelada."
    if isinstance(error, anthropic.AuthenticationError):
        return "La clave de API no es válida. Revísela en la pestaña «Configuración»."
    if isinstance(error, anthropic.PermissionDeniedError):
        return "La clave de API no tiene permiso para usar este modelo o función."
    if isinstance(error, anthropic.NotFoundError):
        return "El modelo seleccionado no está disponible para su cuenta. Elija otro en «Configuración»."
    if isinstance(error, anthropic.RateLimitError):
        return "Se alcanzó el límite de uso de la API. Espere un momento e intente de nuevo."
    if isinstance(error, anthropic.BadRequestError):
        mensaje = error.message or ""
        if "credit balance" in mensaje.lower():
            return "La cuenta de la API no tiene saldo suficiente. Cargue crédito en console.anthropic.com."
        return f"La solicitud no fue aceptada por la API: {mensaje}"
    if isinstance(error, anthropic.APIStatusError):
        if error.status_code >= 500:
            return "El servicio de IA no está disponible en este momento. Intente de nuevo en unos minutos."
        return f"Error de la API ({error.status_code}): {error.message}"
    if isinstance(error, anthropic.APITimeoutError):
        return "La IA tardó demasiado en responder. Intente de nuevo."
    if isinstance(error, anthropic.APIConnectionError):
        return "No hay conexión con el servicio de IA. Revise su conexión a internet."
    return f"Error inesperado: {error}"
