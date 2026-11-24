"""Recorre filtros y vistas en Chrome local para verificar la interacción.
La captura móvil ayuda a revisar el diseño adaptable.
"""
from pathlib import Path
import os
from playwright.sync_api import sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
URL = os.getenv("TABLERO_URL", "http://localhost:3000")

with sync_playwright() as playwright:
    navegador = playwright.chromium.launch(executable_path=CHROME, headless=True)
    pagina = navegador.new_page(viewport={"width": 1440, "height": 900})
    pagina.goto(URL, wait_until="networkidle")
    pagina.get_by_text("£ 19,645,617.79").wait_for()
    pagina.screenshot(path=str(RAIZ / "vista-inicio.png"), full_page=False)
    pagina.get_by_label("País", exact=True).select_option("Germany")
    pagina.get_by_text("Germany ·").first.wait_for()
    assert pagina.get_by_text("£ 19,645,617.79").count() == 0
    pagina.get_by_label("Año", exact=True).select_option("2011")
    pagina.get_by_label("Mes", exact=True).select_option("2011-10")
    assert "2011-10" in pagina.locator("main").inner_text()
    pagina.get_by_role("button", name="Limpiar filtros").click()
    pagina.get_by_role("button", name="Unidades").click()
    pagina.locator("section").filter(has_text="Top 10 productos").get_by_role("button").nth(2).click()
    pagina.get_by_role("button", name="Ver en Demanda").click()
    pagina.get_by_text("Validación temporal").wait_for()
    pagina.get_by_role("button", name="Clientes").click()
    pagina.get_by_text("Simulador de retención").wait_for()
    pagina.get_by_role("button", name="Gobierno").click()
    pagina.get_by_text("Ficha de datos").wait_for()
    pagina.get_by_role("button", name="Inicio").click()
    pagina.get_by_role("button", name="Pregúntale al Copiloto").click()
    pagina.get_by_role("button", name="¿Cuáles son los productos líderes?").click()
    assert "Dato observado" in pagina.locator("section").last.inner_text()
    pagina.get_by_role("button", name="Cerrar").click()
    pagina.get_by_role("button", name="Reposición").click()
    pagina.get_by_role("button", name="Calcular plan").click()
    pagina.get_by_text("Margen óptimo").wait_for()
    pagina.locator("main").screenshot(path=str(RAIZ / "vista-reposicion.png"))
    pagina.get_by_role("button", name="Pregúntale a tus datos").click()
    pagina.get_by_role("button", name="¿Cuánto vendimos en total?").click()
    pagina.get_by_text("19645617.79").wait_for()
    movil = navegador.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=1)
    movil.goto(URL, wait_until="networkidle")
    movil.screenshot(path=str(RAIZ / "vista-movil.png"), full_page=True)
    if not movil.evaluate("document.documentElement.scrollWidth <= window.innerWidth"):
        print(movil.evaluate("({ancho:innerWidth,documento:document.documentElement.scrollWidth,elementos:[...document.querySelectorAll('*')].filter(x=>x.getBoundingClientRect().right>innerWidth+1).slice(0,8).map(x=>({etiqueta:x.tagName,clase:x.className?.baseVal||x.className,derecha:x.getBoundingClientRect().right}))})"))
        raise AssertionError("Desbordamiento horizontal en celular")
    print("Filtros, asistente, reposición, SQL y diseño móvil: correctos")
    navegador.close()
