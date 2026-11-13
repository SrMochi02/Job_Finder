"""
Orquestador Principal (Fase 5).
Une todo el flujo lineal:
Scrapear -> Parsear -> Guardar nuevas en BD -> Consultar pendientes ->
Enviar correos -> Enviar WhatsApp -> Actualizar estados.
"""

import argparse
import logging
import sys
from typing import Any

from database import (
    contar_envios_hoy,
    guardar_vacante,
    inicializar_bd,
    obtener_postulaciones_pendientes,
    registrar_postulacion_pendiente,
)
from mailer import procesar_cola_correos
from parser import es_oferta_excluida, extraer_contactos_oferta
from scraper import ejecutar_scraping_todos_los_portales
from whatsapp import procesar_cola_whatsapp

# Configuración de logging en consola y archivo local
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("jobfinder.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("orquestador")


def procesar_ofertas_extraidas(ofertas: list[dict[str, Any]]) -> dict[str, int]:
    """
    Recibe la lista de ofertas del scraper, aplica el parser de Regex para extraer
    correos y números salvadoreños (503XXXXXXXX), y guarda tanto las vacantes como
    las postulaciones pendientes en SQLite evitando duplicados.
    """
    estadisticas = {
        "vacantes_nuevas": 0,
        "vacantes_duplicadas": 0,
        "vacantes_excluidas": 0,
        "emails_agendados": 0,
        "whatsapp_agendados": 0,
    }

    for oferta in ofertas:
        excluida, palabra = es_oferta_excluida(
            oferta["titulo"], oferta.get("empresa", "")
        )
        if excluida:
            estadisticas["vacantes_excluidas"] += 1
            logger.info(
                "Ignorando vacante del sector excluido ('%s'): %s",
                palabra,
                oferta["titulo"],
            )
            continue

        vacante_id, es_nueva = guardar_vacante(
            titulo=oferta["titulo"],
            empresa=oferta["empresa"],
            ubicacion=oferta["ubicacion"],
            url_original=oferta["url_original"],
            descripcion_cruda=oferta["descripcion_cruda"],
            portal=oferta.get("portal", "Computrabajo"),
        )

        if es_nueva:
            estadisticas["vacantes_nuevas"] += 1
        else:
            estadisticas["vacantes_duplicadas"] += 1

        # Extraer correos y teléfonos salvadoreños desde la descripción cruda
        contactos = extraer_contactos_oferta(oferta["descripcion_cruda"])

        for correo in contactos["emails"]:
            if registrar_postulacion_pendiente(vacante_id, "EMAIL", correo):
                estadisticas["emails_agendados"] += 1
                logger.info(
                    "Nuevo correo detectado para '%s' (%s): %s",
                    oferta["titulo"],
                    oferta["empresa"],
                    correo,
                )

        for numero_wa in contactos["whatsapp"]:
            if registrar_postulacion_pendiente(vacante_id, "WHATSAPP", numero_wa):
                estadisticas["whatsapp_agendados"] += 1
                logger.info(
                    "Nuevo WhatsApp detectado para '%s' (%s): %s",
                    oferta["titulo"],
                    oferta["empresa"],
                    numero_wa,
                )

    return estadisticas


def ejecutar_flujo_completo(
    ejecutar_etl: bool = True,
    ejecutar_email: bool = True,
    ejecutar_whatsapp: bool = True,
    modo_demo: bool = False,
) -> None:
    """Ejecuta de principio a fin el flujo lineal de Job Finder."""
    logger.info("=== INICIANDO FLUJO DE AUTOMATIZACIÓN JOB FINDER (SAN MIGUEL) ===")

    # Paso 1: Inicializar Base de Datos
    inicializar_bd()

    # Paso 2 y 3: Scrapear, Parsear y Guardar en BD
    if modo_demo:
        logger.info("Ejecutando en modo DEMO con oferta simulada de San Miguel...")
        ofertas_demo = [
            {
                "portal": "Computrabajo",
                "titulo": "Desarrollador Python / Automatización",
                "empresa": "Tecnologías de Oriente S.A. de C.V.",
                "ubicacion": "San Miguel",
                "url_original": "https://sv.computrabajo.com/ofertas-de-trabajo/oferta-demo-san-miguel",
                "descripcion_cruda": (
                    "Buscamos talento en San Miguel con conocimientos en Python y SQL. "
                    "Interesados enviar CV al correo reclutamiento@tecnologiasoriente.com.sv "
                    "o escribir por WhatsApp al +503 7890-1234."
                ),
            }
        ]
        resumen_etl = procesar_ofertas_extraidas(ofertas_demo)
        logger.info("Resumen ETL (Demo): %s", resumen_etl)
    elif ejecutar_etl:
        ofertas = ejecutar_scraping_todos_los_portales()
        resumen_etl = procesar_ofertas_extraidas(ofertas)
        logger.info("Resumen ETL: %s", resumen_etl)

    # Paso 4: Consultar pendientes actuales
    pendientes_email = len(obtener_postulaciones_pendientes("EMAIL"))
    pendientes_wa = len(obtener_postulaciones_pendientes("WHATSAPP"))
    logger.info(
        "Estado de cola antes de envíos -> EMAIL pendientes: %d | WHATSAPP pendientes: %d",
        pendientes_email,
        pendientes_wa,
    )

    if modo_demo:
        logger.info(
            "Modo DEMO finalizado sin enviar correos ni mensajes reales. Base de datos verificada."
        )
        return

    # Paso 5: Enviar Correos (Canal 1 - SMTP)
    if ejecutar_email:
        enviados_email = procesar_cola_correos()
        logger.info("Correos enviados en esta sesión: %d", enviados_email)

    # Paso 6: Enviar WhatsApp (Canal 2 - Playwright Persistente)
    if ejecutar_whatsapp:
        enviados_wa = procesar_cola_whatsapp()
        logger.info("Mensajes de WhatsApp enviados en esta sesión: %d", enviados_wa)

    # Paso 7: Resumen final del día
    logger.info(
        "=== FLUJO COMPLETADO | Total hoy -> EMAIL: %d | WHATSAPP: %d ===",
        contar_envios_hoy("EMAIL"),
        contar_envios_hoy("WHATSAPP"),
    )


def parsear_argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Orquestador de búsqueda de empleo y postulación automática en San Miguel."
    )
    parser.add_argument(
        "--solo-etl",
        action="store_true",
        help="Ejecuta únicamente el scraping, parseo y guardado en base de datos sin enviar mensajes.",
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
        "--demo",
        action="store_true",
        help="Inserta una oferta de prueba en la base de datos y verifica el flujo sin enviar mensajes.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parsear_argumentos()

    if args.demo:
        ejecutar_flujo_completo(modo_demo=True)
    elif args.solo_etl:
        ejecutar_flujo_completo(
            ejecutar_etl=True, ejecutar_email=False, ejecutar_whatsapp=False
        )
    elif args.solo_email:
        ejecutar_flujo_completo(
            ejecutar_etl=False, ejecutar_email=True, ejecutar_whatsapp=False
        )
    elif args.solo_whatsapp:
        ejecutar_flujo_completo(
            ejecutar_etl=False, ejecutar_email=False, ejecutar_whatsapp=True
        )
    else:
        ejecutar_flujo_completo()
