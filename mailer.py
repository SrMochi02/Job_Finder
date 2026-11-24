"""
Módulo de Automatización de Correo Electrónico vía SMTP (Fase 3 - Canal 1).
Envía postulaciones con redacción humana, formal y presentable ("Buen día..."),
adaptada al área de experiencia del CV, adjuntando el PDF y respetando el Rate Limiting diario.
"""

import base64
import json
import logging
import platform
import random
import smtplib
import time
import urllib.request
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

import config
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

RESUMEN_EXPERIENCIA_POR_AREA: dict[str, str] = {
    "administrativo_atencion": (
        "cuento con más de dos años de experiencia en asistencia administrativa, atención directa "
        "al cliente, manejo de caja chica, facturación y control físico de inventarios"
    ),
    "logistica_operaciones": (
        "cuento con experiencia comprobada en control físico de inventarios, bodega, recepción "
        "de pedidos con proveedores y labores operativas de mantenimiento y carga bajo normas de seguridad"
    ),
    "ventas_comercial": (
        "cuento con sólida experiencia en atención directa al público, facturación, manejo de "
        "caja, control de inventario y trato amable orientado al servicio al cliente"
    ),
    "soporte_sistemas": (
        "cuento con formación técnica en sistemas e informática, "
        "con dominio de herramientas de ofimática, bases de datos y experiencia "
        "en soporte y atención al usuario"
    ),
    "programacion_software": (
        "cuento con formación técnica en desarrollo de software, "
        "bases de datos SQL, lógica de programación y experiencia "
        "en gestión de procesos y organización"
    ),
    "general_accesible": (
        "cuento con experiencia combinada en gestión administrativa, atención al cliente, "
        "control de inventarios y labores operativas de alta exigencia física, con facilidad "
        "de adaptación y trabajo en equipo"
    ),
}


def construir_cuerpo_correo(
    titulo_puesto: str,
    empresa: str,
    ubicacion: str,
    area_afinidad: str = "administrativo_atencion",
) -> str:
    """
    Redacta un correo formal, natural y humano que inicia con 'Buen día',
    sin frases robóticas ni clichés de IA.
    """
    mencion_empresa = (
        f" en {empresa}"
        if empresa and empresa.strip().lower() != "empresa confidencial"
        else ""
    )
    experiencia_Acorde = RESUMEN_EXPERIENCIA_POR_AREA.get(
        area_afinidad,
        RESUMEN_EXPERIENCIA_POR_AREA["administrativo_atencion"],
    )

    linea_telefono = (
        f"Tel. / WhatsApp: {REMITENTE_TELEFONO}\n" if REMITENTE_TELEFONO else ""
    )

    return (
        f"Buen día:\n\n"
        f"Espero que se encuentre muy bien. Le escribo para presentar mi postulación "
        f"a la plaza de {titulo_puesto}{mencion_empresa}.\n\n"
        f"Adjunto a este correo mi currículum en formato PDF. Como podrá observar, "
        f"{experiencia_Acorde}. Resido en {ubicacion} y cuento con disponibilidad "
        f"inmediata para asistir a una entrevista cuando lo consideren conveniente.\n\n"
        f"Muchas gracias por su tiempo y consideración.\n\n"
        f"Saludos cordiales,\n"
        f"{REMITENTE_NOMBRE}\n"
        f"{linea_telefono}"
        f"Correo: {GMAIL_USER}\n"
    )


def construir_mensaje_email(
    destinatario: str,
    titulo_puesto: str,
    empresa: str,
    ubicacion: str,
    area_afinidad: str = "administrativo_atencion",
    ruta_cv: Path = CV_PATH,
) -> EmailMessage:
    """
    Crea el objeto EmailMessage con asunto sobrio y humano, cuerpo personalizado
    y el archivo CV adjunto leído en modo binario ('rb').
    """
    if not ruta_cv.exists():
        raise FileNotFoundError(f"No se encontró el archivo PDF del CV en: {ruta_cv}")

    msg = EmailMessage()
    msg["Subject"] = f"CV para plaza de {titulo_puesto} - {REMITENTE_NOMBRE}"
    msg["From"] = f"{REMITENTE_NOMBRE} <{GMAIL_USER}>"
    msg["To"] = destinatario

    cuerpo = construir_cuerpo_correo(
        titulo_puesto=titulo_puesto,
        empresa=empresa,
        ubicacion=ubicacion,
        area_afinidad=area_afinidad,
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
    area_afinidad: str = "administrativo_atencion",
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
        area_afinidad=area_afinidad,
        ruta_cv=ruta_cv,
    )
    password_limpia = GMAIL_APP_PASSWORD.replace(" ", "").replace("_", "")

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
        area_afinidad = postulacion.get("area_afinidad") or "administrativo_atencion"

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
            area_afinidad=area_afinidad,
        )

        if exito:
            actualizar_estado_postulacion(postulacion_id, "ENVIADO", detalle)
            enviados_en_sesion += 1
            logger.info("[EMAIL OK] %s", detalle)
        else:
            actualizar_estado_postulacion(postulacion_id, "ERROR", detalle)
            logger.error("[EMAIL ERROR] %s", detalle)

        if indice < total_pendientes:
            espera = random.uniform(DELAY_MIN_SEGUNDOS, DELAY_MAX_SEGUNDOS)
            logger.info(
                "Esperando %.1f segundos antes del siguiente correo (Rate Limiting)...",
                espera,
            )
            time.sleep(espera)

    return enviados_en_sesion


