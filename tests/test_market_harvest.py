# -*- coding: utf-8 -*-
"""MARKET HARVEST — pruebas OFFLINE (sin red) de la adquisición de evidencia de mercado.

Todo aquí corre SIN red: el transporte se sustituye por un `fetch_fn` falso declarado en
el propio archivo. Se prueba lo que puede hacer daño si se rompe:

  1. **Procedencia OBLIGATORIA.** Si falta URL, `queried_at`, `http_status`, bytes o
     sha256 —o el sha256 no es un sha256— el resultado NO puede ser `EXTERNAL_SOURCE`
     utilizable: se degrada. Igual si la respuesta no fue un HTTP 200.
  2. **`MANUAL_CONFIG` / `MODEL_PRIOR` / `STATIC_REFERENCE` / `LEGACY_MODEL_PRIOR` JAMÁS se
     etiquetan como externos**, ni siquiera con procedencia completa.
  3. **Ausencia ≠ `NO_MATCH`.** No poder consultar es `SOURCE_UNAVAILABLE`; romper el
     parseo es `QUERY_FAILED`; `NO_MATCH` exige consulta EJECUTADA con éxito contra una
     capa que tiene datos.
  4. **Nada de valores por defecto.** No se promedia el rango declarado, no se inventa
     `sample_size`, no se rellena con `0`, no se elige capa «a dedo».
  5. **El payload crudo se preserva byte a byte** y su sha256 reproduce el declarado.

Las lecturas del Golden (`docs/estimation/MARKET_HARVEST_040-646406.json` y
`docs/estimation/raw/**`) son del producto REAL y se comprueban por INVARIANTES
estructurales, nunca fijando las cifras: si la fuente republicara sus datos, la prueba
sigue siendo válida sin dejar de vigilar la doctrina.
"""
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import market_evidence as me                       # noqa: E402
import market_harvest as mh                        # noqa: E402

GOLDEN_JSON = ROOT / "docs" / "estimation" / "MARKET_HARVEST_040-646406.json"
RAW_DIR = ROOT / "docs" / "estimation" / "raw"


# ══════════════════════════════════════════════════════════════════════════════
# Utilidades de laboratorio (datos de prueba, NO datos del producto)
# ══════════════════════════════════════════════════════════════════════════════
def _raw(url, status, cuerpo, queried_at="2026-09-30T12:00:00+00:00"):
    """RawFetch de laboratorio con cuerpo JSON o bytes crudos."""
    if isinstance(cuerpo, (bytes, bytearray)):
        body = bytes(cuerpo)
    elif isinstance(cuerpo, str):
        body = cuerpo.encode("utf-8")
    else:
        body = json.dumps(cuerpo, ensure_ascii=False).encode("utf-8")
    return mh.RawFetch(url=url, http_status=status, body=body, queried_at=queried_at)


class FetchFalso:
    """Transporte falso: enruta por subcadena de URL. NO simula red, la sustituye."""

    def __init__(self, rutas):
        self.rutas = list(rutas)
        self.llamadas = []

    def __call__(self, url, timeout=30, **kw):
        self.llamadas.append(url)
        for aguja, respuesta in self.rutas:
            if aguja in url:
                return respuesta(url) if callable(respuesta) else respuesta
        raise AssertionError(f"FetchFalso: URL no declarada en el laboratorio: {url}")


def _meta_valoresm2():
    """Metadata REAL-shaped del servicio de bandas por área."""
    return {"currentVersion": 11.5,
            "layers": [
                {"id": 1, "name": "Rango valores por m². Área (36-60m²).",
                 "geometryType": "esriGeometryPolygon"},
                {"id": 2, "name": "Rango valores por m². Área (61-175m²).",
                 "geometryType": "esriGeometryPolygon"},
                {"id": 3, "name": "Rango valores por m². Área (176-290m²)",
                 "geometryType": "esriGeometryPolygon"},
                {"id": 4, "name": "Rango valores por m². Área (>291m²)",
                 "geometryType": "esriGeometryPolygon"},
            ]}


def _feature(nombre, banda, lo, hi):
    return {"attributes": {"objectid": 5, "nombre": nombre, "area_construida": banda,
                           "min_valor_m2": lo, "max_valor_m2": hi}}


SUJETO = mh.Sujeto(folio="TEST-000", barrio="Miramar", localidad="02",
                   codigo_manzana="08001010300001004", estrato="4",
                   tipologia="Unidad En Propiedad Horizontal", area_m2=58.75,
                   lat=11.006055954316363, lon=-74.8375696549899)

SPEC_BANDA = mh.capas_por_source_id()["BAQ_OBS_VALORESM2_AREA"]
SPEC_SUELO = mh.capas_por_source_id()["BAQ_OBS_VALORSUELOURBANO"]


