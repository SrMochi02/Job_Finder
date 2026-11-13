"""
Módulo de Base de Datos Relacional en SQLite (Fase 1).
Gestiona las tablas 'vacantes' y 'postulaciones' para evitar postularse
dos veces a la misma oferta o reclutador en San Miguel.
"""

import hashlib
import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Any

from config import DB_PATH


def obtener_conexion(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """Crea y retorna una conexión SQLite con soporte para llaves foráneas y filas tipo dict."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def generar_hash_vacante(titulo: str, empresa: str, portal: str) -> str:
    """
    Genera un identificador único SHA-256 a partir de titulo + empresa + portal
    normalizados en minúsculas y sin espacios redundantes.
    """
    clave_normalizada = (
        f"{titulo.strip().lower()}|{empresa.strip().lower()}|{portal.strip().lower()}"
    )
    return hashlib.sha256(clave_normalizada.encode("utf-8")).hexdigest()


def inicializar_bd(db_path: Path = DB_PATH) -> None:
    """Crea las tablas 'vacantes' y 'postulaciones' si no existen."""
    with obtener_conexion(db_path) as conn:
        cursor = conn.cursor()

        # Tabla principal de vacantes detectadas
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS vacantes (
                id TEXT PRIMARY KEY,
                portal TEXT NOT NULL,
                titulo TEXT NOT NULL,
                empresa TEXT NOT NULL,
                ubicacion TEXT NOT NULL,
                url_original TEXT NOT NULL,
                descripcion_cruda TEXT NOT NULL,
                fecha_deteccion TEXT NOT NULL
            );
            """
        )

        # Tabla relacional de postulaciones por canal (EMAIL o WHATSAPP)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS postulaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vacante_id TEXT NOT NULL,
                canal TEXT NOT NULL CHECK(canal IN ('EMAIL', 'WHATSAPP')),
                contacto_destino TEXT NOT NULL,
                estado TEXT NOT NULL CHECK(estado IN ('PENDIENTE', 'ENVIADO', 'ERROR')) DEFAULT 'PENDIENTE',
                timestamp_envio TEXT,
                mensaje_log TEXT,
                FOREIGN KEY (vacante_id) REFERENCES vacantes(id) ON DELETE CASCADE,
                UNIQUE(vacante_id, canal, contacto_destino)
            );
            """
        )

        # Índices para acelerar búsquedas de estado y conteo diario
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_postulaciones_estado_canal
            ON postulaciones(canal, estado);
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_postulaciones_contacto
            ON postulaciones(contacto_destino, estado);
            """
        )
        conn.commit()


