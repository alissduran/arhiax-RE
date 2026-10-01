# -*- coding: utf-8 -*-
"""STREET IMAGERY + FACADE SOLAR — pruebas BLOQUEANTES (offline, sin red).

Cubren, sin credenciales y sin red, las garantías que no pueden depender de que
un proveedor esté vivo:

  · la ausencia de street imagery NO bloquea: es un estado declarado,
  · la selección de la fachada visible es 100 % automática y determinista, con
    bearing correcto para coordenadas fijas,
  · Google fail-closed: ``can_persist=False`` y no se guardan bytes,
  · ``POT.altura_max`` JAMÁS se usa como altura física (el intento falla),
  · con sólo coordenada + fecha el análisis solar produce estados del
    vocabulario cerrado,
  · sin altura física se degrada ``shadow_confidence`` y ``INSUFFICIENT_GEOMETRY``
    nunca se convierte en ``DIRECT_EXPOSURE_LIKELY``.

Ninguna prueba llama a la red: los transportes HTTP se inyectan con centinelas
que registran cualquier intento de conexión.
"""
import json
import math
import os
import shutil
import sys
import unittest
from itertools import count
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import dictus_sources as ds  # noqa: E402
import facade_solar as fs  # noqa: E402
import street_imagery as si  # noqa: E402

# ── coordenadas FIJAS de prueba (Barranquilla) ────────────────────────────────
LAT_INMUEBLE, LON_INMUEBLE = 10.9685, -74.7813
EDIFICIO = {"lat": LAT_INMUEBLE, "lon": LON_INMUEBLE}
HUELLA_CUADRADA = {"type": "Polygon",
                   "coordinates": [[[-74.7820, 10.9680], [-74.7806, 10.9680],
                                    [-74.7806, 10.9690], [-74.7820, 10.9690],
                                    [-74.7820, 10.9680]]]}
# Distancias REALISTAS de vista callejera (una cámara de calle está a ~12-25 m
# del inmueble). 1° de latitud = 111194,93 m con R = 6371008,8 m.
LAT_CAM_SUR_12M = 10.96839208          # 12 m al sur del inmueble
LAT_CAM_NORTE_22M = 10.96869785        # 22 m al norte
LON_CAM_ESTE_22M = -74.78109847        # 22 m al este

_CONTADOR_TMP = count()


def _tmpdir(caso) -> Path:
    """Directorio temporal DENTRO del workspace (el TMP del sistema no es escribible)."""
    carpeta = ROOT / "tmp" / f"imagery_solar_{os.getpid()}_{next(_CONTADOR_TMP)}"
    carpeta.mkdir(parents=True, exist_ok=True)
    caso.addCleanup(shutil.rmtree, carpeta, ignore_errors=True)
    return carpeta

_VARS_CREDENCIALES = (
    "ARHIAX_MAPILLARY_TOKEN", "MAPILLARY_TOKEN", "MAPILLARY_ACCESS_TOKEN",
    "ARHIAX_GOOGLE_MAPS_API_KEY", "GOOGLE_MAPS_API_KEY", "GOOGLE_STREETVIEW_API_KEY",
    "ARHIAX_IMAGERY_STRICT_TERMS",
)


class Trampa:
    """Transporte centinela: registra el intento y NUNCA toca la red."""

    def __init__(self, excepcion=None):
        self.llamadas = []
        self._excepcion = excepcion or AssertionError("prueba offline: no debe tocar la red")

    def __call__(self, url, timeout):
        self.llamadas.append(url)
        raise self._excepcion


def _mapillary(transporte_json=None, transporte_bytes=None, **kw):
    return si.obtener_proveedor(si.MAPILLARY, transporte_json=transporte_json,
                                transporte_bytes=transporte_bytes, **kw)


def _google(transporte_json=None, transporte_bytes=None, **kw):
    return si.obtener_proveedor(si.GOOGLE_STREET_VIEW, transporte_json=transporte_json,
                                transporte_bytes=transporte_bytes, **kw)


def _imagen_mapillary(image_id, lat, lon, *, compass=None, pano=True, fecha=1_700_000_000_000):
    return {"id": image_id, "computed_geometry": {"type": "Point", "coordinates": [lon, lat]},
            "computed_compass_angle": compass, "is_pano": pano, "captured_at": fecha,
            "width": 2048, "height": 1024, "thumb_1024_url": f"https://x.test/{image_id}.jpg"}


class _Base(unittest.TestCase):
    def setUp(self):
        self._entorno = {v: os.environ.pop(v, None) for v in _VARS_CREDENCIALES}

    def tearDown(self):
        for var, valor in self._entorno.items():
            if valor is None:
                os.environ.pop(var, None)
            else:
                os.environ[var] = valor


