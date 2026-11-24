"""
Interfaz Gráfica Moderna, Amigable y Explicativa para PC (Windows 10 y 11) - Job Finder Desktop v1.1.
Incluye:
- Búsqueda por Interés Positivo ("Lo que SÍ quiero": puestos deseados, clic rápido en etiquetas y salario mínimo).
- Catálogo completo de las 16 categorías de empleo de El Salvador en tarjetas desplegables con checklist.
- Nivel Académico seleccionable + interruptor para filtrar ofertas que exijan títulos superiores.
- Selector de Nivel de Inglés (Sin inglés, A1, A2, B1, B2, C1, C2) + constructor interactivo para agregar otros idiomas.
- Diseño moderno con tarjetas estilizadas, navegación lateral con indicador activo y privacidad 100% local.
"""

import logging
import os
import queue
import shutil
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

import customtkinter as ctk

import config
from config import (
    CATALOGO_EMPLEOS_SV,
    NIVELES_ACADEMICOS_ORDEN,
    NIVELES_INGLES_LISTA,
)
from database import (
    contar_envios_hoy,
    depurar_vacantes_existentes,
    exportar_reporte_empresas_csv,
    inicializar_bd,
    obtener_directorio_empresas,
    registrar_respuesta_entrevista,
)
from mailer import enviar_correo_individual, enviar_reporte_error_diagnostico
from main import ejecutar_flujo_completo
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

IDIOMAS_SUGERIDOS = [
    "Francés",
    "Portugués",
    "Italiano",
    "Alemán",
    "Chino Mandarín",
    "Japonés",
    "Coreano",
    "Lengua de Señas (LESSA)",
]

NIVELES_IDIOMA_GENERAL = [
    "Básico (A1-A2)",
    "Intermedio (B1-B2)",
    "Avanzado (C1)",
    "Nativo / Fluido (C2)",
]