def _fetch_banda_ok(minimo=1000.0, maximo=2000.0, *, punto_features=1):
    """Transporte que sirve la banda del sujeto con un rango declarado."""
    cuerpo = ({"features": [_feature("Norte - centro histórico", "36-60", minimo, maximo)]}
              if punto_features else {"features": []})
    return FetchFalso([
        ("/MapServer?f=json", _raw("meta", 200, _meta_valoresm2())),
        ("/MapServer/1/query", _raw("q", 200, cuerpo)),
    ])


# ══════════════════════════════════════════════════════════════════════════════
# 1 · Estados: ausencia NO es NO_MATCH
# ══════════════════════════════════════════════════════════════════════════════
class TestEstadosCerrados(unittest.TestCase):
    def test_estados_no_mezclan_ausencia_con_no_match(self):
        self.assertIn(mh.STATUS_SOURCE_UNAVAILABLE, mh.ESTADOS_AUSENCIA)
        self.assertIn(mh.STATUS_QUERY_FAILED, mh.ESTADOS_AUSENCIA)
        self.assertIn(mh.STATUS_NOT_SUPPORTED, mh.ESTADOS_AUSENCIA)
        self.assertNotIn(mh.STATUS_NO_MATCH, mh.ESTADOS_AUSENCIA,
                         "NO_MATCH NO es una ausencia: es una respuesta de la fuente")
        self.assertNotIn(mh.STATUS_OK, mh.ESTADOS_AUSENCIA)

    def test_vocabulario_cerrado(self):
        for estado in mh.ESTADOS_HARVEST:
            self.assertIsInstance(estado, str)
        self.assertEqual(len(set(mh.ESTADOS_HARVEST)), len(mh.ESTADOS_HARVEST))


# ══════════════════════════════════════════════════════════════════════════════
# 2 · Procedencia obligatoria
# ══════════════════════════════════════════════════════════════════════════════
class TestProcedenciaObligatoria(unittest.TestCase):
    def _prov(self, **cambios):
        base = {"source_id": "S", "proveedor": "P", "fecha": "2026-09-30",
                "referencia": "r", "url": "https://x/y",
                "queried_at": "2026-09-30T12:00:00+00:00", "http_status": 200,
                "bytes": 10, "sha256": "a" * 64}
        base.update(cambios)
        return base

    def test_procedencia_completa_habilita_externo(self):
        r = mh.clasificar_procedencia_harvest(
            {"origen_tipo": mh.ORIGEN_EXTERNO, "provenance": self._prov()})
        self.assertEqual(r["origin"], mh.ORIGEN_EXTERNO)
        self.assertTrue(r["origin_gate"])

    def test_cada_campo_faltante_degrada(self):
        """Falta CUALQUIERA de los 5 campos → no puede ser EXTERNAL_SOURCE utilizable."""
        for campo in mh.CAMPOS_PROVENANCE_OBLIGATORIOS:
            with self.subTest(campo=campo):
                prov = self._prov()
                prov.pop(campo)
                r = mh.clasificar_procedencia_harvest(
                    {"origen_tipo": mh.ORIGEN_EXTERNO, "provenance": prov})
                self.assertEqual(r["origin"], mh.ORIGEN_MANUAL)
                self.assertFalse(r["origin_gate"])
                self.assertIn(campo, r["provenance_faltante"])
                self.assertTrue(r["origin_blockers"])

    def test_campo_vacio_cuenta_como_faltante(self):
        for campo in mh.CAMPOS_PROVENANCE_OBLIGATORIOS:
            with self.subTest(campo=campo):
                prov = self._prov(**{campo: ""})
                r = mh.clasificar_procedencia_harvest(
                    {"origen_tipo": mh.ORIGEN_EXTERNO, "provenance": prov})
                self.assertFalse(r["origin_gate"])

    def test_sha256_invalido_degrada(self):
        for malo in ("a" * 63, "a" * 65, "z" * 64, "no-es-un-hash", 12345):
            with self.subTest(sha256=malo):
                r = mh.clasificar_procedencia_harvest(
                    {"origen_tipo": mh.ORIGEN_EXTERNO,
                     "provenance": self._prov(sha256=malo)})
                self.assertEqual(r["origin"], mh.ORIGEN_MANUAL)
                self.assertFalse(r["origin_gate"])
                self.assertIn("sha256", r["provenance_faltante"])

    def test_http_status_no_200_degrada(self):
        for estado in (403, 404, 500, None):
            with self.subTest(http_status=estado):
                r = mh.clasificar_procedencia_harvest(
                    {"origen_tipo": mh.ORIGEN_EXTERNO,
                     "provenance": self._prov(http_status=estado)})
                self.assertFalse(r["origin_gate"])
                self.assertEqual(r["origin"], mh.ORIGEN_MANUAL)

    def test_provenance_ausente_o_no_mapping(self):
        for prov in (None, {}, [], "texto"):
            with self.subTest(prov=prov):
                r = mh.clasificar_procedencia_harvest(
                    {"origen_tipo": mh.ORIGEN_EXTERNO, "provenance": prov})
                self.assertFalse(r["origin_gate"])
                self.assertEqual(len(r["provenance_faltante"]),
                                 len(mh.CAMPOS_PROVENANCE_OBLIGATORIOS))

    def test_rawfetch_calcula_sha256_de_los_bytes_exactos(self):
        cuerpo = b'{"a":1}'
        raw = mh.RawFetch(url="u", http_status=200, body=cuerpo, queried_at="t")
        self.assertEqual(raw.sha256, hashlib.sha256(cuerpo).hexdigest())
        self.assertEqual(raw.bytes, len(cuerpo))

    def test_rawfetch_sin_respuesta_no_inventa_hash(self):
        raw = mh.RawFetch(url="u", http_status=None, body=b"", queried_at="t")
        self.assertIsNone(raw.sha256)


