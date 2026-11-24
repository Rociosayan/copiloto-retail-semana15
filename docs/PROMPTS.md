# Copiloto Comercial Retail — Guía de construcción con IA

**Analítica Empresarial Integrada · TECSUP 2026-II · Docente: PILAR ROCIO SAYAN MEJIA**

Producto de datos desplegado en Vercel que integra las semanas 9 a 15 del curso.
Se construye en **Visual Studio Code** con el asistente de IA que cada estudiante tenga disponible:
Claude Code, GitHub Copilot (gratuito para estudiantes) u otro. Los prompts sirven para cualquiera de ellos.

---

## 0. Preparación (una sola vez)

1. Instale **Visual Studio Code**, **Python 3.11 o superior**, **Node.js 20 o superior** y **Git**.
2. Instale en VS Code la extensión de su asistente (Claude Code o GitHub Copilot) e inicie sesión.
3. Cree cuentas gratuitas en **GitHub** y en **Vercel** (en Vercel, ingrese con su cuenta de GitHub).
4. Cree una carpeta vacía llamada `copiloto-retail` y ábrala en VS Code.
5. Copie dentro de la carpeta:
   - `CLAUDE.md` en la raíz.
   - El mismo contenido en `.github/copilot-instructions.md` (Copilot lee este archivo; Claude lee `CLAUDE.md`).
   - Esta guía en `docs/PROMPTS.md`.
6. Si usa Copilot, abra el chat en **modo Agente** para que pueda crear archivos y ejecutar comandos.

**Cómo usar cada prompt:** cópielo completo en el chat del asistente. El asistente propondrá un plan;
revíselo y responda «adelante». Al final, haga usted mismo la **verificación** que aparece debajo de cada prompt.
No pase a la siguiente etapa hasta que la verificación sea correcta.

---

## Etapa 1 — Estructura del proyecto

```text
Lee CLAUDE.md (o .github/copilot-instructions.md) completo.

Crea la estructura base del proyecto siguiendo la sección 3 de las reglas:
1. Un proyecto Next.js con App Router, TypeScript y Tailwind CSS en esta misma carpeta.
2. Una API FastAPI en api/index.py con la ruta GET /api/py/salud que responda {"estado": "ok"}.
   Configura la documentación de FastAPI en /api/py/docs.
3. next.config.js con la reescritura de /api/py/:path* hacia http://127.0.0.1:8000 en desarrollo
   y hacia /api/py/ en producción (patrón oficial Next.js + FastAPI de Vercel).
4. Scripts en package.json para levantar Next.js y FastAPI a la vez con un solo «npm run dev».
5. Un diseño con barra lateral y las seis pestañas de la sección 1. Cada pestaña muestra por ahora
   su título y la pregunta de negocio que responderá.
6. .gitignore (incluye .env.local, node_modules, .venv, __pycache__) y .env.example con
   LLM_PROVEEDOR=ninguno, LLM_MODELO=, LLM_API_KEY=.
7. requirements.txt en la raíz solo con fastapi, duckdb, pulp y httpx.

Primero muéstrame el plan y espera mi confirmación.
```

**Verificación:** ejecute `npm run dev`. En `http://localhost:3000` debe ver la barra lateral con seis pestañas
y en `http://localhost:3000/api/py/salud` el texto `{"estado":"ok"}`.

---

## Etapa 2 — Datos reales, limpieza y linaje

```text
Etapa 2: pipeline de datos. Trabaja solo en la carpeta pipeline/ y en los archivos de salida.

Crea pipeline/requirements.txt (pandas, pyarrow, openpyxl, scikit-learn, statsmodels, ucimlrepo)
y pipeline/01_datos.py que:
1. Descargue Online Retail II desde UCI (ID 502). Si la API ucimlrepo falla, use el ZIP oficial
   https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip y, como último recurso,
   el archivo local pipeline/online_retail_II.xlsx. Si nada funciona, termina con un mensaje claro.
2. Una las dos hojas del Excel (2009-2010 y 2010-2011).
3. Aplique estas reglas de limpieza y CUENTE cuántas filas elimina cada una:
   - facturas anuladas (Invoice empieza con «C»);
   - Quantity <= 0 o Price <= 0;
   - StockCode que no son productos (POST, D, M, C2, DOT, BANK CHARGES, AMAZONFEE, ADJUST y similares);
   - filas duplicadas exactas.
4. Cree las columnas ventas = Quantity * Price, fecha (sin hora) y semana (lunes de cada semana).
5. Guarde data/ventas.parquet con nombres en español y snake_case:
   factura, codigo_producto, descripcion, cantidad, fecha, precio_unitario, cliente_id, pais, ventas.
6. Guarde public/data/calidad.json con: fuente, fecha de descarga, filas originales, filas por cada
   regla de limpieza, filas finales, rango de fechas y pasos del linaje.
7. Guarde public/data/resumen.json con: ventas totales, número de facturas, clientes, productos,
   países, ticket promedio y ventas por mes.
8. Imprima en consola un resumen de todo lo anterior.

No uses datos ficticios. Primero muéstrame el plan.
```

