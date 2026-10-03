"""Ventana principal de Posteos."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtGui import QCloseEvent, QIcon
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMainWindow, QMessageBox, QTabWidget, QVBoxLayout, QWidget

from posteos import NOMBRE_APP
from posteos.config import Configuracion
from posteos.ui.comunes import Avisos, Contexto
from posteos.ui.pestana_analizar import PestanaAnalizar
from posteos.ui.pestana_configuracion import PestanaConfiguracion
from posteos.ui.pestana_crear import PestanaCrear
from posteos.ui.pestana_historial import PestanaHistorial
from posteos.ui.trabajador import GestorTareas

RECURSOS = Path(__file__).resolve().parent.parent / "recursos"


def icono_app() -> QIcon:
    return QIcon(str(RECURSOS / "icono.png"))


class VentanaPrincipal(QMainWindow):
    def __init__(self, config: Configuracion | None = None) -> None:
        super().__init__()
        self.setWindowTitle(f"{NOMBRE_APP} · Publicaciones para redes sociales con IA")
        self.setWindowIcon(icono_app())
        self.resize(1320, 860)

        self.gestor = GestorTareas(self)
        self.ctx = Contexto(config=config or Configuracion.cargar(), gestor=self.gestor, avisos=Avisos(self))

        titulo = QLabel(f"✨ {NOMBRE_APP}")
        titulo.setObjectName("titulo")
        subtitulo = QLabel("Convierta sus ideas en publicaciones listas para LinkedIn, Instagram, Facebook, X, WhatsApp y más.")
        subtitulo.setObjectName("subtitulo")
        cabecera = QHBoxLayout()
        cabecera.addWidget(titulo)
        cabecera.addSpacing(12)
        cabecera.addWidget(subtitulo, 1)

        self.crear = PestanaCrear(self.ctx)
        self.analizar = PestanaAnalizar(self.ctx)
        self.historial = PestanaHistorial(self.ctx)
        self.configuracion = PestanaConfiguracion(self.ctx)

        self.pestanas = QTabWidget()
        self.pestanas.addTab(self.crear, "✍️  Crear publicación")
        self.pestanas.addTab(self.analizar, "🔍  Analizar cuenta")
        self.pestanas.addTab(self.historial, "🕘  Historial")
        self.pestanas.addTab(self.configuracion, "⚙️  Configuración")

        central = QWidget()
        central.setObjectName("fondo")
        diseno = QVBoxLayout(central)
        diseno.setContentsMargins(14, 10, 14, 14)
        diseno.addLayout(cabecera)
        diseno.addWidget(self.pestanas, 1)
        self.setCentralWidget(central)

        self.ctx.avisos.usar_perfil.connect(self._usar_perfil)
        self.ctx.avisos.ir_a_configuracion.connect(self._ir_a_configuracion)

        if not self.ctx.config.proveedor_listo():
            self._ir_a_configuracion(
                "Bienvenido. Para empezar gratis, consiga una clave de Google Gemini en aistudio.google.com "
                "(no pide tarjeta), péguela abajo y presione «Guardar configuración»."
            )

    @Slot(str)
    def _usar_perfil(self, identificador: str) -> None:
        self.crear.usar_perfil(identificador)
        self.pestanas.setCurrentWidget(self.crear)

    @Slot(str)
    def _ir_a_configuracion(self, mensaje: str) -> None:
        self.pestanas.setCurrentWidget(self.configuracion)
        self.configuracion.mostrar_aviso(mensaje)

    def closeEvent(self, evento: QCloseEvent) -> None:
        if self.gestor.hay_tareas():
            respuesta = QMessageBox.question(
                self, "Tarea en curso", "Hay una tarea de IA en curso. ¿Desea salir de todos modos?"
            )
            if respuesta != QMessageBox.StandardButton.Yes:
                evento.ignore()
                return
            self.crear.cancelar()
            self.analizar.cancelar()
            self.gestor.esperar()
        evento.accept()
