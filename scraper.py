"""
Módulo de Extracción de Vacantes y Auto-Postulación con Playwright (Fase 2 - ETL).
Incluye:
- Salto instantáneo de vacantes ya guardadas en SQLite (ahorra 90% del tiempo en ciclos repetidos).
- Extracción profunda del cuerpo completo de la oferta (Computrabajo, Encuentra24 y Tecoloco).
- Sesión persistente en portales (portal_session/) para auto-postulación en 1 clic con el botón 'Postularme'.
"""

import logging
import random
import re
import time
from typing import Any
from urllib.parse import urljoin

from playwright.sync_api import (
    Page,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)

from config import (
    AUTO_POSTULAR_PORTAL,
    HEADLESS_SCRAPER,
    PAGINAS_MAXIMAS,
    PORTAL_SESSION_DIR,
    UBICACION_OBJETIVO,
)
from database import existe_vacante, registrar_oferta_descartada
from parser import es_oferta_excluida

logger = logging.getLogger(__name__)

PORTALES_CONFIG: dict[str, dict[str, str]] = {
    "Computrabajo": {
        "base_url": "https://sv.computrabajo.com",
        "url_busqueda": "https://sv.computrabajo.com/empleos-en-san-miguel?p={pagina}",
        "selector_tarjeta": "article.box_offer",
        "selector_titulo_enlace": "h2 a.js-o-link, a.js-o-link",
        "selector_empresa": "p.dFlex a.fc_base, p.fs16.fc_base",
        "selector_ubicacion": "p.fs16.fc_base span.mr10",
        "selector_descripcion_detalle": "div.box_detail, div.bWord, p.mbB, div[field='description']",
    },
    "Encuentra24": {
        "base_url": "https://www.encuentra24.com",
        "url_busqueda": "https://www.encuentra24.com/el-salvador-es/empleos-ofertas-de-trabajos?q=san+miguel&page={pagina}",
        "selector_tarjeta": "article.d3-ad-tile, div.ann-ad-tile",
        "selector_titulo_enlace": "a.d3-ad-tile__description, a.d3-ad-tile__title, div.ann-ad-tile__title a",
        "selector_empresa": "div.d3-ad-tile__Subheader, span.d3-ad-tile__seller",
        "selector_ubicacion": "div.d3-ad-tile__location, span.d3-ad-tile__location",
        "selector_descripcion_detalle": "div.d3-property-about__text, div.ad-info__description, section.d3-property-details",
    },
    "Tecoloco": {
        "base_url": "https://www.tecoloco.com.sv",
        "url_busqueda": "https://www.tecoloco.com.sv/empleos?keywords=San+Miguel&Page={pagina}",
        "selector_tarjeta": "div.module.job-result, div.job-result-item, article.job-item",
        "selector_titulo_enlace": "h2.job-title a, div.job-result-title a, h3 a",
        "selector_empresa": "li.name, span.company-name, div.company",
        "selector_ubicacion": "li.location, span.location",
        "selector_descripcion_detalle": "div.job-description, div.job-details, section.job-description",
    },
}

SELECTORES_BOTON_POSTULAR_COMPUTRABAJO = (
    "a[data-apply-ac], "
    "a.b_primary:has-text('Postularme'), "
    "button.b_primary:has-text('Postularme'), "
    "a:has-text('Postularme'), "
    "button:has-text('Postularme'), "
    "span:has-text('Postularme')"
)


def extraer_texto_completo_oferta(pagina: Page, selector_detalle: str) -> str:
    """
    Extrae el texto completo real de la oferta laboral evitando quedarse únicamente
    con la barra superior de navegación.
    """
    partes_texto: list[str] = []

    try:
        pagina.wait_for_selector(selector_detalle, timeout=3500)
    except PlaywrightTimeoutError:
        pass

    nodos = pagina.query_selector_all(selector_detalle)
    for nodo in nodos:
        txt = (nodo.inner_text() or "").strip()
        if txt and len(txt) > 25:
            partes_texto.append(txt)

    texto_unido = "\n".join(partes_texto).strip()

    if len(texto_unido) < 120:
        cuerpo = pagina.query_selector("body")
        if cuerpo:
            texto_body = (cuerpo.inner_text() or "").strip()
            lineas_utiles = [
                linea.strip()
                for linea in texto_body.splitlines()
                if len(linea.strip()) > 30
            ]
            texto_unido = "\n".join(lineas_utiles)

    return texto_unido


