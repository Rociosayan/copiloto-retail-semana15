"""
Pronostica la demanda semanal de los diez productos con mayores ventas.
Las últimas doce semanas quedan fuera del entrenamiento para comparar los modelos con honestidad.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing

RAIZ = Path(__file__).resolve().parent.parent
VENTAS = RAIZ / "data" / "ventas.parquet"
SALIDA = RAIZ / "public" / "data" / "demanda.json"
PRONOSTICO = RAIZ / "data" / "pronostico.parquet"
HORIZONTE_PRUEBA = 12
HORIZONTE_FUTURO = 8


def main() -> None:
    if not VENTAS.exists():
        raise SystemExit("No está data/ventas.parquet. Ejecute antes pipeline/01_datos.py.")

    ventas = pd.read_parquet(VENTAS)
    ventas["fecha"] = pd.to_datetime(ventas["fecha"])
    ventas["semana"] = ventas["fecha"] - pd.to_timedelta(ventas["fecha"].dt.weekday, unit="D")

    totales = ventas.groupby("codigo_producto")["ventas"].sum().sort_values(ascending=False)
    top = list(totales.head(10).index)
    descripciones = (
        ventas.groupby("codigo_producto")["descripcion"]
        .agg(lambda serie: serie.mode().iloc[0] if not serie.mode().empty else serie.iloc[0])
    )
    precios = ventas.groupby("codigo_producto").apply(
        lambda g: g["ventas"].sum() / g["cantidad"].sum(), include_groups=False
    )

    lunes = pd.date_range(ventas["semana"].min(), ventas["semana"].max(), freq="W-MON")
    productos = []
    filas_parquet = []

    for codigo in top:
        sub = ventas.loc[ventas["codigo_producto"] == codigo]
        serie = sub.groupby("semana")["cantidad"].sum().reindex(lunes, fill_value=0).astype(float)
        resultado = evaluar(serie)
        futuro = pronosticar(serie, resultado["elegido"])
        historia = [
            {
                "semana": fecha.date().isoformat(),
                "unidades": round(float(valor), 2),
                "prueba": fecha >= serie.index[-HORIZONTE_PRUEBA],
            }
            for fecha, valor in serie.items()
        ]
        productos.append(
            {
                "codigo": codigo,
                "descripcion": str(descripciones.get(codigo, "")),
                "modelo_elegido": resultado["elegido"],
                "mae_elegido": resultado["mae_elegido"],
                "wape_elegido": resultado["wape_elegido"],
                "mejora_wape_vs_ingenuo": resultado["mejora"],
                "advertencia": resultado["advertencia"],
                "inicio_prueba": serie.index[-HORIZONTE_PRUEBA].date().isoformat(),
                "modelos": resultado["modelos"],
                "historia": historia,
                "pronostico": [
                    {"semana": fecha.date().isoformat(), "unidades": round(float(valor), 2)}
                    for fecha, valor in futuro.items()
                ],
            }
        )
        precio = float(precios.get(codigo, 0))
        unidades_4 = float(serie.iloc[-4:].sum())
        filas_parquet.append(
            {
                "codigo_producto": codigo,
                "descripcion": str(descripciones.get(codigo, "")),
                "precio_promedio": round(precio, 4),
                "demanda_4_semanas": round(float(max(futuro.iloc[:4].sum(), 0)), 2),
                # Unidades vendidas, no importe: la reposición compra unidades.
                "ventas_ultimas_4_semanas": round(unidades_4, 2),
            }
        )

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps({"productos": productos}, ensure_ascii=False), encoding="utf-8")
    pd.DataFrame(filas_parquet).to_parquet(PRONOSTICO, index=False)
    print(f"Productos pronosticados: {len(productos)}")
    for producto in productos:
        print(
            f"  {producto['codigo']} {producto['modelo_elegido']:16} "
            f"WAPE {producto['wape_elegido']:.1%}  MAE {producto['mae_elegido']:.1f}"
        )
    print(f"Archivos: {SALIDA}")
    print(f"          {PRONOSTICO}")


def evaluar(serie: pd.Series) -> dict:
    reales = serie.iloc[-HORIZONTE_PRUEBA:].to_numpy()
    entrenamiento = serie.iloc[:-HORIZONTE_PRUEBA]
    candidatos = {
        "Ingenuo": np.repeat(float(entrenamiento.iloc[-1]), HORIZONTE_PRUEBA),
        "Media móvil 4": np.repeat(float(entrenamiento.iloc[-4:].mean()), HORIZONTE_PRUEBA),
        "Suavizamiento con tendencia": holt(entrenamiento, HORIZONTE_PRUEBA),
    }
    modelos = []
    for nombre, estimado in candidatos.items():
        if estimado is None:
            modelos.append({"nombre": nombre, "mae": None, "wape": None, "elegido": False, "disponible": False})
            continue
        modelos.append(
            {
                "nombre": nombre,
                "mae": round(mae(reales, estimado), 2),
                "wape": round(wape(reales, estimado), 4),
                "elegido": False,
                "disponible": True,
            }
        )
    utiles = [m for m in modelos if m["disponible"] and m["wape"] is not None]
    elegido = sorted(utiles, key=lambda m: (m["wape"], m["mae"]))[0]
    ingenuo = next(m for m in modelos if m["nombre"] == "Ingenuo")
    advertencia = None
    if ingenuo["wape"] is not None and elegido["wape"] > ingenuo["wape"] + 1e-9:
        advertencia = "El modelo elegido tiene un WAPE peor que el ingenuo. Conviene quedarse con el ingenuo para este producto."
    for modelo in modelos:
        modelo["elegido"] = modelo["nombre"] == elegido["nombre"]
    mejora = None
    if ingenuo["wape"]:
        mejora = round((ingenuo["wape"] - elegido["wape"]) / ingenuo["wape"], 4)
    return {
        "elegido": elegido["nombre"],
        "mae_elegido": elegido["mae"],
        "wape_elegido": elegido["wape"],
        "mejora": mejora,
        "advertencia": advertencia,
        "modelos": modelos,
    }


def pronosticar(serie: pd.Series, nombre: str) -> pd.Series:
    if nombre == "Ingenuo":
        valores = np.repeat(float(serie.iloc[-1]), HORIZONTE_FUTURO)
    elif nombre == "Media móvil 4":
        valores = np.repeat(float(serie.iloc[-4:].mean()), HORIZONTE_FUTURO)
    else:
        valores = holt(serie, HORIZONTE_FUTURO)
        if valores is None:
            valores = np.repeat(float(serie.iloc[-1]), HORIZONTE_FUTURO)
    valores = np.maximum(valores, 0)
    inicio = serie.index[-1] + pd.Timedelta(days=7)
    indice = pd.date_range(inicio, periods=HORIZONTE_FUTURO, freq="W-MON")
    return pd.Series(valores, index=indice)


def holt(serie: pd.Series, pasos: int):
    if len(serie) < 8 or float(serie.sum()) == 0:
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ajuste = ExponentialSmoothing(
                serie.to_numpy(),
                trend="add",
                seasonal=None,
                initialization_method="estimated",
            ).fit(optimized=True)
            return np.asarray(ajuste.forecast(pasos), dtype=float)
    except Exception:
        return None


def mae(real: np.ndarray, estimado: np.ndarray) -> float:
    return float(np.mean(np.abs(real - estimado)))


def wape(real: np.ndarray, estimado: np.ndarray) -> float:
    denominador = float(np.abs(real).sum())
    if denominador == 0:
        return 0.0
    return float(np.abs(real - estimado).sum() / denominador)


if __name__ == "__main__":
    main()
