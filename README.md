# Copiloto Comercial Retail

Producto de datos para el Laboratorio 15 de Analítica Empresarial Integrada. Usa las ventas reales de [Online Retail II, UCI 502](https://archive.ics.uci.edu/dataset/502/online+retail+ii), de diciembre de 2009 a diciembre de 2011. Los importes están en libras esterlinas. La aplicación tiene seis vistas: Inicio, Clientes, Demanda, Reposición, Pregúntale a tus datos y Gobierno.

## Ejecutar localmente

Requiere Node.js 20+ y Python 3.11+. En Windows:

```powershell
npm install
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
npm run dev
```

Abre http://localhost:3000. El comando inicia Next.js y FastAPI. Para validar: `npm run build` y `.\.venv\Scripts\python.exe -m pytest api/tests`.

## Regenerar los datos

Instala también `pipeline/requirements.txt` en el entorno de Python. Ejecuta, en orden:

```powershell
.\.venv\Scripts\python.exe pipeline/01_datos.py
.\.venv\Scripts\python.exe pipeline/02_clientes.py
.\.venv\Scripts\python.exe pipeline/03_demanda.py
.\.venv\Scripts\python.exe pipeline/04_tablero.py
```

El primer paso descarga la fuente UCI o usa el Excel oficial incluido como respaldo. Las agregaciones de `explorador.json` proceden de `data/ventas.parquet`. Los modelos de clientes y demanda se calculan una vez en el pipeline. El pronóstico es global por producto; no representa un pronóstico por país. Los supuestos académicos son margen de 30 %, costo de compra de 70 %, costo de contacto £2 y éxito de campaña de 20 %.


## Consultas con IA opcional

El tablero y las diez preguntas predefinidas funcionan sin clave. Para preguntas libres, configura `LLM_PROVEEDOR` (`openai`, `anthropic` o `gemini`), `LLM_MODELO` y `LLM_API_KEY` en `.env.local` o en las variables de Vercel. Nunca subas el archivo de claves. El SQL generado pasa por el validador de la API.

## Despliegue

Importa este directorio como proyecto Next.js en Vercel. `vercel.json` incluye `data/**` en la función Python. Verifica tras publicar `/api/py/salud`, una consulta predefinida y el plan de reposición. Si usas Git, crea un repositorio personal y sube el proyecto sin `.env.local`, `.venv`, `node_modules` ni `.next`.

Asistente utilizado: Codex de OpenAI en la interfaz, agregaciones, API, verificación y preparación de despliegue. Los datos y los modelos se generan con los scripts Python indicados arriba.
