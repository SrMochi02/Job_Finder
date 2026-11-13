"""
Módulo de Extracción, Normalización y Afinidad de Perfil (Fase 2 - ETL).
Extrae correos electrónicos, teléfonos salvadoreños (503XXXXXXXX), metadatos de la empresa
y evalúa si la vacante es accesible y acorde a la experiencia del CV.
"""

import re
import unicodedata
from typing import Any

from config import PALABRAS_EXCLUIDAS, PERFIL_AFINIDAD_CV, REMITENTE_TELEFONO

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

# Patrón para detectar requisitos de experiencia excesivos (ej. "5 años de experiencia", "mínimo 4 años")
PATRON_EXPERIENCIA_EXCESIVA = re.compile(
    r"\b(?:minimo|al menos|mas de|experiencia de)?\s*([4-9]|\d{2,})\s*(?:\+\s*)?a(?:ñ|n)os\s+de\s+experiencia\b",
    re.IGNORECASE,
)

# Patrón para detectar salario aproximado en la oferta (ej. $400, $450.00, USD 500)
PATRON_SALARIO = re.compile(
    r"(?:\$|USD\s*)\s*\d{3,4}(?:[.,]\d{2})?(?:\s*a\s*(?:\$|USD\s*)?\d{3,4}(?:[.,]\d{2})?)?",
    re.IGNORECASE,
)


def _quitar_acentos(texto: str) -> str:
    """Normaliza un texto en minúsculas y sin tildes para comparaciones limpias."""
    nfkd = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


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
    - 'whatsapp': teléfonos salvadoreños aptos para WhatsApp (móviles 6XXX/7XXX)
    """
    return {
        "emails": extraer_correos(descripcion_cruda),
        "telefonos": extraer_telefonos_sv(descripcion_cruda, solo_moviles=False),
        "whatsapp": extraer_telefonos_sv(descripcion_cruda, solo_moviles=True),
    }


def es_oferta_excluida(
    titulo: str,
    empresa: str = "",
    descripcion: str = "",
    palabras_excluidas: list[str] | None = None,
) -> tuple[bool, str]:
    """
    Verifica si el título, empresa o requisitos pertenecen a un sector excluido
    (sector de cocina/restaurantes, profesiones médicas/legales ajenas al CV,
    o si exige más de 3 años de experiencia inaccesible).
    Retorna (True, motivo) si debe descartarse, o (False, "") si es accesible.
    """
    lista_excluidas = (
        palabras_excluidas if palabras_excluidas is not None else PALABRAS_EXCLUIDAS
    )
    texto_titulo_empresa = _quitar_acentos(f"{titulo} {empresa}")

    for termino in lista_excluidas:
        termino_limpio = _quitar_acentos(termino.strip())
        if not termino_limpio:
            continue
        patron = rf"\b{re.escape(termino_limpio)}\b"
        if re.search(patron, texto_titulo_empresa):
            return True, f"sector/puesto excluido: '{termino.strip()}'"

    # Verificar cargos gerenciales o senior inaccesibles en el título
    titulo_norm = _quitar_acentos(titulo)
    for cargo_inaccesible in ("gerente", "director", "jefe de", "senior", "sr."):
        if re.search(rf"\b{re.escape(cargo_inaccesible)}\b", titulo_norm):
            return True, f"nivel jerárquico inaccesible: '{cargo_inaccesible}'"

    # Si ya tenemos la descripción completa, verificar que no exija 4+ años de experiencia
    if descripcion:
        desc_norm = _quitar_acentos(descripcion)
        match_exp = PATRON_EXPERIENCIA_EXCESIVA.search(desc_norm)
        if match_exp:
            return True, f"exige demasiados años de experiencia ({match_exp.group(0)})"

    return False, ""


def evaluar_afinidad_cv(titulo: str, descripcion: str = "") -> tuple[bool, str]:
    """
    Evalúa si la oferta laboral está asociada al perfil del CV:
    1. Administración, Atención al Cliente, Recepción y Caja
    2. Logística, Inventarios, Bodega, Compras, Mantenimiento y Carga Operativa
    3. Desarrollo de Software, Soporte Técnico, Base de Datos y Sistemas (ITCA)

    Retorna (es_afin, area_principal).
    """
    texto_completo = _quitar_acentos(f"{titulo} {descripcion}")
    titulo_norm = _quitar_acentos(titulo)

    puntajes: dict[str, int] = {
        "administrativo_atencion": 0,
        "logistica_operaciones": 0,
        "sistemas_software": 0,
    }

    for area, palabras in PERFIL_AFINIDAD_CV.items():
        for palabra in palabras:
            palabra_norm = _quitar_acentos(palabra)
            patron = rf"\b{re.escape(palabra_norm)}\b"
            # Peso triple si aparece en el título del puesto
            if re.search(patron, titulo_norm):
                puntajes[area] += 3
            elif descripcion and re.search(patron, texto_completo):
                puntajes[area] += 1

    mejor_area = max(puntajes, key=lambda k: puntajes[k])
    if puntajes[mejor_area] > 0:
        return True, mejor_area

    return False, "sin_afinidad"


def extraer_metadatos_empresa(descripcion_cruda: str) -> dict[str, Any]:
    """
    Extrae toda la información útil de la empresa y de la vacante desde el texto crudo:
    correos, todos los teléfonos (fijos 2XXX y móviles 6XXX/7XXX), salario ofrecido
    y un resumen limpio de los primeros párrafos.
    """
    contactos = extraer_contactos_oferta(descripcion_cruda)
    salarios = PATRON_SALARIO.findall(descripcion_cruda or "")
    salario_str = salarios[0].strip() if salarios else "No especificado"

    lineas = [
        linea.strip()
        for linea in (descripcion_cruda or "").splitlines()
        if linea.strip()
    ]
    resumen = " | ".join(lineas[:4])[:350] if lineas else ""

    return {
        "emails": contactos["emails"],
        "telefonos_todos": contactos["telefonos"],
        "whatsapp": contactos["whatsapp"],
        "salario": salario_str,
        "resumen_oferta": resumen,
    }
