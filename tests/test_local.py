"""Pruebas del proveedor Ollama (IA local) y de la búsqueda web gratuita, sin red."""

import base64
import json

import httpx
import ollama
import pytest
from PIL import Image

from posteos import busqueda
from posteos.ia import ErrorIA, SolicitudPost, describir_error
from posteos.ia.local import ProveedorOllama, consultas_de_cuenta, consultas_de_horarios, imagenes_de_adjuntos
from posteos.media import Adjunto
from tests.test_claude import RESULTADO_JSON


def ndjson(texto: str, motivo: str = "stop", trozos: int = 3) -> bytes:
    tam = max(1, len(texto) // trozos)
    lineas = [
        {"model": "gemma3:12b", "created_at": "2026-10-03T00:00:00Z",
         "message": {"role": "assistant", "content": texto[i : i + tam]}, "done": False}
        for i in range(0, len(texto), tam)
    ]
    lineas.append({"model": "gemma3:12b", "created_at": "2026-10-03T00:00:01Z",
                   "message": {"role": "assistant", "content": ""}, "done": True, "done_reason": motivo})
    return "\n".join(json.dumps(linea) for linea in lineas).encode() + b"\n"


class Servidor:
    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.peticiones: list[httpx.Request] = []

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        self.peticiones.append(peticion)
        respuesta = self.respuestas.pop(0)
        if isinstance(respuesta, httpx.Response):
            return respuesta
        return httpx.Response(200, headers={"content-type": "application/x-ndjson"}, content=respuesta)

    def cuerpo(self, i: int) -> dict:
        return json.loads(self.peticiones[i].content)


def proveedor(servidor: Servidor, **kwargs) -> ProveedorOllama:
    cliente = ollama.Client(host="http://localhost:11434", transport=httpx.MockTransport(servidor))
    return ProveedorOllama(modelo="gemma3:12b", cliente=cliente, **kwargs)


def solicitud(**cambios) -> SolicitudPost:
    datos = dict(
        idea="Abrimos sucursal nueva", redes=["linkedin", "instagram"], objetivo="Vender", tono="Cercano",
        publico="General", variante="Español neutro (Latinoamérica)", longitud="Corta", emojis="Pocos",
        hashtags="Pocos (1 a 3)", llamada_a_la_accion="Comentar", pais="Argentina", investigar_web=False,
    )
    datos.update(cambios)
    return SolicitudPost(**datos)


@pytest.fixture
def web_falsa(monkeypatch):
    consultas = []

    def buscar(consulta, region="xl-es", cantidad=5):
        consultas.append((consulta, region))
        return [busqueda.ResultadoBusqueda("Estudio de horarios", f"https://ejemplo.com/{len(consultas)}", "Martes 9 h")]

    monkeypatch.setattr(busqueda, "buscar", buscar)
    monkeypatch.setattr(busqueda, "texto_de_pagina", lambda url, max_caracteres=3500: "Lo mejor es publicar martes y jueves.")
    return consultas


def test_generar_posts_con_formato_json(web_falsa):
    servidor = Servidor(ndjson(json.dumps(RESULTADO_JSON)))
    resultado = proveedor(servidor).generar_posts(solicitud())

    assert resultado.posts.posts[0].texto == "Hola LinkedIn"
    assert resultado.modelo == "gemma3:12b"
    cuerpo = servidor.cuerpo(0)
    assert cuerpo["model"] == "gemma3:12b"
    assert cuerpo["format"]["type"] == "object"
    assert cuerpo["options"]["num_ctx"] == 16384
    assert cuerpo["messages"][0]["role"] == "system"
    assert web_falsa == []  # sin investigación no se busca


def test_investigacion_con_duckduckgo(web_falsa):
    servidor = Servidor(ndjson("Publicar martes y jueves de 9 a 11 h."), ndjson(json.dumps(RESULTADO_JSON)))
    progreso = []
    resultado = proveedor(servidor, progreso=progreso.append).generar_posts(solicitud(investigar_web=True))

    assert "martes y jueves" in resultado.investigacion
    assert "https://ejemplo.com/1" in resultado.investigacion
    assert web_falsa[0] == (f"mejor horario para publicar en LinkedIn Argentina {__import__('datetime').date.today().year}", "ar-es")
    texto_investigacion = servidor.cuerpo(0)["messages"][1]["content"]
    assert "Lo mejor es publicar martes y jueves." in texto_investigacion
    assert any("Buscando en la web" in m for m in progreso)


def test_si_falla_la_busqueda_se_genera_igual(monkeypatch):
    def sin_red(*_a, **_k):
        raise OSError("sin conexión")

    monkeypatch.setattr(busqueda, "buscar", sin_red)
    progreso = []
    servidor = Servidor(ndjson(json.dumps(RESULTADO_JSON)))
    resultado = proveedor(servidor, progreso=progreso.append).generar_posts(solicitud(investigar_web=True))
    assert resultado.investigacion == ""
    assert any("Se continúa sin ella" in m for m in progreso)


def test_analisis_envia_capturas_y_transmite(tmp_path, web_falsa):
    ruta = tmp_path / "perfil.png"
    Image.new("RGB", (300, 600), (200, 10, 10)).save(ruta)
    captura = Adjunto(ruta=ruta, tipo="imagen", descripcion="Imagen 300×600", imagenes=[Image.open(ruta)])
    fragmentos = []
    servidor = Servidor(ndjson("## Resumen de la cuenta"))

    informe = proveedor(servidor, texto_parcial=fragmentos.append).analizar_cuenta(
        "https://www.instagram.com/cafe.aroma/", "instagram", "Título: Café", capturas=[captura]
    )

    assert informe.startswith("## Resumen de la cuenta")
    assert "".join(fragmentos) == "## Resumen de la cuenta"
    mensaje = servidor.cuerpo(0)["messages"][1]
    assert len(mensaje["images"]) == 1
    assert base64.b64decode(mensaje["images"][0])[:2] == b"\xff\xd8"  # JPEG
    assert "Lo mejor es publicar" in mensaje["content"]
    assert web_falsa[0][0] == "cafe.aroma Instagram"


def test_modelo_no_instalado_tiene_mensaje_claro():
    servidor = Servidor(httpx.Response(404, json={"error": "model 'gemma3:12b' not found"}))
    with pytest.raises(ollama.ResponseError) as info:
        proveedor(servidor).generar_posts(solicitud())
    assert "ollama pull" in describir_error(info.value)


def test_respuesta_cortada():
    servidor = Servidor(ndjson('{"resumen', motivo="length"))
    with pytest.raises(ErrorIA, match="incompleta"):
        proveedor(servidor).generar_posts(solicitud())


def test_auxiliares():
    assert consultas_de_cuenta("https://www.linkedin.com/in/juan-perez", "linkedin")[0] == "juan-perez LinkedIn"
    assert len(consultas_de_horarios(solicitud(redes=["x", "tiktok"]))) == 3
    texto, imagenes = imagenes_de_adjuntos([])
    assert texto == "" and imagenes == []
    assert busqueda.region_de("México") == "mx-es"
    assert busqueda.region_de("Uruguay") == "xl-es"
