"""Pestaña «Crear publicación»: de una idea (y adjuntos) a posts listos para cada red."""

from __future__ import annotations

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
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from posteos import opciones
from posteos.config import agregar_al_historial
from posteos.exportar import resultado_a_markdown
from posteos.ia import MotorIA, ResultadoGeneracion, SolicitudPost
from posteos.ui.adjuntos import SelectorAdjuntos
from posteos.ui.comunes import Contexto, IndicadorProgreso, combo, seleccionar, valor
from posteos.ui.resultados import VistaResultados


class PestanaCrear(QWidget):
    def __init__(self, ctx: Contexto, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ctx = ctx
        self._motor: MotorIA | None = None
        self._idea_en_curso = ""
        config = ctx.config

        # --- Idea y adjuntos ---
        self.idea = QPlainTextEdit()
        self.idea.setPlaceholderText(
            "Escriba aquí la idea, el mensaje o la novedad que quiere publicar.\n\n"
            "Ejemplo: «Este sábado abrimos la nueva sucursal en el centro con 20 % de descuento "
            "en toda la tienda y degustación gratis.»"
        )
        self.idea.setMinimumHeight(120)
        self.adjuntos = SelectorAdjuntos()

        grupo_idea = QGroupBox("1. Su idea")
        diseno_idea = QVBoxLayout(grupo_idea)
        diseno_idea.addWidget(self.idea)
        diseno_idea.addWidget(self.adjuntos)

        # --- Redes ---
        grupo_redes = QGroupBox("2. Redes sociales")
        rejilla = QGridLayout(grupo_redes)
        self.casillas: dict[str, QCheckBox] = {}
        for indice, (clave, red) in enumerate(opciones.REDES.items()):
            casilla = QCheckBox(red.nombre)
            casilla.setChecked(clave in config.redes)
            self.casillas[clave] = casilla
            rejilla.addWidget(casilla, indice // 4, indice % 4)

        # --- Opciones ---
        grupo_opciones = QGroupBox("3. Configuración de la publicación")
        formulario = QFormLayout(grupo_opciones)
        formulario.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.objetivo = combo(opciones.OBJETIVOS)
        self.tono = combo(opciones.TONOS)
        self.publico = combo(opciones.PUBLICOS, editable=True)
        self.publico.setToolTip("Puede elegir una opción o escribir su propio público.")
        self.variante = combo(opciones.VARIANTES_ESPANOL, config.variante)
        self.longitud = combo(opciones.LONGITUDES)
        self.emojis = combo(opciones.EMOJIS)
        self.hashtags = combo(opciones.HASHTAGS)
        self.cta = combo(opciones.LLAMADAS_A_LA_ACCION)
        self.pais = combo([p for p, _ in opciones.PAISES], config.pais)
        self.perfil = combo([])
        self.extra = QLineEdit()
        self.extra.setPlaceholderText("Opcional: incluir el precio, mencionar a @alguien, evitar ciertas palabras…")
        self.investigar = QCheckBox("Investigar en la web el mejor día, horario y formato para publicar")
        self.investigar.setChecked(config.investigar_web)

        formulario.addRow("Objetivo:", self.objetivo)
        formulario.addRow("Tono:", self.tono)
        formulario.addRow("Público:", self.publico)
        formulario.addRow("Idioma:", self.variante)
        formulario.addRow("Longitud:", self.longitud)
        formulario.addRow("Emojis:", self.emojis)
        formulario.addRow("Hashtags:", self.hashtags)
        formulario.addRow("Llamada a la acción:", self.cta)
        formulario.addRow("País (horarios):", self.pais)
        formulario.addRow("Imitar el estilo de:", self.perfil)
        formulario.addRow("Indicaciones extra:", self.extra)
        formulario.addRow(self.investigar)

        # --- Acciones ---
        self.boton_generar = QPushButton("✨ Generar publicaciones")
        self.boton_generar.setObjectName("principal")
        self.boton_generar.clicked.connect(self.generar)
        self.boton_cancelar = QPushButton("Cancelar")
        self.boton_cancelar.clicked.connect(self.cancelar)
        self.boton_cancelar.hide()
        self.boton_nueva = QPushButton("Nueva idea")
        self.boton_nueva.clicked.connect(self.nueva_idea)
        acciones = QHBoxLayout()
        acciones.addWidget(self.boton_generar, 1)
        acciones.addWidget(self.boton_cancelar)
        acciones.addWidget(self.boton_nueva)
        self.progreso = IndicadorProgreso()

        panel = QWidget()
        panel.setObjectName("fondo")
        diseno_panel = QVBoxLayout(panel)
        diseno_panel.addWidget(grupo_idea)
        diseno_panel.addWidget(grupo_redes)
        diseno_panel.addWidget(grupo_opciones)
        diseno_panel.addStretch()
        desplazable = QScrollArea()
        desplazable.setWidgetResizable(True)
        desplazable.setWidget(panel)
        desplazable.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        izquierda = QWidget()
        diseno_izq = QVBoxLayout(izquierda)
        diseno_izq.setContentsMargins(0, 0, 0, 0)
        diseno_izq.addWidget(desplazable, 1)
        diseno_izq.addLayout(acciones)
        diseno_izq.addWidget(self.progreso)

        self.resultados = VistaResultados()

        divisor = QSplitter(Qt.Orientation.Horizontal)
        divisor.addWidget(izquierda)
        divisor.addWidget(self.resultados)
        divisor.setStretchFactor(0, 2)
        divisor.setStretchFactor(1, 3)
        divisor.setSizes([520, 760])

        diseno = QVBoxLayout(self)
        diseno.setContentsMargins(10, 10, 10, 10)
        diseno.addWidget(divisor)

        self.actualizar_perfiles()
        ctx.avisos.perfiles_cambiados.connect(self.actualizar_perfiles)
        ctx.avisos.configuracion_cambiada.connect(self.aplicar_configuracion)

    # --- Perfiles y configuración ---

    @Slot()
    def actualizar_perfiles(self) -> None:
        actual = self.perfil.currentData()
        self.perfil.clear()
        self.perfil.addItem("Ninguna (estilo propio)", None)
        for perfil in self.ctx.perfiles:
            self.perfil.addItem(perfil.nombre, perfil.id)
        if actual:
            seleccionar(self.perfil, actual)

    @Slot()
    def aplicar_configuracion(self) -> None:
        seleccionar(self.variante, self.ctx.config.variante)
        seleccionar(self.pais, self.ctx.config.pais)
        self.investigar.setChecked(self.ctx.config.investigar_web)

    def usar_perfil(self, identificador: str) -> None:
        seleccionar(self.perfil, identificador)
        perfil = self.ctx.perfil(identificador)
        if perfil and perfil.red in self.casillas:
            self.casillas[perfil.red].setChecked(True)
        self.idea.setFocus()

    # --- Generación ---

    def _solicitud(self) -> SolicitudPost:
        config = self.ctx.config
        marca = "\n".join(
            f"{etiqueta}: {texto}"
            for etiqueta, texto in (
                ("Nombre", config.marca_nombre),
                ("Sector", config.marca_sector),
                ("Descripción", config.marca_descripcion),
            )
            if texto.strip()
        )
        perfil_id = self.perfil.currentData()
        return SolicitudPost(
            idea=self.idea.toPlainText(),
            redes=[clave for clave, casilla in self.casillas.items() if casilla.isChecked()],
            objetivo=valor(self.objetivo),
            tono=valor(self.tono),
            publico=valor(self.publico) or "Público general",
            variante=valor(self.variante),
            longitud=valor(self.longitud),
            emojis=valor(self.emojis),
            hashtags=valor(self.hashtags),
            llamada_a_la_accion=valor(self.cta),
            pais=valor(self.pais),
            marca=marca,
            adjuntos=list(self.adjuntos.adjuntos),
            perfil=self.ctx.perfil(perfil_id) if perfil_id else None,
            investigar_web=self.investigar.isChecked(),
            instrucciones_extra=self.extra.text(),
        )

    @Slot()
    def generar(self) -> None:
        solicitud = self._solicitud()
        if not solicitud.idea.strip() and not solicitud.adjuntos:
            QMessageBox.warning(self, "Falta la idea", "Escriba una idea o adjunte una imagen o un video.")
            return
        if not solicitud.redes:
            QMessageBox.warning(self, "Faltan redes", "Seleccione al menos una red social.")
            return
        api_key = self.ctx.config.obtener_api_key()
        if not api_key:
            self.ctx.avisos.ir_a_configuracion.emit("Para generar publicaciones primero cargue su clave de API.")
            return

        config = self.ctx.config
        self._idea_en_curso = solicitud.idea

        def tarea(progreso, _parcial) -> ResultadoGeneracion:
            self._motor = MotorIA(api_key, config.modelo, config.esfuerzo, progreso=progreso)
            return self._motor.generar_posts(solicitud)

        self._en_curso(True)
        self.progreso.iniciar("Preparando…")
        self.ctx.gestor.lanzar(tarea, self._al_terminar, self._al_fallar, self.progreso.informar)

    @Slot()
    def cancelar(self) -> None:
        if self._motor:
            self._motor.cancelar()
            self.progreso.informar("Cancelando…")

    @Slot(object)
    def _al_terminar(self, resultado: ResultadoGeneracion) -> None:
        self._en_curso(False)
        cantidad = len(resultado.posts.posts)
        self.progreso.detener(f"✅ Listo: {cantidad} publicación(es) generada(s).")
        self.resultados.mostrar(resultado, self._idea_en_curso)
        agregar_al_historial(
            {
                "idea": self._idea_en_curso,
                "redes": [p.red for p in resultado.posts.posts],
                "markdown": resultado_a_markdown(resultado, self._idea_en_curso),
            }
        )
        self.ctx.avisos.historial_cambiado.emit()

    @Slot(str)
    def _al_fallar(self, mensaje: str) -> None:
        self._en_curso(False)
        self.progreso.detener("⚠ " + mensaje)
        if mensaje != "Operación cancelada.":
            QMessageBox.warning(self, "No se pudieron generar las publicaciones", mensaje)

    def _en_curso(self, activo: bool) -> None:
        self.boton_generar.setEnabled(not activo)
        self.boton_generar.setText("Generando…" if activo else "✨ Generar publicaciones")
        self.boton_cancelar.setVisible(activo)
        self.boton_nueva.setEnabled(not activo)
        if not activo:
            self._motor = None

    @Slot()
    def nueva_idea(self) -> None:
        self.idea.clear()
        self.extra.clear()
        self.adjuntos.limpiar()
        self.resultados.limpiar()
        self.progreso.detener()
        self.idea.setFocus()