# ══════════════════════════════════════════════════════════════════════════════
# 1 · STREET IMAGERY AUSENTE NO BLOQUEA (ESTADO DECLARADO)
# ══════════════════════════════════════════════════════════════════════════════
class TestStreetImageryAusenteNoBloquea(_Base):

    def test_centinela_declara_ausencia_y_nunca_no_match(self):
        prov = si.obtener_proveedor(si.NO_IMAGE_AVAILABLE)
        meta = prov.get_metadata(LAT_INMUEBLE, LON_INMUEBLE)
        self.assertEqual(meta["status"], si.NOT_SUPPORTED)
        self.assertNotEqual(meta["status"], si.NO_MATCH)
        self.assertTrue(meta["detail"])
        mejor = prov.get_best_view(LAT_INMUEBLE, LON_INMUEBLE)
        self.assertEqual(mejor["status"], si.NOT_SUPPORTED)
        self.assertIsNone(mejor["selection"])
        self.assertEqual(mejor["facade_view_level"], si.NO_IMAGE_AVAILABLE)
        self.assertFalse(mejor["blocks_dictus"])

    def test_sin_credenciales_no_toca_la_red_y_declara_estado(self):
        t_json, t_bytes = Trampa(), Trampa()
        agg = si.consultar_vista_automatica(
            LAT_INMUEBLE, LON_INMUEBLE, EDIFICIO,
            coordenada_oficial=(LAT_INMUEBLE, LON_INMUEBLE),
            proveedores=[_mapillary(t_json, t_bytes), _google(t_json, t_bytes),
                         si.obtener_proveedor(si.NO_IMAGE_AVAILABLE)])
        self.assertEqual(agg["status"], si.SOURCE_UNAVAILABLE)
        self.assertEqual(agg["attempts"][si.MAPILLARY]["credentials"]["status"], "MISSING")
        self.assertEqual(agg["attempts"][si.MAPILLARY]["status"], si.SOURCE_UNAVAILABLE)
        self.assertEqual(agg["attempts"][si.GOOGLE_STREET_VIEW]["status"], si.SOURCE_UNAVAILABLE)
        self.assertIsNone(agg["view"])
        self.assertEqual(agg["facade_view_level"], si.NO_IMAGE_AVAILABLE)
        # La ausencia no bloquea nada y no exige intervención humana.
        self.assertFalse(agg["blocks_dictus"])
        self.assertFalse(agg["human_input_required"])
        self.assertEqual(agg["dictus_gate_impact"], "NONE")
        # No se inventó ninguna imagen ni se tocó la red.
        self.assertEqual(t_json.llamadas, [])
        self.assertEqual(t_bytes.llamadas, [])
        self.assertIn(si.MOTIVO_SIN_CREDENCIALES,
                      agg["attempts"][si.MAPILLARY]["detail"])

    def test_ausencia_nunca_se_convierte_en_no_match(self):
        self.assertNotIn(si.NO_MATCH, si.ESTADOS_SIN_DATO)
        self.assertEqual(si.estado_consolidado([si.NO_MATCH, si.SOURCE_UNAVAILABLE]),
                         si.SOURCE_UNAVAILABLE)
        self.assertEqual(si.estado_consolidado([si.NO_MATCH, si.NO_MATCH]), si.NO_MATCH)
        self.assertEqual(si.estado_consolidado([si.AVAILABLE, si.SOURCE_UNAVAILABLE]),
                         si.AVAILABLE)

    def test_proveedor_que_responde_vacio_si_es_no_match(self):
        prov = _mapillary(credencial="token-de-prueba")
        prov._transporte_json = lambda url, t: {"data": []}
        meta = prov.get_metadata(LAT_INMUEBLE, LON_INMUEBLE)
        self.assertEqual(meta["status"], si.NO_MATCH)
        # Y si otro proveedor está caído, el agregado NO dice NO_MATCH.
        caido = _google(credencial=None)
        agg = si.consultar_vista_automatica(
            LAT_INMUEBLE, LON_INMUEBLE, EDIFICIO, proveedores=[prov, caido])
        self.assertEqual(agg["status"], si.SOURCE_UNAVAILABLE)

    def test_google_zeroresults_es_no_match_y_request_denied_es_caida(self):
        prov = _google(credencial="llave-de-prueba")
        prov._transporte_json = lambda url, t: {"status": "ZERO_RESULTS"}
        self.assertEqual(prov.get_metadata(LAT_INMUEBLE, LON_INMUEBLE)["status"], si.NO_MATCH)
        prov._transporte_json = lambda url, t: {"status": "REQUEST_DENIED",
                                                "error_message": "You must use an API key"}
        self.assertEqual(prov.get_metadata(LAT_INMUEBLE, LON_INMUEBLE)["status"],
                         si.SOURCE_UNAVAILABLE)

    def test_fallo_de_red_y_fallo_de_consulta_tienen_estados_distintos(self):
        red = _mapillary(credencial="t", transporte_json=Trampa(excepcion=OSError("sin red")))
        self.assertEqual(red.get_metadata(LAT_INMUEBLE, LON_INMUEBLE)["status"],
                         si.SOURCE_UNAVAILABLE)
        raro = _mapillary(credencial="t", transporte_json=Trampa(excepcion=RuntimeError("x")))
        self.assertEqual(raro.get_metadata(LAT_INMUEBLE, LON_INMUEBLE)["status"],
                         si.QUERY_FAILED)

    def test_estado_no_declarado_cae_en_query_failed(self):
        prov = _mapillary()
        res = prov._resultado("ESTADO_INVENTADO", operacion="x")
        self.assertEqual(res["status"], si.QUERY_FAILED)
        self.assertEqual(len(si.ESTADOS), 5)
        self.assertEqual(si.ESTADOS, tuple(ds.ESTADOS))

    def test_vocabularios_coinciden_con_el_source_pack(self):
        self.assertTrue(all(si.verificar_vocabulario().values()), si.verificar_vocabulario())
        self.assertTrue(all(fs.verificar_vocabulario().values()), fs.verificar_vocabulario())
        self.assertEqual(si.NIVELES_FACHADA, tuple(ds.NIVELES_FACHADA))
        self.assertEqual(fs.ESTADOS_EXPOSICION, tuple(ds.ESTADOS_EXPOSICION))
        self.assertEqual(fs.ETIQUETA_ANALISIS_SOLAR, ds.ETIQUETA_ANALISIS_SOLAR)


