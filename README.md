# Job Finder - Automatización de Búsqueda de Empleo (San Miguel, El Salvador)

Sistema automatizado de extracción de vacantes (ETL), detección de contactos (correo y teléfono salvadoreño) y postulación automática controlada por SMTP (Gmail) y WhatsApp Web.

## Estructura del Proyecto

- `config.py`: Carga de configuración y variables de entorno desde `.env`.
- `database.py`: Modelo relacional en SQLite (`vacantes` y `postulaciones`) con prevención de duplicados mediante hash SHA-256.
- `parser.py`: Extracción y normalización con expresiones regulares (correos electrónicos y números telefónicos de El Salvador `503XXXXXXXX`).
- `scraper.py`: Extracción de ofertas de empleo en portales locales usando Playwright.
- `mailer.py`: Envío automatizado de correo vía SMTP con plantilla dinámica, adjunto de CV en PDF y control de flujo diario.
- `whatsapp.py`: Envío semiautomatizado por WhatsApp Web con sesión persistente y adjunto de documento PDF.
- `main.py`: Orquestador lineal del flujo completo.
