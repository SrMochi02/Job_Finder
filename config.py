"""
Módulo de configuración del entorno (Fase 1).
Carga las variables desde el archivo .env de forma aislada y segura.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno desde el archivo .env
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Credenciales de Gmail y datos del remitente
GMAIL_USER: str = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD: str = os.getenv("GMAIL_APP_PASSWORD", "")
REMITENTE_NOMBRE: str = os.getenv("REMITENTE_NOMBRE", "Candidato")
REMITENTE_TELEFONO: str = os.getenv("REMITENTE_TELEFONO", "")

# Rutas de archivos y directorios
CV_PATH: Path = Path(os.getenv("CV_PATH", str(BASE_DIR / "cv_postulante.pdf"))).resolve()
DB_PATH: Path = Path(os.getenv("DB_PATH", str(BASE_DIR / "jobfinder.db"))).resolve()
WHATSAPP_SESSION_DIR: Path = Path(
    os.getenv("WHATSAPP_SESSION_DIR", str(BASE_DIR / "whatsapp_session"))
).resolve()

# Parámetros de scraping
UBICACION_OBJETIVO: str = os.getenv("UBICACION_OBJETIVO", "San Miguel")
PAGINAS_MAXIMAS: int = int(os.getenv("PAGINAS_MAXIMAS", "3"))
HEADLESS_SCRAPER: bool = os.getenv("HEADLESS_SCRAPER", "False").strip().lower() in (
    "true",
    "1",
    "yes",
)

# Sectores o palabras clave excluidas (cocina, gastronomía, carreras médicas/legales ajenas al perfil, licencias pesadas)
_EXCLUIDAS_DEFAULT = (
    "cocina,cocinero,cocinera,chef,mesero,mesera,lavaplatos,restaurante,"
    "pupuseria,panadero,pastelero,barista,parrillero,comida rapida,gastronomia,bartender,steward,"
    "medico,doctor,doctora,enfermera,enfermero,odontologo,farmaceutico,regente,abogado,notario,"
    "contador publico,auditor externo,arquitecto,ingeniero civil,ingeniero agronomo,psicologo,"
    "motorista pesado,cabezal,licencia pesada,rastre,guardia armado,seguridad privada"
)
PALABRAS_EXCLUIDAS: list[str] = [
    palabra.strip().lower()
    for palabra in os.getenv("PALABRAS_EXCLUIDAS", _EXCLUIDAS_DEFAULT).split(",")
    if palabra.strip()
]

# Áreas de afinidad asociadas al CV (Administración/Atención al Cliente, Logística/Operaciones, Software/IT)
PERFIL_AFINIDAD_CV: dict[str, list[str]] = {
    "administrativo_atencion": [
        "administrativo",
        "administrativa",
        "asistente",
        "auxiliar administrativo",
        "atencion al cliente",
        "servicio al cliente",
        "recepcion",
        "recepcionista",
        "caja",
        "cajero",
        "facturacion",
        "digitador",
        "oficina",
        "ofimatica",
        "agenda",
        "secretaria",
        "archivo",
        "call center",
        "asesor",
        "ejecutivo",
        "ventas",
        "clinica",
    ],
    "logistica_operaciones": [
        "inventario",
        "bodega",
        "bodeguero",
        "almacen",
        "logistica",
        "compras",
        "pedidos",
        "encomiendas",
        "proveedores",
        "despacho",
        "mantenimiento",
        "carga",
        "descarga",
        "auxiliar",
        "operativo",
        "operaciones",
        "planta",
        "orden",
        "suministros",
        "kardex",
    ],
    "sistemas_software": [
        "software",
        "programador",
        "desarrollador",
        "sistemas",
        "soporte",
        "soporte tecnico",
        "informatica",
        "computacion",
        "base de datos",
        "sql",
        "java",
        "c#",
        "tecnico",
        "tecnologia",
        "it",
        "ti",
        "redes",
        "helpdesk",
        "qa",
        "tester",
    ],
}

# Horario de operación continua (7:00 AM a 4:00 PM por defecto)
HORA_INICIO_JORNADA: int = int(os.getenv("HORA_INICIO_JORNADA", "7"))
HORA_FIN_JORNADA: int = int(os.getenv("HORA_FIN_JORNADA", "16"))
INTERVALO_CICLO_MINUTOS: int = int(os.getenv("INTERVALO_CICLO_MINUTOS", "45"))

# Límites diarios y tiempos de espera (Rate Limiting)
MAX_EMAILS_POR_DIA: int = int(os.getenv("MAX_EMAILS_POR_DIA", "12"))
MAX_WHATSAPP_POR_DIA: int = int(os.getenv("MAX_WHATSAPP_POR_DIA", "6"))
DELAY_MIN_SEGUNDOS: float = float(os.getenv("DELAY_MIN_SEGUNDOS", "30"))
DELAY_MAX_SEGUNDOS: float = float(os.getenv("DELAY_MAX_SEGUNDOS", "90"))


def validar_configuracion_correo() -> tuple[bool, str]:
    """Verifica que las credenciales de Gmail y el archivo CV estén listos antes de enviar."""
    if not GMAIL_USER or GMAIL_USER == "tu_correo@gmail.com":
        return False, "GMAIL_USER no está configurado en el archivo .env"
    if not GMAIL_APP_PASSWORD or "xxxx" in GMAIL_APP_PASSWORD:
        return False, "GMAIL_APP_PASSWORD no está configurado en el archivo .env"
    if not CV_PATH.exists() or not CV_PATH.is_file():
        return False, f"No se encontró el archivo CV en la ruta: {CV_PATH}"
    return True, "Configuración de correo válida"
