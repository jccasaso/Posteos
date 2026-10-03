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
USUARIO_KEYRING = "anthropic_api_key"
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
    modelo: str = "claude-opus-5-5"
    esfuerzo: str = "high"
    pais: str = "Argentina"
    variante: str = "Español neutro (Latinoamérica)"
    redes: list[str] = field(default_factory=lambda: list(REDES_POR_DEFECTO))
    investigar_web: bool = True
    marca_nombre: str = ""
    marca_sector: str = ""
    marca_descripcion: str = ""
    # Solo se usa si el sistema no tiene un almacén seguro de credenciales.
    api_key_respaldo: str = ""

    @classmethod
    def cargar(cls) -> "Configuracion":
        datos = _leer_json(carpeta_datos() / "configuracion.json", {})
        validos = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in datos.items() if k in validos})

    def guardar(self) -> None:
        _escribir_json(carpeta_datos() / "configuracion.json", asdict(self))

    # --- Clave de API -------------------------------------------------------

    def obtener_api_key(self) -> str:
        try:
            import keyring

            clave = keyring.get_password(SERVICIO_KEYRING, USUARIO_KEYRING)
            if clave:
                return clave
        except Exception:
            pass
        return self.api_key_respaldo or os.environ.get("ANTHROPIC_API_KEY", "")

    def guardar_api_key(self, clave: str) -> bool:
        """Guarda la clave en el almacén seguro del sistema. Devuelve False si tuvo que usar el archivo."""
        clave = clave.strip()
        try:
            import keyring

            if clave:
                keyring.set_password(SERVICIO_KEYRING, USUARIO_KEYRING, clave)
            else:
                try:
                    keyring.delete_password(SERVICIO_KEYRING, USUARIO_KEYRING)
                except Exception:
                    pass
            self.api_key_respaldo = ""
            self.guardar()
            return True
        except Exception:
            self.api_key_respaldo = clave
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
