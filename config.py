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
DIRECCION_RESIDENCIA: str = os.getenv("DIRECCION_RESIDENCIA", "San Miguel, El Salvador")
PRETENSION_SALARIAL: str = os.getenv("PRETENSION_SALARIAL", "450")

# Rutas de archivos y directorios
CV_PATH: Path = Path(os.getenv("CV_PATH", str(BASE_DIR / "cv_postulante.pdf"))).resolve()
DB_PATH: Path = Path(os.getenv("DB_PATH", str(BASE_DIR / "jobfinder.db"))).resolve()
WHATSAPP_SESSION_DIR: Path = Path(
    os.getenv("WHATSAPP_SESSION_DIR", str(BASE_DIR / "whatsapp_session"))
).resolve()
PORTAL_SESSION_DIR: Path = Path(
    os.getenv("PORTAL_SESSION_DIR", str(BASE_DIR / "portal_session"))
).resolve()
AUTO_POSTULAR_PORTAL: bool = os.getenv("AUTO_POSTULAR_PORTAL", "True").strip().lower() in (
    "true",
    "1",
    "yes",
)

# Parámetros de scraping
UBICACION_OBJETIVO: str = os.getenv("UBICACION_OBJETIVO", "San Miguel")
PAGINAS_MAXIMAS: int = int(os.getenv("PAGINAS_MAXIMAS", "3"))
HEADLESS_SCRAPER: bool = os.getenv("HEADLESS_SCRAPER", "False").strip().lower() in (
    "true",
    "1",
    "yes",
)

# Sectores o palabras clave excluidas (cocina, conducción/licencia, cargos de supervisión/gerencia, carreras médicas/docencia/mecánica/campo/limpieza)
_EXCLUIDAS_DEFAULT = (
    "cocina,cocinero,cocinera,chef,mesero,mesera,lavaplatos,restaurante,"
    "pupuseria,panadero,pastelero,barista,parrillero,comida rapida,gastronomia,bartender,steward,"
    "medico,doctor,doctora,enfermera,enfermero,odontologo,farmaceutico,farmacia,regente,abogado,notario,"
    "contador publico,auditor externo,arquitecto,ingeniero civil,ingeniero agronomo,psicologo,"
    "profesor,profesora,docente,maestro,maestra,mecanico,automotriz,perito,"
    "tecnico en limpieza,ordenanza,conserje,impulsadora,vendedor de campo,trabajo de campo,cambaceo,"
    "motorista,conductor,chofer,repartidor,rutero,mensajero,motociclista,delivery,"
    "cabezal,licencia,rastre,guardia armado,seguridad privada,supervisor,coordinador,gerente,jefe"
)
PALABRAS_EXCLUIDAS: list[str] = [
    palabra.strip().lower()
    for palabra in os.getenv("PALABRAS_EXCLUIDAS", _EXCLUIDAS_DEFAULT).split(",")
    if palabra.strip()
]

# Áreas de afinidad asociadas al CV y otros ámbitos laborales accesibles (excepto cocina)
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
        "cajera",
        "facturacion",
        "digitador",
        "oficina",
        "ofimatica",
        "agenda",
        "secretaria",
        "archivo",
        "call center",
        "clinica",
        "hospital",
        "cobros",
        "creditos",
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
        "produccion",
        "empaque",
    ],
    "ventas_comercial": [
        "ventas",
        "vendedor",
        "asesor",
        "ejecutivo",
        "comercial",
        "promotor",
        "impulsador",
        "mostrador",
        "tienda",
        "sucursal",
        "agencia",
    ],
    "soporte_sistemas": [
        "soporte tecnico",
        "tecnico en sistemas",
        "tecnico en informatica",
        "tecnico en computacion",
        "auxiliar de sistemas",
        "sistemas",
        "informatica",
        "computacion",
        "tecnologia",
        "it",
        "ti",
        "redes",
        "helpdesk",
        "mantenimiento de computadoras",
    ],
    "programacion_software": [
        "software",
        "programador",
        "desarrollador",
        "base de datos",
        "sql",
        "java",
        "c#",
        ".net",
        "qa",
        "tester",
        "web",
        "junior",
    ],
}

# Guía práctica de preparación cuando el sistema detecta ofertas de Software / TI
GUIAS_PREPARACION_TECH: dict[str, str] = {
    "sql": "Repasar consultas SQL prácticas: SELECT, INNER JOIN, GROUP BY, filtros WHERE y cómo hacer un CRUD básico.",
    "base de datos": "Repasar diseño de tablas relacionales (llaves primarias/foráneas), normalización y respaldos.",
    "c#": "Repasar sintaxis de C#, Programación Orientada a Objetos (clases, herencia) y conexión a SQL Server con .NET.",
    "java": "Repasar estructura de clases en Java, colecciones (ArrayList, HashMap), manejo de excepciones y JDBC.",
    "programador": "Preparar 1 o 2 proyectos que hiciste en ITCA o en el Bachillerato para explicar cómo resolviste la lógica.",
    "desarrollador": "Repasar lógica de programación, control de versiones con Git y cómo explicar tu flujo de trabajo en equipo.",
    "soporte": "Repasar diagnóstico de PC, instalación de Windows/Office, configuración de impresoras y red local (IP/DNS).",
    "redes": "Repasar cableado estructurado, configuración básica de routers/switches, ping, ipconfig y subredes.",
    "excel": "Repasar tablas dinámicas, BUSCARV/XLOOKUP, filtros avanzados y fórmulas condicionales (SI, SUMAR.SI).",
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
