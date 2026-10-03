"""Mensajes claros en español para los errores de cada proveedor de IA."""

from __future__ import annotations

from posteos.ia.base import Cancelado, ErrorIA


def describir_error(error: Exception) -> str:
    if isinstance(error, Cancelado):
        return "Operación cancelada."
    if isinstance(error, ErrorIA):
        return str(error)
    for traductor in (_anthropic, _gemini, _ollama):
        mensaje = traductor(error)
        if mensaje:
            return mensaje
    if isinstance(error, (ConnectionError, TimeoutError)):
        return "No hay conexión con el servicio de IA. Revise su conexión a internet."
    return f"Error inesperado: {error}"


def _anthropic(error: Exception) -> str | None:
    try:
        import anthropic
    except ImportError:
        return None
    if not isinstance(error, anthropic.APIError):
        return None
    if isinstance(error, anthropic.AuthenticationError):
        return "La clave de API de Anthropic no es válida. Revísela en la pestaña «Configuración»."
    if isinstance(error, anthropic.PermissionDeniedError):
        return "La clave de API de Anthropic no tiene permiso para usar este modelo o función."
    if isinstance(error, anthropic.NotFoundError):
        return "El modelo de Claude seleccionado no está disponible para su cuenta. Elija otro en «Configuración»."
    if isinstance(error, anthropic.RateLimitError):
        return "Se alcanzó el límite de uso de la API de Anthropic. Espere un momento e intente de nuevo."
    if isinstance(error, anthropic.BadRequestError):
        mensaje = error.message or ""
        if "credit balance" in mensaje.lower():
            return "La cuenta de Anthropic no tiene saldo. Cargue crédito en console.anthropic.com o use Gemini (gratis)."
        return f"La solicitud no fue aceptada por la API de Anthropic: {mensaje}"
    if isinstance(error, anthropic.APIStatusError):
        if error.status_code >= 500:
            return "El servicio de Claude no está disponible en este momento. Intente de nuevo en unos minutos."
        return f"Error de la API de Anthropic ({error.status_code}): {error.message}"
    if isinstance(error, anthropic.APITimeoutError):
        return "Claude tardó demasiado en responder. Intente de nuevo."
    if isinstance(error, anthropic.APIConnectionError):
        return "No hay conexión con Claude. Revise su conexión a internet."
    return None


def _gemini(error: Exception) -> str | None:
    try:
        from google.genai import errors
    except ImportError:
        return None
    if not isinstance(error, errors.APIError):
        return None
    mensaje = error.message or ""
    minusculas = mensaje.lower()
    if "api key" in minusculas or "api_key" in minusculas or error.code == 401:
        return "La clave de API de Gemini no es válida. Revísela en la pestaña «Configuración»."
    if error.code == 403:
        return "La clave de API de Gemini no tiene permiso para este modelo. Pruebe con otro modelo Flash."
    if error.code == 404:
        return "El modelo de Gemini seleccionado no existe o no está disponible. Use «Actualizar lista» en «Configuración»."
    if error.code == 429:
        return (
            "Se alcanzó el límite gratuito de Gemini (por minuto o por día). Espere un minuto e intente de nuevo; "
            "si sigue ocurriendo, pruebe mañana o elija el modelo Flash-Lite, que tiene más cuota gratuita."
        )
    if error.code and error.code >= 500:
        return "El servicio de Gemini no está disponible en este momento. Intente de nuevo en unos minutos."
    return f"Error de Gemini ({error.code}): {mensaje}"


def _ollama(error: Exception) -> str | None:
    try:
        import ollama
    except ImportError:
        return None
    if isinstance(error, ollama.ResponseError):
        if error.status_code == 404:
            return f"El modelo no está instalado en Ollama. Instálelo desde una terminal con: ollama pull <modelo>\n\n({error.error})"
        return f"Error de Ollama: {error.error}"
    if isinstance(error, ConnectionError) and "ollama" in str(error).lower():
        return "No se pudo conectar con Ollama. Verifique que Ollama esté instalado y abierto (ollama.com/download)."
    return None
