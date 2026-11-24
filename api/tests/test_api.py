"""Verifica consultas seguras y que el optimizador respete el presupuesto.
Usa los dos Parquet reales creados por el pipeline.
"""
from fastapi.testclient import TestClient
from api.index import app, validar_sql

cliente = TestClient(app)

def test_validador_bloquea_operaciones_y_lecturas_externas():
    for sql in ("DROP TABLE ventas", "SELECT * FROM read_parquet('secreto')",
                "SELECT getenv('LLM_API_KEY')", "SELECT * FROM otra_tabla"):
        assert not validar_sql(sql)[0]
    valido, _, seguro = validar_sql("SELECT pais FROM ventas")
    assert valido and seguro.endswith("LIMIT 200")

def test_consulta_real():
    respuesta = cliente.post("/api/py/consulta", json={"modo": "predefinida", "id": "total"})
    assert respuesta.status_code == 200
    assert respuesta.json()["resultados"][0]["facturas"] == 39516

def test_optimizacion_no_excede_presupuesto():
    for presupuesto in (0, 10000):
        respuesta = cliente.post("/api/py/optimizar", json={"presupuesto": presupuesto})
        assert respuesta.status_code == 200
        datos = respuesta.json()
        assert datos["margen_optimo"] >= datos["margen_intuitivo"] - 0.02
        if presupuesto == 0:
            assert all(p["compra_optima"] == 0 for p in datos["productos"])
