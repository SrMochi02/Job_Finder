"""
Interfaz Gráfica de Escritorio para PC (CustomTkinter) - Job Finder El Salvador.
Permite que cualquier usuario configure su perfil, respuestas automáticas, filtros de empleo,
conexiones (Computrabajo, WhatsApp Web, Gmail), ejecute la búsqueda en vivo y lleve el control
de qué empresas lo han llamado a entrevista.
"""

import logging
import os
import queue
import shutil
import threading
import time
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

import customtkinter as ctk

import config
from database import (
    contar_envios_hoy,
    depurar_vacantes_existentes,
    exportar_reporte_empresas_csv,
    inicializar_bd,
    obtener_directorio_empresas,
    obtener_postulaciones_pendientes,
    registrar_respuesta_entrevista,
)
from main import ejecutar_flujo_completo
from mailer import enviar_correo_individual
from scraper import iniciar_sesion_portales
from whatsapp import iniciar_sesion_whatsapp

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

DEPARTAMENTOS_SV = [
    "San Miguel",
    "San Salvador",
    "Santa Ana",
    "La Libertad",
    "Soyapango",
    "Santa Tecla",
    "Sonsonate",
    "Usulután",
    "La Unión",
    "Morazán",
    "La Paz",
    "Cuscatlán",
    "Chalatenango",
    "Ahuachapán",
    "San Vicente",
    "Cabañas",
]

AREAS_LABELS: dict[str, str] = {
    "administrativo_atencion": "Administración, Recepción, Caja, Facturación y Atención al Cliente",
    "logistica_operaciones": "Bodega, Inventarios, Logística, Despacho y Operaciones",
    "ventas_comercial": "Ventas en Sala, Mostrador, Dependiente y Franquicias (Pizza Hut, Wendy's, KFC, etc.)",
    "soporte_sistemas": "Soporte Técnico, Informática, Redes y Mantenimiento de PC",
    "programacion_software": "Desarrollo de Software, Programación, SQL y Bases de Datos",
}


class QueueLogHandler(logging.Handler):
    """Redirige los logs del sistema hacia la consola en vivo de la interfaz gráfica."""

    def __init__(self, log_queue: queue.Queue[str]) -> None:
        super().__init__()
        self.log_queue = log_queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self.log_queue.put(msg)
        except Exception:
            pass


