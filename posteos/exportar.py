"""Conversión de resultados a texto y Markdown para mostrar, copiar y exportar."""

from __future__ import annotations

from posteos.ia import IdeaAudiovisual, PostRed, ResultadoGeneracion
from posteos.opciones import REDES


def texto_publicable(post: PostRed) -> str:
    """Texto final listo para pegar en la red: cuerpo + hashtags."""
    hashtags = " ".join(_hashtag(h) for h in post.hashtags if h.strip())
    return f"{post.texto.strip()}\n\n{hashtags}".strip() if hashtags else post.texto.strip()


def longitud_maxima_segmento(texto: str) -> int:
    """Longitud del segmento más largo (los hilos se separan con líneas «---»)."""
    segmentos = [s.strip() for s in texto.split("\n---\n")] if "\n---\n" in texto else [texto]
    return max((len(s) for s in segmentos), default=0)


def detalle_post_md(post: PostRed) -> str:
    partes = [
        f"**Gancho:** {post.gancho}",
        f"**Llamada a la acción:** {post.llamada_a_la_accion}",
        f"**Mejor momento:** {post.mejor_dia}, {post.mejor_horario}",
        f"**¿Por qué ese horario?** {post.justificacion_horario}",
    ]
    if post.como_usar_el_material.strip():
        partes.append(f"**Cómo usar el material:** {post.como_usar_el_material}")
    if post.texto_alternativo_imagen.strip():
        partes.append(f"**Texto alternativo (accesibilidad):** {post.texto_alternativo_imagen}")
    if post.variante_ab.strip():
        partes.append(f"**Variante para prueba A/B:**\n\n> {_citar(post.variante_ab)}")
    if post.consejos:
        partes.append("**Consejos para publicar:**\n" + "\n".join(f"- {c}" for c in post.consejos))
    return "\n\n".join(partes)


def idea_md(numero: int, idea: IdeaAudiovisual) -> str:
    pasos = "\n".join(f"{i}. {paso}" for i, paso in enumerate(idea.estructura, start=1))
    redes = ", ".join(idea.redes)
    return (
        f"### {numero}. {idea.titulo}\n\n"
        f"**Tipo:** {idea.tipo} · **Duración sugerida:** {idea.duracion_sugerida} · **Redes:** {redes}\n\n"
        f"{idea.descripcion}\n\n"
        f"**Estructura:**\n\n{pasos}"
    )


def ideas_md(resultado: ResultadoGeneracion) -> str:
    ideas = resultado.posts.ideas_audiovisuales
    if not ideas:
        return "No se generaron ideas audiovisuales."
    return "\n\n".join(idea_md(i, idea) for i, idea in enumerate(ideas, start=1))


def estrategia_md(resultado: ResultadoGeneracion) -> str:
    posts = resultado.posts
    partes = ["## Estrategia", posts.resumen_estrategia]
    if posts.analisis_del_material.strip():
        partes += ["## Análisis del material adjunto", posts.analisis_del_material]
    if posts.calendario:
        filas = ["| Red | Día | Horario | Acción |", "|---|---|---|---|"]
        for entrada in posts.calendario:
            filas.append(
                f"| {_celda(entrada.red)} | {_celda(entrada.dia)} | {_celda(entrada.horario)} | {_celda(entrada.accion)} |"
            )
        partes += ["## Calendario sugerido", "\n".join(filas)]
    if posts.advertencias:
        partes += ["## Antes de publicar", "\n".join(f"- {a}" for a in posts.advertencias)]
    if resultado.investigacion:
        partes += ["## Investigación web", resultado.investigacion]
    return "\n\n".join(partes)


def resultado_a_markdown(resultado: ResultadoGeneracion, idea: str = "") -> str:
    partes = ["# Publicaciones generadas con Posteos"]
    if idea.strip():
        partes.append(f"**Idea original:**\n\n> {_citar(idea.strip())}")
    for post in resultado.posts.posts:
        red = REDES.get(post.red)
        nombre = red.nombre if red else post.red
        partes.append(f"## {nombre} — {post.formato_recomendado}")
        partes.append("```text\n" + texto_publicable(post) + "\n```")
        partes.append(detalle_post_md(post))
    partes.append("# Ideas de contenido audiovisual complementario")
    partes.append(ideas_md(resultado))
    partes.append("# " + estrategia_md(resultado).removeprefix("## "))
    return "\n\n".join(partes) + "\n"


def _hashtag(texto: str) -> str:
    texto = texto.strip().replace(" ", "")
    return texto if texto.startswith("#") else f"#{texto}"


def _citar(texto: str) -> str:
    return texto.replace("\n", "\n> ")


def _celda(texto: str) -> str:
    return texto.replace("|", "/").replace("\n", " ")
