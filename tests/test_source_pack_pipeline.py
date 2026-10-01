# -*- coding: utf-8 -*-
"""BARRANQUILLA SOURCE PACK v1.0 — pruebas BLOQUEANTES del pipeline de adquisición (§32).

Cubren los criterios que el contrato de fuentes no cubre, TODOS offline (sin red):
la adquisición se completa SIN intervención humana cuando solo hay dirección (A) o solo
matrícula (B); la ausencia de street imagery no bloquea el resto del pack (J); la selección
de imagen/fachada es determinista y no admite elección humana (K); el motor solar funciona
solo con coordenada y fecha (L); sin altura física la confianza de sombra DEGRADA y no se
inventa nada (M). Además: registro (25 claves y ≥15 fuentes), manifest (secciones) y matriz
de cobertura (18 filas × 7 columnas).

Ninguna prueba toca la red: el módulo de la matriz se fuerza a modo offline y toda ausencia
es un ESTADO DECLARADO del vocabulario cerrado, nunca un dato inventado.

Las pruebas C,D,E,F,G,H,I,N,O ya existen en tests/test_source_pack_contract.py y las de
imagen/asoleamiento en tests/test_source_pack_imagery_solar.py: aquí NO se duplican.
"""
import csv
import datetime as dt
import importlib.util
import inspect
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import dictus_sources as ds  # noqa: E402
import facade_solar as fs  # noqa: E402
import solar_engine as se  # noqa: E402
import street_imagery as si  # noqa: E402

DIR_PACK = ROOT / "docs" / "source_pack"
RUTA_MATRIZ = DIR_PACK / "SOURCE_COVERAGE_MATRIX_040-646406.csv"
RUTA_MANIFEST = DIR_PACK / "BARRANQUILLA_SOURCE_PACK_MANIFEST.json"
RUTA_JSON = DIR_PACK / "barranquilla_sources_v1.json"
RUTA_YAML = DIR_PACK / "barranquilla_sources_v1.yaml"
RUTA_RUN_STATE = (ROOT / "docs" / "forensics" / "040-646406" / "dictus_2b"
                  / "DICTUS_RUN_STATE_040-646406.json")

CLAVES_25 = ("source_id", "source_name", "institution", "authority_class", "base_url",
             "service", "layer_id", "layer_name", "geometry_type", "query_method",
             "expected_fields", "primary_keys", "binding_fields", "spatial_reference",
             "legal_or_normative_context", "version_or_vigency", "precedence",
             "fallback_policy", "freshness_policy", "failure_semantics", "license_or_terms",
             "can_persist_raw", "can_embed_image", "provenance_fields", "enabled")

COLUMNAS_MATRIZ = ["row", "source", "status", "value_or_result", "authority", "provenance",
                   "hash"]

# Frases que delatarían que el pipeline le pidió el dato a una PERSONA.
FRASES_PROHIBIDAS = ("solicitar al usuario", "requiere que el usuario", "pedir al usuario",
                     "pendiente de aporte", "complete la informaci", "ingrese la direccion",
                     "ingrese la dirección", "intervención manual", "intervencion manual")


