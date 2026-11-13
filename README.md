# Job Finder - Automatización de Búsqueda de Empleo (San Miguel, El Salvador)

Sistema automatizado de extracción de vacantes (ETL), detección de contactos con expresiones regulares (correo y teléfono salvadoreño `503XXXXXXXX`) y postulación automática controlada por SMTP (Gmail) y WhatsApp Web.

---

## Arquitectura del Proyecto

1. **Fase 1 — Diseño de Datos y Entorno (`config.py`, `database.py`)**:
   - Entorno aislado con `venv` y variables sensibles en `.env` (excluidas en `.gitignore`).
   - Base de datos SQLite relacional con las tablas `vacantes` (ID único SHA-256 generado a partir de `titulo + empresa + portal`) y `postulaciones` (llave foránea a `vacantes`, canal `EMAIL` o `WHATSAPP`, estado `PENDIENTE`, `ENVIADO` o `ERROR`).
2. **Fase 2 — Extracción y Limpieza ETL (`scraper.py`, `parser.py`)**:
   - Navegación con Playwright sobre las primeras páginas de portales de empleo filtrando por **San Miguel**.
   - Extracción por Regex de correos válidos y números salvadoreños (`7XXX-XXXX`, `6XXX-XXXX`, `2XXX-XXXX`) normalizados a `503XXXXXXXX`.
3. **Fase 3 — Automatización de Correo SMTP (`mailer.py`)**:
   - Envío seguro por `smtplib` (`SMTP_SSL` puerto 465 / `STARTTLS` puerto 587) con plantilla personalizada según el puesto y empresa, adjuntando el CV en PDF (`rb`).
   - Rate Limiting diario (máximo 10-15 correos/día) y pausas aleatorias humanas `time.sleep(random.uniform(30, 90))`.
4. **Fase 4 — Automatización de WhatsApp con Cautela (`whatsapp.py`)**:
   - Sesión persistente con `launch_persistent_context` (solo escaneas el código QR la primera vez).
   - Espera explícita con `wait_for_selector`, adjunto directo de PDF mediante `input[type="file"]` sin abrir ventanas del sistema operativo y límite estricto de supervivencia (5-8 mensajes/día).
5. **Fase 5 — Orquestación y Automatización en el SO (`main.py`)**:
   - Flujo lineal completo: `Scrapear -> Parsear -> Guardar nuevas en BD -> Consultar pendientes -> Enviar correos -> Enviar WhatsApp -> Actualizar estados`.

---

## Instalación y Configuración

```bash
# 1. Activar el entorno virtual
# En Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# En Linux / Fedora / VPS:
source venv/bin/activate

# 2. Instalar dependencias y navegador de Playwright
pip install -r requirements.txt
playwright install chromium
```

Edita tu archivo `.env` (basado en `.env.example`) con tu correo de Gmail, tu Contraseña de Aplicación de 16 caracteres de Google y la ruta a tu CV en PDF (`cv_postulante.pdf`).

---

## Modos de Ejecución (`main.py`)

```bash
# Dejar activo en el curso de 7:00 AM a 4:00 PM buscando ofertas afines al CV y enviando postulaciones
python main.py --jornada

# Ver todas las empresas extraídas, sus teléfonos/correos y exportar reporte_empresas.csv para Excel
python main.py --empresas

# Marcar que una empresa sí te llamó para entrevista
python main.py --marcar-entrevista "Nombre de la Empresa" --notas "Entrevista martes 9:00 AM"

# Probar flujo de base de datos, filtro anti-cocina y afinidad de CV sin enviar mensajes reales
python main.py --demo

# Ejecutar únicamente recolección y guardado en BD (ETL)
python main.py --solo-etl

# Procesar únicamente la cola pendiente de correos electrónicos
python main.py --solo-email

# Procesar únicamente la cola pendiente de WhatsApp Web
python main.py --solo-whatsapp
```

---

## Programación Diaria en el Sistema Operativo (8:30 AM)

### En Linux (Fedora / VPS) con `crontab`

Ejecuta `crontab -e` y agrega la siguiente línea para correr el orquestador de lunes a sábado a las 8:30 AM:

```cron
30 8 * * 1-6 cd /ruta/a/Job_Finder && /ruta/a/Job_Finder/venv/bin/python main.py >> /ruta/a/Job_Finder/cron.log 2>&1
```

### En Windows con Programador de Tareas (`schtasks`)

```powershell
schtasks /Create /SC DAILY /TN "JobFinderSanMiguel" /TR "C:\Users\optim\OneDrive\Documentos\JOBSEARCHING\venv\Scripts\python.exe C:\Users\optim\OneDrive\Documentos\JOBSEARCHING\main.py" /ST 08:30
```