# ══════════════════════════════════════════════════════════════════════════════
# 3 · MANUAL_CONFIG / MODEL_PRIOR NUNCA son externos
# ══════════════════════════════════════════════════════════════════════════════
class TestNoHabilitantesNuncaExternos(unittest.TestCase):
    PROV_COMPLETA = {"source_id": "S", "proveedor": "P", "fecha": "2026-09-30",
                     "referencia": "r", "url": "https://x/y",
                     "queried_at": "2026-09-30T12:00:00+00:00", "http_status": 200,
                     "bytes": 10, "sha256": "b" * 64}

    def test_origenes_no_habilitantes_jamas_se_promueven(self):
        """Aunque la procedencia sea COMPLETA, un origen no habilitante no se promueve."""
        for origen in (mh.ORIGEN_MANUAL, mh.ORIGEN_PRIOR, mh.ORIGEN_ESTATICO,
                       mh.ORIGEN_LEGACY_PRIOR):
            with self.subTest(origen=origen):
                r = mh.clasificar_procedencia_harvest(
                    {"origen_tipo": origen, "provenance": self.PROV_COMPLETA})
                self.assertEqual(r["origin"], origen)
                self.assertNotEqual(r["origin"], mh.ORIGEN_EXTERNO)
                self.assertFalse(r["origin_gate"])
                self.assertTrue(r["origin_blockers"])

    def test_origen_no_declarado_es_manual(self):
        for decl in ({}, {"provenance": self.PROV_COMPLETA}, {"origen_tipo": None},
                     {"origen_tipo": "INVENTADO"}):
            with self.subTest(decl=decl):
                r = mh.clasificar_procedencia_harvest(decl)
                self.assertEqual(r["origin"], mh.ORIGEN_MANUAL)
                self.assertFalse(r["origin_gate"])

    def test_sostiene_estimacion_solo_con_origen_habilitante(self):
        self.assertTrue(mh.origin_sostiene_estimacion(mh.ORIGEN_EXTERNO))
        self.assertTrue(mh.origin_sostiene_estimacion(mh.ORIGEN_COMPUTADO))
        for origen in (mh.ORIGEN_MANUAL, mh.ORIGEN_PRIOR, mh.ORIGEN_ESTATICO,
                       mh.ORIGEN_LEGACY_PRIOR, None, "CUALQUIERA"):
            self.assertFalse(mh.origin_sostiene_estimacion(origen))

    def test_vocabulario_coincide_con_el_contrato_de_evidencia(self):
        self.assertEqual(set(mh.ORIGENES), set(me.ORIGENES))
        self.assertEqual(mh.ORIGENES_HABILITANTES, me.ORIGENES_HABILITANTES)