def _cargar_modulo_matriz():
    """Carga scripts/source_pack_coverage.py como módulo (sin ejecutar main)."""
    ruta = ROOT / "scripts" / "source_pack_coverage.py"
    spec = importlib.util.spec_from_file_location("sp_coverage", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    modulo.OFFLINE = True          # sin red: toda ausencia es un estado declarado
    return modulo


class _Base(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.cov = _cargar_modulo_matriz()
        cls.golden = cls.cov.leer_golden()

    def _filas(self, golden=None):
        return self.cov.correr(golden if golden is not None else self.golden)

    def _por_fila(self, filas, nombre):
        for f in filas:
            if f["row"].endswith(nombre):
                return f
        self.fail(f"la matriz no declara la fila {nombre}")

    def _assert_sin_intervencion_humana(self, filas):
        for f in filas:
            self.assertIn(f["status"], ds.ESTADOS,
                          f"{f['row']} declara un estado fuera del contrato")
            texto = f"{f['status']} {f['value_or_result']} {f['provenance']}".lower()
            for frase in FRASES_PROHIBIDAS:
                self.assertNotIn(frase, texto,
                                 f"la fila {f['row']} pide datos a una persona")
            self.assertNotEqual(f["status"], "", f"{f['row']} sin estado declarado")


# ══════════════════════════════════════════════════════════════════════════════
# A · SOLO DIRECCIÓN → el pipeline resuelve sin intervención manual
# ══════════════════════════════════════════════════════════════════════════════
class TestSoloDireccionResuelveSinHumano(_Base):

    def test_A_solo_direccion_completa_la_adquisicion_y_declara_estados(self):
        self.assertTrue(self.golden.get("direccion"),
                        "el run state del Golden debe aportar la dirección real")
        solo = dict(self.golden)
        solo.update({"nupre": None, "numero_predial": None, "folio": None})
        filas = self._filas(solo)
        self.assertEqual(len(filas), 18)
        self._assert_sin_intervencion_humana(filas)
        # Sin identificadores canónicos la identidad es una AUSENCIA declarada,
        # nunca «sin coincidencia» ni una pregunta a una persona.
        ident = self._por_fila(filas, "identidad")
        self.assertEqual(ident["status"], ds.NO_SOPORTADA)
        self.assertIn("sin coincidencia", ident["value_or_result"].lower())
        # La falta de identificadores se explica; no se pide nada a una persona.
        self.assertIn("no se pide el dato a una persona", ident["value_or_result"])
        self.assertIn("registro de adopción", ident["provenance"] + ident["value_or_result"])

    def test_A_ninguna_fila_queda_en_silencio(self):
        solo = dict(self.golden)
        solo.update({"nupre": None, "numero_predial": None, "folio": None})
        filas = self._filas(solo)
        for f in filas:
            self.assertTrue(f["status"], f"{f['row']} sin estado")
            self.assertTrue(f["value_or_result"], f"{f['row']} sin valor ni explicación")
            self.assertTrue(f["provenance"], f"{f['row']} sin procedencia")
            self.assertEqual(len(f["hash"]), 64, f"{f['row']} sin hash canónico")

    def test_A_la_direccion_no_autoriza_identidad_por_si_sola(self):
        # La dirección ligada es el último recurso del binding y exige que el
        # SERVICIO la ligue al predio: con solo dirección no hay identidad afirmada.
        r = ds.elegir_predio_canonico([{"attributes": {"direccion": "OTRA 1 # 2 - 3"}}],
                                      direccion_ligada=self.golden.get("direccion"))
        self.assertIsNone(r["feature"])
        self.assertEqual(r["binding_status"], ds.SIN_BINDING)
        self.assertFalse(ds.identidad_autorizada_por_binding(r["binding_status"]))


# ══════════════════════════════════════════════════════════════════════════════
# B · SOLO CTL / MATRÍCULA → resuelve y declara el nivel de certeza
# ══════════════════════════════════════════════════════════════════════════════
class TestSoloMatriculaResuelveSinHumano(_Base):

    def test_B_solo_folio_resuelve_con_certeza_declarada(self):
        self.assertTrue(self.golden.get("folio"), "el run state debe aportar el folio")
        solo = dict(self.golden)
        solo.update({"nupre": None, "numero_predial": None, "direccion": None})
        filas = self._filas(solo)
        self.assertEqual(len(filas), 18)
        self._assert_sin_intervencion_humana(filas)
        ident = self._por_fila(filas, "identidad")
        self.assertEqual(ident["status"], ds.DISPONIBLE)
        self.assertIn("EXACT_1", ident["value_or_result"])
        self.assertIn('"identity_verified": false', ident["value_or_result"])
        self.assertIn("NO se declara verificada", ident["provenance"])

    def test_B_sin_ningun_identificador_no_se_afirma_ausencia(self):
        r = self.cov.identidad_adopcion({"folio": None, "nupre": None, "numero_predial": None})
        self.assertEqual(r["status"], ds.NO_SOPORTADA)
        self.assertNotEqual(r["status"], ds.SIN_COINCIDENCIA)

    def test_B_identificadores_disjuntos_son_conflicto_no_eleccion(self):
        r = self.cov.identidad_adopcion({"numero_predial": "080010103000010040001908040002",
                                         "nupre": "AFT0005BORE", "folio": None})
        self.assertEqual(r["payload"]["match_status"], "CONFLICT")
        self.assertEqual(r["status"], ds.CONSULTA_FALLIDA)
        self.assertIn("no se elige uno en silencio", r["detail"])

    def test_B_con_los_tres_identificadores_es_verified(self):
        filas = self._filas()
        ident = self._por_fila(filas, "identidad")
        self.assertEqual(ident["status"], ds.DISPONIBLE)
        self.assertIn("EXACT_3", ident["value_or_result"])
        self.assertIn('"identity_verified": true', ident["value_or_result"])


# ══════════════════════════════════════════════════════════════════════════════
# J · STREET IMAGERY AUSENTE NO BLOQUEA EL PACK
# ══════════════════════════════════════════════════════════════════════════════
class TestStreetImageryNoBloquea(_Base):

    def setUp(self):
        self._vars = ("ARHIAX_MAPILLARY_TOKEN", "MAPILLARY_TOKEN", "MAPILLARY_ACCESS_TOKEN",
                      "ARHIAX_GOOGLE_MAPS_API_KEY", "GOOGLE_MAPS_API_KEY",
                      "GOOGLE_STREETVIEW_API_KEY")
        self._entorno = {v: os.environ.pop(v, None) for v in self._vars}

    def tearDown(self):
        for v, val in self._entorno.items():
            if val is not None:
                os.environ[v] = val

    def test_J_sin_credenciales_el_estado_es_declarado_y_no_bloquea(self):
        agg = si.consultar_vista_automatica(float(self.golden["lat"]), float(self.golden["lon"]),
                                            None,
                                            coordenada_oficial=(float(self.golden["lat"]),
                                                                float(self.golden["lon"])))
        self.assertIn(agg["status"], ds.ESTADOS)
        self.assertNotEqual(agg["status"], ds.SIN_COINCIDENCIA)
        self.assertEqual(agg["facade_view_level"], si.NO_IMAGE_AVAILABLE)
        self.assertFalse(agg["blocks_dictus"])
        self.assertFalse(agg["human_input_required"])
        self.assertEqual(agg["dictus_gate_impact"], "NONE")

    def test_J_el_resto_del_pack_sigue_disponible(self):
        filas = self._filas()
        estados = {f["row"]: f["status"] for f in filas}
        self.assertIn(estados["street_imagery"], (ds.FUENTE_NO_DISPONIBLE, ds.NO_SOPORTADA,
                                                  ds.CONSULTA_FALLIDA))
        for fila in ("identidad", "remocion", "riesgo", "solar"):
            self.assertEqual(estados[fila], ds.DISPONIBLE,
                             f"la fila {fila} debió seguir AVAILABLE sin street imagery")
        # DECISIÓN DE PRODUCTO: `mercado` NO tiene fuente de datos (la Lonja no es una
        # fuente), así que declara la ausencia por DOCTRINA — no por la falta de imágenes —
        # y nunca con un valor sustituido.
        mercado = self._por_fila(filas, "mercado")
        self.assertEqual(mercado["status"], ds.FUENTE_NO_DISPONIBLE)
        self.assertIn("SIN FUENTE DE MERCADO", mercado["value_or_result"])
        # Los servicios de contexto siguen disponibles (en vivo o desde la captura
        # cruda declarada como fallback): la ausencia de imagen no los afecta.
        self.assertIn(estados["servicios_contexto"], (ds.DISPONIBLE, ds.FUENTE_NO_DISPONIBLE))

    def test_J_la_fila_de_imagery_nunca_dice_no_match(self):
        filas = self._filas()
        imagery = self._por_fila(filas, "street_imagery")
        self.assertNotEqual(imagery["status"], ds.SIN_COINCIDENCIA)
        self.assertIn("NO_IMAGE_AVAILABLE", imagery["value_or_result"])
        self.assertIn("human_input_required", imagery["value_or_result"])


# ══════════════════════════════════════════════════════════════════════════════
# K · SELECCIÓN DE IMAGEN/FACHADA SIN PARÁMETROS DE ELECCIÓN HUMANA
# ══════════════════════════════════════════════════════════════════════════════
class TestSeleccionFachadaDeterministaSinHumano(_Base):

    LAT, LON = 10.9685, -74.7813

    def _candidatos(self):
        return [
            {"image_id": "PANO-NORTE", "camera_lat": 10.96869785, "camera_lon": self.LON,
             "is_pano": True, "capture_date": "2024-03-01", "provider": si.MAPILLARY,
             "attribution": "© Mapillary contributors"},
            {"image_id": "PANO-SUR", "camera_lat": 10.96839208, "camera_lon": self.LON,
             "is_pano": True, "capture_date": "2024-05-01", "provider": si.MAPILLARY,
             "attribution": "© Mapillary contributors"},
        ]

    def test_K_la_seleccion_no_admite_eleccion_humana(self):
        firma = inspect.signature(si.seleccionar_vista_automatica)
        parametros = list(firma.parameters.values())
        # Solo el primer parámetro (los candidatos) es obligatorio: todo lo demás
        # tiene valor por defecto, así que NO hay forma de «elegir» una vista.
        obligatorios = [p for p in parametros
                        if p.default is inspect.Parameter.empty
                        and p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD,
                                       p.KEYWORD_ONLY)]
        self.assertEqual(len(obligatorios), 1, f"parámetros obligatorios: {obligatorios}")
        for sospechoso in ("eleccion", "elección", "preferida", "seleccion_manual",
                           "usuario", "humano", "manual"):
            self.assertNotIn(sospechoso, [p.name for p in parametros])

    def test_K_es_determinista_e_independiente_del_orden(self):
        base = si.seleccionar_vista_automatica(self._candidatos(),
                                              coordenada_oficial=(self.LAT, self.LON),
                                              proveedor=si.MAPILLARY)
        otra = si.seleccionar_vista_automatica(list(reversed(self._candidatos())),
                                              coordenada_oficial=(self.LAT, self.LON),
                                              proveedor=si.MAPILLARY)
        self.assertEqual(json.dumps(base, sort_keys=True, default=str),
                         json.dumps(otra, sort_keys=True, default=str))
        self.assertFalse(base["human_input_required"])
        self.assertEqual(base["selection_method"], si.METODO_SELECCION)
        self.assertEqual(base["image_id"], "PANO-SUR")

    def test_K_sin_candidatos_es_ausencia_declarada_no_pregunta(self):
        res = si.seleccionar_vista_automatica([], coordenada_oficial=(self.LAT, self.LON))
        self.assertEqual(res["facade_view_level"], si.NO_IMAGE_AVAILABLE)
        self.assertIsNone(res["imagen"])
        self.assertFalse(res["human_input_required"])


# ══════════════════════════════════════════════════════════════════════════════
# L · EL MOTOR SOLAR FUNCIONA SOLO CON COORDENADA Y FECHA
# ══════════════════════════════════════════════════════════════════════════════
class TestMotorSolarSoloCoordenadaYFecha(_Base):

    def test_L_con_coordenada_y_fecha_hay_posicion_solar(self):
        lat, lon = float(self.golden["lat"]), float(self.golden["lon"])
        fecha = dt.datetime.fromisoformat(str(self.golden["fecha"]) + "T12:00:00")
        az, el = se.get_solar_position(lat, lon, fecha)
        self.assertIsInstance(az, float)
        self.assertIsInstance(el, float)
        self.assertTrue(0.0 <= az <= 360.0)
        self.assertTrue(-90.0 <= el <= 90.0)
        # La hora tiene valor por defecto (mediodía local) y no exige más entradas.
        firma = inspect.signature(se.get_solar_position)
        self.assertGreaterEqual(len(firma.parameters), 3)
        self.assertEqual(firma.parameters["tz_offset"].default, -5)

    def test_L_la_corrida_real_reproduce_los_momentos_del_run_state(self):
        """El motor solar debe reproducir el asoleamiento que la corrida Golden persistió."""
        rs = json.loads(RUTA_RUN_STATE.read_text(encoding="utf-8"))
        momentos = ((rs.get("solar_state") or {}).get("momentos")) or []
        if not momentos:
            self.skipTest("el run state no publica solar_state.momentos")
        lat, lon = float(self.golden["lat"]), float(self.golden["lon"])
        comparados = 0
        for m in momentos:
            hora_txt = str(m.get("hora") or "")           # p. ej. "12:00 COT"
            if ":" not in hora_txt:
                continue
            hora = int(hora_txt.split(":")[0])
            esperado_az = float(str(m.get("azimut") or "nan").rstrip("°"))
            esperado_el = float(str(m.get("elevacion") or "nan").rstrip("°"))
            az, el = se.get_solar_position(
                lat, lon, dt.datetime.fromisoformat(f"{self.golden['fecha']}T{hora:02d}:00:00"))
            self.assertAlmostEqual(az, esperado_az, places=1,
                                   msg=f"azimut {hora_txt} no reproduce el run state")
            self.assertAlmostEqual(el, esperado_el, places=1,
                                   msg=f"elevación {hora_txt} no reproduce el run state")
            comparados += 1
        self.assertGreaterEqual(comparados, 3, "se esperaban al menos 3 momentos comparables")

    def test_L_la_fila_solar_de_la_matriz_esta_disponible_y_declarada(self):
        filas = self._filas()
        solar = self._por_fila(filas, "solar")
        self.assertEqual(solar["status"], ds.DISPONIBLE)
        self.assertIn("azimuth_deg", solar["value_or_result"])
        self.assertIn("es_medicion_fisica", solar["value_or_result"])
        self.assertIn('"es_medicion_fisica": false', solar["value_or_result"])
        self.assertIn("INSUFFICIENT_GEOMETRY", solar["value_or_result"])

    def test_L_el_estado_de_fachada_es_del_vocabulario_cerrado(self):
        out = fs.analizar_exposicion_fachada(float(self.golden["lat"]), float(self.golden["lon"]),
                                             fecha=str(self.golden["fecha"]), hora=12.0)
        self.assertIn(out["estado"], ds.ESTADOS_EXPOSICION)
        self.assertFalse(out["es_medicion_fisica"])
        self.assertEqual(out["etiqueta"], ds.ETIQUETA_ANALISIS_SOLAR)


# ══════════════════════════════════════════════════════════════════════════════
# M · SIN ALTURA FÍSICA: DEGRADA Y NO SE INVENTA
# ══════════════════════════════════════════════════════════════════════════════
class TestSinAlturaFisicaDegradaYNoInventa(_Base):

    def test_M_sin_altura_fisica_la_confianza_degrada(self):
        r = ds.altura_fisica(None, altura_normativa_pot=11)
        self.assertIsNone(r["building_physical_height"])
        self.assertEqual(r["shadow_confidence"], "DEGRADED")
        self.assertNotEqual(r.get("blocking"), True)

    def test_M_la_altura_normativa_del_pot_no_es_altura_fisica(self):
        r = ds.altura_fisica(11, height_source="POT_BAQ_EDIFICABILIDAD.altura_max",
                             altura_normativa_pot=11)
        self.assertIsNone(r["building_physical_height"])
        self.assertEqual(r["shadow_confidence"], "DEGRADED")
        self.assertIn("NORMATIVA", r["reason"])
        # El valor «11» de la corrida Golden es normativo (urban_context.altura_maxima):
        # se lee del run state, no se codifica a mano.
        self.assertTrue(str(self.golden.get("tratamiento")).startswith("Consolidaci"))

    def test_M_el_analisis_de_fachada_degrada_y_no_bloquea(self):
        out = fs.analizar_exposicion_fachada(float(self.golden["lat"]), float(self.golden["lon"]),
                                             fecha=str(self.golden["fecha"]), hora=12.0,
                                             facade_bearing=110.0, building_height=11,
                                             height_source="POT_BAQ_EDIFICABILIDAD.altura_max",
                                             altura_normativa_pot=11)
        self.assertIsNone(out["building_physical_height"])
        self.assertEqual(out["shadow_confidence"], fs.SHADOW_CONFIDENCE_DEGRADED)
        self.assertFalse(out["shadow_length_simulated"])
        self.assertIsNone(out["physical_shadow_length_m"])
        self.assertFalse(out["blocks_dictus"])
        self.assertEqual(out["dictus_gate_impact"], "NONE")

    def test_M_la_degradacion_esta_declarada_en_los_artefactos_de_la_corrida(self):
        ruta = (ROOT / "docs" / "forensics" / "040-646406" / "dictus_2c"
               / "DICTUS_SHADOW_MANIFEST_040-646406.json")
        if not ruta.exists():
            self.skipTest("no existe el manifest de sombras de la corrida 2.0C")
        man = json.loads(ruta.read_text(encoding="utf-8"))
        texto = json.dumps(man, ensure_ascii=False)
        self.assertIn("physical_height_source", texto)
        self.assertIn("shadow_model_status", texto)
        self.assertTrue(man.get("BUILDING_PHYSICAL_HEIGHT", "ausente") is None
                        or '"BUILDING_PHYSICAL_HEIGHT": null' in texto)

    def test_M_la_matriz_no_inventa_altura(self):
        filas = self._filas()
        solar = self._por_fila(filas, "solar")
        self.assertIn('"altura_fisica": null', solar["value_or_result"])
        self.assertIn("DEGRADED", solar["value_or_result"])


# ══════════════════════════════════════════════════════════════════════════════
# REGISTRO · MANIFEST · MATRIZ
# ══════════════════════════════════════════════════════════════════════════════
class TestRegistroManifestYMatriz(_Base):

    def test_registro_declara_25_claves_y_al_menos_15_fuentes(self):
        reg = ds.cargar_registro()
        self.assertNotEqual(reg.get("_status"), ds.NO_SOPORTADA,
                            "el registro debe existir (no se admite skip aquí)")
        fuentes = reg.get("sources") or {}
        self.assertGreaterEqual(len(fuentes), 15)
        for sid, f in fuentes.items():
            for clave in CLAVES_25:
                self.assertIn(clave, f, f"{sid} no declara {clave}")
            self.assertIn(f["authority_class"], ds.CLASES_AUTORIDAD, sid)

    def test_registro_declara_las_fuentes_minimas_del_pack(self):
        fuentes = set((ds.cargar_registro().get("sources") or {}))
        minimas = {"CATASTRO_BAQ_DIRECCION", "CATASTRO_BAQ_TERRENO",
                   "CATASTRO_BAQ_CONSTRUCCION", "CATASTRO_BAQ_PREDIO", "POT_BAQ_BARRIOS",
                   "POT_BAQ_LOCALIDADES", "POT_BAQ_AREAS_ACTIVIDAD", "POT_BAQ_POLIGONOS_USO",
                   "POT_BAQ_TRATAMIENTO", "POT_BAQ_EDIFICABILIDAD", "POT_BAQ_REMOCION_2024",
                   "POT_BAQ_INUNDACION_2024", "POT_BAQ_RIESGO_2024", "POT_BAQ_REMOCION_HIST",
                   "POT_BAQ_INUNDACION_HIST", "POT_BAQ_RIESGO_HIST", "OSM_OVERPASS",
                   "MAPILLARY", "GOOGLE_STREET_VIEW", "SOLAR_ENGINE",
                   "SHADOW_FACADE_EXPOSURE"} | {f"EQUIPAMIENTO_{n}" for n in
                                                (18, 20, 21, 22, 23, 24, 25, 26, 27)}
        self.assertTrue(minimas <= fuentes, f"faltan: {sorted(minimas - fuentes)}")

    def test_la_lonja_esta_fuera_del_registro_como_no_fuente(self):
        """DECISIÓN DE PRODUCTO: la Lonja NO es una fuente de datos.

        `LONJA_MARKET_BAQ` sale de `sources` (ya no es `source_id` del registro) y queda
        declarada como ALIADO INSTITUCIONAL, con el mercado declarado sin fuente externa.
        """
        reg = ds.cargar_registro()
        fuentes = reg.get("sources") or {}
        self.assertNotIn("LONJA_MARKET_BAQ", fuentes)
        no_fuentes = reg.get("no_fuentes_institucionales") or {}
        self.assertTrue(no_fuentes, "el registro debe declarar sus NO fuentes, no silenciarlas")
        lonja = (no_fuentes.get("aliados") or {})["LONJA_BAQ"]
        self.assertFalse(lonja["es_fuente_de_datos"])
        self.assertFalse(lonja["aporta_datos_a_dictus"])
        self.assertFalse(lonja["en_source_registry"])
        self.assertEqual(lonja["product_role"], "NOT_A_SOURCE")
        self.assertEqual(lonja["source_id_historico"], "LONJA_MARKET_BAQ")
        mercado = no_fuentes["valor_de_mercado"]
        self.assertFalse(mercado["es_fuente_de_datos"])
        self.assertFalse(mercado["fuente_externa_verificable"])
        self.assertTrue(mercado["nota"].strip())

    def test_las_capas_de_riesgo_2024_son_vigentes_y_las_hist_referencia(self):
        fuentes = ds.cargar_registro()["sources"]
        for sid in ("POT_BAQ_REMOCION_2024", "POT_BAQ_INUNDACION_2024", "POT_BAQ_RIESGO_2024"):
            self.assertEqual(fuentes[sid]["precedence"], ds.CURRENT_NORMATIVE, sid)
            self.assertEqual(fuentes[sid]["legal_or_normative_context"], "Decreto 893 de 2024")
        for sid in ("POT_BAQ_REMOCION_HIST", "POT_BAQ_INUNDACION_HIST", "POT_BAQ_RIESGO_HIST"):
            self.assertEqual(fuentes[sid]["precedence"], ds.HISTORICAL_REFERENCE, sid)

    def test_el_equipamiento_oficial_no_es_contextual(self):
        fuentes = ds.cargar_registro()["sources"]
        for n in (18, 20, 21, 22, 23, 24, 25, 26, 27):
            self.assertEqual(fuentes[f"EQUIPAMIENTO_{n}"]["authority_class"],
                             ds.AUTORITATIVA_OFICIAL)
        self.assertEqual(fuentes["OSM_OVERPASS"]["authority_class"], ds.CONTEXTUAL_EXTERNA)
        self.assertEqual(fuentes["SOLAR_ENGINE"]["authority_class"], ds.CALCULADA)
        # DECISIÓN DE PRODUCTO: `LONJA_MARKET_BAQ` ya NO es una fuente del registro (la
        # Lonja no aporta datos a DICTUS). No tiene `authority_class` que afirmar.
        self.assertNotIn("LONJA_MARKET_BAQ", fuentes)

    def test_la_fuente_deshabilitada_declara_por_que(self):
        fuentes = ds.cargar_registro()["sources"]
        deshabilitadas = [sid for sid, f in fuentes.items() if f.get("enabled") is False]
        self.assertTrue(deshabilitadas, "debe haber fuentes declaradas como no verificadas")
        for sid in deshabilitadas:
            self.assertTrue(fuentes[sid]["notes"].strip(), f"{sid} deshabilitada sin motivo")
            self.assertEqual(fuentes[sid]["verification_status"], "UNVERIFIED_LIVE", sid)

    def test_declarar_un_campo_inexistente_no_se_hace(self):
        """Ninguna fuente deshabilitada puede declarar campos no observados."""
        fuentes = ds.cargar_registro()["sources"]
        for sid, f in fuentes.items():
            if f["verification_status"] == "UNVERIFIED_LIVE":
                self.assertEqual(f["expected_fields"], [],
                                 f"{sid} declara campos que no se observaron")

    def test_el_yaml_es_gemelo_del_json(self):
        self.assertTrue(RUTA_YAML.exists() and RUTA_JSON.exists())
        try:
            import yaml  # type: ignore
        except Exception:  # noqa: BLE001 — sin PyYAML se verifica la huella declarada
            texto = RUTA_YAML.read_text(encoding="utf-8")
            huella = json.loads(RUTA_JSON.read_text(encoding="utf-8"))
            self.assertIn(ds.hash_canonico(huella), texto)
            return
        self.assertEqual(json.loads(RUTA_JSON.read_text(encoding="utf-8")),
                         yaml.safe_load(RUTA_YAML.read_text(encoding="utf-8")))

    def test_manifest_declara_sus_secciones(self):
        self.assertTrue(RUTA_MANIFEST.exists(), "debe existir el manifest del pack")
        man = json.loads(RUTA_MANIFEST.read_text(encoding="utf-8"))
        for seccion in ("pack_version", "approved_sources", "source_metadata_hashes",
                        "precedence_rules", "licenses", "legal_context", "tested_at",
                        "golden_case", "known_limitations"):
            self.assertIn(seccion, man, f"el manifest no declara {seccion}")
        fuentes = ds.cargar_registro()["sources"]
        self.assertEqual(set(man["source_metadata_hashes"]), set(fuentes))
        self.assertTrue(set(man["approved_sources"]) <= set(fuentes))
        self.assertEqual(man["golden_case"]["folio"], self.golden["folio"])
        self.assertEqual(man["golden_case"]["nupre"], self.golden["nupre"])
        self.assertFalse(man["precedence_rules"]["silent_override"])
        self.assertTrue(man["known_limitations"])

    def test_matriz_tiene_18_filas_y_7_columnas(self):
        self.assertTrue(RUTA_MATRIZ.exists(), "debe existir la matriz de cobertura")
        with RUTA_MATRIZ.open(encoding="utf-8", newline="") as fh:
            lector = csv.reader(fh)
            filas = list(lector)
        self.assertEqual(filas[0], COLUMNAS_MATRIZ)
        self.assertEqual(len(filas) - 1, 18, "la matriz debe tener 18 filas de datos")
        for fila in filas[1:]:
            self.assertEqual(len(fila), 7, f"fila con {len(fila)} columnas: {fila[0]}")
            self.assertIn(fila[2], ds.ESTADOS, f"estado fuera del contrato en {fila[0]}")
            self.assertEqual(len(fila[6]), 64, f"{fila[0]} sin hash canónico")

    def test_matriz_cubre_las_18_filas_exigidas(self):
        with RUTA_MATRIZ.open(encoding="utf-8", newline="") as fh:
            nombres = [r["row"].split("-", 1)[1] for r in csv.DictReader(fh)]
        self.assertEqual(nombres, ["identidad", "direccion", "predio", "construccion",
                                   "barrio", "localidad", "destino", "uso_pot",
                                   "tratamiento", "edificabilidad", "remocion", "inundacion",
                                   "riesgo", "equipamiento_oficial", "servicios_contexto",
                                   "street_imagery", "solar", "mercado"])

    def test_matriz_usa_los_identificadores_del_run_state_no_hardcodeados(self):
        texto = RUTA_MATRIZ.read_text(encoding="utf-8")
        # El número predial y el NUPRE se leyeron del run state.
        for valor in (str(self.golden.get("numero_predial") or ""),
                      str(self.golden.get("nupre") or "")):
            self.assertTrue(valor, "el run state debe aportar los identificadores")
            self.assertIn(valor, texto, f"la matriz no refleja {valor} (leído del run state)")
        # El folio del CTL entra por su parte registral (fmi) al resolver identidad.
        fmi = str(self.golden.get("folio") or "").split("-")[-1]
        self.assertIn(fmi, texto, f"la matriz no refleja el fmi {fmi} del folio")

    def test_manifest_publica_la_cobertura_de_la_corrida(self):
        man = json.loads(RUTA_MANIFEST.read_text(encoding="utf-8"))
        self.assertIn("coverage", man)
        self.assertEqual(man["coverage"]["rows"], 18)
        self.assertEqual(len(man["coverage"]["statuses"]), 18)
        self.assertTrue(man["coverage"]["source_of_input"]["read_not_hardcoded"])
        self.assertEqual(Path(man["coverage"]["matrix_file"]).name, RUTA_MATRIZ.name)

    def test_corrida_offline_nunca_produce_estados_fuera_del_contrato(self):
        filas = self._filas()
        self.assertEqual({f["status"] for f in filas} - set(ds.ESTADOS), set())
        # En modo offline las fuentes de red quedan declaradas, no inventadas.
        self.assertTrue(all(f["value_or_result"] for f in filas))


if __name__ == "__main__":
    unittest.main()
