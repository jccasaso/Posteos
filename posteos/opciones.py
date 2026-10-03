"""Catálogo de redes sociales, buenas prácticas y opciones de los desplegables."""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import quote


@dataclass(frozen=True)
class RedSocial:
    clave: str
    nombre: str
    limite_caracteres: int
    caracteres_visibles: int  # texto visible antes del "ver más"
    formatos: tuple[str, ...]
    buenas_practicas: tuple[str, ...]
    url_publicar: str  # admite {texto} cuando la red permite precargar el texto
    precarga_texto: bool = False
    dominios: tuple[str, ...] = field(default_factory=tuple)

    def enlace_publicacion(self, texto: str) -> str:
        if self.precarga_texto:
            return self.url_publicar.format(texto=quote(texto))
        return self.url_publicar


REDES: dict[str, RedSocial] = {
    "linkedin": RedSocial(
        clave="linkedin",
        nombre="LinkedIn",
        limite_caracteres=3000,
        caracteres_visibles=210,
        formatos=("Texto + imagen", "Carrusel / documento PDF", "Video nativo", "Encuesta", "Artículo", "Newsletter"),
        buenas_practicas=(
            "El gancho debe estar en las 2 primeras líneas (unos 210 caracteres visibles antes de «ver más»).",
            "Párrafos de 1 a 2 líneas con espacios en blanco para facilitar la lectura en móvil.",
            "Aportar valor profesional: aprendizajes, datos, experiencias propias y opinión fundamentada.",
            "Cerrar con una pregunta abierta que invite a comentar; los comentarios largos pesan mucho en el algoritmo.",
            "3 a 5 hashtags específicos al final; evitar etiquetar personas que no vayan a interactuar.",
            "Los enlaces externos en el cuerpo reducen el alcance: sugerir colocarlos en el primer comentario.",
            "Los carruseles en PDF y los videos verticales nativos suelen tener más permanencia y alcance.",
            "Responder los comentarios durante la primera hora para extender la distribución.",
        ),
        url_publicar="https://www.linkedin.com/feed/?shareActive=true&text={texto}",
        precarga_texto=True,
        dominios=("linkedin.com", "lnkd.in"),
    ),
    "instagram": RedSocial(
        clave="instagram",
        nombre="Instagram",
        limite_caracteres=2200,
        caracteres_visibles=125,
        formatos=("Reel (9:16)", "Carrusel (4:5 o 3:4)", "Imagen única", "Historia (9:16)", "Colaboración", "Transmisión en vivo"),
        buenas_practicas=(
            "Los primeros 125 caracteres del texto deben enganchar; el resto queda oculto tras «más».",
            "El contenido visual manda: los primeros 1 a 3 segundos del Reel definen la retención.",
            "Usar texto en pantalla y subtítulos: gran parte del contenido se ve sin sonido.",
            "Pocos hashtags muy relevantes (3 a 5) y palabras clave en el texto para el buscador de Instagram.",
            "Los carruseles favorecen los «guardados» y los Reels el alcance a no seguidores.",
            "Llamadas a la acción de guardar, compartir por DM o comentar una palabra clave.",
            "Formato vertical: 4:5 o 3:4 para el feed, 9:16 para Reels e Historias.",
            "Complementar con Historias (encuestas, stickers) para activar a la comunidad actual.",
        ),
        url_publicar="https://www.instagram.com/",
        dominios=("instagram.com", "instagr.am"),
    ),
    "facebook": RedSocial(
        clave="facebook",
        nombre="Facebook",
        limite_caracteres=63206,
        caracteres_visibles=480,
        formatos=("Reel", "Video nativo", "Imagen", "Álbum / carrusel", "Publicación en grupo", "Evento", "Transmisión en vivo"),
        buenas_practicas=(
            "Los textos breves (40 a 120 caracteres) o historias personales bien narradas generan más interacción.",
            "Los Reels y el video nativo tienen prioridad de distribución frente a los enlaces externos.",
            "Hacer preguntas sencillas que inviten a responder y a etiquetar a otras personas.",
            "Compartir también en grupos relevantes cuando las normas lo permitan.",
            "Uno o dos hashtags como máximo; en Facebook aportan poco alcance.",
            "Contenido emocional, local o comunitario funciona mejor que el puramente promocional.",
        ),
        url_publicar="https://www.facebook.com/",
        dominios=("facebook.com", "fb.com", "fb.watch", "m.facebook.com"),
    ),
    "x": RedSocial(
        clave="x",
        nombre="X (Twitter)",
        limite_caracteres=280,
        caracteres_visibles=280,
        formatos=("Post de texto", "Post con imagen", "Hilo", "Video", "Encuesta", "Espacio en vivo"),
        buenas_practicas=(
            "Máximo 280 caracteres por post en cuentas sin suscripción: ir directo al punto.",
            "Una idea fuerte por post; los hilos funcionan para desarrollar temas con más profundidad.",
            "Las imágenes y videos aumentan notablemente la interacción frente al texto solo.",
            "1 o 2 hashtags como máximo; más hashtags reducen la interacción.",
            "Opiniones claras, datos concretos y actualidad generan respuestas y reposts.",
            "Evitar enlaces externos en el primer post: colocarlos en una respuesta.",
        ),
        url_publicar="https://x.com/intent/post?text={texto}",
        precarga_texto=True,
        dominios=("x.com", "twitter.com", "mobile.twitter.com"),
    ),
    "whatsapp": RedSocial(
        clave="whatsapp",
        nombre="WhatsApp",
        limite_caracteres=4096,
        caracteres_visibles=700,
        formatos=("Estado (24 h)", "Canal de WhatsApp", "Lista de difusión", "Mensaje a grupo", "Catálogo / WhatsApp Business"),
        buenas_practicas=(
            "Mensajes breves, personales y escaneables: frases cortas y viñetas.",
            "Usar el formato propio de WhatsApp: *negrita*, _cursiva_, ~tachado~ y listas.",
            "Una sola llamada a la acción clara (responder, hacer clic, reservar, comprar).",
            "En Estados: imagen o video vertical con texto superpuesto corto; se borran a las 24 h.",
            "En Canales: contenido exclusivo, encuestas y avisos; no saturar con muchos envíos diarios.",
            "Respetar la privacidad: enviar solo a contactos que aceptaron recibir mensajes.",
        ),
        url_publicar="https://wa.me/?text={texto}",
        precarga_texto=True,
        dominios=("whatsapp.com", "wa.me", "chat.whatsapp.com"),
    ),
    "tiktok": RedSocial(
        clave="tiktok",
        nombre="TikTok",
        limite_caracteres=4000,
        caracteres_visibles=100,
        formatos=("Video vertical (9:16)", "Carrusel de fotos", "Video con dueto / stitch", "Transmisión en vivo", "Historia"),
        buenas_practicas=(
            "Gancho en el primer segundo: pregunta, afirmación sorprendente o imagen impactante.",
            "Videos verticales nativos, con texto en pantalla y subtítulos.",
            "Usar sonidos en tendencia cuando encajen con la marca.",
            "La descripción funciona como buscador: incluir palabras clave y 3 a 5 hashtags.",
            "Mostrar personas reales, detrás de escena y contenido auténtico más que producciones muy pulidas.",
            "Animar a comentar con preguntas; responder comentarios con videos.",
        ),
        url_publicar="https://www.tiktok.com/upload",
        dominios=("tiktok.com", "vm.tiktok.com"),
    ),
    "threads": RedSocial(
        clave="threads",
        nombre="Threads",
        limite_caracteres=500,
        caracteres_visibles=500,
        formatos=("Post de texto", "Post con imagen o video", "Hilo", "Encuesta"),
        buenas_practicas=(
            "Tono conversacional y cercano: preguntas, opiniones y debates.",
            "Máximo 500 caracteres por post; usar hilos para desarrollar ideas.",
            "Una sola etiqueta de tema (topic tag) por publicación.",
            "Responder y conversar en los comentarios aumenta la distribución.",
        ),
        url_publicar="https://www.threads.net/intent/post?text={texto}",
        precarga_texto=True,
        dominios=("threads.net", "threads.com"),
    ),
    "youtube": RedSocial(
        clave="youtube",
        nombre="YouTube",
        limite_caracteres=5000,
        caracteres_visibles=150,
        formatos=("Short (vertical, hasta 3 min)", "Video largo", "Publicación de comunidad", "Transmisión en vivo"),
        buenas_practicas=(
            "Título de hasta 100 caracteres (idealmente menos de 60) con la palabra clave al principio.",
            "Los primeros 150 caracteres de la descripción aparecen en búsquedas: incluir la propuesta de valor.",
            "Miniatura con rostro, contraste alto y 3 a 5 palabras como máximo.",
            "Retención: gancho en los primeros 5 segundos y promesa clara del contenido.",
            "Agregar capítulos, enlaces y 3 a 5 hashtags en la descripción.",
            "Los Shorts sirven para atraer audiencia nueva hacia los videos largos.",
        ),
        url_publicar="https://studio.youtube.com/",
        dominios=("youtube.com", "youtu.be", "m.youtube.com"),
    ),
}