class JobFinderDesktopApp(ctk.CTk):
    """Ventana principal de la aplicación de escritorio Job Finder para PC."""

    def __init__(self) -> None:
        super().__init__()

        self.title("Job Finder Desktop — Buscador y Auto-Postulador Inteligente de Empleo (PC)")
        self.geometry("1240x820")
        self.minsize(1080, 720)

        inicializar_bd()
        config.recargar_configuracion()

        self.log_queue: queue.Queue[str] = queue.Queue()
        self._configurar_logging_gui()

        self.ejecutando_jornada = False
        self.detener_evento = threading.Event()
        self.hilo_trabajo: threading.Thread | None = None

        self._construir_layout_principal()
        self._cargar_valores_en_formularios()
        self._actualizar_estadisticas_y_tabla()
        self.after(250, self._procesar_cola_logs)

    def _configurar_logging_gui(self) -> None:
        handler = QueueLogHandler(self.log_queue)
        handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S")
        )
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(handler)

    def _construir_layout_principal(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ================== BARRA LATERAL ==================
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(7, weight=1)

        lbl_logo = ctk.CTkLabel(
            self.sidebar,
            text="🚀 JOB FINDER PC",
            font=ctk.CTkFont(size=22, weight="bold"),
        )
        lbl_logo.grid(row=0, column=0, padx=20, pady=(24, 4))

        lbl_sub = ctk.CTkLabel(
            self.sidebar,
            text="Auto-Postulador Multi-Usuario",
            font=ctk.CTkFont(size=12),
            text_color="gray70",
        )
        lbl_sub.grid(row=1, column=0, padx=20, pady=(0, 20))

        self.btn_nav_panel = ctk.CTkButton(
            self.sidebar,
            text="▶  Panel y Búsqueda en Vivo",
            anchor="w",
            height=40,
            command=lambda: self.tabview.set("Panel de Control"),
        )
        self.btn_nav_panel.grid(row=2, column=0, padx=16, pady=6, sticky="ew")

        self.btn_nav_perfil = ctk.CTkButton(
            self.sidebar,
            text="👤  1. Mi Perfil y Respuestas",
            anchor="w",
            height=40,
            fg_color="transparent",
            border_width=1,
            command=lambda: self.tabview.set("1. Mi Perfil y CV"),
        )
        self.btn_nav_perfil.grid(row=3, column=0, padx=16, pady=6, sticky="ew")

        self.btn_nav_rubros = ctk.CTkButton(
            self.sidebar,
            text="🎯  2. Mis Rubros y Filtros",
            anchor="w",
            height=40,
            fg_color="transparent",
            border_width=1,
            command=lambda: self.tabview.set("2. Rubros y Filtros"),
        )
        self.btn_nav_rubros.grid(row=4, column=0, padx=16, pady=6, sticky="ew")

        self.btn_nav_conexiones = ctk.CTkButton(
            self.sidebar,
            text="🔗  3. Cuentas y Conexiones",
            anchor="w",
            height=40,
            fg_color="transparent",
            border_width=1,
            command=lambda: self.tabview.set("3. Conexiones"),
        )
        self.btn_nav_conexiones.grid(row=5, column=0, padx=16, pady=6, sticky="ew")

        self.btn_nav_empresas = ctk.CTkButton(
            self.sidebar,
            text="🏢  4. Empresas y Entrevistas",
            anchor="w",
            height=40,
            fg_color="transparent",
            border_width=1,
            command=lambda: self.tabview.set("4. Empresas Postuladas"),
        )
        self.btn_nav_empresas.grid(row=6, column=0, padx=16, pady=6, sticky="ew")

        # Estado actual en barra lateral
        self.frame_estado_side = ctk.CTkFrame(self.sidebar, corner_radius=10)
        self.frame_estado_side.grid(row=8, column=0, padx=16, pady=12, sticky="ew")

        self.lbl_estado_motor = ctk.CTkLabel(
            self.frame_estado_side,
            text="● Motor: Detenido",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#f39c12",
        )
        self.lbl_estado_motor.pack(padx=12, pady=(10, 4), anchor="w")

        self.lbl_resumen_side = ctk.CTkLabel(
            self.frame_estado_side,
            text="Ofertas en BD: 0\nAuto-postuladas: 0",
            font=ctk.CTkFont(size=12),
            justify="left",
        )
        self.lbl_resumen_side.pack(padx=12, pady=(0, 10), anchor="w")

        # Selector de tema Claro / Oscuro
        self.menu_tema = ctk.CTkOptionMenu(
            self.sidebar,
            values=["Oscuro", "Claro", "Sistema"],
            command=self._cambiar_tema,
        )
        self.menu_tema.grid(row=9, column=0, padx=16, pady=(4, 20), sticky="ew")
        self.menu_tema.set("Oscuro")

        # ================== CONTENEDOR DE PESTAÑAS ==================
        self.tabview = ctk.CTkTabview(self, corner_radius=12)
        self.tabview.grid(row=0, column=1, padx=18, pady=14, sticky="nsew")

        self.tab_panel = self.tabview.add("Panel de Control")
        self.tab_perfil = self.tabview.add("1. Mi Perfil y CV")
        self.tab_rubros = self.tabview.add("2. Rubros y Filtros")
        self.tab_conexiones = self.tabview.add("3. Conexiones")
        self.tab_empresas = self.tabview.add("4. Empresas Postuladas")

        self._construir_tab_panel()
        self._construir_tab_perfil()
        self._construir_tab_rubros()
        self._construir_tab_conexiones()
        self._construir_tab_empresas()

    def _cambiar_tema(self, seleccion: str) -> None:
        mapa = {"Oscuro": "Dark", "Claro": "Light", "Sistema": "System"}
        ctk.set_appearance_mode(mapa.get(seleccion, "Dark"))

    # =========================================================================
    # PESTAÑA 0: PANEL DE CONTROL Y CONSOLA EN VIVO
    # =========================================================================
    def _construir_tab_panel(self) -> None:
        self.tab_panel.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.tab_panel.grid_rowconfigure(2, weight=1)

        # Tarjetas superiores de métricas
        self.card_total = self._crear_tarjeta_kpi(
            self.tab_panel, 0, "Vacantes Compatibles", "0", "#3498db"
        )
        self.card_portal = self._crear_tarjeta_kpi(
            self.tab_panel, 1, "Auto-Postuladas en Portal", "0", "#2ecc71"
        )
        self.card_correos = self._crear_tarjeta_kpi(
            self.tab_panel, 2, "Correos Enviados Hoy", "0", "#9b59b6"
        )
        self.card_entrevistas = self._crear_tarjeta_kpi(
            self.tab_panel, 3, "Llamaron a Entrevista", "0", "#f1c40f"
        )

        # Barra de botones de ejecución
        frame_acciones = ctk.CTkFrame(self.tab_panel, corner_radius=10)
        frame_acciones.grid(row=1, column=0, columnspan=4, padx=8, pady=10, sticky="ew")

        self.btn_ciclo_unico = ctk.CTkButton(
            frame_acciones,
            text="⚡ Buscar y Postular Ahora (1 Ciclo)",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#27ae60",
            hover_color="#1e8449",
            height=42,
            command=self._iniciar_ciclo_unico_thread,
        )
        self.btn_ciclo_unico.pack(side="left", padx=(14, 8), pady=12)

        self.btn_jornada = ctk.CTkButton(
            frame_acciones,
            text="🔄 Iniciar Jornada Continua (Automático cada 45 min)",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2980b9",
            hover_color="#1f618d",
            height=42,
            command=self._iniciar_jornada_continua_thread,
        )
        self.btn_jornada.pack(side="left", padx=8, pady=12)

        self.btn_detener = ctk.CTkButton(
            frame_acciones,
            text="⏹ Detener",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#c0392b",
            hover_color="#922b21",
            height=42,
            width=120,
            state="disabled",
            command=self._detener_ejecucion,
        )
        self.btn_detener.pack(side="left", padx=8, pady=12)

        btn_limpiar_log = ctk.CTkButton(
            frame_acciones,
            text="🧹 Limpiar Consola",
            fg_color="gray35",
            hover_color="gray25",
            height=42,
            width=140,
            command=self._limpiar_consola,
        )
        btn_limpiar_log.pack(side="right", padx=14, pady=12)

        # Consola en vivo
        frame_consola = ctk.CTkFrame(self.tab_panel, corner_radius=10)
        frame_consola.grid(row=2, column=0, columnspan=4, padx=8, pady=(4, 8), sticky="nsew")
        frame_consola.grid_rowconfigure(1, weight=1)
        frame_consola.grid_columnconfigure(0, weight=1)

        lbl_consola = ctk.CTkLabel(
            frame_consola,
            text="📋 Actividad del Sistema en Tiempo Real (Preguntas respondidas, filtros y postulaciones):",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        lbl_consola.grid(row=0, column=0, padx=14, pady=(10, 4), sticky="w")

        self.txt_consola = ctk.CTkTextbox(
            frame_consola,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word",
        )
        self.txt_consola.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        self.txt_consola.insert(
            "end",
            "Bienvenido a Job Finder Desktop.\n"
            "1. Revisa tus datos y tu CV en la pestaña '1. Mi Perfil y CV'.\n"
            "2. Elige tu ciudad y áreas de trabajo en '2. Rubros y Filtros'.\n"
            "3. Inicia sesión una vez en Computrabajo desde '3. Conexiones'.\n"
            "4. Presiona 'Buscar y Postular Ahora' para comenzar.\n"
            + "=" * 85
            + "\n",
        )

    def _crear_tarjeta_kpi(
        self, parent: Any, col: int, titulo: str, valor: str, color: str
    ) -> ctk.CTkLabel:
        frame = ctk.CTkFrame(parent, corner_radius=10)
        frame.grid(row=0, column=col, padx=8, pady=8, sticky="ew")
        lbl_t = ctk.CTkLabel(
            frame, text=titulo, font=ctk.CTkFont(size=12), text_color="gray75"
        )
        lbl_t.pack(padx=14, pady=(10, 2), anchor="w")
        lbl_v = ctk.CTkLabel(
            frame,
            text=valor,
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=color,
        )
        lbl_v.pack(padx=14, pady=(0, 10), anchor="w")
        return lbl_v

    # =========================================================================
    # PESTAÑA 1: MI PERFIL, CV Y RESPUESTAS AUTOMÁTICAS
    # =========================================================================
    def _construir_tab_perfil(self) -> None:
        scroll = ctk.CTkScrollableFrame(self.tab_perfil, corner_radius=10)
        scroll.pack(fill="both", expand=True, padx=6, pady=6)
        scroll.grid_columnconfigure((0, 1), weight=1)

        lbl_intro = ctk.CTkLabel(
            scroll,
            text="👤 Datos del Candidato y Respuestas para 'Preguntas de Selección' de Computrabajo",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        lbl_intro.grid(row=0, column=0, columnspan=2, padx=14, pady=(10, 4), sticky="w")

        lbl_sub = ctk.CTkLabel(
            scroll,
            text="El sistema usará esta información automáticamente cada vez que una empresa haga preguntas filtro al postularte.",
            font=ctk.CTkFont(size=12),
            text_color="gray70",
        )
        lbl_sub.grid(row=1, column=0, columnspan=2, padx=14, pady=(0, 12), sticky="w")

        # Fila 2: Nombre y Teléfono
        self.ent_nombre = self._crear_campo(
            scroll, 2, 0, "Nombre Completo:", "Ej. Raúl Isaías Hernández López"
        )
        self.ent_telefono = self._crear_campo(
            scroll, 2, 1, "Teléfono / WhatsApp (+503):", "Ej. +503 7000-0000"
        )

        # Fila 4: Edad y Dirección
        self.ent_edad = self._crear_campo(
            scroll, 4, 0, "Edad actual (para filtro de edad mínima):", "Ej. 21 años"
        )
        self.ent_direccion = self._crear_campo(
            scroll,
            4,
            1,
            "Dirección exacta de residencia:",
            "Ej. Residencial La Pradera, San Miguel",
        )

        # Fila 6: Pretensión salarial y Último salario
        self.ent_pretension = self._crear_campo(
            scroll,
            6,
            0,
            "Pretensión Salarial Mensual (USD - solo número):",
            "Ej. 450",
        )
        self.ent_ultimo_salario = self._crear_campo(
            scroll,
            6,
            1,
            "Último Salario Devengado (USD - solo número):",
            "Ej. 380",
        )

        # Fila 8: Estado civil y Respuesta sobre hijos
        frame_ec = ctk.CTkFrame(scroll, fg_color="transparent")
        frame_ec.grid(row=8, column=0, padx=14, pady=6, sticky="ew")
        ctk.CTkLabel(
            frame_ec, text="Estado Civil:", font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", pady=(0, 4))
        self.cmb_estado_civil = ctk.CTkComboBox(
            frame_ec,
            values=["Soltero(a)", "Acompañado (Unión libre)", "Casado(a)"],
            height=34,
        )
        self.cmb_estado_civil.pack(fill="x")

        self.ent_hijos = self._crear_campo(
            scroll,
            8,
            1,
            "Respuesta cuando pregunten si tiene hijos:",
            "Ej. No tengo hijos / Sí, esperando una hija próximamente.",
        )

        # Fila 10: Licencia/Vehículo y ¿Estudia actualmente?
        frame_lic = ctk.CTkFrame(scroll, fg_color="transparent")
        frame_lic.grid(row=10, column=0, padx=14, pady=6, sticky="ew")
        ctk.CTkLabel(
            frame_lic,
            text="¿Posee Licencia de Conducir / Vehículo o Moto propia?",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", pady=(0, 4))
        self.cmb_licencia = ctk.CTkComboBox(
            frame_lic,
            values=[
                "NO (Descartar ofertas que exijan licencia o moto)",
                "SI (Poseo licencia y/o vehículo propio)",
            ],
            height=34,
        )
        self.cmb_licencia.pack(fill="x")

        frame_est = ctk.CTkFrame(scroll, fg_color="transparent")
        frame_est.grid(row=10, column=1, padx=14, pady=6, sticky="ew")
        ctk.CTkLabel(
            frame_est,
            text="¿Estudia actualmente (horarios de clases)?",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", pady=(0, 4))
        self.cmb_estudia = ctk.CTkComboBox(
            frame_est,
            values=[
                "NO (Ya graduado/egresado - Disponibilidad completa)",
                "SI (Estudio actualmente con horarios definidos)",
            ],
            height=34,
        )
        self.cmb_estudia.pack(fill="x")

        # Fila 12: Nivel académico y Motivo de salida del último empleo
        self.ent_nivel_academico = self._crear_campo(
            scroll,
            12,
            0,
            "Estudios / Título Académico (para preguntas de educación):",
            "Ej. Egresado de Técnico en Desarrollo de Software (ITCA) y Bachiller",
        )
        self.ent_motivo_salida = self._crear_campo(
            scroll,
            12,
            1,
            "Motivo de salida de su último empleo:",
            "Ej. Finalización de proyecto y superación profesional.",
        )

        # Fila 14: Resumen de Experiencia del CV
        ctk.CTkLabel(
            scroll,
            text="Resumen de tu Experiencia Laboral (se usa cuando preguntan por tu experiencia en caja, bodega, atención, etc.):",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=14, column=0, columnspan=2, padx=14, pady=(10, 4), sticky="w")

        self.txt_experiencia = ctk.CTkTextbox(scroll, height=70)
        self.txt_experiencia.grid(
            row=15, column=0, columnspan=2, padx=14, pady=(0, 8), sticky="ew"
        )

        # Fila 16: Carta de Presentación
        ctk.CTkLabel(
            scroll,
            text="Carta de Presentación Automática (máximo 1500 caracteres para Computrabajo):",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=16, column=0, columnspan=2, padx=14, pady=(8, 4), sticky="w")

        self.txt_carta = ctk.CTkTextbox(scroll, height=95)
        self.txt_carta.grid(
            row=17, column=0, columnspan=2, padx=14, pady=(0, 10), sticky="ew"
        )

        # Fila 18: Selección del archivo PDF del CV
        frame_cv = ctk.CTkFrame(scroll, corner_radius=10)
        frame_cv.grid(row=18, column=0, columnspan=2, padx=14, pady=8, sticky="ew")

        ctk.CTkLabel(
            frame_cv,
            text="📄 Archivo PDF de tu Currículum (CV):",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left", padx=14, pady=12)

        self.lbl_ruta_cv = ctk.CTkLabel(
            frame_cv,
            text=str(config.CV_PATH),
            font=ctk.CTkFont(size=12),
            text_color="#2ecc71",
        )
        self.lbl_ruta_cv.pack(side="left", padx=8, pady=12)

        btn_subir_cv = ctk.CTkButton(
            frame_cv,
            text="📂 Seleccionar / Cambiar PDF de mi CV...",
            command=self._seleccionar_pdf_cv,
        )
        btn_subir_cv.pack(side="right", padx=14, pady=12)

        # Botón Guardar Perfil
        btn_guardar_perfil = ctk.CTkButton(
            scroll,
            text="💾 Guardar Mi Perfil y Respuestas Automáticas",
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#27ae60",
            hover_color="#1e8449",
            height=45,
            command=self._guardar_perfil_usuario,
        )
        btn_guardar_perfil.grid(
            row=19, column=0, columnspan=2, padx=14, pady=(14, 20), sticky="ew"
        )

    def _crear_campo(
        self, parent: Any, row: int, col: int, label_text: str, placeholder: str
    ) -> ctk.CTkEntry:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=col, padx=14, pady=6, sticky="ew")
        lbl = ctk.CTkLabel(
            frame, text=label_text, font=ctk.CTkFont(size=13, weight="bold")
        )
        lbl.pack(anchor="w", pady=(0, 4))
        entry = ctk.CTkEntry(frame, placeholder_text=placeholder, height=34)
        entry.pack(fill="x")
        return entry

    def _seleccionar_pdf_cv(self) -> None:
        ruta = filedialog.askopenfilename(
            title="Selecciona el archivo PDF de tu Currículum",
            filetypes=[("Archivos PDF", "*.pdf")],
        )
        if not ruta:
            return
        origen = Path(ruta).resolve()
        destino = (config.BASE_DIR / "cv_postulante.pdf").resolve()
        try:
            if origen != destino:
                shutil.copy2(origen, destino)
            self.lbl_ruta_cv.configure(
                text=f"{destino.name} (Cargado desde {origen.name})"
            )
            messagebox.showinfo(
                "CV Actualizado",
                f"Tu currículum '{origen.name}' se copió y configuró correctamente como cv_postulante.pdf.",
            )
        except Exception as exc:
            messagebox.showerror("Error al copiar CV", str(exc))

    # =========================================================================
    # PESTAÑA 2: MIS RUBROS, CIUDAD Y FILTROS
    # =========================================================================
    def _construir_tab_rubros(self) -> None:
        scroll = ctk.CTkScrollableFrame(self.tab_rubros, corner_radius=10)
        scroll.pack(fill="both", expand=True, padx=6, pady=6)
        scroll.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            scroll,
            text="🎯 Configuración de Ciudad, Áreas de Trabajo y Filtros de Exclusión",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, padx=14, pady=(10, 12), sticky="w")

        # Ciudad / Departamento y Páginas máximas
        frame_ubi = ctk.CTkFrame(scroll, fg_color="transparent")
        frame_ubi.grid(row=1, column=0, padx=14, pady=6, sticky="ew")
        ctk.CTkLabel(
            frame_ubi,
            text="Departamento / Ciudad donde buscas empleo:",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", pady=(0, 4))
        self.cmb_ubicacion = ctk.CTkComboBox(
            frame_ubi, values=DEPARTAMENTOS_SV, height=34
        )
        self.cmb_ubicacion.pack(fill="x")

        self.ent_paginas = self._crear_campo(
            scroll,
            1,
            1,
            "Cantidad de páginas a revisar por portal (1 página = 20 ofertas):",
            "Ej. 8",
        )

        # Checkboxes de Áreas Laborales
        frame_areas = ctk.CTkFrame(scroll, corner_radius=10)
        frame_areas.grid(
            row=2, column=0, columnspan=2, padx=14, pady=12, sticky="ew"
        )
        ctk.CTkLabel(
            frame_areas,
            text="✅ Marca las áreas laborales a las que SÍ quieres que el sistema te postule:",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(12, 6))

        self.vars_areas: dict[str, ctk.BooleanVar] = {}
        for clave_area, descripcion_area in AREAS_LABELS.items():
            var = ctk.BooleanVar(value=True)
            self.vars_areas[clave_area] = var
            chk = ctk.CTkCheckBox(
                frame_areas,
                text=descripcion_area,
                variable=var,
                font=ctk.CTkFont(size=13),
            )
            chk.pack(anchor="w", padx=20, pady=6)

        # Opciones de auto-postulación y navegador visible
        frame_switches = ctk.CTkFrame(scroll, corner_radius=10)
        frame_switches.grid(
            row=3, column=0, columnspan=2, padx=14, pady=8, sticky="ew"
        )

        self.var_auto_postular = ctk.BooleanVar(value=True)
        sw_auto = ctk.CTkSwitch(
            frame_switches,
            text="Auto-postularme automáticamente en Computrabajo y responder encuestas",
            variable=self.var_auto_postular,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        sw_auto.pack(anchor="w", padx=14, pady=(12, 6))

        self.var_ocultar_nav = ctk.BooleanVar(value=False)
        sw_headless = ctk.CTkSwitch(
            frame_switches,
            text="Ejecutar navegador en modo oculto/segundo plano (Headless)",
            variable=self.var_ocultar_nav,
            font=ctk.CTkFont(size=13),
        )
        sw_headless.pack(anchor="w", padx=14, pady=(4, 12))

        # Palabras clave excluidas
        ctk.CTkLabel(
            scroll,
            text="🚫 Palabras Clave, Puestos o Empresas Bloqueadas (separadas por coma):",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=4, column=0, columnspan=2, padx=14, pady=(10, 4), sticky="w")

        ctk.CTkLabel(
            scroll,
            text="Cualquier oferta que tenga una de estas palabras en su título o nombre de empresa será ignorada de inmediato.",
            font=ctk.CTkFont(size=12),
            text_color="gray70",
        ).grid(row=5, column=0, columnspan=2, padx=14, pady=(0, 6), sticky="w")

        self.txt_excluidas = ctk.CTkTextbox(scroll, height=130)
        self.txt_excluidas.grid(
            row=6, column=0, columnspan=2, padx=14, pady=(0, 12), sticky="ew"
        )

        btn_guardar_rubros = ctk.CTkButton(
            scroll,
            text="💾 Guardar Mis Rubros y Filtros (y Limpiar Ofertas No Compatibles)",
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#27ae60",
            hover_color="#1e8449",
            height=45,
            command=self._guardar_rubros_y_filtros,
        )
        btn_guardar_rubros.grid(
            row=7, column=0, columnspan=2, padx=14, pady=(8, 20), sticky="ew"
        )

    # =========================================================================
    # PESTAÑA 3: CONEXIONES (COMPUTRABAJO, WHATSAPP WEB, GMAIL)
    # =========================================================================
    def _construir_tab_conexiones(self) -> None:
        scroll = ctk.CTkScrollableFrame(self.tab_conexiones, corner_radius=10)
        scroll.pack(fill="both", expand=True, padx=6, pady=6)
        scroll.grid_columnconfigure(0, weight=1)

        # 1. Computrabajo
        frame_ct = ctk.CTkFrame(scroll, corner_radius=10)
        frame_ct.grid(row=0, column=0, padx=14, pady=10, sticky="ew")

        ctk.CTkLabel(
            frame_ct,
            text="🌐 1. Cuenta de Computrabajo El Salvador (Auto-Postulación en 1 Clic)",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 4))

        ctk.CTkLabel(
            frame_ct,
            text="Haz clic en el botón para abrir el navegador integrado. Inicia sesión en tu cuenta de Computrabajo,\n"
            "sube tu foto/CV si aún no lo has hecho y luego CIERRA esa ventana del navegador para que tu sesión quede guardada.",
            font=ctk.CTkFont(size=12),
            text_color="gray75",
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))

        btn_login_ct = ctk.CTkButton(
            frame_ct,
            text="🔑 Abrir Computrabajo para Iniciar Sesión",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#e67e22",
            hover_color="#d35400",
            height=40,
            command=self._abrir_login_computrabajo_thread,
        )
        btn_login_ct.pack(anchor="w", padx=16, pady=(0, 14))

        # 2. Gmail SMTP (Para cuando la oferta trae correo de RRHH)
        frame_gmail = ctk.CTkFrame(scroll, corner_radius=10)
        frame_gmail.grid(row=1, column=0, padx=14, pady=10, sticky="ew")

        ctk.CTkLabel(
            frame_gmail,
            text="📧 2. Correo Gmail (Envío automático de CV a correos de Recursos Humanos)",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 4))

        ctk.CTkLabel(
            frame_gmail,
            text="Cuando una oferta incluye un correo electrónico (ej. rrhh@empresa.com), el sistema envía tu CV en PDF automáticamente.\n"
            "Usa una 'Contraseña de Aplicación' de 16 letras de Google (no tu contraseña normal).",
            font=ctk.CTkFont(size=12),
            text_color="gray75",
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))

        sub_gmail = ctk.CTkFrame(frame_gmail, fg_color="transparent")
        sub_gmail.pack(fill="x", padx=16, pady=4)
        sub_gmail.grid_columnconfigure((0, 1), weight=1)

        self.ent_gmail_user = self._crear_campo(
            sub_gmail, 0, 0, "Tu Correo Gmail:", "ejemplo@gmail.com"
        )
        self.ent_gmail_pass = self._crear_campo(
            sub_gmail,
            0,
            1,
            "Contraseña de Aplicación de Gmail (16 letras):",
            "xxxx xxxx xxxx xxxx",
        )
        self.ent_gmail_pass.configure(show="*")

        frame_btns_gmail = ctk.CTkFrame(frame_gmail, fg_color="transparent")
        frame_btns_gmail.pack(fill="x", padx=16, pady=(8, 14))

        btn_guardar_gmail = ctk.CTkButton(
            frame_btns_gmail,
            text="💾 Guardar Gmail",
            fg_color="#27ae60",
            hover_color="#1e8449",
            command=self._guardar_credenciales_gmail,
        )
        btn_guardar_gmail.pack(side="left", padx=(0, 10))

        btn_probar_gmail = ctk.CTkButton(
            frame_btns_gmail,
            text="📨 Enviar Correo de Prueba a Mí Mismo",
            command=self._probar_envio_gmail_thread,
        )
        btn_probar_gmail.pack(side="left", padx=10)

        btn_ayuda_app_pass = ctk.CTkButton(
            frame_btns_gmail,
            text="❓ Crear Contraseña de Aplicación en Google",
            fg_color="gray35",
            command=lambda: webbrowser.open("https://myaccount.google.com/apppasswords"),
        )
        btn_ayuda_app_pass.pack(side="right")

        # 3. WhatsApp Web (Opcional)
        frame_wa = ctk.CTkFrame(scroll, corner_radius=10)
        frame_wa.grid(row=2, column=0, padx=14, pady=10, sticky="ew")

        ctk.CTkLabel(
            frame_wa,
            text="💬 3. WhatsApp Web (Opcional - Para ofertas que publican número de WhatsApp)",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 4))

        ctk.CTkLabel(
            frame_wa,
            text="Si deseas que el sistema también envíe tu CV en PDF por WhatsApp cuando una empresa deje su celular en el anuncio,\n"
            "vincula tu QR aquí. Si prefieres escribirles tú manualmente por WhatsApp, pon el límite diario en 0.",
            font=ctk.CTkFont(size=12),
            text_color="gray75",
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))

        sub_wa = ctk.CTkFrame(frame_wa, fg_color="transparent")
        sub_wa.pack(fill="x", padx=16, pady=(0, 14))

        btn_qr_wa = ctk.CTkButton(
            sub_wa,
            text="📱 Abrir WhatsApp Web para Escanear QR",
            fg_color="#16a085",
            hover_color="#117864",
            height=38,
            command=self._abrir_login_whatsapp_thread,
        )
        btn_qr_wa.pack(side="left", padx=(0, 16))

        ctk.CTkLabel(
            sub_wa,
            text="Máximo de WhatsApps automáticos por día (0 = Desactivado):",
            font=ctk.CTkFont(size=13),
        ).pack(side="left", padx=6)

        self.ent_max_wa = ctk.CTkEntry(sub_wa, width=70, height=34)
        self.ent_max_wa.pack(side="left", padx=6)

        btn_save_wa = ctk.CTkButton(
            sub_wa,
            text="Guardar Límite",
            width=120,
            command=self._guardar_limite_whatsapp,
        )
        btn_save_wa.pack(side="left", padx=10)

    # =========================================================================
    # PESTAÑA 4: DIRECTORIO DE EMPRESAS POSTULADAS Y ENTREVISTAS
    # =========================================================================
    def _construir_tab_empresas(self) -> None:
        self.tab_empresas.grid_columnconfigure(0, weight=1)
        self.tab_empresas.grid_rowconfigure(1, weight=1)

        frame_top = ctk.CTkFrame(self.tab_empresas, corner_radius=10)
        frame_top.grid(row=0, column=0, padx=8, pady=8, sticky="ew")

        ctk.CTkLabel(
            frame_top,
            text="🏢 Empresas a las que te has postulado",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(side="left", padx=14, pady=10)

        btn_refrescar = ctk.CTkButton(
            frame_top,
            text="🔄 Actualizar Lista",
            width=140,
            command=self._actualizar_estadisticas_y_tabla,
        )
        btn_refrescar.pack(side="right", padx=10, pady=10)

        btn_abrir_csv = ctk.CTkButton(
            frame_top,
            text="📊 Abrir Excel (CSV)",
            fg_color="#27ae60",
            hover_color="#1e8449",
            width=150,
            command=self._abrir_csv_empresas,
        )
        btn_abrir_csv.pack(side="right", padx=6, pady=10)

        btn_marcar_si = ctk.CTkButton(
            frame_top,
            text="📞 ¡Me Llamaron a Entrevista!",
            fg_color="#f39c12",
            hover_color="#d68910",
            width=200,
            command=lambda: self._marcar_entrevista_seleccionada("SI"),
        )
        btn_marcar_si.pack(side="right", padx=6, pady=10)

        btn_ver_oferta = ctk.CTkButton(
            frame_top,
            text="🌐 Abrir Oferta en Navegador",
            width=190,
            command=self._abrir_url_oferta_seleccionada,
        )
        btn_ver_oferta.pack(side="right", padx=6, pady=10)

        # Tabla Treeview
        frame_tabla = ctk.CTkFrame(self.tab_empresas, corner_radius=10)
        frame_tabla.grid(row=1, column=0, padx=8, pady=4, sticky="nsew")
        frame_tabla.grid_rowconfigure(0, weight=1)
        frame_tabla.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Treeview",
            background="#1e272e",
            foreground="#ecf0f1",
            rowheight=30,
            fieldbackground="#1e272e",
            font=("Segoe UI", 10),
        )
        style.configure(
            "Treeview.Heading",
            background="#2f3640",
            foreground="#ffffff",
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Treeview", background=[("selected", "#2980b9")])

        columnas = (
            "id",
            "empresa",
            "titulo",
            "area",
            "salario",
            "postulado_portal",
            "llamaron",
            "telefonos",
            "url",
        )
        self.tree = ttk.Treeview(
            frame_tabla, columns=columnas, show="headings", selectmode="browse"
        )
        self.tree.heading("id", text="ID")
        self.tree.heading("empresa", text="Empresa")
        self.tree.heading("titulo", text="Puesto / Vacante")
        self.tree.heading("area", text="Área")
        self.tree.heading("salario", text="Salario")
        self.tree.heading("postulado_portal", text="Postulado en Portal")
        self.tree.heading("llamaron", text="¿Llamaron?")
        self.tree.heading("telefonos", text="Contacto Empresa")
        self.tree.heading("url", text="Enlace")

        self.tree.column("id", width=55, anchor="center")
        self.tree.column("empresa", width=210)
        self.tree.column("titulo", width=240)
        self.tree.column("area", width=130)
        self.tree.column("salario", width=95, anchor="center")
        self.tree.column("postulado_portal", width=140, anchor="center")
        self.tree.column("llamaron", width=90, anchor="center")
        self.tree.column("telefonos", width=130)
        self.tree.column("url", width=180)

        scroll_y = ttk.Scrollbar(frame_tabla, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll_y.set)

        self.tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)
        scroll_y.grid(row=0, column=1, sticky="ns", padx=(0, 10), pady=10)

    # =========================================================================
    # CARGA Y GUARDADO DE CONFIGURACIÓN
    # =========================================================================
    def _cargar_valores_en_formularios(self) -> None:
        config.recargar_configuracion()

        self._set_entry(self.ent_nombre, config.REMITENTE_NOMBRE)
        self._set_entry(self.ent_telefono, config.REMITENTE_TELEFONO)
        self._set_entry(self.ent_edad, config.EDAD_POSTULANTE)
        self._set_entry(self.ent_direccion, config.DIRECCION_RESIDENCIA)
        self._set_entry(self.ent_pretension, config.PRETENSION_SALARIAL)
        self._set_entry(self.ent_ultimo_salario, config.ULTIMO_SALARIO)
        self.cmb_estado_civil.set(config.ESTADO_CIVIL_POSTULANTE)
        self._set_entry(self.ent_hijos, config.RESPUESTA_HIJOS)

        if config.POSEE_LICENCIA_VEHICULO.strip().upper().startswith("S"):
            self.cmb_licencia.set("SI (Poseo licencia y/o vehículo propio)")
        else:
            self.cmb_licencia.set("NO (Descartar ofertas que exijan licencia o moto)")

        if config.ESTUDIA_ACTUALMENTE.strip().upper().startswith("S"):
            self.cmb_estudia.set("SI (Estudio actualmente con horarios definidos)")
        else:
            self.cmb_estudia.set("NO (Ya graduado/egresado - Disponibilidad completa)")

        self._set_entry(self.ent_nivel_academico, config.NIVEL_ACADEMICO)
        self._set_entry(self.ent_motivo_salida, config.MOTIVO_SALIDA_ULTIMO_EMPLEO)

        self.txt_experiencia.delete("1.0", "end")
        self.txt_experiencia.insert("1.0", config.RESUMEN_EXPERIENCIA_CV)

        self.txt_carta.delete("1.0", "end")
        self.txt_carta.insert("1.0", config.CARTA_PRESENTACION)

        self.cmb_ubicacion.set(config.UBICACION_OBJETIVO)
        self._set_entry(self.ent_paginas, str(config.PAGINAS_MAXIMAS))

        areas_activas = set(config.AREAS_ACTIVAS)
        for clave, var in self.vars_areas.items():
            var.set(clave in areas_activas)

        self.var_auto_postular.set(config.AUTO_POSTULAR_PORTAL)
        self.var_ocultar_nav.set(config.HEADLESS_SCRAPER)

        self.txt_excluidas.delete("1.0", "end")
        self.txt_excluidas.insert("1.0", ", ".join(config.PALABRAS_EXCLUIDAS))

        self._set_entry(self.ent_gmail_user, config.GMAIL_USER)
        self._set_entry(self.ent_gmail_pass, config.GMAIL_APP_PASSWORD)
        self._set_entry(self.ent_max_wa, str(config.MAX_WHATSAPP_POR_DIA))

    @staticmethod
    def _set_entry(entry: ctk.CTkEntry, valor: str) -> None:
        entry.delete(0, "end")
        entry.insert(0, valor)

    def _guardar_perfil_usuario(self) -> None:
        lic_val = "SI" if self.cmb_licencia.get().startswith("SI") else "NO"
        est_val = "SI" if self.cmb_estudia.get().startswith("SI") else "NO"

        datos = {
            "REMITENTE_NOMBRE": self.ent_nombre.get().strip(),
            "REMITENTE_TELEFONO": self.ent_telefono.get().strip(),
            "EDAD_POSTULANTE": self.ent_edad.get().strip(),
            "DIRECCION_RESIDENCIA": self.ent_direccion.get().strip(),
            "PRETENSION_SALARIAL": self.ent_pretension.get().strip(),
            "ULTIMO_SALARIO": self.ent_ultimo_salario.get().strip(),
            "ESTADO_CIVIL_POSTULANTE": self.cmb_estado_civil.get().strip(),
            "RESPUESTA_HIJOS": self.ent_hijos.get().strip(),
            "POSEE_LICENCIA_VEHICULO": lic_val,
            "ESTUDIA_ACTUALMENTE": est_val,
            "NIVEL_ACADEMICO": self.ent_nivel_academico.get().strip(),
            "MOTIVO_SALIDA_ULTIMO_EMPLEO": self.ent_motivo_salida.get().strip(),
            "RESUMEN_EXPERIENCIA_CV": self.txt_experiencia.get("1.0", "end").strip(),
            "CARTA_PRESENTACION": self.txt_carta.get("1.0", "end").strip(),
        }
        config.guardar_variables_env(datos)
        logging.getLogger("gui").info(
            "Perfil de candidato '%s' y respuestas automáticas guardadas con éxito.",
            config.REMITENTE_NOMBRE,
        )
        messagebox.showinfo(
            "Perfil Guardado",
            "Tus datos personales, respuestas para preguntas de selección y carta de presentación se han guardado correctamente.",
        )

    def _guardar_rubros_y_filtros(self) -> None:
        seleccionadas = [k for k, v in self.vars_areas.items() if v.get()]
        if not seleccionadas:
            messagebox.showwarning(
                "Selecciona al menos un área",
                "Debes marcar al menos un área laboral para que el sistema busque vacantes.",
            )
            return

        palabras_raw = self.txt_excluidas.get("1.0", "end").replace("\n", ",")
        palabras_limpias = ",".join(
            [p.strip() for p in palabras_raw.split(",") if p.strip()]
        )
        paginas_str = self.ent_paginas.get().strip()
        if not paginas_str.isdigit() or int(paginas_str) < 1:
            paginas_str = "5"

        datos = {
            "UBICACION_OBJETIVO": self.cmb_ubicacion.get().strip() or "San Miguel",
            "PAGINAS_MAXIMAS": paginas_str,
            "AREAS_ACTIVAS": ",".join(seleccionadas),
            "AUTO_POSTULAR_PORTAL": "True" if self.var_auto_postular.get() else "False",
            "HEADLESS_SCRAPER": "True" if self.var_ocultar_nav.get() else "False",
            "PALABRAS_EXCLUIDAS": palabras_limpias,
        }
        config.guardar_variables_env(datos)
        eliminadas = depurar_vacantes_existentes()
        exportar_reporte_empresas_csv()
        self._actualizar_estadisticas_y_tabla()
        logging.getLogger("gui").info(
            "Filtros actualizados (Ciudad: %s, Áreas: %d). Vacantes antiguas no compatibles depuradas: %d",
            config.UBICACION_OBJETIVO,
            len(seleccionadas),
            eliminadas,
        )
        messagebox.showinfo(
            "Filtros Guardados",
            f"Tus rubros y filtros para '{config.UBICACION_OBJETIVO}' se guardaron.\n"
            f"Se limpiaron {eliminadas} ofertas antiguas que no encajaban con tus filtros actuales.",
        )

    def _guardar_credenciales_gmail(self) -> None:
        config.guardar_variables_env(
            {
                "GMAIL_USER": self.ent_gmail_user.get().strip(),
                "GMAIL_APP_PASSWORD": self.ent_gmail_pass.get().strip(),
            }
        )
        messagebox.showinfo(
            "Gmail Guardado",
            "Tus credenciales de Gmail fueron guardadas localmente en tu archivo privado .env.",
        )

    def _guardar_limite_whatsapp(self) -> None:
        val = self.ent_max_wa.get().strip()
        if not val.isdigit():
            val = "0"
        config.guardar_variables_env({"MAX_WHATSAPP_POR_DIA": val})
        messagebox.showinfo(
            "WhatsApp Actualizado",
            f"Límite diario de WhatsApp configurado en {val} mensajes por día.",
        )

    # =========================================================================
    # ACCIONES EN HILOS SECUNDARIOS (SIN CONGELAR LA INTERFAZ)
    # =========================================================================
    def _abrir_login_computrabajo_thread(self) -> None:
        def _tarea() -> None:
            logging.getLogger("gui").info(
                "Abriendo ventana de Computrabajo... Inicia sesión y CIERRA el navegador cuando termines."
            )
            iniciar_sesion_portales(esperar_cierre_navegador=True)
            self.after(
                0,
                lambda: messagebox.showinfo(
                    "Sesión Guardada",
                    "Tu sesión de Computrabajo quedó guardada para las auto-postulaciones.",
                ),
            )

        threading.Thread(target=_tarea, daemon=True).start()

    def _abrir_login_whatsapp_thread(self) -> None:
        def _tarea() -> None:
            logging.getLogger("gui").info(
                "Abriendo WhatsApp Web... Escanea el QR, espera que carguen tus chats y CIERRA ese navegador."
            )
            iniciar_sesion_whatsapp(esperar_cierre_navegador=True)
            self.after(
                0,
                lambda: messagebox.showinfo(
                    "WhatsApp Vinculado",
                    "Tu sesión de WhatsApp Web quedó guardada.",
                ),
            )

        threading.Thread(target=_tarea, daemon=True).start()

    def _probar_envio_gmail_thread(self) -> None:
        self._guardar_credenciales_gmail()

        def _tarea() -> None:
            if not config.GMAIL_USER:
                self.after(
                    0,
                    lambda: messagebox.showwarning(
                        "Falta Correo", "Ingresa primero tu correo Gmail."
                    ),
                )
                return
            logging.getLogger("gui").info(
                "Enviando correo de prueba a %s...", config.GMAIL_USER
            )
            ok, msg = enviar_correo_individual(
                destinatario=config.GMAIL_USER,
                titulo_puesto="Prueba de Configuración Job Finder Desktop",
                empresa="Tu Propio Correo",
                ubicacion=config.UBICACION_OBJETIVO,
            )
            if ok:
                logging.getLogger("gui").info("Correo de prueba exitoso: %s", msg)
                self.after(
                    0,
                    lambda: messagebox.showinfo(
                        "¡Correo Enviado!",
                        f"Se envió un correo de prueba con tu CV adjunto a {config.GMAIL_USER}.\nRevisa tu bandeja de entrada.",
                    ),
                )
            else:
                logging.getLogger("gui").error("Fallo en correo de prueba: %s", msg)
                self.after(
                    0,
                    lambda: messagebox.showerror("Error al enviar correo", msg),
                )

        threading.Thread(target=_tarea, daemon=True).start()

    def _iniciar_ciclo_unico_thread(self) -> None:
        if self.ejecutando_jornada:
            return
        self._cambiar_estado_ejecucion(True, "● Motor: Ejecutando Ciclo...")

        def _tarea() -> None:
            try:
                config.recargar_configuracion()
                ejecutar_flujo_completo(respetar_horario=False)
            except Exception as exc:
                logging.getLogger("gui").error("Error durante el ciclo: %s", exc)
            finally:
                self.after(0, self._finalizar_ejecucion_ui)

        self.hilo_trabajo = threading.Thread(target=_tarea, daemon=True)
        self.hilo_trabajo.start()

    def _iniciar_jornada_continua_thread(self) -> None:
        if self.ejecutando_jornada:
            return
        self.detener_evento.clear()
        self._cambiar_estado_ejecucion(True, "● Motor: Jornada Continua Activa")

        def _tarea() -> None:
            try:
                while not self.detener_evento.is_set():
                    config.recargar_configuracion()
                    ejecutar_flujo_completo(respetar_horario=False)
                    self.after(0, self._actualizar_estadisticas_y_tabla)
                    intervalo_seg = max(5, config.INTERVALO_CICLO_MINUTOS) * 60
                    logging.getLogger("gui").info(
                        "Ciclo terminado. Próxima búsqueda automática en %d minutos (puedes pulsar 'Detener' cuando quieras)...",
                        config.INTERVALO_CICLO_MINUTOS,
                    )
                    for _ in range(intervalo_seg):
                        if self.detener_evento.is_set():
                            break
                        time.sleep(1)
            except Exception as exc:
                logging.getLogger("gui").error("Error en jornada continua: %s", exc)
            finally:
                self.after(0, self._finalizar_ejecucion_ui)

        self.hilo_trabajo = threading.Thread(target=_tarea, daemon=True)
        self.hilo_trabajo.start()

    def _detener_ejecucion(self) -> None:
        self.detener_evento.set()
        logging.getLogger("gui").warning(
            "Solicitud de detención enviada. El motor se detendrá al finalizar la oferta actual..."
        )
        self.lbl_estado_motor.configure(
            text="● Motor: Deteniendo...", text_color="#e74c3c"
        )

    def _cambiar_estado_ejecucion(self, activo: bool, texto_estado: str) -> None:
        self.ejecutando_jornada = activo
        if activo:
            self.btn_ciclo_unico.configure(state="disabled")
            self.btn_jornada.configure(state="disabled")
            self.btn_detener.configure(state="normal")
            self.lbl_estado_motor.configure(text=texto_estado, text_color="#2ecc71")
        else:
            self.btn_ciclo_unico.configure(state="normal")
            self.btn_jornada.configure(state="normal")
            self.btn_detener.configure(state="disabled")
            self.lbl_estado_motor.configure(
                text="● Motor: Detenido", text_color="#f39c12"
            )

    def _finalizar_ejecucion_ui(self) -> None:
        self._cambiar_estado_ejecucion(False, "● Motor: Detenido")
        self._actualizar_estadisticas_y_tabla()

    # =========================================================================
    # TABLA DE EMPRESAS, MÉTRICAS Y LOGS EN VIVO
    # =========================================================================
    def _actualizar_estadisticas_y_tabla(self) -> None:
        try:
            empresas = obtener_directorio_empresas()
        except Exception:
            empresas = []

        total_vacantes = len(empresas)
        total_portal = sum(
            1
            for e in empresas
            if str(e.get("postulado_en_portal", "")).upper().startswith("SI")
        )
        total_entrevistas = sum(
            1
            for e in empresas
            if str(e.get("llamaron_entrevista", "")).upper().startswith("SI")
        )
        correos_hoy = contar_envios_hoy("EMAIL")

        self.card_total.configure(text=str(total_vacantes))
        self.card_portal.configure(text=str(total_portal))
        self.card_correos.configure(text=str(correos_hoy))
        self.card_entrevistas.configure(text=str(total_entrevistas))

        self.lbl_resumen_side.configure(
            text=f"Ofertas en BD: {total_vacantes}\nAuto-postuladas: {total_portal}\nEntrevistas: {total_entrevistas}"
        )

        for item in self.tree.get_children():
            self.tree.delete(item)

        for emp in empresas:
            vid = str(emp.get("codigo_corto") or emp.get("vacante_id", ""))[:8]
            self.tree.insert(
                "",
                "end",
                values=(
                    vid,
                    emp.get("empresa", ""),
                    emp.get("titulo", ""),
                    emp.get("area_afinidad", ""),
                    emp.get("salario_ofrecido", "No esp."),
                    emp.get("postulado_en_portal", "NO"),
                    emp.get("llamaron_entrevista", "NO"),
                    emp.get("telefonos_empresa", "") or emp.get("correos_empresa", ""),
                    emp.get("url_original", ""),
                ),
            )

    def _marcar_entrevista_seleccionada(self, estado: str) -> None:
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showwarning(
                "Selecciona una empresa",
                "Haz clic primero en una fila de la tabla para marcar que te llamaron a entrevista.",
            )
            return
        valores = self.tree.item(seleccion[0], "values")
        prefijo_id = str(valores[0])
        empresa_nombre = str(valores[1])
        actualizadas = registrar_respuesta_entrevista(
            criterio=prefijo_id,
            llamaron=(estado.upper() == "SI"),
            notas="Marcado desde Interfaz de Escritorio",
        )
        if actualizadas > 0:
            exportar_reporte_empresas_csv()
            self._actualizar_estadisticas_y_tabla()
            messagebox.showinfo(
                "¡Felicidades por la Entrevista!",
                f"Se registró que '{empresa_nombre}' te llamó a entrevista.",
            )

    def _abrir_url_oferta_seleccionada(self) -> None:
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showwarning(
                "Selecciona una oferta",
                "Haz clic en una fila de la tabla para abrir la oferta en tu navegador.",
            )
            return
        valores = self.tree.item(seleccion[0], "values")
        url = str(valores[8])
        if url.startswith("http"):
            webbrowser.open(url)

    def _abrir_csv_empresas(self) -> None:
        ruta_csv = exportar_reporte_empresas_csv()
        try:
            os.startfile(str(ruta_csv))  # type: ignore[attr-defined]
        except Exception:
            messagebox.showinfo("Reporte Exportado", f"Archivo guardado en:\n{ruta_csv}")

    def _limpiar_consola(self) -> None:
        self.txt_consola.delete("1.0", "end")

    def _procesar_cola_logs(self) -> None:
        while not self.log_queue.empty():
            try:
                linea = self.log_queue.get_nowait()
                self.txt_consola.insert("end", linea + "\n")
                self.txt_consola.see("end")
            except queue.Empty:
                break
        self.after(200, self._procesar_cola_logs)


def lanzar_interfaz_escritorio() -> None:
    """Punto de entrada para abrir la aplicación de escritorio Job Finder PC."""
    app = JobFinderDesktopApp()
    app.mainloop()


if __name__ == "__main__":
    lanzar_interfaz_escritorio()
