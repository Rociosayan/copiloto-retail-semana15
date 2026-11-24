"""Precalcula ventas por país, mes y producto desde el Parquet depurado.
Los filtros del tablero usan estas sumas observadas sin consultar un millón de filas.
"""
import json
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parent.parent
con = duckdb.connect()
ruta = (RAIZ / "data" / "ventas.parquet").as_posix()
con.execute(f"CREATE VIEW ventas AS SELECT * FROM read_parquet('{ruta}')")

def filas(sql):
    tabla = con.execute(sql)
    columnas = [c[0] for c in tabla.description]
    return [dict(zip(columnas, fila)) for fila in tabla.fetchall()]

base = """SELECT pais, strftime(fecha, '%Y-%m') mes, codigo_producto codigo,
    coalesce(max(descripcion), codigo_producto) descripcion,
    round(sum(ventas), 2) ventas, sum(cantidad)::BIGINT unidades,
    count(distinct factura)::BIGINT facturas,
    count(distinct cliente_id)::BIGINT clientes
    FROM ventas GROUP BY 1, 2, 3"""
detalle = filas(base)
productos = {fila["codigo"]: fila["descripcion"] for fila in detalle}
datos = {
    "fuente": "Online Retail II · UCI 502 · ventas depuradas",
    "productos": productos,
    "detalle": [[fila["pais"], fila["mes"], fila["codigo"], fila["ventas"], fila["unidades"], fila["facturas"], fila["clientes"]] for fila in detalle],
    "pais_mes": filas("SELECT pais, strftime(fecha, '%Y-%m') mes, round(sum(ventas),2) ventas, count(distinct factura) facturas, count(distinct cliente_id) clientes FROM ventas GROUP BY 1,2"),
}
salida = RAIZ / "public" / "data" / "explorador.json"
salida.write_text(json.dumps(datos, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"{len(datos['detalle']):,} combinaciones; {salida.stat().st_size / 1e6:.1f} MB")
