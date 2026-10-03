"""Genera el ícono de la aplicación (PNG para la ventana e ICO para Windows)."""

from pathlib import Path

from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parent.parent
LADO = 512


def dibujar() -> Image.Image:
    imagen = Image.new("RGBA", (LADO, LADO), (0, 0, 0, 0))
    d = ImageDraw.Draw(imagen)
    # Fondo: degradado violeta en un cuadrado redondeado.
    degradado = Image.new("RGBA", (LADO, LADO))
    dg = ImageDraw.Draw(degradado)
    for y in range(LADO):
        t = y / (LADO - 1)
        color = (int(110 - 40 * t), int(90 - 45 * t), int(240 - 30 * t), 255)
        dg.line([(0, y), (LADO, y)], fill=color)
    mascara = Image.new("L", (LADO, LADO), 0)
    ImageDraw.Draw(mascara).rounded_rectangle([16, 16, LADO - 16, LADO - 16], radius=110, fill=255)
    imagen.paste(degradado, (0, 0), mascara)

    # Globo de conversación blanco.
    d.rounded_rectangle([104, 120, 408, 344], radius=56, fill=(255, 255, 255, 255))
    d.polygon([(170, 330), (150, 410), (250, 336)], fill=(255, 255, 255, 255))
    # Líneas de texto.
    for i, ancho in enumerate((210, 160, 120)):
        y = 176 + i * 50
        d.rounded_rectangle([150, y, 150 + ancho, y + 22], radius=11, fill=(91, 75, 219, 255))
    # Destello.
    cx, cy, r = 392, 128, 46
    d.polygon(
        [(cx, cy - r), (cx + 12, cy - 12), (cx + r, cy), (cx + 12, cy + 12),
         (cx, cy + r), (cx - 12, cy + 12), (cx - r, cy), (cx - 12, cy - 12)],
        fill=(255, 214, 90, 255),
    )
    return imagen


def main() -> None:
    imagen = dibujar()
    recursos = RAIZ / "posteos" / "recursos"
    recursos.mkdir(parents=True, exist_ok=True)
    imagen.resize((256, 256), Image.LANCZOS).save(recursos / "icono.png")
    imagen.save(RAIZ / "packaging" / "posteos.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("Íconos generados.")


if __name__ == "__main__":
    main()
