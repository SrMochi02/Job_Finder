"""
Módulo de Extracción, Normalización y Afinidad de Perfil (Fase 2 - ETL).
Extrae correos electrónicos, teléfonos salvadoreños (503XXXXXXXX), metadatos de la empresa
y evalúa si la vacante es accesible y acorde a la experiencia del CV.
"""

import re
import unicodedata
from typing import Any

from config import (
    EDAD_POSTULANTE,
    GUIAS_PREPARACION_TECH,
    PALABRAS_EXCLUIDAS,
    PERFIL_AFINIDAD_CV,
    REMITENTE_TELEFONO,
)

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

# Patrón para descartar ofertas que exijan licencia de conducir, motocicleta o vehículo propio en la descripción
PATRON_LICENCIA_O_VEHICULO = re.compile(
    r"\b("
    r"licencia\s+de\s+conducir|licencia\s+liviana|licencia\s+pesada|licencia\s+de\s+moto|"
    r"licencia\s+vigente|poseer\s+licencia|con\s+licencia|indispensable\s+licencia|"
    r"vehiculo\s+propio|moto\s+propia|motocicleta\s+propia|poseer\s+vehiculo|"
    r"poseer\s+moto(?:cicleta)?|con\s+motocicleta|saber\s+conducir|saber\s+manejar"
    r")\b",
    re.IGNORECASE,
)

