"""Selector de imágenes y videos con miniaturas y soporte para arrastrar y soltar."""

from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from posteos.media import EXT_IMAGEN, EXT_VIDEO, Adjunto, ErrorAdjunto, cargar_adjunto

MAX_ADJUNTOS = 10


def pil_a_pixmap(imagen: Image.Image) -> QPixmap:
    rgba = imagen.convert("RGBA")
    qimagen = QImage(rgba.tobytes("raw", "RGBA"), rgba.width, rgba.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimagen.copy())


class SelectorAdjuntos(QWidget):
    cambiado = Signal()

    def __init__(self, texto_boton: str = "Adjuntar imagen o video", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.adjuntos: list[Adjunto] = []
        self.setAcceptDrops(True)

        self.lista = QListWidget()
        self.lista.setViewMode(QListWidget.ViewMode.IconMode)
        self.lista.setIconSize(QSize(88, 88))
        self.lista.setGridSize(QSize(112, 122))
        self.lista.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.lista.setMovement(QListWidget.Movement.Static)
        self.lista.setWordWrap(True)
        self.lista.setFixedHeight(136)
        self.lista.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.lista.setToolTip("También puede arrastrar archivos hasta aquí.")
        self.lista.setAcceptDrops(False)  # los archivos soltados los recibe este widget

        self.boton_agregar = QPushButton("📎 " + texto_boton)
        self.boton_quitar = QPushButton("Quitar seleccionados")
        self.boton_agregar.clicked.connect(self.elegir_archivos)
        self.boton_quitar.clicked.connect(self.quitar_seleccionados)
        self.ayuda = QLabel("Arrastre archivos aquí · JPG, PNG, WEBP, MP4, MOV…")
        self.ayuda.setObjectName("subtitulo")

        botones = QHBoxLayout()
        botones.addWidget(self.boton_agregar)
        botones.addWidget(self.boton_quitar)
        botones.addStretch()

        diseno = QVBoxLayout(self)
        diseno.setContentsMargins(0, 0, 0, 0)
        diseno.addLayout(botones)
        diseno.addWidget(self.lista)
        diseno.addWidget(self.ayuda)
        self._actualizar()

    def elegir_archivos(self) -> None:
        patrones = " ".join(f"*{e}" for e in sorted(EXT_IMAGEN | EXT_VIDEO))
        rutas, _ = QFileDialog.getOpenFileNames(
            self, "Elegir imágenes o videos", "", f"Imágenes y videos ({patrones});;Todos los archivos (*)"
        )
        self.agregar_rutas(rutas)

    def agregar_rutas(self, rutas: list[str]) -> None:
        errores = []
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            for ruta in rutas:
                if len(self.adjuntos) >= MAX_ADJUNTOS:
                    errores.append(f"Se admiten como máximo {MAX_ADJUNTOS} archivos.")
                    break
                try:
                    adjunto = cargar_adjunto(ruta)
                except ErrorAdjunto as e:
                    errores.append(str(e))
                    continue
                self.adjuntos.append(adjunto)
                self._agregar_item(adjunto)
        finally:
            QApplication.restoreOverrideCursor()
        if errores:
            QMessageBox.warning(self, "Archivos adjuntos", "\n".join(errores))
        self._actualizar()
        self.cambiado.emit()

    def _agregar_item(self, adjunto: Adjunto) -> None:
        icono = "🎬 " if adjunto.tipo == "video" else ""
        item = QListWidgetItem(f"{icono}{adjunto.nombre}")
        miniatura = adjunto.miniatura(176)
        if miniatura is not None:
            item.setIcon(QIcon(pil_a_pixmap(miniatura)))
        item.setToolTip(f"{adjunto.ruta}\n{adjunto.descripcion}")
        self.lista.addItem(item)

    def quitar_seleccionados(self) -> None:
        filas = sorted((self.lista.row(i) for i in self.lista.selectedItems()), reverse=True)
        for fila in filas:
            self.lista.takeItem(fila)
            del self.adjuntos[fila]
        self._actualizar()
        self.cambiado.emit()

    def limpiar(self) -> None:
        self.lista.clear()
        self.adjuntos.clear()
        self._actualizar()
        self.cambiado.emit()

    def _actualizar(self) -> None:
        self.boton_quitar.setEnabled(bool(self.adjuntos))

    # --- Arrastrar y soltar ---------------------------------------------------

    def dragEnterEvent(self, evento) -> None:
        if evento.mimeData().hasUrls():
            evento.acceptProposedAction()

    def dropEvent(self, evento) -> None:
        rutas = [u.toLocalFile() for u in evento.mimeData().urls() if u.isLocalFile()]
        if rutas:
            self.agregar_rutas(rutas)
            evento.acceptProposedAction()
