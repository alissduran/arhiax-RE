import asyncio
import os
import sys
from pathlib import Path

# Asegurar que playwright esté disponible antes de importar
try:
    from playwright.async_api import async_playwright
except ImportError:
    # Fallback si no está instalado aún
    async_playwright = None

# URL de Escena 3D por defecto de Barranquilla (volumetría y sombras de ArcGIS Online)
DEFAULT_SCENE_URL = "https://www.arcgis.com/home/webscene/viewer.html?webscene=8c30467b36f74a3891823eb29e614d3f"

def actualizar_bd_sombra(case_id: int, columna: str):
    if case_id == 0:
        return
    import sqlite3
    try:
        # Resolver ruta del proyecto relativa para importar database de forma segura
        API_DIR = os.path.dirname(os.path.abspath(__file__))
        DB_PATH = os.path.join(API_DIR, "database.db")
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute(f"UPDATE dictamenes SET {columna} = 1 WHERE id = ?", (case_id,))
        conn.commit()
        conn.close()
        print(f"  [DB] Columna {columna} marcada como cargada para Caso #{case_id}")
    except Exception as e:
        print(f"  [ERROR DB] No se pudo actualizar {columna} en SQLite: {e}")

async def capturar_sombras_playwright(lat: float, lon: float, case_id: int, output_dir: str, scene_url: str = None):
    """
    Automatiza la navegación, traslación de cámara y captura de sombras 3D 
    a las 9:00 AM y 3:00 PM usando Playwright.
    """
    if not async_playwright:
        print("[ERROR] Playwright no está instalado en este entorno.")
        return False

    if not scene_url:
        scene_url = DEFAULT_SCENE_URL

    print(f"[ARHIAX Solar Engine] Iniciando captura automática de sombras para Caso #{case_id}...")
    print(f"  Coordenadas: Latitud {lat}, Longitud {lon}")
    print(f"  Escena Base: {scene_url}")

    os.makedirs(output_dir, exist_ok=True)
    sombra_9am_path = os.path.join(output_dir, "sombra_9am.png")
    sombra_3pm_path = os.path.join(output_dir, "sombra_3pm.png")

    async with async_playwright() as p:
        # Iniciar navegador en segundo plano
        browser = await p.chromium.launch(headless=True)
        # Configurar un viewport grande para obtener imágenes de alta calidad
        page = await browser.new_page(viewport={"width": 1600, "height": 1000})

        try:
            # 1. Cargar la URL de la escena
            await page.goto(scene_url, wait_until="networkidle", timeout=60000)
            
            # Esperar a que el contenedor de la vista 3D (WebGL canvas) esté cargado
            await page.wait_for_selector(".esri-view-surface", timeout=60000)
            await asyncio.sleep(6) # Esperar renderizado inicial de capas

            # 2. Inyectar comando JavaScript para centrar la cámara en las coordenadas del predio
            # La mayoría de visores estándar de ArcGIS Online exponen la variable global 'view' o 'mapView'
            js_center_camera = f"""
                (async () => {{
                    // Intentar recuperar la instancia de view desde el objeto global o desde el DOM
                    let view = window.view || window.mapView;
                    if (!view) {{
                        const esriSurface = document.querySelector('.esri-view-surface');
                        if (esriSurface && esriSurface.__view) {{
                            view = esriSurface.__view;
                        }}
                    }}
                    
                    if (view) {{
                        // Ir a las coordenadas exactas del inmueble con zoom a escala de predio
                        await view.goTo({{
                            center: [{lon}, {lat}],
                            zoom: 18,
                            tilt: 45
                        }}, {{ duration: 2000 }});
                        return true;
                    }}
                    return false;
                }})();
            """
            
            camera_moved = await page.evaluate(js_center_camera)
            if not camera_moved:
                print("  [Advertencia] No se pudo acceder directamente al API JS de ArcGIS. Intentando navegación alternativa por query params...")
                # Alternativa: recargar el visor pasando parámetros de coordenadas en la URL si el API no se expone
                coords_url = f"{scene_url}&find={lon},{lat}"
                await page.goto(coords_url, wait_until="networkidle", timeout=60000)
                await page.wait_for_selector(".esri-view-surface", timeout=60000)
                await asyncio.sleep(6)

            # 3. Función auxiliar para cambiar la iluminación y tomar screenshots
            async def tomar_captura_hora(hora_militar: int, target_path: str):
                js_set_time = f"""
                    (() => {{
                        let view = window.view || window.mapView;
                        if (!view) {{
                            const esriSurface = document.querySelector('.esri-view-surface');
                            if (esriSurface && esriSurface.__view) {{
                                view = esriSurface.__view;
                            }}
                        }}
                        if (view && view.environment) {{
                            // Fijar fecha de análisis (ej: Julio 11) a la hora correspondiente
                            view.environment.lighting.date = new Date(2026, 6, 11, {hora_militar}, 0, 0);
                            view.environment.lighting.directShadowsEnabled = true;
                            view.environment.lighting.ambientOcclusionEnabled = true;
                            return true;
                        }}
                        return false;
                    }})();
                """
                await page.evaluate(js_set_time)
                await asyncio.sleep(4) # Esperar a que se proyecten las sombras
                # Tomar captura solo del canvas 3D
                await page.locator(".esri-view-surface").screenshot(path=target_path)
                print(f"  [Sombras] Captura guardada a las {hora_militar}:00 en: {target_path}")

            # Captura 9:00 AM (Luz Este/Mañana)
            await tomar_captura_hora(9, sombra_9am_path)
            actualizar_bd_sombra(case_id, "sombra_9am_cargada")
            
            # Captura 3:00 PM (Luz Oeste/Tarde)
            await tomar_captura_hora(15, sombra_3pm_path)
            actualizar_bd_sombra(case_id, "sombra_3pm_cargada")

            return True

        except Exception as e:
            print(f"[ERROR] Excepción durante la automatización de sombras: {e}")
            return False
            
        finally:
            await browser.close()

if __name__ == "__main__":
    # Test rápido si se ejecuta como script
    if len(sys.argv) >= 3:
        lat_t = float(sys.argv[1])
        lon_t = float(sys.argv[2])
        asyncio.run(capturar_sombras_playwright(lat_t, lon_t, 0, "./test_output"))
    else:
        # Coordenadas por defecto de Miramar
        asyncio.run(capturar_sombras_playwright(10.9875, -74.8115, 0, "./test_output"))