# ══════════════════════════════════════════════════════════════════════════════
# 4 · Ausencia ≠ NO_MATCH (extremo a extremo con transporte falso)
# ══════════════════════════════════════════════════════════════════════════════
class TestAusenciaNoEsNoMatch(unittest.TestCase):
    def test_403_es_source_unavailable_y_no_no_match(self):
        f = FetchFalso([
            ("/MapServer?f=json", _raw("u", 403, b"<html>Just a moment...</html>")),
        ])
        r = mh.adquirir_capa(SPEC_BANDA, SUJETO, fetch_fn=f)
        self.assertEqual(r["status"], mh.STATUS_SOURCE_UNAVAILABLE)
        self.assertNotEqual(r["status"], mh.STATUS_NO_MATCH)
        self.assertFalse(r["usable_for_estimation"])
        self.assertEqual(r["origin"], mh.ORIGEN_MANUAL)
        self.assertFalse(r["origin_gate"])
        # El 403 se documenta con su evidencia real, incluido el hash del bloqueo.
        self.assertEqual(r["http_status"], 403)
        self.assertIsNotNone(r["sha256"])

    def test_timeout_es_source_unavailable(self):
        def explotar(url, timeout=30, **kw):
            raise TimeoutError("timed out")

        r = mh.adquirir_capa(SPEC_BANDA, SUJETO, fetch_fn=explotar)
        self.assertEqual(r["status"], mh.STATUS_SOURCE_UNAVAILABLE)
        self.assertIsNone(r["http_status"])
        self.assertIsNone(r["sha256"])

    def test_json_invalido_es_query_failed(self):
        f = FetchFalso([("/MapServer?f=json", _raw("u", 200, b"<<no es json>>"))])
        r = mh.adquirir_capa(SPEC_BANDA, SUJETO, fetch_fn=f)
        self.assertEqual(r["status"], mh.STATUS_QUERY_FAILED)
        self.assertNotEqual(r["status"], mh.STATUS_NO_MATCH)

    def test_error_arcgis_es_query_failed(self):
        f = FetchFalso([
            ("/MapServer?f=json", _raw("u", 200, _meta_valoresm2())),
            ("/MapServer/1/query", _raw("q", 200, {"error": {"code": 400,
                                                             "message": "Invalid query"}})),
        ])
        r = mh.adquirir_capa(SPEC_BANDA, SUJETO, fetch_fn=f)
        self.assertEqual(r["status"], mh.STATUS_QUERY_FAILED)

    def test_features_vacias_con_http_200_es_no_match(self):
        """Consulta EJECUTADA con éxito y capa CON datos, pero sin dato del sujeto."""
        f = _fetch_banda_ok(punto_features=0)
        r = mh.adquirir_capa(SPEC_BANDA, SUJETO, fetch_fn=f)
        self.assertEqual(r["status"], mh.STATUS_NO_MATCH)
        self.assertEqual(r["http_status"], 200)
        self.assertFalse(r["usable_for_estimation"])

    def test_no_match_exige_que_la_consulta_se_haya_ejecutado(self):
        """Si NADIE respondió (no hubo 200), el estado NO puede ser NO_MATCH."""
        f = FetchFalso([
            ("/MapServer?f=json", _raw("u", 200, _meta_valoresm2())),
            ("/MapServer/1/query", _raw("q", 503, b"upstream error")),
        ])
        r = mh.adquirir_capa(SPEC_BANDA, SUJETO, fetch_fn=f)
        self.assertNotEqual(r["status"], mh.STATUS_NO_MATCH)
        self.assertEqual(r["status"], mh.STATUS_SOURCE_UNAVAILABLE)

    def test_sin_coordenadas_es_source_unavailable(self):
        sujeto = mh.Sujeto(folio="X", area_m2=58.75, codigo_manzana=None, lat=None, lon=None)
        f = _fetch_banda_ok()
        r = mh.adquirir_capa(SPEC_BANDA, sujeto, fetch_fn=f)
        self.assertEqual(r["status"], mh.STATUS_SOURCE_UNAVAILABLE)
        self.assertFalse(r["usable_for_estimation"])


