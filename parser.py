"""
Módulo de Extracción y Normalización con Expresiones Regulares (Fase 2 - ETL).
Extrae correos electrónicos válidos y números telefónicos de El Salvador
(series 7XXX-XXXX, 6XXX-XXXX, 2XXX-XXXX) normalizándolos al formato 503XXXXXXXX.
"""

import re
import unicodedata

from config import PALABRAS_EXCLUIDAS, REMITENTE_TELEFONO

# Patrón Regex para correos electrónicos válidos
PATRON_EMAIL = re.compile(
    r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,10}\b",
    re.IGNORECASE,
)

# Extensiones o dominios que suelen ser falsos positivos en HTML/texto
EXTENSIONES_IGNORADAS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".webp",
    ".css",
    ".js",
)

# Patrón Regex para números salvadoreños:
# Acepta prefijo opcional (+503, (503), 503) seguido de 8 dígitos que inicien con 2, 6 o 7,
# separados opcionalmente por espacio o guion tras los primeros 4 dígitos.
PATRON_TELEFONO_SV = re.compile(
    r"(?:(?:\+?503|\(\+?503\))[\s.-]*)?\b([267]\d{3})[\s.-]?(\d{4})\b"
)


def extraer_correos(texto: str) -> list[str]:
    """
    Extrae todos los correos electrónicos válidos desde un bloque de texto crudo.
    Normaliza en minúsculas, elimina duplicados y descarta falsos positivos.
    """
    if not texto:
        return []

    encontrados = PATRON_EMAIL.findall(texto)
    correos_limpios: list[str] = []
    vistos: set[str] = set()

    for correo in encontrados:
        correo_norm = correo.strip().lower().rstrip(".")
        if any(correo_norm.endswith(ext) for ext in EXTENSIONES_IGNORADAS):
            continue
        if correo_norm not in vistos:
            vistos.add(correo_norm)
            correos_limpios.append(correo_norm)

    return correos_limpios


def normalizar_telefono_sv(prefijo_4: str, sufijo_4: str) -> str:
    """Convierte las dos partes de 4 dígitos al formato internacional limpio 503XXXXXXXX."""
    solo_digitos = f"{prefijo_4}{sufijo_4}"
    return f"503{solo_digitos}"


def extraer_telefonos_sv(texto: str, solo_moviles: bool = False) -> list[str]:
    """
    Extrae números telefónicos salvadoreños (7XXX-XXXX, 6XXX-XXXX, 2XXX-XXXX)
    desde el texto crudo de la oferta y los normaliza al formato internacional 503XXXXXXXX.

    Si `solo_moviles=True`, filtra únicamente los que inician con 6 o 7 (aptos para WhatsApp).
    """
    if not texto:
        return []

    coincidencias = PATRON_TELEFONO_SV.findall(texto)
    telefonos_limpios: list[str] = []
    vistos: set[str] = set()
    propio_digitos = re.sub(r"\D", "", REMITENTE_TELEFONO)

    for bloque_1, bloque_2 in coincidencias:
        if solo_moviles and not bloque_1.startswith(("6", "7")):
            continue
        numero_normalizado = normalizar_telefono_sv(bloque_1, bloque_2)
        if propio_digitos and numero_normalizado == propio_digitos:
            continue
        if numero_normalizado not in vistos:
            vistos.add(numero_normalizado)
            telefonos_limpios.append(numero_normalizado)

    return telefonos_limpios


def extraer_contactos_oferta(descripcion_cruda: str) -> dict[str, list[str]]:
    """
    Analiza la descripción cruda de una vacante y retorna un diccionario con:
    - 'emails': lista de correos válidos
    - 'telefonos': todos los teléfonos salvadoreños normalizados (503XXXXXXXX)
    - 'whatsapp': teléfonos salvadoreños aptos para WhatsApp (móviles 6XXX/7XXX y fijos con WA)
    """
    return {
        "emails": extraer_correos(descripcion_cruda),
        "telefonos": extraer_telefonos_sv(descripcion_cruda, solo_moviles=False),
        "whatsapp": extraer_telefonos_sv(descripcion_cruda, solo_moviles=True),
    }


def _quitar_acentos(texto: str) -> str:
    """Normaliza un texto en minúsculas y sin tildes para comparaciones limpias."""
    nfkd = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def es_oferta_excluida(
    titulo: str,
    empresa: str = "",
    palabras_excluidas: list[str] | None = None,
) -> tuple[bool, str]:
    """
    Verifica si el título o nombre de la empresa pertenece a un sector excluido
    (por defecto el sector de cocina, restaurantes, gastronomía, etc.).
    Retorna (True, palabra_detectada) si debe descartarse, o (False, "") si es válida.
    """
    lista_excluidas = (
        palabras_excluidas if palabras_excluidas is not None else PALABRAS_EXCLUIDAS
    )
    texto_objetivo = _quitar_acentos(f"{titulo} {empresa}")

    for termino in lista_excluidas:
        termino_limpio = _quitar_acentos(termino.strip())
        if not termino_limpio:
            continue
        # Coincidencia por palabra completa o frase exacta
        patron = rf"\b{re.escape(termino_limpio)}\b"
        if re.search(patron, texto_objetivo):
            return True, termino.strip()

    return False, ""

