"""
Interfaz Gráfica Minimalista y Explicativa para PC (Windows 10 y 11) - Job Finder Desktop.
Diseñada para que cualquier persona, sin conocimientos técnicos, pueda configurar sus datos,
conectar su cuenta de Computrabajo, elegir qué empleos busca y postularse automáticamente.
Todos los datos se guardan exclusivamente en la computadora de cada usuario.
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
    registrar_respuesta_entrevista,
)
from mailer import enviar_correo_individual
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

AREAS_LABELS: dict[str, str] = {
    "administrativo_atencion": "Oficina, Recepción, Caja, Facturación y Atención al Cliente",
    "logistica_operaciones": "Bodega, Inventarios, Despacho, Logística y Operaciones",
    "ventas_comercial": "Ventas en Sala, Mostrador, Dependiente y Restaurantes (Pizza Hut, Wendy's, KFC, etc.)",
    "soporte_sistemas": "Soporte Técnico, Informática, Redes y Mantenimiento de Computadoras",
    "programacion_software": "Programación, Desarrollo de Software y Bases de Datos (SQL)",
}


class QueueLogHandler(logging.Handler):
    """Envía los mensajes del sistema hacia la pantalla principal en lenguaje claro."""

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
    """Ventana principal minimalista y explicativa de Job Finder Desktop."""

    def __init__(self) -> None:
        super().__init__()

        self.title("Job Finder PC — Asistente Automático para Buscar Empleo (Windows 10 / 11)")
        self.geometry("1200x790")
        self.minsize(1040, 700)

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
        handler.setFormatter(logging.Formatter("%(asctime)s  |  %(message)s", "%H:%M:%S"))
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(handler)

    def _construir_layout_principal(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ================== MENÚ LATERAL MINIMALISTA ==================
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(7, weight=1)

        ctk.CTkLabel(
            self.sidebar,
            text="🚀 Job Finder PC",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(24, 2), sticky="w")

        ctk.CTkLabel(
            self.sidebar,
            text="Postúlate en automático",
            font=ctk.CTkFont(size=12),
            text_color="gray70",
        ).grid(row=1, column=0, padx=20, pady=(0, 18), sticky="w")

        self._crear_boton_menu(2, "▶  Inicio y Búsqueda", "Inicio")
        self._crear_boton_menu(3, "👤  Paso 1: Mis Datos y CV", "Paso 1: Mis Datos")
        self._crear_boton_menu(4, "🎯  Paso 2: Qué Trabajo Busco", "Paso 2: Qué Busco")
        self._crear_boton_menu(5, "🔑  Paso 3: Conectar Cuentas", "Paso 3: Cuentas")
        self._crear_boton_menu(6, "📋  Mis Postulaciones", "Mis Postulaciones")

        # Tarjeta de privacidad y estado en la barra lateral
        self.frame_estado_side = ctk.CTkFrame(self.sidebar, corner_radius=10)
        self.frame_estado_side.grid(row=8, column=0, padx=14, pady=10, sticky="ew")

        self.lbl_estado_motor = ctk.CTkLabel(
            self.frame_estado_side,
            text="● Estado: Listo para iniciar",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#f39c12",
        )
        self.lbl_estado_motor.pack(padx=12, pady=(10, 4), anchor="w")

        self.lbl_resumen_side = ctk.CTkLabel(
            self.frame_estado_side,
            text="Empleos encontrados: 0\nPostulados hoy: 0",
            font=ctk.CTkFont(size=12),
            justify="left",
        )
        self.lbl_resumen_side.pack(padx=12, pady=(0, 8), anchor="w")

        ctk.CTkLabel(
            self.frame_estado_side,
            text="🔒 100% Privado: Tus datos se\nguardan solo en tu propia PC.",
            font=ctk.CTkFont(size=11),
            text_color="#2ecc71",
            justify="left",
        ).pack(padx=12, pady=(0, 10), anchor="w")

        self.menu_tema = ctk.CTkOptionMenu(
            self.sidebar,
            values=["Modo Oscuro", "Modo Claro"],
            command=self._cambiar_tema,
        )
        self.menu_tema.grid(row=9, column=0, padx=14, pady=(4, 18), sticky="ew")
        self.menu_tema.set("Modo Oscuro")

        # ================== PESTAÑAS PRINCIPALES ==================
        self.tabview = ctk.CTkTabview(self, corner_radius=12)
        self.tabview.grid(row=0, column=1, padx=16, pady=12, sticky="nsew")

        self.tab_panel = self.tabview.add("Inicio")
        self.tab_perfil = self.tabview.add("Paso 1: Mis Datos")
        self.tab_rubros = self.tabview.add("Paso 2: Qué Busco")
        self.tab_conexiones = self.tabview.add("Paso 3: Cuentas")
        self.tab_empresas = self.tabview.add("Mis Postulaciones")

        self._construir_tab_panel()
        self._construir_tab_perfil()
        self._construir_tab_rubros()
        self._construir_tab_conexiones()
        self._construir_tab_empresas()

    def _crear_boton_menu(self, fila: int, texto: str, nombre_tab: str) -> None:
        btn = ctk.CTkButton(
            self.sidebar,
            text=texto,
            anchor="w",
            height=38,
            fg_color="transparent" if fila > 2 else ["#3B8ED0", "#1F6AA5"],
            border_width=0 if fila == 2 else 1,
            command=lambda: self.tabview.set(nombre_tab),
        )
        btn.grid(row=fila, column=0, padx=14, pady=5, sticky="ew")

    def _cambiar_tema(self, seleccion: str) -> None:
        ctk.set_appearance_mode("Light" if "Claro" in seleccion else "Dark")

    # =========================================================================
    # PESTAÑA 0: INICIO Y BÚSQUEDA EN VIVO
    # =========================================================================
    def _construir_tab_panel(self) -> None:
        self.tab_panel.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.tab_panel.grid_rowconfigure(3, weight=1)

        # Guía rápida de 3 pasos en la parte superior
        frame_guia = ctk.CTkFrame(self.tab_panel, corner_radius=10)
        frame_guia.grid(row=0, column=0, columnspan=4, padx=8, pady=(6, 8), sticky="ew")
        ctk.CTkLabel(
            frame_guia,
            text="💡 ¿Cómo funciona?  1️⃣ Llena tus datos y sube tu CV en 'Paso 1'   →   "
            "2️⃣ Elige tu ciudad y áreas en 'Paso 2'   →   "
            "3️⃣ Inicia sesión en Computrabajo en 'Paso 3' y dale a Buscar.",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#5dade2",
        ).pack(padx=14, pady=10, anchor="w")

        # 4 contadores simples
        self.card_total = self._crear_tarjeta_kpi(
            self.tab_panel, 0, "Ofertas Compatibles", "0", "#3498db"
        )
        self.card_portal = self._crear_tarjeta_kpi(
            self.tab_panel, 1, "Postuladas en Computrabajo", "0", "#2ecc71"
        )
        self.card_correos = self._crear_tarjeta_kpi(
            self.tab_panel, 2, "Correos Enviados Hoy", "0", "#9b59b6"
        )
        self.card_entrevistas = self._crear_tarjeta_kpi(
            self.tab_panel, 3, "Me Llamaron a Entrevista", "0", "#f1c40f"
        )

        # Botones grandes de acción
        frame_acciones = ctk.CTkFrame(self.tab_panel, corner_radius=10)
        frame_acciones.grid(row=2, column=0, columnspan=4, padx=8, pady=8, sticky="ew")

        self.btn_ciclo_unico = ctk.CTkButton(
            frame_acciones,
            text="⚡ Buscar Trabajo y Postularme Ahora",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#27ae60",
            hover_color="#1e8449",
            height=42,
            command=self._iniciar_ciclo_unico_thread,
        )
        self.btn_ciclo_unico.pack(side="left", padx=(14, 8), pady=12)

        self.btn_jornada = ctk.CTkButton(
            frame_acciones,
            text="🔄 Modo Automático Continuo (Revisar cada 45 min)",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#2980b9",
            hover_color="#1f618d",
            height=42,
            command=self._iniciar_jornada_continua_thread,
        )
        self.btn_jornada.pack(side="left", padx=8, pady=12)

        self.btn_detener = ctk.CTkButton(
            frame_acciones,
            text="⏹ Detener",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#c0392b",
            hover_color="#922b21",
            height=42,
            width=110,
            state="disabled",
            command=self._detener_ejecucion,
        )
        self.btn_detener.pack(side="left", padx=8, pady=12)

        btn_limpiar_log = ctk.CTkButton(
            frame_acciones,
            text="Limpiar Pantalla",
            fg_color="gray35",
            hover_color="gray25",
            height=42,
            width=130,
            command=self._limpiar_consola,
        )
        btn_limpiar_log.pack(side="right", padx=14, pady=12)

        # Registro de actividad
        frame_consola = ctk.CTkFrame(self.tab_panel, corner_radius=10)
        frame_consola.grid(row=3, column=0, columnspan=4, padx=8, pady=(4, 8), sticky="nsew")
        frame_consola.grid_rowconfigure(1, weight=1)
        frame_consola.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            frame_consola,
            text="📺 Lo que el asistente está haciendo en este momento:",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=0, column=0, padx=14, pady=(10, 4), sticky="w")

        self.txt_consola = ctk.CTkTextbox(
            frame_consola,
            font=ctk.CTkFont(family="Consolas", size=12),
            wrap="word",
        )
        self.txt_consola.grid(row=1, column=0, padx=12, pady=(0, 12), sticky="nsew")
        self.txt_consola.insert(
            "end",
            "¡Hola! Bienvenido a Job Finder PC.\n"
            "• Si es tu primera vez usando el programa, ve a 'Paso 1: Mis Datos' para poner tu nombre, teléfono y subir tu CV en PDF.\n"
            "• Tus datos y tu correo son 100% privados: solo se guardan en esta computadora.\n"
            + "-" * 85
            + "\n",
        )

    def _crear_tarjeta_kpi(
        self, parent: Any, col: int, titulo: str, valor: str, color: str
    ) -> ctk.CTkLabel:
        frame = ctk.CTkFrame(parent, corner_radius=10)
        frame.grid(row=1, column=col, padx=8, pady=4, sticky="ew")
        ctk.CTkLabel(
            frame, text=titulo, font=ctk.CTkFont(size=12), text_color="gray75"
        ).pack(padx=14, pady=(10, 2), anchor="w")
        lbl_v = ctk.CTkLabel(
            frame,
            text=valor,
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color=color,
        )
        lbl_v.pack(padx=14, pady=(0, 10), anchor="w")
        return lbl_v

    # =========================================================================
    # PESTAÑA 1: PASO 1 - MIS DATOS Y CV
    # =========================================================================
    def _construir_tab_perfil(self) -> None:
        scroll = ctk.CTkScrollableFrame(self.tab_perfil, corner_radius=10)
        scroll.pack(fill="both", expand=True, padx=6, pady=6)
        scroll.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            scroll,
            text="👤 Paso 1: Tu Información y Respuestas para las Empresas",
            font=ctk.CTkFont(size=17, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, padx=14, pady=(10, 2), sticky="w")

        ctk.CTkLabel(
            scroll,
            text="En Computrabajo muchas empresas hacen preguntas antes de recibir tu CV (por ejemplo: ¿Cuánto deseas ganar? o ¿Dónde vives?).\n"
            "Llena estos campos una sola vez y el asistente responderá por ti automáticamente.",
            font=ctk.CTkFont(size=12),
            text_color="gray75",
            justify="left",
        ).grid(row=1, column=0, columnspan=2, padx=14, pady=(0, 12), sticky="w")

        # 1. Subir PDF del CV (Arriba para que sea lo primero y más fácil)
        frame_cv = ctk.CTkFrame(scroll, corner_radius=10)
        frame_cv.grid(row=2, column=0, columnspan=2, padx=14, pady=(0, 12), sticky="ew")

        ctk.CTkLabel(
            frame_cv,
            text="📄 Tu Currículum (Archivo PDF):",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left", padx=14, pady=12)

        texto_cv_inicial = (
            f"Listo ({config.CV_PATH.name})"
            if config.CV_PATH.exists()
            else "Aún no has seleccionado tu PDF"
        )
        self.lbl_ruta_cv = ctk.CTkLabel(
            frame_cv,
            text=texto_cv_inicial,
            font=ctk.CTkFont(size=12),
            text_color="#2ecc71" if config.CV_PATH.exists() else "#f39c12",
        )
        self.lbl_ruta_cv.pack(side="left", padx=8, pady=12)

        ctk.CTkButton(
            frame_cv,
            text="📂 Elegir mi CV en PDF...",
            command=self._seleccionar_pdf_cv,
        ).pack(side="right", padx=14, pady=12)

        # Campos básicos explicados con sencillez
        self.ent_nombre = self._crear_campo(
            scroll, 3, 0, "Tu Nombre Completo:", "Ejemplo: Juan Pérez"
        )
        self.ent_telefono = self._crear_campo(
            scroll, 3, 1, "Tu Número de Celular / WhatsApp:", "Ejemplo: +503 7000-0000"
        )

        self.ent_edad = self._crear_campo(
            scroll,
            4,
            0,
            "Tu Edad (para no postularte a ofertas que pidan más edad):",
            "Ejemplo: 21 años",
        )
        self.ent_direccion = self._crear_campo(
            scroll,
            4,
            1,
            "Tu Dirección o Colonia donde vives:",
            "Ejemplo: Col. Ciudad Pacífica, San Miguel",
        )

        self.ent_pretension = self._crear_campo(
            scroll,
            5,
            0,
            "¿Cuánto deseas ganar al mes? (Solo el número en dólares):",
            "Ejemplo: 450",
        )
        self.ent_ultimo_salario = self._crear_campo(
            scroll,
            5,
            1,
            "¿Cuánto ganabas en tu último trabajo? (Solo el número):",
            "Ejemplo: 380",
        )

        # Estado civil e hijos
        frame_ec = ctk.CTkFrame(scroll, fg_color="transparent")
        frame_ec.grid(row=6, column=0, padx=14, pady=6, sticky="ew")
        ctk.CTkLabel(
            frame_ec, text="Tu Estado Civil:", font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", pady=(0, 4))
        self.cmb_estado_civil = ctk.CTkComboBox(
            frame_ec,
            values=["Soltero(a)", "Acompañado(a) / Unión libre", "Casado(a)"],
            height=34,
        )
        self.cmb_estado_civil.pack(fill="x")

        self.ent_hijos = self._crear_campo(
            scroll,
            6,
            1,
            "Si preguntan '¿Tiene hijos?', ¿qué deseas responder?:",
            "Ejemplo: No tengo hijos  /  Sí, 1 hijo",
        )

        # Licencia y estudios actuales
        frame_lic = ctk.CTkFrame(scroll, fg_color="transparent")
        frame_lic.grid(row=7, column=0, padx=14, pady=6, sticky="ew")
        ctk.CTkLabel(
            frame_lic,
            text="¿Tienes Licencia de Conducir o Moto/Carro propio?",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", pady=(0, 4))
        self.cmb_licencia = ctk.CTkComboBox(
            frame_lic,
            values=[
                "NO (Ignorar empleos que exijan licencia o moto)",
                "SI (Tengo licencia de conducir y/o vehículo)",
            ],
            height=34,
        )
        self.cmb_licencia.pack(fill="x")

        frame_est = ctk.CTkFrame(scroll, fg_color="transparent")
        frame_est.grid(row=7, column=1, padx=14, pady=6, sticky="ew")
        ctk.CTkLabel(
            frame_est,
            text="¿Estás estudiando actualmente?",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", pady=(0, 4))
        self.cmb_estudia = ctk.CTkComboBox(
            frame_est,
            values=[
                "NO (Ya terminé mis estudios - Disponibilidad de horario total)",
                "SI (Estudio actualmente)",
            ],
            height=34,
        )
        self.cmb_estudia.pack(fill="x")

        self.ent_nivel_academico = self._crear_campo(
            scroll,
            8,
            0,
            "Tu Nivel de Estudios (Bachillerato, Técnico o Universidad):",
            "Ejemplo: Bachiller General / Técnico en Software",
        )
        self.ent_motivo_salida = self._crear_campo(
            scroll,
            8,
            1,
            "¿Por qué saliste de tu último trabajo?:",
            "Ejemplo: Finalización de contrato y superación personal",
        )

        # Resumen corto de experiencia
        ctk.CTkLabel(
            scroll,
            text="Breve resumen de tu experiencia (para responder cuando pregunten en qué has trabajado):",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=9, column=0, columnspan=2, padx=14, pady=(10, 4), sticky="w")

        self.txt_experiencia = ctk.CTkTextbox(scroll, height=65)
        self.txt_experiencia.grid(
            row=10, column=0, columnspan=2, padx=14, pady=(0, 8), sticky="ew"
        )

        # Carta de presentación
        ctk.CTkLabel(
            scroll,
            text="Tu Carta de Presentación (se envía junto con tu CV en los portales):",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=11, column=0, columnspan=2, padx=14, pady=(6, 4), sticky="w")

        self.txt_carta = ctk.CTkTextbox(scroll, height=85)
        self.txt_carta.grid(
            row=12, column=0, columnspan=2, padx=14, pady=(0, 10), sticky="ew"
        )

        ctk.CTkButton(
            scroll,
            text="💾 Guardar Mis Datos",
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#27ae60",
            hover_color="#1e8449",
            height=44,
            command=self._guardar_perfil_usuario,
        ).grid(row=13, column=0, columnspan=2, padx=14, pady=(10, 18), sticky="ew")

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
                text=f"Listo ({origen.name})", text_color="#2ecc71"
            )
            messagebox.showinfo(
                "Currículum Cargado",
                f"Tu archivo '{origen.name}' quedó guardado en el programa para tus postulaciones.",
            )
        except Exception as exc:
            messagebox.showerror("Error al copiar PDF", str(exc))

    # =========================================================================
    # PESTAÑA 2: PASO 2 - QUÉ TRABAJO BUSCO
    # =========================================================================
    def _construir_tab_rubros(self) -> None:
        scroll = ctk.CTkScrollableFrame(self.tab_rubros, corner_radius=10)
        scroll.pack(fill="both", expand=True, padx=6, pady=6)
        scroll.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkLabel(
            scroll,
            text="🎯 Paso 2: ¿Dónde y en qué áreas quieres trabajar?",
            font=ctk.CTkFont(size=17, weight="bold"),
        ).grid(row=0, column=0, columnspan=2, padx=14, pady=(10, 4), sticky="w")

        ctk.CTkLabel(
            scroll,
            text="El asistente solo te postulará a los rubros que marques con un check (✔) y descartará automáticamente todo lo demás.",
            font=ctk.CTkFont(size=12),
            text_color="gray75",
        ).grid(row=1, column=0, columnspan=2, padx=14, pady=(0, 12), sticky="w")

        frame_ubi = ctk.CTkFrame(scroll, fg_color="transparent")
        frame_ubi.grid(row=2, column=0, padx=14, pady=6, sticky="ew")
        ctk.CTkLabel(
            frame_ubi,
            text="Ciudad o Departamento donde buscas empleo:",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(anchor="w", pady=(0, 3))
        self.cmb_ubicacion = ctk.CTkComboBox(
            frame_ubi, values=DEPARTAMENTOS_SV, height=34
        )
        self.cmb_ubicacion.pack(fill="x")

        self.ent_paginas = self._crear_campo(
            scroll,
            2,
            1,
            "¿Cuántas páginas de ofertas revisar? (Recomendado: 5 a 8):",
            "Ejemplo: 8",
        )

        # Áreas laborales
        frame_areas = ctk.CTkFrame(scroll, corner_radius=10)
        frame_areas.grid(row=3, column=0, columnspan=2, padx=14, pady=10, sticky="ew")
        ctk.CTkLabel(
            frame_areas,
            text="✔ Marca los tipos de trabajo que SÍ te interesan:",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(12, 6))

        self.vars_areas: dict[str, ctk.BooleanVar] = {}
        for clave_area, descripcion_area in AREAS_LABELS.items():
            var = ctk.BooleanVar(value=True)
            self.vars_areas[clave_area] = var
            ctk.CTkCheckBox(
                frame_areas,
                text=descripcion_area,
                variable=var,
                font=ctk.CTkFont(size=13),
            ).pack(anchor="w", padx=20, pady=6)

        # Opciones simples
        frame_switches = ctk.CTkFrame(scroll, corner_radius=10)
        frame_switches.grid(row=4, column=0, columnspan=2, padx=14, pady=8, sticky="ew")

        self.var_auto_postular = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(
            frame_switches,
            text="Postularme automáticamente en Computrabajo y contestar preguntas por mí",
            variable=self.var_auto_postular,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(anchor="w", padx=14, pady=(12, 6))

        self.var_ocultar_nav = ctk.BooleanVar(value=False)
        ctk.CTkSwitch(
            frame_switches,
            text="Ocultar la ventana del navegador mientras busca (Modo silencioso)",
            variable=self.var_ocultar_nav,
            font=ctk.CTkFont(size=12),
        ).pack(anchor="w", padx=14, pady=(4, 12))

        # Palabras bloqueadas
        ctk.CTkLabel(
            scroll,
            text="🚫 Trabajos o Empresas que NO quieres (separados por coma):",
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=5, column=0, columnspan=2, padx=14, pady=(10, 2), sticky="w")

        ctk.CTkLabel(
            scroll,
            text="Si una oferta contiene cualquiera de estas palabras (ej. motorista, cocinero, gerente, pollo campero), el asistente la saltará.",
            font=ctk.CTkFont(size=12),
            text_color="gray70",
        ).grid(row=6, column=0, columnspan=2, padx=14, pady=(0, 6), sticky="w")

        self.txt_excluidas = ctk.CTkTextbox(scroll, height=110)
        self.txt_excluidas.grid(
            row=7, column=0, columnspan=2, padx=14, pady=(0, 12), sticky="ew"
        )

        ctk.CTkButton(
            scroll,
            text="💾 Guardar Mis Preferencias de Búsqueda",
            font=ctk.CTkFont(size=15, weight="bold"),
            fg_color="#27ae60",
            hover_color="#1e8449",
            height=44,
            command=self._guardar_rubros_y_filtros,
        ).grid(row=8, column=0, columnspan=2, padx=14, pady=(8, 18), sticky="ew")

    # =========================================================================
    # PESTAÑA 3: PASO 3 - CONECTAR CUENTAS (EXPLICATIVO Y PRIVADO)
    # =========================================================================
    def _construir_tab_conexiones(self) -> None:
        scroll = ctk.CTkScrollableFrame(self.tab_conexiones, corner_radius=10)
        scroll.pack(fill="both", expand=True, padx=6, pady=6)
        scroll.grid_columnconfigure(0, weight=1)

        # Aviso claro de privacidad
        frame_priv = ctk.CTkFrame(scroll, corner_radius=10)
        frame_priv.grid(row=0, column=0, padx=14, pady=(8, 6), sticky="ew")
        ctk.CTkLabel(
            frame_priv,
            text="🔒 Privacidad Total: Cada persona que instala este programa ve sus casillas en blanco.\n"
            "Tu cuenta de Computrabajo, tu correo y tu WhatsApp se guardan únicamente dentro de tu propia computadora. Nadie más tiene acceso a ellos.",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#2ecc71",
            justify="left",
        ).pack(padx=16, pady=10, anchor="w")

        # 1. Computrabajo (Obligatorio / Principal)
        frame_ct = ctk.CTkFrame(scroll, corner_radius=10)
        frame_ct.grid(row=1, column=0, padx=14, pady=8, sticky="ew")

        ctk.CTkLabel(
            frame_ct,
            text="🌐 1. Conectar tu cuenta de Computrabajo (Recomendado - Solo se hace 1 vez)",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 4))

        ctk.CTkLabel(
            frame_ct,
            text="¿Para qué sirve?: Para que el programa pueda darle clic al botón 'Postularme' dentro de Computrabajo con tu cuenta.\n"
            "¿Cómo se hace?: Haz clic en el botón naranja de abajo, inicia sesión en Computrabajo normalmente y luego CIERRA esa ventana del navegador.",
            font=ctk.CTkFont(size=12),
            text_color="gray75",
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))

        ctk.CTkButton(
            frame_ct,
            text="🔑 Abrir Computrabajo e Iniciar Sesión",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#e67e22",
            hover_color="#d35400",
            height=40,
            command=self._abrir_login_computrabajo_thread,
        ).pack(anchor="w", padx=16, pady=(0, 14))

        # 2. Correo Gmail (Explicado paso a paso para una persona normal)
        frame_gmail = ctk.CTkFrame(scroll, corner_radius=10)
        frame_gmail.grid(row=2, column=0, padx=14, pady=8, sticky="ew")

        ctk.CTkLabel(
            frame_gmail,
            text="📧 2. Tu Correo Gmail (Opcional - Para empresas que piden enviar CV por correo)",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 4))

        ctk.CTkLabel(
            frame_gmail,
            text="¿Para qué sirve?: Algunas ofertas dicen 'Interesados enviar CV al correo rrhh@empresa.com'. Si configuras esto, el programa les enviará tu PDF automáticamente.\n"
            "Nota: Por seguridad, Google no usa tu contraseña normal, sino un código de 16 letras llamado 'Contraseña de Aplicación'.\n"
            "Si no quieres enviar correos automáticos (y solo quieres postularte en la web de Computrabajo), puedes dejar esto vacío o poner solo tu correo.",
            font=ctk.CTkFont(size=12),
            text_color="gray75",
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))

        sub_gmail = ctk.CTkFrame(frame_gmail, fg_color="transparent")
        sub_gmail.pack(fill="x", padx=16, pady=2)
        sub_gmail.grid_columnconfigure((0, 1), weight=1)

        self.ent_gmail_user = self._crear_campo(
            sub_gmail, 0, 0, "Tu Correo Electrónico (Gmail):", "tucorreo@gmail.com"
        )
        self.ent_gmail_pass = self._crear_campo(
            sub_gmail,
            0,
            1,
            "Código de 16 letras de Google (Opcional):",
            "xxxx xxxx xxxx xxxx",
        )
        self.ent_gmail_pass.configure(show="*")

        frame_btns_gmail = ctk.CTkFrame(frame_gmail, fg_color="transparent")
        frame_btns_gmail.pack(fill="x", padx=16, pady=(8, 14))

        ctk.CTkButton(
            frame_btns_gmail,
            text="💾 Guardar Mi Correo",
            fg_color="#27ae60",
            hover_color="#1e8449",
            command=self._guardar_credenciales_gmail,
        ).pack(side="left", padx=(0, 8))

        self.btn_ver_pass = ctk.CTkButton(
            frame_btns_gmail,
            text="👁 Mostrar/Ocultar Código",
            fg_color="gray35",
            width=160,
            command=self._alternar_ver_password_gmail,
        )
        self.btn_ver_pass.pack(side="left", padx=6)

        ctk.CTkButton(
            frame_btns_gmail,
            text="📨 Probar Envío a Mi Correo",
            command=self._probar_envio_gmail_thread,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            frame_btns_gmail,
            text="❓ Obtener código de 16 letras en Google",
            fg_color="gray35",
            command=lambda: webbrowser.open("https://myaccount.google.com/apppasswords"),
        ).pack(side="right")

        # 3. WhatsApp Web (Opcional)
        frame_wa = ctk.CTkFrame(scroll, corner_radius=10)
        frame_wa.grid(row=3, column=0, padx=14, pady=8, sticky="ew")

        ctk.CTkLabel(
            frame_wa,
            text="💬 3. WhatsApp Web (Opcional - Déjalo en 0 si prefieres escribir tú mismo por WhatsApp)",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 4))

        ctk.CTkLabel(
            frame_wa,
            text="Si pones el límite en 0, el programa NO enviará mensajes por tu WhatsApp (solo guardará el número de la empresa en la tabla para que tú les escribas si quieres).",
            font=ctk.CTkFont(size=12),
            text_color="gray75",
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))

        sub_wa = ctk.CTkFrame(frame_wa, fg_color="transparent")
        sub_wa.pack(fill="x", padx=16, pady=(0, 14))

        ctk.CTkLabel(
            sub_wa,
            text="Cantidad máxima de WhatsApps automáticos por día (0 = No enviar WhatsApps):",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left", padx=(0, 8))

        self.ent_max_wa = ctk.CTkEntry(sub_wa, width=65, height=34)
        self.ent_max_wa.pack(side="left", padx=6)

        ctk.CTkButton(
            sub_wa,
            text="Guardar",
            width=100,
            fg_color="#27ae60",
            hover_color="#1e8449",
            command=self._guardar_limite_whatsapp,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            sub_wa,
            text="📱 Vincular QR de WhatsApp Web",
            fg_color="#16a085",
            hover_color="#117864",
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

        frame_top = ctk.CTkFrame(self.tab_empresas, corner_radius=10)
        frame_top.grid(row=0, column=0, padx=8, pady=8, sticky="ew")

        ctk.CTkLabel(
            frame_top,
            text="📋 Historial de Ofertas y Empresas",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(side="left", padx=14, pady=10)

        ctk.CTkButton(
            frame_top,
            text="🔄 Actualizar",
            width=120,
            command=self._actualizar_estadisticas_y_tabla,
        ).pack(side="right", padx=10, pady=10)

        ctk.CTkButton(
            frame_top,
            text="📊 Abrir en Excel",
            fg_color="#27ae60",
            hover_color="#1e8449",
            width=140,
            command=self._abrir_csv_empresas,
        ).pack(side="right", padx=6, pady=10)

        ctk.CTkButton(
            frame_top,
            text="📞 ¡Me Llamaron a Entrevista!",
            fg_color="#f39c12",
            hover_color="#d68910",
            width=195,
            command=lambda: self._marcar_entrevista_seleccionada("SI"),
        ).pack(side="right", padx=6, pady=10)

        ctk.CTkButton(
            frame_top,
            text="🌐 Ver Anuncio en Internet",
            width=180,
            command=self._abrir_url_oferta_seleccionada,
        ).pack(side="right", padx=6, pady=10)

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
        self.tree.heading("id", text="Código")
        self.tree.heading("empresa", text="Empresa")
        self.tree.heading("titulo", text="Puesto de Trabajo")
        self.tree.heading("area", text="Rubro")
        self.tree.heading("salario", text="Salario")
        self.tree.heading("postulado_portal", text="¿Ya Postulado?")
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
            self.cmb_licencia.set("NO (Ignorar empleos que exijan licencia o moto)")

        if config.ESTUDIA_ACTUALMENTE.strip().upper().startswith("S"):
            self.cmb_estudia.set("SI (Estudio actualmente)")
        else:
            self.cmb_estudia.set(
                "NO (Ya terminé mis estudios - Disponibilidad de horario total)"
            )

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
            "Tus datos personales (%s) fueron guardados en esta PC.",
            config.REMITENTE_NOMBRE or "Usuario",
        )
        messagebox.showinfo(
            "Datos Guardados",
            "¡Listo! Tus datos y respuestas automáticas quedaron guardados en tu computadora.",
        )

    def _guardar_rubros_y_filtros(self) -> None:
        seleccionadas = [k for k, v in self.vars_areas.items() if v.get()]
        if not seleccionadas:
            messagebox.showwarning(
                "Elige al menos un área",
                "Marca al menos un tipo de trabajo que te interese.",
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
        messagebox.showinfo(
            "Preferencias Guardadas",
            f"¡Listo! El asistente buscará empleos en {config.UBICACION_OBJETIVO} únicamente en las áreas que marcaste.",
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
                logging.getLogger("gui").error("Ocurrió un error: %s", exc)
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
                logging.getLogger("gui").error("Ocurrió un error: %s", exc)
            finally:
                self.after(0, self._finalizar_ejecucion_ui)

        self.hilo_trabajo = threading.Thread(target=_tarea, daemon=True)
        self.hilo_trabajo.start()

    def _detener_ejecucion(self) -> None:
        self.detener_evento.set()
        logging.getLogger("gui").warning(
            "Deteniendo al terminar la oferta actual..."
        )
        self.lbl_estado_motor.configure(
            text="● Estado: Deteniendo...", text_color="#e74c3c"
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
                text="● Estado: Listo para iniciar", text_color="#f39c12"
            )

    def _finalizar_ejecucion_ui(self) -> None:
        self._cambiar_estado_ejecucion(False, "● Estado: Listo para iniciar")
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
            text=f"Empleos encontrados: {total_vacantes}\nPostulados en portal: {total_portal}\nEntrevistas: {total_entrevistas}"
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
        while not self.log_queue.empty():
            try:
                linea = self.log_queue.get_nowait()
                self.txt_consola.insert("end", linea + "\n")
                self.txt_consola.see("end")
            except queue.Empty:
                break
        self.after(200, self._procesar_cola_logs)


def lanzar_interfaz_escritorio() -> None:
    """Inicia la ventana gráfica de Job Finder PC."""
    app = JobFinderDesktopApp()
    app.mainloop()


if __name__ == "__main__":
    lanzar_interfaz_escritorio()
