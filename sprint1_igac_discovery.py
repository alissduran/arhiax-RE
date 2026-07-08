"""
Sprint 1 — Validacion IGAC vs AMB para Barranquilla
Y query de POT via miciudad.barranquilla.gov.co REST API
"""
import requests, json

print("=" * 70)
print("FASE A: Verificar si IGAC tiene predios de Barranquilla (cod 08001)")
print("=" * 70)

# IGAC FeatureServer - buscar por codigo_municipio = 08001 (Barranquilla)
BASE_IGAC = "https://services2.arcgis.com/RVvWzU3lgJISqdke/arcgis/rest/services/CATASTRO_PUBLICO_31032026/FeatureServer"

# Probar U_TERRENO (layer 7) filtrando por municipio Barranquilla
qurl = f"{BASE_IGAC}/7/query?where=codigo_municipio%3D%2708001%27&outFields=*&resultRecordCount=1&f=geojson"
try:
    r = requests.get(qurl, timeout=20)
    d = r.json()
    feats = d.get("features", [])
    if feats:
        print(f"  IGAC SI tiene Barranquilla! {len(feats)} feature(s)")
        props = feats[0].get("properties", {})
        for k, v in props.items():
            print(f"    {k}: {v}")
    else:
        print("  IGAC NO tiene predios de Barranquilla en U_TERRENO")
        # Intentar con codigo_departamento
        qurl2 = f"{BASE_IGAC}/7/query?where=CODIGO_DEPARTAMENTO%3D%2708%27&outFields=*&resultRecordCount=1&f=geojson"
        r2 = requests.get(qurl2, timeout=20)
        d2 = r2.json()
        feats2 = d2.get("features", [])
        if feats2:
            print(f"  Hay features con depto 08: {len(feats2)}")
            props = feats2[0].get("properties", {})
            for k, v in props.items():
                print(f"    {k}: {v}")
        else:
            print("  Tampoco por departamento 08 (Atlantico)")
except Exception as e:
    print(f"  Error: {e}")

print("\n" + "=" * 70)
print("FASE B: Servicios REST de miciudad.barranquilla.gov.co")
print("(Acceso directo via requests — puede fallar por Cloudflare)")
print("=" * 70)

BAQ_REST = "https://miciudad.barranquilla.gov.co/gis/rest/services"

# Intentar listar servicios
services_to_try = [
    ("Catastro", f"{BAQ_REST}/catastro/destinoseconomicos/MapServer?f=json"),
    ("Riesgos/Amenazas", f"{BAQ_REST}/riesgos/amenazas/MapServer?f=json"),
    ("Ordenamiento/POT", f"{BAQ_REST}/ordenamiento/planeacion/MapServer?f=json"),
    ("Ambiente", f"{BAQ_REST}/ambiente/areasproteccion/MapServer?f=json"),
]

for name, url in services_to_try:
    print(f"\n  {name}:")
    print(f"    URL: {url}")
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        if r.status_code == 200:
            ct = r.headers.get("content-type", "")
            if "json" in ct:
                d = r.json()
                if "layers" in d:
                    for l in d["layers"]:
                        print(f"    Layer {l['id']}: {l['name']}")
                elif "error" in d:
                    print(f"    Error: {d['error'].get('message','?')}")
            else:
                print(f"    Status 200 but content-type: {ct[:50]} (Cloudflare?)")
        elif r.status_code == 403:
            print(f"    403 FORBIDDEN (Cloudflare blocking)")
        else:
            print(f"    HTTP {r.status_code}")
    except Exception as e:
        print(f"    FAILED: {str(e)[:80]}")

print("\n" + "=" * 70)
print("FASE C: Verificar datos AMB (Area Metropolitana de Barranquilla)")
print("=" * 70)
# Buscar servicios del AMB en ArcGIS Online
try:
    search_url = "https://www.arcgis.com/sharing/rest/search?q=barranquilla+catastro+predios&f=json&num=10"
    r = requests.get(search_url, timeout=15)
    d = r.json()
    results = d.get("results", [])
    if results:
        for item in results[:5]:
            print(f"  {item.get('title','?')}")
            print(f"    Owner: {item.get('owner','?')}")
            print(f"    URL: {item.get('url','N/A')}")
            print(f"    Type: {item.get('type','?')}")
            print()
    else:
        print("  No results from ArcGIS Online search")
except Exception as e:
    print(f"  Error: {e}")