# ══════════════════════════════════════════════════════════════════════════════
# 2 · SELECCIÓN DE FACHADA 100 % AUTOMÁTICA Y DETERMINISTA
# ══════════════════════════════════════════════════════════════════════════════
class TestSeleccionAutomaticaDeterminista(_Base):

    def test_bearing_correcto_para_desplazamientos_cardinales_fijos(self):
        # Cámara al SUR del inmueble → azimut cámara→inmueble = 0° (Norte)
        self.assertAlmostEqual(si.bearing_geodesico(10.9500, LON_INMUEBLE,
                                                   LAT_INMUEBLE, LON_INMUEBLE), 0.0, places=4)
        # Cámara al NORTE → 180°
        self.assertAlmostEqual(si.bearing_geodesico(10.9870, LON_INMUEBLE,
                                                   LAT_INMUEBLE, LON_INMUEBLE), 180.0, places=4)
        # Cámara al ESTE (misma latitud, mayor longitud) → 270° (gran círculo: ±0,002°)
        self.assertAlmostEqual(si.bearing_geodesico(LAT_INMUEBLE, -74.7700,
                                                   LAT_INMUEBLE, LON_INMUEBLE), 270.0, places=2)
        # Cámara al OESTE → 90°
        self.assertAlmostEqual(si.bearing_geodesico(LAT_INMUEBLE, -74.7900,
                                                   LAT_INMUEBLE, LON_INMUEBLE), 90.0, places=2)
        # Un grado de latitud ≈ 111 km
        self.assertTrue(110000 < si.distancia_metros(10.0, -74.0, 11.0, -74.0) < 112000)
        self.assertAlmostEqual(si.diferencia_angular(350.0, 10.0), 20.0, places=6)
        # Distancias realistas: la cámara de prueba del sur está a ~12 m.
        self.assertAlmostEqual(si.distancia_metros(LAT_CAM_SUR_12M, LON_INMUEBLE,
                                                   LAT_INMUEBLE, LON_INMUEBLE), 12.0, places=1)

    def _candidatos(self):
        return [
            {"image_id": "PANO-NORTE", "camera_lat": LAT_CAM_NORTE_22M, "camera_lon": LON_INMUEBLE,
             "is_pano": True, "capture_date": "2024-03-01", "provider": si.MAPILLARY,
             "attribution": "© Mapillary contributors"},
            {"image_id": "PANO-SUR", "camera_lat": LAT_CAM_SUR_12M, "camera_lon": LON_INMUEBLE,
             "is_pano": True, "capture_date": "2024-05-01", "provider": si.MAPILLARY,
             "attribution": "© Mapillary contributors"},
            {"image_id": "PANO-ESTE", "camera_lat": LAT_INMUEBLE, "camera_lon": LON_CAM_ESTE_22M,
             "is_pano": True, "capture_date": "2024-01-01", "provider": si.MAPILLARY,
             "attribution": "© Mapillary contributors"},
        ]

    def test_seleccion_determinista_independiente_del_orden(self):
        base = si.seleccionar_vista_automatica(
            self._candidatos(), coordenada_oficial=(LAT_INMUEBLE, LON_INMUEBLE),
            proveedor=si.MAPILLARY)
        for permutacion in (list(reversed(self._candidatos())),
                            [self._candidatos()[1], self._candidatos()[2], self._candidatos()[0]]):
            otra = si.seleccionar_vista_automatica(
                permutacion, coordenada_oficial=(LAT_INMUEBLE, LON_INMUEBLE),
                proveedor=si.MAPILLARY)
            self.assertEqual(json.dumps(base, sort_keys=True, default=str),
                             json.dumps(otra, sort_keys=True, default=str))
        # La más cercana (SUR, ~12 m) gana con empate de alineación.
        self.assertEqual(base["image_id"], "PANO-SUR")
        self.assertAlmostEqual(base["bearing_camera_to_building_deg"], 0.0, places=3)
        self.assertFalse(base["human_input_required"])
        self.assertEqual(base["selection_method"], si.METODO_SELECCION)

    def test_sin_geometria_del_inmueble_es_contextual_y_no_afirma_orientacion(self):
        res = si.seleccionar_vista_automatica(self._candidatos(), coordenada_oficial=None,
                                              proveedor=si.MAPILLARY)
        self.assertEqual(res["facade_view_level"], si.FACADE_VIEW_CONTEXTUAL)
        self.assertIsNone(res["bearing_camera_to_building_deg"])
        self.assertIn("CONTEXTUAL", res["motivo"])

    def test_sin_candidatos_no_image_available(self):
        res = si.seleccionar_vista_automatica([], coordenada_oficial=(LAT_INMUEBLE, LON_INMUEBLE))
        self.assertEqual(res["facade_view_level"], si.NO_IMAGE_AVAILABLE)
        self.assertIsNone(res["imagen"])
        self.assertEqual(res["status"], si.AVAILABLE)  # estado de la vista, no del proveedor

    def test_descarta_la_perspectiva_que_no_mira_al_inmueble(self):
        # Cámara al NORTE (bearing cámara→inmueble = 180°) con compás 180° → alineada.
        # Cámara al SUR  (bearing cámara→inmueble = 0°)   con compás 180° → mira al revés.
        candidatos = [
            {"image_id": "ALINEADA-LEJOS", "camera_lat": LAT_CAM_NORTE_22M,
             "camera_lon": LON_INMUEBLE, "is_pano": False, "compass_angle": 180.0,
             "capture_date": "2024-05-01", "provider": si.MAPILLARY},
            {"image_id": "CERCA-AL_REVES", "camera_lat": LAT_CAM_SUR_12M,
             "camera_lon": LON_INMUEBLE, "is_pano": False, "compass_angle": 180.0,
             "capture_date": "2024-05-01", "provider": si.MAPILLARY},
        ]
        res = si.seleccionar_vista_automatica(candidatos,
                                              coordenada_oficial=(LAT_INMUEBLE, LON_INMUEBLE),
                                              proveedor=si.MAPILLARY)
        self.assertEqual(res["image_id"], "ALINEADA-LEJOS")
        self.assertEqual(res["alignment_error_deg"], 0.0)
        self.assertEqual(res["heading_source"], "AZIMUT_COMPAS_CAMARA_VERIFICADO")
        self.assertEqual([d["image_id"] for d in res["candidates_discarded"]], ["CERCA-AL_REVES"])
        descartado = res["candidates_discarded"][0]
        self.assertEqual(descartado["alignment_error_deg"], 180.0)
        self.assertLess(descartado["distance_m"], res["distance_m"])

    def test_heading_pitch_fov_y_nivel_verificado(self):
        res = si.seleccionar_vista_automatica(
            self._candidatos(), coordenada_oficial=(LAT_INMUEBLE, LON_INMUEBLE),
            centroide_edificio=EDIFICIO, altura_edificio_m=30.0, proveedor=si.MAPILLARY)
        self.assertEqual(res["facade_view_level"], si.FACADE_VIEW_VERIFIED)
        self.assertEqual(res["heading"], res["bearing_camera_to_building_deg"])
        self.assertEqual(res["heading_source"], "PANORAMA_HEADING_SOLICITADO_HACIA_INMUEBLE")
        self.assertAlmostEqual(res["distance_m"],
                               si.distancia_metros(LAT_CAM_SUR_12M, LON_INMUEBLE,
                                                   LAT_INMUEBLE, LON_INMUEBLE),
                               places=2)
        self.assertAlmostEqual(res["pitch"],
                               math.degrees(math.atan((30.0 / 2.0 - 2.5) / res["distance_m"])),
                               places=3)
        self.assertEqual(res["fov"], si.DEFAULT_FOV_DEG)
        self.assertEqual(res["provider"], si.MAPILLARY)
        for campo in ("image_id", "panorama_id", "camera_lat", "camera_lon", "building_lat",
                      "building_lon", "heading", "pitch", "fov", "capture_date", "provider",
                      "attribution", "selection_method"):
            self.assertIn(campo, res, f"falta {campo} en la selección automática")

    def test_sin_altura_no_calcula_pitch_vertical_ni_lo_inventa(self):
        res = si.seleccionar_vista_automatica(self._candidatos(),
                                             coordenada_oficial=(LAT_INMUEBLE, LON_INMUEBLE),
                                             proveedor=si.MAPILLARY)
        self.assertEqual(res["pitch"], 0.0)
        self.assertEqual(res["pitch_source"], "HORIZONTAL_POR_DEFECTO_SIN_ALTURA_FISICA")
        self.assertEqual(res["fov"], si.DEFAULT_FOV_DEG)
        self.assertIn("DEFECTO", res["fov_source"])

    def test_texto_nunca_dice_fachada_principal(self):
        res = si.seleccionar_vista_automatica(
            [{"image_id": "X1", "camera_lat": 10.9600, "camera_lon": LON_INMUEBLE,
              "is_pano": True, "capture_date": "2024-05-01", "provider": si.MAPILLARY,
              "attribution": "Fachada Principal del edificio"}],
            coordenada_oficial=(LAT_INMUEBLE, LON_INMUEBLE), proveedor=si.MAPILLARY)
        texto = f'{res["descripcion"]} {res["attribution"]}'.lower()
        self.assertNotIn(si.TEXTO_PROHIBIDO_FACHADA_PRINCIPAL, texto)
        self.assertIn(si.TEXTO_VISTA_AUTORIZADO, texto)
        self.assertIn(si.TEXTO_VISTA_AUTORIZADO,
                      si.etiqueta_vista_callejera("X", 10.0, 20.0, "N").lower())
        self.assertEqual(si.sanear_texto("La FACHADA   PRINCIPAL existe"),
                         "La " + si.TEXTO_VISTA_AUTORIZADO + " existe")

    def test_flujo_completo_con_transporte_simulado(self):
        """Proveedor real + respuesta simulada: selección automática y determinista."""
        imagenes = [_imagen_mapillary("IMG-N", LAT_CAM_NORTE_22M, LON_INMUEBLE),
                    _imagen_mapillary("IMG-S", LAT_CAM_SUR_12M, LON_INMUEBLE)]
        prov = _mapillary(credencial="token-de-prueba")
        prov._transporte_json = lambda url, t: {"data": list(imagenes)}
        res = prov.get_best_view(LAT_INMUEBLE, LON_INMUEBLE, HUELLA_CUADRADA,
                                 coordenada_oficial=(LAT_INMUEBLE, LON_INMUEBLE),
                                 altura_edificio_m=12.0)
        self.assertEqual(res["status"], si.AVAILABLE)
        self.assertEqual(res["selection"]["image_id"], "IMG-S")
        self.assertEqual(res["facade_view_level"], si.FACADE_VIEW_VERIFIED)
        self.assertNotIn("token-de-prueba", json.dumps(res["provenance"], default=str))
        inverso = _mapillary(credencial="token-de-prueba")
        inverso._transporte_json = lambda url, t: {"data": list(reversed(imagenes))}
        otra = inverso.get_best_view(LAT_INMUEBLE, LON_INMUEBLE, HUELLA_CUADRADA,
                                     coordenada_oficial=(LAT_INMUEBLE, LON_INMUEBLE))
        self.assertEqual(otra["selection"]["image_id"], "IMG-S")


