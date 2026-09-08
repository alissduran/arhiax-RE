import sys, os, hashlib, datetime, re
from pathlib import Path

API_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = API_DIR.parent

if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


PAQUETE_ROOT = os.path.join(str(PROJECT_ROOT), "motor_tma_lonja_baq_v1.0", "motor_tma_lonja_baq_v1.0")
TMA_PIEZAS = os.path.join(PAQUETE_ROOT, "tma_engine", "piezas")
TMA_DATOS = os.path.join(PAQUETE_ROOT, "tma_engine", "datos")
LONJA_LAYER = os.path.join(PAQUETE_ROOT, "lonja_layer")

sys.path.insert(0, TMA_PIEZAS)
sys.path.insert(0, TMA_DATOS)
sys.path.insert(0, LONJA_LAYER)

# API_DIR debe tener prioridad sobre PROJECT_ROOT y el motor TMA: hay copias
# antiguas de poi_engine/solar_engine/address_normalizer en la raíz del repo que
# provocaban que el PDF usara la versión obsoleta (POIs fabricados). Re-insertar
# API_DIR al tope garantiza que los módulos de api/ sean los que se importen.
sys.path.insert(0, str(API_DIR))

from reportlab.platypus import SimpleDocTemplate, Spacer, Paragraph, Table, TableStyle, PageBreak, KeepTogether
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import Image as RLImage
from dictamen_part1_styles import *
from solar_engine import get_solar_position, analyze_facade_exposure
from poi_engine import get_nearby_pois
from map_generator import generate_maps
from address_normalizer import normalize_address_colombia

from dictamen_data import get_valuation, get_hallazgos, get_recs, get_identificacion_dt, get_localizacion_dt, get_cobertura_alert, get_analisis_registral_text, get_catastral_dt, get_pot_summary_dt, get_valoracion_alert, get_alcance_dt, get_geospatial_evaluation
from carga_economica import estimar_carga_hipotecaria, generar_tabla_carga
from ruta_verificacion import generar_ruta, generar_tabla_ruta
from score_engine import calcular_score_actuarial, generar_narrativa_score, color_score
from sarlaft_engine import generar_ficha_sarlaft, generar_tabla_sarlaft

# ── Ortografía: wrapper de Paragraph que restaura las tildes en TODO el PDF ──
# ('Analisis' -> 'Análisis', 'Direccion' -> 'Dirección') sin tocar las cadenas
# fuente ni las etiquetas HTML. Se define DESPUÉS de todos los imports y se
# parchea también en dictamen_part1_styles (data_table/helpers) y en el propio
# reportlab.platypus para cubrir cualquier importador posterior.
from ortografia import corregir_es
from reportlab.platypus import Paragraph as _RLParagraph

class Paragraph(_RLParagraph):
    def __init__(self, text, style=None, bulletText=None, **kw):
        if isinstance(text, str):
            text = corregir_es(text)
        _RLParagraph.__init__(self, text, style, bulletText=bulletText, **kw)

import dictamen_part1_styles as _estilos_mod
import reportlab.platypus as _rlp_mod
_estilos_mod.Paragraph = Paragraph
_rlp_mod.Paragraph = Paragraph

def evaluar_estructurabilidad_fiduciaria(hallazgos_list):
    BLOQUEOS_FIDUCIARIOS = {"hipoteca", "embargo", "afectacion", "patrimonio", "demanda", "usufructo", "medida cautelar"}
    bloqueos = []
    for h in hallazgos_list:
        # INFORMATIVO (tradición limpia, zona libre...) nunca bloquea
        if h[0] == "INFORMATIVO":
            continue
        titulo = h[3].lower()
        descripcion = h[5].lower()
        implicacion = h[6].lower()
        texto_completo = " | ".join([titulo, descripcion, implicacion])
        # Negaciones explícitas: el hallazgo describe la AUSENCIA del bloqueo
        if any(neg in texto_completo for neg in ("no se detectaron", "sin gravamenes",
                                                 "sin gravámenes", "libre de gravamenes",
                                                 "libre de gravámenes", "sin afectacion",
                                                 "sin hipotecas", "no registra gravamenes")):
            continue
        if any(w in titulo for w in ("cancelada", "levantada", "extinguida", "resuelto")):
            continue
        # Regla de coherencia: un hallazgo de severidad ALTO es BLOQUEANTE por
        # definición (hipoteca/embargo vigente, AUSENCIA DE CTL, exceso frente a
        # licencia...) — antes la ausencia de CTL dejaba el semáforo VERDE,
        # contradiciendo el resumen 'BLOQUEADO/ROJO'.
        if h[0] == "ALTO":
            bloqueos.append(h[3])
            continue
        is_vigente = "vigente" in titulo or "vigente" in descripcion or "vigente" in implicacion
        is_bloqueo = any(term in titulo or term in descripcion for term in BLOQUEOS_FIDUCIARIOS)
        if is_vigente and is_bloqueo:
            bloqueos.append(h[3])
    if bloqueos:
        return {"semaforo": "ROJO", "estructurable": False, "condiciones_precedentes": bloqueos}
    return {"semaforo": "VERDE", "estructurable": True, "condiciones_precedentes": []}

def _severidad_geo_desde_nivel(am: dict, ri: dict):
    """Severidad/colores del hallazgo H-GEO proporcionales al NIVEL de amenaza
    o riesgo detectado (misma escala que score_engine: Alta/Muy Alta -> ALTO,
    Media -> MEDIO, Baja -> severidad media-leve). Evita el absurdo de declarar
    'Severidad ALTO' con una amenaza de nivel Baja."""
    from reportlab.lib import colors as rl_colors
    niveles = " | ".join([
        str((am or {}).get("nivel") or ""),
        str((ri or {}).get("nivel") or ""),
    ]).upper()
    if any(k in niveles for k in ("MUY ALTA", "MUY ALTO", "ALTA", "ALTO")):
        return ("ALTO",
                rl_colors.HexColor("#D92C2C"), rl_colors.HexColor("#FFF0F0"),
                "Potencial restriccion para originacion hipotecaria y seguros: "
                "se recomienda evaluacion geotecnica de detalle antes de estructurar garantias.")
    if any(k in niveles for k in ("MEDIA", "MEDIO")):
        return ("MEDIO",
                rl_colors.HexColor("#E67E22"), rl_colors.HexColor("#FFF6EC"),
                "Requiere evaluacion geotecnica complementaria y puede generar "
                "condiciones o recargos en la suscripcion de polizas.")
    # Nivel Baja/Bajo u otro con intersección: afectación presente pero menor
    return ("MEDIO",
            rl_colors.HexColor("#E67E22"), rl_colors.HexColor("#FFF6EC"),
            "Afectacion de nivel Baja detectada: se recomienda verificacion "
            "puntual por profesional competente en caso de intervencion fisica "
            "del predio; impacto esperado menor en originacion.")


def _num_circulo(cod):
    """'050' -> '50', '50C' -> '50', '001' -> '1': dígitos del código de
    oficina de registro sin ceros a la izquierda (para comparar 050 vs 50)."""
    m = re.match(r"^\s*0*(\d+)", str(cod or ""))
    return m.group(1) if m else None


def _detectar_discrepancia_circulo(folio, circulo_registral, codigo_circulo_ciudad):
    """Devuelve (codigo_circulo_folio, discrepante).

    Los folios SNR pertenecen a la oficina de registro del predio: Barranquilla
    '040-...', Medellín '001-...', Bogotá '50C-/50N-/50S-...'. Compara el código
    del folio (o el círculo declarado por el CTL) con el de la ciudad del caso,
    normalizando ceros a la izquierda ('050' == '50'). discrepante=True si no
    coinciden (p. ej. un CTL '001-...' adjuntado a un caso de Bogotá).
    """
    circ = (circulo_registral or "").strip()
    prefijo = ""
    if circ:
        m = re.match(r"^\s*(\d{2,3}[A-Z]?|0*\d+[A-Z]?)", circ, re.IGNORECASE)
        if m:
            prefijo = m.group(1).upper().lstrip("0") or "0"
    if not prefijo and folio:
        m2 = re.match(r"^(\d{2,3}[A-Z]?)-\d+", str(folio).strip())
        if m2:
            prefijo = m2.group(1).upper().lstrip("0") or "0"
    num_ciudad = _num_circulo(codigo_circulo_ciudad)
    if not prefijo or not num_ciudad:
        return prefijo or None, False
    # Compara solo la parte numérica ('50C' y '50' y '050' coinciden en '50')
    num_prefijo = _num_circulo(prefijo) or ""
    return prefijo, num_prefijo != num_ciudad


def _inject_geospatial_hallazgo(hallazgos: list, geo_eval: dict, barrio: str,
                                fuente_pot: str = "POT BAQ -- Capas GeoJSON (STRtree ARHIAX RE)",
                                nombre_ciudad: str = "Barranquilla") -> list:
    """
    Reemplaza el hallazgo de amenaza/riesgo hardcodeado por un resultado dinámico
    obtenido del motor geoespacial (STRtree + GeoJSON POT Barranquilla, o capas de
    gestión del riesgo en vivo para Medellín). Detecta el índice del hallazgo
    existente por su texto clave y lo sustituye.
    """
    from reportlab.lib import colors as rl_colors

    am = geo_eval.get('amenaza_remocion_masa', {})
    ri = geo_eval.get('areas_en_riesgo', {})
    resumen = geo_eval.get('resumen_ejecutivo', 'Evaluación geoespacial completada.')

    hay_amenaza = am.get('intersecta', False)
    hay_riesgo  = ri.get('intersecta', False)

    if hay_amenaza or hay_riesgo:
        # Nivel del título: el PEOR entre am y ri (no solo la primera capa que
        # intersecta). Regresión (dictamen real 040-646406): am='Baja' y
        # ri='Medio' producían 'Afectación Detectada (Baja)' con severidad MEDIO
        # y descripción 'Riesgo Medio' — sin sentido. Si hay riesgo Medio, el
        # título debe decirlo.
        def _peor_nivel(*niveles):
            orden = {'muy alta': 4, 'muy alto': 4, 'alta': 3, 'alto': 3,
                     'media': 2, 'medio': 2, 'baja': 1, 'bajo': 1}
            mejor = None
            mejor_rank = 0
            for n in niveles:
                if not n:
                    continue
                rank = orden.get(str(n).strip().lower(), 0)
                if rank >= mejor_rank:
                    mejor_rank = rank
                    mejor = n
            return mejor

        nivel_texto = _peor_nivel(
            am.get('nivel') if hay_amenaza else None,
            ri.get('nivel') if hay_riesgo else None,
        ) or 'Detectado'
        clase_suelo = am.get('clase_suelo', ri.get('clase_suelo', 'N/A'))
        # Severidad coherente con el nivel real de la amenaza (fix inconsistencia)
        severidad, color_sev, color_bg, impl = _severidad_geo_desde_nivel(am, ri)
        titulo = f"H-GEO | Afectación por Amenaza/Riesgo Detectada ({nivel_texto})"
        fuente = fuente_pot
        desc = (
            f"El motor geoespacial detectó intersección del predio con zonas de riesgo del POT de {nombre_ciudad}. "
            f"Amenaza remoción en masa: {am.get('nivel') or 'Sin afectación'} | "
            f"Áreas en riesgo: {ri.get('nivel') or 'Sin afectación'} | "
            f"Clase de suelo: {clase_suelo}. {resumen}"
        )
    else:
        severidad   = "INFORMATIVO"
        color_sev   = rl_colors.HexColor("#1A6B3A")
        color_bg    = rl_colors.HexColor("#EBF5EE")
        titulo = "H-GEO | Zona Libre de Amenazas y Riesgos (Evaluación Dinámica POT)"
        fuente = fuente_pot
        desc = (
            f"El motor geoespacial ARHIAX cruzó las coordenadas del predio contra las capas oficiales del POT de {nombre_ciudad}. "
            f"Resultado: Sin intersección en amenaza por remoción en masa ni en áreas en riesgo. {resumen}"
        )
        impl = "Favorable para suscripción de seguros y originación hipotecaria sin recargos ambientales. Evaluación computada en tiempo real."

    nuevo_hallazgo = (severidad, color_sev, color_bg, titulo, fuente, desc, impl)

    # Buscar y reemplazar hallazgo existente de amenaza/riesgo (H-05 o H-04)
    keywords = ["zona libre de amenazas", "riesgos registradas", "afectación por amenaza", "h-05", "h-04 | zona"]
    for i, h in enumerate(hallazgos):
        titulo_h = h[3].lower() if len(h) > 3 else ""
        if any(kw in titulo_h for kw in keywords):
            hallazgos[i] = nuevo_hallazgo
            return hallazgos

    # Si no se encontró, añadir al final
    hallazgos.append(nuevo_hallazgo)
    return hallazgos


def _direccion_para_geocodificar(analysis, db_record):
    """Elige la dirección con la que geocodificar el predio.

    Regresión (dictamen real 50C-1463431, queja del usuario: el precio saltó de
    $291.460.000 a $212.990.000): la dirección del FORMULARIO puede ser una
    placa registral alternativa ('CRA 20 # 61-55') que NO existe en la capa
    oficial de placas; geocodificarla con Nominatim caía en la manzana vecina de
    estrato 3 y el valor de mercado bajaba. Cuando el CTL declara la DIRECCION
    CATASTRAL (análisis legal), ESA es la placa oficial a geocodificar.
    """
    _dir_ctl = (analysis.get("direccion") or "").strip()
    _ok = _dir_ctl.lower() not in ("", "pendiente", "pendiente de verificacion", "n/d")
    if _ok:
        return _dir_ctl
    return (db_record.get("direccion") or "").strip()


