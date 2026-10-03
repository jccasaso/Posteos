"""Proveedor Google Gemini (plan gratuito con límites): búsqueda en Google, lectura de enlaces y video nativo."""

from __future__ import annotations

import mimetypes
import time

from google import genai
from google.genai import errors as errores_genai
from google.genai import types

from posteos import prompts
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

TIEMPO_MAXIMO_MS = 600_000
ESPERA_VIDEO_S = 300
# Tipos de video que Gemini acepta; los demás se envían como fotogramas.
VIDEOS_ADMITIDOS = {
    "video/mp4", "video/mpeg", "video/quicktime", "video/x-msvideo", "video/avi",
    "video/webm", "video/x-ms-wmv", "video/wmv", "video/3gpp", "video/mpg", "video/x-flv",
}
MOTIVOS_BLOQUEO = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION", "IMAGE_SAFETY"}


class ProveedorGemini(Proveedor):
    nombre = "Gemini"

    def __init__(
        self,
        api_key: str,
        modelo: str = "gemini-flash-latest",
        progreso: Progreso | None = None,
        texto_parcial: Progreso | None = None,
        cliente: genai.Client | None = None,
    ) -> None:
        if not api_key and cliente is None:
            raise ErrorIA("Falta la clave de API de Google Gemini. Cárguela en la pestaña «Configuración».")
        super().__init__(modelo, progreso, texto_parcial)
        self.cliente = cliente or genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=TIEMPO_MAXIMO_MS))
        self._subidos: list[str] = []

    def es_error_de_credenciales(self, error: Exception) -> bool:
        return es_error_de_clave(error)

    # --- Operaciones ----------------------------------------------------------

    def _analizar(self, pedido: PedidoAnalisis) -> str:
        try:
            contenidos = [types.Part.from_text(text=pedido.texto)] + self._partes_adjuntos(pedido.capturas)
            configuracion = types.GenerateContentConfig(
                system_instruction=prompts.SISTEMA_ANALISIS,
                tools=[types.Tool(url_context=types.UrlContext()), types.Tool(google_search=types.GoogleSearch())],
            )
            texto, fuentes, _ = self._transmitir(contenidos, configuracion, transmitir_texto=True)
        finally:
            self._borrar_subidos()
        return con_fuentes(texto, fuentes)

    def _investigar(self, solicitud: SolicitudPost, texto: str) -> str:
        configuracion = types.GenerateContentConfig(
            system_instruction=prompts.SISTEMA_INVESTIGACION,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        )
        respuesta, fuentes, _ = self._transmitir([types.Part.from_text(text=texto)], configuracion)
        return con_fuentes(respuesta, fuentes)

    def _generar(self, solicitud: SolicitudPost, pedido: str) -> tuple[ResultadoPosts, str]:
        try:
            contenidos = [types.Part.from_text(text=pedido)] + self._partes_adjuntos(solicitud.adjuntos)
            configuracion = types.GenerateContentConfig(
                system_instruction=prompts.SISTEMA_GENERACION,
                response_mime_type="application/json",
                response_schema=ResultadoPosts,
            )
            if sum(a.duracion for a in solicitud.adjuntos) > 180:
                # Videos largos: menor resolución para no agotar la cuota gratuita de tokens.
                configuracion.media_resolution = types.MediaResolution.MEDIA_RESOLUTION_LOW
            texto, _, modelo = self._transmitir(contenidos, configuracion)
        finally:
            self._borrar_subidos()
        return validar_resultado(texto), modelo

    # --- Adjuntos ---------------------------------------------------------------

    def _partes_adjuntos(self, adjuntos: list[Adjunto]) -> list[types.Part]:
        partes: list[types.Part] = []
        for numero, (adjunto, imagenes) in enumerate(repartir_imagenes(adjuntos), start=1):
            texto = describir_adjunto(numero, adjunto)
            if adjunto.tipo == "video":
                archivo = self._subir_video(adjunto)
                if archivo is not None:
                    partes.append(types.Part.from_text(text=texto + " Se adjunta el video completo."))
                    partes.append(types.Part.from_uri(file_uri=archivo.uri, mime_type=archivo.mime_type))
                    continue
                texto += f" Se adjuntan {len(imagenes)} fotogramas representativos en orden cronológico."
            partes.append(types.Part.from_text(text=texto))
            partes.extend(types.Part.from_bytes(data=imagen_a_jpeg(img), mime_type="image/jpeg") for img in imagenes)
        return partes

    def _subir_video(self, adjunto: Adjunto) -> types.File | None:
        tipo = mimetypes.guess_type(adjunto.ruta.name)[0] or ""
        if tipo not in VIDEOS_ADMITIDOS:
            return None
        self._progreso(f"Subiendo el video «{adjunto.nombre}» a Gemini…")
        try:
            archivo = self.cliente.files.upload(file=str(adjunto.ruta), config=types.UploadFileConfig(mime_type=tipo))
            self._subidos.append(archivo.name)
            limite = time.monotonic() + ESPERA_VIDEO_S
            while _estado(archivo) == "PROCESSING":
                self._verificar_cancelacion()
                if time.monotonic() > limite:
                    raise TimeoutError("el video tardó demasiado en procesarse")
                self._progreso(f"Gemini está procesando el video «{adjunto.nombre}»…")
                time.sleep(3)
                archivo = self.cliente.files.get(name=archivo.name)
            if _estado(archivo) != "ACTIVE":
                raise ErrorIA("Gemini no pudo procesar el video")
            return archivo
        except Exception as e:
            from posteos.ia.base import Cancelado
            from posteos.ia.errores import describir_error

            if isinstance(e, Cancelado) or es_error_de_clave(e):
                raise
            self._progreso(f"No se pudo subir el video ({describir_error(e)}). Se usarán fotogramas.")
            return None

    def _borrar_subidos(self) -> None:
        for nombre in self._subidos:
            try:
                self.cliente.files.delete(name=nombre)
            except Exception:
                pass  # Gemini los borra solo a las 48 h
        self._subidos.clear()

    # --- Llamada a la API -------------------------------------------------------

    def _transmitir(
        self, contenidos: list, configuracion: types.GenerateContentConfig, transmitir_texto: bool = False
    ) -> tuple[str, list[tuple[str, str]], str]:
        textos: list[str] = []
        fuentes: list[tuple[str, str]] = []
        informados: set[str] = set()
        modelo = self.modelo
        motivo_fin = ""

        flujo = self.cliente.models.generate_content_stream(model=self.modelo, contents=contenidos, config=configuracion)
        for fragmento in flujo:
            self._verificar_cancelacion()
            bloqueo = fragmento.prompt_feedback.block_reason if fragmento.prompt_feedback else None
            if bloqueo:
                raise ErrorIA("Gemini bloqueó la solicitud por sus filtros de seguridad. Reformule la idea.")
            modelo = fragmento.model_version or modelo
            if not fragmento.candidates:
                continue
            candidato = fragmento.candidates[0]
            for parte in (candidato.content.parts if candidato.content and candidato.content.parts else []):
                if parte.text and not parte.thought:
                    textos.append(parte.text)
                    if transmitir_texto and self._texto_parcial:
                        self._texto_parcial(parte.text)
            self._informar(candidato, informados, fuentes)
            if candidato.finish_reason:
                motivo_fin = getattr(candidato.finish_reason, "name", str(candidato.finish_reason))

        if motivo_fin in MOTIVOS_BLOQUEO:
            raise ErrorIA("Gemini bloqueó la respuesta por sus filtros de seguridad. Reformule la idea e intente de nuevo.")
        if motivo_fin == "MAX_TOKENS":
            raise ErrorIA("La respuesta fue demasiado larga y quedó incompleta. Pruebe con menos redes a la vez.")
        return "".join(textos).strip(), fuentes, modelo

    def _informar(self, candidato: types.Candidate, informados: set[str], fuentes: list[tuple[str, str]]) -> None:
        metadatos = candidato.grounding_metadata
        if metadatos:
            for consulta in metadatos.web_search_queries or []:
                if consulta not in informados:
                    informados.add(consulta)
                    self._progreso(f"Buscando en Google: «{consulta}»")
            for trozo in metadatos.grounding_chunks or []:
                if trozo.web and trozo.web.uri:
                    fuentes.append((trozo.web.uri, trozo.web.title or trozo.web.domain or trozo.web.uri))
        lecturas = candidato.url_context_metadata
        for dato in (lecturas.url_metadata or []) if lecturas else []:
            url = dato.retrieved_url or ""
            if url and url not in informados:
                informados.add(url)
                self._progreso(f"Leyendo la página: {url}")


def _estado(archivo: types.File) -> str:
    return getattr(archivo.state, "name", str(archivo.state or ""))


def es_error_de_clave(error: Exception) -> bool:
    if not isinstance(error, errores_genai.ClientError):
        return False
    mensaje = (error.message or "").lower()
    return error.code in (401, 403) or "api key" in mensaje or "api_key" in mensaje


def probar_conexion(api_key: str, modelo: str) -> str:
    cliente = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=30_000))
    info = cliente.models.get(model=modelo)
    return info.display_name or modelo


def listar_modelos(api_key: str) -> list[str]:
    """Modelos Gemini de texto disponibles para la clave (excluye imagen, audio, embeddings…)."""
    excluir = ("embedding", "image", "tts", "audio", "live", "robotics", "computer", "aqa", "veo", "imagen")
    cliente = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=30_000))
    nombres = []
    for modelo in cliente.models.list():
        nombre = (modelo.name or "").removeprefix("models/")
        acciones = modelo.supported_actions or []
        if nombre.startswith("gemini") and "generateContent" in acciones and not any(x in nombre for x in excluir):
            nombres.append(nombre)
    return sorted(set(nombres), reverse=True)
