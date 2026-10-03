"""Preparación de imágenes y videos adjuntos para enviarlos a la IA."""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, ImageOps

EXT_IMAGEN = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
EXT_VIDEO = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".wmv", ".3gp"}

LADO_MAXIMO = 1568  # lado máximo recomendado para visión, en píxeles
FOTOGRAMAS_POR_VIDEO = 6
MAX_IMAGENES_TOTALES = 20


class ErrorAdjunto(Exception):
    pass


@dataclass
class Adjunto:
    ruta: Path
    tipo: str  # "imagen" o "video"
    descripcion: str  # metadatos legibles (resolución, duración...)
    imagenes: list[Image.Image] = field(default_factory=list, repr=False)
    duracion: float = 0.0  # segundos (solo videos)

    @property
    def nombre(self) -> str:
        return self.ruta.name

    def miniatura(self, lado: int = 160) -> Image.Image | None:
        if not self.imagenes:
            return None
        copia = self.imagenes[0].copy()
        copia.thumbnail((lado, lado))
        return copia


def tipo_de_archivo(ruta: Path) -> str | None:
    ext = ruta.suffix.lower()
    if ext in EXT_IMAGEN:
        return "imagen"
    if ext in EXT_VIDEO:
        return "video"
    return None


def _ajustar(imagen: Image.Image) -> Image.Image:
    imagen = ImageOps.exif_transpose(imagen)
    if imagen.mode not in ("RGB", "L"):
        fondo = Image.new("RGB", imagen.size, (255, 255, 255))
        convertida = imagen.convert("RGBA")
        fondo.paste(convertida, mask=convertida.split()[-1])
        imagen = fondo
    elif imagen.mode == "L":
        imagen = imagen.convert("RGB")
    imagen.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
    return imagen


def cargar_imagen(ruta: Path) -> Adjunto:
    try:
        with Image.open(ruta) as original:
            ancho, alto = original.size
            original.seek(0)
            imagen = _ajustar(original.copy())
    except (OSError, ValueError) as e:
        raise ErrorAdjunto(f"No se pudo abrir la imagen «{ruta.name}»: {e}") from e
    orientacion = "vertical" if alto > ancho else "horizontal" if ancho > alto else "cuadrada"
    descripcion = f"Imagen {ancho}×{alto} px ({orientacion}, proporción {_proporcion(ancho, alto)})"
    return Adjunto(ruta=ruta, tipo="imagen", descripcion=descripcion, imagenes=[imagen])


def cargar_video(ruta: Path, fotogramas: int = FOTOGRAMAS_POR_VIDEO) -> Adjunto:
    try:
        import cv2
    except ImportError as e:
        raise ErrorAdjunto("No está disponible el módulo de video (opencv).") from e

    captura = cv2.VideoCapture(str(ruta))
    if not captura.isOpened():
        raise ErrorAdjunto(f"No se pudo abrir el video «{ruta.name}».")
    try:
        total = int(captura.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(captura.get(cv2.CAP_PROP_FPS) or 0)
        ancho = int(captura.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        alto = int(captura.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        duracion = total / fps if fps > 0 and total > 0 else 0.0

        # Fotogramas repartidos a lo largo del video, evitando el primero y el último exactos.
        if total > 0:
            posiciones = [int(total * (i + 0.5) / fotogramas) for i in range(fotogramas)]
        else:
            posiciones = [None] * fotogramas
        imagenes: list[Image.Image] = []
        for posicion in posiciones:
            if posicion is not None:
                captura.set(cv2.CAP_PROP_POS_FRAMES, posicion)
            ok, cuadro = captura.read()
            if not ok:
                continue
            rgb = cv2.cvtColor(cuadro, cv2.COLOR_BGR2RGB)
            imagenes.append(_ajustar(Image.fromarray(rgb)))
    finally:
        captura.release()

    if not imagenes:
        raise ErrorAdjunto(f"No se pudieron extraer fotogramas del video «{ruta.name}».")
    orientacion = "vertical" if alto > ancho else "horizontal" if ancho > alto else "cuadrado"
    descripcion = (
        f"Video {ancho}×{alto} px ({orientacion}, proporción {_proporcion(ancho, alto)}), "
        f"duración {_formatear_duracion(duracion)}, {fps:.0f} fps."
    )
    return Adjunto(ruta=ruta, tipo="video", descripcion=descripcion, imagenes=imagenes, duracion=duracion)


def cargar_adjunto(ruta: str | Path) -> Adjunto:
    ruta = Path(ruta)
    if not ruta.is_file():
        raise ErrorAdjunto(f"No se encontró el archivo «{ruta}».")
    tipo = tipo_de_archivo(ruta)
    if tipo == "imagen":
        return cargar_imagen(ruta)
    if tipo == "video":
        return cargar_video(ruta)
    raise ErrorAdjunto(f"Formato no admitido: «{ruta.suffix}». Use imágenes o videos.")


def imagen_a_jpeg(imagen: Image.Image) -> bytes:
    buffer = io.BytesIO()
    imagen.save(buffer, format="JPEG", quality=85, optimize=True)
    return buffer.getvalue()


def repartir_imagenes(adjuntos: list[Adjunto]) -> list[tuple[Adjunto, list[Image.Image]]]:
    """Imágenes a enviar por adjunto, respetando el máximo total (en videos, fotogramas distribuidos)."""
    resultado = []
    restantes = MAX_IMAGENES_TOTALES
    for adjunto in adjuntos:
        imagenes = adjunto.imagenes[: max(restantes, 0)]
        if adjunto.tipo == "video" and imagenes and len(imagenes) < len(adjunto.imagenes):
            paso = len(adjunto.imagenes) / len(imagenes)
            imagenes = [adjunto.imagenes[int(i * paso)] for i in range(len(imagenes))]
        resultado.append((adjunto, imagenes))
        restantes -= len(imagenes)
    return resultado


def describir_adjunto(numero: int, adjunto: Adjunto) -> str:
    return f"Adjunto {numero}: «{adjunto.nombre}» — {adjunto.descripcion}"


def _proporcion(ancho: int, alto: int) -> str:
    if not ancho or not alto:
        return "desconocida"
    conocidas = {"1:1": 1.0, "4:5": 0.8, "3:4": 0.75, "9:16": 0.5625, "16:9": 1.7778, "4:3": 1.3333, "3:2": 1.5, "2:3": 0.6667}
    relacion = ancho / alto
    nombre, valor = min(conocidas.items(), key=lambda kv: abs(kv[1] - relacion))
    return nombre if abs(valor - relacion) < 0.03 else f"{relacion:.2f}:1"


def _formatear_duracion(segundos: float) -> str:
    if segundos <= 0:
        return "desconocida"
    minutos, seg = divmod(int(round(segundos)), 60)
    return f"{minutos} min {seg} s" if minutos else f"{seg} s"
