"""
Descarga Online Retail II, aplica las reglas de limpieza y exporta la base del producto.
Cada regla deja contadas las filas que elimina para mostrar el linaje en Gobierno.
"""

from __future__ import annotations

import json
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parent.parent
DIR_DATA = RAIZ / "data"
DIR_PUBLIC = RAIZ / "public" / "data"
DIR_PIPELINE = Path(__file__).resolve().parent
ZIP_LOCAL = DIR_PIPELINE / "online_retail_ii.zip"
XLSX_LOCAL = DIR_PIPELINE / "online_retail_II.xlsx"
URL_ZIP = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"

# Cargos, ajustes y códigos de servicio que no son mercadería.
CODIGOS_NO_PRODUCTO = {
    "POST",
    "D",
    "M",
    "C2",
    "DOT",
    "BANK CHARGES",
    "AMAZONFEE",
    "ADJUST",
    "ADJUST2",
    "CRUK",
    "PADS",
    "B",
    "S",
    "GIFT",
    "TEST001",
    "TEST002",
}


def main() -> None:
    DIR_DATA.mkdir(parents=True, exist_ok=True)
    DIR_PUBLIC.mkdir(parents=True, exist_ok=True)

    crudo = cargar()
    crudo = normalizar_columnas(crudo)
    filas_originales = int(len(crudo))
    reglas: list[dict] = []

    factura = crudo["factura"].astype(str).str.strip()
    anuladas = factura.str.upper().str.startswith("C")
    crudo, _ = aplicar(crudo, anuladas, reglas, "facturas_anuladas", "Facturas anuladas (el código empieza con C)")

    cantidad = pd.to_numeric(crudo["cantidad"], errors="coerce")
    precio = pd.to_numeric(crudo["precio_unitario"], errors="coerce")
    invalidas = cantidad.isna() | precio.isna() | (cantidad <= 0) | (precio <= 0)
    crudo, _ = aplicar(crudo, invalidas, reglas, "cantidad_o_precio", "Cantidad o precio menores o iguales a cero, o no numéricos")

    codigo = crudo["codigo_producto"].astype(str).str.strip().str.upper()
    no_producto = codigo.isin(CODIGOS_NO_PRODUCTO) | codigo.eq("") | codigo.eq("NAN")
    crudo, _ = aplicar(crudo, no_producto, reglas, "no_producto", "Códigos que no son productos (envío, descuento, ajuste y similares)")

    antes = len(crudo)
    crudo = crudo.drop_duplicates()
    reglas.append(
        {
            "id": "duplicados",
            "descripcion": "Filas duplicadas exactas",
            "filas_eliminadas": int(antes - len(crudo)),
        }
    )

    crudo["cantidad"] = pd.to_numeric(crudo["cantidad"], errors="coerce")
    crudo["precio_unitario"] = pd.to_numeric(crudo["precio_unitario"], errors="coerce")
    crudo["fecha"] = pd.to_datetime(crudo["fecha"], errors="coerce").dt.normalize()
    sin_fecha = crudo["fecha"].isna()
    if sin_fecha.any():
        reglas.append(
            {
                "id": "sin_fecha",
                "descripcion": "Filas sin fecha interpretable",
                "filas_eliminadas": int(sin_fecha.sum()),
            }
        )
        crudo = crudo.loc[~sin_fecha].copy()

    cliente = pd.to_numeric(crudo["cliente_id"], errors="coerce").round()
    crudo["cliente_id"] = cliente.astype("Int64")
    crudo["factura"] = crudo["factura"].astype(str).str.strip()
    crudo["codigo_producto"] = crudo["codigo_producto"].astype(str).str.strip().str.upper()
    crudo["descripcion"] = crudo["descripcion"].fillna("").astype(str).str.strip()
    crudo["pais"] = crudo["pais"].fillna("").astype(str).str.strip()
    crudo["ventas"] = crudo["cantidad"] * crudo["precio_unitario"]

    columnas = [
        "factura",
        "codigo_producto",
        "descripcion",
        "cantidad",
        "fecha",
        "precio_unitario",
        "cliente_id",
        "pais",
        "ventas",
    ]
    ventas = crudo[columnas].copy()
    destino = DIR_DATA / "ventas.parquet"
    ventas.to_parquet(destino, index=False)

    por_mes = (
        ventas.groupby(ventas["fecha"].dt.to_period("M"))["ventas"]
        .sum()
        .reset_index()
    )
    por_mes["mes"] = por_mes["fecha"].astype(str)
    ticket = ventas.groupby("factura")["ventas"].sum()
    por_pais = (
        ventas.groupby("pais", as_index=False)
        .agg(ventas=("ventas", "sum"), facturas=("factura", "nunique"))
        .sort_values("ventas", ascending=False)
    )
    productos = (
        ventas.groupby("codigo_producto", as_index=False)
        .agg(ventas=("ventas", "sum"), descripcion=("descripcion", "first"))
        .nlargest(10, "ventas")
    )
    avance_pais = ventas.assign(mes=ventas["fecha"].dt.to_period("M").astype(str))
    avance_pais = (
        avance_pais.groupby(["pais", "mes"], as_index=False)["ventas"]
        .sum()
        .sort_values(["pais", "mes"])
    )
    resumen = {
        "ventas_totales": redondear(ventas["ventas"].sum()),
        "facturas": int(ventas["factura"].nunique()),
        "clientes": int(ventas["cliente_id"].nunique(dropna=True)),
        "productos": int(ventas["codigo_producto"].nunique()),
        "paises": int(ventas["pais"].nunique()),
        "ticket_promedio": redondear(ticket.mean()),
        "ventas_por_mes": [
            {"mes": fila.mes, "ventas": redondear(fila.ventas)}
            for fila in por_mes.itertuples(index=False)
        ],
    }

    filas_finales = int(len(ventas))
    linaje = [{"paso": "Fuente UCI Online Retail II", "filas": filas_originales}]
    restantes = filas_originales
    for regla in reglas:
        restantes -= regla["filas_eliminadas"]
        linaje.append({"paso": regla["descripcion"], "filas": int(restantes)})

    calidad = {
        "fuente": "UCI Machine Learning Repository — Online Retail II",
        "id_uci": 502,
        "url": "https://archive.ics.uci.edu/dataset/502/online+retail+ii",
        "licencia": "Creative Commons Attribution 4.0 (CC BY 4.0)",
        "fecha_descarga": datetime.now(timezone.utc).date().isoformat(),
        "filas_originales": filas_originales,
        "reglas": reglas,
        "filas_finales": filas_finales,
        "fecha_min": ventas["fecha"].min().date().isoformat(),
        "fecha_max": ventas["fecha"].max().date().isoformat(),
        "linaje": linaje,
        "responsable_propuesto": "Analítica comercial",
        "finalidad": "Apoyar decisiones de retención, pronóstico de demanda y compras.",
        "moneda": "GBP",
        "diccionario": [
            {"campo": "factura", "descripcion": "Código de la factura", "ejemplo": "489434"},
            {"campo": "codigo_producto", "descripcion": "Código de producto (SKU)", "ejemplo": "85048"},
            {"campo": "descripcion", "descripcion": "Nombre del producto", "ejemplo": "15CM CHRISTMAS GLASS BALL"},
            {"campo": "cantidad", "descripcion": "Unidades de la línea de factura", "ejemplo": "12"},
            {"campo": "fecha", "descripcion": "Día de la factura, sin hora", "ejemplo": "2009-12-01"},
            {"campo": "precio_unitario", "descripcion": "Precio unitario en libras esterlinas", "ejemplo": "6.95"},
            {"campo": "cliente_id", "descripcion": "Identificador del cliente; vacío si la tienda no lo registró", "ejemplo": "13085"},
            {"campo": "pais", "descripcion": "País de entrega", "ejemplo": "United Kingdom"},
            {"campo": "ventas", "descripcion": "Importe de la línea: cantidad por precio unitario, en libras", "ejemplo": "83.40"},
        ],
    }

    tablero = {
        "ventas_totales": resumen["ventas_totales"],
        "facturas": resumen["facturas"],
        "clientes": resumen["clientes"],
        "productos": resumen["productos"],
        "paises": resumen["paises"],
        "ticket_promedio": resumen["ticket_promedio"],
        "fecha_min": ventas["fecha"].min().date().isoformat(),
        "fecha_max": ventas["fecha"].max().date().isoformat(),
        "ranking_paises": [
            {"pais": fila.pais, "ventas": redondear(fila.ventas), "facturas": int(fila.facturas)}
            for fila in por_pais.itertuples(index=False)
        ],
        "avance_mensual": resumen["ventas_por_mes"],
        "avance_por_pais": [
            {"pais": fila.pais, "mes": fila.mes, "ventas": redondear(fila.ventas)}
            for fila in avance_pais.itertuples(index=False)
        ],
        "top_productos": [
            {
                "codigo": fila.codigo_producto,
                "descripcion": fila.descripcion,
                "ventas": redondear(fila.ventas),
            }
            for fila in productos.itertuples(index=False)
        ],
    }
    escribir_json(DIR_PUBLIC / "calidad.json", calidad)
    escribir_json(DIR_PUBLIC / "resumen.json", resumen)
    escribir_json(DIR_PUBLIC / "tablero.json", tablero)
    imprimir(filas_originales, reglas, filas_finales, resumen, destino)


