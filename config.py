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
ULTIMO_SALARIO: str = os.getenv("ULTIMO_SALARIO", "380")
EDAD_POSTULANTE: str = os.getenv("EDAD_POSTULANTE", "21 años")
ESTADO_CIVIL_POSTULANTE: str = os.getenv("ESTADO_CIVIL_POSTULANTE", "Acompañado")
RESPUESTA_HIJOS: str = os.getenv("RESPUESTA_HIJOS", "Sí, esperando una hija próximamente.")
POSEE_LICENCIA_VEHICULO: str = os.getenv("POSEE_LICENCIA_VEHICULO", "NO")
ESTUDIA_ACTUALMENTE: str = os.getenv("ESTUDIA_ACTUALMENTE", "NO")
NIVEL_ACADEMICO: str = os.getenv(
    "NIVEL_ACADEMICO",
    "Egresado de Técnico en Ingeniería en Desarrollo de Software (ITCA FEPADE) y Bachiller Técnico en Software.",
)
RESUMEN_EXPERIENCIA_CV: str = os.getenv(
    "RESUMEN_EXPERIENCIA_CV",
    "Más de 2 años de experiencia comprobada en atención al cliente, manejo y cuadre de caja chica, facturación, control físico de inventarios en bodega y recepción de proveedores, más labores operativas.",
)
CARTA_PRESENTACION: str = os.getenv(
    "CARTA_PRESENTACION",
    "Buen día. Pongo a su disposición mi CV para la vacante. Cuento con más de 2 años de experiencia en asistencia administrativa, atención al cliente, manejo de caja chica, facturación y control físico de inventarios, además de experiencia operativa en bodega y formación técnica. Resido en la zona y tengo disponibilidad inmediata. Saludos cordiales.",
)
MOTIVO_SALIDA_ULTIMO_EMPLEO: str = os.getenv(
    "MOTIVO_SALIDA_ULTIMO_EMPLEO",
    "Búsqueda de superación profesional y estabilidad laboral a largo plazo.",
)
AREAS_ACTIVA_STR: str = os.getenv(
    "AREAS_ACTIVAS",
    "administrativo_atencion,logistica_operaciones,ventas_comercial,soporte_sistemas,programacion_software",
)
AREAS_ACTIVAS: list[str] = [
    a.strip() for a in AREAS_ACTIVA_STR.split(",") if a.strip()
]

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
PAGINAS_MAXIMAS: int = int(os.getenv("PAGINAS_MAXIMAS", "8"))
HEADLESS_SCRAPER: bool = os.getenv("HEADLESS_SCRAPER", "False").strip().lower() in (
    "true",
    "1",
    "yes",
)

