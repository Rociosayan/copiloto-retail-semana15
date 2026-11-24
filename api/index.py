"""
API de optimización y consultas sobre ventas reales.
Las preguntas pasan por un validador antes de llegar a DuckDB.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import duckdb
import httpx
import pulp
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

RAIZ = Path(__file__).resolve().parent.parent
VENTAS = RAIZ / "data" / "ventas.parquet"
PRONOSTICO = RAIZ / "data" / "pronostico.parquet"
app = FastAPI(title="Copiloto Comercial Retail", docs_url="/api/py/docs", redoc_url=None, openapi_url="/api/py/openapi.json")


@app.get("/api/py/salud")
def salud():
    return {"estado": "ok"}


class Compra(BaseModel):
    presupuesto: float = Field(ge=0, le=1e9)
    margen: float = Field(default=0.30, gt=0, lt=1)


@app.post("/api/py/optimizar")
def optimizar(cuerpo: Compra):
    if not PRONOSTICO.exists():
        raise HTTPException(503, "Falta el pronóstico. Ejecute pipeline/03_demanda.py.")
    con = duckdb.connect()
    productos = con.execute("SELECT * FROM read_parquet(?)", [str(PRONOSTICO)]).df().to_dict("records")
    con.close()
    problema = pulp.LpProblem("reposicion", pulp.LpMaximize)
    compra = [pulp.LpVariable(f"q_{i}", lowBound=0, cat="Integer") for i in range(len(productos))]
    venta = [pulp.LpVariable(f"s_{i}", lowBound=0, cat="Integer") for i in range(len(productos))]
    costo = [float(p["precio_promedio"]) * (1 - cuerpo.margen) for p in productos]
    problema += pulp.lpSum(float(p["precio_promedio"]) * cuerpo.margen * venta[i] for i, p in enumerate(productos))
    problema += pulp.lpSum(costo[i] * compra[i] for i in range(len(productos))) <= cuerpo.presupuesto
    for i, p in enumerate(productos):
        problema += venta[i] <= compra[i]
        problema += venta[i] <= max(0, int(float(p["demanda_4_semanas"])))
    problema.solve(pulp.PULP_CBC_CMD(msg=False))
    if pulp.LpStatus[problema.status] != "Optimal":
        raise HTTPException(500, "El optimizador no encontró una solución.")
    # Referencia intuitiva: unidades de las cuatro semanas recientes, escaladas al presupuesto.
    intuitivo = [max(0, int(float(p["ventas_ultimas_4_semanas"]))) for p in productos]
    gasto = sum(c * q for c, q in zip(costo, intuitivo))
    if gasto > cuerpo.presupuesto and gasto:
        factor = cuerpo.presupuesto / gasto
        intuitivo = [int(q * factor) for q in intuitivo]
    filas = []
    margen_optimo = margen_intuitivo = 0.0
    for i, p in enumerate(productos):
        qo = int(pulp.value(compra[i]) or 0)
        qi = intuitivo[i]
        demanda = max(0, int(float(p["demanda_4_semanas"])))
        mo = min(qo, demanda) * float(p["precio_promedio"]) * cuerpo.margen
        mi = min(qi, demanda) * float(p["precio_promedio"]) * cuerpo.margen
        margen_optimo += mo
        margen_intuitivo += mi
        filas.append({"codigo_producto": p["codigo_producto"], "descripcion": p["descripcion"],
                      "compra_optima": qo, "compra_intuitiva": qi,
                      "margen_optimo": round(mo, 2), "margen_intuitivo": round(mi, 2)})
    return {"presupuesto": cuerpo.presupuesto, "margen_optimo": round(margen_optimo, 2),
            "margen_intuitivo": round(margen_intuitivo, 2),
            "mejora": round(margen_optimo - margen_intuitivo, 2), "productos": filas}


PREGUNTAS = [
    ("paises", "¿Qué países aportan más ventas?", "SELECT pais, ROUND(SUM(ventas),2) ventas FROM ventas GROUP BY pais ORDER BY ventas DESC LIMIT 10"),
    ("productos", "¿Cuáles son los diez productos líderes?", "SELECT codigo_producto, MAX(descripcion) descripcion, ROUND(SUM(ventas),2) ventas FROM ventas GROUP BY codigo_producto ORDER BY ventas DESC LIMIT 10"),
    ("meses", "¿Cómo evolucionaron las ventas por mes?", "SELECT strftime(fecha,'%Y-%m') mes, ROUND(SUM(ventas),2) ventas FROM ventas GROUP BY 1 ORDER BY 1"),
    ("clientes", "¿Qué clientes compraron más?", "SELECT cliente_id, ROUND(SUM(ventas),2) ventas FROM ventas WHERE cliente_id IS NOT NULL GROUP BY cliente_id ORDER BY ventas DESC LIMIT 10"),
    ("facturas", "¿Cuántas facturas hubo por año?", "SELECT year(fecha) anio, COUNT(DISTINCT factura) facturas FROM ventas GROUP BY 1 ORDER BY 1"),
    ("unidades", "¿Qué productos lideran por unidades?", "SELECT codigo_producto, MAX(descripcion) descripcion, SUM(cantidad) unidades FROM ventas GROUP BY 1 ORDER BY unidades DESC LIMIT 10"),
    ("ticket", "¿Cuál fue el ticket promedio por país?", "SELECT pais, ROUND(SUM(ventas)/COUNT(DISTINCT factura),2) ticket_promedio FROM ventas GROUP BY 1 ORDER BY ticket_promedio DESC LIMIT 10"),
    ("mejor_mes", "¿Cuál fue el mejor mes?", "SELECT strftime(fecha,'%Y-%m') mes, ROUND(SUM(ventas),2) ventas FROM ventas GROUP BY 1 ORDER BY ventas DESC LIMIT 1"),
    ("paises_2011", "¿Qué países destacaron en 2011?", "SELECT pais, ROUND(SUM(ventas),2) ventas FROM ventas WHERE year(fecha)=2011 GROUP BY 1 ORDER BY ventas DESC LIMIT 10"),
    ("total", "¿Cuánto vendimos en total?", "SELECT ROUND(SUM(ventas),2) ventas, COUNT(DISTINCT factura) facturas FROM ventas"),
]


def validar_sql(sql: str) -> tuple[bool, str, str]:
    limpio = re.sub(r"/\*.*?\*/|--[^\n]*", " ", sql.strip(), flags=re.S).strip().rstrip(";").strip()
    if not limpio or ";" in limpio:
        return False, "Solo se permite una sentencia.", ""
    if not re.match(r"(?is)^(SELECT|WITH)\b", limpio):
        return False, "Solo se permite SELECT o WITH … SELECT.", ""
    if re.search(r"(?is)\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|COPY|ATTACH|DETACH|PRAGMA|INSTALL|LOAD|SET|CALL|EXPORT|IMPORT|VACUUM|DESCRIBE|EXPLAIN|READ_\w+|GLOB|HTTPFS|SQLITE_SCAN|GETENV|QUERY|CURRENT_SETTING|DUCKDB_\w+|SECRET)\b", limpio):
        return False, "La consulta contiene una operación no permitida.", ""
    if re.search(r"(?is)\bFROM\s+(?!ventas\b)|\bJOIN\s+(?!ventas\b)", limpio):
        return False, "Solo se permite consultar la vista ventas.", ""
    if re.search(r"(?is)\bLIMIT\s+\d+", limpio):
        limpio = re.sub(r"(?is)\bLIMIT\s+\d+", "LIMIT 200", limpio)
    else:
        limpio += " LIMIT 200"
    return True, "Aprobado: SELECT de solo lectura, máximo 200 filas.", limpio


@app.get("/api/py/preguntas")
def preguntas():
    return [{"id": p[0], "pregunta": p[1]} for p in PREGUNTAS]


@app.get("/api/py/modo")
def modo():
    return {"ia_disponible": bool(os.getenv("LLM_API_KEY") and os.getenv("LLM_PROVEEDOR", "ninguno") != "ninguno")}


class Consulta(BaseModel):
    modo: str
    id: str | None = None
    pregunta: str | None = None


def generar_sql(pregunta: str) -> str:
    proveedor = os.getenv("LLM_PROVEEDOR", "ninguno").lower()
    clave = os.getenv("LLM_API_KEY")
    modelo = os.getenv("LLM_MODELO")
    if not clave or not modelo or proveedor not in {"openai", "anthropic", "gemini"}:
        raise HTTPException(503, "Modo IA no configurado.")
    contexto = ("Devuelve solo SQL DuckDB SELECT sobre la vista ventas. Columnas: factura, codigo_producto, "
                "descripcion, cantidad, fecha, precio_unitario, cliente_id, pais, ventas. Máximo 200 filas. Pregunta: " + pregunta)
    try:
        with httpx.Client(timeout=30) as cliente:
            if proveedor == "openai":
                r = cliente.post("https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {clave}"},
                                 json={"model": modelo, "temperature": 0, "messages": [{"role": "user", "content": contexto}]})
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"]
            if proveedor == "anthropic":
                r = cliente.post("https://api.anthropic.com/v1/messages", headers={"x-api-key": clave, "anthropic-version": "2023-06-01"},
                                 json={"model": modelo, "max_tokens": 500, "temperature": 0, "messages": [{"role": "user", "content": contexto}]})
                r.raise_for_status()
                return r.json()["content"][0]["text"]
            r = cliente.post(f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent?key={clave}",
                             json={"contents": [{"parts": [{"text": contexto}]}], "generationConfig": {"temperature": 0}})
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (httpx.HTTPError, KeyError, IndexError) as exc:
        raise HTTPException(502, "El proveedor de IA no respondió correctamente.") from exc


@app.post("/api/py/consulta")
def consulta(cuerpo: Consulta):
    if cuerpo.modo == "predefinida":
        seleccion = next((p for p in PREGUNTAS if p[0] == cuerpo.id), None)
        if not seleccion:
            raise HTTPException(404, "Pregunta no encontrada.")
        sql = seleccion[2]
    elif cuerpo.modo == "ia":
        sql = generar_sql(cuerpo.pregunta or "")
    else:
        raise HTTPException(400, "Modo desconocido.")
    valido, motivo, seguro = validar_sql(sql)
    if not valido:
        return {"sql": sql, "validacion": motivo, "resultados": []}
    con = duckdb.connect()
    try:
        # La ruta es una constante local del proyecto, no texto recibido del usuario.
        con.execute(f"CREATE VIEW ventas AS SELECT * FROM read_parquet('{VENTAS.as_posix()}')")
        cursor = con.execute(seguro)
        columnas = [d[0] for d in cursor.description]
        filas = [dict(zip(columnas, row)) for row in cursor.fetchall()]
        return {"sql": seguro, "validacion": motivo, "resultados": filas}
    except duckdb.Error as exc:
        return {"sql": seguro, "validacion": f"Error de consulta: {str(exc)[:200]}", "resultados": []}
    finally:
        con.close()