def cargar() -> pd.DataFrame:
    """Usa el ZIP oficial si ya está en la carpeta; si no, prueba ucimlrepo y la descarga."""
    if ZIP_LOCAL.exists():
        print(f"Fuente: ZIP oficial ya presente en {ZIP_LOCAL.name}.")
        with zipfile.ZipFile(ZIP_LOCAL) as archivo:
            nombre = next(item for item in archivo.namelist() if item.lower().endswith(".xlsx"))
            excel = archivo.read(nombre)
        XLSX_LOCAL.write_bytes(excel)
        return leer_excel(BytesIO(excel))

    obtenido = intentar_ucimlrepo()
    if obtenido is not None and len(obtenido) > 0:
        print("Fuente: ucimlrepo, conjunto 502.")
        return obtenido

    contenido = None
    if ZIP_LOCAL.exists():
        contenido = ZIP_LOCAL.read_bytes()
        print(f"Fuente: ZIP oficial ya presente en {ZIP_LOCAL.name}.")
    else:
        try:
            import urllib.request

            print("Descargando el ZIP oficial de UCI...")
            with urllib.request.urlopen(URL_ZIP, timeout=180) as respuesta:
                contenido = respuesta.read()
            ZIP_LOCAL.write_bytes(contenido)
            print("Fuente: ZIP oficial descargado de UCI.")
        except Exception as exc:
            print(f"No se pudo descargar el ZIP ({exc}).")

    if contenido:
        with zipfile.ZipFile(BytesIO(contenido)) as archivo:
            nombre = next(item for item in archivo.namelist() if item.lower().endswith(".xlsx"))
            excel = archivo.read(nombre)
        XLSX_LOCAL.write_bytes(excel)
        return leer_excel(BytesIO(excel))

    if XLSX_LOCAL.exists():
        print(f"Fuente: Excel local {XLSX_LOCAL.name}.")
        return leer_excel(XLSX_LOCAL)

    raise SystemExit(
        "No se pudo obtener Online Retail II. Coloque pipeline/online_retail_II.xlsx y vuelva a ejecutar."
    )


