"""
Módulo de Automatización de WhatsApp Web con Cautela (Fase 4 - Canal 2).
Utiliza un contexto persistente de Playwright para conservar la sesión tras escanear el QR,
redacta un saludo humano y formal ("Buen día..."), adjunta el CV en PDF mediante input[type="file"]
y limita estrictamente los envíos diarios (máximo 5-8 mensajes por día).
"""

import logging
import random
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from playwright.sync_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from config import (
    CV_PATH,
    DELAY_MAX_SEGUNDOS,
    DELAY_MIN_SEGUNDOS,
    MAX_WHATSAPP_POR_DIA,
    REMITENTE_NOMBRE,
    REMITENTE_TELEFONO,
    WHATSAPP_SESSION_DIR,
)
from database import (
    actualizar_estado_postulacion,
    contar_envios_hoy,
    obtener_postulaciones_pendientes,
)

logger = logging.getLogger(__name__)

SELECTOR_CAJA_MENSAJE = (
    "footer div[contenteditable='true'][data-tab], "
    "div[title='Escribe un mensaje'], "
    "div[aria-placeholder='Escribe un mensaje']"
)
SELECTOR_BOTON_ADJUNTAR = (
    "span[data-icon='plus'], "
    "span[data-icon='attach-menu-plus'], "
    "div[title='Adjuntar'], "
    "button[aria-label='Adjuntar']"
)
SELECTOR_INPUT_DOCUMENTO = "input[type='file'][accept='*']"
SELECTOR_INPUT_ARCHIVO_GENERICO = "input[type='file']"
SELECTOR_BOTON_ENVIAR = (
    "span[data-icon='send'], "
    "div[aria-label='Enviar'], "
    "button[aria-label='Enviar']"
)


def construir_mensaje_whatsapp(titulo_puesto: str, empresa: str, ubicacion: str) -> str:
    """
    Construye un saludo formal, directo y 100% humano ('Buen día...'),
    sin formato robótico ni asteriscos artificiales.
    """
    mencion_empresa = (
        f" en {empresa}"
        if empresa and empresa.strip().lower() != "empresa confidencial"
        else ""
    )
    return (
        f"Buen día, le saluda {REMITENTE_NOMBRE}. "
        f"Vi su publicación para la plaza de {titulo_puesto}{mencion_empresa} "
        f"y por este medio le comparto mi currículum en PDF para su consideración. "
        f"Resido en {ubicacion} y cuento con disponibilidad inmediata. "
        f"Muchas gracias por su tiempo, quedo atento a sus comentarios."
    )


def enviar_whatsapp_en_pagina(
    pagina: Page,
    telefono_503: str,
    titulo_puesto: str,
    empresa: str,
    ubicacion: str,
    ruta_cv: Path = CV_PATH,
) -> tuple[bool, str]:
    """
    Navega a la URL de envío directo en WhatsApp Web para el número 503XXXXXXXX,
    espera la carga explícita del cuadro de chat con wait_for_selector,
    adjunta el PDF usando input[type='file'] sin abrir diálogo del SO y pulsa Enviar.
    """
    if not ruta_cv.exists():
        return False, f"No se encontró el archivo PDF del CV en: {ruta_cv}"

    texto_plano = construir_mensaje_whatsapp(titulo_puesto, empresa, ubicacion)
    mensaje_codificado = quote(texto_plano)
    url_destino = (
        f"https://web.whatsapp.com/send?phone={telefono_503}&text={mensaje_codificado}"
    )

    try:
        pagina.goto(url_destino, wait_until="domcontentloaded", timeout=45000)

        # Esperar explícitamente a que cargue el cuadro de texto (permite escanear QR la 1ra vez)
        pagina.wait_for_selector(SELECTOR_CAJA_MENSAJE, timeout=90000)

        boton_adjuntar = pagina.wait_for_selector(
            SELECTOR_BOTON_ADJUNTAR, timeout=15000
        )
        if not boton_adjuntar:
            return False, "No se encontró el botón de adjuntar (clip/plus)"
        boton_adjuntar.click()

        input_file = pagina.query_selector(SELECTOR_INPUT_DOCUMENTO)
        if not input_file:
            input_file = pagina.wait_for_selector(
                SELECTOR_INPUT_ARCHIVO_GENERICO, state="attached", timeout=10000
            )
        if not input_file:
            return False, "No se encontró el elemento input[type='file'] en WhatsApp Web"

        input_file.set_input_files(str(ruta_cv.resolve()))

        boton_enviar = pagina.wait_for_selector(SELECTOR_BOTON_ENVIAR, timeout=20000)
        if not boton_enviar:
            return False, "No apareció el botón de enviar tras adjuntar el PDF"

        boton_enviar.click()

        pagina.wait_for_selector(SELECTOR_CAJA_MENSAJE, timeout=15000)

        caja_texto = pagina.query_selector(SELECTOR_CAJA_MENSAJE)
        if caja_texto and (caja_texto.inner_text() or "").strip():
            caja_texto.press("Enter")

        return True, f"WhatsApp con CV adjunto enviado exitosamente a {telefono_503}"

    except PlaywrightTimeoutError as exc:
        return (
            False,
            f"Tiempo de espera agotado en WhatsApp Web para {telefono_503}: {exc}",
        )
    except Exception as exc:
        return False, f"Error inesperado en WhatsApp Web para {telefono_503}: {exc}"


