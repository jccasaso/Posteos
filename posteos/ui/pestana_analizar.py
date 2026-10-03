"""Pestaña «Analizar cuenta»: estudia un enlace de red social y guarda su estilo como referencia."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from posteos.config import PerfilAnalizado
from posteos.ia import Proveedor, crear_proveedor
from posteos.opciones import REDES
from posteos.social import ErrorEnlace, detectar_red, nombre_sugerido, normalizar_url, obtener_metadatos
from posteos.ui.adjuntos import SelectorAdjuntos
from posteos.ui.comunes import Contexto, IndicadorProgreso

AYUDA_INICIAL = """\
## ¿Cómo funciona?

1. Pegue el enlace de una cuenta o de una publicación (Instagram, LinkedIn, Facebook, X, TikTok, YouTube, \
Threads o un canal de WhatsApp).
2. La IA lee la página, busca información pública en la web y analiza el contenido, la estructura, el tono, \
los formatos y qué le funciona a esa cuenta.
3. El análisis queda guardado en «Cuentas analizadas». Con el botón **«Crear un post con este estilo»** puede \
pedir una publicación nueva, con imagen o video, que imite a esa cuenta.

**Consejo:** varias redes piden iniciar sesión para ver las publicaciones. Para un análisis más preciso, \
pegue el texto de algunas publicaciones recientes o adjunte capturas de pantalla del perfil.
"""


class PestanaAnalizar(QWidget):
    def __init__(self, ctx: Contexto, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._motor: Proveedor | None = None
        self._url_en_curso = ""
        self._red_en_curso: str | None = None
        self._perfil_mostrado: PerfilAnalizado | None = None

        # --- Datos de entrada ---
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://www.instagram.com/usuario  ·  https://www.linkedin.com/in/persona")
        self.url.textChanged.connect(self._detectar)
        self.url.returnPressed.connect(self.analizar)
        self.red_detectada = QLabel("Red: —")
        self.red_detectada.setObjectName("subtitulo")

        self.texto_pegado = QPlainTextEdit()
        self.texto_pegado.setPlaceholderText(
            "Opcional: pegue aquí el texto de varias publicaciones recientes de la cuenta "
            "(muy útil si la red pide iniciar sesión)."
        )
        self.texto_pegado.setMaximumHeight(110)
        self.capturas = SelectorAdjuntos("Adjuntar capturas del perfil")
        self.notas = QLineEdit()
        self.notas.setPlaceholderText("Opcional: ¿qué quiere saber? Ej.: qué formatos le dan más interacción")

        grupo = QGroupBox("Cuenta o publicación a analizar")
        formulario = QFormLayout(grupo)
        formulario.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        formulario.addRow("Enlace:", self.url)
        formulario.addRow("", self.red_detectada)
        formulario.addRow("Publicaciones:", self.texto_pegado)
        formulario.addRow("Capturas:", self.capturas)
        formulario.addRow("Su pregunta:", self.notas)

        self.boton_analizar = QPushButton("🔍 Analizar cuenta")
        self.boton_analizar.setObjectName("principal")
        self.boton_analizar.clicked.connect(self.analizar)
        self.boton_cancelar = QPushButton("Cancelar")
        self.boton_cancelar.clicked.connect(self.cancelar)
        self.boton_cancelar.hide()
        acciones = QHBoxLayout()
        acciones.addWidget(self.boton_analizar, 1)
        acciones.addWidget(self.boton_cancelar)
        self.progreso = IndicadorProgreso()

        # --- Cuentas guardadas ---
        self.lista = QListWidget()
        self.lista.currentItemChanged.connect(self._mostrar_guardado)
        self.boton_borrar = QPushButton("Eliminar")
        self.boton_borrar.clicked.connect(self.eliminar_perfil)
        grupo_guardados = QGroupBox("Cuentas analizadas")
        diseno_guardados = QVBoxLayout(grupo_guardados)
        diseno_guardados.addWidget(self.lista)
        diseno_guardados.addWidget(self.boton_borrar, 0, Qt.AlignmentFlag.AlignRight)

        panel = QWidget()
        panel.setObjectName("fondo")
        diseno_panel = QVBoxLayout(panel)
        diseno_panel.addWidget(grupo)
        diseno_panel.addLayout(acciones)
        diseno_panel.addWidget(self.progreso)
        diseno_panel.addWidget(grupo_guardados, 1)
        desplazable = QScrollArea()
        desplazable.setWidgetResizable(True)
        desplazable.setWidget(panel)
        desplazable.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # --- Resultado ---
        self.informe = QTextBrowser()
        self.informe.setOpenExternalLinks(True)
        self.informe.setMarkdown(AYUDA_INICIAL)
        self.boton_usar = QPushButton("✍️ Crear un post con este estilo")
        self.boton_usar.setObjectName("principal")
        self.boton_usar.clicked.connect(self.usar_perfil)
        self.boton_exportar = QPushButton("💾 Exportar análisis…")
        self.boton_exportar.clicked.connect(self.exportar)
        barra = QHBoxLayout()
        barra.addWidget(self.boton_exportar)
        barra.addStretch()
        barra.addWidget(self.boton_usar)
        derecha = QWidget()
        diseno_der = QVBoxLayout(derecha)
        diseno_der.setContentsMargins(0, 0, 0, 0)
        diseno_der.addWidget(self.informe, 1)
        diseno_der.addLayout(barra)

        divisor = QSplitter(Qt.Orientation.Horizontal)
        divisor.addWidget(desplazable)
        divisor.addWidget(derecha)
        divisor.setStretchFactor(0, 2)
        divisor.setStretchFactor(1, 3)
        divisor.setSizes([500, 780])

        diseno = QVBoxLayout(self)
        diseno.setContentsMargins(10, 10, 10, 10)
        diseno.addWidget(divisor)

        self.actualizar_lista()
        self._actualizar_botones()
        ctx.avisos.perfiles_cambiados.connect(self.actualizar_lista)

    # --- Lista de perfiles ---

    @Slot()
    def actualizar_lista(self) -> None:
        actual = self._perfil_mostrado.id if self._perfil_mostrado else None
        self.lista.blockSignals(True)
        self.lista.clear()
        for perfil in self.ctx.perfiles:
            item = QListWidgetItem(f"{perfil.nombre}\n{perfil.fecha}")
            item.setData(Qt.ItemDataRole.UserRole, perfil.id)
            item.setToolTip(perfil.url)
            self.lista.addItem(item)
            if perfil.id == actual:
                self.lista.setCurrentItem(item)
        self.lista.blockSignals(False)
        self._actualizar_botones()

    @Slot(QListWidgetItem, QListWidgetItem)
    def _mostrar_guardado(self, item: QListWidgetItem | None, _anterior=None) -> None:
        if item is None:
            return
        perfil = self.ctx.perfil(item.data(Qt.ItemDataRole.UserRole))
        if perfil:
            self._perfil_mostrado = perfil
            self.informe.setMarkdown(f"# {perfil.nombre}\n\n<{perfil.url}>\n\n{perfil.analisis}")
        self._actualizar_botones()

    @Slot()
    def eliminar_perfil(self) -> None:
        item = self.lista.currentItem()
        if not item:
            return
        perfil = self.ctx.perfil(item.data(Qt.ItemDataRole.UserRole))
        if not perfil:
            return
        respuesta = QMessageBox.question(self, "Eliminar análisis", f"¿Eliminar el análisis de «{perfil.nombre}»?")
        if respuesta != QMessageBox.StandardButton.Yes:
            return
        self.ctx.perfiles.remove(perfil)
        if self._perfil_mostrado is perfil:
            self._perfil_mostrado = None
            self.informe.setMarkdown(AYUDA_INICIAL)
        self.ctx.guardar_perfiles()

    def _actualizar_botones(self) -> None:
        hay_perfil = self._perfil_mostrado is not None
        self.boton_usar.setEnabled(hay_perfil)
        self.boton_exportar.setEnabled(hay_perfil)
        self.boton_borrar.setEnabled(self.lista.currentItem() is not None)

    # --- Análisis ---

    @Slot(str)
    def _detectar(self, texto: str) -> None:
        red = detectar_red(texto) if texto.strip() else None
        self.red_detectada.setText(f"Red: {REDES[red].nombre}" if red else "Red: —")

    @Slot()
    def analizar(self) -> None:
        if not self.boton_analizar.isEnabled():
            return
        try:
            url = normalizar_url(self.url.text())
        except ErrorEnlace as e:
            QMessageBox.warning(self, "Enlace no válido", str(e))
            return
        config = self.ctx.config
        if not config.proveedor_listo():
            self.ctx.avisos.ir_a_configuracion.emit("Para analizar cuentas primero cargue la clave de API de la IA elegida.")
            return
        red = detectar_red(url)
        texto_pegado = self.texto_pegado.toPlainText()
        notas = self.notas.text()
        capturas = list(self.capturas.adjuntos)
        self._url_en_curso = url
        self._red_en_curso = red

        def tarea(progreso, parcial) -> str:
            progreso("Leyendo los datos públicos de la página…")
            metadatos = obtener_metadatos(url)
            self._motor = crear_proveedor(config, progreso, parcial)
            return self._motor.analizar_cuenta(url, red, metadatos.como_texto(), texto_pegado, notas, capturas)

        self._perfil_mostrado = None
        self.lista.clearSelection()
        self.informe.clear()
        self._en_curso(True)
        self.progreso.iniciar("Preparando…")
        self.ctx.gestor.lanzar(tarea, self._al_terminar, self._al_fallar, self.progreso.informar, self._al_recibir_texto)

    @Slot(str)
    def _al_recibir_texto(self, fragmento: str) -> None:
        cursor = self.informe.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(fragmento)
        self.informe.setTextCursor(cursor)
        self.informe.ensureCursorVisible()

    @Slot()
    def cancelar(self) -> None:
        if self._motor:
            self._motor.cancelar()
            self.progreso.informar("Cancelando…")

    @Slot(object)
    def _al_terminar(self, analisis: str) -> None:
        self._en_curso(False)
        perfil = PerfilAnalizado(
            nombre=nombre_sugerido(self._url_en_curso),
            url=self._url_en_curso,
            red=self._red_en_curso or "",
            analisis=analisis,
        )
        self.ctx.perfiles.insert(0, perfil)
        self._perfil_mostrado = perfil
        self.informe.setMarkdown(f"# {perfil.nombre}\n\n<{perfil.url}>\n\n{analisis}")
        self.progreso.detener("✅ Análisis terminado y guardado en «Cuentas analizadas».")
        self.ctx.guardar_perfiles()

    @Slot(str)
    def _al_fallar(self, mensaje: str) -> None:
        self._en_curso(False)
        self.progreso.detener("⚠ " + mensaje)
        if mensaje != "Operación cancelada.":
            QMessageBox.warning(self, "No se pudo analizar la cuenta", mensaje)

    def _en_curso(self, activo: bool) -> None:
        self.boton_analizar.setEnabled(not activo)
        self.boton_analizar.setText("Analizando…" if activo else "🔍 Analizar cuenta")
        self.boton_cancelar.setVisible(activo)
        if not activo:
            self._motor = None
        self._actualizar_botones()

    # --- Acciones sobre el análisis ---

    @Slot()
    def usar_perfil(self) -> None:
        if self._perfil_mostrado:
            self.ctx.avisos.usar_perfil.emit(self._perfil_mostrado.id)

    @Slot()
    def exportar(self) -> None:
        perfil = self._perfil_mostrado
        if not perfil:
            return
        sugerido = "".join(c if c.isalnum() else "_" for c in perfil.nombre).strip("_") or "analisis"
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Exportar análisis", str(Path.home() / f"analisis_{sugerido}.md"), "Markdown (*.md);;Texto (*.txt)"
        )
        if ruta:
            Path(ruta).write_text(f"# {perfil.nombre}\n\n{perfil.url}\n\n{perfil.analisis}\n", encoding="utf-8")
            QMessageBox.information(self, "Exportado", f"Se guardó el archivo:\n{ruta}")
