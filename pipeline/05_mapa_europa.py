"""Genera una ilustración SVG de Europa a partir de Natural Earth 110m.
El mapa es geográfico; los importes interactivos se leen del pipeline de ventas.
"""
import json
from pathlib import Path
from urllib.request import urlopen

FUENTE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson"
SALIDA = Path(__file__).resolve().parent.parent / "public" / "mapa-europa.svg"

with urlopen(FUENTE, timeout=30) as respuesta:
    geo = json.load(respuesta)

def xy(punto):
    longitud, latitud = punto
    return ((longitud + 12) / 57 * 100, (72 - latitud) / 39 * 95)

def trazado(anillo):
    pares = [xy(p) for p in anillo]
    if not pares:
        return ""
    return "M" + " ".join(f"{x:.2f},{y:.2f}" for x, y in pares) + "Z"

formas = []
for pais in geo["features"]:
    geometria = pais.get("geometry") or {}
    if geometria.get("type") == "Polygon":
        poligonos = [geometria["coordinates"]]
    elif geometria.get("type") == "MultiPolygon":
        poligonos = geometria["coordinates"]
    else:
        continue
    for poligono in poligonos:
        if not poligono:
            continue
        anillo = poligono[0]
        if any(-12 <= p[0] <= 45 and 33 <= p[1] <= 72 for p in anillo):
            formas.append(f'<path d="{trazado(anillo)}"/>')

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 95" preserveAspectRatio="xMidYMid meet">
<!-- Natural Earth 110m countries, public domain: https://www.naturalearthdata.com/about/terms-of-use/ -->
<rect width="100" height="95" fill="#eaf2f6"/>
<g fill="#c4d7e1" stroke="#eaf2f6" stroke-width=".35" stroke-linejoin="round">{"".join(formas)}</g>
</svg>'''
SALIDA.write_text(svg, encoding="utf-8")
print(f"{SALIDA.name}: {len(formas)} polígonos, {SALIDA.stat().st_size:,} bytes")