def _lanzar_contexto_whatsapp(p: Any, directorio_sesion: Path) -> Any:
    """Lanza el navegador persistente para WhatsApp Web con banderas limpias."""
    directorio_sesion.mkdir(parents=True, exist_ok=True)
    opciones = {
        "user_data_dir": str(directorio_sesion),
        "headless": False,
        "viewport": {"width": 1280, "height": 800},
        "ignore_default_args": ["--enable-automation"],
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-default-browser-check",
        ],
    }
    for canal in ("chrome", "msedge"):
        try:
            return p.chromium.launch_persistent_context(channel=canal, **opciones)
        except Exception:
            continue
    return p.chromium.launch_persistent_context(**opciones)


def iniciar_sesion_whatsapp(
    directorio_sesion: Path = WHATSAPP_SESSION_DIR,
    esperar_cierre_navegador: bool = False,
) -> None:
    """
    Abre WhatsApp Web en el perfil persistente (whatsapp_session/) para que el usuario
    escanee el código QR con calma una sola vez y deje sincronizados sus chats.
    """
    logger.info(
        "Abriendo WhatsApp Web en %s para vincular código QR...",
        directorio_sesion,
    )
    with sync_playwright() as p:
        try:
            contexto = _lanzar_contexto_whatsapp(p, directorio_sesion)
        except Exception as exc:
            logger.error(
                "No se pudo abrir WhatsApp Web porque otra ventana ya está usando la sesión: %s",
                exc,
            )
            return

        pagina = contexto.pages[0] if contexto.pages else contexto.new_page()
        pagina.goto("https://web.whatsapp.com/", wait_until="domcontentloaded")
        if esperar_cierre_navegador:
            logger.info(
                "Escanea el código QR en WhatsApp Web, espera a que carguen tus chats y cierra la ventana del navegador para guardar la sesión."
            )
            try:
                while contexto.pages:
                    time.sleep(1.0)
            except Exception:
                pass
            finally:
                try:
                    contexto.close()
                except Exception:
                    pass
        else:
            print("\n" + "=" * 80)
            print(
                f"1. Escanea el código QR en la ventana de WhatsApp Web con tu celular ({REMITENTE_TELEFONO or 'tu número'})."
            )
            print("2. Espera unos segundos a que carguen tus chats en pantalla.")
            print("3. Cuando ya veas tus chats cargados, vuelve a esta ventana negra y presiona ENTER.")
            print("=" * 80 + "\n")
            try:
                input("Presiona ENTER cuando tu WhatsApp Web ya esté vinculado y cargado...")
            except EOFError:
                time.sleep(30)
            finally:
                contexto.close()
    logger.info("Sesión de WhatsApp Web guardada exitosamente en %s", directorio_sesion)


def procesar_cola_whatsapp(
    max_diario: int = MAX_WHATSAPP_POR_DIA,
    directorio_sesion: Path = WHATSAPP_SESSION_DIR,
    ruta_cv: Path = CV_PATH,
) -> int:
    """
    Procesa las postulaciones pendientes del canal WHATSAPP usando launch_persistent_context.
    Respeta la regla de supervivencia: máximo 5-8 mensajes por día.
    """
    if not ruta_cv.exists():
        logger.warning(
            "Canal WHATSAPP omitido: no existe el archivo CV en %s", ruta_cv
        )
        return 0

    limite_seguro = min(max_diario, 8)
    enviados_hoy = contar_envios_hoy("WHATSAPP")
    cupo_restante = max(0, limite_seguro - enviados_hoy)

    if cupo_restante == 0:
        logger.info(
            "Límite diario de supervivencia en WhatsApp alcanzado (%d/%d enviados hoy).",
            enviados_hoy,
            limite_seguro,
        )
        return 0

    pendientes = obtener_postulaciones_pendientes("WHATSAPP", limite=cupo_restante)
    if not pendientes:
        logger.info("No hay postulaciones pendientes por WhatsApp.")
        return 0

    directorio_sesion.mkdir(parents=True, exist_ok=True)
    enviados_en_sesion = 0
    total_pendientes = len(pendientes)

    with sync_playwright() as p:
        contexto = _lanzar_contexto_whatsapp(p, directorio_sesion)
        pagina = contexto.pages[0] if contexto.pages else contexto.new_page()

        try:
            for indice, postulacion in enumerate(pendientes, start=1):
                postulacion_id = postulacion["postulacion_id"]
                telefono = postulacion["contacto_destino"]
                titulo = postulacion["titulo"]
                empresa = postulacion["empresa"]
                ubicacion = postulacion["ubicacion"]

                logger.info(
                    "[WHATSAPP %d/%d] Enviando postulación para '%s' (%s) -> %s",
                    indice,
                    total_pendientes,
                    titulo,
                    empresa,
                    telefono,
                )

                exito, detalle = enviar_whatsapp_en_pagina(
                    pagina=pagina,
                    telefono_503=telefono,
                    titulo_puesto=titulo,
                    empresa=empresa,
                    ubicacion=ubicacion,
                    ruta_cv=ruta_cv,
                )

                if exito:
                    actualizar_estado_postulacion(postulacion_id, "ENVIADO", detalle)
                    enviados_en_sesion += 1
                    logger.info("[WHATSAPP OK] %s", detalle)
                else:
                    actualizar_estado_postulacion(postulacion_id, "ERROR", detalle)
                    logger.error("[WHATSAPP ERROR] %s", detalle)

                if indice < total_pendientes:
                    espera = random.uniform(
                        max(35.0, DELAY_MIN_SEGUNDOS), max(95.0, DELAY_MAX_SEGUNDOS)
                    )
                    logger.info(
                        "Pausa anti-bloqueo de %.1f segundos antes del siguiente WhatsApp...",
                        espera,
                    )
                    time.sleep(espera)
        finally:
            contexto.close()

    return enviados_en_sesion
