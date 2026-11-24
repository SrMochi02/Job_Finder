"""
Módulo de Base de Datos Relacional en SQLite (Fase 1).
Gestiona las tablas 'vacantes' y 'postulaciones', almacenando toda la información
de la empresa reclutadora, el área de afinidad con el CV y el seguimiento de entrevistas
(si la empresa llamó a entrevista o no).
"""

import csv
import hashlib
import re
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

from config import BASE_DIR, DB_PATH, UBICACION_OBJETIVO
from parser import es_oferta_excluida

COLUMNAS_ADICIONALES_VACANTES: dict[str, str] = {
    "area_afinidad": "TEXT DEFAULT 'general'",
    "salario_ofrecido": "TEXT DEFAULT 'No especificado'",
    "correos_empresa": "TEXT DEFAULT ''",
    "telefonos_empresa": "TEXT DEFAULT ''",
    "resumen_oferta": "TEXT DEFAULT ''",
    "consejo_preparacion": "TEXT DEFAULT ''",
    "postulado_en_portal": "TEXT DEFAULT 'NO'",
    "llamaron_entrevista": "TEXT DEFAULT 'NO'",
    "notas_entrevista": "TEXT DEFAULT ''",
}


def obtener_conexion(db_path: Path = DB_PATH) -> sqlite3.Connection:
    """
    Crea y retorna una conexión SQLite optimizada para discos duros mecánicos (HDD)
    y equipos de bajos recursos (2GB RAM / Intel Celeron):
    - journal_mode = WAL (reduce bloqueos y escrituras físicas en HDD).
    - synchronous = NORMAL (ahorra ciclos de espera de cabezal en HDD sin perder integridad).
    - temp_store = MEMORY y cache_size moderado (-4000 = ~4MB RAM).
    """
    conn = sqlite3.connect(str(db_path), timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA temp_store = MEMORY;")
    conn.execute("PRAGMA cache_size = -4000;")
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


def existe_vacante(
    titulo: str,
    empresa: str,
    portal: str = "Computrabajo",
    db_path: Path = DB_PATH,
) -> bool:
    """
    Consulta en 1 milisegundo si la vacante ya fue procesada (y postulada en el portal
    o descartada previamente) para no volver a abrirla.
    Si la vacante estaba guardada con postulado_en_portal IN ('NO', 'REQUIERE_LOGIN'),
    retorna False para que el scraper entre a postularla ahora que ya hay sesión activa.
    """
    if not db_path.exists():
        return False
    vacante_id = generar_hash_vacante(titulo=titulo, empresa=empresa, portal=portal)
    with obtener_conexion(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT postulado_en_portal FROM vacantes WHERE id = ? LIMIT 1;",
            (vacante_id,),
        )
        fila = cursor.fetchone()
        if fila is None:
            cursor.execute(
                "SELECT 1 FROM ofertas_descartadas WHERE id = ? LIMIT 1;",
                (vacante_id,),
            )
            return cursor.fetchone() is not None

        estado_portal = (fila["postulado_en_portal"] or "NO").strip().upper()
        # Si ya se postuló en el portal ('SI...'), ya no hace falta volver a abrirla
        return estado_portal.startswith("SI")


def registrar_oferta_descartada(
    titulo: str,
    empresa: str,
    portal: str,
    motivo: str,
    db_path: Path = DB_PATH,
) -> None:
    """
    Guarda el hash de una oferta que fue descartada tras leer su descripción
    (ej. porque adentro pedía licencia de conducir o moto propia) para no volver
    a abrirla nunca más en ciclos futuros.
    """
    vacante_id = generar_hash_vacante(titulo=titulo, empresa=empresa, portal=portal)
    ahora = datetime.now().isoformat(timespec="seconds")
    with obtener_conexion(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO ofertas_descartadas (id, portal, titulo, empresa, motivo, fecha)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (vacante_id, portal.strip(), titulo.strip(), empresa.strip(), motivo.strip(), ahora),
        )
        conn.commit()


def inicializar_bd(db_path: Path = DB_PATH) -> None:
    """Crea las tablas 'vacantes' y 'postulaciones' y asegura todas las columnas de empresa/entrevista."""
    with obtener_conexion(db_path) as conn:
        cursor = conn.cursor()

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
                fecha_deteccion TEXT NOT NULL,
                area_afinidad TEXT DEFAULT 'general',
                salario_ofrecido TEXT DEFAULT 'No especificado',
                correos_empresa TEXT DEFAULT '',
                telefonos_empresa TEXT DEFAULT '',
                resumen_oferta TEXT DEFAULT '',
                consejo_preparacion TEXT DEFAULT '',
                postulado_en_portal TEXT DEFAULT 'NO',
                llamaron_entrevista TEXT DEFAULT 'NO',
                notas_entrevista TEXT DEFAULT ''
            );
            """
        )

        # Migración automática segura si la tabla ya existía de una versión previa
        cursor.execute("PRAGMA table_info(vacantes);")
        columnas_existentes = {fila["name"] for fila in cursor.fetchall()}
        for col_nombre, col_tipo in COLUMNAS_ADICIONALES_VACANTES.items():
            if col_nombre not in columnas_existentes:
                cursor.execute(
                    f"ALTER TABLE vacantes ADD COLUMN {col_nombre} {col_tipo};"
                )

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

        # Tabla de memoria para ofertas descartadas al leer su descripción (ej. exigen licencia/moto)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS ofertas_descartadas (
                id TEXT PRIMARY KEY,
                portal TEXT NOT NULL,
                titulo TEXT NOT NULL,
                empresa TEXT NOT NULL,
                motivo TEXT NOT NULL,
                fecha TEXT NOT NULL
            );
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
    area_afinidad: str = "general",
    salario_ofrecido: str = "No especificado",
    correos_empresa: str = "",
    telefonos_empresa: str = "",
    resumen_oferta: str = "",
    consejo_preparacion: str = "",
    postulado_en_portal: str = "NO",
    db_path: Path = DB_PATH,
) -> tuple[str, bool]:
    """
    Inserta una vacante junto con toda la información extraída de la empresa.
    Retorna (vacante_id, es_nueva).
    """
    vacante_id = generar_hash_vacante(titulo=titulo, empresa=empresa, portal=portal)
    ahora = datetime.now().isoformat(timespec="seconds")

    with obtener_conexion(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, postulado_en_portal FROM vacantes WHERE id = ?;",
            (vacante_id,),
        )
        existente = cursor.fetchone()
        if existente is not None:
            # Si la vacante ya existía pero ahora sí se logró postular en el portal, actualizar su estado
            if postulado_en_portal.strip().upper().startswith("SI") or (
                existente["postulado_en_portal"] in ("NO", "REQUIERE_LOGIN")
                and postulado_en_portal != "NO"
            ):
                cursor.execute(
                    """
                    UPDATE vacantes
                    SET postulado_en_portal = ?,
                        correos_empresa = CASE WHEN ? != '' THEN ? ELSE correos_empresa END,
                        telefonos_empresa = CASE WHEN ? != '' THEN ? ELSE telefonos_empresa END
                    WHERE id = ?;
                    """,
                    (
                        postulado_en_portal.strip(),
                        correos_empresa.strip(),
                        correos_empresa.strip(),
                        telefonos_empresa.strip(),
                        telefonos_empresa.strip(),
                        vacante_id,
                    ),
                )
                conn.commit()
            return vacante_id, False

        cursor.execute(
            """
            INSERT INTO vacantes (
                id, portal, titulo, empresa, ubicacion, url_original, descripcion_cruda,
                fecha_deteccion, area_afinidad, salario_ofrecido, correos_empresa,
                telefonos_empresa, resumen_oferta, consejo_preparacion, postulado_en_portal,
                llamaron_entrevista, notas_entrevista
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'NO', '');
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
                area_afinidad.strip(),
                salario_ofrecido.strip(),
                correos_empresa.strip(),
                telefonos_empresa.strip(),
                resumen_oferta.strip(),
                consejo_preparacion.strip(),
                postulado_en_portal.strip(),
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
    """
    canal_upper = canal.strip().upper()
    contacto_limpio = contacto_destino.strip()

    with obtener_conexion(db_path) as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id FROM postulaciones
            WHERE vacante_id = ? AND canal = ? AND contacto_destino = ?;
            """,
            (vacante_id, canal_upper, contacto_limpio),
        )
        if cursor.fetchone() is not None:
            return False

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
    uniendo los datos de la vacante (título, empresa, ubicación, area_afinidad, url_original).
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
                v.area_afinidad,
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
    para el canal indicado ('EMAIL' o 'WHATSAPP').
    """
    canal_upper = canal.strip().upper()
    prefijo_hoy = date.today().isoformat()

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


def registrar_respuesta_entrevista(
    criterio: str,
    llamaron: bool = True,
    notas: str = "",
    db_path: Path = DB_PATH,
) -> int:
    """
    Permite marcar si una empresa llamó para entrevista ('SI' o 'NO') buscando por
    prefijo del ID de vacante o por nombre de la empresa. Retorna cuántas filas actualizó.
    """
    valor_llamaron = "SI" if llamaron else "NO"
    criterio_limpio = criterio.strip()

    with obtener_conexion(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE vacantes
            SET llamaron_entrevista = ?,
                notas_entrevista = ?
            WHERE id LIKE ? OR lower(empresa) LIKE ? OR lower(titulo) LIKE ?;
            """,
            (
                valor_llamaron,
                notas.strip(),
                f"{criterio_limpio}%",
                f"%{criterio_limpio.lower()}%",
                f"%{criterio_limpio.lower()}%",
            ),
        )
        conn.commit()
        return cursor.rowcount


