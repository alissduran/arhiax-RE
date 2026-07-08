import math
import os
from PIL import Image, ImageDraw, ImageFont
from poi_engine import get_nearby_pois

def generate_maps(lat, lon, pois, output_png_path, output_html_path):
    """
    Genera un mapa estático (PNG) usando Pillow y un mapa interactivo (HTML) con Leaflet.js.
    """
    is_miramar = lat > 10.985
    inmueble_label = "Napoli (Inmueble)" if is_miramar else "Inmueble"
    inmueble_popup = "<b>Inmueble: Conjunto Residencial Napoli</b><br/>Tv 43 # 100-50" if is_miramar else "<b>Inmueble: Calle 63 #37-71</b><br/>Barrio El Recreo"

    # ── 1. GENERAR MAPA ESTÁTICO (Pillow) ──────────────────────────────────
    # Dimensiones de la imagen
    width, height = 1800, 1100
    cx, cy = width // 2, height // 2
    
    # Crear lienzo en blanco con fondo gris claro
    img = Image.new("RGBA", (width, height), "#F7F8FC")
    draw = ImageDraw.Draw(img)
    
    # Intentar cargar fuente Arial de Windows, si no usar default
    try:
        font_title = ImageFont.truetype("C:\\Windows\\Fonts\\arialbd.ttf", 36)
        font_labels = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 22)
        font_legend = ImageFont.truetype("C:\\Windows\\Fonts\\arialbd.ttf", 24)
        font_sub = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 20)
    except Exception:
        font_title = ImageFont.load_default()
        font_labels = ImageFont.load_default()
        font_legend = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        
    # Paleta de colores ARHIAX
    colors_dict = {
        "Salud": "#8B1A1A",       # Carmesí
        "Educacion": "#1A6B3A",   # Verde bosque
        "Comercio": "#D97D24",    # Ámbar/Naranja
        "Recreacion": "#1B4FAF"   # Azul medio
    }
    
    # Radio de 2000m mapeado a 450 píxeles
    scale = 450.0 / 2000.0
    
    # Dibujar círculos concéntricos de distancia
    distances = [500, 1000, 1500, 2000]
    for d in distances:
        r_px = int(d * scale)
        # Bounding box del círculo
        bbox = [cx - r_px, cy - r_px, cx + r_px, cy + r_px]
        draw.ellipse(bbox, outline="#D0D8E8", width=2)
        # Etiqueta de la distancia
        draw.text((cx, cy - r_px - 25), f"{d} m", fill="#718096", font=font_sub, anchor="md")
        
    # Dibujar el predio Napoli en el centro
    # Dibujar estrella dorada simple o rombo dorado
    r_center = 12
    draw.regular_polygon((cx, cy, r_center), 4, rotation=45, fill="#C9A84C", outline="#0D2C6B", width=3)
    draw.text((cx, cy + r_center + 15), inmueble_label, fill="#0D2C6B", font=font_legend, anchor="mt")
    
    # Trazar puntos de interés y asignar numeración secuencial
    poi_list = []
    poi_idx = 1
    for category, items in pois.items():
        color = colors_dict.get(category, "#555555")
        for item in items:
            poi_list.append((poi_idx, category, color, item))
            poi_idx += 1

    for idx, category, color, item in poi_list:
        # Pseudo-ángulo determinista basado en el hash del nombre
        angle = (hash(item["name"]) % 360) * (math.pi / 180.0)
        dist_m = item["distance"]
        
        dx = dist_m * scale * math.cos(angle)
        dy = dist_m * scale * math.sin(angle)
        
        px, py = int(cx + dx), int(cy + dy)
        
        # Dibujar el punto (un poco más grande para que quepa el número)
        draw.ellipse([px - 14, py - 14, px + 14, py + 14], fill=color, outline="#ffffff", width=2)
        
        # Dibujar el número adentro
        try:
            font_num = ImageFont.truetype("C:\\Windows\\Fonts\\arialbd.ttf", 16)
        except Exception:
            font_num = ImageFont.load_default()
        draw.text((px, py), str(idx), fill="#ffffff", font=font_num, anchor="mm")
            
    # Dibujar leyenda en la esquina superior izquierda (Categorías)
    lx, ly = 80, 80
    draw.rectangle([lx, ly, lx + 360, ly + 250], fill="#FFFFFFFC", outline="#0D2C6B", width=2)
    draw.text((lx + 20, ly + 15), "CATEGORÍAS", fill="#0D2C6B", font=font_legend)
    
    legend_items = [
        (inmueble_label, "#C9A84C", "diamond"),
        ("Salud", "#8B1A1A", "circle"),
        ("Educacion", "#1A6B3A", "circle"),
        ("Comercio", "#D97D24", "circle"),
        ("Recreacion", "#1B4FAF", "circle")
    ]
    
    ly_offset = ly + 65
    for text, col, shape in legend_items:
        if shape == "diamond":
            draw.regular_polygon((lx + 35, ly_offset + 10, 8), 4, rotation=45, fill=col, outline="#0D2C6B", width=2)
        else:
            draw.ellipse([lx + 27, ly_offset + 2, lx + 43, ly_offset + 18], fill=col, outline="#ffffff", width=1)
        draw.text((lx + 60, ly_offset), text, fill="#2D3748", font=font_labels)
        ly_offset += 35
        
    # Dibujar cuadro de POIs detallado en la derecha
    rx, ry = 1380, 80
    box_w, box_h = 360, 940
    draw.rectangle([rx, ry, rx + box_w, ry + box_h], fill="#FFFFFFFC", outline="#0D2C6B", width=2)
    draw.text((rx + 20, ry + 15), "EQUIPAMIENTOS (POIs)", fill="#0D2C6B", font=font_legend)
    
    ry_offset = ry + 65
    for idx, category, color, item in poi_list:
        # Dibujar circulito con el número
        draw.ellipse([rx + 20, ry_offset + 2, rx + 48, ry_offset + 30], fill=color, outline="#ffffff", width=1)
        try:
            font_num_leg = ImageFont.truetype("C:\\Windows\\Fonts\\arialbd.ttf", 16)
        except Exception:
            font_num_leg = ImageFont.load_default()
        draw.text((rx + 34, ry_offset + 16), str(idx), fill="#ffffff", font=font_num_leg, anchor="mm")
        
        # Dibujar texto de POI
        display_name = item["name"]
        if len(display_name) > 22:
            display_name = display_name[:20] + ".."
        
        text_line = f"{display_name}"
        dist_line = f"{category} - {int(item['distance'])} m"
        
        draw.text((rx + 65, ry_offset), text_line, fill="#2D3748", font=font_labels)
        draw.text((rx + 65, ry_offset + 22), dist_line, fill="#718096", font=font_sub)
        
        ry_offset += 58

    # Dibujar título principal
    draw.text((width // 2, 40), "Mapa de Equipamiento Urbano y POIs (Radio de 2.0 km)", fill="#0D2C6B", font=font_title, anchor="mt")
    
    # Guardar imagen PNG
    img.save(output_png_path, "PNG")
    
    # ── 2. GENERAR MAPA INTERACTIVE (HTML / Leaflet.js) ────────────────────────
    # Radio de la Tierra en metros por grado (aproximación local para Barranquilla)
    meters_per_lat = 111320.0
    meters_per_lon = 111320.0 * math.cos(math.radians(lat))
    
    markers_js = []
    markers_js.append(f"""
        L.marker([{lat}, {lon}], {{
            icon: L.divIcon({{
                className: 'custom-div-icon',
                html: "<div style='background-color:#C9A84C;width:15px;height:15px;border-radius:50%;border:2px solid #0D2C6B;box-shadow: 0 0 10px rgba(0,0,0,0.5);'></div>",
                iconSize: [15, 15],
                iconAnchor: [7.5, 7.5]
            }})
        }}).addTo(map).bindPopup(`{inmueble_popup}`).openPopup();
    """)
    
    for category, items in pois.items():
        color = colors_dict.get(category, "#555555")
        for item in items:
            angle = (hash(item["name"]) % 360) * (math.pi / 180.0)
            dist_deg_lat = (item["distance"] * math.sin(angle)) / meters_per_lat
            dist_deg_lon = (item["distance"] * math.cos(angle)) / meters_per_lon
            
            p_lat = lat + dist_deg_lat
            p_lon = lon + dist_deg_lon
            
            markers_js.append(f"""
                L.circleMarker([{p_lat}, {p_lon}], {{
                    radius: 7,
                    fillColor: '{color}',
                    color: '#ffffff',
                    weight: 1.5,
                    opacity: 1,
                    fillOpacity: 0.95
                }}).addTo(map).bindPopup("<b>{item['name']}</b><br/>Categoria: {category}<br/>Distancia: {int(item['distance'])} m");
            """)
            
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>ARHIAX - Mapa Interactivo de Equipamientos cercanos</title>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        body, html {{ margin: 0; padding: 0; width: 100%; height: 100%; font-family: 'Helvetica Neue', Arial, sans-serif; }}
        #map {{ width: 100%; height: 100%; }}
        .legend {{
            background: white; padding: 10px; line-height: 18px; color: #333; border-radius: 5px;
            box-shadow: 0 0 15px rgba(0,0,0,0.2); font-size: 12px;
        }}
        .legend i {{ width: 12px; height: 12px; float: left; margin-right: 8px; border-radius: 50%; opacity: 0.9; }}
        .header {{
            position: absolute; top: 10px; left: 50px; z-index: 1000; background: rgba(13, 44, 107, 0.9);
            color: white; padding: 5px 15px; border-radius: 4px; box-shadow: 0 0 10px rgba(0,0,0,0.3);
            pointer-events: none; font-size: 14px; font-weight: bold; letter-spacing: 0.5px;
        }}
    </style>
</head>
<body>
    <div class="header">A R H I A X — Mapa de Equipamiento Urbano (2.0 km)</div>
    <div id="map"></div>

    <script>
        var map = L.map('map').setView([{lat}, {lon}], 15);
        
        L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
            maxZoom: 19,
            attribution: '© OpenStreetMap contributors'
        }}).addTo(map);

        // Añadir círculo de 2km de referencia
        L.circle([{lat}, {lon}], {{
            color: '#1B4FAF',
            fillColor: '#1B4FAF',
            fillOpacity: 0.05,
            radius: 2000,
            dashArray: '5, 5',
            weight: 1.5
        }}).addTo(map);

        // Inyectar marcadores
        {"".join(markers_js)}

        // Leyenda
        var legend = L.control({{position: 'bottomright'}});
        legend.onAdd = function (map) {{
            var div = L.DomUtil.create('div', 'legend'),
                categories = ['Inmueble', 'Salud', 'Educacion', 'Comercio', 'Recreacion'],
                colors = ['#C9A84C', '#8B1A1A', '#1A6B3A', '#D97D24', '#1B4FAF'];

            div.innerHTML = '<b>Referencia</b><br>';
            for (var i = 0; i < categories.length; i++) {{
                div.innerHTML +=
                    '<i style="background:' + colors[i] + '"></i> ' +
                    categories[i] + '<br>';
            }}
            return div;
        }};
        legend.addTo(map);
    </script>
</body>
</html>
"""
    
    with open(output_html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    print(f"Mapas generados correctamente (Pillow):\n  PNG: {output_png_path}\n  HTML: {output_html_path}")
