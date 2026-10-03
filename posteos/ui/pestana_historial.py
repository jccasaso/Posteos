"""Pestaña «Historial»: publicaciones generadas anteriormente."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from posteos.config import borrar_historial, cargar_historial
from posteos.opciones import REDES
from posteos.ui.comunes import Contexto


class PestanaHistorial(QWidget):
    def __init__(self, ctx: Contexto, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self.entradas: list[dict] = []

        self.lista = QListWidget()
        self.lista.currentRowChanged.connect(self._mostrar)
        self.vista = QTextBrowser()
        self.vista.setOpenExternalLinks(True)

        self.boton_copiar = QPushButton("📋 Copiar")
        self.boton_copiar.clicked.connect(self.copiar)
        self.boton_exportar = QPushButton("💾 Exportar…")
        self.boton_exportar.clicked.connect(self.exportar)
        self.boton_borrar = QPushButton("Borrar historial")
        self.boton_borrar.clicked.connect(self.borrar)

        barra = QHBoxLayout()
        barra.addWidget(self.boton_borrar)
        barra.addStretch()
        barra.addWidget(self.boton_copiar)
        barra.addWidget(self.boton_exportar)

        divisor = QSplitter(Qt.Orientation.Horizontal)
        divisor.addWidget(self.lista)
        divisor.addWidget(self.vista)
        divisor.setSizes([360, 900])

        diseno = QVBoxLayout(self)
        diseno.setContentsMargins(10, 10, 10, 10)
        diseno.addWidget(divisor, 1)
        diseno.addLayout(barra)

        self.actualizar()
        ctx.avisos.historial_cambiado.connect(self.actualizar)

    @Slot()
    def actualizar(self) -> None:
        self.entradas = cargar_historial()
        self.lista.clear()
        for entrada in self.entradas:
            idea = " ".join((entrada.get("idea") or "(solo material adjunto)").split())
            if len(idea) > 70:
                idea = idea[:70] + "…"
            redes = ", ".join(REDES[r].nombre if r in REDES else r for r in entrada.get("redes", []))
            item = QListWidgetItem(f"{entrada.get('fecha', '')} · {redes}\n{idea}")
            self.lista.addItem(item)
        if self.entradas:
            self.lista.setCurrentRow(0)
        else:
            self.vista.setMarkdown("Todavía no hay publicaciones generadas.")
        self._actualizar_botones()

    @Slot(int)
    def _mostrar(self, fila: int) -> None:
        if 0 <= fila < len(self.entradas):
            self.vista.setMarkdown(self.entradas[fila].get("markdown", ""))
        self._actualizar_botones()

    def _actual(self) -> str:
        fila = self.lista.currentRow()
        return self.entradas[fila].get("markdown", "") if 0 <= fila < len(self.entradas) else ""

    def _actualizar_botones(self) -> None:
        hay = bool(self._actual())
        self.boton_copiar.setEnabled(hay)
        self.boton_exportar.setEnabled(hay)
        self.boton_borrar.setEnabled(bool(self.entradas))

    @Slot()
    def copiar(self) -> None:
        QGuiApplication.clipboard().setText(self._actual())

    @Slot()
    def exportar(self) -> None:
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Exportar publicaciones", str(Path.home() / "publicaciones.md"), "Markdown (*.md);;Texto (*.txt)"
        )
        if ruta:
            Path(ruta).write_text(self._actual(), encoding="utf-8")

    @Slot()
    def borrar(self) -> None:
        if QMessageBox.question(self, "Borrar historial", "¿Borrar todo el historial?") == QMessageBox.StandardButton.Yes:
            borrar_historial()
            self.actualizar()
