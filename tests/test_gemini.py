"""Pruebas del proveedor Gemini contra el SDK real con respuestas HTTP simuladas."""

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from google import genai
from google.genai import types
from PIL import Image

from posteos.ia import ErrorIA, SolicitudPost, describir_error
from posteos.ia.gemini import ProveedorGemini
from posteos.media import Adjunto
from tests.test_claude import RESULTADO_JSON


def sse(*fragmentos: dict) -> bytes:
    return "".join(f"data: {json.dumps(f)}\r\n\r\n" for f in fragmentos).encode()


def fragmento(texto="", fin=None, consultas=(), fuentes=(), modelo="gemini-3-flash"):
    candidato: dict = {"content": {"role": "model", "parts": [{"text": texto}] if texto else []}, "index": 0}
    if fin:
        candidato["finishReason"] = fin
    if consultas or fuentes:
        candidato["groundingMetadata"] = {
            "webSearchQueries": list(consultas),
            "groundingChunks": [{"web": {"uri": u, "title": t}} for u, t in fuentes],
        }
    return {"candidates": [candidato], "modelVersion": modelo}


class Servidor:
    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.peticiones: list[httpx.Request] = []

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        self.peticiones.append(peticion)
        respuesta = self.respuestas.pop(0)
        if isinstance(respuesta, httpx.Response):
            return respuesta
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=respuesta)

    def cuerpo(self, i: int) -> dict:
        return json.loads(self.peticiones[i].content)


def proveedor(servidor: Servidor, **kwargs) -> ProveedorGemini:
    cliente = genai.Client(
        api_key="clave-prueba",
        http_options=types.HttpOptions(httpx_client=httpx.Client(transport=httpx.MockTransport(servidor))),
    )
    return ProveedorGemini("clave-prueba", modelo="gemini-flash-latest", cliente=cliente, **kwargs)


def solicitud(**cambios) -> SolicitudPost:
    datos = dict(
        idea="Abrimos sucursal nueva", redes=["linkedin"], objetivo="Vender", tono="Cercano", publico="General",
        variante="Español neutro (Latinoamérica)", longitud="Corta", emojis="Pocos", hashtags="Pocos (1 a 3)",
        llamada_a_la_accion="Comentar", pais="Argentina", investigar_web=False,
    )
    datos.update(cambios)
    return SolicitudPost(**datos)


def test_generar_posts_con_esquema_json():
    json_texto = json.dumps(RESULTADO_JSON)
    mitad = len(json_texto) // 2
    servidor = Servidor(sse(fragmento(json_texto[:mitad]), fragmento(json_texto[mitad:], fin="STOP")))

    resultado = proveedor(servidor).generar_posts(solicitud())

    assert resultado.posts.posts[0].texto == "Hola LinkedIn"
    assert resultado.modelo == "gemini-3-flash"
    peticion = servidor.peticiones[0]
    assert "gemini-flash-latest:streamGenerateContent" in str(peticion.url)
    cuerpo = servidor.cuerpo(0)
    assert cuerpo["generationConfig"]["responseMimeType"] == "application/json"
    assert "responseSchema" in cuerpo["generationConfig"] or "responseJsonSchema" in cuerpo["generationConfig"]
    assert "tools" not in cuerpo
    assert "Abrimos sucursal nueva" in cuerpo["contents"][0]["parts"][0]["text"]


def test_investigacion_con_busqueda_en_google():
    progreso = []
    investigacion = sse(
        fragmento("Martes a jueves de 9 a 11 h.", consultas=["mejor horario linkedin argentina"],
                  fuentes=[("https://ejemplo.com/horarios", "ejemplo.com")], fin="STOP"),
    )
    generacion = sse(fragmento(json.dumps(RESULTADO_JSON), fin="STOP"))
    servidor = Servidor(investigacion, generacion)

    resultado = proveedor(servidor, progreso=progreso.append).generar_posts(solicitud(investigar_web=True))

    assert "google_search" in json.dumps(servidor.cuerpo(0)["tools"]) or "googleSearch" in json.dumps(servidor.cuerpo(0)["tools"])
    assert "Martes a jueves" in resultado.investigacion
    assert "https://ejemplo.com/horarios" in resultado.investigacion
    assert any("mejor horario linkedin argentina" in m for m in progreso)