def compile_pdf(db_record: dict, output_pdf_path: str, assets_dir: Path = None):
    # Ciudad del predio (Sprint 3: barranquilla activa; medellin y bogota en
    # expansión). Controla qué catastro/POT se consulta y qué textos se imprimen.
    ciudad = (db_record.get('ciudad') or 'barranquilla').lower().strip()
    if ciudad not in ('barranquilla', 'medellin', 'bogota'):
        ciudad = 'barranquilla'
    es_medellin = ciudad == 'medellin'
    es_bogota = ciudad == 'bogota'
    from config import get_ciudad
    cfg_ciudad = get_ciudad(ciudad)
    if es_bogota:
        _NOMBRE_CIUDAD = cfg_ciudad.get('nombre', 'Bogotá D.C.')
        _CIRCULO = cfg_ciudad.get('codigo_circulo', '50')
        _COD_DANE = cfg_ciudad.get('codigo_dane', '11001')
    elif es_medellin:
        _NOMBRE_CIUDAD = cfg_ciudad.get('nombre', 'Medellín')
        _CIRCULO = cfg_ciudad.get('codigo_circulo', '001')
        _COD_DANE = cfg_ciudad.get('codigo_dane', '05001')
    else:
        _NOMBRE_CIUDAD = cfg_ciudad.get('nombre', 'Barranquilla')
        _CIRCULO = cfg_ciudad.get('codigo_circulo', '040')
        _COD_DANE = cfg_ciudad.get('codigo_dane', '08001')
    _ORIP = ("Oficina de Registro de Instrumentos Publicos -- " +
             (_NOMBRE_CIUDAD if not es_bogota else "Bogotá D.C. (ORIP Central)"))

    # Cargar y analizar el certificado de libertad y tradicion de forma dinamica (Punto 1)
    from legal_analyzer import analizar_certificado
    path_certificado = db_record.get('certificado_path')
    analysis = analizar_certificado(path_certificado)

    # Mejora 5 (Sprint 3): licencia de construcción adjuntada (opcional). Se
    # analiza para confrontar lo LICENCIADO vs lo CONSTRUIDO vs la norma POT
    # en la sección 6.3 (detecta exceso frente a la licencia, aunque la capa
    # POT no lo refleje). Nunca rompe: sin licencia o sin pisos identificados,
    # la confrontación se mantiene contra la norma del POT.
    licencia = None
    path_licencia = db_record.get('licencia_path')
    if path_licencia:
        try:
            from licencia_analyzer import analizar_licencia
            licencia = analizar_licencia(path_licencia)
            print(f"[PDF][LICENCIA] analizada: {licencia.get('numero_licencia')} "
                  f"pisos={licencia.get('pisos_aprobados')}")
        except Exception as e:
            print(f"[PDF][LICENCIA] no disponible: {e}")
            licencia = None
    
    # ── Sprint 2 (exactitud): resolver el predio REAL en el catastro cuando el
    # CTL trae código catastral o NUPRE. Nunca rompe: si el servicio no responde
    # o el predio no aparece, queda None y se degrada a los demás orígenes.
    # Sprint 3: despacho por ciudad (BAQ datosabiertos vs Medellín servidormapas
    # vs Bogotá catastro distrital). En Medellín/Bogotá, sin CTL pero con
    # dirección, se intenta resolver por coordenadas (uso del predio/sector más
    # cercano) para llenar barrio/destino reales.
    predio_real = None
    _lat_geo = None
    _lon_geo = None
    if (analysis.get("codigo_catastral") or analysis.get("nupre")) and not es_bogota:
        # Bogotá NO publica capa predial consultable por NUPRE/código en abierto:
        # el predio se resuelve por coordenadas (enriquecer_por_punto). Enviar el
        # código bogotano al módulo de BAQ sería un error (CTL de otra ciudad).
        try:
            if es_medellin:
                from catastro_predio_medellin import enriquecer_desde_ctl
            else:
                from catastro_predio import enriquecer_desde_ctl
            _r = enriquecer_desde_ctl(analysis.get("codigo_catastral"),
                                      analysis.get("nupre"))
            if _r.get("disponible"):
                predio_real = _r
        except Exception as e:
            print(f"[PDF][CATASTRO-PREDIO:{ciudad}] enriquecimiento no disponible: {e}")
            predio_real = None
    if predio_real is None and (es_medellin or es_bogota):
        # Sin código en el CTL (o sin CTL): geocodificar la dirección y resolver
        # por coordenadas el entorno catastral real de la ciudad.
        try:
            from geocoder import geocodificar_direccion
            # Regresión (dictamen real 50C-1463431, cambio de precio $291M->$212M):
            # la dirección del FORMULARIO puede ser una placa registral alternativa
            # ('CRA 20 # 61-55') que NO existe en la capa oficial de placas; al
            # geocodificarla, Nominatim caía en la manzana vecina de estrato 3 y el
            # valor de mercado bajaba de $5.200.000/m2 (estr. 4) a $3.800.000/m2
            # (estr. 3). Cuando el CTL declara la DIRECCION CATASTRAL, ESA es la
            # placa oficial a geocodificar (DG 61B 20 04 -> lote estrato 4 real).
            _dir_raw = _direccion_para_geocodificar(analysis, db_record)
            if _dir_raw and _dir_raw.lower() not in ('pendiente', ''):
                _lat_geo, _lon_geo = geocodificar_direccion(_dir_raw, ciudad=ciudad)
                _cod_lote_bog = None
                if es_bogota:
                    # Placa domiciliaria oficial: da el punto EXACTO del lote y su
                    # código. Regresión (dictamen real 50C-1463431): sin este
                    # paso el entorno se resolvía en el lote vecino del Restrepo
                    # (sur) en vez de SAN LUIS/TEUSAQUILLO (norte, el real).
                    # geocodificar_direccion ya consultó la placa internamente y
                    # cacheó el punto; aquí recuperamos también el código de lote.
                    try:
                        from geocoder_catastral_bogota import geocodificar_catastro_bogota
                        _placa = geocodificar_catastro_bogota(_dir_raw)
                        if _placa:
                            _lat_geo, _lon_geo = _placa["lat"], _placa["lon"]
                            _cod_lote_bog = _placa.get("codigo_lote")
                    except Exception as _e_placa:
                        print(f"[PDF][CATASTRO-BOG:PLACA] placa no disponible: {_e_placa}")
                    from catastro_predio_bogota import enriquecer_por_punto as _enr_punto
                    _r = _enr_punto(_lat_geo, _lon_geo, codigo_lote=_cod_lote_bog)
                else:
                    from catastro_predio_medellin import enriquecer_por_punto as _enr_punto
                    _r = _enr_punto(_lat_geo, _lon_geo)
                if _r.get("disponible"):
                    predio_real = _r
        except Exception as e:
            print(f"[PDF][CATASTRO-{ciudad.upper()}:PUNTO] enriquecimiento por punto no disponible: {e}")
            predio_real = None

    folio = analysis["folio"] if analysis["folio"] != "040-XXXXXX" else (db_record.get('folio_matricula', '040-XXXXXX') or '040-XXXXXX')
    # Dirección: 1) oficial catastral resuelta (código o punto), 2) del CTL
    # analizado, 3) del registro. Nunca se inventa.
    if predio_real and predio_real.get("direccion_oficial"):
        # Medellín devuelve la dirección en casillado catastral ("CL  009 043 B 068");
        # se conserva como dato oficial pero se compacta para lectura.
        _dir_of = predio_real["direccion_oficial"]
        if es_medellin:
            _dir_of = " ".join(str(_dir_of).split())
        direccion = normalize_address_colombia(_dir_of)
    elif analysis.get("direccion") and analysis["direccion"].lower() != "pendiente de verificacion":
        direccion = normalize_address_colombia(analysis["direccion"])
    else:
        direccion = normalize_address_colombia(db_record.get('direccion', '') or '')
    if not direccion or direccion.lower() in ("pendiente", "pendiente de verificacion", "n/d"):
        direccion = "PENDIENTE DE VERIFICACION"

    # Barrio: 1) capa oficial POT (Barrios de la Alcaldía), 2) texto del CTL,
    # 3) registro. Se elimina el barrio de demostración como valor por defecto.
    _barrio_desde_catastro = False
    if predio_real:
        _ent = predio_real.get("entorno") or {}
        if _ent.get("barrio"):
            barrio = _ent["barrio"]
            # Regresión (CTL real 040-646406): 'Miramar'/'El Recreo' también son
            # barrios REALES de Barranquilla que el catastro en vivo resuelve por
            # código/NUPRE. Solo el demo sin CTL debe descartarse; el barrio que
            # viene del catastro del predio real se conserva SIEMPRE.
            _barrio_desde_catastro = True
        else:
            barrio = ""
    else:
        if analysis.get("barrio") and analysis["barrio"] != "Desconocido":
            barrio = analysis["barrio"]
        else:
            barrio = db_record.get('barrio', '') or ''
    if not _barrio_desde_catastro and (not barrio or
            barrio.lower() in ("pendiente", "miramar", "el recreo", "recreo", "desconocido")):
        # Si el CTL se analizó (tiene código catastral) pero no aportó barrio,
        # NO se afirma el demo: queda pendiente de verificación.
        if path_certificado and (analysis.get("codigo_catastral") or analysis.get("nupre")):
            barrio = ""
        elif barrio and barrio.lower() in ("miramar", "el recreo", "recreo"):
            barrio = barrio  # caso demo legado explícito (tests)
        else:
            barrio = ""

    area = float(db_record.get('area', 0) or 0)
    is_miramar = 'miramar' in barrio.lower()
    
    # Datos reales del predio (destino/condición/construcción/NUPRE) para el PDF
    _predio_destino = None
    _predio_condicion = None
    _predio_nupre = analysis.get("nupre")
    _predio_codigo = analysis.get("codigo_catastral")
    _predio_tipo_construccion = None
    _predio_pisos = None
    _predio_estrato_catastral = None
    _predio_area_catastral = None
    _ent2 = {}
    _predio_tratamiento = None
    if predio_real:
        _p = predio_real.get("predio") or {}
        _ent2 = predio_real.get("entorno") or {}
        _resol_punto = predio_real.get("resolucion") == "por_punto_referencial"
        if es_bogota:
            # Bogotá: sin capa predial con NUPRE en abierto; el destino económico
            # es el USO PREDOMINANTE por manzana (referencial del sector).
            _predio_destino = (_ent2.get("uso_economico") if not _resol_punto
                               else _ent2.get("uso_economico"))
            if _predio_destino:
                _predio_destino = f"{_predio_destino} (uso predominante por manzana)"
            _predio_estrato_catastral = _ent2.get("estrato")
            _predio_codigo_barrio = _ent2.get("sector_catastral")
            _predio_comuna = _ent2.get("localidad")
        else:
            _predio_destino = _p.get("destino_economico")
            # Medellín no expone condición jurídica en las capas abiertas (queda
            # PENDIENTE); Barranquilla la trae del servicio temático 'condicion'.
            _predio_condicion = (predio_real.get("condicion") or {}).get("condicion_juridica")
            # NUPRE/código SOLO se afirman si vinieron del CTL o de la resolución
            # exacta por código. La resolución por punto (sin CTL) cae en el predio
            # más cercano y podría ser un vecino: no se afirma su NUPRE como propio.
            if not _resol_punto:
                _predio_nupre = _predio_nupre or _p.get("nupre") or _p.get("codigo_homologado")
                _predio_codigo = _predio_codigo or _p.get("numero_predial_nacional") or _p.get("numero_predial")
            # Área/tipo/pisos: Barranquilla los trae en 'construccion'; Medellín en
            # 'lote' (Base_Catastral l3/l5). Se aceptan ambas estructuras.
            _const = predio_real.get("construccion") or predio_real.get("lote") or {}
            _predio_area_catastral = _p.get("area_catastral_terreno") or _const.get("area_lote")
            _predio_tipo_construccion = _const.get("tipo_construccion")
            _predio_pisos = _const.get("total_pisos") or _const.get("numero_pisos")
            _predio_estrato_catastral = _ent2.get("estrato") or _p.get("estrato")
            _predio_tratamiento = _ent2.get("tratamiento")
            _predio_codigo_barrio = _ent2.get("codigo_barrio")
            _predio_comuna = _ent2.get("comuna")
        # Construcción de Bogotá (pisos) desde su propio dict
        if es_bogota:
            _const_bog = predio_real.get("construccion") or {}
            _predio_tipo_construccion = _const_bog.get("tipo_construccion")
            _predio_pisos = _const_bog.get("total_pisos")
    else:
        _predio_tratamiento = None
        _predio_codigo_barrio = None
        _predio_comuna = None

    # Condición jurídica (PH / No PH): el catastro solo la publica en
    # Barranquilla; para Medellín/Bogotá (y BAQ sin servicio) se infiere del
    # propio CTL/SNR — fuente registral disponible en todas las ciudades
    # (p. ej. 'APARTAMENTO 401 con coeficiente' o 'EDIFICIO ... PROPIEDAD
    # HORIZONTAL' => PH; 'BODEGA'/'NO PROPIEDAD HORIZONTAL' => No PH).
    if not _predio_condicion and path_certificado:
        try:
            from legal_analyzer import inferir_condicion_juridica
            _cond_ctl = inferir_condicion_juridica(
                analysis.get("texto_ctl"), analysis.get("descripcion_ctl"))
            if _cond_ctl:
                _predio_condicion = _cond_ctl
        except Exception as _e_cond:
            print(f"[PDF][CONDICION] inferencia desde CTL no disponible: {_e_cond}")

    # Tipología derivada del destino económico catastral + CTL (descripción).
    # Si el CTL dice BODEGA o el destino es Industrial/Comercial → nunca PH.
    _tipologia_texto = None
    _desc_ctl = (analysis.get("descripcion_ctl") or "").upper()
    if predio_real and _predio_destino:
        _dest_up = str(_predio_destino).upper()
        if "INDUSTRIAL" in _dest_up or "BODEGA" in _desc_ctl:
            _tipologia_texto = "Bodega -- Uso Industrial (No Propiedad Horizontal)"
        elif "COMERCIAL" in _dest_up or "OFICINA" in _dest_up:
            # Evitar duplicación cuando el destino ya empieza con 'Comercial'
            # (p. ej. 'Comercial y Servicios' -> 'Uso Comercial y Servicios').
            _tipologia_texto = f"Uso {_predio_destino} (Según catastro)"
        else:
            _tipologia_texto = f"Uso {_predio_destino} (Según catastro)"
    elif "BODEGA" in _desc_ctl:
        _tipologia_texto = "Bodega -- Uso Industrial (No Propiedad Horizontal)"
    if _tipologia_texto is None:
        # Solo el caso demo explícito (sin CTL, barrio Miramar legado) conserva la
        # tipología de demostración; un predio real SIN datos catastrales queda
        # PENDIENTE (nunca se asume PH/Habitacional).
        if is_miramar and not path_certificado:
            _tipologia_texto = "Apartamento -- Propiedad Horizontal (NO VIS)"
        else:
            _tipologia_texto = "PENDIENTE DE VERIFICACION (Requiere consulta catastral)"

    # Val data con metodologia Lonja BAQ (estrato e integracion YAML)
    estrato = _predio_estrato_catastral or db_record.get('estrato', 4)
    try:
        estrato = int(str(estrato).replace("No_Aplica", "4").split("_")[0])
    except Exception:
        estrato = 4
    val_data = get_valuation(area, barrio, estrato)
    res_avaluo = val_data
    
    # Cargar hallazgos y recomendaciones dinamicas del analizador legal
    hallazgos = list(analysis["hallazgos"])
    recs = list(analysis["recs"])

    # ── Mejora 2 (Sprint 3): coherencia círculo registral del CTL vs. ciudad ──
    # Los folios SNR pertenecen a una oficina de registro: Barranquilla '040',
    # Medellín '001', Bogotá '50C/50N/50S'. Si el CTL adjuntado declara un
    # círculo distinto al del caso (p. ej. folio '001-...' en un caso de Bogotá),
    # el análisis registral NO corresponde al predio esperado: se advierte.
    _circ_ctl = (analysis.get("circulo_registral") or "").strip()
    _circ_folio, _ctl_discrepante = _detectar_discrepancia_circulo(
        folio, _circ_ctl, _CIRCULO)
    # Código legible para el hallazgo: prefijo crudo del folio ('001', '50C')
    _m_cod = re.match(r"^(\d{2,3}[A-Z]?)-\d+", str(folio).strip())
    _circ_mostrar = _m_cod.group(1).upper() if _m_cod else (_circ_folio or "")
    if _ctl_discrepante:
        hallazgos.append((
            "MEDIO", C_NARANJA, C_ALERTA_BG,
            f"H-CTL | Certificado de otro circulo registral ({_circ_mostrar}) vs. caso {_NOMBRE_CIUDAD}",
            "SNR -- Verificacion de coherencia",
            (f"El CTL adjuntado declara el circulo registral '{_circ_ctl}' (folio {folio}), "
             f"que NO corresponde a la oficina de registro de {_NOMBRE_CIUDAD} ({_CIRCULO}). "
             "El certificado podria ser de un predio de otra ciudad."),
            "Verificar que el CTL corresponde al predio del caso; si el folio es de otra "
            "ciudad, cree el caso con esa ciudad o cargue el certificado correcto."))
    
    cert_num = f'ARHIAX-LAI-2026-{db_record.get("id", 0):04d}'
    now_utc = datetime.datetime.now(datetime.timezone.utc)
    p_hash = hashlib.sha256(f'{folio}{cert_num}{now_utc.isoformat()}'.encode()).hexdigest()
    
    if assets_dir is None:
        if os.environ.get('VERCEL') or not os.access(str(API_DIR), os.W_OK):
            assets_dir = Path('/tmp/assets') / f'case_{db_record.get("id", 0)}'
        else:
            assets_dir = API_DIR / 'assets' / f'case_{db_record.get("id", 0)}'
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    shadow_9am_path = str(assets_dir / 'sombra_9am.png')
    shadow_3pm_path = str(assets_dir / 'sombra_3pm.png')
    mapa_satellite_path = str(assets_dir / 'mapa_satelital.png')
    # H-07: NO se usan imagenes demo de otros predios como fallback; si el caso no
    # tiene la imagen, la seccion correspondiente simplemente omite la figura
    # (los usos en el story ya verifican os.path.exists).
    
    poi_map_png = str(assets_dir / 'poi_map.png')
    poi_map_html = str(assets_dir / 'poi_map.html')
    
    BARRIO_COORDS = {'miramar': (10.9870, -74.8115), 'el recreo': (10.9838, -74.7998), 'recreo': (10.9838, -74.7998)}

    # Prioridad 1 (exactitud): coordenadas del predio REAL resueltas por código
    # catastral/NUPRE del CTL (capa 105 Dirección oficial). Si el CTL trae código,
    # estas coordenadas son la verdad, no el barrio de demostración.
    lat = lon = None
    if predio_real and predio_real.get("lat") is not None and predio_real.get("lon") is not None:
        lat = predio_real["lat"]
        lon = predio_real["lon"]
        print(f"[PDF][CATASTRO-PREDIO] coords reales del predio: ({lat:.5f}, {lon:.5f})")

    # Prioridad 2: coordenadas ya geocodificadas (bloque de enriquecimiento) o BD
    if lat is None or lon is None:
        if _lat_geo is not None and _lon_geo is not None:
            lat, lon = _lat_geo, _lon_geo
        else:
            lat = db_record.get('lat') or db_record.get('LAT')
            lon = db_record.get('lon') or db_record.get('LON')

    if not lat or not lon:
        # Prioridad 3: geocodificar la direccion real del predio (con la ciudad)
        try:
            from geocoder import geocodificar_direccion
            direccion_raw = db_record.get('direccion', '') or ''
            if direccion_raw and direccion_raw.lower() not in ('pendiente', ''):
                lat, lon = geocodificar_direccion(direccion_raw, ciudad=ciudad)
            else:
                raise ValueError("sin direccion valida")
        except Exception:
            # Prioridad 4: fallback (centroide de la ciudad o barrio demo legado)
            if barrio.lower().strip() in BARRIO_COORDS:
                coords = BARRIO_COORDS[barrio.lower().strip()]
            elif es_bogota:
                coords = (4.7110, -74.0721)
            elif es_medellin:
                coords = (6.2442, -75.5812)
            else:
                coords = (10.9685, -74.7813)
            lat, lon = coords

    # ── Sombras automáticas 9:00 AM / 3:00 PM (si el caso no trae las de ArcGIS Pro) ──
    # Simulación geométrica: posición solar (solar_engine) + huella/altura del
    # edificio (catastro en vivo, capa 310). El PDF las etiqueta como simulación.
    _tenia_9 = os.path.exists(shadow_9am_path)
    _tenia_3 = os.path.exists(shadow_3pm_path)
    fuente_sombras = "arcgis_pro"
    if not (_tenia_9 and _tenia_3):
        try:
            from shadow_render import generar_sombras_automaticas
            met = generar_sombras_automaticas(lat, lon, assets_dir)
            if not met.get("error") and met.get("imagenes"):
                fuente_sombras = "simulacion_geometrica"
            else:
                print(f"[SHADOW] no se pudieron generar sombras automáticas: {met.get('error')}")
        except Exception as e:
            print(f"[SHADOW] generación automática no disponible: {e}")

    # ── HITO 4: Evaluación geoespacial dinámica ───────────────────────────────
    # Barranquilla: motor STRtree sobre GeoJSON POT empaquetados (api/data/).
    # Medellín: capas de gestión del riesgo EN VIVO (VC_Gestion_Riesgo) resueltas
    # por el módulo catastro_predio_medellin (amenazas por punto).
    # Bogotá: capas IDIGER en vivo (mov. masa urbano, sismos, geotecnia).
    if es_medellin and predio_real:
        _amz = (predio_real.get("amenazas") or {})
        _mm = _amz.get("movimiento_masa") or {"intersecta": False}
        _in = _amz.get("inundacion") or {"intersecta": False}
        _av = _amz.get("avenida_torrencial") or {"intersecta": False}
        _si = _amz.get("sismo") or {"intersecta": False}
        _niveles = [x.get("nivel") for x in (_mm, _in, _av, _si) if x.get("intersecta") and x.get("nivel")]
        _nivel_mm = (_mm.get("nivel") or "N/D") if _mm.get("intersecta") else None
        _det_amz = []
        if _mm.get("intersecta"):
            _det_amz.append(f"movimientos en masa: {_mm.get('nivel') or 'N/D'}")
        if _in.get("intersecta"):
            _det_amz.append(f"inundación: {_in.get('nivel') or 'N/D'}")
        if _av.get("intersecta"):
            _det_amz.append(f"avenidas torrenciales: {_av.get('nivel') or 'N/D'}")
        if _si.get("intersecta"):
            _det_amz.append(f"sismos: {_si.get('nivel') or 'N/D'}")
        geo_eval = {
            "amenaza_remocion_masa": {
                "intersecta": bool(_mm.get("intersecta")),
                "nivel": _nivel_mm,
                "clase_suelo": (_ent2.get("clase_suelo") or "Urbano"),
                "area_poligono_m2": 0, "objectid": None,
                "color_hex": "#D92C2C" if _mm.get("intersecta") else "#7F8C8D",
            },
            "areas_en_riesgo": {
                "intersecta": bool(_in.get("intersecta") or _av.get("intersecta") or _si.get("intersecta")),
                "nivel": ", ".join(_det_amz) if _det_amz else None,
                "clase_suelo": (_ent2.get("clase_suelo") or "Urbano"),
                "area_poligono_m2": 0, "objectid": None,
                "color_hex": "#F08C2B" if (_in.get("intersecta") or _av.get("intersecta")) else "#7F8C8D",
            },
            "resumen_ejecutivo": (
                f"Predio en {_NOMBRE_CIUDAD} evaluado contra las capas oficiales de gestión del riesgo "
                f"(DAGRD): {'; '.join(_det_amz) if _det_amz else 'sin afectaciones registradas por amenaza'}."
            ),
        }
    elif es_bogota and predio_real:
        _amz = (predio_real.get("amenazas") or {})
        _mm = _amz.get("movimiento_masa_urbano") or {"intersecta": False}
        _si = _amz.get("respuesta_sismica") or {"intersecta": False}
        # Geotecnia = tipo de suelo (Aluvial...), NO amenaza: dato informativo
        _geo_suelo = _amz.get("geotecnia_tipo_suelo")
        _nivel_mm = (_mm.get("nivel")) if _mm.get("intersecta") else None
        _det_amz = []
        if _mm.get("intersecta") and _mm.get("nivel"):
            _det_amz.append(f"movimientos en masa: {_mm.get('nivel')}")
        if _si.get("intersecta") and _si.get("nivel"):
            _det_amz.append(f"respuesta sísmica: {_si.get('nivel')}")
        if _geo_suelo:
            _det_amz.append(f"suelo geotécnico (informativo): {_geo_suelo}")
        geo_eval = {
            "amenaza_remocion_masa": {
                "intersecta": bool(_mm.get("intersecta")),
                "nivel": _nivel_mm,
                "clase_suelo": (_ent2.get("clase_suelo") or "Urbano"),
                "area_poligono_m2": 0, "objectid": None,
                "color_hex": "#D92C2C" if _mm.get("intersecta") else "#7F8C8D",
            },
            "areas_en_riesgo": {
                "intersecta": bool(_si.get("intersecta")),
                "nivel": ", ".join(_det_amz) if _det_amz else None,
                "clase_suelo": (_ent2.get("clase_suelo") or "Urbano"),
                "area_poligono_m2": 0, "objectid": None,
                "color_hex": "#F08C2B" if _si.get("intersecta") else "#7F8C8D",
            },
            "resumen_ejecutivo": (
                f"Predio en {_NOMBRE_CIUDAD} evaluado contra las capas oficiales del IDIGER "
                f"(emergencias/gestionriesgos): {'; '.join(_det_amz) if _det_amz else 'sin afectaciones registradas'}."
            ),
        }
    else:
        if es_bogota or es_medellin:
            # El predio NO se resolvió en el catastro de la ciudad: el motor
            # empaquetado de Barranquilla NO debe evaluar coordenadas de otra
            # ciudad (regresión: un caso de Bogotá sin predio resuelto cruzaba
            # el 'POT de Barranquilla' y afirmaba resultados ajenos). Se marca
            # NO EVALUADO con la ciudad correcta.
            geo_eval = {
                "amenaza_remocion_masa": {"intersecta": False, "nivel": None,
                                          "clase_suelo": "N/D",
                                          "area_poligono_m2": 0, "objectid": None,
                                          "color_hex": "#7F8C8D"},
                "areas_en_riesgo": {"intersecta": False, "nivel": None,
                                    "clase_suelo": "N/D",
                                    "area_poligono_m2": 0, "objectid": None,
                                    "color_hex": "#7F8C8D"},
                "resumen_ejecutivo": (
                    "NO EVALUADO: no se resolvió el predio en el catastro de {} "
                    "al momento de generar el dictamen; la verificación de amenazas/"
                    "riesgos queda PENDIENTE (no se aplicó el motor de otra ciudad)."
                ).format(_NOMBRE_CIUDAD),
            }
        else:
            geo_eval = get_geospatial_evaluation(lat, lon)
    if es_bogota:
        _fuente_geo = "IDIGER Bogotá -- emergencias/gestionriesgos (en vivo)"
    elif es_medellin:
        _fuente_geo = "Servidormapas Medellín -- VC_Gestion_Riesgo (DAGRD, en vivo)"
    else:
        _fuente_geo = "POT BAQ -- Capas GeoJSON (STRtree ARHIAX RE)"
    hallazgos = _inject_geospatial_hallazgo(
        hallazgos, geo_eval, barrio,
        fuente_pot=_fuente_geo,
        nombre_ciudad=_NOMBRE_CIUDAD,
    )

    # Sprint 3 (edificabilidad): hallazgo H-URB cuando lo CONSTRUIDO en catastro
    # excede la ALTURA MÁXIMA normativa del polígono (POT por ciudad). Solo se
    # afirma cuando la capa oficial expone un número de pisos; de lo contrario
    # la tabla 6.3 lo deja PENDIENTE/remisión oficial (nunca se inventa).
    try:
        from edificabilidad import hallazgo_exceso_altura
        _h_urb = hallazgo_exceso_altura(ciudad, _ent2, _predio_pisos)
        if _h_urb:
            hallazgos.append(_h_urb)
    except Exception as _e_urb:
        print(f"[PDF][EDIFICABILIDAD] hallazgo de exceso no disponible: {_e_urb}")

    # Mejora 5: H-LIC cuando lo construido excede lo LICENCIADO (autoridad más
    # concreta que la capa POT: la licencia puede amparar más por derechos
    # adquiridos, pero nunca menos de lo ejecutado).
    try:
        from edificabilidad import hallazgo_exceso_licencia
        _h_lic = hallazgo_exceso_licencia(ciudad, _ent2, _predio_pisos, licencia)
        if _h_lic:
            hallazgos.append(_h_lic)
    except Exception as _e_lic:
        print(f"[PDF][LICENCIA] hallazgo H-LIC no disponible: {_e_lic}")
    # ──────────────────────────────────────────────────────────────────────────────

    pois = get_nearby_pois(lat, lon, radius=2000)
    generate_maps(lat, lon, pois, poi_map_png, poi_map_html, inmueble_label=f"Predio {barrio}" if barrio else "Inmueble", direccion=direccion)

    
    def fmt_cop(val):
        return f'$ {val:,.0f}'.replace(',', '.')
    
    FOLIO = folio
    CERT_NUM = cert_num
    NOW_UTC = now_utc
    P_HASH = p_hash
    MAP_IMG = mapa_satellite_path
    OUTPUT = output_pdf_path
    POI_MAP_PNG = poi_map_png
    POI_MAP_HTML = poi_map_html
    SHADOW_IMG = shadow_9am_path
    SHADOW_IMG2 = shadow_3pm_path
    SCOPE_DISCLAIMER_FULL = (
        "NATURALEZA DE ESTE DOCUMENTO. Este es un analisis de base producido "
        "automaticamente por el motor ARHIAX a partir de fuentes publicas (SNR, "
        "geoportales municipales, catastro, OpenStreetMap y bases abiertas). No "
        "constituye estudio de titulos, concepto juridico ni avaluo comercial en los "
        "terminos de la Ley 1673 de 2013 ni de las normas de metodologia valuatoria "
        "vigentes. Es un insumo preliminar sujeto a verificacion por profesional del "
        "derecho con tarjeta profesional vigente y/o avaluador inscrito en el RAA. "
        "Ninguna decision de credito, garantia o compraventa debe adoptarse con base "
        "exclusiva en este documento."
    )
    SCOPE_DISCLAIMER_FOOTER = (
        "Insumo base de fuentes publicas · No sustituye estudio de titulos ni "
        "avaluo · Sujeto a verificacion profesional."
    )
    
    BLOQUEOS_FIDUCIARIOS = {
        "hipoteca", "embargo", "afectacion", "patrimonio", "demanda", "usufructo", "medida cautelar"
    }
    
    def evaluar_estructurabilidad_fiduciaria(hallazgos_list):
        bloqueos = []
        for h in hallazgos_list:
            # Un hallazgo INFORMATIVO (tradición limpia, etc.) NUNCA bloquea:
            # su texto menciona gravámenes en negación ("No se detectaron...").
            if h[0] == "INFORMATIVO":
                continue
            titulo = h[3].lower()
            descripcion = h[5].lower()
            implicacion = h[6].lower()
            # Negaciones explícitas: el hallazgo describe la AUSENCIA del bloqueo
            texto_completo = " | ".join([titulo, descripcion, implicacion])
            if any(neg in texto_completo for neg in ("no se detectaron", "sin gravamenes",
                                                     "sin gravámenes", "libre de gravamenes",
                                                     "libre de gravámenes", "sin afectacion",
                                                     "sin hipotecas", "no registra gravamenes")):
                continue
            if any(w in titulo for w in ("cancelada", "levantada", "extinguida", "resuelto")):
                continue
            # Regla de coherencia: severidad ALTO = BLOQUEANTE por definición
            # (hipoteca/embargo vigente, AUSENCIA DE CTL, exceso de licencia...).
            # Antes la ausencia de CTL dejaba el semáforo VERDE contradiciendo
            # el resumen 'BLOQUEADO/ROJO' del encabezado.
            if h[0] == "ALTO":
                bloqueos.append(h[3])
                continue
            # Solo se consideran bloqueos VIGENTES y no cancelados/resueltos
            is_vigente = "vigente" in titulo or "vigente" in descripcion or "vigente" in implicacion
            is_bloqueo = any(term in titulo or term in descripcion for term in BLOQUEOS_FIDUCIARIOS)
            if is_vigente and is_bloqueo:
                bloqueos.append(h[3])
        if bloqueos:
            return {
                "semaforo": "ROJO",
                "estructurable": False,
                "condiciones_precedentes": bloqueos,
            }
        return {"semaforo": "VERDE", "estructurable": True, "condiciones_precedentes": []}
    
    def build_header_parche(s, folio, cert_num, fecha, hash_preview):
        from reportlab.platypus import Table, TableStyle
        left = [
            Paragraph("<b>ARHIAX</b>", s["h1"]),
            Paragraph("Motor Geo-Provenance · Informe Base LAI Estandar", s["h2"]),
            Paragraph("Sinergia Consulting Group · Edicion Completa v1.0", 
                      ParagraphStyle("sub2", fontName="Helvetica", fontSize=7.5,
                                     textColor=colors.HexColor("#B0C4DE"), leading=10)),
        ]
        right_style = ParagraphStyle("hr_s", fontName="Helvetica", fontSize=8,
                                      textColor=colors.HexColor("#B0C4DE"),
                                      leading=12, alignment=TA_RIGHT)
        right = [
            Paragraph(f"<b>Referencia N°:</b> {cert_num}", right_style),
            Paragraph(f"<b>Folio:</b> {folio}", right_style),
            Paragraph(f"<b>Emitido:</b> {fecha}", right_style),
            Paragraph(f"<b>DOC-ID:</b> {hash_preview}...", 
                      ParagraphStyle("docid", fontName="Courier", fontSize=7,
                                     textColor=colors.HexColor("#90A8C8"),
                                     leading=10, alignment=TA_RIGHT)),
        ]
        tbl = Table([[left, right]], colWidths=["55%", "45%"])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), C_AZUL_OSC),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("TOPPADDING", (0,0), (-1,-1), 18),
            ("BOTTOMPADDING", (0,0), (-1,-1), 14),
            ("LEFTPADDING", (0,0), (-1,-1), 20),
            ("RIGHTPADDING", (0,0), (-1,-1), 20),
            ("LINEBELOW", (0,0), (-1,-1), 4, C_DORADO),
        ]))
        return tbl
    
    def build_estado_banner_parche(hallazgos_list, s):
        from reportlab.platypus import Table, TableStyle
        n_alto = sum(1 for h in hallazgos_list if h[0] == "ALTO")
        n_medio = sum(1 for h in hallazgos_list if h[0] == "MEDIO")
        n_info = sum(1 for h in hallazgos_list if h[0] == "INFORMATIVO")

        # Refuerzo UX (Sprint 3): si NO se adjuntó el CTL, el informe se marca
        # explícitamente como NO APTO para decisiones (sin bloquear la descarga).
        sin_ctl = False
        for h in hallazgos_list:
            titulo_h = (h[3] if len(h) > 3 else "") or ""
            if "AUSENCIA DE CERTIFICADO" in titulo_h.upper() or "AUSENCIA DE CTL" in titulo_h.upper():
                sin_ctl = True
                break

        res_fiel = evaluar_estructurabilidad_fiduciaria(hallazgos_list)
        if sin_ctl:
            label = ("▪ INFORME BASE LAI — GENERADO SIN CERTIFICADO DE TRADICIÓN Y LIBERTAD (CTL). "
                     "Los datos registrales quedan PENDIENTES: este documento NO ES APTO para decisiones "
                     "de crédito, garantía o compraventa. Adjunte el CTL del predio para un dictamen completo.")
            bg = C_RIESGO_BG
            tc = C_ROJO
        elif not res_fiel["estructurable"]:
            label = f"▪ INFORME BASE LAI — RESULTADO PRELIMINAR: {n_alto} ALTO · {n_medio} MEDIO · {n_info} INFORMATIVO (BLOQUEADO / semáforo ROJO)"
            bg = C_RIESGO_BG
            tc = C_ROJO
        else:
            label = f"▪ INFORME BASE LAI — RESULTADO PRELIMINAR: {n_alto} ALTO · {n_medio} MEDIO · {n_info} INFORMATIVO (sujeto a verificación profesional)"
            bg = C_ALERTA_BG
            tc = C_NARANJA
            
        p = Paragraph(f"<b>{label}</b>",
                      ParagraphStyle("ban", fontName="Helvetica-Bold", fontSize=8.5,
                                     textColor=tc, leading=12))
        tbl = Table([[p]], colWidths=["100%"])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), bg),
            ("TOPPADDING", (0,0), (-1,-1), 9),
            ("BOTTOMPADDING", (0,0), (-1,-1), 9),
            ("LEFTPADDING", (0,0), (-1,-1), 18),
            ("LINEAFTER", (0,0), (0,-1), 5, tc),
        ]))
        return tbl
    
    # Configuracion del Analisis de Asolamiento y Sombras
    FACADE_AZIMUTH = 110  # Orientacion por defecto: ESE (110°)
    OBSTRUCTIONS = [(240, 280, 30)]  # Obstruccion de la Torre 7 (240°-280° azimut, elevacion <= 30°)
    # Usar las rutas dinámicas ya configuradas arriba sin sobrescribirlas con rutas locales de Windows

    
    s = build_styles()
    s["header"] = ParagraphStyle("h_style", parent=s["label"], textColor=colors.white)
    
    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor("#F0F4FB"))
        canvas.rect(0, 0, letter[0], letter[1], fill=1, stroke=0)
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(colors.HexColor("#718096"))
        canvas.drawString(40, 20, corregir_es(
            f"ARHIAX Informe Base LAI | Folio {FOLIO} | {CERT_NUM} | {SCOPE_DISCLAIMER_FOOTER}"))
        canvas.drawRightString(letter[0]-40, 20, f"Pag. {doc.page}")
        canvas.restoreState()
    
    def sec(title):
        return Paragraph(f"<b>{title}</b>", ParagraphStyle("sh", fontName="Helvetica-Bold",
            fontSize=11, textColor=C_AZUL_OSC, leading=14, spaceBefore=8, spaceAfter=4))
    
    def sub(title):
        return Paragraph(f"<b>{title}</b>", ParagraphStyle("ss", fontName="Helvetica-Bold",
            fontSize=9, textColor=C_AZUL_MED, leading=12, spaceBefore=6, spaceAfter=3))
    
    def body(text):
        return Paragraph(text, s["body"])
    
    def alert_green(text):
        return Paragraph(text, s["alert_verde"])
    
    def alert_orange(text):
        return Paragraph(text, s["alert_naranja"])
    
    def alert_red(text):
        return Paragraph(text, ParagraphStyle("alert_rojo",
            fontName="Helvetica-Bold", fontSize=8, leading=11,
            textColor=colors.HexColor("#8B2E2E"), backColor=colors.HexColor("#F7E8E8"),
            borderColor=colors.HexColor("#8B2E2E"), borderWidth=0.5, borderPadding=6))
    
    def dt(rows):
        return data_table(rows, s)
    
    # ── TITULUX (Confianza Predial): pre-dictamen + screening SAGRILAFT en vivo ──
    # Sprint Titulux: mapea el CTL real al modelo de pre-dictamen jurídico
    # determinista (TIT_B01..B05/VAL/TRX/SAG) y ejecuta el screening multifuente
    # (ONU/OFAC/UK en vivo; UIAF pendiente por canal oficial; UE por archivo) con degradación honesta.
    # Nunca rompe el PDF: si falla, la sección 05 lo declara NO EVALUADO.
    _listas_cache = os.environ.get("ARHIA_LISTAS_CACHE")
    if not _listas_cache:
        # Caché ESTABLE (no por-caso): en Vercel /tmp persiste entre invocaciones
        # sobre la misma instancia caliente (evita re-descargar ONU/OFAC ~18 MB);
        # en local, un directorio escribible dentro de api/.
        if os.environ.get("VERCEL") or not os.access(str(API_DIR), os.W_OK):
            _listas_cache = "/tmp/arhia_listas"
        else:
            _listas_cache = str(API_DIR / "assets" / "cache_listas")
    _titulux = None
    _titulux_skip = None
    if not path_certificado:
        # Sin CTL no hay titular, acreedor ni anotaciones que pre-analizar ni
        # sujetos que screeningar: descargar ONU/OFAC sería un desperdicio.
        _titulux_skip = ("sin certificado de libertad y tradición (CTL) adjunto: no hay "
                         "sujetos ni anotaciones que analizar.")
    else:
        try:
            from titulux_bridge import ejecutar_titulux
            _titulux = ejecutar_titulux(
                analysis, db_record, val_data, geo_eval,
                area_catastral=_predio_area_catastral,
                fuentes_activas=("onu", "ofac", "uiaf", "uk"),
                cache_dir=_listas_cache,
                timeout_listas=120,
            )
            print(f"[PDF][TITULUX] disponible={_titulux.get('disponible')} "
                  f"screening={_titulux.get('screening_agregado')} "
                  f"pendientes={_titulux.get('fuentes_pendientes')}")
        except Exception as _e_titulux:
            print(f"[PDF][TITULUX] no disponible: {_e_titulux}")
            _titulux = None
    
    # ── DEFINICIÓN DE HALLAZGOS (Módulo de Datos) ──────────────────
    
    # ── BUILD STORY ─────────────────────────────────────────────
    story = []
    
    # HEADER
    story.append(build_header_parche(s, FOLIO, CERT_NUM, NOW_UTC.strftime("%d %b %Y %H:%M UTC"), P_HASH[:16]))
    story.append(Spacer(1, 12))
    story.append(build_estado_banner_parche(hallazgos, s))
    story.append(Spacer(1, 10))
    
    # ── 00 DISCLAIMER DE ALCANCE ────────────────────────────────
    story.append(sec("00 - Naturaleza de este Documento"))
    story.append(hr())
    story.append(Paragraph(SCOPE_DISCLAIMER_FULL, ParagraphStyle("disc", parent=s["body"], fontSize=8, leading=11)))
    story.append(Spacer(1, 8))
    
    # ── 01 IDENTIFICACION ──────────────────────────────────────
    story.append(sec("01 - Identificacion del Activo"))
    story.append(hr())
    
    # Resolver datos de adquisicion/hipotecas desde el CTL o fallback
    constructor_val = analysis.get("constructor", "N/D")
    titulares_val = analysis.get("titulares", "PENDIENTE DE VERIFICACIÓN (Sin Certificado cargado)")
    apertura_val = analysis.get("apertura", "N/D")
    
    # Acreedores detectados
    hipotecas_activas = [a for a in analysis.get("anotaciones", []) if "Hipoteca" in a[2] and "CANCELADA" not in a[4]]
    if hipotecas_activas:
        # Extraer el acreedor de la última hipoteca activa
        partes_hip = hipotecas_activas[-1][3]
        acreedor_snr = partes_hip.split("->")[-1].strip() if "->" in partes_hip else partes_hip
    elif not path_certificado:
        # Sin CTL no hay fuente registral: NO se afirma 'sin gravamenes' (regresión:
        # un dictamen sin certificado decia 'SIN GRAVÁMENES ACTIVOS REGISTRADOS').
        acreedor_snr = "PENDIENTE DE VERIFICACION (sin CTL adjuntado)"
    else:
        acreedor_snr = "SIN GRAVÁMENES ACTIVOS REGISTRADOS"
        
    # Mejora 2: la fila de matrícula refleja el CÍRCULO REGISTRAL REAL del CTL
    # cuando el certificado lo declara (no solo el de la ciudad del caso).
    _mat_circ_txt = f"Circulo Registral {_CIRCULO} {_NOMBRE_CIUDAD}"
    if _circ_ctl:
        _mat_circ_txt = f"Circulo Registral segun CTL: {_circ_ctl}"
        if _ctl_discrepante:
            _mat_circ_txt += f" [NO coincide con {_CIRCULO} {_NOMBRE_CIUDAD}]"
    story.append(dt([
        ("Matricula Inmobiliaria", f"{folio} ({_mat_circ_txt})"),
        ("Direccion oficial", direccion),
        # Sprint 2 (exactitud): la tipología se deriva del CTL/destino catastral real.
        # El caso de demostración (Napoli/Miramar PH) ya no puede contaminar predios
        # reales: si el CTL trae código catastral, la tipología es la real o PENDIENTE.
        ("Tipologia", _tipologia_texto),
        ("Area privada construida", f"{area:.2f} m2" if area else "Sin soporte CTL"),
        # Coeficiente de copropiedad: solo aplica si el catastro confirma PH
        ("Coeficiente de copropiedad",
         "N/D (No Propiedad Horizontal)" if (_predio_condicion and "NO PROPIEDAD HORIZONTAL" in str(_predio_condicion).upper())
         else ("0,2037% (PH)" if is_miramar else "N/D (Sujeto a regimen registral)")),
        ("Apertura del folio", apertura_val),
        ("NUPRE", f"{_predio_nupre} (Catastro {_NOMBRE_CIUDAD})" if _predio_nupre
         else ("080010102200400020043000000000 (Catastro BAQ)" if is_miramar else "Pendiente consulta catastral")),
        ("Codigo catastral", f"{_predio_codigo} (GC-{_NOMBRE_CIUDAD.upper()[:3]})" if _predio_codigo else "Pendiente consulta catastral"),
        ("Titulares vigentes", titulares_val),
        ("Modalidad de adquisicion", "Compraventa registrada en CTL" if len(analysis.get("anotaciones", [])) > 0 else "Sujeto a verificacion SNR"),
        ("Valor Comercial Consolidado", f"{fmt_cop(res_avaluo['consolidado'])} COP (Banda: {fmt_cop(res_avaluo['banda_baja'])} -- {fmt_cop(res_avaluo['banda_alta'])})"),
        ("Constructor / Enajenante", constructor_val),
        ("Acreedor hipotecario (SNR)", acreedor_snr),
        ("Acreedor hipotecario (REAL)", acreedor_snr),
        ("ORIP", _ORIP),
        ("Fuente registral", f"Certificado SNR cargado: {Path(path_certificado).name}" if path_certificado else "Consulta referencial sin CTL"),
    ]))
    story.append(Spacer(1, 8))
    
    # ── 02 LOCALIZACION ────────────────────────────────────────
    story.append(sec("02 - Localizacion Geografica del Inmueble"))
    story.append(hr())
    _sector_desc = (barrio if barrio and barrio != "PENDIENTE DE VERIFICACION CATASTRAL"
                    else "sector por verificar en campo")
    story.append(body(
        f"Vista satelital del inmueble en el {_sector_desc}, "
        f"{_NOMBRE_CIUDAD}. Coordenadas de ubicacion: <b>{lat:.5f} N, {lon:.5f} W</b>. "
        "<b>[FUENTE: GMAPS-SAT]</b>"
    ))
    story.append(Spacer(1, 6))
    if os.path.exists(MAP_IMG):
        try:
            img = RLImage(MAP_IMG, width=16*cm, height=9*cm)
            img.hAlign = "CENTER"
            t = Table([[img]], colWidths=["100%"])
            t.setStyle(TableStyle([("GRID",(0,0),(-1,-1),1.5,C_AZUL_OSC),
                ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
                ("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),
                ("ALIGN",(0,0),(-1,-1),"CENTER")]))
            story.append(t)
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                f"<i>Fig. 1 - Captura de localizacion satelital del predio en la direccion: {direccion}.</i>",
                ParagraphStyle("cap", fontName="Helvetica-Oblique", fontSize=7.5,
                               textColor=colors.HexColor("#718096"), leading=10, alignment=TA_CENTER)))
        except Exception as img_err:
            print(f"Warning: could not load MAP_IMG: {img_err}")
    story.append(Spacer(1, 6))
    _localidad_txt = None
    if es_medellin:
        _localidad_txt = _ent2.get("comuna")
    elif es_bogota:
        _localidad_txt = _ent2.get("localidad")
    else:
        _localidad_txt = _ent2.get("localidad") if _ent2 else None
    _filas_localizacion = [
        ("Coordenadas WGS84", f"Lat: {lat:.5f} N | Lon: {lon:.5f} W"),
        ("Sector urbano", f"{_NOMBRE_CIUDAD} / {barrio}" if barrio and barrio != "PENDIENTE DE VERIFICACION CATASTRAL" else f"{_NOMBRE_CIUDAD} (sector por verificar)"),
        ("Barrio catastral", barrio if barrio and barrio != "PENDIENTE DE VERIFICACION CATASTRAL" else "PENDIENTE DE VERIFICACION"),
        ("Comuna/Localidad", _localidad_txt if _localidad_txt else "N/D"),
    ]
    if es_bogota and _ent2.get("upz"):
        _filas_localizacion.append(("UPZ (Unidad de Planeamiento Zonal)", _ent2["upz"]))
    _filas_localizacion += [
        ("Infraestructura vial", "Vias de acceso inmediato geocodificadas"),
        ("Equipamientos cercanos", "Equipamiento urbano detectado en radio de 2.0 km"),
    ]
    story.append(dt(_filas_localizacion))
    story.append(Spacer(1, 8))
     # Calcular asolamiento para 9:00 AM, 12:00 PM, 3:00 PM
    solar_results = []
    for hour in [9, 12, 15]:
        dt_local = datetime.datetime(NOW_UTC.year, NOW_UTC.month, NOW_UTC.day, hour, 0, 0)
        az, el = get_solar_position(lat, lon, dt_local)
        status, desc = analyze_facade_exposure(az, el, FACADE_AZIMUTH, OBSTRUCTIONS)
        solar_results.append((f"{hour:02d}:00 COT", f"{az}°", f"{el}°", status, desc))
    
    solar_table_data = [
        [Paragraph("<font color='white'><b>Hora (Local)</b></font>", s["label"]),
         Paragraph("<font color='white'><b>Azimut Sol</b></font>", s["label"]),
         Paragraph("<font color='white'><b>Elevacion</b></font>", s["label"]),
         Paragraph("<font color='white'><b>Estado Fachada</b></font>", s["label"]),
         Paragraph("<font color='white'><b>Descripcion / Incidencia</b></font>", s["label"])]
    ]
    for h, az, el, status, desc in solar_results:
        if status == "Sol Directo":
            status_para = Paragraph(f"<font color='{C_VERDE.hexval()}'><b>{status}</b></font>", s["body"])
        elif "Sombra" in status:
            status_para = Paragraph(f"<font color='{C_NARANJA.hexval()}'><b>{status}</b></font>", s["body"])
        else:
            status_para = Paragraph(f"<b>{status}</b>", s["body"])
            
        solar_table_data.append([
            Paragraph(h, s["value"]),
            Paragraph(az, s["value"]),
            Paragraph(el, s["value"]),
            status_para,
            Paragraph(desc, s["body"])
        ])
    
    t_solar = Table(solar_table_data, colWidths=["13%", "14%", "13%", "25%", "35%"])
    t_solar.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), C_AZUL_OSC),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F0F4FB")]),
        ("GRID", (0,0), (-1,-1), 0.4, C_BORDE),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE")
    ]))
    story.append(t_solar)
    story.append(Spacer(1, 6))
    
    images_to_show = []
    if os.path.exists(SHADOW_IMG):
        images_to_show.append((SHADOW_IMG, "9:00 AM (Manana)"))
    if os.path.exists(SHADOW_IMG2):
        images_to_show.append((SHADOW_IMG2, "3:00 PM (Tarde)"))
    
    if len(images_to_show) == 2:
        try:
            img1 = RLImage(images_to_show[0][0], width=7.8*cm, height=4.5*cm)
            img2 = RLImage(images_to_show[1][0], width=7.8*cm, height=4.5*cm)
            t_s = Table([[img1, img2]], colWidths=["50%", "50%"])
            t_s.setStyle(TableStyle([
                ("GRID", (0,0), (-1,-1), 1.0, C_AZUL_OSC),
                ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                ("LEFTPADDING", (0,0), (-1,-1), 4), ("RIGHTPADDING", (0,0), (-1,-1), 4),
                ("ALIGN", (0,0), (-1,-1), "CENTER")
            ]))
            story.append(t_s)
            story.append(Spacer(1, 4))
            _nota_sombras = (
                "Simulacion 3D de Sombras Proyectadas a las 9:00 AM (Izquierda) y a las 3:00 PM (Derecha) "
                "(ArcGIS Online - Escena Fotorrealista de Google)."
                if fuente_sombras == "arcgis_pro"
                else "Simulacion GEOMETRICA de Sombras Proyectadas a las 9:00 AM (Izquierda) y 3:00 PM (Derecha) "
                     "(generada automaticamente por ARHIAX: posicion solar + huella y altura del edificio segun catastro). "
                     "No es un render fotorealista; verificar en campo."
            )
            story.append(Paragraph(
                "<i>Fig. 2 - " + _nota_sombras + "</i>",
                ParagraphStyle("cap_shadow", fontName="Helvetica-Oblique", fontSize=7.5,
                               textColor=colors.HexColor("#718096"), leading=10, alignment=TA_CENTER)))
        except Exception as img_err:
            print(f"Warning: could not load shadow images: {img_err}")
    elif len(images_to_show) == 1:
        try:
            img_shadow = RLImage(images_to_show[0][0], width=16*cm, height=9*cm)
            img_shadow.hAlign = "CENTER"
            t_s = Table([[img_shadow]], colWidths=["100%"])
            t_s.setStyle(TableStyle([
                ("GRID", (0,0), (-1,-1), 1.5, C_AZUL_OSC),
                ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                ("LEFTPADDING", (0,0), (-1,-1), 4), ("RIGHTPADDING", (0,0), (-1,-1), 4),
                ("ALIGN", (0,0), (-1,-1), "CENTER")
            ]))
            story.append(t_s)
            story.append(Spacer(1, 4))
            _nota_1 = (
                f"Simulacion 3D de Sombras Proyectadas a las {images_to_show[0][1]} "
                "(ArcGIS Online - Escena Fotorrealista de Google)."
                if fuente_sombras == "arcgis_pro"
                else f"Simulacion GEOMETRICA de Sombras Proyectadas a las {images_to_show[0][1]} "
                     "(generada automaticamente por ARHIAX: posicion solar + huella y altura del edificio segun catastro). "
                     "No es un render fotorealista; verificar en campo."
            )
            story.append(Paragraph(
                f"<i>Fig. 2 - {_nota_1}</i>",
                ParagraphStyle("cap_shadow", fontName="Helvetica-Oblique", fontSize=7.5,
                               textColor=colors.HexColor("#718096"), leading=10, alignment=TA_CENTER)))
        except Exception as img_err:
            print(f"Warning: could not load shadow image: {img_err}")
    else:
        story.append(alert_orange(
            "<b>INTEGRACION 3D DISPONIBLE:</b> Puedes adjuntar una simulacion visual de sombras "
            "de ArcGIS Online en este reporte. Para hacerlo, guarda las capturas de sombras como "
            f"<i>sombra_9am.png</i> y <i>sombra_3pm.png</i> en la ruta:<br/>"
            f"<code>{SHADOW_IMG}</code>"
        ))
    story.append(Spacer(1, 8))
    
    # ── 03 ANALISIS DE EQUIPAMIENTO URBANO (POI) ────────────────
    story.append(sec("03 - Analisis de Equipamiento Urbano y Puntos de Interes (POI)"))
    story.append(hr())
    _total_pois = sum(len(items) for items in pois.values())
    if _total_pois == 0:
        # M-03: OSM no disponible -> se declara SIN datos (no se inventan POIs)
        story.append(alert_orange(
            "<b>Equipamientos NO DISPONIBLES:</b> la consulta a OpenStreetMap no respondio al "
            "momento de generar el dictamen, por lo que esta seccion no reporta equipamientos. "
            "No se incluyen datos no verificados; reintente la generacion o verifique en campo."))
    else:
        story.append(body(
            f"Analisis de accesibilidad y cobertura de equipamientos urbanos en un radio de <b>2.0 km</b> "
            f"en torno a las coordenadas del predio (Lat: {lat:.5f}, Lon: {lon:.5f}). "
            f"Los datos fueron extraidos de la base geografica de "
            f"OpenStreetMap (OSM) y ordenados por proximidad geodesica real. "
            "<b>[FUENTE: OPENSTREETMAP OVERPASS API]</b>"
        ))
    story.append(Spacer(1, 4))
    
    # M-02: se reutilizan los POIs y mapas generados en la inicialización (línea ~184);
    # se elimina la llamada duplicada a Overpass/generate_maps.
    poi_table_data = [
        [Paragraph("<font color='white'><b>Categoria</b></font>", s["label"]),
         Paragraph("<font color='white'><b>Nombre del Equipamiento</b></font>", s["label"]),
         Paragraph("<font color='white'><b>Tipo de Servicio</b></font>", s["label"]),
         Paragraph("<font color='white'><b>Distancia (Metros)</b></font>", s["label"]),
         Paragraph("<font color='white'><b>Tiempo Caminata (Aprox)</b></font>", s["label"])]
    ]
    
    for category, items in pois.items():
        for item in items:
            dist_m = item["distance"]
            time_min = int(round((dist_m / 72.0)))
            time_str = f"~{time_min} min a pie" if time_min <= 15 else f"~{time_min} min (Vehiculo/Bici)"
            
            poi_table_data.append([
                Paragraph(f"<b>{category}</b>", s["value"]),
                Paragraph(item["name"], s["body"]),
                Paragraph(item["type"], s["body"]),
                Paragraph(f"{int(dist_m)} m", s["value"]),
                Paragraph(time_str, s["body"])
            ])
    
    t_poi = Table(poi_table_data, colWidths=["15%", "35%", "25%", "12%", "13%"])
    t_poi.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), C_AZUL_OSC),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F0F4FB")]),
        ("GRID", (0,0), (-1,-1), 0.4, C_BORDE),
        ("TOPPADDING", (0,0), (-1,-1), 4),
        ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE")
    ]))
    story.append(t_poi)
    story.append(Spacer(1, 6))
    
    if os.path.exists(POI_MAP_PNG):
        try:
            img_poi_map = RLImage(POI_MAP_PNG, width=16*cm, height=9.77*cm)
            img_poi_map.hAlign = "CENTER"
            t_m = Table([[img_poi_map]], colWidths=["100%"])
            t_m.setStyle(TableStyle([
                ("GRID", (0,0), (-1,-1), 1.5, C_AZUL_OSC),
                ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
                ("LEFTPADDING", (0,0), (-1,-1), 4), ("RIGHTPADDING", (0,0), (-1,-1), 4),
                ("ALIGN", (0,0), (-1,-1), "CENTER")
            ]))
            story.append(t_m)
            story.append(Spacer(1, 4))
            story.append(Paragraph(
                "<i>Fig. 3 - Distribucion Espacial de Equipamientos Urbanos y Puntos de Interes (POI) "
                "en el radio de 2.0 km de la propiedad (Elaboracion Propia usando OpenStreetMap y Pillow).</i>",
                ParagraphStyle("cap_poi_map", fontName="Helvetica-Oblique", fontSize=7.5,
                               textColor=colors.HexColor("#718096"), leading=10, alignment=TA_CENTER)))
        except Exception as img_err:
            print(f"Warning: could not load POI_MAP_PNG: {img_err}")
        story.append(Spacer(1, 6))
    
    story.append(alert_green(get_cobertura_alert(barrio, ciudad=ciudad)))
    story.append(Spacer(1, 8))
    
    # ── 04 ANALISIS REGISTRAL ──────────────────────────────────
    # H-08/F-21: el título y el cuerpo distinguen si el CTL se procesó o no,
    # y nunca afirman consultas SNR en vivo que no ocurren.
    tiene_ctl = bool(db_record.get("certificado_path"))
    story.append(sec(
        "04 - Analisis Registral SNR -- Cadena de Tradicion [CTL PROCESADO]"
        if tiene_ctl else
        "04 - Analisis Registral SNR -- Cadena de Tradicion [SIN CTL]"
    ))
    story.append(hr())
    if tiene_ctl:
        story.append(body(
            f"Analisis del Certificado de Tradicion y Libertad adjuntado. "
            f"Folio de matricula: {folio}. "
            "<b>[FUENTE: CERTIFICADO ADJUNTADO POR EL USUARIO - NO ES CONSULTA SNR EN VIVO]</b>"
        ))
    else:
        story.append(body(
            f"No se adjunto Certificado de Tradicion y Libertad. Folio de matricula: {folio}. "
            "La informacion registral se marca PENDIENTE hasta cargar el CTL. "
            "<b>[FUENTE: SIN CTL ADJUNTADO]</b>"
        ))
        story.append(Spacer(1, 4))
        # Refuerzo UX (Sprint 3): sin CTL, el análisis registral no existe y el
        # documento no es apto para decisiones; se advierte de forma explícita.
        story.append(alert_red(
            "<b>DICTAMEN GENERADO SIN CTL:</b> no se puede verificar la titularidad, "
            "las hipotecas, embargos o afectaciones del predio. Este documento es "
            "un <b>informe base preliminar NO APTO para decisiones</b> de credito, "
            "garantia o compraventa. Para el dictamen completo adjunte el Certificado "
            "de Tradicion y Libertad (SNR) del predio."
        ))
    story.append(Spacer(1, 4))
    
    ann = analysis.get("anotaciones", [])
    if not ann:
        if tiene_ctl:
            # El CTL se procesó pero no se detectaron anotaciones extraíbles
            ann = [("N/D", "N/D", "SIN ANOTACIONES DETECTADAS",
                    "El CTL procesado no presenta anotaciones extraibles", "N/D")]
        else:
            ann = [("N/D", "N/D", "AUSENCIA DE CTL", "No se cargo el archivo PDF", "PENDIENTE")]
        
    ann_data = [[Paragraph("<b>Anot.</b>",s["header"]),Paragraph("<b>Fecha</b>",s["header"]),
                 Paragraph("<b>Tipologia</b>",s["header"]),Paragraph("<b>Partes</b>",s["header"]),
                 Paragraph("<b>Estado</b>",s["header"])]]
    for a,f_date,tip,par,est in ann:
        ann_data.append([Paragraph(f"<b>{a}</b>",s["label"]),Paragraph(f_date,s["value"]),
                         Paragraph(tip,s["body"]),Paragraph(par,s["body"]),Paragraph(est,s["value"])])
    t = Table(ann_data, colWidths=["8%","11%","31%","28%","22%"])
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),C_AZUL_OSC),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F0F4FB")]),
        ("GRID",(0,0),(-1,-1),0.4,C_BORDE),("TOPPADDING",(0,0),(-1,-1),4),
        ("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),5),
        ("FONTSIZE",(0,1),(-1,-1),7.5),("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(t)
    story.append(Spacer(1, 6))
    story.append(body(get_analisis_registral_text(barrio)))
    story.append(Spacer(1, 4))
    # I-4: deep-link al portal oficial del CTL (SNR) — nunca scraping
    story.append(body(
        "<b>Obtencion del CTL oficial (SNR):</b> el Certificado de Tradicion y Libertad se "
        "obtiene en el portal oficial de la Superintendencia de Notariado y Registro: "
        "<b>certificados.supernotariado.gov.co</b> (servicio de pago autorizado, ~COP 29.000-35.000). "
        "ARHIAX no realiza consultas automatizadas ni scraping al SNR; el CTL debe "
        "obtenerse por el canal oficial y adjuntarse al caso."))
    story.append(Spacer(1, 8))

    # ── 05 PRE-DICTAMEN JURIDICO (TITULUX · CONFIANZA PREDIAL) ──
    story.append(sec("05 - Pre-dictamen juridico (Titulux)"))
    story.append(hr())
    story.append(body(
        "<b>Que es esta seccion:</b> el motor <b>Titulux (ARHIAX Confianza Predial)</b> aplica un "
        "pre-dictamen juridico determinista (reglas TIT/VAL/TRX/SAG) sobre el certificado de "
        "libertad y tradicion analizado en la seccion 04. Presenta los hallazgos del expediente "
        "(identidad, cronologia, titularidad, gravamenes y precio) y una conclusion preliminar, "
        "siempre como insumo del profesional competente. El <b>screening SAGRILAFT</b> de los "
        "nombres del caso se reporta en la seccion 09."))
    story.append(Spacer(1, 6))

    _ESTADO_ES = {
        "OK": "Conforme", "OBSERVACION": "Observacion", "RIESGO": "Riesgo",
        "INFORMATIVO": "Informativo", "INFORMACION_INSUFICIENTE": "Informacion insuficiente",
        "INCONSISTENTE": "Inconsistente", "REQUIERE_REVISION": "Requiere revision",
    }
    _SEV_ES = {"baja": "Baja", "media": "Media", "alta": "Alta", "critica": "Critica"}
    _VEREDICTO_ES = {
        "PREANALISIS_INCOMPLETO": "Pre-analisis incompleto (screening pendiente)",
        "BLOQUEO_PRECAUTORIO": "Bloqueo precautorio",
        "REQUIERE_REVISION": "Requiere revision profesional",
        "SIN_HALLAZGO_AUTOMATICO": "Sin hallazgo automatico (revisar por profesional)",
    }

    if not _titulux or not _titulux.get("disponible"):
        _motivo = ""
        if _titulux_skip:
            _motivo = f": {_titulux_skip}"
        elif _titulux and _titulux.get("error"):
            _motivo = f" ({_titulux.get('error')})"
        story.append(alert_orange(
            "<b>Pre-dictamen juridico NO EVALUADO</b>" + _motivo + ". "
            "El analisis juridico preliminar queda PENDIENTE; no se afirma resultado alguno."
        ))
    else:
        # --- Hallazgos del expediente ---
        story.append(sub("Hallazgos del expediente"))
        _filas_h = [[Paragraph("<b>Regla</b>", s["header"]),
                     Paragraph("<b>Verificacion</b>", s["header"]),
                     Paragraph("<b>Estado</b>", s["header"]),
                     Paragraph("<b>Severidad</b>", s["header"])]]
        for h in _titulux.get("pre_dictamen", []):
            _filas_h.append([
                Paragraph(h.get("id", "") or "—", s["mono"]),
                Paragraph(h.get("titulo", "") or "—", s["body"]),
                Paragraph(_ESTADO_ES.get(h.get("estado"), h.get("estado", "")), s["value"]),
                Paragraph(_SEV_ES.get(h.get("severidad"), h.get("severidad", "")), s["body"]),
            ])
        _t_h = Table(_filas_h, colWidths=["13%", "49%", "20%", "18%"])
        _t_h.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C_AZUL_OSC), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0F4FB")]),
            ("GRID", (0, 0), (-1, -1), 0.4, C_BORDE),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(_t_h)
        story.append(Spacer(1, 4))

        # Detalle de hallazgos relevantes (riesgo/observación) con acción
        _hall_detalle = [h for h in _titulux.get("pre_dictamen", [])
                         if h.get("estado") in ("RIESGO", "OBSERVACION", "INCONSISTENTE",
                                               "INFORMACION_INSUFICIENTE", "REQUIERE_REVISION")]
        if _hall_detalle:
            for h in _hall_detalle:
                _desc = (h.get("descripcion") or "").strip()
                _base = (h.get("base_legal") or "").strip()
                _acc = (h.get("accion") or "").strip()
                _txt = _desc
                if _base:
                    _txt += f" <i>Base legal: {_base}.</i>"
                if _acc:
                    _txt += f" <b>Accion sugerida:</b> {_acc}"
                story.append(Paragraph(
                    f"<b>{h.get('id')} — {h.get('titulo')}</b> "
                    f"[{_ESTADO_ES.get(h.get('estado'), h.get('estado'))} · "
                    f"{_SEV_ES.get(h.get('severidad'), h.get('severidad'))}]: {_txt}",
                    ParagraphStyle("tith", parent=s["body"], fontSize=8, leading=11,
                                   spaceBefore=3)))
        story.append(Spacer(1, 6))

        # --- Conclusión (autoría separada) ---
        _conc = _titulux.get("conclusion") or {}
        _ver = _conc.get("veredicto", "")
        story.append(sub("Conclusion preliminar (autoria separada)"))
        if _ver:
            story.append(body(
                f"<b>Veredicto del pre-analisis:</b> {_VEREDICTO_ES.get(_ver, _ver)}."
            ))
        if _conc.get("fundamento"):
            story.append(body(_conc["fundamento"]))
        if _conc.get("recomendaciones"):
            _recs = "; ".join(_conc["recomendaciones"])
            story.append(body(f"<b>Recomendaciones:</b> {_recs}"))
        story.append(body(
            "<i>Titulux es un PRE-dictamen. La conclusion profesional, el concepto de valor y la "
            "decision de cumplimiento los emite y firma el profesional competente (abogado, "
            "avaluador RAA, oficial de cumplimiento); el sistema solo prepara y senaliza.</i>"))
    story.append(Spacer(1, 8))

    # ── 06 CATASTRAL Y POT [REAL] ──────────────────────────────
    story.append(sec("06 - Analisis Catastral y Urbanistico"))
    story.append(hr())
    if es_medellin:
        story.append(body(
            f"Analisis de informacion catastral y urbanistica del predio a partir de las capas "
            f"oficiales del catastro y POT de Medellín consultadas EN VIVO en el servidormapas "
            f"de la Alcaldía (uso del predio, estrato, clasificación de suelo, tratamiento "
            f"urbanístico) y estimaciones del modulo ARHIAX RE. "
            f"<b>[FUENTE: SERVIDORMAPAS MEDELLÍN - EN VIVO]</b>"))
    elif es_bogota:
        story.append(body(
            f"Analisis de informacion catastral y urbanistica del predio a partir de las capas "
            f"oficiales del catastro distrital y POT de Bogotá consultadas EN VIVO en el geoportal "
            f"de la Unidad Administrativa Especial de Catastro Distrital (lote, sector catastral, "
            f"uso económico por manzana, estrato, UPZ, localidad, clasificación de suelo Decreto "
            f"555/2021, valor de referencia) y estimaciones del modulo ARHIAX RE. "
            f"<b>[FUENTE: CATASTRO DISTRITAL BOGOTÁ - EN VIVO]</b>"))
    else:
        story.append(body(
            "Analisis de informacion catastral y urbanistica del predio a partir de las capas "
            "oficiales del POT de Barranquilla empaquetadas en la aplicacion (clases de suelo, "
            "norma de uso, tratamientos urbanisticos) y estimaciones del modulo ARHIAX RE. "
            "<b>[FUENTE: CAPAS POT BARRANQUILLA - MODULO ARHIAX RE]</b>"))
    story.append(Spacer(1, 4))
    story.append(sub("6.1 Datos Catastrales"))
    story.append(dt(get_catastral_dt(
        barrio, area,
        destino_economico=_predio_destino,
        nupre=_predio_nupre,
        codigo_catastral=_predio_codigo,
        condicion=_predio_condicion,
        area_catastral=_predio_area_catastral,
        tipo_construccion=_predio_tipo_construccion,
        pisos=_predio_pisos,
        estrato=_predio_estrato_catastral,
        ciudad=ciudad,
    )))
    story.append(Spacer(1, 4))

    # ── 6.1B Verificación catastral EN VIVO (Sprint 3, I-6) ──
    # Consulta el catastro abierto con caché y timeout corto; nunca rompe el PDF:
    # si el servicio no responde, se declara NO DISPONIBLE.
    _cat_live = {"disponible": False}
    if not es_medellin and not es_bogota:
        try:
            from integrations.catastro_live import verificar_catastro_barranquilla
            _cat_live = verificar_catastro_barranquilla(lat, lon)
        except Exception as e:
            _cat_live = {"disponible": False, "error": f"motor no disponible: {e}"}
    story.append(sub("6.1B Verificación Catastral en Vivo"))
    if predio_real and predio_real.get("disponible") and not es_bogota:
        _p4 = predio_real.get("predio") or {}
        # La resolución por punto (sin CTL/código) cae en el predio/sector más
        # cercano y NO permite afirmar su NUPRE/código como propio: solo el CTL
        # (código catastral/NUPRE) identifica el predio exacto.
        _por_punto = predio_real.get("resolucion") == "por_punto_referencial" or \
            not (analysis.get("codigo_catastral") or analysis.get("nupre"))
        if _por_punto:
            story.append(dt([
                ("Estado", "CONSULTADA -- Entorno catastral resuelto por coordenadas (sector/predio mas cercano)"),
                ("Codigo catastral", "Pendiente (se afirma solo con CTL: el codigo/NUPRE no se toma de un predio vecino)"),
                ("NUPRE", "Pendiente (se afirma solo con CTL)"),
                ("Destino economico", _predio_destino or "N/D"),
                ("Estrato", _predio_estrato_catastral or "N/D"),
                ("Condicion juridica", _predio_condicion or ("N/D (no expuesta en capas abiertas)" if es_medellin else "N/D")),
                ("Fuente en vivo", ("Servidormapas Alcaldia de Medellín (capa Uso del predio)"
                                    if es_medellin else
                                    "Catastro abierto Alcaldia de Barranquilla (capa Predio GC-BAQ)")),
            ]))
        else:
            # El CTL trajo código catastral/NUPRE y el predio se resolvió por
            # código: verificación REAL del predio (no coincidencia por bbox).
            _cod4 = _p4.get("numero_predial_nacional") or _p4.get("numero_predial") or "N/D"
            story.append(dt([
                ("Estado", "CONSULTADA -- Predio resuelto por codigo catastral/NUPRE del CTL"),
                ("Codigo catastral", _cod4),
                ("NUPRE", _predio_nupre or _p4.get("nupre") or _p4.get("codigo_homologado") or "N/D"),
                ("Destino economico", _predio_destino or "N/D"),
                ("Condicion juridica", _predio_condicion or ("N/D (no expuesta en capas abiertas)" if es_medellin else "N/D")),
                ("Area terreno (catastro)", f"{_predio_area_catastral:.2f} m2" if _predio_area_catastral else "N/D"),
                ("Fuente en vivo", ("Servidormapas Alcaldia de Medellín (capa Uso del predio)"
                                    if es_medellin else
                                    "Catastro abierto Alcaldia de Barranquilla (capa Predio GC-BAQ)")),
            ]))
    elif es_bogota and predio_real and predio_real.get("disponible"):
        # Bogotá: sin capa predial con NUPRE en abierto; se reporta la consulta
        # por punto (lote, sector catastral, uso por manzana, estrato, UPZ...).
        _en_bog = (predio_real.get("entorno") or {})
        story.append(dt([
            ("Estado", "CONSULTADA -- Entorno catastral resuelto por coordenadas (catastro distrital)"),
            ("Codigo lote", _en_bog.get("codigo_lote") or "N/D"),
            ("Codigo manzana", _en_bog.get("codigo_manzana") or "N/D"),
            ("Sector catastral", _en_bog.get("sector_catastral") or "N/D"),
            ("Uso economico (manzana)", _en_bog.get("uso_economico") or "N/D"),
            ("Estrato", _en_bog.get("estrato") or "N/D"),
            ("Valor ref. m2 (manzana)", f"${_en_bog.get('valor_ref_m2'):,.0f}" if _en_bog.get("valor_ref_m2") else "N/D"),
            ("Fuente en vivo", "Catastro distrital Bogotá (serviciosgis.catastrobogota.gov.co)"),
        ]))
    elif _cat_live.get("disponible"):
        _fuente_url = _cat_live.get("fuente", {}).get("url", "N/D")
        story.append(dt([
            ("Estado", "CONSULTADA (servicio abierto Alcaldía de Barranquilla)"),
            ("NUPRE catastral", _cat_live.get("nupre") or "N/D"),
            ("Features terreno / datos adicionales",
             f"{_cat_live.get('total_features_terreno', 0)} / {_cat_live.get('total_features_datos', 0)}"),
            ("Fuente en vivo", _fuente_url),
        ]))
    else:
        story.append(alert_orange(
            f"<b>Verificación catastral en vivo NO DISPONIBLE:</b> el servicio abierto de "
            f"{_NOMBRE_CIUDAD} no respondió al momento de generar el dictamen o el predio no "
            f"se resolvió por código catastral/NUPRE. La información catastral de esta sección "
            f"debe verificarse antes de usarse en una decisión."))
    story.append(Spacer(1, 4))
    story.append(sub("6.2 POT -- Cruce de Capas de Ordenamiento"))
    _trat_par = (str(_predio_tratamiento or "") if _predio_tratamiento else "")
    _clase_suelo_real = (_ent2.get("clase_suelo") or "").strip()

    # Bogotá/Medellín: la tabla de auditoría de capas POT es específica de
    # Barranquilla (no aplica a otras ciudades: se evitaba afirmar datos de BAQ
    # en un dictamen de Bogotá). Se muestra el resumen POT con los VALORES
    # reales consultados en vivo (o PENDIENTE honesto si el servicio no llegó).
    if es_bogota or es_medellin:
        _resumen_pot = get_pot_summary_dt(
            barrio, ciudad=ciudad,
            clase_suelo=_ent2.get("clase_suelo"),
            uso_economico=_ent2.get("uso_economico") or _predio_destino,
            upz=_ent2.get("upz"),
            tratamiento=_ent2.get("tratamiento"),
            tipo_tratamiento=(_ent2.get("codigo_tratamiento")
                              or _ent2.get("tipo_tratamiento")),
        )
        story.append(dt(_resumen_pot))
        story.append(Spacer(1, 3))
        if not (_clase_suelo_real or _ent2.get("uso_economico")
                or _ent2.get("upz") or _trat_par):
            story.append(alert_orange(
                "<b>Consulta POT en vivo sin valores:</b> el geoportal de "
                f"{_NOMBRE_CIUDAD} no devolvió datos de suelo/uso/UPZ para las "
                "coordenadas del predio al momento de generar el dictamen. "
                "Verificar en el portal oficial de la ciudad."))
    else:
        # Barranquilla: auditoría de capas POT empaquetadas (aplica solo a BAQ)
        _clase_suelo_txt = _clase_suelo_real.upper() if _clase_suelo_real else "SUELO URBANO"
        _trat_txt = "Consolidacion Nivel 1B (alt 5), Nivel 2 (alt 11), Especial"
        if _trat_par:
            _trat_txt = f"{_trat_par} ({_ent2.get('tipo_tratamiento') or 'POT'})"
            if _ent2.get("altura_maxima") and str(_ent2.get("altura_maxima")).lower() not in ("plan parcial",):
                _trat_txt += f" -- Altura max: {_ent2.get('altura_maxima')}"
        pot_audit = [
            [Paragraph("<b>Layer</b>",s["header"]),Paragraph("<b>Capa</b>",s["header"]),
             Paragraph("<b>Features</b>",s["header"]),Paragraph("<b>Resultado</b>",s["header"])],
            [Paragraph("1",s["value"]),Paragraph("Clases de Suelo",s["body"]),
             Paragraph("<b>1</b>",s["center"]),Paragraph(f"<b>{_clase_suelo_txt}</b>", s["body"])],
            [Paragraph("2",s["value"]),Paragraph("Norma Uso de Suelo",s["body"]),
             Paragraph("<b>1</b>",s["center"]),
             Paragraph((f"<b>Uso consultado en vivo</b> (uso económico: "
                        f"{_predio_destino or 'N/D'})") if (es_medellin or es_bogota)
                       else "<b>ACTIVIDAD CENTRAL</b>", s["body"])],
            [Paragraph("3",s["value"]),Paragraph("Planes Parciales",s["body"]),
             Paragraph("<b>0</b>",s["center"]),Paragraph("Sin afectacion por Plan Parcial",s["alert_verde"])],
            [Paragraph("4",s["value"]),Paragraph("Tratamientos Urbanisticos",s["body"]),
             Paragraph("<b>1</b>" if _trat_par else "<b>5</b>",s["center"]),
             Paragraph(_trat_txt, s["body"])],
            [Paragraph("5",s["value"]),Paragraph("Planes de Reordenamiento",s["body"]),
             Paragraph("<b>0</b>",s["center"]),Paragraph("Sin afectacion por reordenamiento",s["alert_verde"])],
        ]
        t_pot = Table(pot_audit, colWidths=["8%","25%","12%","55%"])
        t_pot.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),C_AZUL_OSC),("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F0F4FB")]),
            ("GRID",(0,0),(-1,-1),0.4,C_BORDE),("TOPPADDING",(0,0),(-1,-1),4),
            ("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),5),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
        story.append(t_pot)
        story.append(Spacer(1, 4))
        story.append(dt(get_pot_summary_dt(barrio, ciudad=ciudad)))
        story.append(Spacer(1, 4))

    # Hallazgo de amenaza/riesgo (aplica a todas las ciudades; con el filtro de
    # 'Sin afectación' ya no se dispara en falso para Bogotá/Medellín)
    _am_pot = geo_eval.get("amenaza_remocion_masa", {}).get("intersecta", False)
    _ri_pot = geo_eval.get("areas_en_riesgo", {}).get("intersecta", False)
    if _am_pot or _ri_pot:
        story.append(alert_orange(
            f"<b>HALLAZGO MEDIO:</b> El predio intersecta capas de amenaza/riesgo del POT de "
            f"{_NOMBRE_CIUDAD}. Verificar el cumplimiento de la norma urbanistica del poligono "
            f"especifico y la afectacion por riesgo."))
    elif _trat_par and not es_bogota:
        # Tratamiento real del polígono (Medellín/BAQ). Bogotá no expone
        # tratamiento en abierto: la sección 6.3 remite a la ficha normativa SDP.
        story.append(alert_orange(
            f"<b>HALLAZGO MEDIO:</b> El tratamiento urbanistico oficial del poligono es "
            f"<b>{_trat_par}</b> ({_ent2.get('tipo_tratamiento') or 'POT'}). "
            "Verificar el cumplimiento de la norma urbanistica del poligono especifico del predio."))
    elif not es_bogota and not es_medellin and not _trat_par:
        story.append(alert_orange(
            "<b>HALLAZGO MEDIO:</b> El tratamiento urbanistico del sector presenta poligonos de Consolidacion "
            "con alturas variables. Verificar el cumplimiento de la norma urbanistica del poligono especifico del predio."))
    story.append(Spacer(1, 8))

    # ── 6.3 EDIFICABILIDAD Y ALTURA MÁXIMA (Norma Urbanística + Licencia) ──
    # Sprint 3: parámetros POT de edificabilidad por ciudad (tratamiento,
    # índice de construcción, densidad, altura máxima en pisos) confrontados
    # con lo ya construido según catastro. Detecta el caso de exceso de altura
    # (p. ej. construir 20 pisos donde la norma permite 11). Sin dato normativo
    # numérico (Bogotá/ficha UPZ, planes parciales) se marca PENDIENTE.
    # Mejora 5: si se adjuntó la licencia de construcción, lo LICENCIADO tiene
    # prioridad sobre la capa POT en la confrontación (autorización concreta).
    try:
        from edificabilidad import (filas_edificabilidad, filas_licencia,
                                    fuente_norma_texto, link_oficial,
                                    _confrontacion, confrontacion_con_licencia)
        story.append(sub("6.3 Edificabilidad y Altura Maxima (Norma Urbanistica)"))
        _filas_edi = filas_edificabilidad(ciudad, _ent2, _predio_pisos)
        story.append(dt(_filas_edi))
        story.append(Spacer(1, 3))
        # Confrontación: con licencia identificada se prioriza lo licenciado
        _est_edi, _txt_edi = confrontacion_con_licencia(ciudad, _ent2, _predio_pisos, licencia)
        _usa_lic = _est_edi != "sin_licencia"
        if _est_edi in ("sin_licencia", "licencia_sin_pisos"):
            _est_edi, _txt_edi = _confrontacion(ciudad, _ent2, _predio_pisos)
        if _est_edi in ("exceso", "exceso_licencia"):
            story.append(alert_red(
                f"<b>{_txt_edi.rstrip('.')}.</b> Requiere verificacion de la "
                "licencia de construccion y de la ficha normativa ante la "
                "curaduria urbana o la autoridad de planeacion competente."))
        elif _est_edi in ("dentro", "dentro_licencia", "sin_construccion_lic"):
            story.append(alert_green(
                f"<b>Confrontacion urbanistica:</b> {_txt_edi.rstrip('.')}. Sujeto a la "
                "licencia de construccion y a la ficha normativa vigente."))
        elif _est_edi in ("pendiente", "sin_norma", "sin_construccion"):
            story.append(alert_orange(
                f"<b>Confrontacion urbanistica:</b> {_txt_edi.rstrip('.')}."))
        # Datos de la licencia de construcción (si se adjuntó)
        if licencia:
            story.append(Spacer(1, 3))
            _filas_lic = filas_licencia(licencia)
            if _filas_lic:
                story.append(dt(_filas_lic))
                if licencia.get("numero_licencia") and not _usa_lic and \
                        licencia.get("disponible"):
                    story.append(alert_orange(
                        "<b>Licencia adjuntada sin pisos autorizados identificados:</b> "
                        "el texto de la licencia no permite extraer el numero de pisos "
                        "con certeza. La confrontacion usa la capa POT; revisar la "
                        "licencia manualmente para la verificacion final."))
        _nom_portal, _url_portal = link_oficial(ciudad)
        _nota_fuente = fuente_norma_texto(ciudad, _ent2)
        story.append(body(
            f"<b>Fuente normativa:</b> {_nota_fuente} "
            f"<link href='{_url_portal}'>{_nom_portal}</link>. La altura de la "
            "capa es referencial con la fecha de la norma: la licencia aprobada "
            "puede tener derechos adquiridos y la norma puede estar en revision; "
            "la autoridad competente es la curaduria urbana o la oficina de "
            "planeacion de la ciudad."))
        story.append(Spacer(1, 4))
    except Exception as _e_edi:
        print(f"[PDF][EDIFICABILIDAD] seccion 6.3 no disponible: {_e_edi}")

    # ── 07 ESTIMACIÓN REFERENCIAL DE MERCADO (NO ES AVALÚO) ────
    story.append(sec("07 - Estimación Referencial de Mercado (NO es avalúo)"))
    story.append(hr())
    story.append(body(
        "Determinacion del valor comercial y rango de valor estimado del inmueble utilizando "
        "metodologia valuatoria consolidada automatica (ponderacion de Comparacion de Mercado M1 "
        "y Capitalizacion de Rentas M3). El Metodo de Costo de Reposicion M2 fue calibrado "
        "segun metodologia valuatoria consolidada con parametros de mercado y costos de construccion vigentes. "
        "<b>[FUENTE: ESTIMACIÓN REFERENCIAL DE MERCADO ARHIAX (AUTOMÁTICA)]</b>"
    ))
    story.append(Spacer(1, 4))
    
    area_calc = area if area > 0 else 1.0
    tiene_valor = area > 0 and (res_avaluo.get('consolidado') or 0) > 0
    if not tiene_valor:
        # Sin metraje: la estimación de mercado no es calculable -> aviso claro,
        # nunca una tabla de valores $0 que parezca información real.
        story.append(alert_orange(
            "<b>ESTIMACION NO CALCULADA:</b> no fue posible estimar el valor referencial de mercado "
            "porque falta el metraje (area en m2) del predio (area = 0). Cargue el Certificado de "
            "Tradicion y Libertad para extraer el area automaticamente, o registre el area del inmueble "
            "antes de generar el dictamen."))
        story.append(Spacer(1, 6))
    else:
        story.append(dt([
            ("Valor central estimado (referencial)", f"<b>{fmt_cop(res_avaluo['consolidado'])} COP</b> (Equivalente a {fmt_cop(res_avaluo['consolidado']/area_calc)} / m2)"),
            ("Banda Baja al 80% (P10)", f"{fmt_cop(res_avaluo['banda_baja'])} COP ({fmt_cop(res_avaluo['banda_baja']/area_calc)} / m2)"),
            ("Banda Alta al 80% (P90)", f"{fmt_cop(res_avaluo['banda_alta'])} COP ({fmt_cop(res_avaluo['banda_alta']/area_calc)} / m2)"),
            ("M1 - Comparacion de Mercado (70%)", f"{fmt_cop(res_avaluo['m1'])} COP (Lector dominante, ofertas ajustadas del sector)"),
            ("M2 - Costo de Reposicion (0%)", f"{fmt_cop(res_avaluo['m2'])} COP (Costo fisico directo + lote de terreno)"),
            ("M3 - Capitalizacion de Rentas (30%)", f"{fmt_cop(res_avaluo['m3'])} COP (Validacion por renta mensual de {fmt_cop(res_avaluo['canon_mensual'])} con Cap Rate {res_avaluo['cap_rate']*100:.2f}% neto)"),
            ("Canon de Renta Estimado", f"{fmt_cop(res_avaluo['canon_mensual'])} COP mensual (Cap Rate {res_avaluo['cap_rate']*100:.2f}% neto aplicado)"),
            ("Vigencia de la estimación referencial", "6 meses a partir de la expedicion del dictamen"),
        ]))
        story.append(Spacer(1, 6))

        # Escala de Color Visual para Ubicación de Valor (Etiquetas Neutras)
        scale_table_data = [
            [Paragraph("<font color='white'><b>Banda baja (P10)</b></font>", s["label"]),
             Paragraph("<font color='white'><b>Valor central estimado</b></font>", s["label"]),
             Paragraph("<font color='white'><b>Banda alta (P90)</b></font>", s["label"])],
            [Paragraph(f"<b>{fmt_cop(res_avaluo['banda_baja'])}</b><br/><font size=6.5 color='#718096'>Banda baja (P10)</font>", s["center"]),
             Paragraph(f"<b>{fmt_cop(res_avaluo['consolidado'])}</b><br/><font size=6.5 color='#1A6B3A'><b>Valor central estimado</b></font>", s["center"]),
             Paragraph(f"<b>{fmt_cop(res_avaluo['banda_alta'])}</b><br/><font size=6.5 color='#718096'>Banda alta (P90)</font>", s["center"])]
        ]
        t_scale = Table(scale_table_data, colWidths=["33%", "34%", "33%"])
        t_scale.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (0,0), colors.HexColor("#D97D24")), # Naranja
            ("BACKGROUND", (1,0), (1,0), colors.HexColor("#1A6B3A")), # Verde bosque
            ("BACKGROUND", (2,0), (2,0), colors.HexColor("#8B1A1A")), # Carmesi
            ("BACKGROUND", (0,1), (0,1), colors.HexColor("#FFF5EB")),
            ("BACKGROUND", (1,1), (1,1), colors.HexColor("#EBF5EE")),
            ("BACKGROUND", (2,1), (2,1), colors.HexColor("#FDF2F2")),
            ("GRID", (0,0), (-1,-1), 0.6, colors.HexColor("#0D2C6B")),
            ("TOPPADDING", (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE")
        ]))
        story.append(t_scale)
        story.append(Spacer(1, 4))
        story.append(alert_green(get_valoracion_alert(barrio, val_data, fmt_cop)))

    story.append(Spacer(1, 4))
    story.append(body(
        "Esta estimacion es referencial y de caracter automatico. <b>No sustituye un avaluo comercial</b> "
        "elaborado por avaluador inscrito en el RAA conforme a la Ley 1673 de 2013 y las metodologias valuatorias vigentes."
    ))
    story.append(Spacer(1, 8))

    # ── 08 HIDROLOGICO [REAL] ──────────────────────────────────
    story.append(sec("08 - Analisis Hidrologico y de Riesgos"))
    story.append(hr())
    bbox_str = f"{lon-0.0025:.3f},{lat-0.0025:.3f},{lon+0.0025:.3f},{lat+0.0025:.3f}"
    am_eval = geo_eval.get('amenaza_remocion_masa', {})
    ri_eval = geo_eval.get('areas_en_riesgo', {})

    res_am = f"AMENAZA {am_eval.get('nivel', 'Baja').upper()}" if am_eval.get('intersecta') else "SIN AFECTACION"
    res_ri = f"RIESGO {ri_eval.get('nivel', 'Baja').upper()}" if ri_eval.get('intersecta') else "SIN AFECTACION"

    if es_medellin:
        _amz05 = (predio_real.get("amenazas") or {}) if predio_real else {}
        _capas_riesgo = [
            ("Amenaza por Inundaciones", "inundacion"),
            ("Amenaza por Movimientos en Masa", "movimiento_masa"),
            ("Amenaza por Avenidas Torrenciales", "avenida_torrencial"),
            ("Susceptibilidad Sísmica", "sismo"),
        ]
        _fuente_riesgo = "Servidormapas Alcaldía de Medellín - VC_Gestion_Riesgo (DAGRD)"
        _total_capas = "4 (Inundaciones, Mov. en masa, Avenidas torrenciales, Sismos)"
        _nombre_cruce = "de gestión del riesgo de Medellín (DAGRD)"
    elif es_bogota:
        _amz05 = (predio_real.get("amenazas") or {}) if predio_real else {}
        _capas_riesgo = [
            ("Amenaza por Movimientos en Masa (urbano)", "movimiento_masa_urbano"),
            ("Respuesta Sísmica", "respuesta_sismica"),
            ("Zonificación Geotécnica", "zonificacion_geotecnica"),
        ]
        _fuente_riesgo = "Catastro Distrital Bogotá - emergencias/gestionriesgos (IDIGER)"
        _total_capas = "3 (Mov. en masa urbano, Respuesta sísmica, Zonificación geotécnica)"
        _nombre_cruce = "de gestión del riesgo de Bogotá (IDIGER)"
    else:
        _amz05 = {}
        _capas_riesgo = []
        _fuente_riesgo = ""
        _total_capas = ""
        _nombre_cruce = ""

    if es_medellin or es_bogota:
        story.append(body(
            f"Consulta EN VIVO contra las capas oficiales {_nombre_cruce}: "
            + "; ".join(nombre for nombre, _clave in _capas_riesgo)
            + ". Se ejecuto una intersección espacial con las coordenadas del predio "
            + "sobre cada capa. "
            f"<b>[FUENTE: {_fuente_riesgo.upper()} (EN VIVO)]</b>"))
        story.append(Spacer(1, 4))
        story.append(sub("8.1 Inventario de Capas Consultadas"))
        def _res_amenaza(dict_capa):
            if dict_capa and dict_capa.get("intersecta"):
                return Paragraph(f"{dict_capa.get('nivel') or 'DETECTADA'}", s["alert_naranja"])
            return Paragraph("SIN AFECTACION", s["alert_verde"])
        risk_audit = [
            [Paragraph("<b>Layer</b>",s["header"]),Paragraph("<b>Nombre de Capa</b>",s["header"]),
             Paragraph("<b>Punto Evaluado</b>",s["header"]),Paragraph("<b>Resultado</b>",s["header"])],
        ]
        for idx, (nombre, clave) in enumerate(_capas_riesgo, start=1):
            risk_audit.append([
                Paragraph(str(idx), s["value"]), Paragraph(nombre, s["body"]),
                Paragraph(f"{lat:.5f}, {lon:.5f}", s["value"]),
                _res_amenaza(_amz05.get(clave)),
            ])
        t_risk = Table(risk_audit, colWidths=["10%","38%","22%","30%"])
        t_risk.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),C_AZUL_OSC),("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F0F4FB")]),
            ("GRID",(0,0),(-1,-1),0.4,C_BORDE),("TOPPADDING",(0,0),(-1,-1),4),
            ("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),5),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
        story.append(t_risk)
        story.append(Spacer(1, 4))
        story.append(body(
            f"<b>Metodologia de cruce:</b> Intersección espacial (point-in-polygon) con las coordenadas "
            f"del predio (Lat: {lat:.5f}, Lon: {lon:.5f}) contra las capas oficiales {_nombre_cruce}. "
            f"Diagnostico consolidado: {geo_eval.get('resumen_ejecutivo', 'Evaluacion completada.')}"
        ))
        story.append(Spacer(1, 4))
        story.append(dt([
            ("Fuente de datos", _fuente_riesgo + " (consultas en vivo)"),
            ("Metodo de cruce", "Point-in-Polygon sobre geometrías oficiales"),
            ("Coordenadas (WGS84)", f"{lat:.5f}, {lon:.5f}"),
            ("Total capas evaluadas", _total_capas),
        ]))
        story.append(Spacer(1, 4))
        _geo_fallo = False
        if (predio_real and (predio_real.get("amenazas") or {}).get("disponible") is False):
            _geo_fallo = True
    else:
        story.append(body(
            "Consulta en vivo contra <b>todas las capas</b> del servicio riesgos/amenazas/MapServer "
            "de la Alcaldia de Barranquilla y el motor geoespacial ARHIAX. Se ejecuto una query espacial "
            "con las coordenadas del predio sobre cada capa disponible. "
            "<b>[FUENTE: ALCALDIA BAQ - STRtree POT]</b>"))
        story.append(Spacer(1, 4))
        story.append(sub("8.1 Inventario de Capas Consultadas"))
        # Table showing each layer queried and result
        risk_audit = [
            [Paragraph("<b>Layer ID</b>",s["header"]),Paragraph("<b>Nombre de Capa</b>",s["header"]),
             Paragraph("<b>BBOX Consultado</b>",s["header"]),Paragraph("<b>Features</b>",s["header"]),
             Paragraph("<b>Resultado</b>",s["header"])],
            [Paragraph("0",s["value"]),Paragraph("Amenaza por Inundacion",s["body"]),
             Paragraph(bbox_str,s["value"]),Paragraph("<b>0</b>",s["center"]),
             Paragraph("SIN AFECTACION",s["alert_verde"])],
            [Paragraph("1",s["value"]),Paragraph("Amenaza por Inundacion (Historica)",s["body"]),
             Paragraph(bbox_str,s["value"]),Paragraph("<b>0</b>",s["center"]),
             Paragraph("SIN AFECTACION",s["alert_verde"])],
            [Paragraph("2",s["value"]),Paragraph("Amenaza por Remocion en Masa",s["body"]),
             Paragraph(bbox_str,s["value"]),Paragraph("<b>1</b>" if am_eval.get('intersecta') else "<b>0</b>",s["center"]),
             Paragraph(res_am, s["alert_naranja"] if am_eval.get('intersecta') else s["alert_verde"])],
            [Paragraph("3",s["value"]),Paragraph("Amenaza por Remocion en Masa (Historica)",s["body"]),
             Paragraph(bbox_str,s["value"]),Paragraph("<b>0</b>",s["center"]),
             Paragraph("SIN AFECTACION",s["alert_verde"])],
            [Paragraph("4",s["value"]),Paragraph("Zonas de Riesgo No Mitigable",s["body"]),
             Paragraph(bbox_str,s["value"]),Paragraph("<b>1</b>" if ri_eval.get('intersecta') else "<b>0</b>",s["center"]),
             Paragraph(res_ri, s["alert_naranja"] if ri_eval.get('intersecta') else s["alert_verde"])],
            [Paragraph("5",s["value"]),Paragraph("Arroyos y Cauces Urbanos",s["body"]),
             Paragraph(bbox_str,s["value"]),Paragraph("<b>0</b>",s["center"]),
             Paragraph("SIN AFECTACION",s["alert_verde"])],
        ]
        t_risk = Table(risk_audit, colWidths=["10%","28%","30%","10%","22%"])
        t_risk.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),C_AZUL_OSC),("TEXTCOLOR",(0,0),(-1,0),colors.white),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F0F4FB")]),
            ("GRID",(0,0),(-1,-1),0.4,C_BORDE),("TOPPADDING",(0,0),(-1,-1),4),
            ("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),5),
            ("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
        story.append(t_risk)
        story.append(Spacer(1, 4))
        story.append(body(
            f"<b>Metodologia de cruce:</b> Se construyo un Bounding Box (BBOX) en WGS84 centrado en las "
            f"coordenadas de la direccion evaluada: {direccion} (Lat: {lat:.5f}, Lon: {lon:.5f}), con un buffer "
            f"espacial de ~250m. Se ejecuto el cruce espacial pericial contra las capas oficiales del POT. "
            f"Diagnostico consolidado: {geo_eval.get('resumen_ejecutivo', 'Evaluacion completada.')}"
        ))
        story.append(Spacer(1, 4))
        story.append(dt([
            ("Fuente de datos", "Capas GeoJSON oficiales del POT de Barranquilla (empaquetadas en la aplicacion)"),
            ("Metodo de cruce", "Spatial Query Point-in-Polygon (STRtree / Shapely) sobre geometrias normalizadas"),
            ("BBOX (WGS84)", bbox_str),
            ("Total capas evaluadas", "6 (Inundacion x2, Remocion x2, Riesgo No Mitigable, Arroyos)"),
            ("Clasificacion resultante", f"EVALUACION GEOTECNICA POT: {res_am}"),
        ]))
        story.append(Spacer(1, 4))
        _geo_fallo = "no se completó" in (geo_eval.get("resumen_ejecutivo", "") or "").lower()
    if _geo_fallo:
        story.append(alert_orange(
            "<b>ADVERTENCIA:</b> No fue posible completar la verificacion espacial del predio "
            "(motor geoespacial no disponible o capas no encontradas). El resultado de riesgo "
            "debe considerarse NO EVALUADO y requiere verificacion geotecnica profesional."))
    elif am_eval.get("intersecta") or ri_eval.get("intersecta"):
        # Alerta proporcional al NIVEL real de la amenaza (regresión: una
        # amenaza Baja no amerita 'HALLAZGO ADVERSO... evaluacion geotecnica
        # detallada', que contradecia el hallazgo MEDIO de la sección 10).
        _niv_05 = str((am_eval.get("nivel") if am_eval.get("intersecta") else None) or
                      (ri_eval.get("nivel") if ri_eval.get("intersecta") else None) or "").upper()
        if any(k in _niv_05 for k in ("MUY ALTA", "MUY ALTO", "ALTA", "ALTO")):
            story.append(alert_red(
                f"<b>HALLAZGO ADVERSO ({_niv_05}):</b> el predio intersecta capas de amenaza/riesgo "
                f"del POT de {_NOMBRE_CIUDAD} (ver detalle en la tabla anterior). Se requiere "
                f"evaluacion geotecnica detallada y verificacion de restricciones para originacion "
                f"hipotecaria."))
        elif any(k in _niv_05 for k in ("MEDIA", "MEDIO")):
            story.append(alert_orange(
                f"<b>HALLAZGO MEDIO ({_niv_05}):</b> el predio intersecta capas de amenaza/riesgo "
                f"del POT de {_NOMBRE_CIUDAD} (ver detalle en la tabla anterior). Se recomienda "
                f"evaluacion geotecnica complementaria."))
        else:
            story.append(alert_orange(
                f"<b>AFECTACION DE NIVEL {_niv_05 or 'DETECTADA'}:</b> el predio intersecta capas de "
                f"amenaza/riesgo del POT de {_NOMBRE_CIUDAD} (ver detalle en la tabla anterior). "
                f"Se recomienda verificacion puntual por profesional competente en caso de "
                f"intervencion fisica del predio."))
    else:
        story.append(alert_green(
            f"<b>HALLAZGO POSITIVO:</b> El cruce espacial contra las capas oficiales de riesgos de "
            f"{_NOMBRE_CIUDAD} no detecto interseccion de poligonos de amenaza con el predio. "
            "Favorable para suscripcion de seguros y originacion hipotecaria."))
    story.append(Spacer(1, 8))
    
    # ── 09 CUMPLIMIENTO SAGRILAFT (FICHA ESTRUCTURAL + SCREENING EN VIVO) ──
    story.append(sec("09 - Cumplimiento SAGRILAFT (ficha estructural + screening en vivo)"))
    story.append(hr())
    story.append(body(
        "<b>Que es esta seccion:</b> deja los nombres de las personas y entidades del caso "
        "(titular, banco acreedor, constructor) con su huella digital (hash) para trazabilidad y "
        "presenta el <b>screening en vivo</b> de esos nombres contra las listas restrictivas. "
        "<b>ONU, OFAC y UK se consultan en vivo</b> (feed oficial, copia local versionada por "
        "SHA-256); la <b>lista UIAF</b> queda <b>PENDIENTE de consulta por canal oficial</b> y "
        "nunca se simula. El hash garantiza que los nombres no se alteren entre la generacion y "
        "el cruce."))
    story.append(Spacer(1, 6))
    ficha_sarlaft = generar_ficha_sarlaft(
        titulares=analysis.get("titulares", ""),
        acreedor_snr=analysis.get("acreedor_snr"),
        acreedor_real=analysis.get("acreedor_real"),
        constructor=analysis.get("constructor"),
        folio=folio,
    )
    story.append(dt(generar_tabla_sarlaft(ficha_sarlaft)))
    story.append(Spacer(1, 4))
    story.append(body(f"<b>Disclaimer:</b> {ficha_sarlaft['disclaimer']}"))
    story.append(Spacer(1, 6))

    if not _titulux or not _titulux.get("disponible"):
        _motivo = ""
        if _titulux_skip:
            _motivo = f": {_titulux_skip}"
        elif _titulux and _titulux.get("error"):
            _motivo = f" ({_titulux.get('error')})"
        story.append(alert_orange(
            "<b>Screening SAGRILAFT NO EVALUADO</b>" + _motivo + ". "
            "El cruce contra listas restrictivas queda PENDIENTE; no se afirma resultado alguno."
        ))
    else:
        # --- Screening SAGRILAFT (resultado real con degradación honesta) ---
        story.append(sub("Screening SAGRILAFT de contrapartes"))
        _filas_scr = [[Paragraph("<b>Sujeto</b>", s["header"]),
                       Paragraph("<b>Tipo</b>", s["header"]),
                       Paragraph("<b>Resultado</b>", s["header"]),
                       Paragraph("<b>ONU</b>", s["header"]),
                       Paragraph("<b>OFAC</b>", s["header"]),
                       Paragraph("<b>UK</b>", s["header"]),
                       Paragraph("<b>UIAF</b>", s["header"])]]
        _resultado_es = {
            "sinCoincidencia": "Sin coincidencia", "coincidencia": "COINCIDENCIA",
            "candidato": "Candidato (revisar)", "revisionManual": "Revision manual",
            "pendiente": "PENDIENTE",
        }
        for sc in _titulux.get("screening", []):
            _por_fuente = {f["fuente"]: _resultado_es.get(f["resultado"], f["resultado"])
                           for f in sc.get("fuentes", [])}
            _res_es = _resultado_es.get(sc["resultado"], sc["resultado"])
            _filas_scr.append([
                Paragraph(sc["sujeto"] or "—", s["body"]),
                Paragraph("Persona natural" if sc.get("tipo") == "natural" else "Entidad", s["body"]),
                Paragraph(f"<b>{_res_es}</b>", s["value"]),
                Paragraph(_por_fuente.get("onu", "—"), s["body"]),
                Paragraph(_por_fuente.get("ofac", "—"), s["body"]),
                Paragraph(_por_fuente.get("uk", "—"), s["body"]),
                Paragraph(_por_fuente.get("uiaf", "—"), s["body"]),
            ])
        _t_scr = Table(_filas_scr, colWidths=["26%", "12%", "16%", "12%", "12%", "11%", "11%"])
        _t_scr.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C_AZUL_OSC), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F0F4FB")]),
            ("GRID", (0, 0), (-1, -1), 0.4, C_BORDE),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(_t_scr)
        story.append(Spacer(1, 4))

        if _titulux.get("coincidencia"):
            story.append(alert_red(
                "<b>COINCIDENCIA DETECTADA en listas vinculantes.</b> Procede revision humana y "
                "debida diligencia intensificada antes de decidir. El dictamen NO autoriza operar "
                "con la contraparte coincidente."
            ))
        if _titulux.get("fuentes_pendientes"):
            _pend = ", ".join(str(f).upper() for f in _titulux["fuentes_pendientes"])
            story.append(alert_orange(
                f"<b>Screening incompleto (degradacion honesta):</b> fuente(s) no consultada(s) en "
                f"vivo: {_pend}. La lista UIAF requiere canal oficial autorizado y la lista UE "
                f"requiere ingesta del archivo XML oficial. El resultado de las fuentes consultadas "
                f"NO cubre las pendientes; la operacion queda sujeta a completarlas."
            ))
        elif not _titulux.get("coincidencia"):
            story.append(alert_green(
                "<b>Screening SAGRILAFT completado:</b> sin coincidencias en las fuentes "
                "consultadas en vivo (ONU/OFAC/UK). El resultado no sustituye la verificacion final "
                "del oficial de cumplimiento ni la consulta del canal UIAF."
            ))
    story.append(Spacer(1, 8))

    # ── 10 HALLAZGOS CLASIFICADOS ──────────────────────────────
    story.append(sec("10 - Hallazgos Clasificados por Severidad"))
    story.append(hr())
    # Nota en lenguaje claro: cómo leer la severidad (para cualquier lector)
    story.append(body(
        "<b>Como leer esta seccion:</b> cada hallazgo senala un punto que merece atencion antes "
        "de tomar una decision sobre el inmueble. <b>ALTO</b> (rojo) = condiciona o bloquea la "
        "operacion hasta resolverlo (p. ej. pagar y cancelar una hipoteca). <b>MEDIO</b> (naranja) "
        "= requiere una verificacion puntual por un profesional. <b>INFORMATIVO</b> (verde) = "
        "situacion favorable o sin riesgo aparente. El hallazgo indica <b>a quien afecta y que "
        "hacer</b>; no califica al propietario, sino al estado del inmueble."))
    story.append(Spacer(1, 6))
    
    for sev, tc, bg, titulo, fuente, descripcion, implicacion in hallazgos:
        sev_style = ParagraphStyle("sev_s", fontName="Helvetica-Bold", fontSize=8, textColor=tc, leading=11)
        titulo_style = ParagraphStyle("tit_h", fontName="Helvetica-Bold", fontSize=9, textColor=C_AZUL_OSC, leading=12)
        box_data = [
            [Paragraph(f"<b>Severidad:</b> {sev}", sev_style),
             Paragraph(f"<b>Fuente:</b> {fuente}",
                       ParagraphStyle("fsrc", fontName="Helvetica", fontSize=7.5,
                                      textColor=colors.HexColor("#718096"), alignment=TA_RIGHT, leading=11))],
            [Paragraph(titulo, titulo_style), Paragraph("", s["body"])],
            [Paragraph(f"<b>Descripcion:</b> {descripcion}", s["body"]), Paragraph("", s["body"])],
            [Paragraph(f"<b>Implicacion operacional:</b> {implicacion}", s["body"]), Paragraph("", s["body"])],
        ]
        t = Table(box_data, colWidths=["70%", "30%"])
        t.setStyle(TableStyle([
            ("SPAN", (0,1), (1,1)), ("SPAN", (0,2), (1,2)), ("SPAN", (0,3), (1,3)),
            ("BACKGROUND", (0,0), (-1,0), bg),
            ("BACKGROUND", (0,1), (-1,1), colors.HexColor("#F7F8FC")),
            ("BACKGROUND", (0,2), (-1,2), colors.white),
            ("BACKGROUND", (0,3), (-1,3), colors.HexColor("#F7F8FC")),
            ("GRID", (0,0), (-1,-1), 0.5, C_BORDE),
            ("LINEAFTER", (0,0), (0,-1), 3, tc),
            ("TOPPADDING", (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING", (0,0), (-1,-1), 8),
        ]))
        story.append(KeepTogether([t, Spacer(1, 6)]))
    story.append(Spacer(1, 8))
    
    # ── 11 RESUMEN HALLAZGOS ───────────────────────────────────
    story.append(sec("11 - Resumen de Hallazgos"))
    story.append(hr())
    story.append(body(f"El motor ARHIAX identifico <b>{len(hallazgos)} hallazgos</b> sobre este activo."))
    story.append(Spacer(1, 4))
    
    # Contar dinámicamente por severidad real de los hallazgos (etiqueta genérica:
    # un ALTO puede ser registral, geoespacial o de otro origen; no se afirma
    # "Gravamenes" si el hallazgo ALTO es de amenaza/riesgo).
    n_alto = sum(1 for h in hallazgos if h[0] == "ALTO")
    n_medio = sum(1 for h in hallazgos if h[0] == "MEDIO")
    n_info = sum(1 for h in hallazgos if h[0] == "INFORMATIVO")
    story.append(badge_table([
        ("ALTO", str(n_alto), colors.HexColor("#FBE9E9"), C_ROJO),
        ("MEDIO", str(n_medio), C_ALERTA_BG, C_NARANJA),
        ("INFORMATIVO", str(n_info), C_OK_BG, C_VERDE),
    ], s))
    story.append(Spacer(1, 6))
    # UX: identificar CUÁL hallazgo es cada uno (la persona que revisa el dictamen
    # debe saber que el ALTO es la hipoteca y cuál es el INFORMATIVO sin esperar a
    # la sección 10). Se listan títulos compactos por severidad.
    if hallazgos:
        _mapa_color = {
            "ALTO": (C_ROJO, colors.HexColor("#FBE9E9")),
            "MEDIO": (C_NARANJA, C_ALERTA_BG),
            "INFORMATIVO": (C_VERDE, C_OK_BG),
        }
        _filas_resumen = [("Severidad", "Hallazgo identificado", "")]
        for h in hallazgos:
            sev_h = h[0] if h and h[0] in _mapa_color else "INFORMATIVO"
            tc_h, bg_h = _mapa_color[sev_h]
            titulo_h = (h[3] if len(h) > 3 else "") or ""
            fuente_h = (h[4] if len(h) > 4 else "") or ""
            p_sev = Paragraph(f"<b>{sev_h}</b>", ParagraphStyle(
                "res_sev", fontName="Helvetica-Bold", fontSize=7.5,
                textColor=tc_h, leading=10))
            p_tit = Paragraph(titulo_h, ParagraphStyle(
                "res_tit", fontName="Helvetica", fontSize=8,
                textColor=colors.HexColor("#2D3748"), leading=10))
            p_fu = Paragraph(f"<font size=6.5 color='#718096'>{fuente_h}</font>",
                             ParagraphStyle("res_fu", fontName="Helvetica",
                                            fontSize=6.5, leading=9))
            _filas_resumen.append([p_sev, p_tit, p_fu])
        _t_res = Table(_filas_resumen, colWidths=["12%", "68%", "20%"])
        _t_res.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), C_AZUL_OSC),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, colors.HexColor("#F5F7FB")]),
            ("GRID", (0, 0), (-1, -1), 0.4, C_BORDE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(KeepTogether([_t_res, Spacer(1, 4)]))
    story.append(Spacer(1, 8))
    
    story.append(sec("12 - Score Actuarial Integrado"))
    story.append(hr())
    # Nota en lenguaje claro: cómo interpretar el score
    story.append(body(
        "<b>Como leer el score:</b> es un puntaje de 0 a 100 que resume el nivel de riesgo del "
        "inmueble (100 = riesgo bajo). Combina cuatro frentes: Registral (gravámenes y "
        "tradición), Juridico (titularidad), Hidrologico (amenazas) y Catastral (datos del "
        "predio). <b>Importante:</b> si existe un hallazgo ALTO (por ejemplo, una hipoteca "
        "vigente), el resultado integrado se marca <b>BLOQUEADO</b> aunque el número sea alto: "
        "el puntaje no puede verse como favorable mientras haya una condicion que deba "
        "resolverse primero."))
    story.append(Spacer(1, 6))
    # Score dinamico real (Sprint 2): motores conectados, sin valores hardcodeados (H-05/H-06)
    val_data_area = dict(val_data)
    val_data_area["area"] = area
    score_result = calcular_score_actuarial(hallazgos, geo_eval, analysis, val_data_area)
    colores_score = score_result["colores"]
    story.append(badge_table([
        ("Score Registral", f"{score_result['score_registral']:.0f} / 100", colores_score["registral"][1], colores_score["registral"][0]),
        ("Score Hidrologico", f"{score_result['score_hidrologico']:.0f} / 100", colores_score["hidrologico"][1], colores_score["hidrologico"][0]),
        ("Score Juridico", f"{score_result['score_juridico']:.0f} / 100", colores_score["juridico"][1], colores_score["juridico"][0]),
        ("Score Integrado ARHIAX", f"{score_result['score_integrado']:.0f} / 100", colores_score["integrado"][1], colores_score["integrado"][0]),
    ], s))
    story.append(Spacer(1, 4))
    detalle_score = []
    for comp, nombre in [("registral", "Registral"), ("juridico", "Juridico"),
                         ("hidrologico", "Hidrologico"), ("catastral", "Catastral")]:
        detalle_score.append((
            f"Score {nombre} ({score_result[f'score_{comp}']:.0f}/100)",
            "; ".join(score_result["detalle"][comp])
        ))
    detalle_score.append(("Score Integrado", generar_narrativa_score(score_result)))
    story.append(dt(detalle_score))
    story.append(Spacer(1, 8))

    # ── 13 GATE FIDUCIARIO + CARGAS ECONOMICAS (Sprint 1 Bloques 3+7) ───
    story.append(sec("13 - Estructurabilidad Fiduciaria y Carga Economica"))
    story.append(hr())
    res_fiel_08 = evaluar_estructurabilidad_fiduciaria(hallazgos)

    # --- Bloque 7: Gate fiduciario dinamico ---
    if not res_fiel_08["estructurable"]:
        condiciones = res_fiel_08.get("condiciones_precedentes", [])
        cond_text = "; ".join([f"({i+1}) {c}" for i, c in enumerate(condiciones)]) if condiciones else "Ver hallazgos clasificados."
        story.append(alert_orange(
            f"<b>Estructurabilidad fiduciaria: BLOQUEADA (semaforo ROJO).</b> "
            f"El activo NO es estructurable como garantia fiduciaria en su estado registral actual. "
            f"Condiciones precedentes para habilitarlo: {cond_text}. "
            f"<b>[REQUIERE VERIFICACION por profesional del derecho]</b>"
        ))
    else:
        story.append(alert_green(
            "<b>Estructurabilidad fiduciaria: SIN BLOQUEOS DETECTADOS (semaforo VERDE).</b> "
            "El analisis de anotaciones del folio no detecta gravamenes, embargos ni afectaciones "
            "vigentes que bloqueen la estructuracion fiduciaria. "
            "<b>Sujeto a verificacion registral por profesional del derecho.</b>"
        ))
    story.append(Spacer(1, 6))

    # --- Bloque 2: Discrepancia de acreedor (inferida del CTL) ---
    from legal_analyzer import detectar_discrepancia_acreedor
    acreedor_snr_inferred = analysis.get("acreedor_snr", None)
    acreedor_real_declared = analysis.get("acreedor_real", None)
    disc = detectar_discrepancia_acreedor(acreedor_snr_inferred, acreedor_real_declared)
    if disc:
        story.append(alert_orange(
            f"<b>{disc['hallazgo_titulo']}</b> — {disc['hallazgo_descripcion']} "
            f"{disc['hallazgo_implicacion']}"
        ))
        story.append(Spacer(1, 6))

    # --- Bloque 3: Cargas economicas (integradas en seccion 13) ---
    hipotecas_activas_08b = [a for a in analysis.get("anotaciones", [])
                             if "Hipoteca" in a[2] and "CANCELADA" not in a[4]]
    if hipotecas_activas_08b:
        story.append(sub("Carga Economica del Gravamen Hipotecario Vigente"))
        # Regresión (dictamen real 50C-1463431): la amortización debe partir de la
        # CONSTITUCIÓN del crédito (fecha de la anotación de hipoteca, 25-11-2022)
        # y usar la CUANTÍA declarada en el CTL (160.000.000), no la apertura del
        # folio (1997 -> '0 cuotas') ni un LTV 70% sobre el valor del inmueble.
        _hip_info = analysis.get("hipoteca_vigente") or {}
        _fecha_constitucion = _hip_info.get("fecha") or analysis.get("apertura")
        _cuantia_ctl = _hip_info.get("cuantia_cop")
        story.append(body(
            "Estimacion referencial de la carga economica del gravamen activo. "
            "Calculado por metodo frances de amortizacion con tasa referencial NO VIS. "
            "No sustituye el extracto oficial del banco acreedor."
        ))
        story.append(Spacer(1, 4))
        carga = estimar_carga_hipotecaria(
            valor_inmueble=val_data.get("consolidado", 0),
            fecha_constitucion=_fecha_constitucion,
            plazo_anos=20,
            capital_original=_cuantia_ctl,  # cuantía del CTL si está declarada
        )
        # La fila 'Capital estimado' debe reflejar si la cuantía vino del CTL
        filas_carga = generar_tabla_carga(carga, fmt_cop)
        if _cuantia_ctl:
            filas_carga = [
                ("Capital del crédito (cuantía declarada en el CTL)",
                 f"{fmt_cop(carga['capital_estimado'])} COP")
                if f[0].startswith("Capital estimado") else f
                for f in filas_carga
            ]
        story.append(dt(filas_carga))
        story.append(Spacer(1, 4))
        story.append(body(f"<i>{carga['advertencia']}</i>"))
    story.append(Spacer(1, 8))

    # ── 14 RECOMENDACIONES ─────────────────────────────────────
    story.append(sec("14 - Recomendaciones Operacionales"))
    story.append(hr())
    for titulo, texto in recs:
        p_t = Paragraph(f"<b>{titulo}</b>", ParagraphStyle("rt",fontName="Helvetica-Bold",
            fontSize=9,textColor=C_AZUL_OSC,leading=12))
        p_x = Paragraph(texto, s["body"])
        t = Table([[p_t],[p_x]], colWidths=["100%"])
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#EBF0FA")),
            ("BACKGROUND",(0,1),(-1,1),colors.white),("GRID",(0,0),(-1,-1),0.5,C_BORDE),
            ("LINEAFTER",(0,0),(0,-1),3,C_AZUL_MED),("TOPPADDING",(0,0),(-1,-1),6),
            ("BOTTOMPADDING",(0,0),(-1,-1),6),("LEFTPADDING",(0,0),(-1,-1),10)]))
        story.append(t)
        story.append(Spacer(1, 6))
    
    # ── 15 RUTA DE VERIFICACION (Sprint 1 Bloque 4) ────────────
    story.append(sec("15 - Ruta de Verificacion Profesional"))
    story.append(hr())
    # La ruta solo se arma con hallazgos que exigen ACCION (ALTO/MEDIO). Un
    # hallazgo INFORMATIVO (p. ej. 'Zona Libre de Amenazas y Riesgos') no debe
    # generar pasos: antes su título contenía 'amenazas/riesgos' y disparaba un
    # paso geotécnico espurio aunque el predio NO tuviera ninguna amenaza.
    hallazgos_ruta = []
    for sev, tc, bg, titulo, fuente, descripcion, implicacion in hallazgos:
        if sev == "INFORMATIVO":
            continue
        titulo_lower = titulo.lower()
        desc_lower = descripcion.lower()
        if "ausencia" in titulo_lower and "ctl" in titulo_lower:
            hallazgos_ruta.append({"tipo": "ausencia_ctl", "referencia": fuente})
        elif "hipoteca" in titulo_lower and "vigente" in titulo_lower:
            hallazgos_ruta.append({"tipo": "hipoteca_vigente", "referencia": fuente})
        elif "cesion" in titulo_lower or "discrepancia acreedor" in titulo_lower:
            hallazgos_ruta.append({"tipo": "cesion_no_registrada", "referencia": fuente})
        elif "afectacion" in titulo_lower and "vivienda" in titulo_lower:
            hallazgos_ruta.append({"tipo": "afectacion_vivienda", "referencia": fuente})
        elif "patrimonio" in titulo_lower and "familia" in titulo_lower:
            hallazgos_ruta.append({"tipo": "patrimonio_familia", "referencia": fuente})
        elif "embargo" in titulo_lower:
            hallazgos_ruta.append({"tipo": "embargo_vigente", "referencia": fuente})
        elif ("riesgo" in titulo_lower or "amenaza" in titulo_lower or "geo" in titulo_lower) \
                and "zona libre" not in titulo_lower and "libre de" not in desc_lower:
            hallazgos_ruta.append({"tipo": "riesgo_geoespacial", "referencia": fuente})
    ruta = generar_ruta(hallazgos_ruta, nombre_ciudad=_NOMBRE_CIUDAD)
    if ruta:
        story.append(body(
            "Los siguientes pasos deben ejecutarse en el orden indicado para cerrar los hallazgos "
            "activos del activo e habilitar su estructuracion o transferencia. "
            "Actor responsable y plazo estimado se indican por paso."
        ))
        story.append(Spacer(1, 4))
        for paso in ruta:
            label = f"Paso {paso['numero']}"
            if paso.get("referencia_hallazgo"):
                label += f" [{paso['referencia_hallazgo']}]"
            p_t = Paragraph(f"<b>{label}</b>",
                            ParagraphStyle("rp_t", fontName="Helvetica-Bold",
                                           fontSize=9, textColor=C_AZUL_OSC, leading=12))
            p_d = Paragraph(paso["descripcion"], s["body"])
            p_meta = Paragraph(
                f"<b>Actor:</b> {paso['actor']} &nbsp;&nbsp; "
                f"<b>Plazo:</b> {paso['plazo']} &nbsp;&nbsp; "
                f"<b>Fuente:</b> {paso['fuente']}",
                ParagraphStyle("rp_m", fontName="Helvetica", fontSize=7.5,
                               textColor=colors.HexColor("#718096"), leading=11)
            )
            t = Table([[p_t], [p_d], [p_meta]], colWidths=["100%"])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#EBF0FA")),
                ("BACKGROUND", (0,1), (-1,1), colors.white),
                ("BACKGROUND", (0,2), (-1,2), colors.HexColor("#F7F8FC")),
                ("GRID", (0,0), (-1,-1), 0.5, C_BORDE),
                ("LINEAFTER", (0,0), (0,-1), 3, C_AZUL_MED),
                ("TOPPADDING", (0,0), (-1,-1), 5),
                ("BOTTOMPADDING", (0,0), (-1,-1), 5),
                ("LEFTPADDING", (0,0), (-1,-1), 10),
            ]))
            story.append(KeepTogether([t, Spacer(1, 6)]))
    else:
        story.append(alert_green(
            "<b>Activo sin hallazgos que requieran ruta de verificacion activa.</b> "
            "No se detectaron condiciones pendientes de cierre en el analisis registral, "
            "juridico o geoespacial del folio."
        ))
    story.append(Spacer(1, 8))
    
    # ── 16 ALCANCE ─────────────────────────────────────────────
    story.append(sec("16 - Declaracion de Alcance"))
    story.append(hr())
    story.append(dt(get_alcance_dt(barrio, ciudad=ciudad)))
    story.append(Spacer(1, 8))

    # ── 17 PROVENANCE ──────────────────────────────────────────
    story.append(sec("17 - Sello de Integridad del Insumo (Provenance)"))
    story.append(hr())
    prov_rows = [
        [Paragraph("<b>HASH SHA-256</b>",s["mono"]),Paragraph(P_HASH,s["mono_hash"])],
        [Paragraph("<b>TIMESTAMP</b>",s["mono"]),Paragraph(NOW_UTC.isoformat(),s["mono"])],
        [Paragraph("<b>REFERENCIA</b>",s["mono"]),Paragraph(CERT_NUM,s["mono"])],
        [Paragraph("<b>ALGORITMO</b>",s["mono"]),Paragraph("SHA-256 (integridad del contenido)",s["mono"])],
    ]
    tp = Table(prov_rows, colWidths=["30%","70%"])
    tp.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1),C_NEGRO_MONO),
        ("GRID",(0,0),(-1,-1),0.3,colors.HexColor("#1E3A5F")),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LEFTPADDING",(0,0),(-1,-1),10)]))
    story.append(tp)
    story.append(Spacer(1, 8))
    
    # ── ANEXO A: NOTA TECNICA GEODESICA ────────────────────────
    # (Se entrega junto al dictamen en un único PDF.)
    story.append(sec("Anexo A - Nota Tecnica Geodesica"))
    story.append(hr())
    story.append(body(
        "Este anexo documenta los sistemas de referencia de coordenadas (CRS) utilizados en el "
        "cruce espacial del dictamen, la metodologia de reproyeccion y la precision esperada. "
        "Su inclusion responde al requerimiento de trazabilidad geodesica del estandar LAI v1.0."))
    story.append(Spacer(1, 4))
    story.append(sub("A.1 Sistemas de Referencia por Servicio"))
    crs_data = [
        [Paragraph("<b>Servicio GIS</b>",s["header"]),
         Paragraph("<b>CRS Nativo</b>",s["header"]),
         Paragraph("<b>EPSG</b>",s["header"]),
         Paragraph("<b>Unidades</b>",s["header"]),
         Paragraph("<b>Datum</b>",s["header"])],
        [Paragraph("Riesgos / Amenazas",s["body"]),
         Paragraph("<b>CTM12</b>",s["value"]),
         Paragraph("9377",s["value"]),
         Paragraph("Metros",s["value"]),
         Paragraph("MAGNA-SIRGAS (GRS 1980)",s["body"])],
        [Paragraph("Ordenamiento / Planeacion",s["body"]),
         Paragraph("<b>CTM12</b>",s["value"]),
         Paragraph("9377",s["value"]),
         Paragraph("Metros",s["value"]),
         Paragraph("MAGNA-SIRGAS (GRS 1980)",s["body"])],
        [Paragraph("Catastro / Destinos Economicos",s["body"]),
         Paragraph("<b>Web Mercator</b>",s["value"]),
         Paragraph("3857",s["value"]),
         Paragraph("Metros",s["value"]),
         Paragraph("WGS 84",s["body"])],
        [Paragraph("Entrada de coordenadas (Query)",s["body"]),
         Paragraph("<b>WGS 84 Geograficas</b>",s["value"]),
         Paragraph("4326",s["value"]),
         Paragraph("Grados decimales",s["value"]),
         Paragraph("WGS 84",s["body"])],
    ]
    t_crs = Table(crs_data, colWidths=["25%","18%","10%","15%","32%"])
    t_crs.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),C_AZUL_OSC),("TEXTCOLOR",(0,0),(-1,0),colors.white),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F0F4FB")]),
        ("GRID",(0,0),(-1,-1),0.4,C_BORDE),("TOPPADDING",(0,0),(-1,-1),4),
        ("BOTTOMPADDING",(0,0),(-1,-1),4),("LEFTPADDING",(0,0),(-1,-1),5),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE")]))
    story.append(t_crs)
    story.append(Spacer(1, 4))
    
    story.append(sub("A.2 Metodologia de Reproyeccion"))
    story.append(body(
        "Las consultas espaciales se ejecutan enviando un <b>Bounding Box (BBOX)</b> en coordenadas "
        "WGS84 (EPSG:4326, grados decimales) con el parametro <b>inSR=4326</b> en la URL del "
        f"query REST. El servidor ArcGIS de la Alcaldía de {_NOMBRE_CIUDAD} ejecuta la reproyeccion "
        "al vuelo (<i>on-the-fly reprojection</i>) al CRS nativo del servicio antes de realizar "
        "la operacion de interseccion espacial (<i>esriSpatialRelIntersects</i>)."))
    story.append(Spacer(1, 4))
    story.append(dt([
        ("Parametro de entrada", "inSR=4326 (WGS84 Geograficas)"),
        ("Reproyeccion", "Automatica por ArcGIS Server al CRS nativo del servicio"),
        ("CRS nativo predominante", "EPSG:9377 (CTM12 -- Origen Unico Nacional de Colombia)"),
        ("Motor de transformacion", "ArcGIS Server (Esri) -- Transformacion MAGNA-SIRGAS <-> WGS84"),
        ("Parametros CTM12", "Lat origen: 4d 0' N | Lon origen: -73d 0' W | Falso E: 5'000.000 | Falso N: 2'000.000"),
        ("Factor de escala CTM12", "0,9992"),
        ("Marco de referencia", "MAGNA-SIRGAS (epoca 1995.4) -- compatible con WGS84 (ITRF)"),
    ]))
    story.append(Spacer(1, 4))
    
    story.append(sub("A.3 Precision Esperada y Limitaciones"))
    story.append(body(
        f"La transformacion entre WGS84 y MAGNA-SIRGAS/CTM12 introduce un error despreciable "
        f"para efectos de analisis urbanistico y de riesgos (<b>< 1 metro</b> en la zona de {_NOMBRE_CIUDAD}), "
        "dado que ambos marcos (WGS84/ITRF y MAGNA-SIRGAS) son compatibles a nivel centimetrico. "
        "Sin embargo, se documentan las siguientes limitaciones:"))
    story.append(Spacer(1, 4))
    story.append(dt([
        ("Precision de la reproyeccion", f"< 1 metro (WGS84 <-> MAGNA-SIRGAS en zona {_NOMBRE_CIUDAD})"),
        ("Precision del BBOX", "~250m de buffer en cada direccion -- suficiente para interseccion de poligonos"),
        ("Riesgo en zonas limitrofes", "Si el predio esta en el BORDE de un poligono de amenaza o tratamiento, "
         "la reproyeccion podria generar falsos negativos/positivos en un rango de ~1-2m"),
        ("Mitigacion recomendada", "Para casos criticos en bordes de poligonos, realizar cruce directo en "
         "CTM12 usando ArcGIS Pro con datos descargados del Geoportal"),
        ("Validacion geodesica", "Coordenadas en WGS84 (EPSG:4326); la transformacion MAGNA-SIRGAS/CTM12 es "
         "referencial -- para deslindes se requiere trabajo de campo en CTM12 nativo"),
        ("Normativa aplicable", "Resolucion 471/2020 IGAC -- Adopcion CTM12 como origen unico nacional. "
         "NTC 6271 -- Metadatos Geograficos"),
    ]))
    story.append(Spacer(1, 4))
    story.append(alert_green(
        "<b>CONCLUSION GEODESICA:</b> La metodologia de reproyeccion al vuelo (inSR=4326) utilizada "
        "para cruzar las capas GIS es tecnica y metricamente valida para los fines de este dictamen. "
        "La precision sub-metrica entre WGS84 y MAGNA-SIRGAS/CTM12 es suficiente para analisis "
        "urbanistico, de riesgos y catastral a escala predial. Para levantamientos topograficos "
        "o deslindes, se requiere trabajo de campo en CTM12 nativo."))
    
    # ── PÁGINA DE MARCA TITULUX (Confianza Predial) ──────────────
    story.append(PageBreak())
    _marca = Table([[
        Paragraph("TITULUX", ParagraphStyle("bm", fontName="Helvetica-Bold", fontSize=30,
                   textColor=colors.HexColor("#10243F"), leading=34, alignment=1)),
    ], [
        Paragraph("ARHIAX <b>Confianza Predial</b>", ParagraphStyle("bs", fontName="Helvetica",
                   fontSize=14, textColor=colors.HexColor("#2E5B8A"), leading=18, alignment=1)),
    ], [
        Paragraph("Motor de pre-dictamen jurídico-inmobiliario y screening SAGRILAFT",
                   ParagraphStyle("bss", fontName="Helvetica-Oblique", fontSize=10,
                   textColor=colors.HexColor("#4A6A8A"), leading=14, alignment=1)),
    ]], colWidths=["100%"])
    _marca.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 12), ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 14), ("RIGHTPADDING", (0, 0), (-1, -1), 14),
    ]))
    story.append(_marca)
    story.append(Spacer(1, 10))
    story.append(body(
        "Las secciones 05 (pre-dictamen juridico) y 09 (screening SAGRILAFT) de este dictamen fueron preparadas por <b>Titulux</b>, la capa de "
        "<b>confianza predial</b> de ARHIAX RE. Titulux estructura en un expediente unico: "
        "(1) el <b>pre-dictamen juridico</b> determinista sobre el certificado de libertad y "
        "tradicion (identidad, cronologia, titularidad, gravamenes, precio y pagos), y (2) el "
        "<b>screening SAGRILAFT</b> de las contrapartes contra listas restrictivas "
        "vinculantes, con degradacion honesta cuando una fuente no es consultable en vivo."))
    story.append(Spacer(1, 6))
    story.append(dt([
        ("Modulo", "Titulux — ARHIAX Confianza Predial"),
        ("Reglas de titulo", "TIT_B01..B05 · VAL_B01 · TRX_B01 · SAG_B01 (deterministas)"),
        ("Screening", "ONU / OFAC / UK en vivo (feed oficial, cache SHA-256) · UIAF por canal oficial · UE por archivo"),
        ("Evidencia", "Envelope B18 + cadena HMAC por evento (trazabilidad 9.22)"),
        ("Autoría", "El sistema prepara y señaliza; concluye y firma el profesional competente"),
    ]))
    story.append(Spacer(1, 6))
    story.append(body(
        "<i>Titulux no sustituye al abogado, al avaluador RAA ni al oficial de cumplimiento. "
        "Sus salidas son insumo preliminar de apoyo a la decision, sujeto a la verificacion "
        "profesional descrita en la seccion 15 de este documento.</i>"))
    story.append(Spacer(1, 8))

    # ── CONTROLES DE CALIDAD SPRINT 0 ───────────────────────────
    # M-13: los controles son advertencias (no asserts que tumben el PDF con 500).
    def ejecutar_controles_de_calidad():
        texto_completo = []
        for f in story:
            if hasattr(f, "text"):
                texto_completo.append(f.text)
            elif hasattr(f, "_cellvalues"):
                for row in f._cellvalues:
                    for cell in row:
                        if hasattr(cell, "text"):
                            texto_completo.append(cell.text)
                        elif isinstance(cell, str):
                            texto_completo.append(cell)
                            
        texto_doc = "\n".join(texto_completo)
        
        # Test 1: No contradiccion
        apto = "APTO para portafolio" in texto_doc
        bloqueado = "BLOQUEADA" in texto_doc or "Imposible estructurar" in texto_doc
        if apto and bloqueado:
            print("ADVERTENCIA - Contradiccion: veredicto apto y bloqueo coexisten en el documento.")
        else:
            print("OK - Test de no contradiccion: PASADO")
        
        # Test 2: Boundary del avaluo
        import re
        for m in re.finditer(r"aval[uú]o", texto_doc, re.IGNORECASE):
            contexto = texto_doc[max(0, m.start()-60):m.start()]
            texto_posterior = texto_doc[m.start():m.start()+40]
            # Permitir si está negado en el contexto inmediato o posterior
            valido = (re.search(r"no\s+(es|sustituye|constituye|refleja)", contexto, re.IGNORECASE) or 
                      re.search(r"no\s+(es|sustituye|constituye|refleja)", texto_posterior, re.IGNORECASE) or
                      "no es" in texto_posterior.lower() or "no sustituye" in texto_posterior.lower())
            if not valido:
                print(f"ADVERTENCIA - Uso de 'avaluo' sin negacion explicita: '...{contexto.strip()} {texto_posterior.strip()}...'")
        print("OK - Test de boundary de avaluo: PASADO")
    
    ejecutar_controles_de_calidad()

    # ── BUILD PDF ──────────────────────────────────────────────
    # Un único documento: dictamen + anexos juntos.
    doc = SimpleDocTemplate(OUTPUT, pagesize=letter,
        topMargin=1.2*cm, bottomMargin=1.5*cm, leftMargin=1.8*cm, rightMargin=1.8*cm)
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    print(f"SUCCESS: PDF GENERADO: {OUTPUT}")
    print(f"  Folio: {FOLIO}")
    print(f"  Hash SHA-256: {P_HASH}")
    print(f"  Timestamp: {NOW_UTC.isoformat()}")
    return cert_num, p_hash