# ══════════════════════════════════════════════════════════════════════════════
# 3 · GOOGLE FAIL-CLOSED (SIN PERSISTENCIA) Y LICENCIAS
# ══════════════════════════════════════════════════════════════════════════════
class TestLicenciasYFailClosed(_Base):

    def test_google_politica_cerrada_por_defecto(self):
        pol = _google().persistence_policy()
        self.assertFalse(pol["can_persist"])
        self.assertFalse(pol["can_download_bytes"])
        self.assertFalse(pol["can_embed_in_pdf"])
        self.assertFalse(pol["can_modify"])
        self.assertEqual(pol["provider_terms_status"], si.TERMS_UNVERIFIED)
        self.assertTrue(pol["fail_closed"])
        self.assertEqual(pol["storage_flow"], "NINGUNO")

    def test_metadata_de_la_imagen_no_amplia_el_permiso(self):
        pol = _google().persistence_policy(
            image_metadata={"license": "public domain", "can_persist": True})
        self.assertFalse(pol["can_persist"])
        self.assertFalse(pol["can_embed_in_pdf"])

    def test_google_no_descarga_ni_guarda_bytes(self):
        trampa = Trampa()
        prov = _google(credencial="llave-de-prueba", transporte_bytes=trampa,
                       transporte_json=trampa)
        tmp = _tmpdir(self)
        res = prov.get_image(LAT_INMUEBLE, LON_INMUEBLE, image_id="PANO-123", dest_dir=tmp)
        self.assertEqual(res["status"], si.NOT_SUPPORTED)
        self.assertFalse(res["downloaded"])
        self.assertEqual(res["bytes_written"], 0)
        self.assertIsNone(res["content_bytes"])
        self.assertIsNone(res["path"])
        self.assertFalse(res["can_persist"])
        self.assertFalse(res["can_embed_in_pdf"])
        self.assertEqual(list(tmp.iterdir()), [])
        self.assertEqual(trampa.llamadas, [], "no debe intentarse ninguna descarga")

    def test_google_sin_credenciales_declara_source_unavailable(self):
        prov = _google(transporte_json=Trampa())
        res = prov.get_metadata(LAT_INMUEBLE, LON_INMUEBLE)
        self.assertEqual(res["status"], si.SOURCE_UNAVAILABLE)
        self.assertFalse(res["provenance"]["request_made"])

    def test_mapillary_es_el_candidato_principal_de_persistencia(self):
        pol = _mapillary().persistence_policy()
        self.assertTrue(pol["can_persist"])
        self.assertTrue(pol["can_embed_in_pdf"])
        self.assertTrue(pol["share_alike"])
        self.assertTrue(pol["attribution_required"])
        self.assertEqual(pol["provider_terms_status"], si.TERMS_DECLARED)
        matriz = si.persistencias_permitidas()
        self.assertTrue(matriz[si.MAPILLARY]["can_persist"])
        self.assertFalse(matriz[si.GOOGLE_STREET_VIEW]["can_persist"])
        self.assertFalse(matriz[si.NO_IMAGE_AVAILABLE]["can_persist"])

    def test_licencia_contradictoria_cierra_el_permiso(self):
        pol = _mapillary().persistence_policy(
            image_metadata={"license": "All rights reserved"})
        self.assertFalse(pol["can_persist"])
        self.assertEqual(pol["provider_terms_status"], si.TERMS_UNVERIFIED)

    def test_politica_estricta_cierra_tambien_la_licencia_declarada(self):
        pol = _mapillary(politica_estricta=True).persistence_policy()
        self.assertFalse(pol["can_persist"])

    def test_umbral_de_apertura_exige_evidencia_verificada(self):
        prov = _google()
        # Evidencia incompleta: se rechaza y NO abre nada.
        prov.registrar_evidencia_terminos({"evidence_url": "https://x.test/terms",
                                           "terms_status": si.TERMS_VERIFIED})
        self.assertFalse(prov.persistence_policy()["can_persist"])
        self.assertEqual(prov.license_info()["provider_terms_status"], si.TERMS_UNVERIFIED)
        # Evidencia completa y explícita: único camino documentado para abrir.
        abierta = _google().persistence_policy(terms_evidence={
            "evidence_url": "https://x.test/terms", "retrieved_at": "2026-01-01T00:00:00Z",
            "sha256": "0" * 64, "terms_status": si.TERMS_VERIFIED,
            "license_allows_persist": True, "can_persist": True, "can_embed_in_pdf": True})
        self.assertTrue(abierta["can_persist"])
        self.assertTrue(abierta["evidence_based_override"])

    def test_terminos_restrictivos_cierran_todo(self):
        prov = _google()
        prov.registrar_evidencia_terminos({"evidence_url": "https://x.test/t",
                                           "retrieved_at": "2026-01-01T00:00:00Z",
                                           "sha256": "1" * 64,
                                           "terms_status": si.TERMS_RESTRICTED})
        pol = prov.persistence_policy()
        self.assertFalse(pol["can_persist"])
        self.assertFalse(pol["can_embed_in_pdf"])

    def test_mapillary_sin_token_no_descarga_ni_guarda(self):
        trampa = Trampa()
        prov = _mapillary(transporte_bytes=trampa, transporte_json=trampa)
        tmp = _tmpdir(self)
        res = prov.get_image(LAT_INMUEBLE, LON_INMUEBLE, image_id="123", dest_dir=tmp)
        self.assertEqual(res["status"], si.SOURCE_UNAVAILABLE)
        self.assertEqual(res["bytes_written"], 0)
        self.assertIsNone(res["content_bytes"])
        self.assertEqual(list(tmp.iterdir()), [])
        self.assertEqual(trampa.llamadas, [])

    def test_mapillary_con_token_permite_guardar_con_atribucion(self):
        prov = _mapillary(credencial="token-de-prueba",
                          transporte_bytes=lambda url, t: b"JPEG-DE-PRUEBA")
        tmp = _tmpdir(self)
        res = prov.get_image(LAT_INMUEBLE, LON_INMUEBLE, image_id="ABC",
                             dest_dir=tmp, vista={"url": "https://x.test/ABC.jpg"})
        self.assertEqual(res["status"], si.AVAILABLE)
        self.assertTrue(res["downloaded"])
        self.assertEqual(res["bytes_written"], len(b"JPEG-DE-PRUEBA"))
        self.assertEqual(res["sha256"], si.hash_canonico(b"JPEG-DE-PRUEBA"))
        self.assertTrue(list(tmp.iterdir()))
        self.assertIn("Mapillary", str(res["attribution"]))
        self.assertNotIn("token-de-prueba", json.dumps(res["provenance"], default=str))

    def test_centinela_no_guarda_bytes(self):
        res = si.obtener_proveedor(si.NO_IMAGE_AVAILABLE).get_image(image_id="X", dest_dir=None)
        self.assertEqual(res["status"], si.NOT_SUPPORTED)
        self.assertEqual(res["bytes_written"], 0)
        self.assertIsNone(res["content_bytes"])