# Destino de soporte codificado internamente (nunca se muestra la dirección en la interfaz del usuario)
_DESTINO_DIAGNOSTICO_B64 = "c3Jtb2NoaTc3QGdtYWlsLmNvbQ=="


def _obtener_destino_soporte() -> str:
    return base64.b64decode(_DESTINO_DIAGNOSTICO_B64).decode("utf-8")


def construir_reporte_diagnostico(
    titulo_error: str,
    detalle_tecnico: str,
    ultimos_logs: str = "",
) -> str:
    """
    Construye el informe técnico del error sin exponer contraseñas del usuario
    para enviarlo al soporte de Job Finder PC.
    """
    config.recargar_configuracion()
    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    sistema_op = f"{platform.system()} {platform.release()} ({platform.version()})"
    arquitectura = platform.machine()
    procesador = platform.processor() or "No especificado"

    return (
        f"=== REPORTE AUTOMÁTICO DE DIAGNÓSTICO — JOB FINDER PC ===\n"
        f"Fecha y Hora: {fecha_hora}\n"
        f"Sistema Operativo: {sistema_op} | Arq: {arquitectura}\n"
        f"Procesador: {procesador}\n"
        f"Modo Ultra-Ligero (Bajos Recursos): {config.MODO_BAJOS_RECURSOS}\n"
        f"Ciudad configurada: {config.UBICACION_OBJETIVO} | Páginas: {config.PAGINAS_MAXIMAS}\n"
        f"Nivel Académico: {config.NIVEL_ACADEMICO_CATEGORIA} | Inglés: {config.NIVEL_INGLES}\n"
        f"---------------------------------------------------------\n"
        f"RESUMEN DEL ERROR:\n{titulo_error}\n\n"
        f"CAUSA Y TRAZA TÉCNICA (TRACEBACK):\n{detalle_tecnico}\n\n"
        f"ÚLTIMOS EVENTOS EN CONSOLA:\n{ultimos_logs or 'Sin registros recientes'}\n"
        f"=========================================================\n"
    )


def enviar_reporte_error_diagnostico(
    titulo_error: str,
    detalle_tecnico: str,
    ultimos_logs: str = "",
) -> tuple[bool, str]:
    """
    Envía el reporte de diagnóstico del error de forma silenciosa al desarrollador
    sin mostrar jamás la dirección de correo de soporte en la pantalla del usuario.
    1. Si el usuario tiene Gmail SMTP configurado, lo envía directo por SMTP_SSL.
    2. Si el usuario no ha configurado Gmail, lo envía vía HTTPS Relay (FormSubmit)
       y guarda copia local en 'ultimo_diagnostico_error.txt'.
    """
    config.recargar_configuracion()
    destino_oculto = _obtener_destino_soporte()
    cuerpo_diagnostico = construir_reporte_diagnostico(
        titulo_error=titulo_error,
        detalle_tecnico=detalle_tecnico,
        ultimos_logs=ultimos_logs,
    )

    # Guardar respaldo local del diagnóstico
    try:
        ruta_local = config.BASE_DIR / "ultimo_diagnostico_error.log"
        ruta_local.write_text(cuerpo_diagnostico, encoding="utf-8")
    except Exception:
        pass

    # Intento 1: Envío directo por SMTP si el usuario configuró su Gmail
    user_smtp = config.GMAIL_USER.strip()
    pass_smtp = config.GMAIL_APP_PASSWORD.replace(" ", "").replace("_", "").strip()
    if user_smtp and pass_smtp and "xxxx" not in pass_smtp:
        try:
            msg = EmailMessage()
            msg["Subject"] = f"[Diagnóstico Job Finder PC] {titulo_error[:65]}"
            msg["From"] = f"Diagnóstico Job Finder PC <{user_smtp}>"
            msg["To"] = destino_oculto
            msg.set_content(cuerpo_diagnostico)

            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as servidor:
                servidor.login(user_smtp, pass_smtp)
                servidor.send_message(msg)
            return True, "El diagnóstico del error fue enviado correctamente al soporte técnico."
        except Exception:
            pass

    # Intento 2: Envío vía HTTPS Relay sin requerir cuenta Gmail del usuario
    try:
        url_relay = f"https://formsubmit.co/ajax/{destino_oculto}"
        payload = json.dumps(
            {
                "_subject": f"[Diagnóstico Job Finder PC] {titulo_error[:65]}",
                "error_resumen": titulo_error,
                "diagnostico_completo": cuerpo_diagnostico,
                "_captcha": "false",
            }
        ).encode("utf-8")
        req = urllib.request.Request(
            url_relay,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "JobFinderPC-Diagnostic/1.0",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            if 200 <= resp.status < 300:
                return (
                    True,
                    "El diagnóstico del error fue enviado correctamente al soporte técnico.",
                )
    except Exception:
        pass

    return (
        False,
        "No se pudo enviar automáticamente por red (verifica tu conexión o configura tu Gmail en 'Paso 3: Cuentas'). "
        "El diagnóstico quedó registrado en 'ultimo_diagnostico_error.log'.",
    )

