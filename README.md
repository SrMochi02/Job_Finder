# 🚀 Job Finder PC — Asistente Automático para Buscar Empleo (Windows 10 y Windows 11)

**Job Finder PC** es una aplicación de escritorio gratuita y **100% privada** para Windows 10 y Windows 11 que busca ofertas de empleo compatibles con tu perfil en El Salvador, descarta automáticamente puestos que no van contigo, **se postula en 1 clic dentro de Computrabajo**, responde las preguntas de selección de las empresas por ti y envía tu CV en PDF.

> 🔒 **Privacidad Total:** Ningún dato sale a servidores externos. Tu nombre, tu correo, tu CV en PDF y tu sesión de Computrabajo se guardan **exclusivamente dentro de tu propia computadora**.
>
> 📘 **[Lee aquí el Manual Oficial de Usuario Completo (`MANUAL_USUARIO.md`)](MANUAL_USUARIO.md)** con la explicación minuciosa de cada pantalla, botón, filtro, campo y solución de problemas.

---

## 📥 Cómo Descargar e Instalar en Windows 10 o Windows 11 (Sin saber programar)

1. Ve a la sección **[Releases](https://github.com/SrMochi02/Job_Finder/releases)** (a la derecha de esta página de GitHub).
2. Descarga el archivo **`JobFinderPC_Windows10_11.zip`**.
3. Haz clic derecho sobre el archivo descargado y selecciona **"Extraer todo..."** (Descomprimir).
4. Entra a la carpeta extraída y haz doble clic en:
   - **`Instalar_Acceso_Directo.bat`** *(Te creará el ícono **Job Finder PC** en tu Escritorio y abrirá el programa)*, o abre directamente **`JobFinderPC.exe`**.

---

## 🧭 Guía Rápida en 3 Pasos (Dentro de la Aplicación)

### 👤 Paso 1: Mis Datos y CV
- Haz clic en **`📂 Elegir mi CV en PDF...`** y selecciona el archivo PDF de tu currículum.
- Escribe tu nombre, teléfono, dirección, cuánto deseas ganar, estado civil y un resumen corto de tu experiencia.
- *¿Para qué sirve?* Cuando una empresa en Computrabajo pregunte *"¿Cuál es su pretensión salarial?"* o *"Coloque su dirección"*, el programa contestará por ti en segundos.

### 🎯 Paso 2: Qué Trabajo Busco
- Elige tu **Departamento o Ciudad** (*San Miguel, San Salvador, Santa Ana, La Libertad, Soyapango, Santa Tecla, Sonsonate, Usulután, La Unión*, etc.).
- Marca con un check (`✔`) únicamente los tipos de trabajo a los que sí te quieres postular (*Oficina/Caja/Atención*, *Bodega/Inventario*, *Ventas/Restaurantes*, *Soporte Técnico* o *Programación*).
- En la caja inferior puedes escribir palabras de empleos que **NO** quieres (por ejemplo: `motorista, cocinero, gerente`).

### 🔑 Paso 3: Conectar Cuentas
- Haz clic en **`🔑 Abrir Computrabajo e Iniciar Sesión`**.
- Se abrirá una ventana del navegador: inicia sesión en tu cuenta de Computrabajo y luego **cierra esa ventana**. ¡Tu sesión quedará guardada!
- *(Opcional)* Si quieres que el programa también envíe tu CV por correo cuando un anuncio incluya el email de Recursos Humanos, puedes agregar tu correo Gmail.

### ⚡ ¡Listo! Dale a Buscar
- Ve a la pestaña **`▶ Inicio`** y presiona **`⚡ Buscar Trabajo y Postularme Ahora`** (o activa el **`🔄 Modo Automático Continuo`** para que revise ofertas nuevas cada 45 minutos).
- En la pestaña **`📋 Mis Postulaciones`** podrás ver todas las empresas donde ya te postulaste, abrir el reporte en **Excel** y marcar cuáles te llamaron a entrevista.

---

## 🛠️ Ejecución desde Código Fuente (Para Desarrolladores)

Si prefieres ejecutarlo o modificarlo desde Python:

```bat
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python interfaz_pc.py
```

Para volver a generar el ejecutable `.exe` y el paquete `.zip` para Windows 10/11:
```bat
scripts\crear_ejecutable_windows.bat
```