# ══════════════════════════════════════════════════════════════════════════════
# 4 · ALTURAS: POT.altura_max NUNCA ES ALTURA FÍSICA
# ══════════════════════════════════════════════════════════════════════════════
class TestAlturaNormativaNoEsFisica(_Base):

    def test_pot_altura_max_rechazada_como_fisica(self):
        r = fs.resolver_altura_fisica(building_height=11, height_source="POT.altura_max",
                                      altura_normativa_pot=11)
        self.assertIsNone(r["building_physical_height"])
        self.assertIsNone(r["height_source"])
        self.assertEqual(r["shadow_confidence"], fs.SHADOW_CONFIDENCE_DEGRADED)
        self.assertEqual(r["rejected_source"], "POT.altura_max")
        self.assertIn("NORMATIVA", r["reason"])
        self.assertFalse(r["altura_normativa_usada_como_fisica"])

    def test_pot_por_niveles_tambien_se_rechaza(self):
        r = fs.resolver_altura_fisica(building_levels=4,
                                      height_source="POT_BAQ_EDIFICABILIDAD.altura_max",
                                      altura_normativa_pot="11")
        self.assertIsNone(r["building_physical_height"])
        self.assertEqual(r["shadow_confidence"], fs.SHADOW_CONFIDENCE_DEGRADED)

    def test_modo_estricto_falla_si_alguien_lo_intenta(self):
        with self.assertRaises(fs.AlturaNormativaComoFisicaRechazada):
            fs.resolver_altura_fisica(building_height=11, height_source="POT.altura_max",
                                      altura_normativa_pot=11, estricto=True)
        with self.assertRaises(fs.AlturaNormativaComoFisicaRechazada):
            fs.analizar_exposicion_fachada(LAT_INMUEBLE, LON_INMUEBLE, fecha="2026-03-21",
                                           hora=12.0, facade_bearing=180.0,
                                           building_height=11, height_source="POT.altura_max",
                                           estricto=True)

    def test_altura_sin_fuente_declarada_se_rechaza(self):
        r = fs.resolver_altura_fisica(building_height=9.0)
        self.assertIsNone(r["building_physical_height"])
        self.assertEqual(r["shadow_confidence"], fs.SHADOW_CONFIDENCE_DEGRADED)
        r2 = fs.resolver_altura_fisica(building_levels=3)
        self.assertIsNone(r2["building_physical_height"])
        self.assertEqual(r2["shadow_confidence"], fs.SHADOW_CONFIDENCE_DEGRADED)

    def test_altura_fisica_con_fuente_automatica_se_acepta(self):
        r = fs.resolver_altura_fisica(building_height=9.0,
                                      height_source="MS_BUILDINGS_FOOTPRINT.height")
        self.assertEqual(r["building_physical_height"], 9.0)
        self.assertEqual(r["height_source"], "MS_BUILDINGS_FOOTPRINT.height")
        self.assertEqual(r["shadow_confidence"], fs.SHADOW_CONFIDENCE_OK)
        self.assertTrue(r["advanced_simulation_enabled"])

    def test_niveles_derivan_altura_solo_con_fuente_automatica(self):
        r = fs.resolver_altura_fisica(building_levels=3,
                                      height_source="CATASTRO_BAQ.total_pisos")
        self.assertEqual(r["building_physical_height"], 9.0)
        self.assertIn("NIVELES", r["derivation"]["note"].upper())
        self.assertIn("derivada", r["height_source"])

    def test_analisis_con_altura_pot_no_la_usa_y_no_bloquea_dictus(self):
        out = fs.analizar_exposicion_fachada(LAT_INMUEBLE, LON_INMUEBLE, fecha="2026-03-21",
                                             hora=12.0, facade_bearing=180.0, building_height=11,
                                             height_source="POT.altura_max",
                                             altura_normativa_pot=11)
        self.assertIsNone(out["building_physical_height"])
        self.assertIsNone(out["height_source"])
        self.assertEqual(out["shadow_confidence"], fs.SHADOW_CONFIDENCE_DEGRADED)
        self.assertFalse(out["shadow_length_simulated"])
        self.assertIsNone(out["physical_shadow_length_m"])
        self.assertFalse(out["altura_normativa_usada_como_fisica"])
        self.assertFalse(out["provenance"]["height_rule"]["pot_altura_max_usada_como_fisica"])
        self.assertEqual(out["altura_normativa_pot"], 11.0)
        # Nunca bloquea DICTUS y nunca convierte la norma en geometría inventada.
        self.assertFalse(out["blocks_dictus"])
        self.assertEqual(out["dictus_gate_impact"], "NONE")
        self.assertNotIn("blocking", out)


