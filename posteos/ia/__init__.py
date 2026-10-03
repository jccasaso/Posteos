"""Proveedores de IA (Gemini, Ollama y Claude) detrás de una interfaz común."""

from __future__ import annotations

from posteos.ia.base import (
    Cancelado,
    EntradaCalendario,
    ErrorIA,
    IdeaAudiovisual,
    PostRed,
    Progreso,
    Proveedor,
    ResultadoGeneracion,
    ResultadoPosts,
    SolicitudPost,
    construir_pedido,
)
from posteos.ia.errores import describir_error

__all__ = [
    "Cancelado", "EntradaCalendario", "ErrorIA", "IdeaAudiovisual", "PostRed", "Progreso", "Proveedor",
    "ResultadoGeneracion", "ResultadoPosts", "SolicitudPost", "construir_pedido", "crear_proveedor",
    "describir_error", "listar_modelos", "probar_conexion",
]


def crear_proveedor(config, progreso: Progreso | None = None, texto_parcial: Progreso | None = None) -> Proveedor:
    """Crea el proveedor elegido en la configuración (los SDK se importan solo cuando se usan)."""
    if config.proveedor == "claude":
        from posteos.ia.claude import ProveedorClaude

        return ProveedorClaude(
            config.obtener_api_key("claude"), config.modelo_claude, config.esfuerzo, progreso, texto_parcial
        )
    if config.proveedor == "ollama":
        from posteos.busqueda import region_de
        from posteos.ia.local import ProveedorOllama

        return ProveedorOllama(
            config.ollama_url, config.modelo_ollama, progreso, texto_parcial, region_busqueda=region_de(config.pais)
        )
    from posteos.ia.gemini import ProveedorGemini

    return ProveedorGemini(config.obtener_api_key("gemini"), config.modelo_gemini, progreso, texto_parcial)


def probar_conexion(proveedor: str, clave_o_url: str, modelo: str) -> str:
    if proveedor == "claude":
        from posteos.ia.claude import probar_conexion as probar
    elif proveedor == "ollama":
        from posteos.ia.local import probar_conexion as probar
    else:
        from posteos.ia.gemini import probar_conexion as probar
    return probar(clave_o_url, modelo)


def listar_modelos(proveedor: str, clave_o_url: str) -> list[str]:
    if proveedor == "ollama":
        from posteos.ia.local import listar_modelos as listar
    elif proveedor == "gemini":
        from posteos.ia.gemini import listar_modelos as listar
    else:
        return []
    return listar(clave_o_url)