# ══════════════════════════════════════════════════════════════════════════════
# 5 · Nada de valores por defecto
# ══════════════════════════════════════════════════════════════════════════════
class TestCeroValoresInventados(unittest.TestCase):
    def test_no_se_promedia_el_rango(self):
        """La fuente declara min/max: el resultado NO puede contener el promedio."""
        f = _fetch_banda_ok(1000.0, 3000.0)
        r = mh.adquirir_capa(SPEC_BANDA, SUJETO, fetch_fn=f)
        ref = mh.referencia_nivel_3(r, SUJETO, market_evidence=me)
        self.assertIsNotNone(ref)
        self.assertIsNone(ref["valor_m2"],
                          "la fuente NO declara valor único: no se deriva un promedio")
        self.assertEqual(ref["rango_valor_m2"]["min"], 1000.0)
        self.assertEqual(ref["rango_valor_m2"]["max"], 3000.0)
        promedio = (1000.0 + 3000.0) / 2.0
        for clave, valor in _numeros(ref).items():
            with self.subTest(campo=clave):
                self.assertNotEqual(valor, promedio,
                                    f"{clave} contiene el promedio inventado del rango")

    def test_sample_size_no_se_inventa(self):
        f = _fetch_banda_ok()
        r = mh.adquirir_capa(SPEC_BANDA, SUJETO, fetch_fn=f)
        self.assertIsNone(r["sample_size"],
                          "la capa no declara N: el sample_size NO se rellena")

    def test_sample_size_se_lee_cuando_la_fuente_lo_declara(self):
        spec = mh.capas_por_source_id()["BAQ_OBS_ARRENDAMIENTOS"]
        f = FetchFalso([
            ("/MapServer?f=json", _raw("m", 200, {"layers": [{"id": 1, "name": "x"}]})),
            ("/query", _raw("q", 200, {"features": [{"attributes": {
                "codigo_manzana": SUJETO.codigo_manzana, "cantidad_ofertas": 48,
                "valor_promedio": 100.0}}]})),
        ])
        r = mh.adquirir_capa(spec, SUJETO, fetch_fn=f)
        self.assertEqual(r["sample_size"], 48)

    def test_valor_ausente_queda_none_y_no_cero(self):
        f = FetchFalso([
            ("/MapServer?f=json", _raw("m", 200, _meta_valoresm2())),
            ("/MapServer/1/query", _raw("q", 200, {"features": [{"attributes": {
                "objectid": 5, "nombre": "Z", "area_construida": "36-60"}}]})),
        ])
        r = mh.adquirir_capa(SPEC_BANDA, SUJETO, fetch_fn=f)
        self.assertIsNone(r["value_or_range"]["min_valor_m2"])
        self.assertIsNone(r["value_or_range"]["max_valor_m2"])
        self.assertIsNone(mh.referencia_nivel_3(r, SUJETO),
                          "sin extremos declarados no hay referencia agregada")

    def test_ningun_tipo_no_habilitante_marca_usable(self):
        for tipo in mh.TIPOS_REFERENCIA:
            with self.subTest(tipo=tipo):
                if tipo in mh.TIPOS_QUE_SOSTIENEN_ESTIMACION:
                    continue
                self.assertFalse(mh.TIPOS_QUE_SOSTIENEN_ESTIMACION & {tipo})

    def test_referencia_nunca_usable_sin_procedencia(self):
        f = _fetch_banda_ok()
        r = mh.adquirir_capa(SPEC_BANDA, SUJETO, fetch_fn=f)
        for campo in mh.CAMPOS_PROVENANCE_OBLIGATORIOS:
            with self.subTest(campo=campo):
                roto = dict(r)
                roto["provenance"] = {k: v for k, v in r["provenance"].items()
                                      if k != campo}
                self.assertIsNone(mh.referencia_nivel_3(roto, SUJETO),
                                  f"sin {campo} la referencia NO puede emitirse")

    def test_referencia_nunca_usable_sin_origen_gate(self):
        f = _fetch_banda_ok()
        r = mh.adquirir_capa(SPEC_BANDA, SUJETO, fetch_fn=f)
        for origen in (mh.ORIGEN_MANUAL, mh.ORIGEN_PRIOR, mh.ORIGEN_ESTATICO,
                       mh.ORIGEN_LEGACY_PRIOR):
            with self.subTest(origen=origen):
                r2 = dict(r, origin=origen, origin_gate=False)
                self.assertIsNone(mh.referencia_nivel_3(r2, SUJETO))

    def test_referencia_nunca_usable_con_status_no_ok(self):
        f = _fetch_banda_ok()
        r = mh.adquirir_capa(SPEC_BANDA, SUJETO, fetch_fn=f)
        for estado in (mh.STATUS_NO_MATCH, mh.STATUS_SOURCE_UNAVAILABLE,
                       mh.STATUS_QUERY_FAILED, mh.STATUS_NOT_SUPPORTED):
            with self.subTest(status=estado):
                self.assertIsNone(mh.referencia_nivel_3(dict(r, status=estado), SUJETO))


def _scratch(caso) -> Path:
    """Directorio de trabajo DENTRO del repo: el temporal del sistema no es borrable aquí.

    Se registra la limpieza con `addCleanup` en modo tolerante: la prueba no depende de
    poder borrar, sólo de poder escribir y releer bytes exactos.
    """
    destino = ROOT / "tests" / "_scratch_market_harvest"
    destino.mkdir(parents=True, exist_ok=True)
    for sobrante in destino.glob("*.json"):
        try:
            sobrante.unlink()
        except OSError:
            pass
    caso.addCleanup(lambda: [p.unlink(missing_ok=True) for p in destino.glob("*.json")])
    return destino


def _numeros(dato, prefijo=""):
    """Aplana los valores numéricos de una estructura, para poder auditarlos."""
    salida = {}
    if isinstance(dato, dict):
        for k, v in dato.items():
            salida.update(_numeros(v, f"{prefijo}.{k}"))
    elif isinstance(dato, (list, tuple)):
        for i, v in enumerate(dato):
            salida.update(_numeros(v, f"{prefijo}[{i}]"))
    elif isinstance(dato, (int, float)) and not isinstance(dato, bool):
        salida[prefijo] = float(dato)
    return salida