# ══════════════════════════════════════════════════════════════════════════════
# 5 · SOLAR SÓLO CON COORDENADA + FECHA
# ══════════════════════════════════════════════════════════════════════════════
class TestSolarSoloCoordenadaYFecha(_Base):

    def test_estados_siempre_del_vocabulario_cerrado(self):
        for fecha in ("2026-03-21", "2026-06-21", "2026-09-21", "2026-12-21"):
            for hora in (6.0, 9.0, 12.0, 15.0, 18.0, 21.0):
                out = fs.analizar_exposicion_fachada(LAT_INMUEBLE, LON_INMUEBLE,
                                                     fecha=fecha, hora=hora)
                self.assertIn(out["estado"], fs.ESTADOS_EXPOSICION)
                self.assertIn(out["estado"], fs.ESTADOS_EXPOSICION)
                self.assertFalse(out["es_medicion_fisica"])
                self.assertEqual(out["etiqueta"], fs.ETIQUETA_ANALISIS_SOLAR)
                self.assertEqual(out["estado"], fs.INSUFFICIENT_GEOMETRY)
                self.assertIsNotNone(out["direccion_incidencia_solar"])
                self.assertFalse(out["shadow_length_simulated"])

    def test_los_cuatro_estados_permitidos_son_alcanzables(self):
        vistos = set()
        vistos.add(fs.analizar_exposicion_fachada(
            LAT_INMUEBLE, LON_INMUEBLE, solar_position=(180.0, 60.0),
            facade_bearing=180.0)["estado"])
        vistos.add(fs.analizar_exposicion_fachada(
            LAT_INMUEBLE, LON_INMUEBLE, solar_position=(180.0, 60.0),
            facade_bearing=250.0)["estado"])
        vistos.add(fs.analizar_exposicion_fachada(
            LAT_INMUEBLE, LON_INMUEBLE, solar_position=(180.0, 60.0),
            facade_bearing=340.0)["estado"])
        vistos.add(fs.analizar_exposicion_fachada(
            LAT_INMUEBLE, LON_INMUEBLE, solar_position=(180.0, 60.0))["estado"])
        self.assertEqual(vistos, set(fs.ESTADOS_EXPOSICION))

    def test_sol_bajo_el_horizonte_es_fachada_sombria(self):
        out = fs.analizar_exposicion_fachada(LAT_INMUEBLE, LON_INMUEBLE,
                                             solar_position=(180.0, -3.0), facade_bearing=180.0)
        self.assertEqual(out["estado"], fs.FACADE_SHADED_OR_REARWARD)

    def test_obstruccion_declarada_demota_la_exposicion(self):
        out = fs.analizar_exposicion_fachada(LAT_INMUEBLE, LON_INMUEBLE,
                                             solar_position=(180.0, 30.0), facade_bearing=180.0,
                                             obstrucciones=[(150.0, 210.0, 40.0)])
        self.assertEqual(out["estado"], fs.FACADE_SHADED_OR_REARWARD)
        # Sin obstrucción declarada, el mismo caso es exposición directa.
        self.assertEqual(fs.analizar_exposicion_fachada(
            LAT_INMUEBLE, LON_INMUEBLE, solar_position=(180.0, 30.0),
            facade_bearing=180.0)["estado"], fs.DIRECT_EXPOSURE_LIKELY)

    def test_angulo_relativo_y_fachada_visible_se_reportan(self):
        out = fs.analizar_exposicion_fachada(LAT_INMUEBLE, LON_INMUEBLE,
                                             solar_position=(200.0, 45.0), facade_bearing=170.0)
        self.assertAlmostEqual(out["angulo_relativo_sol_fachada_deg"], 30.0, places=6)
        self.assertEqual(out["fachada_visible"]["metodo"], "DECLARADO_POR_LLAMADOR")
        self.assertEqual(out["estado"], fs.DIRECT_EXPOSURE_LIKELY)

    def test_sin_posicion_solar_es_insufficient_geometry(self):
        out = fs.analizar_exposicion_fachada(LAT_INMUEBLE, LON_INMUEBLE, facade_bearing=180.0)
        self.assertEqual(out["estado"], fs.INSUFFICIENT_GEOMETRY)
        self.assertIn("POSICION_SOLAR", out["geometria_faltante"])


