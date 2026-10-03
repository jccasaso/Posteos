"""Arranque de la aplicación de escritorio."""

from __future__ import annotations

import sys


def main() -> None:
    if "--version" in sys.argv:
        from posteos import __version__

        print(__version__)
        return

    from PySide6.QtCore import QLocale, Qt, QTimer
    from PySide6.QtWidgets import QApplication

    from posteos import NOMBRE_APP
    from posteos.ui.estilo import ESTILO
    from posteos.ui.ventana import VentanaPrincipal, icono_app

    if sys.platform == "win32":
        # Para que Windows muestre el ícono propio en la barra de tareas.
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Posteos.App")
        except Exception:
            pass

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(NOMBRE_APP)
    app.setStyle("Fusion")
    app.setStyleSheet(ESTILO)
    app.setWindowIcon(icono_app())
    QLocale.setDefault(QLocale(QLocale.Language.Spanish))

    ventana = VentanaPrincipal()
    ventana.show()

    if "--autoprueba" in sys.argv:
        # Verificación del ejecutable empaquetado: carga los proveedores de IA, abre la ventana y sale.
        import posteos.busqueda  # noqa: F401
        import posteos.ia.claude  # noqa: F401
        import posteos.ia.gemini  # noqa: F401
        import posteos.ia.local  # noqa: F401
        from ddgs import DDGS  # noqa: F401

        QTimer.singleShot(1500, app.quit)

    sys.exit(app.exec())