def guardar_vacante(
    titulo: str,
    empresa: str,
    ubicacion: str,
    url_original: str,
    descripcion_cruda: str,
    portal: str = "Computrabajo",
    db_path: Path = DB_PATH,
) -> tuple[str, bool]:
    """
    Inserta una vacante si no existe previamente en la base de datos.
    Retorna (vacante_id, es_nueva).
    """
    vacante_id = generar_hash_vacante(titulo=titulo, empresa=empresa, portal=portal)
    ahora = datetime.now().isoformat(timespec="seconds")

    with obtener_conexion(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM vacantes WHERE id = ?;", (vacante_id,))
        if cursor.fetchone() is not None:
            return vacante_id, False

        cursor.execute(
            """
            INSERT INTO vacantes (
                id, portal, titulo, empresa, ubicacion, url_original, descripcion_cruda, fecha_deteccion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                vacante_id,
                portal.strip(),
                titulo.strip(),
                empresa.strip(),
                ubicacion.strip(),
                url_original.strip(),
                descripcion_cruda.strip(),
                ahora,
            ),
        )
        conn.commit()
        return vacante_id, True


def registrar_postulacion_pendiente(
    vacante_id: str,
    canal: str,
    contacto_destino: str,
    db_path: Path = DB_PATH,
) -> bool:
    """
    Registra una postulación en estado PENDIENTE para un canal ('EMAIL' o 'WHATSAPP').
    Evita duplicados para la misma vacante/contacto o si ya se envió previamente
    al mismo contacto para un puesto con igual título.
    Retorna True si se agendó como nueva postulación pendiente, False si ya existía.
    """
    canal_upper = canal.strip().upper()
    contacto_limpio = contacto_destino.strip()

    with obtener_conexion(db_path) as conn:
        cursor = conn.cursor()

        # Verificar si ya se envió o está pendiente para este mismo contacto y vacante
        cursor.execute(
            """
            SELECT id FROM postulaciones
            WHERE vacante_id = ? AND canal = ? AND contacto_destino = ?;
            """,
            (vacante_id, canal_upper, contacto_limpio),
        )
        if cursor.fetchone() is not None:
            return False

        # Prevención adicional: verificar si ya enviamos con éxito a este mismo contacto
        # en otra publicación idéntica o repetida de la misma empresa
        cursor.execute(
            """
            SELECT p.id
            FROM postulaciones p
            JOIN vacantes v_existente ON p.vacante_id = v_existente.id
            JOIN vacantes v_nueva ON v_nueva.id = ?
            WHERE p.canal = ?
              AND p.contacto_destino = ?
              AND p.estado = 'ENVIADO'
              AND lower(v_existente.titulo) = lower(v_nueva.titulo);
            """,
            (vacante_id, canal_upper, contacto_limpio),
        )
        if cursor.fetchone() is not None:
            return False

        cursor.execute(
            """
            INSERT INTO postulaciones (
                vacante_id, canal, contacto_destino, estado, timestamp_envio, mensaje_log
            ) VALUES (?, ?, ?, 'PENDIENTE', NULL, 'Registrada para envío');
            """,
            (vacante_id, canal_upper, contacto_limpio),
        )
        conn.commit()
        return True


def obtener_postulaciones_pendientes(
    canal: str, limite: int = 50, db_path: Path = DB_PATH
) -> list[dict[str, Any]]:
    """
    Devuelve la lista de postulaciones en estado PENDIENTE para el canal especificado,
    uniendo los datos de la vacante (título, empresa, ubicación, url_original).
    """
    canal_upper = canal.strip().upper()
    with obtener_conexion(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                p.id AS postulacion_id,
                p.vacante_id,
                p.canal,
                p.contacto_destino,
                p.estado,
                v.portal,
                v.titulo,
                v.empresa,
                v.ubicacion,
                v.url_original
            FROM postulaciones p
            JOIN vacantes v ON p.vacante_id = v.id
            WHERE p.canal = ? AND p.estado = 'PENDIENTE'
            ORDER BY v.fecha_deteccion ASC, p.id ASC
            LIMIT ?;
            """,
            (canal_upper, limite),
        )
        return [dict(fila) for fila in cursor.fetchall()]


def actualizar_estado_postulacion(
    postulacion_id: int,
    estado: str,
    mensaje_log: str = "",
    db_path: Path = DB_PATH,
) -> None:
    """
    Actualiza el estado de una postulación ('ENVIADO', 'ERROR' o 'PENDIENTE'),
    registrando el timestamp de envío y el mensaje de log/error.
    """
    estado_upper = estado.strip().upper()
    ahora = datetime.now().isoformat(timespec="seconds")

    with obtener_conexion(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE postulaciones
            SET estado = ?,
                timestamp_envio = ?,
                mensaje_log = ?
            WHERE id = ?;
            """,
            (estado_upper, ahora, mensaje_log.strip(), postulacion_id),
        )
        conn.commit()


def contar_envios_hoy(canal: str, db_path: Path = DB_PATH) -> int:
    """
    Cuenta cuántas postulaciones han sido marcadas como 'ENVIADO' en la fecha actual
    para el canal indicado ('EMAIL' o 'WHATSAPP'). Usado para Rate Limiting diario.
    """
    canal_upper = canal.strip().upper()
    prefijo_hoy = date.today().isoformat()  # Formato YYYY-MM-DD

    with obtener_conexion(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM postulaciones
            WHERE canal = ?
              AND estado = 'ENVIADO'
              AND timestamp_envio LIKE ?;
            """,
            (canal_upper, f"{prefijo_hoy}%"),
        )
        fila = cursor.fetchone()
        return int(fila["total"]) if fila else 0
