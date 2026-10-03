"""Pestaña «Configuración»: proveedor de IA, claves, modelos, valores por defecto y datos de la marca."""

from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from posteos import __version__, opciones
from posteos.config import carpeta_datos
from posteos.ia import listar_modelos, probar_conexion
from posteos.ui.comunes import Contexto, combo, seleccionar, valor

AYUDA_GEMINI = (
    "Gratis y sin tarjeta: entre en "
    '<a href="https://aistudio.google.com/apikey">aistudio.google.com/apikey</a>, inicie sesión con su cuenta '
    "de Google y presione «Create API key». El plan gratuito tiene límites por minuto y por día, suficientes para "
    "uso personal. En el plan gratuito, Google puede usar lo que envía para mejorar sus productos."
)
AYUDA_OLLAMA = (
    "La IA funciona en esta PC, sin internet y sin costo. 1) Instale Ollama desde "
    '<a href="https://ollama.com/download">ollama.com/download</a>. 2) Abra una terminal y descargue un modelo con '
    "visión, por ejemplo: <b>ollama pull gemma3:12b</b> (necesita unos 16 GB de RAM; con menos memoria use "
    "<b>gemma3:4b</b>). 3) Presione «Actualizar lista» y elija el modelo. La búsqueda web se hace con DuckDuckGo. "
    "La calidad es menor que la de Gemini o Claude y puede tardar varios minutos."
)
AYUDA_CLAUDE = (
    "De pago por uso: cree una clave en "
    '<a href="https://console.anthropic.com/settings/keys">console.anthropic.com</a> y cargue crédito. '
    "Ese crédito es independiente de las suscripciones de claude.ai y de Claude Code."
)