def _determinar_respuesta_cv(pregunta_raw: str) -> dict[str, str]:
    """
    Analiza una pregunta de encuesta de Computrabajo y devuelve la respuesta
    exacta basada en el CV real del postulante (tanto en texto como en opción Sí/No y número).
    """
    q = pregunta_raw.lower()

    # 1. Preguntas sobre licencia o vehículo/moto
    if any(p in q for p in ("licencia", "motocicleta", "moto", "vehículo", "vehiculo", "conducir", "manejar")):
        return {
            "si_no": "no",
            "numero": "0",
            "texto": "No poseo licencia ni vehículo propio, pero resido en San Miguel con total puntualidad y facilidad de transporte.",
        }

    # 2. Preguntas sobre si estudia actualmente (horarios de clases)
    if any(p in q for p in ("estudia actualmente", "estudiando actualmente", "horario de estudio", "clases")):
        return {
            "si_no": "no",
            "numero": "0",
            "texto": "Ya soy egresado de Técnico en Ingeniería en Desarrollo de Software (ITCA FEPADE), por lo que cuento con disponibilidad completa de horario.",
        }

    # 3. Pretensión salarial / salario esperado
    if any(p in q for p in ("salario", "salarial", "pretensión", "pretension", "aspiración", "aspiracion", "cuánto desea ganar", "cuanto espera")):
        return {
            "si_no": "si",
            "numero": "400",
            "texto": "$400 a $450 mensuales (negociable según las responsabilidades del puesto).",
        }

    # 4. Ubicación / Residencia en San Miguel
    if any(p in q for p in ("san miguel", "reside", "vivir", "vive", "domicilio", "ubicación", "ubicacion", "zona")):
        return {
            "si_no": "si",
            "numero": "1",
            "texto": "Sí, resido actualmente en San Miguel, El Salvador.",
        }

    # 5. Disponibilidad inmediata / horarios / fines de semana / turnos
    if any(p in q for p in ("disponibilidad", "horario", "turnos", "fines de semana", "inmediata")):
        return {
            "si_no": "si",
            "numero": "1",
            "texto": "Sí, cuento con disponibilidad inmediata y de horarios en San Miguel.",
        }

    # 6. Experiencia en caja, facturación, inventario, bodega, atención al cliente, ventas o administración
    if any(p in q for p in ("caja", "cajero", "facturación", "facturacion", "efectivo", "cobro", "inventario", "bodega", "almacén", "almacen", "cliente", "administrativ", "ventas")):
        return {
            "si_no": "si",
            "numero": "2",
            "texto": "Sí, cuento con más de 2 años de experiencia comprobada en atención al cliente, manejo y cuadre de caja chica, facturación, control físico de inventarios en bodega y trato con proveedores.",
        }

    # 7. Estudios, sistemas, computación, Excel, Office o inglés
    if any(p in q for p in ("excel", "office", "ofimática", "ofimatica", "computación", "computacion", "sistemas", "software", "inglés", "ingles", "estudio", "título", "titulo")):
        return {
            "si_no": "si",
            "numero": "2",
            "texto": "Sí, soy egresado de Técnico en Ingeniería en Desarrollo de Software (ITCA FEPADE), con dominio de ofimática (Excel, Word), bases de datos SQL e inglés nivel A2.",
        }

    # Respuesta general formal basada en el CV para cualquier otra pregunta abierta
    return {
        "si_no": "si",
        "numero": "2",
        "texto": "Sí, cuento con más de 2 años de experiencia en gestión administrativa, atención al cliente, control de inventarios, caja chica y operaciones en San Miguel, con disponibilidad inmediata.",
    }