REDES_POR_DEFECTO = ("linkedin", "instagram", "facebook", "x")

OBJETIVOS = (
    "Aumentar alcance y visualizaciones",
    "Generar interacción (comentarios y reacciones)",
    "Ganar seguidores",
    "Llevar tráfico a un sitio web",
    "Vender un producto o servicio",
    "Captar contactos o clientes potenciales",
    "Posicionar marca personal",
    "Educar o informar",
    "Anunciar un evento o lanzamiento",
    "Fidelizar a la comunidad",
)

TONOS = (
    "Automático (según la red y la cuenta)",
    "Profesional",
    "Cercano y amigable",
    "Inspirador / motivacional",
    "Divertido / humorístico",
    "Educativo / didáctico",
    "Persuasivo / vendedor",
    "Emotivo / storytelling",
    "Formal / institucional",
    "Provocador / disruptivo",
)

PUBLICOS = (
    "Público general",
    "Profesionales y empresas (B2B)",
    "Emprendedores y pymes",
    "Jóvenes (18 a 24 años)",
    "Adultos (25 a 44 años)",
    "Mayores de 45 años",
    "Estudiantes",
    "Madres y padres",
    "Clientes actuales",
)

VARIANTES_ESPANOL = (
    "Español neutro (Latinoamérica)",
    "Español de Argentina (voseo)",
    "Español de España",
    "Español de México",
    "Español de Colombia",
    "Español de Chile",
    "Español de Perú",
    "Español de Uruguay (voseo)",
    "Español de Venezuela",
    "Español de EE. UU. (hispano)",
)

