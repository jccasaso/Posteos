"""Configuración persistente, clave de API, perfiles analizados e historial."""

from __future__ import annotations

import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime
from pathlib import Path
from typing import Any

from posteos import NOMBRE_APP
from posteos.opciones import REDES_POR_DEFECTO

SERVICIO_KEYRING = NOMBRE_APP
USUARIOS_KEYRING = {"claude": "anthropic_api_key", "gemini": "gemini_api_key"}
VARIABLES_ENTORNO = {"claude": ("ANTHROPIC_API_KEY",), "gemini": ("GEMINI_API_KEY", "GOOGLE_API_KEY")}
MAX_HISTORIAL = 200


def carpeta_datos() -> Path:
    """Carpeta de datos del usuario (por ejemplo %APPDATA%\\Posteos en Windows)."""
    personalizada = os.environ.get("POSTEOS_DATOS")
    if personalizada:
        base = Path(personalizada)
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / NOMBRE_APP
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / NOMBRE_APP
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / NOMBRE_APP.lower()
    base.mkdir(parents=True, exist_ok=True)
    return base


def _leer_json(ruta: Path, defecto: Any) -> Any:
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defecto


def _escribir_json(ruta: Path, datos: Any) -> None:
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    temporal.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    temporal.replace(ruta)


@dataclass
class Configuracion:
    proveedor: str = "gemini"  # gemini | ollama | claude
    modelo_gemini: str = "gemini-flash-latest"
    modelo_ollama: str = "gemma3:12b"
    ollama_url: str = "http://localhost:11434"
    modelo_claude: str = "claude-opus-5-5"
    esfuerzo: str = "high"  # solo Claude
    pais: str = "Argentina"
    variante: str = "Español neutro (Latinoamérica)"
    redes: list[str] = field(default_factory=lambda: list(REDES_POR_DEFECTO))
    investigar_web: bool = True
    marca_nombre: str = ""
    marca_sector: str = ""
    marca_descripcion: str = ""
    # Solo se usan si el sistema no tiene un almacén seguro de credenciales.
    claves_respaldo: dict[str, str] = field(default_factory=dict)

    @classmethod
    def cargar(cls) -> "Configuracion":
        datos = _leer_json(carpeta_datos() / "configuracion.json", {})
        # Compatibilidad con la versión 1.0, que solo usaba Claude.
        if "modelo" in datos and "modelo_claude" not in datos:
            datos["modelo_claude"] = datos["modelo"]
        if datos.get("api_key_respaldo"):
            datos.setdefault("claves_respaldo", {})["claude"] = datos["api_key_respaldo"]
        validos = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in datos.items() if k in validos})

    def guardar(self) -> None:
        _escribir_json(carpeta_datos() / "configuracion.json", asdict(self))

    @property
    def modelo_actual(self) -> str:
        return {"claude": self.modelo_claude, "ollama": self.modelo_ollama}.get(self.proveedor, self.modelo_gemini)

    def proveedor_listo(self) -> bool:
        """Ollama no necesita clave; Gemini y Claude sí."""
        return self.proveedor == "ollama" or bool(self.obtener_api_key(self.proveedor))

    # --- Claves de API --------------------------------------------------------

    def obtener_api_key(self, proveedor: str) -> str:
        usuario = USUARIOS_KEYRING.get(proveedor)
        if not usuario:
            return ""
        try:
            import keyring

            clave = keyring.get_password(SERVICIO_KEYRING, usuario)
            if clave:
                return clave
        except Exception:
            pass
        if self.claves_respaldo.get(proveedor):
            return self.claves_respaldo[proveedor]
        return next((os.environ[v] for v in VARIABLES_ENTORNO.get(proveedor, ()) if os.environ.get(v)), "")

    def guardar_api_key(self, proveedor: str, clave: str) -> bool:
        """Guarda la clave en el almacén seguro del sistema. Devuelve False si tuvo que usar el archivo."""
        usuario = USUARIOS_KEYRING[proveedor]
        clave = clave.strip()
        try:
            import keyring

            if clave:
                keyring.set_password(SERVICIO_KEYRING, usuario, clave)
            else:
                try:
                    keyring.delete_password(SERVICIO_KEYRING, usuario)
                except Exception:
                    pass
            self.claves_respaldo.pop(proveedor, None)
            self.guardar()
            return True
        except Exception:
            if clave:
                self.claves_respaldo[proveedor] = clave
            else:
                self.claves_respaldo.pop(proveedor, None)
            self.guardar()
            return False


# --- Perfiles de cuentas analizadas ------------------------------------------


@dataclass
class PerfilAnalizado:
    nombre: str
    url: str
    red: str
    analisis: str
    fecha: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M"))
    id: str = field(default_factory=lambda: uuid.uuid4().hex)


def cargar_perfiles() -> list[PerfilAnalizado]:
    datos = _leer_json(carpeta_datos() / "perfiles.json", [])
    validos = {f.name for f in fields(PerfilAnalizado)}
    perfiles = []
    for item in datos:
        try:
            perfiles.append(PerfilAnalizado(**{k: v for k, v in item.items() if k in validos}))
        except TypeError:
            continue
    return perfiles


def guardar_perfiles(perfiles: list[PerfilAnalizado]) -> None:
    _escribir_json(carpeta_datos() / "perfiles.json", [asdict(p) for p in perfiles])


# --- Historial de publicaciones generadas ------------------------------------


def cargar_historial() -> list[dict]:
    datos = _leer_json(carpeta_datos() / "historial.json", [])
    return datos if isinstance(datos, list) else []


def agregar_al_historial(entrada: dict) -> list[dict]:
    historial = cargar_historial()
    historial.insert(0, {"fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), **entrada})
    del historial[MAX_HISTORIAL:]
    _escribir_json(carpeta_datos() / "historial.json", historial)
    return historial


def borrar_historial() -> None:
    _escribir_json(carpeta_datos() / "historial.json", [])