# ══════════════════════════════════════════════════════════════════════════════
# 6 · Banda de área: selección por CONTENCIÓN, nunca a dedo
# ══════════════════════════════════════════════════════════════════════════════
class TestBandaArea(unittest.TestCase):
    def test_parseo_con_y_sin_unidad(self):
        self.assertEqual(mh.parsear_banda_m2("36-60"), (36.0, 60.0))
        self.assertEqual(mh.parsear_banda_m2("36-60m²"), (36.0, 60.0))
        self.assertEqual(mh.parsear_banda_m2(" 61 - 175 m2 "), (61.0, 175.0))
        lo, hi = mh.parsear_banda_m2(">291m²")
        self.assertEqual(lo, 292.0)
        self.assertEqual(hi, float("inf"))

    def test_texto_sin_banda_no_se_adivina(self):
        for texto in (None, "", "sin banda", "36 a 60", "abc", "-"):
            with self.subTest(texto=texto):
                self.assertIsNone(mh.parsear_banda_m2(texto))

    def test_contencion_incluye_los_extremos(self):
        self.assertTrue(mh.banda_contiene("36-60", 36.0))
        self.assertTrue(mh.banda_contiene("36-60", 60.0))
        self.assertTrue(mh.banda_contiene("36-60", 58.75))
        self.assertFalse(mh.banda_contiene("36-60", 35.99))
        self.assertFalse(mh.banda_contiene("36-60", 60.01))

    def test_banda_sin_dato_de_area_no_contiene(self):
        for area in (None, "x", "", object()):
            with self.subTest(area=area):
                self.assertFalse(mh.banda_contiene("36-60", area))

    def test_selecciona_la_banda_del_sujeto_y_no_otra(self):
        elegida = mh.seleccionar_capa_banda(_meta_valoresm2()["layers"], 58.75)
        self.assertIsNotNone(elegida)
        self.assertEqual(elegida["layer"]["id"], 1)
        self.assertEqual(elegida["banda_area_m2"], "36-60m²")

    def test_area_fuera_de_toda_banda_no_elige_capa(self):
        """Las bandas del servicio cubren [36, ∞): 20 m² no cae en NINGUNA."""
        self.assertIsNone(mh.seleccionar_capa_banda(_meta_valoresm2()["layers"], 20.0))
        self.assertIsNone(mh.seleccionar_capa_banda(_meta_valoresm2()["layers"], None))

    def test_la_banda_abierta_si_contiene_areas_grandes(self):
        elegida = mh.seleccionar_capa_banda(_meta_valoresm2()["layers"], 5000.0)
        self.assertIsNotNone(elegida)
        self.assertEqual(elegida["layer"]["id"], 4)

    def test_sin_banda_que_contenga_el_area_el_estado_no_inventa_capa(self):
        sujeto = mh.Sujeto(folio="X", area_m2=20.0, lat=11.0, lon=-74.8)
        f = _fetch_banda_ok()
        r = mh.adquirir_capa(SPEC_BANDA, sujeto, fetch_fn=f)
        self.assertEqual(r["status"], mh.STATUS_NO_MATCH)
        self.assertIsNone(r["layer_id"])
        self.assertFalse(r["usable_for_estimation"])
        self.assertIn("no se elige capa a dedo", r["reason"])


