"""Pestaña «Configuración»: clave de API, modelo, valores por defecto y datos de la marca."""

from __future__ import annotations

import anthropic
from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from posteos import __version__, opciones
from posteos.config import carpeta_datos
from posteos.ui.comunes import Contexto, combo, valor


class PestanaConfiguracion(QWidget):
    def __init__(self, ctx: Contexto, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        config = ctx.config

        self.aviso = QLabel()
        self.aviso.setObjectName("etiquetaDato")
        self.aviso.setWordWrap(True)
        self.aviso.hide()

        # --- IA ---
        self.api_key = QLineEdit(config.obtener_api_key())
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key.setPlaceholderText("sk-ant-…")
        self.mostrar_clave = QCheckBox("Mostrar")
        self.mostrar_clave.toggled.connect(
            lambda visible: self.api_key.setEchoMode(
                QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password
            )
        )
        self.boton_probar = QPushButton("Probar conexión")
        self.boton_probar.clicked.connect(self.probar)
        fila_clave = QHBoxLayout()
        fila_clave.addWidget(self.api_key, 1)
        fila_clave.addWidget(self.mostrar_clave)
        fila_clave.addWidget(self.boton_probar)
        ayuda_clave = QLabel(
            'Obtenga su clave en <a href="https://console.anthropic.com/settings/keys">console.anthropic.com</a>. '
            "Se guarda de forma segura en el administrador de credenciales del sistema."
        )
        ayuda_clave.setOpenExternalLinks(True)
        ayuda_clave.setWordWrap(True)
        ayuda_clave.setObjectName("subtitulo")

        self.modelo = combo(opciones.MODELOS, config.modelo)
        self.esfuerzo = combo(opciones.ESFUERZOS, config.esfuerzo)
        self.esfuerzo.setToolTip("Cuánto razona la IA antes de responder: más esfuerzo = mejor calidad, pero más lento.")

        grupo_ia = QGroupBox("Inteligencia artificial")
        form_ia = QFormLayout(grupo_ia)
        form_ia.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form_ia.addRow("Clave de API:", fila_clave)
        form_ia.addRow("", ayuda_clave)
        form_ia.addRow("Modelo:", self.modelo)
        form_ia.addRow("Nivel de razonamiento:", self.esfuerzo)

        # --- Valores por defecto ---
        self.pais = combo([p for p, _ in opciones.PAISES], config.pais)
        self.variante = combo(opciones.VARIANTES_ESPANOL, config.variante)
        self.investigar = QCheckBox("Investigar en la web el mejor día y horario (recomendado)")
        self.investigar.setChecked(config.investigar_web)
        self.redes = {}
        fila_redes = QGridLayout()
        for indice, (clave, red) in enumerate(opciones.REDES.items()):
            casilla = QCheckBox(red.nombre)
            casilla.setChecked(clave in config.redes)
            self.redes[clave] = casilla
            fila_redes.addWidget(casilla, indice // 4, indice % 4)

        grupo_defecto = QGroupBox("Valores por defecto")
        form_defecto = QFormLayout(grupo_defecto)
        form_defecto.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form_defecto.addRow("País y zona horaria:", self.pais)
        form_defecto.addRow("Idioma:", self.variante)
        form_defecto.addRow("Redes marcadas:", fila_redes)
        form_defecto.addRow(self.investigar)

        # --- Marca ---
        self.marca_nombre = QLineEdit(config.marca_nombre)
        self.marca_nombre.setPlaceholderText("Ej.: Café Aroma / Juan Pérez")
        self.marca_sector = QLineEdit(config.marca_sector)
        self.marca_sector.setPlaceholderText("Ej.: Gastronomía, consultoría financiera, moda…")
        self.marca_descripcion = QPlainTextEdit(config.marca_descripcion)
        self.marca_descripcion.setPlaceholderText(
            "Qué hace, a quién le habla, valores, productos principales, palabras que usa o evita, "
            "sitio web, ubicación…"
        )
        self.marca_descripcion.setMaximumHeight(120)
        grupo_marca = QGroupBox("Su marca (se usa en todas las publicaciones)")
        form_marca = QFormLayout(grupo_marca)
        form_marca.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        form_marca.addRow("Nombre:", self.marca_nombre)
        form_marca.addRow("Sector:", self.marca_sector)
        form_marca.addRow("Descripción:", self.marca_descripcion)

        self.boton_guardar = QPushButton("💾 Guardar configuración")
        self.boton_guardar.setObjectName("principal")
        self.boton_guardar.clicked.connect(self.guardar)

        info = QLabel(f"Posteos {__version__} · Datos guardados en: {carpeta_datos()}")
        info.setObjectName("subtitulo")
        info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        info.setWordWrap(True)

        panel = QWidget()
        panel.setObjectName("fondo")
        diseno_panel = QVBoxLayout(panel)
        diseno_panel.addWidget(self.aviso)
        diseno_panel.addWidget(grupo_ia)
        diseno_panel.addWidget(grupo_defecto)
        diseno_panel.addWidget(grupo_marca)
        diseno_panel.addWidget(self.boton_guardar, 0, Qt.AlignmentFlag.AlignRight)
        diseno_panel.addStretch()
        diseno_panel.addWidget(info)
        panel.setMaximumWidth(900)

        contenedor = QWidget()
        diseno_cont = QHBoxLayout(contenedor)
        diseno_cont.addStretch()
        diseno_cont.addWidget(panel, 10)
        diseno_cont.addStretch()
        desplazable = QScrollArea()
        desplazable.setWidgetResizable(True)
        desplazable.setWidget(contenedor)

        diseno = QVBoxLayout(self)
        diseno.setContentsMargins(0, 0, 0, 0)
        diseno.addWidget(desplazable)

    def mostrar_aviso(self, mensaje: str) -> None:
        self.aviso.setText("🔑 " + mensaje)
        self.aviso.show()
        self.api_key.setFocus()

    @Slot()
    def guardar(self) -> None:
        config = self.ctx.config
        config.modelo = valor(self.modelo)
        config.esfuerzo = valor(self.esfuerzo)
        config.pais = valor(self.pais)
        config.variante = valor(self.variante)
        config.investigar_web = self.investigar.isChecked()
        config.redes = [clave for clave, casilla in self.redes.items() if casilla.isChecked()]
        config.marca_nombre = self.marca_nombre.text().strip()
        config.marca_sector = self.marca_sector.text().strip()
        config.marca_descripcion = self.marca_descripcion.toPlainText().strip()
        seguro = config.guardar_api_key(self.api_key.text())
        config.guardar()
        self.ctx.avisos.configuracion_cambiada.emit()
        self.aviso.hide()
        mensaje = "La configuración se guardó correctamente."
        if not seguro and self.api_key.text().strip():
            mensaje += (
                "\n\nAtención: el sistema no tiene un almacén seguro de credenciales disponible; "
                "la clave se guardó en el archivo de configuración."
            )
        QMessageBox.information(self, "Configuración", mensaje)

    @Slot()
    def probar(self) -> None:
        clave = self.api_key.text().strip()
        if not clave:
            QMessageBox.warning(self, "Probar conexión", "Escriba primero la clave de API.")
            return
        modelo = valor(self.modelo)

        def tarea(_progreso, _parcial) -> str:
            info = anthropic.Anthropic(api_key=clave, max_retries=1, timeout=30.0).models.retrieve(modelo)
            return info.display_name or modelo

        self.boton_probar.setEnabled(False)
        self.boton_probar.setText("Probando…")
        self.ctx.gestor.lanzar(tarea, self._prueba_correcta, self._prueba_fallida)

    @Slot(object)
    def _prueba_correcta(self, nombre: str) -> None:
        self._restaurar_boton()
        QMessageBox.information(
            self, "Probar conexión", f"✅ Conexión correcta. Modelo disponible: {nombre}.\n\nRecuerde guardar la configuración."
        )

    @Slot(str)
    def _prueba_fallida(self, mensaje: str) -> None:
        self._restaurar_boton()
        QMessageBox.warning(self, "Probar conexión", mensaje)

    def _restaurar_boton(self) -> None:
        self.boton_probar.setEnabled(True)
        self.boton_probar.setText("Probar conexión")