# Patrón para detectar edad mínima exigida en la oferta (ej. "Edad entre 25 y 39 años", "Edad: 25 a 35 años", "Mayor de 25 años")
PATRON_EDAD_MINIMA = re.compile(
    r"\b(?:edad(?:\s+entre|\s+de)?|mayor(?:es)?\s+de|de)\s*(\d{2})\s*(?:a|y|hasta|-)\s*\d{2}\s*a(?:ñ|n)os\b"
    r"|\bmayor(?:es)?\s+de\s+(\d{2})\s*a(?:ñ|n)os\b",
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

    # Verificar cargos gerenciales, supervisión, ruta o rubros ajenos en el título
    titulo_norm = _quitar_acentos(titulo)
    for cargo_inaccesible in (
        "gerente",
        "director",
        "jefe",
        "jefa",
        "supervisor",
        "supervisora",
        "coordinador",
        "coordinadora",
        "encargado de tienda",
        "encargada de tienda",
        "lider de tienda",
        "administrador de tienda",
        "administradora de tienda",
        "senior",
        "sr.",
        "ventas detalle",
        "vendedor de ruta",
        "ventas de ruta",
        "gestor de campo",
        "arq",
        "ing civil",
        "ingeniero civil",
        "arquitecto",
        "arquitectura",
        "lavador",
        "volanteo",
        "little caesars",
        "refrigeracion",
        "aire acondicionado",
        "vigilante",
    ):
        if re.search(rf"\b{re.escape(cargo_inaccesible)}\b", titulo_norm):
            return True, f"cargo o rubro excluido: '{cargo_inaccesible}'"

    # Verificar que el TÍTULO del puesto pertenezca explícitamente a al menos una de las 5 áreas del CV
    coincide_titulo_cv = False
    for _area, palabras_area in PERFIL_AFINIDAD_CV.items():
        for palabra in palabras_area:
            palabra_norm = _quitar_acentos(palabra)
            if re.search(rf"\b{re.escape(palabra_norm)}\b", titulo_norm):
                coincide_titulo_cv = True
                break
        if coincide_titulo_cv:
            break

    if not coincide_titulo_cv:
        return True, "el título del puesto no pertenece a tus áreas (Administración, Bodega/Logística, Atención/Caja/Ventas en local o Informática)"

    # Si ya tenemos la descripción completa, verificar que no exija licencia/vehículo ni 4+ años de experiencia
    if descripcion:
        desc_norm = _quitar_acentos(descripcion)
        match_licencia = PATRON_LICENCIA_O_VEHICULO.search(desc_norm)
        if match_licencia:
            return True, f"exige licencia de conducir o vehículo ({match_licencia.group(0)})"

        match_exp = PATRON_EXPERIENCIA_EXCESIVA.search(desc_norm)
        if match_exp:
            return True, f"exige demasiados años de experiencia ({match_exp.group(0)})"

        # Verificar si la oferta exige una edad mínima mayor a la edad del postulante
        edad_usuario_str = re.sub(r"\D", "", EDAD_POSTULANTE)
        edad_usuario = int(edad_usuario_str) if edad_usuario_str else 21
        for match_edad in PATRON_EDAD_MINIMA.finditer(desc_norm):
            edad_min_str = match_edad.group(1) or match_edad.group(2)
            if edad_min_str:
                edad_min = int(edad_min_str)
                if edad_min > edad_usuario and 18 <= edad_min <= 50:
                    return (
                        True,
                        f"exige edad mínima de {edad_min} años ({match_edad.group(0)})",
                    )

    return False, ""


def evaluar_afinidad_cv(titulo: str, descripcion: str = "") -> tuple[bool, str]:
    """
    Evalúa el ámbito laboral de la oferta:
    1. Administración, Atención al Cliente, Recepción y Caja ('administrativo_atencion')
    2. Logística, Inventarios, Bodega, Compras, Mantenimiento y Carga ('logistica_operaciones')
    3. Ventas, Atención en Sucursal y Comercial ('ventas_comercial')
    4. Soporte Técnico, Sistemas e Informática ('soporte_sistemas')
    5. Programación, Desarrollo de Software y Bases de Datos ('programacion_software')
    6. Otros ámbitos laborales accesibles fuera de cocina ('general_accesible')

    Retorna (es_afin, area_principal).
    """
    texto_completo = _quitar_acentos(f"{titulo} {descripcion}")
    titulo_norm = _quitar_acentos(titulo)

    puntajes: dict[str, int] = {area: 0 for area in PERFIL_AFINIDAD_CV}

    for area, palabras in PERFIL_AFINIDAD_CV.items():
        for palabra in palabras:
            palabra_norm = _quitar_acentos(palabra)
            patron = rf"\b{re.escape(palabra_norm)}\b"
            if re.search(patron, titulo_norm):
                puntajes[area] += 3
            elif descripcion and re.search(patron, texto_completo):
                puntajes[area] += 1

    mejor_area = max(puntajes, key=lambda k: puntajes[k])
    if puntajes[mejor_area] > 0:
        return True, mejor_area

    # Si no coincidió ninguna palabra clave de las 5 áreas del CV, se descarta.
    return False, "sin_afinidad"


def generar_consejo_preparacion(
    titulo: str,
    descripcion: str = "",
    area_afinidad: str = "general_accesible",
) -> str:
    """
    Genera una recomendación personalizada de preparación para entrevista.
    Si detecta una oferta de Programación / Desarrollo de Software o Soporte TI,
    le indica exactamente qué temas repasar para ir seguro a la entrevista.
    """
    texto_norm = _quitar_acentos(f"{titulo} {descripcion}")
    consejos_especificos: list[str] = []

    for clave, guia in GUIAS_PREPARACION_TECH.items():
        clave_norm = _quitar_acentos(clave)
        if re.search(rf"\b{re.escape(clave_norm)}\b", texto_norm):
            consejos_especificos.append(guia)

    if area_afinidad == "programacion_software":
        detalle = (
            " ".join(consejos_especificos[:3])
            if consejos_especificos
            else "Repasa lógica de programación, consultas SQL básicas y cómo explicar tus proyectos de ITCA."
        )
        return (
            f"[ALERTA DE PREPARACIÓN SOFTWARE/TI] Tienes 5 años de base técnica (Bachillerato + ITCA), "
            f"¡sí puedes aplicar! Antes de la entrevista prepárate bien en: {detalle}"
        )

    if area_afinidad == "soporte_sistemas":
        detalle = (
            " ".join(consejos_especificos[:2])
            if consejos_especificos
            else "Repasa mantenimiento preventivo, soporte a usuarios, Office y configuración básica de red."
        )
        return f"[PREPARACIÓN SOPORTE/TI] Combina tu título de ITCA con tu trato al cliente en clínica. {detalle}"

    if area_afinidad == "administrativo_atencion":
        return (
            "Destaca tus más de 2 años en Clínica Cliniciru: cuadre de caja chica sin faltantes, "
            "facturación, control de agenda y trato amable a clientes."
        )

    if area_afinidad == "logistica_operaciones":
        return (
            "Destaca tu experiencia combinada: auditoría física de inventarios y recepción de proveedores "
            "en clínica + resistencia física, orden y seguridad ocupacional en mantenimiento y carga."
        )

    return (
        "Destaca tu puntualidad, disponibilidad inmediata en San Miguel, experiencia en atención "
        "al cliente, manejo de inventarios y facilidad para aprender rápido."
    )


def extraer_metadatos_empresa(
    descripcion_cruda: str,
    titulo: str = "",
    area_afinidad: str = "general_accesible",
) -> dict[str, Any]:
    """
    Extrae toda la información útil de la empresa y de la vacante desde el texto crudo:
    correos, todos los teléfonos (fijos 2XXX y móviles 6XXX/7XXX), salario ofrecido,
    resumen de la oferta y guía de preparación para la entrevista.
    """
    contactos = extraer_contactos_oferta(descripcion_cruda)
    salarios = PATRON_SALARIO.findall(descripcion_cruda or "")
    if salarios:
        salario_str = re.sub(r"\s+", "", salarios[0].strip())
    else:
        salario_str = "No especificado"

    lineas_ignoradas = {"volver al listado", "oferta", "postularme", "compartir"}
    lineas = [
        linea.strip()
        for linea in (descripcion_cruda or "").splitlines()
        if linea.strip() and linea.strip().lower() not in lineas_ignoradas
    ]
    resumen = " | ".join(lineas[:6])[:380] if lineas else ""
    consejo = generar_consejo_preparacion(titulo, descripcion_cruda, area_afinidad)

    return {
        "emails": contactos["emails"],
        "telefonos_todos": contactos["telefonos"],
        "whatsapp": contactos["whatsapp"],
        "salario": salario_str,
        "resumen_oferta": resumen,
        "consejo_preparacion": consejo,
    }