def _ayuda(texto: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setOpenExternalLinks(True)
    etiqueta.setWordWrap(True)
    etiqueta.setObjectName("subtitulo")
    return etiqueta


class CampoClave(QWidget):
    """Campo de clave de API con casilla «Mostrar»."""

    def __init__(self, clave: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.campo = QLineEdit(clave)
        self.campo.setEchoMode(QLineEdit.EchoMode.Password)
        mostrar = QCheckBox("Mostrar")
        mostrar.toggled.connect(
            lambda visible: self.campo.setEchoMode(QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password)
        )
        diseno = QHBoxLayout(self)
        diseno.setContentsMargins(0, 0, 0, 0)
        diseno.addWidget(self.campo, 1)
        diseno.addWidget(mostrar)

    def texto(self) -> str:
        return self.campo.text().strip()


class PestanaConfiguracion(QWidget):
    def __init__(self, ctx: Contexto, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._proveedor_lista = "gemini"
        config = ctx.config

        self.aviso = QLabel()
        self.aviso.setObjectName("etiquetaDato")
        self.aviso.setWordWrap(True)
        self.aviso.hide()

        # --- Proveedor de IA ---
        self.proveedor = combo(opciones.PROVEEDORES, config.proveedor)
        self.paginas = QStackedWidget()

        # Gemini
        self.clave_gemini = CampoClave(config.obtener_api_key("gemini"))
        self.clave_gemini.campo.setPlaceholderText("AIza…")
        self.modelo_gemini = combo(opciones.MODELOS_GEMINI, editable=True)
        seleccionar(self.modelo_gemini, config.modelo_gemini)
        self.boton_lista_gemini = QPushButton("Actualizar lista")
        self.boton_lista_gemini.clicked.connect(lambda: self._actualizar_modelos("gemini"))
        pagina_gemini = self._pagina(
            [("Clave de API:", self.clave_gemini), ("Modelo:", self._fila(self.modelo_gemini, self.boton_lista_gemini))],
            AYUDA_GEMINI,
        )

        # Ollama
        self.url_ollama = QLineEdit(config.ollama_url)
        self.url_ollama.setPlaceholderText("http://localhost:11434")
        self.modelo_ollama = combo(opciones.MODELOS_OLLAMA, editable=True)
        seleccionar(self.modelo_ollama, config.modelo_ollama)
        self.boton_lista_ollama = QPushButton("Actualizar lista")
        self.boton_lista_ollama.clicked.connect(lambda: self._actualizar_modelos("ollama"))
        pagina_ollama = self._pagina(
            [("Dirección de Ollama:", self.url_ollama), ("Modelo:", self._fila(self.modelo_ollama, self.boton_lista_ollama))],
            AYUDA_OLLAMA,
        )

        # Claude
        self.clave_claude = CampoClave(config.obtener_api_key("claude"))
        self.clave_claude.campo.setPlaceholderText("sk-ant-…")
        self.modelo_claude = combo(opciones.MODELOS_CLAUDE, config.modelo_claude)
        self.esfuerzo = combo(opciones.ESFUERZOS, config.esfuerzo)
        self.esfuerzo.setToolTip("Cuánto razona la IA antes de responder: más esfuerzo = mejor calidad, pero más lento.")
        pagina_claude = self._pagina(
            [("Clave de API:", self.clave_claude), ("Modelo:", self.modelo_claude), ("Nivel de razonamiento:", self.esfuerzo)],
            AYUDA_CLAUDE,
        )

        self._paginas = {"gemini": pagina_gemini, "ollama": pagina_ollama, "claude": pagina_claude}
        for pagina in self._paginas.values():
            self.paginas.addWidget(pagina)
        self.proveedor.currentIndexChanged.connect(self._cambiar_proveedor)

        self.boton_probar = QPushButton("Probar conexión")
        self.boton_probar.clicked.connect(self.probar)

        grupo_ia = QGroupBox("Inteligencia artificial")
        diseno_ia = QVBoxLayout(grupo_ia)
        fila_proveedor = QFormLayout()
        fila_proveedor.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        fila_proveedor.addRow("IA a utilizar:", self.proveedor)
        diseno_ia.addLayout(fila_proveedor)
        diseno_ia.addWidget(self.paginas)
        diseno_ia.addWidget(self.boton_probar, 0, Qt.AlignmentFlag.AlignRight)

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
        self._cambiar_proveedor()

    # --- Construcción ---

    @staticmethod
    def _fila(*widgets: QWidget) -> QWidget:
        fila = QWidget()
        diseno = QHBoxLayout(fila)
        diseno.setContentsMargins(0, 0, 0, 0)
        diseno.addWidget(widgets[0], 1)
        for widget in widgets[1:]:
            diseno.addWidget(widget)
        return fila

    @staticmethod
    def _pagina(filas: list[tuple[str, QWidget]], ayuda: str) -> QWidget:
        pagina = QWidget()
        diseno = QVBoxLayout(pagina)
        diseno.setContentsMargins(0, 4, 0, 0)
        formulario = QFormLayout()
        formulario.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        for etiqueta, widget in filas:
            formulario.addRow(etiqueta, widget)
        diseno.addLayout(formulario)
        diseno.addWidget(_ayuda(ayuda))
        return pagina

    # --- Acciones ---

    def _proveedor_elegido(self) -> str:
        return valor(self.proveedor)

    @Slot()
    def _cambiar_proveedor(self) -> None:
        actual = self._paginas[self._proveedor_elegido()]
        # El contenedor toma la altura de la página visible, no la de la más alta.
        for pagina in self._paginas.values():
            politica = QSizePolicy.Policy.Preferred if pagina is actual else QSizePolicy.Policy.Ignored
            pagina.setSizePolicy(politica, politica)
        self.paginas.setCurrentWidget(actual)
        self.paginas.updateGeometry()

    def _datos_conexion(self, proveedor: str) -> tuple[str, str]:
        """(clave o URL, modelo) escritos en pantalla para el proveedor indicado."""
        if proveedor == "ollama":
            return self.url_ollama.text().strip(), valor(self.modelo_ollama)
        if proveedor == "claude":
            return self.clave_claude.texto(), valor(self.modelo_claude)
        return self.clave_gemini.texto(), valor(self.modelo_gemini)

    def mostrar_aviso(self, mensaje: str) -> None:
        self.aviso.setText("🔑 " + mensaje)
        self.aviso.show()

    @Slot()
    def guardar(self) -> None:
        config = self.ctx.config
        config.proveedor = self._proveedor_elegido()
        config.modelo_gemini = valor(self.modelo_gemini) or "gemini-flash-latest"
        config.ollama_url = self.url_ollama.text().strip() or "http://localhost:11434"
        config.modelo_ollama = valor(self.modelo_ollama)
        config.modelo_claude = valor(self.modelo_claude)
        config.esfuerzo = valor(self.esfuerzo)
        config.pais = valor(self.pais)
        config.variante = valor(self.variante)
        config.investigar_web = self.investigar.isChecked()
        config.redes = [clave for clave, casilla in self.redes.items() if casilla.isChecked()]
        config.marca_nombre = self.marca_nombre.text().strip()
        config.marca_sector = self.marca_sector.text().strip()
        config.marca_descripcion = self.marca_descripcion.toPlainText().strip()
        seguro = True
        for proveedor, campo in (("gemini", self.clave_gemini), ("claude", self.clave_claude)):
            if campo.texto() != config.obtener_api_key(proveedor):
                seguro = config.guardar_api_key(proveedor, campo.texto()) and seguro
        config.guardar()
        self.ctx.avisos.configuracion_cambiada.emit()

        mensaje = "La configuración se guardó correctamente."
        if not seguro:
            mensaje += (
                "\n\nAtención: el sistema no tiene un almacén seguro de credenciales disponible; "
                "la clave se guardó en el archivo de configuración."
            )
        if config.proveedor_listo():
            self.aviso.hide()
        else:
            mensaje += "\n\nFalta la clave de API de la IA elegida."
        QMessageBox.information(self, "Configuración", mensaje)

    @Slot()
    def probar(self) -> None:
        proveedor = self._proveedor_elegido()
        clave_o_url, modelo = self._datos_conexion(proveedor)
        if proveedor != "ollama" and not clave_o_url:
            QMessageBox.warning(self, "Probar conexión", "Escriba primero la clave de API.")
            return

        def tarea(_progreso, _parcial) -> str:
            return probar_conexion(proveedor, clave_o_url, modelo)

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

    # --- Lista de modelos ---

    def _actualizar_modelos(self, proveedor: str) -> None:
        clave_o_url, _ = self._datos_conexion(proveedor)
        if proveedor == "gemini" and not clave_o_url:
            QMessageBox.warning(self, "Modelos", "Escriba primero la clave de API de Gemini.")
            return
        self._proveedor_lista = proveedor
        boton = self.boton_lista_gemini if proveedor == "gemini" else self.boton_lista_ollama
        boton.setEnabled(False)
        boton.setText("Buscando…")

        def tarea(_progreso, _parcial) -> list[str]:
            return listar_modelos(proveedor, clave_o_url)

        self.ctx.gestor.lanzar(tarea, self._modelos_recibidos, self._modelos_fallidos)

    def _caja_y_boton(self) -> tuple[QComboBox, QPushButton]:
        if self._proveedor_lista == "gemini":
            return self.modelo_gemini, self.boton_lista_gemini
        return self.modelo_ollama, self.boton_lista_ollama

    @Slot(object)
    def _modelos_recibidos(self, modelos: list[str]) -> None:
        caja, boton = self._caja_y_boton()
        boton.setEnabled(True)
        boton.setText("Actualizar lista")
        if not modelos:
            QMessageBox.information(self, "Modelos", "No se encontraron modelos disponibles.")
            return
        actual = valor(caja)
        for modelo in modelos:
            if caja.findData(modelo) < 0:
                caja.addItem(modelo, modelo)
        seleccionar(caja, actual if actual else modelos[0])
        if self._proveedor_lista == "ollama" and actual not in modelos:
            seleccionar(caja, modelos[0])
        caja.showPopup()

    @Slot(str)
    def _modelos_fallidos(self, mensaje: str) -> None:
        _, boton = self._caja_y_boton()
        boton.setEnabled(True)
        boton.setText("Actualizar lista")
        QMessageBox.warning(self, "Modelos", mensaje)