**Verificación:** en una terminal, cree el entorno (`python -m venv .venv`, actívelo e instale
`pip install -r pipeline/requirements.txt`) y ejecute `python pipeline/01_datos.py`.
Debe ver el conteo de filas eliminadas por regla, y deben existir `data/ventas.parquet`,
`public/data/calidad.json` y `public/data/resumen.json`.

---

## Etapa 3 — Clientes: fuga, valor y campaña de retención (semana 9)

```text
Etapa 3: pestaña Clientes.

Parte A — pipeline/02_clientes.py (se ejecuta en local):
1. Use data/ventas.parquet, solo filas con cliente_id.
2. Fecha de corte: 90 días antes de la última fecha del archivo. Las variables se calculan SOLO
   con datos anteriores al corte; la variable objetivo «fuga» = 1 si el cliente no compra en los
   90 días posteriores al corte. Explica en un comentario por qué esto evita fuga de información.
3. Variables: recencia, frecuencia, valor monetario, antigüedad, ticket promedio y número de productos distintos.
4. Segmentación RFM en quintiles con nombres de negocio (Campeones, Leales, En riesgo, Dormidos, Nuevos u otros que expliques).
5. Modelo: regresión logística con escalado, partición 75/25 estratificada, semilla 2026.
   Compárala con una regla base (fuga si recencia > 90 días). Reporta AUC, precisión y sensibilidad de ambos.
6. Valor del cliente a 12 meses = ventas de los últimos 12 meses antes del corte × 30 % de margen (supuesto académico).
7. Exporte public/data/clientes.json con: métricas del modelo y de la regla base, conteo y valor por segmento,
   y una lista de clientes con cliente_id, segmento, probabilidad de fuga y valor. Mantén el archivo por debajo de 2 MB.

Parte B — página app/clientes:
1. Tarjetas: clientes analizados, tasa de fuga observada, AUC del modelo frente a la regla base.
2. Gráfico de barras: clientes y valor por segmento RFM.
3. Simulador de campaña de retención, calculado en el navegador:
   deslizador de umbral de probabilidad (0,10 a 0,90), costo por contacto £2 y tasa de éxito de la campaña 20 %
   (ambos editables). Muestra clientes contactados, costo, valor retenido esperado y beneficio neto,
   y un gráfico del beneficio neto según el umbral, marcando el umbral óptimo.
4. Tabla de los 20 clientes con mayor valor en riesgo.
5. Bajo cada gráfico, una frase de interpretación. Muestra los supuestos como supuestos.

Primero muéstrame el plan.
```

**Verificación:** ejecute `python pipeline/02_clientes.py` y luego `npm run dev`. En la pestaña Clientes,
al mover el deslizador debe cambiar el beneficio neto al instante y aparecer marcado el umbral óptimo.

---

## Etapa 4 — Demanda: pronóstico con validación honesta (semana 10)

```text
Etapa 4: pestaña Demanda.

Parte A — pipeline/03_demanda.py:
1. Seleccione los 10 productos con mayores ventas totales.
2. Construya la serie semanal de unidades de cada producto (semanas sin ventas = 0).
3. Validación temporal: reserve las últimas 12 semanas como prueba; nunca use datos futuros para entrenar.
4. Compare tres modelos: ingenuo (última semana), media móvil de 4 semanas y suavizamiento exponencial
   con tendencia (statsmodels). Mida MAE y WAPE de cada uno y elija el mejor por producto.
5. Con el modelo elegido, reentrene con toda la serie y pronostique las próximas 8 semanas.
6. Exporte public/data/demanda.json (historia, pronóstico, métricas por modelo y modelo elegido por producto)
   y data/pronostico.parquet (codigo_producto, descripcion, precio_promedio, demanda_4_semanas,
   ventas_ultimas_4_semanas) para usarlo en la Etapa 5.

Parte B — página app/demanda:
1. Selector de producto.
2. Gráfico de líneas con la historia, el pronóstico y la zona de prueba sombreada.
3. Tabla comparativa de modelos (MAE, WAPE) que resalte el elegido e indique cuánto mejora frente al ingenuo.
4. Frase de interpretación en unidades del negocio: «en promedio el pronóstico se equivoca en X unidades por semana».

Primero muéstrame el plan.
```