# ══════════════════════════════════════════════════════════════════════════════
# 7 · LEVEL 3 y compatibilidad con `api/market_evidence.py`
# ══════════════════════════════════════════════════════════════════════════════
class TestNivel3(unittest.TestCase):
    def _ref(self, **kw):
        f = _fetch_banda_ok(**kw)
        r = mh.adquirir_capa(SPEC_BANDA, SUJETO, fetch_fn=f)
        return r, mh.referencia_nivel_3(r, SUJETO, market_evidence=me)

    def test_referencia_completa_es_nivel_3_del_contrato(self):
        _, ref = self._ref()
        self.assertIsNotNone(ref)
        self.assertEqual(ref["nivel"], me.LEVEL_3_AGGREGATED_MARKET_REFERENCES)
        self.assertEqual(ref["clasificacion_contrato"],
                         me.LEVEL_3_AGGREGATED_MARKET_REFERENCES)
        self.assertEqual(ref["origin"], me.ORIGEN_EXTERNO)
        self.assertTrue(me.origin_sostiene_estimacion(ref["origin"]))

    def test_la_escalera_la_sostiene_sin_implicar_closed(self):
        _, ref = self._ref()
        escalera = me.evaluar_escalera([ref["nivel"]])
        self.assertEqual(escalera["mejor_nivel"],
                         me.LEVEL_3_AGGREGATED_MARKET_REFERENCES)
        self.assertIn(me.LEVEL_3_AGGREGATED_MARKET_REFERENCES,
                      escalera["niveles_con_soporte"])
        self.assertTrue(escalera["sin_level_1"])
        self.assertFalse(escalera["implica_closed"],
                         "sin LEVEL 1 NO se cierra: regla dura del contrato")
        self.assertFalse(escalera["closed_por_ausencia_total_de_soporte"])

    def test_declara_metodologia_y_vigencia(self):
        _, ref = self._ref()
        self.assertTrue(ref["metodologia_declarada"])
        self.assertIn("vigencia_declarada", ref)
        self.assertTrue(ref["vigencia_declarada"]["basis"])

    def test_evidence_hash_determinista_y_sensible(self):
        _, a = self._ref(minimo=1000.0, maximo=3000.0)
        _, b = self._ref(minimo=1000.0, maximo=3000.0)
        _, c = self._ref(minimo=1000.0, maximo=3001.0)
        self.assertEqual(a["evidence_hash"], b["evidence_hash"])
        self.assertNotEqual(a["evidence_hash"], c["evidence_hash"])
        self.assertEqual(len(a["evidence_hash"]), 64)

    def test_identifica_la_banda_y_el_sector_del_sujeto(self):
        _, ref = self._ref()
        self.assertEqual(ref["banda_area_m2"], "36-60")
        self.assertEqual(ref["area_sujeto_m2"], 58.75)
        self.assertEqual(ref["sector_referencia"], "Norte - centro histórico")

    def test_tipos_que_no_sostienen_no_producen_nivel_3(self):
        for source_id in ("BAQ_OBS_VALORSUELOURBANO", "BAQ_OBS_ARRENDAMIENTOS",
                          "BAQ_OBS_AVALUOCATASTRAL", "BAQ_OBS_VALORCOMPRAVENTAS",
                          "BAQ_OBS_CANTIDADTRANSACCIONES"):
            with self.subTest(source_id=source_id):
                spec = mh.capas_por_source_id()[source_id]
                f = FetchFalso([
                    ("/MapServer?f=json", _raw("m", 200, {"layers": [{"id": spec.layer_id,
                                                                      "name": "x"}]})),
                    ("/query", _raw("q", 200, {"features": [{"attributes": {
                        "valorm2": 1, "cantidad": 1, "avaluo": 1,
                        "codigo_manzana": SUJETO.codigo_manzana}}]})),
                ])
                r = mh.adquirir_capa(spec, SUJETO, fetch_fn=f)
                self.assertFalse(r["usable_for_estimation"])
                self.assertEqual(r["status"], mh.STATUS_NOT_SUPPORTED)
                self.assertIsNone(mh.referencia_nivel_3(r, SUJETO))


# ══════════════════════════════════════════════════════════════════════════════
# 8 · El payload crudo se preserva byte a byte
# ══════════════════════════════════════════════════════════════════════════════
class TestPreservacionCruda(unittest.TestCase):
    def test_capa_json_es_byte_a_byte_y_reproduce_el_hash(self):
        tmp = _scratch(self)
        f = _fetch_banda_ok()
        r = mh.adquirir_capa(SPEC_BANDA, SUJETO, fetch_fn=f, out_dir=tmp)
        destino = tmp / "valoresm2_area.json"
        self.assertTrue(destino.is_file(), "debe preservarse raw/<capa>.json")
        crudo = destino.read_bytes()
        self.assertEqual(hashlib.sha256(crudo).hexdigest(), r["sha256"])
        self.assertEqual(len(crudo), r["bytes"])
        # El archivo es la respuesta EXACTA: sigue siendo JSON válido y trae el dato.
        self.assertEqual(json.loads(crudo.decode("utf-8"))["features"][0]["attributes"]
                         ["nombre"], "Norte - centro histórico")

    def test_el_crudo_de_un_403_tambien_se_preserva(self):
        tmp = _scratch(self)
        html = b"<html>Just a moment...</html>"
        f = FetchFalso([("/MapServer?f=json", _raw("m", 403, html))])
        r = mh.adquirir_capa(SPEC_BANDA, SUJETO, fetch_fn=f, out_dir=tmp)
        self.assertEqual(r["status"], mh.STATUS_SOURCE_UNAVAILABLE)
        self.assertEqual((tmp / "valoresm2_area.json").read_bytes(), html)


