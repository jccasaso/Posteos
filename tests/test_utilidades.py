"""Pruebas de detección de redes, adjuntos, exportación y configuración."""

import pytest
from PIL import Image

from posteos import config, exportar
from posteos.ia import PostRed
from posteos.media import ErrorAdjunto, bloques_de_adjuntos, cargar_adjunto
from posteos.opciones import REDES
from posteos.social import ErrorEnlace, MetadatosPagina, _LectorHTML, detectar_red, nombre_sugerido, normalizar_url


@pytest.mark.parametrize(
    "url, red",
    [
        ("https://www.instagram.com/usuario/", "instagram"),
        ("linkedin.com/in/persona", "linkedin"),
        ("https://es.linkedin.com/company/empresa", "linkedin"),
        ("https://twitter.com/cuenta", "x"),
        ("https://x.com/cuenta/status/1", "x"),
        ("https://m.facebook.com/pagina", "facebook"),
        ("https://www.tiktok.com/@creador", "tiktok"),
        ("https://youtu.be/abc", "youtube"),
        ("https://www.threads.net/@cuenta", "threads"),
        ("https://whatsapp.com/channel/123", "whatsapp"),
        ("https://ejemplo.com", None),
        ("https://falsoinstagram.com/x", None),
    ],
)
def test_detectar_red(url, red):
    assert detectar_red(url) == red


def test_normalizar_url():
    assert normalizar_url(" instagram.com/a ") == "https://instagram.com/a"
    with pytest.raises(ErrorEnlace):
        normalizar_url("")
    with pytest.raises(ErrorEnlace):
        normalizar_url("ftp://ejemplo.com")
    with pytest.raises(ErrorEnlace):
        normalizar_url("hola")


def test_nombre_sugerido():
    assert nombre_sugerido("https://www.instagram.com/cafe.aroma/") == "@cafe.aroma · Instagram"
    assert nombre_sugerido("https://www.linkedin.com/in/juan-perez") == "@juan-perez · LinkedIn"
    assert nombre_sugerido("https://www.tiktok.com/@creador") == "@creador · TikTok"


def test_lector_html_extrae_metadatos():
    lector = _LectorHTML()
    lector.feed(
        "<html><head><title>Café Aroma</title>"
        '<meta property="og:description" content="Café de especialidad">'
        '<meta name="viewport" content="x">'
        '<script type="application/ld+json">{"@type": "Organization", "name": "Café Aroma"}</script>'
        "</head></html>"
    )
    assert lector.titulo == "Café Aroma"
    assert lector.meta == {"og:description": "Café de especialidad"}
    assert "Organization" in lector.json_ld[0]
    texto = MetadatosPagina(url_final="u", estado=200, titulo="T", meta={"a": "b"}).como_texto()
    assert "Título: T" in texto


def test_cargar_imagen_y_bloques(tmp_path):
    ruta = tmp_path / "foto.png"
    Image.new("RGBA", (3000, 1500), (255, 0, 0, 128)).save(ruta)
    adjunto = cargar_adjunto(ruta)
    assert adjunto.tipo == "imagen"
    assert max(adjunto.imagenes[0].size) <= 1568
    assert "3000×1500" in adjunto.descripcion
    bloques = bloques_de_adjuntos([adjunto])
    assert bloques[0]["type"] == "text"
    assert bloques[1]["source"]["media_type"] == "image/jpeg"


def test_cargar_video(tmp_path):
    cv2 = pytest.importorskip("cv2")
    import numpy as np

    ruta = tmp_path / "clip.mp4"
    escritor = cv2.VideoWriter(str(ruta), cv2.VideoWriter_fourcc(*"mp4v"), 10, (180, 320))
    for i in range(50):
        escritor.write(np.full((320, 180, 3), i * 4, np.uint8))
    escritor.release()
    adjunto = cargar_adjunto(ruta)
    assert adjunto.tipo == "video"
    assert 1 <= len(adjunto.imagenes) <= 6
    assert "9:16" in adjunto.descripcion


def test_adjunto_no_admitido(tmp_path):
    ruta = tmp_path / "doc.txt"
    ruta.write_text("hola")
    with pytest.raises(ErrorAdjunto):
        cargar_adjunto(ruta)


def _post(**cambios):
    datos = dict(
        red="x", formato_recomendado="Hilo", gancho="G", texto="Uno\n---\nDos más largo", hashtags=["ia", "#Marketing"],
        llamada_a_la_accion="C", mejor_dia="Lunes", mejor_horario="9:00", justificacion_horario="J",
        como_usar_el_material="", texto_alternativo_imagen="", variante_ab="", consejos=[],
    )
    datos.update(cambios)
    return PostRed(**datos)


def test_exportar_texto_y_hilo():
    post = _post()
    assert exportar.texto_publicable(post).endswith("#ia #Marketing")
    assert exportar.longitud_maxima_segmento("Uno\n---\nDos más largo") == len("Dos más largo")
    detalle = exportar.detalle_post_md(post)
    assert "Lunes, 9:00" in detalle


def test_enlaces_de_publicacion():
    assert REDES["x"].enlace_publicacion("Hola mundo #ia") == "https://x.com/intent/post?text=Hola%20mundo%20%23ia"
    assert REDES["instagram"].enlace_publicacion("texto") == "https://www.instagram.com/"


def test_configuracion_perfiles_e_historial(tmp_path, monkeypatch):
    monkeypatch.setenv("POSTEOS_DATOS", str(tmp_path))
    c = config.Configuracion.cargar()
    c.pais = "México"
    c.guardar()
    assert config.Configuracion.cargar().pais == "México"

    perfil = config.PerfilAnalizado(nombre="n", url="u", red="x", analisis="a")
    config.guardar_perfiles([perfil])
    assert config.cargar_perfiles()[0].id == perfil.id

    config.agregar_al_historial({"idea": "i", "redes": ["x"], "markdown": "m"})
    assert config.cargar_historial()[0]["idea"] == "i"
    config.borrar_historial()
    assert config.cargar_historial() == []