def intentar_ucimlrepo() -> pd.DataFrame | None:
    import threading

    caja: dict = {}

    def trabajo() -> None:
        try:
            from ucimlrepo import fetch_ucirepo

            repo = fetch_ucirepo(id=502)
            caja["df"] = repo.data.original.copy()
        except Exception as exc:  # La red o el paquete pueden fallar: se usa el ZIP.
            caja["error"] = exc

    hilo = threading.Thread(target=trabajo, daemon=True)
    hilo.start()
    hilo.join(90)
    if hilo.is_alive():
        print("ucimlrepo no respondió a tiempo. Se usa el ZIP oficial.")
        return None
    if "error" in caja:
        print(f"ucimlrepo no disponible ({caja['error']}). Se usa el ZIP oficial.")
        return None
    return caja.get("df")


def leer_excel(origen) -> pd.DataFrame:
    print("Leyendo el Excel oficial.")
    motor = "openpyxl"
    try:
        import python_calamine  # noqa: F401

        motor = "calamine"
    except ImportError:
        print("Sin lector rápido: openpyxl puede tardar varios minutos.")
    hojas = pd.read_excel(origen, sheet_name=None, engine=motor)
    marcos = []
    for nombre, hoja in hojas.items():
        print(f"Hoja {nombre}: {len(hoja):,} filas")
        marcos.append(hoja)
    return pd.concat(marcos, ignore_index=True)


