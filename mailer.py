"""
Módulo de Automatización de Correo Electrónico vía SMTP (Fase 3 - Canal 1).
Envía postulaciones personalizadas con el CV adjunto en PDF, respetando el
límite diario (Rate Limiting) y pausas aleatorias humanas entre cada envío.
"""

import logging
import random
import smtplib
import time
from email.message import EmailMessage
from pathlib import Path

from config import (
    CV_PATH,
    DELAY_MAX_SEGUNDOS,
    DELAY_MIN_SEGUNDOS,
    GMAIL_APP_PASSWORD,
    GMAIL_USER,
    MAX_EMAILS_POR_DIA,
    REMITENTE_NOMBRE,
    REMITENTE_TELEFONO,
    validar_configuracion_correo,
)
from database import (
    actualizar_estado_postulacion,
    contar_envios_hoy,
    obtener_postulaciones_pendientes,
)

logger = logging.getLogger(__name__)


def construir_cuerpo_correo(titulo_puesto: str, empresa: str, ubicacion: str) -> str:
    """
    Genera una plantilla dinámica y profesional adaptada al nombre de la vacante
    y a la empresa reclutadora en San Miguel.
    """
    destinatario_empresa = (
        f" del equipo de selección de {empresa}"
        if empresa and empresa.lower() != "empresa confidencial"
        else ""
    )
    return (
        f"Estimado/a responsable{destinatario_empresa}:\n\n"
        f"Le saludo cordialmente. Por medio del presente correo presento mi postulación formal "
        f"para la vacante de «{titulo_puesto}» ubicada en {ubicacion}.\n\n"
        f"Adjunto a este mensaje mi Currículum Vitae actualizado en formato PDF para que puedan "
        f"conocer en detalle mi experiencia, formación técnica y disponibilidad inmediata en la zona "
        f"de San Miguel.\n\n"
        f"Quedo a su entera disposición para ampliar cualquier información en una entrevista.\n\n"
        f"Atentamente,\n"
        f"{REMITENTE_NOMBRE}\n"
        f"Teléfono / WhatsApp: {REMITENTE_TELEFONO}\n"
        f"Correo: {GMAIL_USER}\n"
    )


def construir_mensaje_email(
    destinatario: str,
    titulo_puesto: str,
    empresa: str,
    ubicacion: str,
    ruta_cv: Path = CV_PATH,
) -> EmailMessage:
    """
    Crea el objeto EmailMessage con asunto dinámico, cuerpo personalizado
    y el archivo CV adjunto leído en modo binario ('rb').
    """
    if not ruta_cv.exists():
        raise FileNotFoundError(f"No se encontró el archivo PDF del CV en: {ruta_cv}")

    msg = EmailMessage()
    msg["Subject"] = f"Postulación a vacante: {titulo_puesto} - {REMITENTE_NOMBRE}"
    msg["From"] = f"{REMITENTE_NOMBRE} <{GMAIL_USER}>"
    msg["To"] = destinatario

    cuerpo = construir_cuerpo_correo(
        titulo_puesto=titulo_puesto,
        empresa=empresa,
        ubicacion=ubicacion,
    )
    msg.set_content(cuerpo)

    with open(ruta_cv, "rb") as archivo_pdf:
        datos_pdf = archivo_pdf.read()

    msg.add_attachment(
        datos_pdf,
        maintype="application",
        subtype="pdf",
        filename=ruta_cv.name,
    )
    return msg


def enviar_correo_individual(
    destinatario: str,
    titulo_puesto: str,
    empresa: str,
    ubicacion: str,
    usar_ssl: bool = True,
    ruta_cv: Path = CV_PATH,
) -> tuple[bool, str]:
    """
    Envía un correo electrónico individual mediante Gmail SMTP (puerto 465 con SMTP_SSL
    o puerto 587 con STARTTLS). Retorna (exito, mensaje_log).
    """
    msg = construir_mensaje_email(
        destinatario=destinatario,
        titulo_puesto=titulo_puesto,
        empresa=empresa,
        ubicacion=ubicacion,
        ruta_cv=ruta_cv,
    )
    password_limpia = GMAIL_APP_PASSWORD.replace(" ", "")

    try:
        if usar_ssl:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as servidor:
                servidor.login(GMAIL_USER, password_limpia)
                servidor.send_message(msg)
        else:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as servidor:
                servidor.ehlo()
                servidor.starttls()
                servidor.ehlo()
                servidor.login(GMAIL_USER, password_limpia)
                servidor.send_message(msg)

        return True, f"Correo enviado exitosamente a {destinatario}"
    except Exception as exc:
        return False, f"Error SMTP al enviar a {destinatario}: {exc}"


def procesar_cola_correos(max_diario: int = MAX_EMAILS_POR_DIA) -> int:
    """
    Procesa las postulaciones pendientes del canal EMAIL respetando el límite diario
    (10-15 correos/día) y aplicando time.sleep(random.uniform(30, 90)) entre envíos.
    Retorna la cantidad de correos enviados en esta ejecución.
    """
    valido, motivo = validar_configuracion_correo()
    if not valido:
        logger.warning("Canal EMAIL omitido: %s", motivo)
        return 0

    enviados_hoy = contar_envios_hoy("EMAIL")
    cupo_restante = max(0, max_diario - enviados_hoy)

    if cupo_restante == 0:
        logger.info(
            "Límite diario de correos alcanzado (%d/%d enviados hoy).",
            enviados_hoy,
            max_diario,
        )
        return 0

    pendientes = obtener_postulaciones_pendientes("EMAIL", limite=cupo_restante)
    if not pendientes:
        logger.info("No hay postulaciones pendientes por correo electrónico.")
        return 0

    enviados_en_sesion = 0
    total_pendientes = len(pendientes)

    for indice, postulacion in enumerate(pendientes, start=1):
        postulacion_id = postulacion["postulacion_id"]
        destinatario = postulacion["contacto_destino"]
        titulo = postulacion["titulo"]
        empresa = postulacion["empresa"]
        ubicacion = postulacion["ubicacion"]

        logger.info(
            "[EMAIL %d/%d] Enviando postulación para '%s' (%s) -> %s",
            indice,
            total_pendientes,
            titulo,
            empresa,
            destinatario,
        )

        exito, detalle = enviar_correo_individual(
            destinatario=destinatario,
            titulo_puesto=titulo,
            empresa=empresa,
            ubicacion=ubicacion,
        )

        if exito:
            actualizar_estado_postulacion(postulacion_id, "ENVIADO", detalle)
            enviados_en_sesion += 1
            logger.info("[EMAIL OK] %s", detalle)
        else:
            actualizar_estado_postulacion(postulacion_id, "ERROR", detalle)
            logger.error("[EMAIL ERROR] %s", detalle)

        # Pausa aleatoria entre 30 y 90 segundos si aún quedan más correos por enviar
        if indice < total_pendientes:
            espera = random.uniform(DELAY_MIN_SEGUNDOS, DELAY_MAX_SEGUNDOS)
            logger.info(
                "Esperando %.1f segundos antes del siguiente correo (Rate Limiting)...",
                espera,
            )
            time.sleep(espera)

    return enviados_en_sesion
