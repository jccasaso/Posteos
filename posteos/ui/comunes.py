"""Estado compartido entre pestañas y widgets auxiliares."""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QElapsedTimer, QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from posteos.config import Configuracion, PerfilAnalizado, cargar_perfiles, guardar_perfiles
from posteos.ui.trabajador import GestorTareas


class Avisos(QObject):
    """Señales para que las pestañas se comuniquen sin conocerse entre sí."""

    perfiles_cambiados = Signal()
    historial_cambiado = Signal()
    configuracion_cambiada = Signal()
    usar_perfil = Signal(str)  # id del perfil
    ir_a_configuracion = Signal(str)  # mensaje para el usuario


@dataclass
class Contexto:
    config: Configuracion
    gestor: GestorTareas
    avisos: Avisos
    perfiles: list[PerfilAnalizado] = field(default_factory=cargar_perfiles)

    def guardar_perfiles(self) -> None:
        guardar_perfiles(self.perfiles)
        self.avisos.perfiles_cambiados.emit()

    def perfil(self, identificador: str) -> PerfilAnalizado | None:
        return next((p for p in self.perfiles if p.id == identificador), None)


def combo(opciones, actual: str | None = None, editable: bool = False) -> QComboBox:
    """Desplegable con textos; `opciones` puede ser una lista de textos o de pares (valor, texto)."""
    caja = QComboBox()
    caja.setEditable(editable)
    for opcion in opciones:
        if isinstance(opcion, tuple):
            caja.addItem(opcion[1], opcion[0])
        else:
            caja.addItem(opcion, opcion)
    if actual is not None:
        seleccionar(caja, actual)
    caja.setMinimumContentsLength(18)
    caja.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    return caja


def seleccionar(caja: QComboBox, valor: str) -> None:
    indice = caja.findData(valor)
    if indice < 0:
        indice = caja.findText(valor)
    if indice >= 0:
        caja.setCurrentIndex(indice)
    elif caja.isEditable():
        caja.setEditText(valor)


def valor(caja: QComboBox) -> str:
    if caja.isEditable():
        return caja.currentText().strip()
    dato = caja.currentData()
    return dato if dato is not None else caja.currentText()


class IndicadorProgreso(QWidget):
    """Barra animada con el último mensaje de progreso y el tiempo transcurrido."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.barra = QProgressBar()
        self.barra.setRange(0, 0)
        self.barra.setTextVisible(False)
        self.mensaje = QLabel()
        self.mensaje.setWordWrap(True)
        self.mensaje.setObjectName("subtitulo")
        self.tiempo = QLabel()
        self.tiempo.setObjectName("subtitulo")
        self.tiempo.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)

        fila = QHBoxLayout()
        fila.addWidget(self.mensaje, 1)
        fila.addWidget(self.tiempo)
        diseno = QVBoxLayout(self)
        diseno.setContentsMargins(0, 0, 0, 0)
        diseno.addWidget(self.barra)
        diseno.addLayout(fila)

        self._reloj = QElapsedTimer()
        self._temporizador = QTimer(self)
        self._temporizador.timeout.connect(self._tic)
        self.hide()

    def iniciar(self, mensaje: str) -> None:
        self.mensaje.setText(mensaje)
        self.barra.show()
        self._reloj.start()
        self._tic()
        self._temporizador.start(1000)
        self.show()

    def informar(self, mensaje: str) -> None:
        self.mensaje.setText(mensaje)

    def detener(self, mensaje: str = "") -> None:
        self._temporizador.stop()
        self.barra.hide()
        self.tiempo.clear()
        if mensaje:
            self.mensaje.setText(mensaje)
        else:
            self.hide()

    def _tic(self) -> None:
        segundos = self._reloj.elapsed() // 1000
        minutos, seg = divmod(segundos, 60)
        self.tiempo.setText(f"{minutos}:{seg:02d}")