def normalizar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(columna).strip() for columna in df.columns]
    mapa = {
        "Invoice": "factura",
        "InvoiceNo": "factura",
        "StockCode": "codigo_producto",
        "Description": "descripcion",
        "Quantity": "cantidad",
        "InvoiceDate": "fecha",
        "Price": "precio_unitario",
        "UnitPrice": "precio_unitario",
        "Customer ID": "cliente_id",
        "CustomerID": "cliente_id",
        "Country": "pais",
    }
    faltan = [origen for origen in ("Invoice", "InvoiceNo") if origen not in df.columns and "factura" not in df.columns]
    df = df.rename(columns={origen: destino for origen, destino in mapa.items() if origen in df.columns})
    requeridas = ["factura", "codigo_producto", "descripcion", "cantidad", "fecha", "precio_unitario", "cliente_id", "pais"]
    ausentes = [columna for columna in requeridas if columna not in df.columns]
    if ausentes:
        raise SystemExit(f"El archivo no trae las columnas esperadas: {', '.join(ausentes)}. Revisar la fuente, no se inventan datos.")
    if faltan and "factura" not in df.columns:
        raise SystemExit("No se encontró la columna de factura.")
    return df


def aplicar(df: pd.DataFrame, mascara, reglas: list[dict], identificador: str, descripcion: str):
    eliminadas = int(mascara.fillna(False).sum())
    reglas.append({"id": identificador, "descripcion": descripcion, "filas_eliminadas": eliminadas})
    return df.loc[~mascara.fillna(False)].copy(), eliminadas


def escribir_json(ruta: Path, contenido: dict) -> None:
    ruta.write_text(json.dumps(contenido, ensure_ascii=False, indent=2), encoding="utf-8")


def redondear(valor) -> float:
    return round(float(valor), 2)


def imprimir(filas_originales: int, reglas: list[dict], filas_finales: int, resumen: dict, destino: Path) -> None:
    print("--- Limpieza ---")
    print(f"Filas originales: {filas_originales:,}")
    for regla in reglas:
        print(f"  {regla['descripcion']}: {regla['filas_eliminadas']:,}")
    print(f"Filas finales: {filas_finales:,}")
    print("--- Negocio ---")
    print(f"Ventas: £ {resumen['ventas_totales']:,.2f}")
    print(f"Facturas: {resumen['facturas']:,} | Clientes: {resumen['clientes']:,} | Productos: {resumen['productos']:,} | Países: {resumen['paises']:,}")
    print(f"Ticket promedio: £ {resumen['ticket_promedio']:,.2f}")
    print(f"Archivos: {destino}")
    print(f"          {DIR_PUBLIC / 'calidad.json'}")
    print(f"          {DIR_PUBLIC / 'resumen.json'}")


if __name__ == "__main__":
    main()
