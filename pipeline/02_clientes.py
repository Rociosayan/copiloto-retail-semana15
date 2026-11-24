"""
Estima qué clientes dejarán de comprar y cuánto vale intentar retenerlos.
La fecha de corte separa las variables del resultado, para no usar el futuro al entrenar.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_score, recall_score, roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

RAIZ = Path(__file__).resolve().parent.parent
VENTAS = RAIZ / "data" / "ventas.parquet"
SALIDA = RAIZ / "public" / "data" / "clientes.json"
# Supuesto académico: el margen bruto es el 30 % de las ventas. No es un dato observado.
MARGEN = 0.30
SEMILLA = 2026


def main() -> None:
    if not VENTAS.exists():
        raise SystemExit("No está data/ventas.parquet. Ejecute antes pipeline/01_datos.py.")

    ventas = pd.read_parquet(VENTAS)
    ventas = ventas.dropna(subset=["cliente_id"]).copy()
    ventas["cliente_id"] = ventas["cliente_id"].astype("int64").astype(str)
    ventas["fecha"] = pd.to_datetime(ventas["fecha"])

    ultima = ventas["fecha"].max()
    corte = ultima - pd.Timedelta(days=90)
    # Solo lo anterior al corte entra a las variables. Los 90 días siguientes definen la fuga.
    antes = ventas.loc[ventas["fecha"] < corte].copy()
    despues = ventas.loc[ventas["fecha"] >= corte, "cliente_id"]
    compraron_despues = set(despues.unique())

    tabla = agregar(antes, corte)
    tabla["fuga"] = (~tabla["cliente_id"].isin(compraron_despues)).astype(int)
    inicio_12 = corte - pd.Timedelta(days=365)
    ventas_12 = (
        antes.loc[antes["fecha"] >= inicio_12]
        .groupby("cliente_id")["ventas"]
        .sum()
    )
    tabla["valor"] = tabla["cliente_id"].map(ventas_12).fillna(0) * MARGEN

    tabla["r"] = quintil_mejor_si_menor(tabla["recencia"])
    tabla["f"] = quintil_mejor_si_mayor(tabla["frecuencia"])
    tabla["m"] = quintil_mejor_si_mayor(tabla["valor_monetario"])
    tabla["segmento"] = tabla.apply(etiquetar, axis=1)

    metricas, modelo = entrenar(tabla)
    variables = ["recencia", "frecuencia", "valor_monetario", "antiguedad", "ticket_promedio", "productos_distintos"]
    tabla["probabilidad_fuga"] = modelo.predict_proba(tabla[variables])[:, 1]

    segmentos = (
        tabla.groupby("segmento")
        .agg(clientes=("cliente_id", "size"), valor=("valor", "sum"))
        .reset_index()
        .sort_values("valor", ascending=False)
    )
    clientes = tabla[["cliente_id", "segmento", "probabilidad_fuga", "valor"]].copy()
    clientes["probabilidad_fuga"] = clientes["probabilidad_fuga"].round(4)
    clientes["valor"] = clientes["valor"].round(2)

    payload = {
        "fecha_corte": corte.date().isoformat(),
        "fecha_ultima": ultima.date().isoformat(),
        "clientes_analizados": int(len(tabla)),
        "tasa_fuga": round(float(tabla["fuga"].mean()), 4),
        "modelo": metricas["modelo"],
        "regla_base": metricas["regla_base"],
        "segmentos": [
            {
                "segmento": fila.segmento,
                "clientes": int(fila.clientes),
                "valor": round(float(fila.valor), 2),
            }
            for fila in segmentos.itertuples(index=False)
        ],
        "clientes": clientes.to_dict(orient="records"),
        "supuestos": {
            "margen": MARGEN,
            "costo_contacto": 2,
            "tasa_exito": 0.20,
            "texto": "El valor a 12 meses es las ventas del año previo al corte por un margen del 30 %. El costo de contacto (£2) y la tasa de éxito (20 %) son supuestos académicos.",
        },
    }
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    peso = SALIDA.stat().st_size / (1024 * 1024)
    print(f"Corte: {payload['fecha_corte']} | Clientes: {payload['clientes_analizados']:,} | Fuga: {payload['tasa_fuga']:.1%}")
    print(f"AUC modelo {metricas['modelo']['auc']:.3f} | AUC regla base {metricas['regla_base']['auc']:.3f}")
    print(f"Archivo {SALIDA} ({peso:.2f} MB)")
    if peso > 2:
        raise SystemExit("clientes.json superó 2 MB. Hay que reducir la lista antes de publicar.")


def agregar(antes: pd.DataFrame, corte: pd.Timestamp) -> pd.DataFrame:
    grupo = antes.groupby("cliente_id")
    tabla = grupo.agg(
        ultima_compra=("fecha", "max"),
        primera_compra=("fecha", "min"),
        frecuencia=("factura", "nunique"),
        valor_monetario=("ventas", "sum"),
        productos_distintos=("codigo_producto", "nunique"),
    ).reset_index()
    tabla["recencia"] = (corte - tabla["ultima_compra"]).dt.days
    tabla["antiguedad"] = (corte - tabla["primera_compra"]).dt.days
    tabla["ticket_promedio"] = tabla["valor_monetario"] / tabla["frecuencia"].clip(lower=1)
    return tabla


def quintil_mejor_si_menor(serie: pd.Series) -> pd.Series:
    """Quintil 5 = mejor. En recencia, menos días es mejor."""
    orden = serie.rank(method="first", ascending=True)
    return pd.qcut(orden, 5, labels=False) + 1


def quintil_mejor_si_mayor(serie: pd.Series) -> pd.Series:
    """Quintil 5 = mejor. En frecuencia y valor, más es mejor."""
    orden = serie.rank(method="first", ascending=False)
    return (pd.qcut(orden, 5, labels=False) + 1).astype(int)


def etiquetar(fila: pd.Series) -> str:
    # El orden importa: un cliente nuevo no se etiqueta como dormido por comprar poco.
    if fila["antiguedad"] <= 90 and fila["frecuencia"] <= 2:
        return "Nuevos"
    if fila["r"] >= 4 and fila["f"] >= 4 and fila["m"] >= 4:
        return "Campeones"
    if fila["f"] >= 4 and fila["m"] >= 3 and fila["r"] >= 3:
        return "Leales"
    if fila["r"] <= 2 and fila["m"] >= 4:
        return "En riesgo"
    if fila["r"] <= 2 and fila["f"] <= 2:
        return "Dormidos"
    return "Regulares"


def entrenar(tabla: pd.DataFrame):
    variables = ["recencia", "frecuencia", "valor_monetario", "antiguedad", "ticket_promedio", "productos_distintos"]
    x = tabla[variables]
    y = tabla["fuga"]
    x_ent, x_pru, y_ent, y_pru = train_test_split(
        x, y, test_size=0.25, random_state=SEMILLA, stratify=y
    )
    modelo = Pipeline(
        [
            ("escala", StandardScaler()),
            ("logistica", LogisticRegression(max_iter=500, random_state=SEMILLA)),
        ]
    )
    modelo.fit(x_ent, y_ent)
    proba = modelo.predict_proba(x_pru)[:, 1]
    pred = (proba >= 0.5).astype(int)

    # La regla base no mira el modelo: si lleva más de 90 días sin comprar, se da por fugado.
    recencia_prueba = x_pru["recencia"]
    pred_base = (recencia_prueba > 90).astype(int)
    metricas = {
        "modelo": {
            "auc": round(float(roc_auc_score(y_pru, proba)), 4),
            "precision": round(float(precision_score(y_pru, pred, zero_division=0)), 4),
            "sensibilidad": round(float(recall_score(y_pru, pred, zero_division=0)), 4),
        },
        "regla_base": {
            "nombre": "Fuga si la recencia es mayor a 90 días",
            "auc": round(float(roc_auc_score(y_pru, pred_base)), 4),
            "precision": round(float(precision_score(y_pru, pred_base, zero_division=0)), 4),
            "sensibilidad": round(float(recall_score(y_pru, pred_base, zero_division=0)), 4),
        },
    }
    # Las métricas salen del 25 % reservado. El puntaje que ve la gerencia se reentrena con todos.
    modelo.fit(x, y)
    return metricas, modelo


if __name__ == "__main__":
    main()
