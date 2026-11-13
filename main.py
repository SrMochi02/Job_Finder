"""
Orquestador Principal (Fase 5).
Une todo el flujo lineal:
Scrapear -> Filtrar por afinidad de CV y experiencia accesible -> Extraer datos de empresa ->
Guardar en BD -> Exportar reporte CSV -> Enviar correos y WhatsApp (en horario de 7:00 AM a 4:00 PM).
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from typing import Any

from config import (
    HORA_FIN_JORNADA,
    HORA_INICIO_JORNADA,
    INTERVALO_CICLO_MINUTOS,
)
from database import (
    contar_envios_hoy,
    exportar_reporte_empresas_csv,
    guardar_vacante,
    inicializar_bd,
    obtener_directorio_empresas,
    obtener_postulaciones_pendientes,
    registrar_postulacion_pendiente,
    registrar_respuesta_entrevista,
)
from mailer import procesar_cola_correos
from parser import (
    es_oferta_excluida,
    evaluar_afinidad_cv,
    extraer_metadatos_empresa,
)
from scraper import ejecutar_scraping_todos_los_portales
from whatsapp import procesar_cola_whatsapp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("jobfinder.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("orquestador")


def esta_en_horario_laboral(
    hora_inicio: int = HORA_INICIO_JORNADA,
    hora_fin: int = HORA_FIN_JORNADA,
) -> bool:
    """Verifica si la hora actual del sistema está entre las 7:00 AM y las 4:00 PM (16:00)."""
    hora_actual = datetime.now().hour
    return hora_inicio <= hora_actual < hora_fin


def procesar_ofertas_extraidas(ofertas: list[dict[str, Any]]) -> dict[str, int]:
    """
    Filtra las ofertas para asegurar que:
    1. No pertenezcan al sector excluido (cocina, etc.) ni pidan experiencia inaccesible (4+ años / gerencias).
    2. Estén asociadas al perfil del CV (Administración/Atención, Logística/Inventarios/Carga, o Software/IT).
    3. Extrae toda la información de la empresa (correos, teléfonos fijos y móviles, salario, resumen)
       y la guarda en la base de datos junto con las postulaciones pendientes.
    """
    estadisticas = {
        "vacantes_nuevas": 0,
        "vacantes_duplicadas": 0,
        "vacantes_excluidas": 0,
        "vacantes_sin_afinidad_cv": 0,
        "emails_agendados": 0,
        "whatsapp_agendados": 0,
    }

    for oferta in ofertas:
        titulo = oferta["titulo"]
        empresa = oferta.get("empresa", "Empresa Confidencial")
        descripcion = oferta.get("descripcion_cruda", "")

        # 1. Filtro de exclusión (cocina, carreras médicas/legales o experiencia excesiva)
        excluida, motivo = es_oferta_excluida(titulo, empresa, descripcion)
        if excluida:
            estadisticas["vacantes_excluidas"] += 1
            logger.info("Descartada (%s): %s - %s", motivo, titulo, empresa)
            continue

        # 2. Filtro de afinidad con el CV
        es_afin, area_afinidad = evaluar_afinidad_cv(titulo, descripcion)
        if not es_afin:
            estadisticas["vacantes_sin_afinidad_cv"] += 1
            logger.info(
                "Omitida por no coincidir con las áreas del CV: %s (%s)",
                titulo,
                empresa,
            )
            continue

        # 3. Extraer toda la información disponible de la empresa
        info_empresa = extraer_metadatos_empresa(descripcion)
        correos_str = ", ".join(info_empresa["emails"])
        telefonos_str = ", ".join(info_empresa["telefonos_todos"])

        vacante_id, es_nueva = guardar_vacante(
            titulo=titulo,
            empresa=empresa,
            ubicacion=oferta.get("ubicacion", "San Miguel"),
            url_original=oferta["url_original"],
            descripcion_cruda=descripcion,
            portal=oferta.get("portal", "Computrabajo"),
            area_afinidad=area_afinidad,
            salario_ofrecido=info_empresa["salario"],
            correos_empresa=correos_str,
            telefonos_empresa=telefonos_str,
            resumen_oferta=info_empresa["resumen_oferta"],
        )

        if es_nueva:
            estadisticas["vacantes_nuevas"] += 1
        else:
            estadisticas["vacantes_duplicadas"] += 1

        for correo in info_empresa["emails"]:
            if registrar_postulacion_pendiente(vacante_id, "EMAIL", correo):
                estadisticas["emails_agendados"] += 1
                logger.info(
                    "[%s] Correo agendado para '%s' (%s): %s",
                    area_afinidad,
                    titulo,
                    empresa,
                    correo,
                )

        for numero_wa in info_empresa["whatsapp"]:
            if registrar_postulacion_pendiente(vacante_id, "WHATSAPP", numero_wa):
                estadisticas["whatsapp_agendados"] += 1
                logger.info(
                    "[%s] WhatsApp agendado para '%s' (%s): %s",
                    area_afinidad,
                    titulo,
                    empresa,
                    numero_wa,
                )

    # Exportar automáticamente el reporte actualizado de empresas a CSV
    ruta_csv = exportar_reporte_empresas_csv()
    logger.info("Directorio de empresas actualizado en: %s", ruta_csv)

    return estadisticas


def mostrar_resumen_empresas() -> None:
    """Muestra en consola el listado de empresas, contactos y seguimiento de entrevistas."""
    inicializar_bd()
    empresas = obtener_directorio_empresas()
    ruta_csv = exportar_reporte_empresas_csv()

    if not empresas:
        print("\nAún no hay empresas registradas en la base de datos.")
        return

    print("\n" + "=" * 95)
    print(
        f"{'CÓDIGO':<9} | {'EMPRESA':<26} | {'PUESTO':<28} | {'ENTREVISTA':<10} | {'CONTACTOS'}"
    )
    print("-" * 95)
    for emp in empresas:
        contactos = emp["correos_empresa"] or emp["telefonos_empresa"] or "Sin contacto directo"
        print(
            f"{emp['codigo_corto']:<9} | "
            f"{emp['empresa'][:26]:<26} | "
            f"{emp['titulo'][:28]:<28} | "
            f"{emp['llamaron_entrevista']:<10} | "
            f"{contactos[:35]}"
        )
    print("=" * 95)
    print(f"Reporte completo exportado para Excel en: {ruta_csv}\n")


def ejecutar_flujo_completo(
    ejecutar_etl: bool = True,
    ejecutar_email: bool = True,
    ejecutar_whatsapp: bool = True,
    modo_demo: bool = False,
    respetar_horario: bool = True,
) -> None:
    """Ejecuta un ciclo del flujo lineal de Job Finder."""
    logger.info("=== INICIANDO CICLO DE AUTOMATIZACIÓN JOB FINDER (SAN MIGUEL) ===")
    inicializar_bd()

    if modo_demo:
        logger.info("Ejecutando en modo DEMO con ofertas de prueba en San Miguel...")
        ofertas_demo = [
            {
                "portal": "Computrabajo",
                "titulo": "Asistente Administrativo y de Inventario",
                "empresa": "Distribuidora de Oriente S.A. de C.V.",
                "ubicacion": "San Miguel",
                "url_original": "https://sv.computrabajo.com/ofertas-de-trabajo/oferta-demo-inventario",
                "descripcion_cruda": (
                    "Buscamos Asistente Administrativo y control de inventario en bodega para San Miguel. "
                    "Salario $450.00. Experiencia de 1 a 2 años en facturación, caja chica, recepción de pedidos "
                    "y atención al cliente. Interesados enviar CV a rrhh@distribuidoraoriente.com.sv "
                    "o escribir al WhatsApp +503 7890-1234 / Teléfono fijo 2661-4455."
                ),
            },
            {
                "portal": "Computrabajo",
                "titulo": "Cocinero de Restaurante",
                "empresa": "Asados San Miguel",
                "ubicacion": "San Miguel",
                "url_original": "https://sv.computrabajo.com/ofertas-de-trabajo/oferta-demo-cocina",
                "descripcion_cruda": "Se solicita cocinero con experiencia en parrilla. Tel 7111-2222.",
            },
        ]
        resumen_etl = procesar_ofertas_extraidas(ofertas_demo)
        logger.info("Resumen ETL (Demo): %s", resumen_etl)
        mostrar_resumen_empresas()
        return

    if ejecutar_etl:
        ofertas = ejecutar_scraping_todos_los_portales()
        resumen_etl = procesar_ofertas_extraidas(ofertas)
        logger.info("Resumen ETL: %s", resumen_etl)

    pendientes_email = len(obtener_postulaciones_pendientes("EMAIL"))
    pendientes_wa = len(obtener_postulaciones_pendientes("WHATSAPP"))
    logger.info(
        "Cola actual -> EMAIL pendientes: %d | WHATSAPP pendientes: %d",
        pendientes_email,
        pendientes_wa,
    )

    if respetar_horario and not esta_en_horario_laboral():
        logger.info(
            "Fuera del horario de envío (%02d:00 a %02d:00). "
            "Los envíos quedan agendados para la ventana de 7:00 AM a 4:00 PM.",
            HORA_INICIO_JORNADA,
            HORA_FIN_JORNADA,
        )
        return

    if ejecutar_email:
        enviados_email = procesar_cola_correos()
        logger.info("Correos enviados en este ciclo: %d", enviados_email)

    if ejecutar_whatsapp:
        enviados_wa = procesar_cola_whatsapp()
        logger.info("Mensajes de WhatsApp enviados en este ciclo: %d", enviados_wa)

    exportar_reporte_empresas_csv()
    logger.info(
        "=== CICLO COMPLETADO | Total enviados hoy -> EMAIL: %d | WHATSAPP: %d ===",
        contar_envios_hoy("EMAIL"),
        contar_envios_hoy("WHATSAPP"),
    )


def ejecutar_jornada_continua() -> None:
    """
    Mantiene la aplicación activa buscando ofertas compatibles con el CV y enviando
    postulaciones de forma distribuida en el horario de 7:00 AM a 4:00 PM.
    """
    logger.info(
        "Iniciando modo JORNADA CONTINUA (%02d:00 a %02d:00, ciclos cada %d minutos)...",
        HORA_INICIO_JORNADA,
        HORA_FIN_JORNADA,
        INTERVALO_CICLO_MINUTOS,
    )
    try:
        while True:
            if esta_en_horario_laboral():
                ejecutar_flujo_completo(respetar_horario=True)
                logger.info(
                    "Próxima revisión automática en %d minutos...",
                    INTERVALO_CICLO_MINUTOS,
                )
                time.sleep(INTERVALO_CICLO_MINUTOS * 60)
            else:
                ahora = datetime.now().strftime("%H:%M")
                logger.info(
                    "Hora actual (%s) fuera de la jornada de %02d:00 a %02d:00. "
                    "En espera (revisando cada 15 min)...",
                    ahora,
                    HORA_INICIO_JORNADA,
                    HORA_FIN_JORNADA,
                )
                time.sleep(15 * 60)
    except KeyboardInterrupt:
        logger.info("Jornada continua detenida manualmente por el usuario.")


def parsear_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Orquestador de búsqueda de empleo y postulación automática en San Miguel."
    )
    parser.add_argument(
        "--jornada",
        action="store_true",
        help="Mantiene el programa buscando ofertas y enviando CVs automáticamente entre las 7:00 AM y las 4:00 PM.",
    )
    parser.add_argument(
        "--forzar-ahora",
        action="store_true",
        help="Ejecuta el ciclo completo inmediatamente aunque sea después de las 4:00 PM.",
    )
    parser.add_argument(
        "--solo-etl",
        action="store_true",
        help="Ejecuta únicamente el scraping, filtrado por CV y guardado en base de datos.",
    )
    parser.add_argument(
        "--solo-email",
        action="store_true",
        help="Procesa únicamente la cola pendiente de correos electrónicos (SMTP).",
    )
    parser.add_argument(
        "--solo-whatsapp",
        action="store_true",
        help="Procesa únicamente la cola pendiente de WhatsApp Web.",
    )
    parser.add_argument(
        "--empresas",
        action="store_true",
        help="Muestra el directorio de empresas, datos de contacto y exporta reporte_empresas.csv.",
    )
    parser.add_argument(
        "--marcar-entrevista",
        type=str,
        metavar="EMPRESA_O_CODIGO",
        help="Marca que una empresa sí te llamó a entrevista (puedes buscar por nombre o código corto).",
    )
    parser.add_argument(
        "--notas",
        type=str,
        default="",
        help="Notas adicionales al marcar una entrevista (ej. fecha, hora o nombre del reclutador).",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Prueba el filtro de CV y guardado de empresas con datos simulados sin enviar mensajes.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parsear_argumentos()

    if args.empresas:
        mostrar_resumen_empresas()
    elif args.marcar_entrevista:
        inicializar_bd()
        actualizadas = registrar_respuesta_entrevista(
            criterio=args.marcar_entrevista,
            llamaron=True,
            notas=args.notas,
        )
        print(
            f"Se actualizaron {actualizadas} vacante(s) con llamaron_entrevista = 'SI'."
        )
        mostrar_resumen_empresas()
    elif args.demo:
        ejecutar_flujo_completo(modo_demo=True)
    elif args.jornada:
        ejecutar_jornada_continua()
    elif args.solo_etl:
        ejecutar_flujo_completo(
            ejecutar_etl=True,
            ejecutar_email=False,
            ejecutar_whatsapp=False,
            respetar_horario=False,
        )
    elif args.solo_email:
        ejecutar_flujo_completo(
            ejecutar_etl=False,
            ejecutar_email=True,
            ejecutar_whatsapp=False,
            respetar_horario=not args.forzar_ahora,
        )
    elif args.solo_whatsapp:
        ejecutar_flujo_completo(
            ejecutar_etl=False,
            ejecutar_email=False,
            ejecutar_whatsapp=True,
            respetar_horario=not args.forzar_ahora,
        )
    else:
        ejecutar_flujo_completo(respetar_horario=not args.forzar_ahora)
