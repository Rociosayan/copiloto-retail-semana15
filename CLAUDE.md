# Copiloto Comercial Retail — Reglas del proyecto

Este archivo describe el producto y las reglas de trabajo. Léelo completo antes de cada tarea y respétalo siempre.
Si una instrucción del usuario contradice estas reglas, pregunta antes de actuar.

## 1. Qué es el producto

Aplicación web de analítica empresarial para una tienda mayorista en línea. Integra en un solo producto
lo trabajado en el curso Analítica Empresarial Integrada (TECSUP 2026-II), semanas 9 a 15:

| Pestaña | Ruta | Pregunta de negocio | Semana |
|---|---|---|---|
| Inicio | `/` | ¿Cómo va el negocio? Indicadores y resumen ejecutivo | 15 |
| Clientes | `/clientes` | ¿Qué clientes están en riesgo de irse y cuánto vale retenerlos? | 9 |
| Demanda | `/demanda` | ¿Cuánto venderemos de cada producto clave? | 10 |
| Reposición | `/reposicion` | ¿Cuánto comprar de cada producto con el presupuesto disponible? | 11 |
| Pregúntale a tus datos | `/pregunta` | Consultas de negocio convertidas en SQL seguro | 14 |
| Gobierno | `/gobierno` | Ficha de datos, linaje, calidad y supuestos | 13 |

Usuario objetivo: un gerente comercial, no un programador. Todo texto visible debe ser claro y en español.

## 2. Datos

- Fuente única: **Online Retail II**, UCI Machine Learning Repository, ID 502
  (https://archive.ics.uci.edu/dataset/502/online+retail+ii). Ventas reales de diciembre de 2009 a diciembre de 2011.
- Columnas originales: `Invoice`, `StockCode`, `Description`, `Quantity`, `InvoiceDate`, `Price`, `Customer ID`, `Country`.
- Los importes están en libras esterlinas (£). No se convierten a otra moneda.
- **Nunca** generes datos ficticios ni sustituyas la fuente. Si la descarga falla, detente y avísame.
- Supuestos académicos (no son datos observados; deben mostrarse como supuestos en la app):
  margen bruto 30 % del precio, costo unitario 70 % del precio, costo de contactar a un cliente £2.

## 3. Arquitectura (no cambiarla sin preguntar)

Proyecto único desplegado en **Vercel**, siguiendo el patrón oficial *Next.js + FastAPI*:

```
copiloto-retail/
├── CLAUDE.md                      # este archivo
├── .github/copilot-instructions.md  # copia idéntica de este archivo
├── app/                           # Next.js (App Router) + TypeScript + Tailwind CSS
├── components/                    # componentes reutilizables de la interfaz
├── public/data/                   # resultados precalculados en JSON que lee la interfaz
├── api/index.py                   # FastAPI: funciones de Python en Vercel, rutas bajo /api/py/
├── api/tests/                     # pruebas con pytest
├── data/                          # archivos Parquet pequeños que usa la API
├── pipeline/                      # scripts de Python que se ejecutan en local (no en Vercel)
├── requirements.txt               # dependencias de la API (solo las que usa api/)
├── pipeline/requirements.txt      # dependencias del pipeline (pandas, scikit-learn, statsmodels…)
├── next.config.js                 # reescritura /api/py/* → FastAPI (local: 127.0.0.1:8000)
├── vercel.json                    # incluye data/** en la función de Python
└── .env.example                   # variables de entorno sin valores reales
```

Principios de velocidad (la página debe cargar al instante):
1. Lo pesado (limpieza, modelos, pronósticos) se calcula **una vez** en `pipeline/` y se exporta a `public/data/*.json` y `data/*.parquet`.
2. La interfaz lee los JSON precalculados. Los cálculos simples (por ejemplo, un deslizador de umbral) se hacen en el navegador.
3. La API de Python solo atiende lo que debe calcularse en vivo: optimización con PuLP y consultas SQL con DuckDB.
4. `requirements.txt` de la raíz lleva **solo** lo que usa `api/`: `fastapi`, `duckdb`, `pulp`, `httpx`. Nada de scikit-learn ni statsmodels ahí.

## 4. Reglas de código

- Idioma: interfaz, comentarios, nombres de variables de negocio y mensajes de error en **español**.
- Cada archivo empieza con un comentario de 2–3 líneas que explique qué hace.
- Funciones cortas, con comentarios que expliquen la decisión de negocio, no solo el código.
- Gráficos con **Recharts**. Cada gráfico lleva título, ejes rotulados y una frase de interpretación debajo.
- Cifras con separador de miles y máximo dos decimales; porcentajes con el símbolo %.
- Diseño sobrio y profesional: fondo claro, un color principal azul oscuro (#1E3A5F), tarjetas de indicadores, navegación lateral con las seis pestañas.
- Diseño adaptable a celular.
- Ninguna dependencia nueva sin explicar para qué sirve.

## 5. Seguridad y gobierno

- **Ninguna clave** en el código ni en el repositorio. Las claves van en variables de entorno (`.env.local` en local, configuración del proyecto en Vercel). `.env.local` está en `.gitignore`.
- El asistente de consultas solo ejecuta `SELECT` (o `WITH … SELECT`), una sola sentencia, con `LIMIT` máximo de 200 filas, sobre una conexión DuckDB de solo lectura. La protección está en el validador, no en el prompt.
- El modo con IA es **opcional**: si no hay clave configurada, la app funciona completa con preguntas predefinidas y lo indica con un mensaje amable.
- Variables de entorno del modo IA: `LLM_PROVEEDOR` (`ninguno`, `gemini`, `anthropic` u `openai`), `LLM_MODELO`, `LLM_API_KEY`.
- Toda cifra mostrada debe poder rastrearse a un archivo de `public/data/` o a una consulta visible.

## 6. Forma de trabajo

1. Antes de escribir código, presenta un **plan breve** (archivos que crearás o modificarás y por qué) y espera mi confirmación.
2. Trabaja solo en la etapa pedida. No adelantes etapas ni agregues funciones no solicitadas.
3. Al terminar, ejecuta lo necesario para comprobar que funciona (script, `npm run build`, `pytest`) y muéstrame el resultado.
4. Termina con un resumen de 3–5 líneas: qué hiciste, qué archivos cambiaron y cómo lo verifico yo.
5. Si algo falla, explica la causa en lenguaje simple antes de corregirlo.
