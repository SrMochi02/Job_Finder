"""
Módulo de Extracción de Vacantes con Playwright (Fase 2 - ETL).
Recorre las primeras N páginas de portales de empleo locales filtrando por San Miguel
y extrae título, empresa, ubicación, URL original y descripción completa.
"""

import logging
import random
import time
from typing import Any
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from config import HEADLESS_SCRAPER, PAGINAS_MAXIMAS, UBICACION_OBJETIVO
from parser import es_oferta_excluida

logger = logging.getLogger(__name__)

# Configuración de selectores CSS inspeccionados para portales salvadoreños
PORTALES_CONFIG: dict[str, dict[str, str]] = {
    "Computrabajo": {
        "base_url": "https://sv.computrabajo.com",
        "url_busqueda": "https://sv.computrabajo.com/empleos-en-san-miguel?p={pagina}",
        "selector_tarjeta": "article.box_offer",
        "selector_titulo_enlace": "h2 a.js-o-link, a.js-o-link",
        "selector_empresa": "p.dFlex a.fc_base, p.fs16.fc_base",
        "selector_ubicacion": "p.fs16.fc_base span.mr10",
        "selector_descripcion_detalle": "div[div-link='oferta'], div.box_detail, p.mbB",
    },
    "Tecoloco": {
        "base_url": "https://www.tecoloco.com.sv",
        "url_busqueda": "https://www.tecoloco.com.sv/empleos-en-san-miguel?Page={pagina}",
        "selector_tarjeta": "div.module.job-result",
        "selector_titulo_enlace": "h2.job-title a, div.job-result-title a",
        "selector_empresa": "li.name, span.company-name",
        "selector_ubicacion": "li.location",
        "selector_descripcion_detalle": "div.job-description, div.job-details, section.job-description",
    },
}


def extraer_ofertas_portal(
    nombre_portal: str = "Computrabajo",
    paginas_maximas: int = PAGINAS_MAXIMAS,
    headless: bool = HEADLESS_SCRAPER,
) -> list[dict[str, Any]]:
    """
    Navega las primeras `paginas_maximas` páginas del portal indicado usando Playwright
    (headless=False por defecto para depuración visual) y retorna la lista de vacantes extraídas.
    """
    if nombre_portal not in PORTALES_CONFIG:
        raise ValueError(f"Portal '{nombre_portal}' no soportado en PORTALES_CONFIG.")

    cfg = PORTALES_CONFIG[nombre_portal]
    ofertas_extraidas: list[dict[str, Any]] = []
    urls_vistas: set[str] = set()

    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=headless)
        contexto = navegador.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        pagina = contexto.new_page()

        try:
            # 1. Recolectar los enlaces y metadatos básicos de las primeras N páginas
            resumenes_ofertas: list[dict[str, str]] = []

            for num_pagina in range(1, paginas_maximas + 1):
                url_listado = cfg["url_busqueda"].format(pagina=num_pagina)
                logger.info(
                    "[%s] Navegando a página %d: %s",
                    nombre_portal,
                    num_pagina,
                    url_listado,
                )

                pagina.goto(url_listado, wait_until="domcontentloaded", timeout=30000)

                try:
                    pagina.wait_for_selector(cfg["selector_tarjeta"], timeout=12000)
                except PlaywrightTimeoutError:
                    logger.warning(
                        "[%s] No se detectaron tarjetas de empleo en la página %d. Finalizando paginación.",
                        nombre_portal,
                        num_pagina,
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
                    nodo_titulo = tarjeta.query_selector(cfg["selector_titulo_enlace"])
                    if not nodo_titulo:
                        continue

                    titulo = (nodo_titulo.inner_text() or "").strip()
                    href = nodo_titulo.get_attribute("href") or ""
                    if not titulo or not href:
                        continue

                    url_completa = urljoin(cfg["base_url"], href)
                    if url_completa in urls_vistas:
                        continue
                    urls_vistas.add(url_completa)

                    nodo_empresa = tarjeta.query_selector(cfg["selector_empresa"])
                    empresa = (
                        nodo_empresa.inner_text().strip()
                        if nodo_empresa
                        else "Empresa Confidencial"
                    )

                    nodo_ubicacion = tarjeta.query_selector(cfg["selector_ubicacion"])
                    ubicacion = (
                        nodo_ubicacion.inner_text().strip()
                        if nodo_ubicacion
                        else UBICACION_OBJETIVO
                    )

                    excluida, motivo_exclusion = es_oferta_excluida(titulo, empresa)
                    if excluida:
                        logger.info(
                            "[%s] Oferta descartada por filtro ('%s'): %s (%s)",
                            nombre_portal,
                            motivo_exclusion,
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

                # Pequeña pausa humana entre páginas de resultados
                time.sleep(random.uniform(2.0, 4.5))

            # 2. Entrar a cada oferta para extraer su descripción completa cruda
            for item in resumenes_ofertas:
                url_oferta = item["url_original"]
                logger.info(
                    "[%s] Extrayendo detalle de: %s (%s)",
                    nombre_portal,
                    item["titulo"],
                    item["empresa"],
                )
                try:
                    pagina.goto(
                        url_oferta, wait_until="domcontentloaded", timeout=25000
                    )
                    pagina.wait_for_selector(
                        cfg["selector_descripcion_detalle"], timeout=10000
                    )
                    nodos_desc = pagina.query_selector_all(
                        cfg["selector_descripcion_detalle"]
                    )
                    descripcion_cruda = "\n".join(
                        n.inner_text().strip() for n in nodos_desc if n.inner_text()
                    ).strip()
                except PlaywrightTimeoutError:
                    # Fallback al texto visible del body si el selector específico cambia
                    cuerpo = pagina.query_selector("main") or pagina.query_selector("body")
                    descripcion_cruda = (
                        cuerpo.inner_text().strip() if cuerpo else ""
                    )
                except Exception as exc:
                    logger.error(
                        "[%s] Error al abrir detalle %s: %s",
                        nombre_portal,
                        url_oferta,
                        exc,
                    )
                    continue

                if descripcion_cruda:
                    ofertas_extraidas.append(
                        {
                            **item,
                            "descripcion_cruda": descripcion_cruda,
                        }
                    )

                time.sleep(random.uniform(1.5, 3.5))

        finally:
            contexto.close()
            navegador.close()

    return ofertas_extraidas


def ejecutar_scraping_todos_los_portales(
    portales: list[str] | None = None,
    paginas_maximas: int = PAGINAS_MAXIMAS,
    headless: bool = HEADLESS_SCRAPER,
) -> list[dict[str, Any]]:
    """Ejecuta la recolección secuencial sobre la lista de portales configurados."""
    lista_portales = portales or list(PORTALES_CONFIG.keys())
    todas_las_ofertas: list[dict[str, Any]] = []

    for portal in lista_portales:
        try:
            ofertas = extraer_ofertas_portal(
                nombre_portal=portal,
                paginas_maximas=paginas_maximas,
                headless=headless,
            )
            todas_las_ofertas.extend(ofertas)
        except Exception as exc:
            logger.error("Error global al scrapear el portal %s: %s", portal, exc)

    return todas_las_ofertas
