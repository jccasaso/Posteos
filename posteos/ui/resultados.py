"""Visualización de las publicaciones generadas, ideas audiovisuales y estrategia."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from posteos import exportar
from posteos.ia import PostRed, ResultadoGeneracion
from posteos.opciones import REDES


def navegador_markdown(texto: str = "") -> QTextBrowser:
    navegador = QTextBrowser()
    navegador.setOpenExternalLinks(True)
    navegador.setMarkdown(texto)
    return navegador


def _confirmar(boton: QPushButton) -> None:
    """Muestra «Copiado» en el botón durante dos segundos."""
    original = boton.property("textoOriginal") or boton.text()
    boton.setProperty("textoOriginal", original)
    boton.setText("✅ Copiado")
    QTimer.singleShot(2000, boton, lambda: boton.setText(original))


class PanelPost(QWidget):
    """Una publicación para una red: texto editable, contador, copiar/abrir y detalles."""

    def __init__(self, post: PostRed, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.post = post
        self.red = REDES.get(post.red)

        datos = QHBoxLayout()
        for texto in (f"📐 {post.formato_recomendado}", f"🕒 {post.mejor_dia} · {post.mejor_horario}"):
            etiqueta = QLabel(texto)
            etiqueta.setObjectName("etiquetaDato")
            datos.addWidget(etiqueta)
        datos.addStretch()

        self.editor = QPlainTextEdit(exportar.texto_publicable(post))
        self.editor.textChanged.connect(self._contar)
        self.contador = QLabel()

        self.boton_copiar = QPushButton("📋 Copiar texto")
        self.boton_copiar.clicked.connect(self.copiar)
        nombre = self.red.nombre if self.red else post.red
        self.boton_abrir = QPushButton(f"🚀 Abrir {nombre} para publicar")
        self.boton_abrir.clicked.connect(self.abrir_red)

        barra = QHBoxLayout()
        barra.addWidget(self.contador)
        barra.addStretch()
        barra.addWidget(self.boton_copiar)
        barra.addWidget(self.boton_abrir)

        superior = QWidget()
        diseno_sup = QVBoxLayout(superior)
        diseno_sup.setContentsMargins(0, 0, 0, 0)
        diseno_sup.addLayout(datos)
        diseno_sup.addWidget(self.editor)
        diseno_sup.addLayout(barra)

        divisor = QSplitter(Qt.Orientation.Vertical)
        divisor.addWidget(superior)
        divisor.addWidget(navegador_markdown(exportar.detalle_post_md(post)))
        divisor.setStretchFactor(0, 3)
        divisor.setStretchFactor(1, 2)

        diseno = QVBoxLayout(self)
        diseno.setContentsMargins(10, 10, 10, 10)
        diseno.addWidget(divisor)
        self._contar()

    def texto(self) -> str:
        return self.editor.toPlainText()

    def _contar(self) -> None:
        texto = self.texto()
        limite = self.red.limite_caracteres if self.red else 0
        if "\n---\n" in texto:
            largo = exportar.longitud_maxima_segmento(texto)
            descripcion = f"Hilo · post más largo: {largo} / {limite} caracteres"
        else:
            largo = len(texto)
            descripcion = f"{largo} / {limite} caracteres"
        excedido = bool(limite) and largo > limite
        self.contador.setText(descripcion + ("  ⚠ supera el límite" if excedido else ""))
        self.contador.setObjectName("contadorExcedido" if excedido else "contador")
        self.contador.style().unpolish(self.contador)
        self.contador.style().polish(self.contador)

    def copiar(self) -> None:
        QGuiApplication.clipboard().setText(self.texto())
        _confirmar(self.boton_copiar)

    def abrir_red(self) -> None:
        if not self.red:
            return
        texto = self.texto()
        QGuiApplication.clipboard().setText(texto)
        segmentos = [s.strip() for s in texto.split("\n---\n")]
        QDesktopServices.openUrl(QUrl(self.red.enlace_publicacion(segmentos[0])))
        if len(segmentos) > 1 and self.red.precarga_texto:
            QMessageBox.information(
                self,
                "Hilo copiado",
                f"El hilo tiene {len(segmentos)} publicaciones. Se abrió {self.red.nombre} con la primera; "
                "el hilo completo quedó copiado en el portapapeles para agregar las siguientes como respuestas.",
            )
        elif not self.red.precarga_texto:
            QMessageBox.information(
                self,
                "Texto copiado",
                f"El texto se copió al portapapeles. Péguelo (Ctrl+V) al crear la publicación en {self.red.nombre}.",
            )


class VistaResultados(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.resultado: ResultadoGeneracion | None = None
        self.idea = ""

        self.vacio = QLabel(
            "✨ Las publicaciones aparecerán aquí.\n\n"
            "Escriba su idea, adjunte una imagen o un video si quiere,\n"
            "elija las redes y presione «Generar publicaciones»."
        )
        self.vacio.setObjectName("vacio")
        self.vacio.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.pestanas = QTabWidget()
        self.pestanas.setDocumentMode(True)

        self.boton_copiar_todo = QPushButton("📋 Copiar todo")
        self.boton_copiar_todo.clicked.connect(self.copiar_todo)
        self.boton_exportar = QPushButton("💾 Exportar…")
        self.boton_exportar.clicked.connect(self.exportar)
        self.modelo = QLabel()
        self.modelo.setObjectName("subtitulo")
        barra = QHBoxLayout()
        barra.addWidget(self.modelo)
        barra.addStretch()
        barra.addWidget(self.boton_copiar_todo)
        barra.addWidget(self.boton_exportar)

        contenido = QWidget()
        diseno_contenido = QVBoxLayout(contenido)
        diseno_contenido.setContentsMargins(0, 0, 0, 0)
        diseno_contenido.addWidget(self.pestanas)
        diseno_contenido.addLayout(barra)

        self.pila = QStackedWidget()
        self.pila.addWidget(self.vacio)
        self.pila.addWidget(contenido)

        diseno = QVBoxLayout(self)
        diseno.setContentsMargins(0, 0, 0, 0)
        diseno.addWidget(self.pila)

    def mostrar(self, resultado: ResultadoGeneracion, idea: str = "") -> None:
        self.resultado = resultado
        self.idea = idea
        self.pestanas.clear()
        for post in resultado.posts.posts:
            red = REDES.get(post.red)
            self.pestanas.addTab(PanelPost(post), red.nombre if red else post.red)
        self.pestanas.addTab(navegador_markdown(exportar.ideas_md(resultado)), "🎬 Ideas audiovisuales")
        self.pestanas.addTab(navegador_markdown(exportar.estrategia_md(resultado)), "📅 Estrategia y horarios")
        self.modelo.setText(f"Generado con {resultado.modelo}" if resultado.modelo else "")
        self.pila.setCurrentIndex(1)

    def limpiar(self) -> None:
        self.resultado = None
        self.pestanas.clear()
        self.pila.setCurrentIndex(0)

    def _markdown_actual(self) -> str:
        if not self.resultado:
            return ""
        # Se respetan las ediciones que el usuario haya hecho en los textos (que ya incluyen los hashtags).
        editados = [
            panel.post.model_copy(update={"texto": panel.texto(), "hashtags": []})
            for panel in (self.pestanas.widget(i) for i in range(self.pestanas.count()))
            if isinstance(panel, PanelPost)
        ]
        copia = ResultadoGeneracion(
            posts=self.resultado.posts.model_copy(update={"posts": editados}),
            investigacion=self.resultado.investigacion,
            modelo=self.resultado.modelo,
        )
        return exportar.resultado_a_markdown(copia, self.idea)

    def copiar_todo(self) -> None:
        if self.resultado:
            QGuiApplication.clipboard().setText(self._markdown_actual())
            _confirmar(self.boton_copiar_todo)

    def exportar(self) -> None:
        if not self.resultado:
            return
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Exportar publicaciones", str(Path.home() / "publicaciones.md"),
            "Markdown (*.md);;Texto (*.txt)",
        )
        if ruta:
            Path(ruta).write_text(self._markdown_actual(), encoding="utf-8")
            QMessageBox.information(self, "Exportado", f"Se guardó el archivo:\n{ruta}")
