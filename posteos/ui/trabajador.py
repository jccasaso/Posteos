"""Ejecución de tareas largas (llamadas a la IA) en segundo plano sin congelar la ventana."""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QThread, Signal, Slot

from posteos.ia import Cancelado, describir_error

# La función recibe (progreso, texto_parcial) y devuelve el resultado.
Funcion = Callable[[Callable[[str], None], Callable[[str], None]], Any]


class Trabajador(QObject):
    progreso = Signal(str)
    parcial = Signal(str)
    terminado = Signal(object)
    fallo = Signal(str)
    finalizado = Signal()

    def __init__(self, funcion: Funcion) -> None:
        super().__init__()
        self._funcion = funcion

    @Slot()
    def ejecutar(self) -> None:
        try:
            resultado = self._funcion(self.progreso.emit, self.parcial.emit)
        except Cancelado:
            self.fallo.emit("Operación cancelada.")
        except Exception as e:  # se muestra al usuario en lugar de cerrar la aplicación
            self.fallo.emit(describir_error(e))
        else:
            self.terminado.emit(resultado)
        finally:
            self.finalizado.emit()


class GestorTareas(QObject):
    """Mantiene vivos los hilos en curso y los limpia al terminar.

    Las funciones de retorno deben ser métodos de widgets, para que Qt las ejecute en el hilo de la ventana.
    """

    def __init__(self, padre: QObject | None = None) -> None:
        super().__init__(padre)
        self._activos: set[tuple[QThread, Trabajador]] = set()

    def lanzar(
        self,
        funcion: Funcion,
        al_terminar: Callable[[Any], None],
        al_fallar: Callable[[str], None],
        al_progresar: Callable[[str], None] | None = None,
        al_recibir_texto: Callable[[str], None] | None = None,
    ) -> None:
        hilo = QThread()
        trabajador = Trabajador(funcion)
        trabajador.moveToThread(hilo)
        par = (hilo, trabajador)
        self._activos.add(par)

        hilo.started.connect(trabajador.ejecutar)
        trabajador.terminado.connect(al_terminar)
        trabajador.fallo.connect(al_fallar)
        if al_progresar:
            trabajador.progreso.connect(al_progresar)
        if al_recibir_texto:
            trabajador.parcial.connect(al_recibir_texto)
        trabajador.finalizado.connect(hilo.quit)
        hilo.finished.connect(self._al_finalizar_hilo)
        hilo.start()

    @Slot()
    def _al_finalizar_hilo(self) -> None:
        hilo = self.sender()
        for par in list(self._activos):
            if par[0] is hilo:
                self._activos.discard(par)
                par[1].deleteLater()
                hilo.deleteLater()

    def hay_tareas(self) -> bool:
        return bool(self._activos)

    def esperar(self, milisegundos: int = 3000) -> None:
        for hilo, _ in list(self._activos):
            hilo.quit()
            hilo.wait(milisegundos)