def test_analisis_usa_lectura_de_enlaces_y_transmite_texto(tmp_path: Path):
    ruta = tmp_path / "captura.png"
    Image.new("RGB", (400, 800), (10, 20, 30)).save(ruta)
    captura = Adjunto(ruta=ruta, tipo="imagen", descripcion="Imagen 400×800", imagenes=[Image.open(ruta)])
    fragmentos = []
    servidor = Servidor(sse(fragmento("## Resumen"), fragmento(" de la cuenta", fin="STOP")))

    informe = proveedor(servidor, texto_parcial=fragmentos.append).analizar_cuenta(
        "https://instagram.com/cuenta", "instagram", "Título: Cuenta", capturas=[captura]
    )

    assert informe == "## Resumen de la cuenta"
    assert "".join(fragmentos) == informe
    herramientas = json.dumps(servidor.cuerpo(0)["tools"])
    assert ("urlContext" in herramientas or "url_context" in herramientas)
    partes = servidor.cuerpo(0)["contents"][0]["parts"]
    assert any("inlineData" in p or "inline_data" in p for p in partes)


def test_bloqueo_por_seguridad():
    servidor = Servidor(sse(fragmento("", fin="SAFETY")))
    with pytest.raises(ErrorIA, match="seguridad"):
        proveedor(servidor).analizar_cuenta("https://x.com/a", "x", "")


def test_limite_gratuito_tiene_mensaje_claro():
    error = {"error": {"code": 429, "message": "Resource exhausted", "status": "RESOURCE_EXHAUSTED"}}
    servidor = Servidor(httpx.Response(429, json=error))
    with pytest.raises(Exception) as info:
        proveedor(servidor).analizar_cuenta("https://x.com/a", "x", "")
    assert "límite gratuito" in describir_error(info.value)


def test_clave_invalida_no_continua_tras_investigacion():
    error = {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key.", "status": "INVALID_ARGUMENT"}}
    servidor = Servidor(httpx.Response(400, json=error))
    p = proveedor(servidor)
    with pytest.raises(Exception) as info:
        p.generar_posts(solicitud(investigar_web=True))
    assert p.es_error_de_credenciales(info.value)
    assert "clave de API de Gemini" in describir_error(info.value)
    assert len(servidor.peticiones) == 1


def test_video_se_sube_y_si_falla_usa_fotogramas(tmp_path: Path):
    ruta = tmp_path / "clip.mp4"
    ruta.write_bytes(b"0")
    cuadros = [Image.new("RGB", (90, 160), (i * 40, 0, 0)) for i in range(3)]
    video = Adjunto(ruta=ruta, tipo="video", descripcion="Video 9:16", imagenes=cuadros, duracion=10)

    class ArchivosFalsos:
        def __init__(self, falla: bool):
            self.falla, self.borrados = falla, []

        def upload(self, file, config):
            if self.falla:
                raise OSError("sin conexión")
            return types.File(name="files/abc", uri="https://gen.ai/files/abc", mime_type="video/mp4", state="ACTIVE")

        def delete(self, name):
            self.borrados.append(name)

    for falla in (False, True):
        servidor = Servidor(sse(fragmento(json.dumps(RESULTADO_JSON), fin="STOP")))
        p = proveedor(servidor)
        archivos = ArchivosFalsos(falla)
        p.cliente = SimpleNamespace(models=p.cliente.models, files=archivos)
        p.generar_posts(solicitud(adjuntos=[video]))
        partes = servidor.cuerpo(0)["contents"][0]["parts"]
        con_archivo = any("fileData" in x or "file_data" in x for x in partes)
        imagenes = sum(1 for x in partes if "inlineData" in x or "inline_data" in x)
        if falla:
            assert not con_archivo and imagenes == 3
        else:
            assert con_archivo and imagenes == 0
            assert archivos.borrados == ["files/abc"]