LONGITUDES = (
    "Automática (óptima para cada red)",
    "Corta",
    "Media",
    "Larga",
)

EMOJIS = (
    "Automático",
    "Ninguno",
    "Pocos",
    "Moderados",
    "Muchos",
)

HASHTAGS = (
    "Automático (según buenas prácticas)",
    "Ninguno",
    "Pocos (1 a 3)",
    "Moderados (3 a 5)",
    "Muchos (6 a 10)",
)

LLAMADAS_A_LA_ACCION = (
    "Automática",
    "Comentar",
    "Compartir",
    "Guardar la publicación",
    "Visitar un enlace",
    "Escribir por mensaje directo",
    "Comprar",
    "Registrarse o inscribirse",
    "Seguir la cuenta",
    "Sin llamada a la acción",
)

# (país, zona horaria IANA)
PAISES: tuple[tuple[str, str], ...] = (
    ("Argentina", "America/Argentina/Buenos_Aires"),
    ("Bolivia", "America/La_Paz"),
    ("Chile", "America/Santiago"),
    ("Colombia", "America/Bogota"),
    ("Costa Rica", "America/Costa_Rica"),
    ("Ecuador", "America/Guayaquil"),
    ("El Salvador", "America/El_Salvador"),
    ("España", "Europe/Madrid"),
    ("Estados Unidos (hora del Este)", "America/New_York"),
    ("Estados Unidos (hora del Pacífico)", "America/Los_Angeles"),
    ("Guatemala", "America/Guatemala"),
    ("Honduras", "America/Tegucigalpa"),
    ("México", "America/Mexico_City"),
    ("Nicaragua", "America/Managua"),
    ("Panamá", "America/Panama"),
    ("Paraguay", "America/Asuncion"),
    ("Perú", "America/Lima"),
    ("Puerto Rico", "America/Puerto_Rico"),
    ("República Dominicana", "America/Santo_Domingo"),
    ("Uruguay", "America/Montevideo"),
    ("Venezuela", "America/Caracas"),
    ("Internacional (varios países)", "UTC"),
)

PROVEEDORES: tuple[tuple[str, str], ...] = (
    ("gemini", "Google Gemini — gratis con límites diarios (recomendado)"),
    ("ollama", "Ollama — IA local en esta PC, gratis y privada"),
    ("claude", "Claude de Anthropic — de pago, máxima calidad"),
)

MODELOS_GEMINI: tuple[tuple[str, str], ...] = (
    ("gemini-flash-latest", "Gemini Flash más reciente (recomendado)"),
    ("gemini-flash-lite-latest", "Gemini Flash-Lite más reciente (más rápido y con más cuota gratuita)"),
    ("gemini-2.5-flash", "Gemini 2.5 Flash"),
)

# Modelos locales con visión sugeridos para Ollama (se pueden escribir otros).
MODELOS_OLLAMA: tuple[str, ...] = ("gemma3:12b", "gemma3:4b", "gemma3:27b", "qwen2.5vl:7b", "llama3.2-vision")

MODELOS_CLAUDE: tuple[tuple[str, str], ...] = (
    ("claude-opus-5-5", "Claude Opus 5.5 (máxima calidad)"),
    ("claude-sonnet-5-5", "Claude Sonnet 5.5 (más rápido y económico)"),
)

ESFUERZOS: tuple[tuple[str, str], ...] = (
    ("low", "Bajo (más rápido)"),
    ("medium", "Medio"),
    ("high", "Alto (recomendado)"),
    ("xhigh", "Muy alto"),
    ("max", "Máximo (más lento)"),
)


def zona_horaria(pais: str) -> str:
    for nombre, zona in PAISES:
        if nombre == pais:
            return zona
    return "UTC"
