"""Hoja de estilos de la aplicación."""

ACENTO = "#5B4BDB"
ACENTO_OSCURO = "#4535C4"

ESTILO = f"""
QWidget {{
    font-size: 10pt;
    color: #1F2330;
}}
QMainWindow, QWidget#fondo {{
    background: #F5F6FA;
}}
QTabWidget::pane {{
    border: 1px solid #DCDFE8;
    border-radius: 8px;
    background: #FFFFFF;
    top: -1px;
}}
QTabBar::tab {{
    background: transparent;
    padding: 9px 18px;
    margin-right: 2px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
    color: #5A6072;
}}
QTabBar::tab:selected {{
    background: #FFFFFF;
    color: {ACENTO};
    font-weight: 600;
    border: 1px solid #DCDFE8;
    border-bottom-color: #FFFFFF;
}}
QTabBar::tab:hover:!selected {{
    color: #1F2330;
}}
QGroupBox {{
    font-weight: 600;
    border: 1px solid #E3E6EE;
    border-radius: 8px;
    margin-top: 14px;
    padding: 12px 10px 10px 10px;
    background: #FFFFFF;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #3A3F52;
}}
QLineEdit, QPlainTextEdit, QTextEdit, QTextBrowser, QComboBox, QListWidget {{
    border: 1px solid #D5D9E3;
    border-radius: 6px;
    padding: 5px 7px;
    background: #FFFFFF;
    selection-background-color: {ACENTO};
    selection-color: #FFFFFF;
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QComboBox:focus {{
    border: 1px solid {ACENTO};
}}
QComboBox QAbstractItemView {{
    border: 1px solid #D5D9E3;
    selection-background-color: #ECEAFD;
    selection-color: #1F2330;
}}
QPushButton {{
    border: 1px solid #D5D9E3;
    border-radius: 6px;
    padding: 6px 14px;
    background: #FFFFFF;
}}
QPushButton:hover {{
    background: #F0F1F6;
}}
QPushButton:disabled {{
    color: #A0A5B5;
    background: #F3F4F8;
}}
QPushButton#principal {{
    background: {ACENTO};
    color: #FFFFFF;
    border: none;
    font-weight: 600;
    padding: 10px 18px;
    font-size: 11pt;
}}
QPushButton#principal:hover {{
    background: {ACENTO_OSCURO};
}}
QPushButton#principal:disabled {{
    background: #B9B3EE;
}}
QLabel#titulo {{
    font-size: 15pt;
    font-weight: 700;
    color: #1F2330;
}}
QLabel#subtitulo {{
    color: #6B7185;
}}
QLabel#etiquetaDato {{
    background: #ECEAFD;
    color: {ACENTO_OSCURO};
    border-radius: 10px;
    padding: 3px 10px;
    font-weight: 600;
}}
QLabel#contador {{
    color: #6B7185;
}}
QLabel#contadorExcedido {{
    color: #C62828;
    font-weight: 600;
}}
QLabel#vacio {{
    color: #8A90A2;
    font-size: 11pt;
}}
QProgressBar {{
    border: none;
    background: #E8E9F0;
    border-radius: 3px;
    max-height: 6px;
}}
QProgressBar::chunk {{
    background: {ACENTO};
    border-radius: 3px;
}}
QCheckBox {{
    spacing: 6px;
}}
QSplitter::handle {{
    background: transparent;
}}
QScrollArea {{
    border: none;
    background: transparent;
}}
"""