# Sectores o palabras clave excluidas (cocina pesada/asadores, Pollo Campero/Campestre, conducción/licencia, cargos de supervisión/gerencia, carreras médicas/docencia/mecánica/campo/limpieza)
_EXCLUIDAS_DEFAULT = (
    "cocinero,cocinera,chef,lavaplatos,asador,parrillero,pupuseria,panadero,pastelero,bartender,steward,"
    "pollo campero,campero,pollo campestre,campestre,"
    "medico,doctor,doctora,enfermera,enfermero,odontologo,farmaceutico,farmacia,regente,abogado,notario,"
    "contador publico,auditor externo,arquitecto,arquitectura,arq,ingeniero civil,ing civil,ingeniero agronomo,ing agronomo,ingeniero industrial,ing industrial,ingeniero electrico,ing electrico,ingeniero mecanico,psicologo,psicologa,"
    "profesor,profesora,docente,maestro,maestra,mecanico,automotriz,perito,topografo,"
    "tecnico en limpieza,limpieza,ordenanza,conserje,lavador,carwash,autolavado,lavado de vehiculos,volanteo,volantero,edecan,impulsadora,display,mercaderista de ruta,vendedor de campo,trabajo de campo,gestor de campo,cambaceo,"
    "refrigeracion,aire acondicionado,electricista,soldador,albañil,albanil,fontanero,plomero,carpintero,instalador,costurera,sastre,estilista,barbero,peluquero,"
    "motorista,conductor,chofer,repartidor,rutero,mensajero,motociclista,delivery,"
    "cabezal,licencia,rastre,guardia armado,seguridad privada,vigilante,supervisor,supervisora,coordinador,coordinadora,gerente,jefe,jefa,encargada de tienda,encargado de tienda,lider de tienda,administradora de tienda"
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
        "facturador",
        "facturadora",
        "digitador",
        "digitadora",
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
        "auxiliar de bodega",
        "almacen",
        "logistica",
        "compras",
        "pedidos",
        "encomiendas",
        "proveedores",
        "despacho",
        "auxiliar de despacho",
        "carga",
        "descarga",
        "auxiliar de mantenimiento",
        "operador de bodega",
        "suministros",
        "kardex",
        "empaque",
    ],
    "ventas_comercial": [
        "ventas",
        "vendedor",
        "asesor de ventas",
        "ejecutivo de venta",
        "ejecutivo de ventas",
        "dependiente",
        "atencion en sala",
        "mostrador",
        "cajero",
        "little caesar",
        "little caesars",
        "pizza hut",
        "wendys",
        "wendy's",
        "burger king",
        "burguer king",
        "kfc",
        "asociado de restaurante",
        "equipo de restaurante",
        "atencion en restaurante",
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


def recargar_configuracion() -> None:
    """Recarga todas las variables de configuración en caliente desde el archivo .env."""
    global GMAIL_USER, GMAIL_APP_PASSWORD, REMITENTE_NOMBRE, REMITENTE_TELEFONO
    global DIRECCION_RESIDENCIA, PRETENSION_SALARIAL, ULTIMO_SALARIO, EDAD_POSTULANTE
    global ESTADO_CIVIL_POSTULANTE, RESPUESTA_HIJOS, POSEE_LICENCIA_VEHICULO
    global ESTUDIA_ACTUALMENTE, NIVEL_ACADEMICO, RESUMEN_EXPERIENCIA_CV, CARTA_PRESENTACION
    global MOTIVO_SALIDA_ULTIMO_EMPLEO, AREAS_ACTIVA_STR, AREAS_ACTIVAS, CV_PATH
    global AUTO_POSTULAR_PORTAL, UBICACION_OBJETIVO, PAGINAS_MAXIMAS, HEADLESS_SCRAPER
    global PALABRAS_EXCLUIDAS, HORA_INICIO_JORNADA, HORA_FIN_JORNADA, INTERVALO_CICLO_MINUTOS
    global MAX_EMAILS_POR_DIA, MAX_WHATSAPP_POR_DIA

    load_dotenv(BASE_DIR / ".env", override=True)
    GMAIL_USER = os.getenv("GMAIL_USER", "")
    GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
    REMITENTE_NOMBRE = os.getenv("REMITENTE_NOMBRE", "Candidato")
    REMITENTE_TELEFONO = os.getenv("REMITENTE_TELEFONO", "")
    DIRECCION_RESIDENCIA = os.getenv("DIRECCION_RESIDENCIA", "San Miguel, El Salvador")
    PRETENSION_SALARIAL = os.getenv("PRETENSION_SALARIAL", "450")
    ULTIMO_SALARIO = os.getenv("ULTIMO_SALARIO", "380")
    EDAD_POSTULANTE = os.getenv("EDAD_POSTULANTE", "21 años")
    ESTADO_CIVIL_POSTULANTE = os.getenv("ESTADO_CIVIL_POSTULANTE", "Acompañado")
    RESPUESTA_HIJOS = os.getenv("RESPUESTA_HIJOS", "Sí, esperando una hija próximamente.")
    POSEE_LICENCIA_VEHICULO = os.getenv("POSEE_LICENCIA_VEHICULO", "NO")
    ESTUDIA_ACTUALMENTE = os.getenv("ESTUDIA_ACTUALMENTE", "NO")
    NIVEL_ACADEMICO = os.getenv(
        "NIVEL_ACADEMICO",
        "Egresado de Técnico en Ingeniería en Desarrollo de Software (ITCA FEPADE) y Bachiller Técnico en Software.",
    )
    RESUMEN_EXPERIENCIA_CV = os.getenv(
        "RESUMEN_EXPERIENCIA_CV",
        "Más de 2 años de experiencia comprobada en atención al cliente, manejo y cuadre de caja chica, facturación, control físico de inventarios en bodega y recepción de proveedores, más labores operativas.",
    )
    CARTA_PRESENTACION = os.getenv(
        "CARTA_PRESENTACION",
        "Buen día. Pongo a su disposición mi CV para la vacante. Cuento con más de 2 años de experiencia en asistencia administrativa, atención al cliente, manejo de caja chica, facturación y control físico de inventarios, además de experiencia operativa en bodega y formación técnica. Resido en la zona y tengo disponibilidad inmediata. Saludos cordiales.",
    )
    MOTIVO_SALIDA_ULTIMO_EMPLEO = os.getenv(
        "MOTIVO_SALIDA_ULTIMO_EMPLEO",
        "Búsqueda de superación profesional y estabilidad laboral a largo plazo.",
    )
    AREAS_ACTIVA_STR = os.getenv(
        "AREAS_ACTIVAS",
        "administrativo_atencion,logistica_operaciones,ventas_comercial,soporte_sistemas,programacion_software",
    )
    AREAS_ACTIVAS = [a.strip() for a in AREAS_ACTIVA_STR.split(",") if a.strip()]
    CV_PATH = Path(os.getenv("CV_PATH", str(BASE_DIR / "cv_postulante.pdf"))).resolve()
    AUTO_POSTULAR_PORTAL = os.getenv("AUTO_POSTULAR_PORTAL", "True").strip().lower() in (
        "true",
        "1",
        "yes",
    )
    UBICACION_OBJETIVO = os.getenv("UBICACION_OBJETIVO", "San Miguel")
    PAGINAS_MAXIMAS = int(os.getenv("PAGINAS_MAXIMAS", "8"))
    HEADLESS_SCRAPER = os.getenv("HEADLESS_SCRAPER", "False").strip().lower() in (
        "true",
        "1",
        "yes",
    )
    PALABRAS_EXCLUIDAS = [
        palabra.strip().lower()
        for palabra in os.getenv("PALABRAS_EXCLUIDAS", _EXCLUIDAS_DEFAULT).split(",")
        if palabra.strip()
    ]
    HORA_INICIO_JORNADA = int(os.getenv("HORA_INICIO_JORNADA", "7"))
    HORA_FIN_JORNADA = int(os.getenv("HORA_FIN_JORNADA", "16"))
    INTERVALO_CICLO_MINUTOS = int(os.getenv("INTERVALO_CICLO_MINUTOS", "45"))
    MAX_EMAILS_POR_DIA = int(os.getenv("MAX_EMAILS_POR_DIA", "12"))
    MAX_WHATSAPP_POR_DIA = int(os.getenv("MAX_WHATSAPP_POR_DIA", "6"))


def guardar_variables_env(nuevos_valores: dict[str, str]) -> None:
    """
    Actualiza o inserta pares CLAVE=VALOR dentro del archivo .env preservando comentarios,
    y recarga la configuración en memoria inmediatamente.
    """
    env_path = BASE_DIR / ".env"
    lineas_existentes: list[str] = []
    if env_path.exists():
        lineas_existentes = env_path.read_text(encoding="utf-8").splitlines()

    claves_actualizadas: set[str] = set()
    nuevas_lineas: list[str] = []

    for linea in lineas_existentes:
        linea_strip = linea.strip()
        if not linea_strip or linea_strip.startswith("#") or "=" not in linea:
            nuevas_lineas.append(linea)
            continue
        clave, _ = linea.split("=", 1)
        clave_limpia = clave.strip()
        if clave_limpia in nuevos_valores:
            valor_limpio = str(nuevos_valores[clave_limpia]).replace("\n", " ").replace("\r", "").strip()
            nuevas_lineas.append(f"{clave_limpia}={valor_limpio}")
            claves_actualizadas.add(clave_limpia)
        else:
            nuevas_lineas.append(linea)

    for clave, valor in nuevos_valores.items():
        if clave not in claves_actualizadas:
            valor_limpio = str(valor).replace("\n", " ").replace("\r", "").strip()
            nuevas_lineas.append(f"{clave}={valor_limpio}")

    env_path.write_text("\n".join(nuevas_lineas) + "\n", encoding="utf-8")
    recargar_configuracion()