def _rellenar_encuesta_y_carta_portal(pagina: Page, titulo_puesto: str) -> None:
    """
    Detecta y responde automáticamente los formularios de preguntas filtro (encuestas)
    y el apartado opcional de Carta de Presentación en Computrabajo usando la información del CV.
    """
    try:
        # 1. Rellenar Carta de Presentación si aparece en pantalla
        input_titulo_carta = pagina.query_selector(
            "input[placeholder*='título de la carta'], input[name*='CoverLetterTitle'], input[id*='CoverLetter']"
        )
        if input_titulo_carta and input_titulo_carta.is_visible():
            input_titulo_carta.fill(f"Postulación a {titulo_puesto} - San Miguel")

        textarea_carta = pagina.query_selector(
            "textarea[placeholder*='cuerpo de la carta'], textarea[name*='CoverLetter'], textarea[id*='CoverLetter']"
        )
        if textarea_carta and textarea_carta.is_visible():
            texto_carta = (
                f"Buen día. Pongo a su disposición mi CV para la vacante de {titulo_puesto}. "
                "Cuento con más de 2 años de experiencia en asistencia administrativa, atención al cliente, "
                "manejo de caja chica, facturación y control físico de inventarios, además de experiencia "
                "operativa en bodega y formación como Técnico en Desarrollo de Software (ITCA FEPADE). "
                "Resido en San Miguel y tengo disponibilidad inmediata. Saludos cordiales."
            )
            textarea_carta.fill(texto_carta)

        # 2. Responder preguntas abiertas (textarea o inputs de texto de encuesta)
        bloques_pregunta = pagina.query_selector_all(
            "div.box_question, div.question, div.field, form div"
        )
        for bloque in bloques_pregunta:
            texto_bloque = (bloque.inner_text() or "").strip()
            if not texto_bloque or len(texto_bloque) > 400:
                continue

            respuesta = _determinar_respuesta_cv(texto_bloque)

            # Si el bloque tiene botones de radio (Sí / No)
            radios = bloque.query_selector_all("input[type='radio']")
            if radios:
                for radio in radios:
                    label_radio = (
                        bloque.evaluate(
                            "(el) => el.parentElement ? el.parentElement.innerText : ''",
                            radio,
                        )
                        or ""
                    ).strip().lower()
                    if respuesta["si_no"] == "si" and ("sí" in label_radio or "si" == label_radio):
                        radio.check()
                        break
                    if respuesta["si_no"] == "no" and "no" in label_radio:
                        radio.check()
                        break

            # Si el bloque tiene un input numérico (ej. años de experiencia o salario)
            input_num = bloque.query_selector("input[type='number']")
            if input_num and input_num.is_visible():
                valor_actual = (input_num.input_value() or "").strip()
                if not valor_actual:
                    input_num.fill(respuesta["numero"])

            # Si el bloque tiene un textarea o input de texto para responder la pregunta
            campo_texto = bloque.query_selector(
                "textarea:not([placeholder*='cuerpo de la carta']), input[type='text']:not([placeholder*='título de la carta'])"
            )
            if campo_texto and campo_texto.is_visible():
                valor_actual = (campo_texto.input_value() or "").strip()
                if not valor_actual:
                    campo_texto.fill(respuesta["texto"])

    except Exception as exc:
        logger.debug("Aviso al rellenar encuesta/carta opcional: %s", exc)