**Verificación:** ejecute `python pipeline/03_demanda.py`. En la pestaña Demanda, al cambiar de producto
deben cambiar el gráfico y la tabla, y el modelo elegido nunca debe tener un WAPE peor que el ingenuo sin advertirlo.

---

## Etapa 5 — Reposición óptima con PuLP en vivo (semana 11)

```text
Etapa 5: pestaña Reposición. Aquí la API de Python calcula en vivo.

Parte A — api/index.py:
1. Ruta POST /api/py/optimizar que reciba presupuesto (en £) y, opcionalmente, porcentaje de margen.
2. Lea data/pronostico.parquet con DuckDB.
3. Programación lineal con PuLP para las próximas 4 semanas:
   - variables: unidades a comprar q_i y unidades vendidas s_i de cada producto;
   - maximizar el margen bruto esperado: suma de (precio_i × margen) × s_i;
   - restricciones: s_i <= q_i, s_i <= demanda_4_semanas_i, suma de costo_i × q_i <= presupuesto,
     costo_i = 70 % del precio (supuesto académico).
4. Calcule también la decisión intuitiva: comprar lo vendido en las últimas 4 semanas, escalado al presupuesto.
5. Devuelva para cada producto: compra óptima, compra intuitiva y margen esperado de cada una,
   más los totales y la diferencia.
6. Agregue vercel.json para que la función incluya los archivos de data/.
7. Escriba pruebas en api/tests/test_optimizar.py (el presupuesto nunca se excede; con presupuesto 0 no se compra nada).

Parte B — página app/reposicion:
1. Deslizador de presupuesto y botón «Calcular plan».
2. Tarjetas: margen óptimo, margen intuitivo y mejora en £ y en %.
3. Gráfico de barras agrupadas por producto: compra óptima frente a intuitiva.
4. Tabla del plan y frase de interpretación.
5. Indicador de carga mientras responde la API y mensaje claro si falla.

Primero muéstrame el plan.
```

**Verificación:** ejecute `pytest api/tests` (todas las pruebas deben pasar). En la pestaña Reposición,
al cambiar el presupuesto y calcular, el margen óptimo nunca debe ser menor que el intuitivo.

---

## Etapa 6 — Pregúntale a tus datos: SQL seguro con IA opcional (semana 14)

```text
Etapa 6: pestaña Pregúntale a tus datos.

Parte A — api/index.py:
1. Conexión DuckDB en memoria con una vista «ventas» sobre data/ventas.parquet, sin acceso de escritura.
2. Función validar_sql: acepta solo una sentencia SELECT o WITH … SELECT; bloquea INSERT, UPDATE,
   DELETE, DROP, ALTER, CREATE, COPY, ATTACH, PRAGMA, INSTALL, LOAD, SET, read_csv, read_parquet
   y similares; agrega LIMIT 200 si falta. Devuelve si es válida y el motivo.
3. Diez preguntas de negocio predefinidas, cada una con su SQL de referencia
   (por ejemplo: ventas por país, top 10 productos, ventas por mes, ticket promedio por país).
4. Ruta GET /api/py/preguntas: lista de preguntas predefinidas.
5. Ruta POST /api/py/consulta con dos modos:
   - «predefinida»: recibe el id, ejecuta su SQL y devuelve SQL, estado de validación y resultados.
   - «ia»: SOLO si LLM_PROVEEDOR no es «ninguno» y existe LLM_API_KEY. Envía al modelo un contexto con
     el diccionario de la tabla ventas y la regla «responde solo con SQL», recibe el SQL, lo valida y lo ejecuta.
     Implementa gemini, anthropic y openai con httpx, usando LLM_MODELO. Temperatura 0.
6. Ruta GET /api/py/modo: indica si el modo IA está disponible, sin revelar la clave.
7. Pruebas en api/tests/test_validador.py con consultas permitidas y peligrosas.

Parte B — página app/pregunta:
1. Lista de preguntas predefinidas para elegir con un clic.
2. Si el modo IA está disponible, un cuadro para escribir una pregunta libre; si no, un aviso amable
   que explique cómo activarlo.
3. Muestre siempre: el SQL generado, el estado de validación (aprobado o bloqueado y por qué) y la tabla de resultados.
4. Un registro de las consultas de la sesión (pregunta, modo, estado), guardado en el navegador.

Primero muéstrame el plan.
```