# ══════════════════════════════════════════════════════════════════════════════
# 9 · Guardas sobre el artefacto REAL del Golden (sólo lectura, por invariantes)
# ══════════════════════════════════════════════════════════════════════════════
class TestArtefactoGoldenReal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not GOLDEN_JSON.is_file():
            raise unittest.SkipTest("artefacto del harvest no generado todavía")
        cls.datos = json.loads(GOLDEN_JSON.read_text(encoding="utf-8"))

    def test_toda_capa_declara_los_campos_del_contrato(self):
        exigidos = {"source_id", "service_url", "layer_id", "layer_name", "http_status",
                    "consulted_at", "bytes", "sha256", "status", "value_or_range",
                    "effective_from", "effective_to", "sample_size",
                    "usable_for_estimation", "reason"}
        self.assertTrue(self.datos["capas"])
        for nombre, capa in self.datos["capas"].items():
            with self.subTest(capa=nombre):
                faltan = exigidos - set(capa)
                self.assertFalse(faltan, f"faltan campos del contrato: {sorted(faltan)}")
                self.assertIn(capa["status"], mh.ESTADOS_HARVEST)

    def test_usable_implica_procedencia_completa_y_origen_habilitante(self):
        for nombre, capa in self.datos["capas"].items():
            with self.subTest(capa=nombre):
                if not capa["usable_for_estimation"]:
                    continue
                self.assertEqual(capa["status"], mh.STATUS_OK)
                self.assertTrue(capa["origin_gate"])
                self.assertIn(capa["origin"], me.ORIGENES_HABILITANTES)
                self.assertEqual(
                    mh.provenance_faltante(capa["provenance"]), ())

    def test_los_sha256_declarados_reproducen_los_raw(self):
        """El hash declarado tiene que reproducirse desde el archivo crudo preservado."""
        comprobados = 0
        for nombre, capa in self.datos["capas"].items():
            crudo = RAW_DIR / f"{nombre}.json"
            with self.subTest(capa=nombre):
                self.assertTrue(crudo.is_file(), f"falta el crudo raw/{nombre}.json")
                bytes_crudos = crudo.read_bytes()
                if capa["http_status"] is None:
                    continue
                self.assertEqual(hashlib.sha256(bytes_crudos).hexdigest(),
                                 capa["sha256"])
                self.assertEqual(len(bytes_crudos), capa["bytes"])
                comprobados += 1
        self.assertGreater(comprobados, 0)

    def test_ninguna_capa_no_sostenida_se_marca_usable(self):
        for nombre, capa in self.datos["capas"].items():
            with self.subTest(capa=nombre):
                if capa["tipo_referencia"] in mh.TIPOS_QUE_SOSTIENEN_ESTIMACION:
                    continue
                self.assertFalse(capa["usable_for_estimation"],
                                 "un concepto que no es valor/m² de unidad no sostiene")

    def test_level_3_no_contiene_valor_promediado(self):
        for ref in self.datos.get("level_3_referencias") or []:
            with self.subTest(ref=ref.get("reference_id")):
                self.assertEqual(ref["nivel"], me.LEVEL_3_AGGREGATED_MARKET_REFERENCES)
                self.assertIsNone(ref["valor_m2"])
                rango = ref["rango_valor_m2"]
                self.assertIsNotNone(rango["min"])
                self.assertIsNotNone(rango["max"])
                promedio = (rango["min"] + rango["max"]) / 2.0
                for clave, valor in _numeros(ref).items():
                    self.assertNotEqual(valor, promedio,
                                        f"{clave} contiene el promedio del rango")

    def test_gap_report_existe_y_es_accionable(self):
        gap = self.datos.get("GAP_REPORT")
        self.assertIsInstance(gap, dict)
        self.assertIn("resumen", gap)
        self.assertIn("transicion_de_compuerta", gap)
        fuentes = gap.get("fuentes_que_hay_que_incorporar")
        self.assertIsInstance(fuentes, list)
        self.assertTrue(fuentes)
        for fuente in fuentes:
            with self.subTest(fuente=fuente.get("fuente_automatica")):
                self.assertTrue(fuente.get("campos_que_debe_declarar"))
                self.assertTrue(fuente.get("por_que"))
                self.assertIn("estado_actual", fuente)

    def test_el_artefacto_no_introduce_la_lonja(self):
        texto = json.dumps(self.datos, ensure_ascii=False).lower()
        self.assertNotIn("lonja", texto,
                         "la Lonja NO es fuente y no puede entrar por esta vía")


class TestSujetoDesdeManifest(unittest.TestCase):
    def test_lee_el_sujeto_real_sin_inventar_huecos(self):
        manifest = (ROOT / "docs" / "forensics" / "040-646406" / "dictus_2b"
                    / "DICTUS_MANIFEST_040-646406.json")
        if not manifest.is_file():
            self.skipTest("manifest del Golden no disponible")
        s = mh.sujeto_desde_manifest(manifest)
        self.assertEqual(s.folio, "040-646406")
        self.assertEqual(s.area_m2, 58.75)
        self.assertEqual(s.barrio, "Miramar")
        self.assertIsNotNone(s.punto_wgs84)

    def test_sin_coordenadas_el_punto_es_none_y_no_cero(self):
        s = mh.Sujeto(folio="X", area_m2=10.0, lat=0.0, lon=None)
        self.assertIsNone(s.punto_wgs84)
        self.assertFalse(s.puede_consultar_punto())


if __name__ == "__main__":
    unittest.main(verbosity=2)