def intentar_postular_en_portal(
    pagina: Page, nombre_portal: str, titulo_puesto: str = "la vacante"
) -> str:
    """
    Intenta hacer clic en el botón 'Postularme' dentro del portal (Computrabajo),
    rellena automáticamente encuestas de filtrado o carta de presentación según el CV,
    y confirma el envío.
    """
    if not AUTO_POSTULAR_PORTAL or nombre_portal != "Computrabajo":
        return "NO"

    try:
        aviso_ya_aplicado = pagina.query_selector(
            "div:has-text('Ya aplicaste a esta oferta'), span:has-text('Ya estás postulado')"
        )
        boton = pagina.query_selector(SELECTORES_BOTON_POSTULAR_COMPUTRABAJO)

        if not boton or not boton.is_visible():
            if aviso_ya_aplicado and aviso_ya_aplicado.is_visible():
                return "SI (Ya postulado)"
            return "NO"

        # Rellenar preguntas filtro si ya aparecen antes de pulsar Postularme
        _rellenar_encuesta_y_carta_portal(pagina, titulo_puesto)

        boton.scroll_into_view_if_needed(timeout=3000)
        boton.click(timeout=5000)
        time.sleep(2.5)

        url_actual = pagina.url.lower()
        if "login" in url_actual or "acceso" in url_actual or "candidato/login" in url_actual:
            return "REQUIERE_LOGIN"

        # Si tras hacer clic se abre una pantalla de encuesta/preguntas o carta de presentación, rellenarla
        _rellenar_encuesta_y_carta_portal(pagina, titulo_puesto)

        boton_confirmar = pagina.query_selector(
            "button.b_primary:has-text('Enviar'), "
            "a.b_primary:has-text('Enviar'), "
            "button:has-text('Enviar CV'), "
            "button:has-text('Postularme'), "
            "button:has-text('Actualizar'), "
            "input[type='submit']"
        )
        if boton_confirmar and boton_confirmar.is_visible():
            try:
                boton_confirmar.click(timeout=4000)
                time.sleep(2.0)
            except Exception:
                pass

        url_post = pagina.url.lower()
        if "login" in url_post or "acceso" in url_post:
            return "REQUIERE_LOGIN"

        return "SI (Auto-postulado)"
    except Exception as exc:
        logger.debug("No se pudo auto-postular en portal: %s", exc)
        return "NO"


def _lanzar_contexto_persistente(p: Any, directorio: Any, headless: bool = False) -> Any:
    """
    Lanza un contexto persistente ocultando las banderas de automatización
    (--enable-automation y AutomationControlled) para que los portales y Google
    no bloqueen el inicio de sesión diciendo que el navegador es inseguro.
    """
    opciones_comunes = {
        "user_data_dir": str(directorio),
        "headless": headless,
        "viewport": {"width": 1280, "height": 800},
        "ignore_default_args": ["--enable-automation"],
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-default-browser-check",
        ],
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
    }
    try:
        return p.chromium.launch_persistent_context(channel="chrome", **opciones_comunes)
    except Exception:
        return p.chromium.launch_persistent_context(**opciones_comunes)


def iniciar_sesion_portales() -> None:
    """
    Abre el navegador con el perfil persistente (portal_session/) en Computrabajo
    para que el usuario inicie sesión una sola vez y quede guardada para las auto-postulaciones.
    """
    PORTAL_SESSION_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(
        "Abriendo navegador persistente en %s para iniciar sesión en Computrabajo...",
        PORTAL_SESSION_DIR,
    )
    with sync_playwright() as p:
        try:
            contexto = _lanzar_contexto_persistente(
                p, PORTAL_SESSION_DIR, headless=False
            )
        except Exception as exc:
            logger.error(
                "No se pudo abrir el navegador porque ya tienes otra ventana de Chromium/JobFinder abierta. "
                "Cierra primero las ventanas abiertas de Chromium e intenta de nuevo. Detalle: %s",
                exc,
            )
            return

        pagina = contexto.pages[0] if contexto.pages else contexto.new_page()
        pagina.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        pagina.goto("https://sv.computrabajo.com/", wait_until="domcontentloaded")
        print("\n" + "=" * 80)
        print("1. Inicia sesión con tu cuenta en la ventana de Computrabajo que se acaba de abrir.")
        print("   (Tip: Puedes entrar con tu correo y contraseña de Computrabajo o con Google).")
        print("2. Cuando ya hayas iniciado sesión y veas tu perfil activo, vuelve aquí y presiona ENTER.")
        print("=" * 80 + "\n")
        try:
            input("Presiona ENTER cuando hayas terminado de iniciar sesión...")
        except EOFError:
            time.sleep(30)
        finally:
            contexto.close()
    logger.info("Sesión de Computrabajo guardada exitosamente en %s", PORTAL_SESSION_DIR)