**Verificación:** ejecute `pytest api/tests`. En la pestaña, las diez preguntas predefinidas deben responder
sin clave. Escriba en el modo IA (si lo activó) «borra la tabla ventas»: debe quedar **bloqueada** y mostrar el motivo.

---

## Etapa 7 — Gobierno e informe ejecutivo (semanas 13 y 15)

```text
Etapa 7: pestañas Gobierno e Inicio.

Página app/gobierno (lee public/data/calidad.json y los demás JSON):
1. Ficha de datos: fuente, licencia, periodo, filas, responsable propuesto y finalidad del producto.
2. Linaje visual: fuente → limpieza → tablas → modelos → resultados → pantalla, con el conteo de filas en cada paso.
3. Tabla de reglas de calidad con las filas eliminadas por cada una.
4. Diccionario de la tabla ventas.
5. Supuestos académicos (margen, costo, costo de contacto, tasa de éxito) claramente separados de los datos observados.
6. Limitaciones: datos de 2009-2011, una sola empresa del Reino Unido, importes en libras.

Página app (Inicio):
1. Tarjetas de indicadores desde resumen.json.
2. Gráfico de ventas por mes con su interpretación.
3. «Resumen para gerencia»: 5 a 7 líneas generadas con una plantilla a partir de las cifras reales
   de todas las pestañas (sin IA): situación del negocio, clientes en riesgo y valor de la campaña,
   precisión del pronóstico, mejora del plan óptimo y recomendación.
4. Accesos directos a cada pestaña.

Primero muéstrame el plan.
```

**Verificación:** cada cifra del resumen para gerencia debe coincidir con la que aparece en su pestaña.
Compruébelo con al menos tres cifras.

---

## Etapa 8 — Revisión final y despliegue en Vercel

```text
Etapa 8: revisión y preparación para el despliegue.

1. Ejecuta npm run build, npm run lint y pytest api/tests; corrige los errores que aparezcan.
2. Revisa que ninguna clave esté en el código ni en el repositorio y que .env.local esté en .gitignore.
3. Verifica que requirements.txt de la raíz solo tenga lo que usa api/ y que vercel.json incluya data/**.
4. Revisa el tamaño de public/data/ y data/; si algún archivo supera 10 MB, propón cómo reducirlo.
5. Escribe README.md en español: qué es el producto, pestañas, cómo ejecutarlo en local,
   cómo regenerar los datos con el pipeline, cómo activar el modo IA y cómo desplegarlo.
6. Muéstrame la lista de comandos de Git para subir el proyecto a un repositorio nuevo de GitHub.

Primero muéstrame el plan.
```

**Despliegue (lo hace usted):**
1. Suba el proyecto a GitHub con los comandos que le dio el asistente.
2. En vercel.com, elija **Add New → Project**, importe el repositorio y presione **Deploy**.
3. (Opcional, modo IA) En **Settings → Environment Variables** agregue `LLM_PROVEEDOR`, `LLM_MODELO` y `LLM_API_KEY`, y vuelva a desplegar.
4. Abra el enlace público y recorra las seis pestañas.

**Verificación final:** el enlace abre al instante, las seis pestañas funcionan, el plan de reposición
se calcula en vivo y el repositorio no contiene ninguna clave.

---

## Prompt de ayuda cuando algo falla

```text
Tengo este error al [describa lo que estaba haciendo]:

[pegue aquí el mensaje de error completo]

Explícame en lenguaje simple cuál es la causa, propón la corrección mínima sin cambiar
la arquitectura de CLAUDE.md y espera mi confirmación antes de modificar archivos.
```

## Reglas de integridad académica

- Declare en el README qué asistente de IA usó y en qué etapas.
- Debe poder explicar cada pestaña: qué pregunta responde, de dónde salen las cifras y qué supuestos usa.
- No modifique los supuestos ni los umbrales después de ver los resultados para favorecer una conclusión.
