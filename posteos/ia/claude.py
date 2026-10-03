"""Proveedor Claude (API de Anthropic, de pago): máxima calidad, búsqueda y lectura web integradas."""

from __future__ import annotations

import base64

import anthropic
from pydantic import BaseModel

from posteos import prompts
from posteos.ia.base import (
    Cancelado,
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

BETA_FALLBACK = "server-side-fallback-2026-07-01"
MAX_TOKENS = 64000
MAX_CONTINUACIONES = 5
BUSQUEDA_WEB = {"type": "web_search_20260209", "name": "web_search", "max_uses": 8}
LECTURA_WEB = {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 6}


def bloques_de_adjuntos(adjuntos: list[Adjunto]) -> list[dict]:
    """Bloques de contenido de Claude: descripción de cada adjunto seguida de sus imágenes o fotogramas."""
    bloques: list[dict] = []
    for numero, (adjunto, imagenes) in enumerate(repartir_imagenes(adjuntos), start=1):
        texto = describir_adjunto(numero, adjunto)
        if adjunto.tipo == "video":
            texto += f" Se adjuntan {len(imagenes)} fotogramas representativos en orden cronológico."
        bloques.append({"type": "text", "text": texto})
        for imagen in imagenes:
            datos = base64.standard_b64encode(imagen_a_jpeg(imagen)).decode("ascii")
            bloques.append({"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": datos}})
    return bloques


class ProveedorClaude(Proveedor):
    nombre = "Claude"

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
            raise ErrorIA("Falta la clave de API de Anthropic. Cárguela en la pestaña «Configuración».")
        super().__init__(modelo, progreso, texto_parcial)
        self.cliente = cliente or anthropic.Anthropic(api_key=api_key, max_retries=3, timeout=900.0)
        self.esfuerzo = esfuerzo

    def es_error_de_credenciales(self, error: Exception) -> bool:
        return isinstance(error, (anthropic.AuthenticationError, anthropic.PermissionDeniedError))

    # --- Operaciones ----------------------------------------------------------

    def _analizar(self, pedido: PedidoAnalisis) -> str:
        contenido = [{"type": "text", "text": pedido.texto}] + bloques_de_adjuntos(pedido.capturas)
        texto, fuentes, _, _ = self._ejecutar(
            system=prompts.SISTEMA_ANALISIS,
            contenido=contenido,
            herramientas=[LECTURA_WEB, BUSQUEDA_WEB],
            transmitir_texto=True,
        )
        return con_fuentes(texto, fuentes)

    def _investigar(self, solicitud: SolicitudPost, texto: str) -> str:
        respuesta, fuentes, _, _ = self._ejecutar(
            system=prompts.SISTEMA_INVESTIGACION,
            contenido=[{"type": "text", "text": texto}],
            herramientas=[BUSQUEDA_WEB],
        )
        return con_fuentes(respuesta, fuentes)

    def _generar(self, solicitud: SolicitudPost, pedido: str) -> tuple[ResultadoPosts, str]:
        contenido = [{"type": "text", "text": pedido}] + bloques_de_adjuntos(solicitud.adjuntos)
        texto, _, parseado, modelo = self._ejecutar(
            system=prompts.SISTEMA_GENERACION,
            contenido=contenido,
            output_format=ResultadoPosts,
        )
        posts = parseado if isinstance(parseado, ResultadoPosts) else validar_resultado(texto)
        return posts, modelo

    # --- Llamada a la API -----------------------------------------------------

    def _ejecutar(
        self,
        *,
        system: str,
        contenido: list[dict],
        herramientas: list[dict] | None = None,
        output_format: type[BaseModel] | None = None,
        transmitir_texto: bool = False,
    ) -> tuple[str, list[tuple[str, str]], object | None, str]:
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
            self._verificar_cancelacion()
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
                        if url:
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
        return "".join(textos).strip(), fuentes, getattr(final, "parsed_output", None), final.model

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


def probar_conexion(api_key: str, modelo: str) -> str:
    info = anthropic.Anthropic(api_key=api_key, max_retries=1, timeout=30.0).models.retrieve(modelo)
    return info.display_name or modelo
