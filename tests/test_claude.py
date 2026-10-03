"""Pruebas de la capa de IA contra el SDK real con respuestas HTTP simuladas (sin gastar créditos)."""

import json

import anthropic
import httpx2
import pytest

from posteos.config import PerfilAnalizado
from posteos.ia import ErrorIA, SolicitudPost, construir_pedido, describir_error
from posteos.ia.claude import BETA_FALLBACK
from posteos.ia.claude import ProveedorClaude as MotorIA


def sse(*eventos: dict) -> bytes:
    return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in eventos).encode()


def inicio(modelo="claude-opus-5-5"):
    return {
        "type": "message_start",
        "message": {
            "id": "msg_1", "type": "message", "role": "assistant", "model": modelo, "content": [],
            "stop_reason": None, "stop_sequence": None, "usage": {"input_tokens": 10, "output_tokens": 1},
        },
    }


def fin(motivo="end_turn"):
    return [
        {"type": "message_delta", "delta": {"stop_reason": motivo, "stop_sequence": None}, "usage": {"output_tokens": 5}},
        {"type": "message_stop"},
    ]


def bloque_texto(indice, texto, citas=()):
    eventos = [{"type": "content_block_start", "index": indice, "content_block": {"type": "text", "text": ""}}]
    for cita in citas:
        eventos.append({"type": "content_block_delta", "index": indice, "delta": {"type": "citations_delta", "citation": cita}})
    eventos.append({"type": "content_block_delta", "index": indice, "delta": {"type": "text_delta", "text": texto}})
    eventos.append({"type": "content_block_stop", "index": indice})
    return eventos


def busqueda(indice, consulta):
    return [
        {"type": "content_block_start", "index": indice,
         "content_block": {"type": "server_tool_use", "id": f"srvtoolu_{indice}", "name": "web_search", "input": {}}},
        {"type": "content_block_delta", "index": indice,
         "delta": {"type": "input_json_delta", "partial_json": json.dumps({"query": consulta})}},
        {"type": "content_block_stop", "index": indice},
        {"type": "content_block_start", "index": indice + 1,
         "content_block": {"type": "web_search_tool_result", "tool_use_id": f"srvtoolu_{indice}", "content": [
             {"type": "web_search_result", "url": "https://ejemplo.com/horarios", "title": "Mejores horarios",
              "encrypted_content": "abc", "page_age": None}]}},
        {"type": "content_block_stop", "index": indice + 1},
    ]


CITA = {"type": "web_search_result_location", "url": "https://ejemplo.com/horarios", "title": "Mejores horarios",
        "encrypted_index": "x", "cited_text": "Martes 9 h"}

RESULTADO_JSON = {
    "resumen_estrategia": "Publicar el jueves al mediodía.",
    "analisis_del_material": "",
    "posts": [{
        "red": "linkedin", "formato_recomendado": "Carrusel", "gancho": "¿Sabías?", "texto": "Hola LinkedIn",
        "hashtags": ["marketing"], "llamada_a_la_accion": "Comentá", "mejor_dia": "Martes",
        "mejor_horario": "9:00", "justificacion_horario": "Estudio X", "como_usar_el_material": "",
        "texto_alternativo_imagen": "", "variante_ab": "Alt", "consejos": ["Responder"],
    }],
    "ideas_audiovisuales": [{"tipo": "Reel", "titulo": "T", "descripcion": "D", "redes": ["Instagram"],
                             "estructura": ["a", "b"], "duracion_sugerida": "20 s"}],
    "calendario": [{"red": "LinkedIn", "dia": "Martes", "horario": "9:00", "accion": "Publicar"}],
    "advertencias": [],
}


class Servidor:
    """Devuelve una respuesta SSE distinta por cada llamada y guarda las peticiones."""

    def __init__(self, *respuestas: bytes):
        self.respuestas = list(respuestas)
        self.peticiones: list[httpx2.Request] = []

    def __call__(self, peticion: httpx2.Request) -> httpx2.Response:
        self.peticiones.append(peticion)
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, content=self.respuestas.pop(0))

    def cuerpo(self, i: int) -> dict:
        return json.loads(self.peticiones[i].content)


def motor(servidor: Servidor, **kwargs) -> MotorIA:
    cliente = anthropic.Anthropic(
        api_key="sk-prueba", max_retries=0,
        http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(servidor)),
    )
    return MotorIA("sk-prueba", cliente=cliente, **kwargs)


def solicitud(**cambios) -> SolicitudPost:
    datos = dict(
        idea="Abrimos sucursal nueva", redes=["linkedin"], objetivo="Vender", tono="Cercano",
        publico="General", variante="Español de Argentina (voseo)", longitud="Corta", emojis="Pocos",
        hashtags="Pocos (1 a 3)", llamada_a_la_accion="Comentar", pais="Argentina", investigar_web=False,
    )
    datos.update(cambios)
    return SolicitudPost(**datos)