def obtener_directorio_empresas(db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    """
    Obtiene toda la información consolidada de cada empresa, vacante, canales de contacto,
    estado de envío del CV y si llamaron o no a entrevista.
    """
    with obtener_conexion(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                substr(v.id, 1, 8) AS codigo_corto,
                v.id AS vacante_id,
                v.fecha_deteccion,
                v.portal,
                v.empresa,
                v.titulo,
                v.ubicacion,
                v.area_afinidad,
                v.salario_ofrecido,
                v.correos_empresa,
                v.telefonos_empresa,
                v.postulado_en_portal,
                v.consejo_preparacion,
                v.llamaron_entrevista,
                v.notas_entrevista,
                v.url_original,
                v.resumen_oferta,
                GROUP_CONCAT(p.canal || ':' || p.contacto_destino || '(' || p.estado || ')', ' | ') AS estado_postulaciones
            FROM vacantes v
            LEFT JOIN postulaciones p ON v.id = p.vacante_id
            GROUP BY v.id
            ORDER BY v.fecha_deteccion DESC;
            """
        )
        return [dict(fila) for fila in cursor.fetchall()]


def exportar_reporte_empresas_csv(
    ruta_csv: Path = BASE_DIR / "reporte_empresas.csv",
    db_path: Path = DB_PATH,
) -> Path:
    """
    Exporta un archivo CSV (abrible en Excel) con toda la información de las empresas,
    teléfonos, correos, puesto, estado de envío y columna 'llamaron_entrevista' (SI/NO).
    """
    registros = obtener_directorio_empresas(db_path=db_path)
    columnas = [
        "codigo_corto",
        "fecha_deteccion",
        "empresa",
        "titulo",
        "ubicacion",
        "area_afinidad",
        "salario_ofrecido",
        "correos_empresa",
        "telefonos_empresa",
        "postulado_en_portal",
        "estado_postulaciones",
        "llamaron_entrevista",
        "notas_entrevista",
        "consejo_preparacion",
        "portal",
        "url_original",
        "resumen_oferta",
    ]
    with open(ruta_csv, mode="w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
        writer.writeheader()
        for fila in registros:
            writer.writerow(fila)

    return ruta_csv


def depurar_vacantes_existentes(db_path: Path = DB_PATH) -> int:
    """
    Limpia la base de datos existente eliminando ofertas que ahora estén en la lista de
    exclusión (ej. Doctor, Profesora, Perito, Mecánico) y corrigiendo saltos de línea
    en nombres de empresa y salarios para que el CSV en Excel se vea impecable.
    """
    eliminadas = 0
    with obtener_conexion(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, titulo, empresa, ubicacion, salario_ofrecido, descripcion_cruda FROM vacantes;"
        )
        filas = cursor.fetchall()

        for fila in filas:
            vid = fila["id"]
            titulo = fila["titulo"] or ""
            empresa = fila["empresa"] or ""
            ubicacion = fila["ubicacion"] or ""
            salario = fila["salario_ofrecido"] or ""
            desc = fila["descripcion_cruda"] or ""

            excluida, _ = es_oferta_excluida(titulo, empresa, desc)
            if excluida:
                cursor.execute("DELETE FROM vacantes WHERE id = ?;", (vid,))
                eliminadas += 1
                continue

            empresa_limpia = (
                re.sub(r"^\d+(?:[.,]\d+)?\s*", "", empresa).replace("\n", " ").strip()
                or "Empresa Confidencial"
            )
            ubicacion_limpia = (
                UBICACION_OBJETIVO
                if re.fullmatch(r"\d+(?:[.,]\d+)?", ubicacion.strip())
                else ubicacion.replace("\n", " ").strip()
            )
            salario_limpio = (
                re.sub(r"\s+", "", salario.strip())
                if salario and salario != "No especificado"
                else "No especificado"
            )

            if (
                empresa_limpia != empresa
                or ubicacion_limpia != ubicacion
                or salario_limpio != salario
            ):
                cursor.execute(
                    """
                    UPDATE vacantes
                    SET empresa = ?, ubicacion = ?, salario_ofrecido = ?
                    WHERE id = ?;
                    """,
                    (empresa_limpia, ubicacion_limpia, salario_limpio, vid),
                )

        conn.commit()
    return eliminadas