class QueueLogHandler(logging.Handler):
    """Envía los mensajes del sistema hacia la pantalla principal en tiempo real."""

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
    """Ventana principal moderna y amigable de Job Finder PC."""

    def __init__(self) -> None:
        super().__init__()

        self.title("Job Finder PC — Buscador y Auto-Postulador Inteligente de Empleo en El Salvador")
        self.geometry("1260x830")
        self.minsize(1080, 720)

        inicializar_bd()
        config.recargar_configuracion()

        self.log_queue: queue.Queue[str] = queue.Queue()
        self._configurar_logging_gui()

        self.ejecutando_jornada = False
        self.detener_evento = threading.Event()
        self.hilo_trabajo: threading.Thread | None = None
        self.botones_menu: dict[str, ctk.CTkButton] = {}
        self.ultimo_error_titulo: str = "Sin errores registrados en esta sesión"
        self.ultimo_error_traza: str = "No se ha detectado ningún fallo inesperado hasta el momento."
        self.modal_error_abierto = False

        self._instalar_capturador_errores()
        self._construir_layout_principal()
        self._cargar_valores_en_formularios()
        self._actualizar_estadisticas_y_tabla()
        self.after(250, self._procesar_cola_logs)

    def _configurar_logging_gui(self) -> None:
        handler = QueueLogHandler(self.log_queue)
        handler.setFormatter(logging.Formatter("%(asctime)s  •  %(message)s", "%H:%M:%S"))
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(handler)

    def _construir_layout_principal(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ================== BARRA LATERAL MODERNA ==================
        self.sidebar = ctk.CTkFrame(
            self, width=255, corner_radius=0, fg_color=("#ecf0f1", "#111827")
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(7, weight=1)

        frame_brand = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        frame_brand.grid(row=0, column=0, padx=18, pady=(22, 14), sticky="ew")

        ctk.CTkLabel(
            frame_brand,
            text="🚀 Job Finder PC",
            font=ctk.CTkFont(size=23, weight="bold"),
        ).pack(anchor="w")

        ctk.CTkLabel(
            frame_brand,
            text="Tu Asistente Personal de Empleo",
            font=ctk.CTkFont(size=12),
            text_color=("#555555", "#9ca3af"),
        ).pack(anchor="w", pady=(2, 0))

        self._crear_boton_menu(1, "▶   Panel de Inicio", "Inicio")
        self._crear_boton_menu(2, "👤   1. Mi Perfil, Idiomas y CV", "Paso 1: Mi Perfil")
        self._crear_boton_menu(3, "🎯   2. Qué Empleo Quiero", "Paso 2: Qué Quiero")
        self._crear_boton_menu(4, "🔑   3. Conectar Cuentas", "Paso 3: Cuentas")
        self._crear_boton_menu(5, "📋   Mis Postulaciones", "Mis Postulaciones")

        # Tarjeta de estado y privacidad en la barra lateral
        self.frame_estado_side = ctk.CTkFrame(
            self.sidebar, corner_radius=12, fg_color=("#dfe6e9", "#1f2937")
        )
        self.frame_estado_side.grid(row=8, column=0, padx=14, pady=10, sticky="ew")

        self.lbl_estado_motor = ctk.CTkLabel(
            self.frame_estado_side,
            text="● Estado: Listo para buscar",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#f59e0b",
        )
        self.lbl_estado_motor.pack(padx=14, pady=(12, 4), anchor="w")

        self.lbl_resumen_side = ctk.CTkLabel(
            self.frame_estado_side,
            text="Ofertas compatibles: 0\nPostuladas en portal: 0\nLlamadas a entrevista: 0",
            font=ctk.CTkFont(size=12),
            justify="left",
        )
        self.lbl_resumen_side.pack(padx=14, pady=(0, 8), anchor="w")

        ctk.CTkLabel(
            self.frame_estado_side,
            text="🔒 100% Privado en tu PC\nTus datos no se comparten.",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#10b981",
            justify="left",
        ).pack(padx=14, pady=(0, 12), anchor="w")

        ctk.CTkButton(
            self.sidebar,
            text="🛠️ Reportar un Error / Diagnóstico",
            height=34,
            corner_radius=8,
            fg_color=("#cbd5e1", "#374151"),
            hover_color=("#94a3b8", "#4b5563"),
            text_color=("#1e293b", "#f3f4f6"),
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self._mostrar_ventana_reporte_error(
                self.ultimo_error_titulo, self.ultimo_error_traza, es_manual=True
            ),
        ).grid(row=9, column=0, padx=14, pady=(2, 6), sticky="ew")

        self.menu_tema = ctk.CTkOptionMenu(
            self.sidebar,
            values=["🌙 Modo Oscuro", "☀️ Modo Claro"],
            command=self._cambiar_tema,
            height=34,
        )
        self.menu_tema.grid(row=10, column=0, padx=14, pady=(2, 18), sticky="ew")
        self.menu_tema.set("🌙 Modo Oscuro")

        # ================== CONTENEDOR PRINCIPAL ==================
        self.tabview = ctk.CTkTabview(
            self,
            corner_radius=14,
            command=self._actualizar_botones_menu_activo,
        )
        self.tabview.grid(row=0, column=1, padx=16, pady=12, sticky="nsew")

        self.tab_panel = self.tabview.add("Inicio")
        self.tab_perfil = self.tabview.add("Paso 1: Mi Perfil")
        self.tab_rubros = self.tabview.add("Paso 2: Qué Quiero")
        self.tab_conexiones = self.tabview.add("Paso 3: Cuentas")
        self.tab_empresas = self.tabview.add("Mis Postulaciones")

        self._construir_tab_panel()
        self._construir_tab_perfil()
        self._construir_tab_rubros()
        self._construir_tab_conexiones()
        self._construir_tab_empresas()
        self._actualizar_botones_menu_activo()

    def _crear_boton_menu(self, fila: int, texto: str, nombre_tab: str) -> None:
        btn = ctk.CTkButton(
            self.sidebar,
            text=texto,
            anchor="w",
            height=42,
            corner_radius=10,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda: self._ir_a_pestana(nombre_tab),
        )
        btn.grid(row=fila, column=0, padx=14, pady=5, sticky="ew")
        self.botones_menu[nombre_tab] = btn

    def _ir_a_pestana(self, nombre_tab: str) -> None:
        self.tabview.set(nombre_tab)
        self._actualizar_botones_menu_activo()

    def _actualizar_botones_menu_activo(self) -> None:
        actual = self.tabview.get()
        for tab_name, btn in self.botones_menu.items():
            if tab_name == actual:
                btn.configure(
                    fg_color=("#2563eb", "#2563eb"),
                    text_color="#ffffff",
                    border_width=0,
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=("#1f2937", "#e5e7eb"),
                    border_width=1,
                    border_color=("#cbd5e1", "#374151"),
                )

    def _cambiar_tema(self, seleccion: str) -> None:
        ctk.set_appearance_mode("Light" if "Claro" in seleccion else "Dark")

    # =========================================================================
    # PESTAÑA 0: PANEL DE INICIO
    # =========================================================================
    def _construir_tab_panel(self) -> None:
        self.tab_panel.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.tab_panel.grid_rowconfigure(3, weight=1)

        # Banner de bienvenida amigable
        banner = ctk.CTkFrame(
            self.tab_panel, corner_radius=12, fg_color=("#dbeafe", "#1e3a8a")
        )
        banner.grid(row=0, column=0, columnspan=4, padx=8, pady=(6, 10), sticky="ew")
        ctk.CTkLabel(
            banner,
            text="✨ ¡Bienvenido! Configura tu perfil en 3 pasos sencillos:   "
            "1️⃣ Pon tus datos, estudios e idiomas   →   "
            "2️⃣ Marca qué trabajo y salario buscas   →   "
            "3️⃣ Conecta Computrabajo y dale a Buscar.",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("#1e40af", "#bfdbfe"),
        ).pack(padx=16, pady=12, anchor="w")

        # 4 Tarjetas KPI modernas
        self.card_total = self._crear_tarjeta_kpi(
            self.tab_panel, 0, "🔎 Ofertas Compatibles", "0", "#3b82f6"
        )
        self.card_portal = self._crear_tarjeta_kpi(
            self.tab_panel, 1, "✅ Postuladas en Portal", "0", "#10b981"
        )
        self.card_correos = self._crear_tarjeta_kpi(
            self.tab_panel, 2, "📧 Correos Enviados Hoy", "0", "#8b5cf6"
        )
        self.card_entrevistas = self._crear_tarjeta_kpi(
            self.tab_panel, 3, "📞 Llamaron a Entrevista", "0", "#f59e0b"
        )

        # Barra de ejecución
        frame_acciones = ctk.CTkFrame(self.tab_panel, corner_radius=12)
        frame_acciones.grid(row=2, column=0, columnspan=4, padx=8, pady=8, sticky="ew")

        self.btn_ciclo_unico = ctk.CTkButton(
            frame_acciones,
            text="⚡ Buscar Trabajo y Postularme Ahora",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            height=44,
            corner_radius=10,
            command=self._iniciar_ciclo_unico_thread,
        )
        self.btn_ciclo_unico.pack(side="left", padx=(14, 8), pady=12)

        self.btn_jornada = ctk.CTkButton(
            frame_acciones,
            text="🔄 Modo Automático Continuo (Cada 45 min)",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            height=44,
            corner_radius=10,
            command=self._iniciar_jornada_continua_thread,
        )
        self.btn_jornada.pack(side="left", padx=8, pady=12)

        self.btn_detener = ctk.CTkButton(
            frame_acciones,
            text="⏹ Detener",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#ef4444",
            hover_color="#dc2626",
            height=44,
            width=115,
            corner_radius=10,
            state="disabled",
            command=self._detener_ejecucion,
        )
        self.btn_detener.pack(side="left", padx=8, pady=12)

        ctk.CTkButton(
            frame_acciones,
            text="🧹 Limpiar Pantalla",
            fg_color="gray35",
            hover_color="gray25",
            height=44,
            width=145,
            corner_radius=10,
            command=self._limpiar_consola,
        ).pack(side="right", padx=14, pady=12)

        # Consola en vivo
        frame_consola = ctk.CTkFrame(self.tab_panel, corner_radius=12)
        frame_consola.grid(row=3, column=0, columnspan=4, padx=8, pady=(4, 8), sticky="nsew")
        frame_consola.grid_rowconfigure(1, weight=1)
        frame_consola.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame_consola,
            text="📺 Actividad en Vivo (Ofertas analizadas, filtros aplicados y respuestas enviadas):",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, padx=16, pady=(12, 4), sticky="w")

        self.txt_consola = ctk.CTkTextbox(
            frame_consola,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word",
            corner_radius=8,
        )
        self.txt_consola.grid(row=1, column=0, padx=14, pady=(0, 14), sticky="nsew")
        self.txt_consola.insert(
            "end",
            "¡Hola! Todo está listo en Job Finder PC.\n"
            "• Ve a '1. Mi Perfil, Idiomas y CV' para subir tu currículum, indicar tu nivel académico y los idiomas que hablas.\n"
            "• Ve a '2. Qué Empleo Quiero' para escribir qué puestos deseas, tu salario mínimo y marcar tus categorías.\n"
            + "─" * 85
            + "\n",
        )

    def _crear_tarjeta_kpi(
        self, parent: Any, col: int, titulo: str, valor: str, color: str
    ) -> ctk.CTkLabel:
        frame = ctk.CTkFrame(parent, corner_radius=12)
        frame.grid(row=1, column=col, padx=8, pady=4, sticky="ew")
        ctk.CTkLabel(
            frame, text=titulo, font=ctk.CTkFont(size=12, weight="bold"), text_color="gray70"
        ).pack(padx=16, pady=(12, 2), anchor="w")
        lbl_v = ctk.CTkLabel(
            frame,
            text=valor,
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=color,
        )
        lbl_v.pack(padx=16, pady=(0, 12), anchor="w")
        return lbl_v

    # =========================================================================
    # PESTAÑA 1: MI PERFIL, ESTUDIOS, IDIOMAS Y CV
    # =========================================================================
    def _construir_tab_perfil(self) -> None:
        scroll = ctk.CTkScrollableFrame(self.tab_perfil, corner_radius=12)
        scroll.pack(fill="both", expand=True, padx=6, pady=6)
        scroll.grid_columnconfigure(0, weight=1)

        # ---- TARJETA 1: ARCHIVO PDF DEL CV ----
        card_cv = ctk.CTkFrame(scroll, corner_radius=12)
        card_cv.grid(row=0, column=0, padx=10, pady=(8, 10), sticky="ew")

        ctk.CTkLabel(
            card_cv,
            text="📄 1. Tu Currículum Vítae (Archivo PDF)",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(12, 2))

        sub_cv = ctk.CTkFrame(card_cv, fg_color="transparent")
        sub_cv.pack(fill="x", padx=16, pady=(2, 12))

        texto_cv_inicial = (
            f"✔ Archivo cargado: {config.CV_PATH.name}"
            if config.CV_PATH.exists()
            else "⚠ Aún no has elegido el archivo PDF de tu CV"
        )
        self.lbl_ruta_cv = ctk.CTkLabel(
            sub_cv,
            text=texto_cv_inicial,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#10b981" if config.CV_PATH.exists() else "#f59e0b",
        )
        self.lbl_ruta_cv.pack(side="left", pady=4)

        ctk.CTkButton(
            sub_cv,
            text="📂 Seleccionar mi CV en PDF...",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=36,
            command=self._seleccionar_pdf_cv,
        ).pack(side="right")

        # ---- TARJETA 2: DATOS PERSONALES Y SALARIALES ----
        card_personal = ctk.CTkFrame(scroll, corner_radius=12)
        card_personal.grid(row=1, column=0, padx=10, pady=8, sticky="ew")
        card_personal.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            card_personal,
            text="👤 2. Datos Personales y Respuestas para 'Preguntas de Selección'",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, padx=16, pady=(14, 2), sticky="w")

        ctk.CTkLabel(
            card_personal,
            text="Cuando una empresa en Computrabajo te pregunte tu teléfono, dirección, edad o salario esperado, el asistente responderá con estos datos:",
            font=ctk.CTkFont(size=12),
            text_color="gray70",
        ).grid(row=1, column=0, columnspan=2, padx=16, pady=(0, 10), sticky="w")

        self.ent_nombre = self._crear_campo(
            card_personal, 2, 0, "Tu Nombre Completo:", "Ejemplo: Juan Carlos Pérez"
        )
        self.ent_telefono = self._crear_campo(
            card_personal, 2, 1, "Tu Celular / WhatsApp:", "Ejemplo: +503 7000-0000"
        )
        self.ent_edad = self._crear_campo(
            card_personal,
            3,
            0,
            "Tu Edad Actual (filtra ofertas que pidan mayor edad):",
            "Ejemplo: 25 años",
        )
        self.ent_direccion = self._crear_campo(
            card_personal,
            3,
            1,
            "Tu Dirección o Colonia donde vives:",
            "Ejemplo: Colonia Escalón, San Salvador",
        )
        self.ent_pretension = self._crear_campo(
            card_personal,
            4,
            0,
            "¿Cuánto deseas ganar al mes? (USD - solo número):",
            "Ejemplo: 500",
        )
        self.ent_ultimo_salario = self._crear_campo(
            card_personal,
            4,
            1,
            "¿Cuánto ganabas en tu último empleo? (USD - solo número):",
            "Ejemplo: 400",
        )

        frame_ec = ctk.CTkFrame(card_personal, fg_color="transparent")
        frame_ec.grid(row=5, column=0, padx=14, pady=6, sticky="ew")
        ctk.CTkLabel(
            frame_ec, text="Tu Estado Civil:", font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", pady=(0, 3))
        self.cmb_estado_civil = ctk.CTkComboBox(
            frame_ec,
            values=["Soltero(a)", "Acompañado(a) / Unión libre", "Casado(a)"],
            height=34,
        )
        self.cmb_estado_civil.pack(fill="x")

        self.ent_hijos = self._crear_campo(
            card_personal,
            5,
            1,
            "Si preguntan '¿Tiene hijos?', ¿qué responder?:",
            "Ejemplo: No tengo hijos  /  Sí, 1 hijo",
        )

        frame_lic = ctk.CTkFrame(card_personal, fg_color="transparent")
        frame_lic.grid(row=6, column=0, padx=14, pady=(6, 14), sticky="ew")
        ctk.CTkLabel(
            frame_lic,
            text="¿Posees Licencia de Conducir o Moto/Vehículo propio?",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", pady=(0, 3))
        self.cmb_licencia = ctk.CTkComboBox(
            frame_lic,
            values=[
                "NO (Ignorar empleos que pidan licencia o moto)",
                "SI (Tengo licencia de conducir y/o vehículo)",
            ],
            height=34,
        )
        self.cmb_licencia.pack(fill="x")

        self.ent_motivo_salida = self._crear_campo(
            card_personal,
            6,
            1,
            "Motivo de salida de tu último trabajo:",
            "Ejemplo: Búsqueda de crecimiento profesional",
        )

        # ---- TARJETA 3: NIVEL ACADÉMICO Y FILTRO DE ESTUDIOS ----
        card_edu = ctk.CTkFrame(scroll, corner_radius=12)
        card_edu.grid(row=2, column=0, padx=10, pady=8, sticky="ew")
        card_edu.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            card_edu,
            text="🎓 3. Tu Nivel Académico y Filtro de Estudios",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, padx=16, pady=(14, 4), sticky="w")

        frame_niv = ctk.CTkFrame(card_edu, fg_color="transparent")
        frame_niv.grid(row=1, column=0, padx=14, pady=6, sticky="ew")
        ctk.CTkLabel(
            frame_niv,
            text="Selecciona tu Nivel Académico Actual:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", pady=(0, 3))
        self.cmb_nivel_cat = ctk.CTkComboBox(
            frame_niv,
            values=list(NIVELES_ACADEMICOS_ORDEN.keys()),
            height=34,
        )
        self.cmb_nivel_cat.pack(fill="x")

        frame_est = ctk.CTkFrame(card_edu, fg_color="transparent")
        frame_est.grid(row=1, column=1, padx=14, pady=6, sticky="ew")
        ctk.CTkLabel(
            frame_est,
            text="¿Estás estudiando actualmente (tienes horarios de clases)?",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", pady=(0, 3))
        self.cmb_estudia = ctk.CTkComboBox(
            frame_est,
            values=[
                "NO (Ya egresé/gradué - Disponibilidad completa)",
                "SI (Estudio actualmente)",
            ],
            height=34,
        )
        self.cmb_estudia.pack(fill="x")

        self.ent_nivel_academico = self._crear_campo(
            card_edu,
            2,
            0,
            "Nombre de tu Carrera o Título obtenido (para responder en encuestas):",
            "Ejemplo: Bachiller General / Técnico en Administración",
        )
        self.ent_nivel_academico.master.grid_configure(columnspan=2)

        self.var_filtrar_academico = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(
            card_edu,
            text="Usar mi Nivel Académico como filtro (Descartar ofertas que exijan título universitario graduado o maestría si aún no lo tengo)",
            variable=self.var_filtrar_academico,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=3, column=0, columnspan=2, padx=16, pady=(6, 14), sticky="w")

        # ---- TARJETA 4: IDIOMAS Y NIVEL DE INGLÉS ----
        card_idiomas = ctk.CTkFrame(scroll, corner_radius=12)
        card_idiomas.grid(row=3, column=0, padx=10, pady=8, sticky="ew")
        card_idiomas.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            card_idiomas,
            text="🌎 4. Nivel de Inglés y Otros Idiomas que Hablas",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, padx=16, pady=(14, 2), sticky="w")

        ctk.CTkLabel(
            card_idiomas,
            text="El asistente usará tu nivel de inglés para responder encuestas y para descartar plazas 100% bilingües si tu nivel es básico.",
            font=ctk.CTkFont(size=12),
            text_color="gray70",
        ).grid(row=1, column=0, columnspan=2, padx=16, pady=(0, 8), sticky="w")

        frame_ing = ctk.CTkFrame(card_idiomas, fg_color="transparent")
        frame_ing.grid(row=2, column=0, padx=14, pady=6, sticky="ew")
        ctk.CTkLabel(
            frame_ing,
            text="Tu Nivel de Inglés:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", pady=(0, 3))
        self.cmb_ingles = ctk.CTkComboBox(
            frame_ing,
            values=NIVELES_INGLES_LISTA,
            height=34,
        )
        self.cmb_ingles.pack(fill="x")

        self.ent_otros_idiomas = self._crear_campo(
            card_idiomas,
            2,
            1,
            "Idiomas que dominas y su nivel (puedes escribir o usar el botón de abajo):",
            "Ejemplo: Español (Nativo), Francés (Básico)",
        )

        # Constructor rápido para agregar otro idioma con 1 clic
        frame_add_lang = ctk.CTkFrame(card_idiomas, fg_color="transparent")
        frame_add_lang.grid(
            row=3, column=0, columnspan=2, padx=14, pady=(4, 14), sticky="ew"
        )
        ctk.CTkLabel(
            frame_add_lang,
            text="➕ Agregar otro idioma rápido:",
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(0, 8))

        self.cmb_nuevo_idioma = ctk.CTkComboBox(
            frame_add_lang, values=IDIOMAS_SUGERIDOS, width=165, height=32
        )
        self.cmb_nuevo_idioma.pack(side="left", padx=4)

        self.cmb_nuevo_idioma_nivel = ctk.CTkComboBox(
            frame_add_lang, values=NIVELES_IDIOMA_GENERAL, width=165, height=32
        )
        self.cmb_nuevo_idioma_nivel.pack(side="left", padx=4)

        ctk.CTkButton(
            frame_add_lang,
            text="+ Añadir a mi lista",
            width=135,
            height=32,
            fg_color="#3b82f6",
            command=self._agregar_idioma_a_lista,
        ).pack(side="left", padx=8)

        # ---- TARJETA 5: EXPERIENCIA Y CARTA DE PRESENTACIÓN ----
        card_exp = ctk.CTkFrame(scroll, corner_radius=12)
        card_exp.grid(row=4, column=0, padx=10, pady=8, sticky="ew")

        ctk.CTkLabel(
            card_exp,
            text="📝 5. Resumen de tu Experiencia y Carta de Presentación",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 4))

        ctk.CTkLabel(
            card_exp,
            text="Resumen corto de tu experiencia laboral (se usa cuando preguntan '¿Tiene experiencia en caja / bodega / atención?'):",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(4, 3))

        self.txt_experiencia = ctk.CTkTextbox(card_exp, height=65, corner_radius=8)
        self.txt_experiencia.pack(fill="x", padx=16, pady=(0, 10))

        ctk.CTkLabel(
            card_exp,
            text="Tu Carta de Presentación (se envía automáticamente cuando una oferta la solicita):",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(2, 3))

        self.txt_carta = ctk.CTkTextbox(card_exp, height=80, corner_radius=8)
        self.txt_carta.pack(fill="x", padx=16, pady=(0, 14))

        ctk.CTkButton(
            scroll,
            text="💾 Guardar Mi Perfil, Estudios e Idiomas",
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            height=46,
            corner_radius=10,
            command=self._guardar_perfil_usuario,
        ).grid(row=5, column=0, padx=10, pady=(10, 20), sticky="ew")

    def _agregar_idioma_a_lista(self) -> None:
        idioma = self.cmb_nuevo_idioma.get().strip()
        nivel = self.cmb_nuevo_idioma_nivel.get().strip()
        if not idioma:
            return
        actual = self.ent_otros_idiomas.get().strip()
        nuevo_item = f"{idioma} ({nivel})"
        if nuevo_item.lower() not in actual.lower():
            texto_final = f"{actual}, {nuevo_item}" if actual else nuevo_item
            self._set_entry(self.ent_otros_idiomas, texto_final)

    def _crear_campo(
        self, parent: Any, row: int, col: int, label_text: str, placeholder: str
    ) -> ctk.CTkEntry:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=row, column=col, padx=14, pady=5, sticky="ew")
        ctk.CTkLabel(
            frame, text=label_text, font=ctk.CTkFont(size=12, weight="bold")
        ).pack(anchor="w", pady=(0, 3))
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
                text=f"✔ Archivo cargado: {origen.name}", text_color="#10b981"
            )
            messagebox.showinfo(
                "Currículum Cargado",
                f"Tu archivo '{origen.name}' quedó guardado para tus postulaciones.",
            )
        except Exception as exc:
            messagebox.showerror("Error al copiar PDF", str(exc))

    # =========================================================================
    # PESTAÑA 2: QUÉ EMPLEO QUIERO (FILTRO POSITIVO + 16 CATEGORÍAS EL SALVADOR)
    # =========================================================================
    def _construir_tab_rubros(self) -> None:
        scroll = ctk.CTkScrollableFrame(self.tab_rubros, corner_radius=12)
        scroll.pack(fill="both", expand=True, padx=6, pady=6)
        scroll.grid_columnconfigure(0, weight=1)

        # ---- SECCIÓN 1: BÚSQUEDA POR INTERÉS POSITIVO ("LO QUE SÍ QUIERO") ----
        card_positivo = ctk.CTkFrame(
            scroll, corner_radius=12, border_width=1, border_color=("#3b82f6", "#1d4ed8")
        )
        card_positivo.grid(row=0, column=0, padx=10, pady=(8, 10), sticky="ew")
        card_positivo.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkLabel(
            card_positivo,
            text="✨ 1. Búsqueda por Interés: ¿Qué puesto y qué salario QUIERES?",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=("#1d4ed8", "#60a5fa"),
        ).grid(row=0, column=0, columnspan=3, padx=16, pady=(14, 2), sticky="w")

        ctk.CTkLabel(
            card_positivo,
            text="Aquí puedes filtrar en positivo: elige tu ciudad, el salario mínimo que aceptas y escribe los puestos específicos que te interesan.",
            font=ctk.CTkFont(size=12),
            text_color="gray70",
        ).grid(row=1, column=0, columnspan=3, padx=16, pady=(0, 10), sticky="w")

        # Ciudad, Salario mínimo deseado y Páginas
        frame_ubi = ctk.CTkFrame(card_positivo, fg_color="transparent")
        frame_ubi.grid(row=2, column=0, padx=14, pady=6, sticky="ew")
        ctk.CTkLabel(
            frame_ubi,
            text="📍 Departamento / Ciudad en El Salvador:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", pady=(0, 3))
        self.cmb_ubicacion = ctk.CTkComboBox(
            frame_ubi, values=DEPARTAMENTOS_SV, height=34
        )
        self.cmb_ubicacion.pack(fill="x")

        self.ent_salario_min = self._crear_campo(
            card_positivo,
            2,
            1,
            "💵 Salario Mínimo que Aceptas (USD, 0 = Cualquiera):",
            "Ejemplo: 400 (Descarta si pagan menos)",
        )

        self.ent_paginas = self._crear_campo(
            card_positivo,
            2,
            2,
            "📄 Páginas a revisar por portal (Recomendado: 8):",
            "Ejemplo: 8",
        )

        # Puestos específicos deseados (Filtro Positivo)
        ctk.CTkLabel(
            card_positivo,
            text="🎯 Puestos o Empresas en los que ESTÁS INTERESADO (Lo que SÍ quieres, separados por coma):",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=3, column=0, columnspan=3, padx=14, pady=(10, 2), sticky="w")

        ctk.CTkLabel(
            card_positivo,
            text="Tip: Puedes escribirlos aquí o hacer clic en los botones de puestos dentro de las categorías desplegables de abajo para agregarlos.",
            font=ctk.CTkFont(size=11),
            text_color="gray70",
        ).grid(row=4, column=0, columnspan=3, padx=14, pady=(0, 4), sticky="w")

        self.ent_puestos_interes = ctk.CTkEntry(
            card_positivo,
            placeholder_text="Ejemplo: cajero, auxiliar de bodega, recepcionista, digitador, soporte tecnico, pizza hut, wendys...",
            height=36,
        )
        self.ent_puestos_interes.grid(
            row=5, column=0, columnspan=3, padx=14, pady=(0, 14), sticky="ew"
        )

        # ---- SECCIÓN 2: CHECKLIST Y CATEGORÍAS DESPLEGABLES DE TODOS LOS TRABAJOS EN EL SALVADOR ----
        card_cats = ctk.CTkFrame(scroll, corner_radius=12)
        card_cats.grid(row=1, column=0, padx=10, pady=8, sticky="ew")
        card_cats.grid_columnconfigure(0, weight=1)

        header_cats = ctk.CTkFrame(card_cats, fg_color="transparent")
        header_cats.pack(fill="x", padx=16, pady=(14, 4))

        ctk.CTkLabel(
            header_cats,
            text="📂 2. Categorías de Empleo en El Salvador (Checklist + Desplegable de Puestos)",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left")

        ctk.CTkButton(
            header_cats,
            text="Desmarcar Todas",
            width=125,
            height=30,
            fg_color="gray35",
            command=lambda: self._marcar_todas_categorias(False),
        ).pack(side="right", padx=4)

        ctk.CTkButton(
            header_cats,
            text="Marcar Todas",
            width=115,
            height=30,
            fg_color="#2563eb",
            command=lambda: self._marcar_todas_categorias(True),
        ).pack(side="right", padx=4)

        ctk.CTkLabel(
            card_cats,
            text="Marca con un check (✔) las áreas donde quieres buscar trabajo. Haz clic en '▾ Ver puestos' en cualquier categoría para ver todos los trabajos y agregar los que te gusten:",
            font=ctk.CTkFont(size=12),
            text_color="gray70",
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))

        self.vars_areas: dict[str, ctk.BooleanVar] = {}
        self.frames_detalle_cat: dict[str, ctk.CTkFrame] = {}
        self.chips_construidos: set[str] = set()

        for clave_area, info_cat in CATALOGO_EMPLEOS_SV.items():
            contenedor_cat = ctk.CTkFrame(
                card_cats, corner_radius=10, fg_color=("#e2e8f0", "#1f2937")
            )
            contenedor_cat.pack(fill="x", padx=14, pady=4)

            fila_sup = ctk.CTkFrame(contenedor_cat, fg_color="transparent")
            fila_sup.pack(fill="x", padx=12, pady=8)

            var = ctk.BooleanVar(value=True)
            self.vars_areas[clave_area] = var

            chk = ctk.CTkCheckBox(
                fila_sup,
                text=info_cat["titulo"],
                variable=var,
                font=ctk.CTkFont(size=13, weight="bold"),
            )
            chk.pack(side="left")

            # Panel desplegable con carga diferida (Lazy Loading) para no consumir RAM ni CPU en Intel Celeron
            frame_det = ctk.CTkFrame(contenedor_cat, fg_color="transparent")
            self.frames_detalle_cat[clave_area] = frame_det

            btn_toggle = ctk.CTkButton(
                fila_sup,
                text="▾ Ver puestos",
                width=110,
                height=26,
                fg_color=("#cbd5e1", "#374151"),
                text_color=("#1e293b", "#e5e7eb"),
                font=ctk.CTkFont(size=11),
            )
            btn_toggle.configure(
                command=lambda k=clave_area, b=btn_toggle: self._alternar_desplegable_categoria(
                    k, b
                )
            )
            btn_toggle.pack(side="right")

        # ---- SECCIÓN 3: LO QUE NO QUIERO (FILTRO NEGATIVO) ----
        card_negativo = ctk.CTkFrame(scroll, corner_radius=12)
        card_negativo.grid(row=2, column=0, padx=10, pady=8, sticky="ew")

        ctk.CTkLabel(
            card_negativo,
            text="🚫 3. Lo que NO Quieres (Puestos o Empresas Bloqueadas)",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 2))

        ctk.CTkLabel(
            card_negativo,
            text="Cualquier anuncio que tenga una de estas palabras será descartado automáticamente:",
            font=ctk.CTkFont(size=12),
            text_color="gray70",
        ).pack(anchor="w", padx=16, pady=(0, 6))

        self.txt_excluidas = ctk.CTkTextbox(card_negativo, height=95, corner_radius=8)
        self.txt_excluidas.pack(fill="x", padx=16, pady=(0, 10))

        self.var_auto_postular = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(
            card_negativo,
            text="Auto-postularme en 1 clic dentro de Computrabajo y responder preguntas de selección",
            variable=self.var_auto_postular,
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(2, 6))

        self.var_ocultar_nav = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(
            card_negativo,
            text="Ocultar la ventana del navegador mientras busca (Modo silencioso)",
            variable=self.var_ocultar_nav,
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=16, pady=(0, 6))

        self.var_bajos_recursos = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(
            card_negativo,
            text="⚡ Modo Ultra-Ligero (PCs con 2GB RAM, Intel Celeron y Disco Duro HDD — Bloquea imágenes/anuncios y ahorra 70% de memoria)",
            variable=self.var_bajos_recursos,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("#059669", "#34d399"),
        ).pack(anchor="w", padx=16, pady=(0, 14))

        ctk.CTkButton(
            scroll,
            text="💾 Guardar Qué Empleo Quiero y Mis Filtros",
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            height=46,
            corner_radius=10,
            command=self._guardar_rubros_y_filtros,
        ).grid(row=3, column=0, padx=10, pady=(10, 20), sticky="ew")

    def _alternar_desplegable_categoria(
        self, clave_area: str, boton: ctk.CTkButton
    ) -> None:
        frame = self.frames_detalle_cat[clave_area]
        if frame.winfo_ismapped():
            frame.pack_forget()
            boton.configure(text="▾ Ver puestos")
        else:
            if clave_area not in self.chips_construidos:
                self.chips_construidos.add(clave_area)
                info_cat = CATALOGO_EMPLEOS_SV[clave_area]
                ctk.CTkLabel(
                    frame,
                    text="Haz clic en un puesto para agregarlo a tu caja de interés ('Lo que SÍ quiero'):",
                    font=ctk.CTkFont(size=11),
                    text_color="gray70",
                ).pack(anchor="w", padx=10, pady=(2, 4))

                wrap_chips = ctk.CTkFrame(frame, fg_color="transparent")
                wrap_chips.pack(fill="x", padx=8, pady=(0, 8))

                for idx_p, nombre_puesto in enumerate(info_cat["ejemplos"]):
                    chip = ctk.CTkButton(
                        wrap_chips,
                        text=f"+ {nombre_puesto}",
                        height=26,
                        corner_radius=12,
                        fg_color=("#3b82f6", "#2563eb"),
                        hover_color=("#1d4ed8", "#1e40af"),
                        font=ctk.CTkFont(size=11),
                        command=lambda p=nombre_puesto, k=clave_area: self._agregar_puesto_interes_chip(
                            p, k
                        ),
                    )
                    chip.grid(
                        row=idx_p // 4, column=idx_p % 4, padx=4, pady=3, sticky="w"
                    )
            frame.pack(fill="x", padx=12, pady=(0, 8))
            boton.configure(text="▴ Ocultar puestos")

    def _marcar_todas_categorias(self, estado: bool) -> None:
        for var in self.vars_areas.values():
            var.set(estado)

    def _agregar_puesto_interes_chip(self, puesto: str, clave_area: str) -> None:
        self.vars_areas[clave_area].set(True)
        actual = self.ent_puestos_interes.get().strip()
        puesto_clean = puesto.split("/")[0].strip()
        existentes = [p.strip().lower() for p in actual.split(",") if p.strip()]
        if puesto_clean.lower() not in existentes:
            nuevo = f"{actual}, {puesto_clean}" if actual else puesto_clean
            self._set_entry(self.ent_puestos_interes, nuevo)

    # =========================================================================
    # PESTAÑA 3: CONECTAR CUENTAS
    # =========================================================================
    def _construir_tab_conexiones(self) -> None:
        scroll = ctk.CTkScrollableFrame(self.tab_conexiones, corner_radius=12)
        scroll.pack(fill="both", expand=True, padx=6, pady=6)
        scroll.grid_columnconfigure(0, weight=1)

        frame_priv = ctk.CTkFrame(
            scroll, corner_radius=12, fg_color=("#d1fae5", "#064e3b")
        )
        frame_priv.grid(row=0, column=0, padx=10, pady=(8, 8), sticky="ew")
        ctk.CTkLabel(
            frame_priv,
            text="🔒 Privacidad Garantizada: Tus cuentas y tu correo solo existen en tu propia computadora.\n"
            "Cuando otra persona instala Job Finder PC, todas estas casillas aparecen completamente en blanco.",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=("#065f46", "#a7f3d0"),
            justify="left",
        ).pack(padx=16, pady=12, anchor="w")

        # 1. Computrabajo
        frame_ct = ctk.CTkFrame(scroll, corner_radius=12)
        frame_ct.grid(row=1, column=0, padx=10, pady=8, sticky="ew")

        ctk.CTkLabel(
            frame_ct,
            text="🌐 1. Conectar tu Cuenta de Computrabajo (Paso Principal)",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 4))

        ctk.CTkLabel(
            frame_ct,
            text="Haz clic en el botón naranja, inicia sesión en tu cuenta de Computrabajo y luego CIERRA esa ventana del navegador.\n"
            "Con eso el asistente ya podrá presionar 'Postularme' y contestar las preguntas de las empresas por ti.",
            font=ctk.CTkFont(size=12),
            text_color="gray70",
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))

        ctk.CTkButton(
            frame_ct,
            text="🔑 Abrir Computrabajo e Iniciar Sesión",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#f59e0b",
            hover_color="#d97706",
            height=42,
            corner_radius=10,
            command=self._abrir_login_computrabajo_thread,
        ).pack(anchor="w", padx=16, pady=(0, 14))

        # 2. Gmail
        frame_gmail = ctk.CTkFrame(scroll, corner_radius=12)
        frame_gmail.grid(row=2, column=0, padx=10, pady=8, sticky="ew")

        ctk.CTkLabel(
            frame_gmail,
            text="📧 2. Tu Correo Gmail (Opcional - Para ofertas que piden enviar CV por correo)",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 4))

        ctk.CTkLabel(
            frame_gmail,
            text="Si un anuncio incluye el correo de Recursos Humanos (ej. rrhh@empresa.com), el asistente les enviará tu CV en PDF.\n"
            "Si solo deseas postularte dentro de la web de Computrabajo, puedes dejar el código de 16 letras vacío.",
            font=ctk.CTkFont(size=12),
            text_color="gray70",
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))

        sub_gmail = ctk.CTkFrame(frame_gmail, fg_color="transparent")
        sub_gmail.pack(fill="x", padx=16, pady=2)
        sub_gmail.grid_columnconfigure((0, 1), weight=1)

        self.ent_gmail_user = self._crear_campo(
            sub_gmail, 0, 0, "Tu Correo Gmail:", "tucorreo@gmail.com"
        )
        self.ent_gmail_pass = self._crear_campo(
            sub_gmail,
            0,
            1,
            "Código de 16 letras de Google (Contraseña de Aplicación):",
            "xxxx xxxx xxxx xxxx",
        )
        self.ent_gmail_pass.configure(show="*")

        frame_btns_gmail = ctk.CTkFrame(frame_gmail, fg_color="transparent")
        frame_btns_gmail.pack(fill="x", padx=16, pady=(8, 14))

        ctk.CTkButton(
            frame_btns_gmail,
            text="💾 Guardar Mi Correo",
            fg_color="#10b981",
            hover_color="#059669",
            command=self._guardar_credenciales_gmail,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            frame_btns_gmail,
            text="👁 Mostrar / Ocultar Código",
            fg_color="gray35",
            width=165,
            command=self._alternar_ver_password_gmail,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            frame_btns_gmail,
            text="📨 Probar Envío a Mi Correo",
            command=self._probar_envio_gmail_thread,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            frame_btns_gmail,
            text="❓ Crear código de 16 letras en Google",
            fg_color="gray35",
            command=lambda: webbrowser.open("https://myaccount.google.com/apppasswords"),
        ).pack(side="right")

        # 3. WhatsApp Web
        frame_wa = ctk.CTkFrame(scroll, corner_radius=12)
        frame_wa.grid(row=3, column=0, padx=10, pady=8, sticky="ew")

        ctk.CTkLabel(
            frame_wa,
            text="💬 3. WhatsApp Web (Opcional - Pon 0 si prefieres escribir tú mismo por WhatsApp)",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 4))

        sub_wa = ctk.CTkFrame(frame_wa, fg_color="transparent")
        sub_wa.pack(fill="x", padx=16, pady=(4, 14))

        ctk.CTkLabel(
            sub_wa,
            text="Máximo de WhatsApps automáticos por día (0 = Desactivado):",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left", padx=(0, 8))

        self.ent_max_wa = ctk.CTkEntry(sub_wa, width=65, height=34)
        self.ent_max_wa.pack(side="left", padx=6)

        ctk.CTkButton(
            sub_wa,
            text="Guardar",
            width=100,
            fg_color="#10b981",
            hover_color="#059669",
            command=self._guardar_limite_whatsapp,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            sub_wa,
            text="📱 Vincular QR de WhatsApp Web",
            fg_color="#0d9488",
            hover_color="#0f766e",
            command=self._abrir_login_whatsapp_thread,
        ).pack(side="right")

    def _alternar_ver_password_gmail(self) -> None:
        actual = self.ent_gmail_pass.cget("show")
        self.ent_gmail_pass.configure(show="" if actual == "*" else "*")

    # =========================================================================
    # PESTAÑA 4: MIS POSTULACIONES
    # =========================================================================
    def _construir_tab_empresas(self) -> None:
        self.tab_empresas.grid_columnconfigure(0, weight=1)
        self.tab_empresas.grid_rowconfigure(1, weight=1)

        frame_top = ctk.CTkFrame(self.tab_empresas, corner_radius=12)
        frame_top.grid(row=0, column=0, padx=8, pady=8, sticky="ew")

        ctk.CTkLabel(
            frame_top,
            text="📋 Historial de Empresas y Postulaciones",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(side="left", padx=14, pady=10)

        ctk.CTkButton(
            frame_top,
            text="🔄 Actualizar",
            width=115,
            command=self._actualizar_estadisticas_y_tabla,
        ).pack(side="right", padx=10, pady=10)

        ctk.CTkButton(
            frame_top,
            text="📊 Abrir en Excel",
            fg_color="#10b981",
            hover_color="#059669",
            width=140,
            command=self._abrir_csv_empresas,
        ).pack(side="right", padx=6, pady=10)

        ctk.CTkButton(
            frame_top,
            text="📞 ¡Me Llamaron a Entrevista!",
            fg_color="#f59e0b",
            hover_color="#d97706",
            width=195,
            command=lambda: self._marcar_entrevista_seleccionada("SI"),
        ).pack(side="right", padx=6, pady=10)

        ctk.CTkButton(
            frame_top,
            text="🌐 Ver Anuncio en Web",
            width=175,
            command=self._abrir_url_oferta_seleccionada,
        ).pack(side="right", padx=6, pady=10)

        frame_tabla = ctk.CTkFrame(self.tab_empresas, corner_radius=12)
        frame_tabla.grid(row=1, column=0, padx=8, pady=4, sticky="nsew")
        frame_tabla.grid_rowconfigure(0, weight=1)
        frame_tabla.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "Treeview",
            background="#1e293b",
            foreground="#f8fafc",
            rowheight=32,
            fieldbackground="#1e293b",
            font=("Segoe UI", 10),
        )
        style.configure(
            "Treeview.Heading",
            background="#0f172a",
            foreground="#ffffff",
            font=("Segoe UI", 10, "bold"),
        )
        style.map("Treeview", background=[("selected", "#2563eb")])

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
        self.tree.heading("id", text="Código")
        self.tree.heading("empresa", text="Empresa")
        self.tree.heading("titulo", text="Puesto de Trabajo")
        self.tree.heading("area", text="Categoría")
        self.tree.heading("salario", text="Salario")
        self.tree.heading("postulado_portal", text="¿Postulado?")
        self.tree.heading("llamaron", text="¿Te Llamaron?")
        self.tree.heading("telefonos", text="Teléfono / Correo")
        self.tree.heading("url", text="Enlace Web")

        self.tree.column("id", width=60, anchor="center")
        self.tree.column("empresa", width=210)
        self.tree.column("titulo", width=240)
        self.tree.column("area", width=130)
        self.tree.column("salario", width=95, anchor="center")
        self.tree.column("postulado_portal", width=135, anchor="center")
        self.tree.column("llamaron", width=95, anchor="center")
        self.tree.column("telefonos", width=135)
        self.tree.column("url", width=170)

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
            self.cmb_licencia.set("SI (Tengo licencia de conducir y/o vehículo)")
        else:
            self.cmb_licencia.set("NO (Ignorar empleos que pidan licencia o moto)")

        if config.ESTUDIA_ACTUALMENTE.strip().upper().startswith("S"):
            self.cmb_estudia.set("SI (Estudio actualmente)")
        else:
            self.cmb_estudia.set("NO (Ya egresé/gradué - Disponibilidad completa)")

        self.cmb_nivel_cat.set(config.NIVEL_ACADEMICO_CATEGORIA)
        self.var_filtrar_academico.set(config.FILTRAR_POR_NIVEL_ACADEMICO)
        self._set_entry(self.ent_nivel_academico, config.NIVEL_ACADEMICO)
        self._set_entry(self.ent_motivo_salida, config.MOTIVO_SALIDA_ULTIMO_EMPLEO)

        self.cmb_ingles.set(config.NIVEL_INGLES)
        self._set_entry(self.ent_otros_idiomas, config.OTROS_IDIOMAS)

        self.txt_experiencia.delete("1.0", "end")
        self.txt_experiencia.insert("1.0", config.RESUMEN_EXPERIENCIA_CV)

        self.txt_carta.delete("1.0", "end")
        self.txt_carta.insert("1.0", config.CARTA_PRESENTACION)

        self.cmb_ubicacion.set(config.UBICACION_OBJETIVO)
        self._set_entry(self.ent_salario_min, str(config.SALARIO_MINIMO_FILTRO))
        self._set_entry(self.ent_paginas, str(config.PAGINAS_MAXIMAS))
        self._set_entry(self.ent_puestos_interes, ", ".join(config.PUESTOS_INTERES))

        areas_activas = set(config.AREAS_ACTIVAS)
        for clave, var in self.vars_areas.items():
            var.set(clave in areas_activas)

        self.var_auto_postular.set(config.AUTO_POSTULAR_PORTAL)
        self.var_ocultar_nav.set(config.HEADLESS_SCRAPER)
        self.var_bajos_recursos.set(config.MODO_BAJOS_RECURSOS)

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
            "NIVEL_ACADEMICO_CATEGORIA": self.cmb_nivel_cat.get().strip(),
            "FILTRAR_POR_NIVEL_ACADEMICO": (
                "True" if self.var_filtrar_academico.get() else "False"
            ),
            "NIVEL_ACADEMICO": self.ent_nivel_academico.get().strip(),
            "NIVEL_INGLES": self.cmb_ingles.get().strip(),
            "OTROS_IDIOMAS": self.ent_otros_idiomas.get().strip(),
            "MOTIVO_SALIDA_ULTIMO_EMPLEO": self.ent_motivo_salida.get().strip(),
            "RESUMEN_EXPERIENCIA_CV": self.txt_experiencia.get("1.0", "end").strip(),
            "CARTA_PRESENTACION": self.txt_carta.get("1.0", "end").strip(),
        }
        config.guardar_variables_env(datos)
        logging.getLogger("gui").info(
            "Perfil guardado: %s | Nivel: %s | Inglés: %s",
            config.REMITENTE_NOMBRE or "Candidato",
            config.NIVEL_ACADEMICO_CATEGORIA,
            config.NIVEL_INGLES,
        )
        messagebox.showinfo(
            "Perfil Guardado",
            "¡Listo! Tus datos personales, nivel académico, idiomas y respuestas automáticas se guardaron con éxito.",
        )

    def _guardar_rubros_y_filtros(self) -> None:
        seleccionadas = [k for k, v in self.vars_areas.items() if v.get()]
        intereses_raw = self.ent_puestos_interes.get().strip()
        if not seleccionadas and not intereses_raw:
            messagebox.showwarning(
                "Elige qué trabajo buscas",
                "Marca al menos una categoría o escribe un puesto de interés.",
            )
            return

        palabras_raw = self.txt_excluidas.get("1.0", "end").replace("\n", ",")
        palabras_limpias = ",".join(
            [p.strip() for p in palabras_raw.split(",") if p.strip()]
        )
        intereses_limpios = ",".join(
            [p.strip() for p in intereses_raw.split(",") if p.strip()]
        )
        paginas_str = self.ent_paginas.get().strip()
        if not paginas_str.isdigit() or int(paginas_str) < 1:
            paginas_str = "8"

        sal_min_str = self.ent_salario_min.get().strip()
        if not sal_min_str.isdigit():
            sal_min_str = "0"

        datos = {
            "UBICACION_OBJETIVO": self.cmb_ubicacion.get().strip() or "San Miguel",
            "SALARIO_MINIMO_FILTRO": sal_min_str,
            "PAGINAS_MAXIMAS": paginas_str,
            "PUESTOS_INTERES": intereses_limpios,
            "AREAS_ACTIVAS": ",".join(seleccionadas),
            "AUTO_POSTULAR_PORTAL": "True" if self.var_auto_postular.get() else "False",
            "HEADLESS_SCRAPER": "True" if self.var_ocultar_nav.get() else "False",
            "MODO_BAJOS_RECURSOS": "True" if self.var_bajos_recursos.get() else "False",
            "PALABRAS_EXCLUIDAS": palabras_limpias,
        }
        config.guardar_variables_env(datos)
        eliminadas = depurar_vacantes_existentes()
        exportar_reporte_empresas_csv()
        self._actualizar_estadisticas_y_tabla()
        messagebox.showinfo(
            "Preferencias Guardadas",
            f"¡Listo! El asistente buscará empleos en {config.UBICACION_OBJETIVO} según tus categorías, puestos de interés y salario mínimo (${config.SALARIO_MINIMO_FILTRO}).",
        )

    def _guardar_credenciales_gmail(self) -> None:
        config.guardar_variables_env(
            {
                "GMAIL_USER": self.ent_gmail_user.get().strip(),
                "GMAIL_APP_PASSWORD": self.ent_gmail_pass.get().strip(),
            }
        )
        messagebox.showinfo(
            "Correo Guardado",
            "Tu correo quedó guardado de forma privada en tu computadora.",
        )

    def _guardar_limite_whatsapp(self) -> None:
        val = self.ent_max_wa.get().strip()
        if not val.isdigit():
            val = "0"
        config.guardar_variables_env({"MAX_WHATSAPP_POR_DIA": val})
        messagebox.showinfo(
            "Guardado",
            f"Límite de WhatsApps automáticos configurado en: {val} por día.",
        )

    # =========================================================================
    # ACCIONES EN SEGUNDO PLANO
    # =========================================================================
    def _abrir_login_computrabajo_thread(self) -> None:
        def _tarea() -> None:
            logging.getLogger("gui").info(
                "Abriendo Computrabajo... Inicia sesión con tu cuenta y luego CIERRA esa ventana del navegador."
            )
            iniciar_sesion_portales(esperar_cierre_navegador=True)
            self.after(
                0,
                lambda: messagebox.showinfo(
                    "Cuenta Conectada",
                    "Tu sesión de Computrabajo quedó guardada en tu computadora.",
                ),
            )

        threading.Thread(target=_tarea, daemon=True).start()

    def _abrir_login_whatsapp_thread(self) -> None:
        def _tarea() -> None:
            logging.getLogger("gui").info(
                "Abriendo WhatsApp Web... Escanea el código QR y luego CIERRA esa ventana del navegador."
            )
            iniciar_sesion_whatsapp(esperar_cierre_navegador=True)
            self.after(
                0,
                lambda: messagebox.showinfo(
                    "WhatsApp Conectado",
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
                        "Falta tu correo", "Escribe primero tu correo Gmail."
                    ),
                )
                return
            logging.getLogger("gui").info(
                "Enviando correo de prueba a %s...", config.GMAIL_USER
            )
            ok, msg = enviar_correo_individual(
                destinatario=config.GMAIL_USER,
                titulo_puesto="Prueba de Job Finder PC",
                empresa="Prueba Personal",
                ubicacion=config.UBICACION_OBJETIVO,
            )
            if ok:
                self.after(
                    0,
                    lambda: messagebox.showinfo(
                        "¡Prueba Exitosa!",
                        f"Se envió un correo de prueba con tu CV adjunto a {config.GMAIL_USER}.",
                    ),
                )
            else:
                self.after(
                    0,
                    lambda: messagebox.showerror("No se pudo enviar", msg),
                )

        threading.Thread(target=_tarea, daemon=True).start()

    def _iniciar_ciclo_unico_thread(self) -> None:
        if self.ejecutando_jornada:
            return
        self._cambiar_estado_ejecucion(True, "● Estado: Buscando y postulando...")

        def _tarea() -> None:
            try:
                config.recargar_configuracion()
                ejecutar_flujo_completo(respetar_horario=False)
            except Exception as exc:
                traza = traceback.format_exc()
                logging.getLogger("gui").error("Ocurrió un error inesperado: %s", exc)
                self._registrar_y_notificar_error(str(exc), traza)
            finally:
                self.after(0, self._finalizar_ejecucion_ui)

        self.hilo_trabajo = threading.Thread(target=_tarea, daemon=True)
        self.hilo_trabajo.start()

    def _iniciar_jornada_continua_thread(self) -> None:
        if self.ejecutando_jornada:
            return
        self.detener_evento.clear()
        self._cambiar_estado_ejecucion(True, "● Estado: Modo Automático Activo")

        def _tarea() -> None:
            try:
                while not self.detener_evento.is_set():
                    config.recargar_configuracion()
                    ejecutar_flujo_completo(respetar_horario=False)
                    self.after(0, self._actualizar_estadisticas_y_tabla)
                    intervalo_seg = max(5, config.INTERVALO_CICLO_MINUTOS) * 60
                    logging.getLogger("gui").info(
                        "Revisión terminada. El asistente volverá a buscar ofertas nuevas en %d minutos...",
                        config.INTERVALO_CICLO_MINUTOS,
                    )
                    for _ in range(intervalo_seg):
                        if self.detener_evento.is_set():
                            break
                        time.sleep(1)
            except Exception as exc:
                traza = traceback.format_exc()
                logging.getLogger("gui").error("Ocurrió un error inesperado: %s", exc)
                self._registrar_y_notificar_error(str(exc), traza)
            finally:
                self.after(0, self._finalizar_ejecucion_ui)

        self.hilo_trabajo = threading.Thread(target=_tarea, daemon=True)
        self.hilo_trabajo.start()

    def _detener_ejecucion(self) -> None:
        self.detener_evento.set()
        logging.getLogger("gui").warning("Deteniendo al terminar la oferta actual...")
        self.lbl_estado_motor.configure(
            text="● Estado: Deteniendo...", text_color="#ef4444"
        )

    def _cambiar_estado_ejecucion(self, activo: bool, texto_estado: str) -> None:
        self.ejecutando_jornada = activo
        if activo:
            self.btn_ciclo_unico.configure(state="disabled")
            self.btn_jornada.configure(state="disabled")
            self.btn_detener.configure(state="normal")
            self.lbl_estado_motor.configure(text=texto_estado, text_color="#10b981")
        else:
            self.btn_ciclo_unico.configure(state="normal")
            self.btn_jornada.configure(state="normal")
            self.btn_detener.configure(state="disabled")
            self.lbl_estado_motor.configure(
                text="● Estado: Listo para buscar", text_color="#f59e0b"
            )

    def _finalizar_ejecucion_ui(self) -> None:
        self._cambiar_estado_ejecucion(False, "● Estado: Listo para buscar")
        self._actualizar_estadisticas_y_tabla()

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
            text=f"Ofertas compatibles: {total_vacantes}\nPostuladas en portal: {total_portal}\nLlamadas a entrevista: {total_entrevistas}"
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
                "Selecciona una fila",
                "Haz clic primero sobre una empresa de la tabla.",
            )
            return
        valores = self.tree.item(seleccion[0], "values")
        prefijo_id = str(valores[0])
        empresa_nombre = str(valores[1])
        actualizadas = registrar_respuesta_entrevista(
            criterio=prefijo_id,
            llamaron=(estado.upper() == "SI"),
            notas="Marcado desde Job Finder PC",
        )
        if actualizadas > 0:
            exportar_reporte_empresas_csv()
            self._actualizar_estadisticas_y_tabla()
            messagebox.showinfo(
                "¡Excelente!",
                f"Se marcó que '{empresa_nombre}' te llamó a entrevista.",
            )

    def _abrir_url_oferta_seleccionada(self) -> None:
        seleccion = self.tree.selection()
        if not seleccion:
            messagebox.showwarning(
                "Selecciona una oferta",
                "Haz clic sobre una oferta de la tabla para abrirla en el navegador.",
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
            messagebox.showinfo("Excel Guardado", f"Archivo guardado en:\n{ruta_csv}")

    def _limpiar_consola(self) -> None:
        self.txt_consola.delete("1.0", "end")

    def _procesar_cola_logs(self) -> None:
        nuevas_lineas: list[str] = []
        while not self.log_queue.empty():
            try:
                nuevas_lineas.append(self.log_queue.get_nowait())
            except queue.Empty:
                break
        if nuevas_lineas:
            self.txt_consola.insert("end", "\n".join(nuevas_lineas) + "\n")
            # Limitar la consola a máximo 250 líneas en RAM para PCs con 2GB de RAM
            total_lineas = int(self.txt_consola.index("end-1c").split(".")[0])
            if total_lineas > 250:
                self.txt_consola.delete("1.0", f"{total_lineas - 200}.0")
            self.txt_consola.see("end")
        self.after(400, self._procesar_cola_logs)

    # =========================================================================
    # SISTEMA AUTOMÁTICO DE REPORTE DE ERRORES Y DIAGNÓSTICO (DESTINO OCULTO)
    # =========================================================================
    def _instalar_capturador_errores(self) -> None:
        """Captura errores inesperados en la interfaz o en hilos secundarios."""
        self.report_callback_exception = self._capturar_excepcion_tkinter

        def _hook_hilo(args: threading.ExceptHookArgs) -> None:
            traza = "".join(
                traceback.format_exception(
                    args.exc_type, args.exc_value, args.exc_traceback
                )
            )
            titulo = f"{args.exc_type.__name__}: {args.exc_value}"
            self._registrar_y_notificar_error(titulo, traza)

        threading.excepthook = _hook_hilo

    def _capturar_excepcion_tkinter(
        self, exc_type: Any, exc_value: Any, exc_tb: Any
    ) -> None:
        traza = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        titulo = f"{getattr(exc_type, '__name__', 'Error')}: {exc_value}"
        self._registrar_y_notificar_error(titulo, traza)

    def _registrar_y_notificar_error(self, titulo: str, traza: str) -> None:
        self.ultimo_error_titulo = titulo
        self.ultimo_error_traza = traza
        if not self.modal_error_abierto:
            self.after(
                0,
                lambda: self._mostrar_ventana_reporte_error(
                    titulo, traza, es_manual=False
                ),
            )

    def _mostrar_ventana_reporte_error(
        self, titulo_error: str, detalle_traza: str, es_manual: bool = False
    ) -> None:
        """
        Muestra una ventana amigable con el diagnóstico del error y los botones
        'Mandar Reporte de Error' o 'No Mandar', sin mostrar jamás el correo del desarrollador.
        """
        if self.modal_error_abierto and not es_manual:
            return
        self.modal_error_abierto = True

        ventana = ctk.CTkToplevel(self)
        ventana.title("Diagnóstico de Error — Job Finder PC")
        ventana.geometry("650x500")
        ventana.minsize(560, 440)
        ventana.transient(self)
        ventana.grab_set()

        def _al_cerrar() -> None:
            self.modal_error_abierto = False
            ventana.destroy()

        ventana.protocol("WM_DELETE_WINDOW", _al_cerrar)

        encabezado = (
            "🛠️ Enviar Diagnóstico o Reportar un Problema"
            if es_manual
            else "⚠️ Se detectó un error inesperado en la aplicación"
        )
        ctk.CTkLabel(
            ventana,
            text=encabezado,
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color="#f59e0b" if es_manual else "#ef4444",
        ).pack(anchor="w", padx=20, pady=(16, 4))

        ctk.CTkLabel(
            ventana,
            text="A continuación se muestra el diagnóstico técnico de lo que ocurrió.\n"
            "¿Deseas mandar este diagnóstico al soporte técnico del programa para que podamos solucionarlo?\n"
            "(No se enviará ninguna contraseña ni archivo personal).",
            font=ctk.CTkFont(size=12),
            text_color="gray75",
            justify="left",
        ).pack(anchor="w", padx=20, pady=(0, 10))

        ctk.CTkLabel(
            ventana,
            text="Motivo / Descripción del problema (puedes agregar un comentario si deseas):",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", padx=20, pady=(2, 3))

        ent_resumen = ctk.CTkEntry(ventana, height=34)
        ent_resumen.pack(fill="x", padx=20, pady=(0, 8))
        ent_resumen.insert(0, titulo_error)

        ctk.CTkLabel(
            ventana,
            text="Detalle técnico del diagnóstico que se enviará:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", padx=20, pady=(2, 3))

        txt_diag = ctk.CTkTextbox(
            ventana,
            height=190,
            font=ctk.CTkFont(family="Consolas", size=11),
            corner_radius=8,
        )
        txt_diag.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        txt_diag.insert("1.0", detalle_traza)

        lbl_estado_envio = ctk.CTkLabel(
            ventana, text="", font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl_estado_envio.pack(padx=20, pady=(0, 6))

        frame_botones = ctk.CTkFrame(ventana, fg_color="transparent")
        frame_botones.pack(fill="x", padx=20, pady=(4, 16))

        btn_no_mandar = ctk.CTkButton(
            frame_botones,
            text="✖ No Mandar",
            fg_color="gray35",
            hover_color="gray25",
            height=40,
            width=150,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=_al_cerrar,
        )
        btn_no_mandar.pack(side="right", padx=(8, 0))

        btn_mandar = ctk.CTkButton(
            frame_botones,
            text="📨 Mandar Diagnóstico del Error",
            fg_color="#10b981",
            hover_color="#059669",
            height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        btn_mandar.pack(side="right", padx=8)

        def _accion_mandar() -> None:
            resumen_actual = ent_resumen.get().strip() or "Error reportado por usuario"
            traza_actual = txt_diag.get("1.0", "end").strip()
            ultimos_logs = self.txt_consola.get("1.0", "end").strip()[-2500:]
            btn_mandar.configure(state="disabled", text="Enviando diagnóstico...")
            btn_no_mandar.configure(state="disabled")
            lbl_estado_envio.configure(
                text="Enviando reporte de diagnóstico al soporte...",
                text_color="#3b82f6",
            )

            def _hilo_envio() -> None:
                ok, mensaje = enviar_reporte_error_diagnostico(
                    titulo_error=resumen_actual,
                    detalle_tecnico=traza_actual,
                    ultimos_logs=ultimos_logs,
                )

                def _terminar_ui() -> None:
                    if not ventana.winfo_exists():
                        return
                    if ok:
                        messagebox.showinfo("Diagnóstico Enviado", mensaje)
                        _al_cerrar()
                    else:
                        btn_mandar.configure(
                            state="normal", text="📨 Reintentar Mandar Diagnóstico"
                        )
                        btn_no_mandar.configure(state="normal", text="Cerrar")
                        lbl_estado_envio.configure(text=mensaje, text_color="#f59e0b")

                self.after(0, _terminar_ui)

            threading.Thread(target=_hilo_envio, daemon=True).start()

        btn_mandar.configure(command=_accion_mandar)


def lanzar_interfaz_escritorio() -> None:
    """Inicia la ventana gráfica de Job Finder PC."""
    app = JobFinderDesktopApp()
    app.mainloop()


if __name__ == "__main__":
    lanzar_interfaz_escritorio()