def test_generar_posts_envia_parametros_y_parsea_resultado():
    servidor = Servidor(sse(inicio(), *bloque_texto(0, json.dumps(RESULTADO_JSON)), *fin()))
    resultado = motor(servidor, esfuerzo="high").generar_posts(solicitud())

    assert resultado.posts.posts[0].red == "linkedin"
    assert resultado.posts.posts[0].texto == "Hola LinkedIn"
    assert resultado.modelo == "claude-opus-5-5"

    cuerpo = servidor.cuerpo(0)
    assert cuerpo["model"] == "claude-opus-5-5"
    assert cuerpo["fallbacks"] == "default"
    assert cuerpo["thinking"] == {"type": "adaptive"}
    assert cuerpo["output_config"]["effort"] == "high"
    assert cuerpo["output_config"]["format"]["type"] == "json_schema"
    assert cuerpo["stream"] is True
    assert "tools" not in cuerpo
    assert BETA_FALLBACK in servidor.peticiones[0].headers["anthropic-beta"]


def test_generar_con_investigacion_hace_busqueda_y_la_incluye():
    progreso = []
    investigacion = sse(inicio(), *busqueda(0, "mejor hora linkedin argentina"),
                        *bloque_texto(2, "Martes a jueves de 8 a 10 h.", citas=[CITA]), *fin())
    generacion = sse(inicio(), *bloque_texto(0, json.dumps(RESULTADO_JSON)), *fin())
    servidor = Servidor(investigacion, generacion)

    resultado = motor(servidor, progreso=progreso.append).generar_posts(solicitud(investigar_web=True))

    assert servidor.cuerpo(0)["tools"][0]["type"] == "web_search_20260209"
    assert "Martes a jueves" in resultado.investigacion
    assert "https://ejemplo.com/horarios" in resultado.investigacion  # fuentes citadas
    assert any("mejor hora linkedin argentina" in m for m in progreso)
    texto_pedido = servidor.cuerpo(1)["messages"][0]["content"][0]["text"]
    assert "Martes a jueves de 8 a 10 h." in texto_pedido


def test_pausa_de_herramienta_se_reanuda():
    pausa = sse(inicio(), *busqueda(0, "consulta"), *fin("pause_turn"))
    continuacion = sse(inicio(), *bloque_texto(0, "Informe final"), *fin())
    servidor = Servidor(pausa, continuacion)

    texto = motor(servidor).analizar_cuenta("https://instagram.com/cuenta", "instagram", "sin datos")

    assert texto == "Informe final"
    mensajes = servidor.cuerpo(1)["messages"]
    assert [m["role"] for m in mensajes] == ["user", "assistant"]
    assert mensajes[1]["content"][0]["type"] == "server_tool_use"


def test_analisis_transmite_texto_parcial_y_usa_lectura_web():
    fragmentos = []
    servidor = Servidor(sse(inicio(), *bloque_texto(0, "## Resumen"), *fin()))
    motor(servidor, texto_parcial=fragmentos.append).analizar_cuenta("https://x.com/cuenta", "x", "Título: Cuenta")
    tipos = [h["type"] for h in servidor.cuerpo(0)["tools"]]
    assert tipos == ["web_fetch_20260209", "web_search_20260209"]
    assert "".join(fragmentos) == "## Resumen"


def test_rechazo_se_informa_como_error():
    servidor = Servidor(sse(inicio(), *bloque_texto(0, ""), *fin("refusal")))
    with pytest.raises(ErrorIA, match="rechazó"):
        motor(servidor).analizar_cuenta("https://x.com/a", "x", "")


def test_validaciones_previas():
    with pytest.raises(ErrorIA):
        motor(Servidor()).generar_posts(solicitud(idea="  "))
    with pytest.raises(ErrorIA):
        motor(Servidor()).generar_posts(solicitud(redes=[]))
    with pytest.raises(ErrorIA, match="clave de API"):
        MotorIA("")


def test_pedido_incluye_perfil_buenas_practicas_y_zona_horaria():
    perfil = PerfilAnalizado(nombre="@cuenta · Instagram", url="https://instagram.com/cuenta", red="instagram",
                             analisis="Usa frases cortas y muchos emojis.")
    texto = construir_pedido(solicitud(perfil=perfil, redes=["instagram", "x"]), "")
    assert "Usa frases cortas y muchos emojis." in texto
    assert "America/Argentina/Buenos_Aires" in texto
    assert "Límite de caracteres: 280" in texto
    assert "Español de Argentina (voseo)" in texto


def test_describir_error_autenticacion():
    peticion = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    error = anthropic.AuthenticationError("x", response=httpx2.Response(401, request=peticion), body=None)
    assert "clave de API" in describir_error(error)


def test_cancelacion_previa_detiene_la_tarea():
    from posteos.ia import Cancelado

    m = motor(Servidor())
    m.cancelar()
    with pytest.raises(Cancelado):
        m.analizar_cuenta("https://x.com/a", "x", "")