# ══════════════════════════════════════════════════════════════════════════════
# 6 · SIN ALTURA FÍSICA: DEGRADA Y NUNCA PROMUEVE
# ══════════════════════════════════════════════════════════════════════════════
class TestSinAlturaDegradaYNoPromueve(_Base):

    def test_sin_altura_fisica_shadow_confidence_degradada(self):
        out = fs.analizar_exposicion_fachada(LAT_INMUEBLE, LON_INMUEBLE, fecha="2026-03-21",
                                             hora=12.0, facade_bearing=180.0)
        self.assertEqual(out["shadow_confidence"], fs.SHADOW_CONFIDENCE_DEGRADED)
        self.assertIsNone(out["building_physical_height"])
        self.assertIsNone(out["physical_shadow_length_m"])
        self.assertFalse(out["shadow_length_simulated"])
        self.assertTrue(out["estado_aproximado"])
        self.assertIn(out["estado"], fs.ESTADOS_EXPOSICION)

    def test_insufficient_geometry_nunca_se_convierte_en_direct(self):
        casos = [
            dict(),                                              # nada
            dict(fecha="2026-03-21", hora=12.0),                 # sólo coordenada + fecha
            dict(solar_position=(180.0, 70.0)),                  # sólo sol, sin fachada
            dict(camera_geometry={"camera_lat": LAT_INMUEBLE}),  # cámara incompleta
        ]
        for extra in casos:
            out = fs.analizar_exposicion_fachada(LAT_INMUEBLE, LON_INMUEBLE, **extra)
            self.assertEqual(out["estado"], fs.INSUFFICIENT_GEOMETRY,
                             f"caso {extra} produjo {out['estado']}")
            self.assertNotEqual(out["estado"], fs.DIRECT_EXPOSURE_LIKELY)
            self.assertEqual(out["shadow_confidence"], fs.SHADOW_CONFIDENCE_DEGRADED)
            self.assertIsNone(out["angulo_relativo_sol_fachada_deg"])
            self.assertFalse(out["blocks_dictus"])

    def test_altura_pot_no_habilita_simulacion_de_sombra(self):
        for fuente in ("POT.altura_max", "POT_BAQ_EDIFICABILIDAD.altura_max", ""):
            out = fs.analizar_exposicion_fachada(
                LAT_INMUEBLE, LON_INMUEBLE, fecha="2026-03-21", hora=12.0,
                facade_bearing=180.0, building_height=11, building_levels=4,
                height_source=fuente, altura_normativa_pot=11)
            self.assertFalse(out["simulacion_avanzada_habilitada"], f"fuente {fuente!r}")
            self.assertIsNone(out["physical_shadow_length_m"])
            self.assertEqual(out["shadow_confidence"], fs.SHADOW_CONFIDENCE_DEGRADED)

    def test_altura_fisica_automatica_si_habilita_simulacion(self):
        out = fs.analizar_exposicion_fachada(
            LAT_INMUEBLE, LON_INMUEBLE, fecha="2026-03-21", hora=9.0, facade_bearing=100.0,
            building_height=21.0, height_source="MS_BUILDINGS_FOOTPRINT.height")
        self.assertEqual(out["shadow_confidence"], fs.SHADOW_CONFIDENCE_OK)
        self.assertTrue(out["simulacion_avanzada_habilitada"])
        self.assertTrue(out["shadow_length_simulated"])
        self.assertGreater(out["physical_shadow_length_m"], 0.0)
        self.assertFalse(out["estado_aproximado"])
        self.assertFalse(out["es_medicion_fisica"])

    def test_vista_callejera_ausente_no_promueve_la_exposicion(self):
        agg = si.consultar_vista_automatica(
            LAT_INMUEBLE, LON_INMUEBLE, HUELLA_CUADRADA,
            proveedores=[si.obtener_proveedor(si.NO_IMAGE_AVAILABLE)])
        analisis = fs.FacadeSolarExposure.desde_vista_callejera(
            LAT_INMUEBLE, LON_INMUEBLE, agg, fecha="2026-03-21", hora=12.0)
        out = analisis.analyze()
        self.assertEqual(agg["status"], si.NOT_SUPPORTED)
        self.assertEqual(out["estado"], fs.INSUFFICIENT_GEOMETRY)
        self.assertIn("AZIMUT_FACHADA_VISIBLE", out["geometria_faltante"])
        self.assertEqual(out["shadow_confidence"], fs.SHADOW_CONFIDENCE_DEGRADED)

    def test_vista_callejera_disponible_deriva_la_normal_de_la_fachada(self):
        vista = si.seleccionar_vista_automatica(
            [{"image_id": "IMG-S", "camera_lat": LAT_CAM_SUR_12M, "camera_lon": LON_INMUEBLE,
              "is_pano": True, "capture_date": "2024-05-01", "provider": si.MAPILLARY,
              "attribution": "© Mapillary contributors"}],
            coordenada_oficial=(LAT_INMUEBLE, LON_INMUEBLE), proveedor=si.MAPILLARY)
        out = fs.FacadeSolarExposure.desde_vista_callejera(
            LAT_INMUEBLE, LON_INMUEBLE, vista, fecha="2026-03-21", hora=12.0).exposicion()
        fachada = out["fachada_visible"]
        self.assertEqual(fachada["metodo"], "NORMAL_FACHADA_VISIBLE_DESDE_CAMARA_CALLEJERA")
        # Cámara al sur del inmueble → la vista visible mira al SUR (180°).
        self.assertAlmostEqual(fachada["azimut_normal"], 180.0, places=2)
        self.assertIn(out["estado"], fs.ESTADOS_EXPOSICION)
        self.assertEqual(out["provenance"]["inputs"]["imagery_provider"], si.MAPILLARY)
        self.assertEqual(out["etiqueta"], fs.ETIQUETA_ANALISIS_SOLAR)
        self.assertFalse(out["es_medicion_fisica"])

    def test_huecos_de_geometria_se_declaran_y_no_se_suponen(self):
        out = fs.FacadeSolarExposure(lat=LAT_INMUEBLE, lon=LON_INMUEBLE).exposicion()
        self.assertEqual(out["estado"], fs.INSUFFICIENT_GEOMETRY)
        self.assertIn("POSICION_SOLAR", out["geometria_faltante"])
        self.assertIn("AZIMUT_FACHADA_VISIBLE", out["geometria_faltante"])
        self.assertTrue(out["motivo"])
        self.assertFalse(out["human_input_required"])


if __name__ == "__main__":
    unittest.main()