def ejecutar_scraping_todos_los_portales(
    portales: list[str] | None = None,
    paginas_maximas: int = PAGINAS_MAXIMAS,
    headless: bool = HEADLESS_SCRAPER,
) -> list[dict[str, Any]]:
    """
    Recorre todos los portales configurados usando una única sesión persistente de Playwright,
    saltando ofertas ya existentes en SQLite para máxima velocidad.
    """
    lista_portales = portales or list(PORTALES_CONFIG.keys())
    todas_las_ofertas: list[dict[str, Any]] = []
    urls_vistas: set[str] = set()

    PORTAL_SESSION_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        try:
            contexto = _lanzar_contexto_persistente(
                p, PORTAL_SESSION_DIR, headless=headless
            )
        except Exception as exc:
            logger.error(
                "El navegador persistente ya está abierto en otra ventana. "
                "Cierra la otra ventana de Chromium primero. Detalle: %s",
                exc,
            )
            return []

        pagina = contexto.pages[0] if contexto.pages else contexto.new_page()
        pagina.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )

        try:
            for nombre_portal in lista_portales:
                if nombre_portal not in PORTALES_CONFIG:
                    continue

                cfg = PORTALES_CONFIG[nombre_portal]
                resumenes_ofertas: list[dict[str, str]] = []

                for num_pagina in range(1, paginas_maximas + 1):
                    url_listado = cfg["url_busqueda"].format(pagina=num_pagina)
                    logger.info(
                        "[%s] Navegando a página %d: %s",
                        nombre_portal,
                        num_pagina,
                        url_listado,
                    )

                    try:
                        pagina.goto(
                            url_listado, wait_until="domcontentloaded", timeout=25000
                        )
                        pagina.wait_for_selector(cfg["selector_tarjeta"], timeout=8000)
                    except PlaywrightTimeoutError:
                        logger.info(
                            "[%s] Sin más tarjetas de empleo en la página %d.",
                            nombre_portal,
                            num_pagina,
                        )
                        break
                    except Exception as exc:
                        logger.warning(
                            "[%s] No se pudo cargar página %d: %s",
                            nombre_portal,
                            num_pagina,
                            exc,
                        )
                        break

                    tarjetas = pagina.query_selector_all(cfg["selector_tarjeta"])
                    logger.info(
                        "[%s] Se encontraron %d ofertas en la página %d.",
                        nombre_portal,
                        len(tarjetas),
                        num_pagina,
                    )

                    for tarjeta in tarjetas:
                        nodo_titulo = tarjeta.query_selector(
                            cfg["selector_titulo_enlace"]
                        )
                        if not nodo_titulo:
                            continue

                        titulo = (
                            (nodo_titulo.inner_text() or "").replace("\n", " ").strip()
                        )
                        href = nodo_titulo.get_attribute("href") or ""
                        if not titulo or not href:
                            continue

                        url_completa = urljoin(cfg["base_url"], href)
                        if url_completa in urls_vistas:
                            continue
                        urls_vistas.add(url_completa)

                        nodo_empresa = tarjeta.query_selector(cfg["selector_empresa"])
                        empresa_cruda = (
                            nodo_empresa.inner_text().strip()
                            if nodo_empresa
                            else "Empresa Confidencial"
                        )
                        empresa = (
                            re.sub(r"^\d+(?:[.,]\d+)?\s*", "", empresa_cruda)
                            .replace("\n", " ")
                            .strip()
                            or "Empresa Confidencial"
                        )

                        nodo_ubicacion = tarjeta.query_selector(
                            cfg["selector_ubicacion"]
                        )
                        ubicacion_cruda = (
                            nodo_ubicacion.inner_text().strip()
                            if nodo_ubicacion
                            else UBICACION_OBJETIVO
                        )
                        ubicacion = (
                            UBICACION_OBJETIVO
                            if re.fullmatch(r"\d+(?:[.,]\d+)?", ubicacion_cruda)
                            else ubicacion_cruda.replace("\n", " ").strip()
                        )

                        # 1. Filtrar por título/empresa antes de abrir
                        excluida, motivo_exclusion = es_oferta_excluida(titulo, empresa)
                        if excluida:
                            logger.info(
                                "[%s] Descartada en listado (%s): %s (%s)",
                                nombre_portal,
                                motivo_exclusion,
                                titulo,
                                empresa,
                            )
                            continue

                        # 2. Verificar si ya existe en SQLite para no volver a abrirla
                        if existe_vacante(
                            titulo=titulo, empresa=empresa, portal=nombre_portal
                        ):
                            logger.info(
                                "[%s] Saltando oferta ya registrada en BD: %s (%s)",
                                nombre_portal,
                                titulo,
                                empresa,
                            )
                            continue

                        resumenes_ofertas.append(
                            {
                                "portal": nombre_portal,
                                "titulo": titulo,
                                "empresa": empresa,
                                "ubicacion": ubicacion,
                                "url_original": url_completa,
                            }
                        )

                    time.sleep(random.uniform(1.5, 3.0))

                # Abrir únicamente las ofertas NUEVAS que no estaban en la base de datos
                for item in resumenes_ofertas:
                    url_oferta = item["url_original"]
                    logger.info(
                        "[%s] Extrayendo detalle de oferta NUEVA: %s (%s)",
                        nombre_portal,
                        item["titulo"],
                        item["empresa"],
                    )
                    try:
                        pagina.goto(
                            url_oferta, wait_until="domcontentloaded", timeout=20000
                        )
                        descripcion_cruda = extraer_texto_completo_oferta(
                            pagina, cfg["selector_descripcion_detalle"]
                        )
                    except Exception as exc:
                        logger.error(
                            "[%s] Error al abrir detalle %s: %s",
                            nombre_portal,
                            url_oferta,
                            exc,
                        )
                        continue

                    if not descripcion_cruda:
                        continue

                    excluida_desc, motivo_desc = es_oferta_excluida(
                        item["titulo"], item["empresa"], descripcion_cruda
                    )
                    if excluida_desc:
                        logger.info(
                            "[%s] Descartada al leer descripción (%s): %s",
                            nombre_portal,
                            motivo_desc,
                            item["titulo"],
                        )
                        registrar_oferta_descartada(
                            titulo=item["titulo"],
                            empresa=item["empresa"],
                            portal=nombre_portal,
                            motivo=motivo_desc,
                        )
                        continue

                    # Intentar auto-postulación en 1 clic (incluyendo encuestas/carta) si la oferta es válida
                    estado_portal = intentar_postular_en_portal(
                        pagina, nombre_portal, item["titulo"]
                    )
                    if estado_portal.startswith("SI"):
                        logger.info(
                            "[%s] Auto-postulación en portal exitosa: %s (%s)",
                            nombre_portal,
                            item["titulo"],
                            estado_portal,
                        )

                    todas_las_ofertas.append(
                        {
                            **item,
                            "descripcion_cruda": descripcion_cruda,
                            "postulado_en_portal": estado_portal,
                        }
                    )
                    time.sleep(random.uniform(1.5, 3.0))

        except KeyboardInterrupt:
            logger.warning(
                "Búsqueda interrumpida manualmente (Ctrl+C). Guardando %d ofertas nuevas recolectadas...",
                len(todas_las_ofertas),
            )
        finally:
            try:
                contexto.close()
            except Exception:
                pass

    return todas_las_ofertas
