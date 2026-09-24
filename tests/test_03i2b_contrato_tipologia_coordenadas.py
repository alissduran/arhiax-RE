# -*- coding: utf-8 -*-
"""03I.2B — Endurecimiento final: contrato del gate (R1), render de la
clasificación (R2) y promoción de la geometría oficial del predio (H-1).

Los tres hallazgos residuales que cierra esta rebanada:

  R1  un contrato de liberación MALFORMADO (`None`, `{}`, un string, o un dict al
      que le faltan campos) podía leerse como «no bloqueante» = fail-open.
  R2  el render de clasificación INVENTABA el uso: toda bodega se imprimía como
      «Bodega -- Uso Industrial» aunque el destino económico fuera «Comercial».
  H-1 `resolve_market_location` promovía CUALQUIER `predio_real["lat"]` a la fuente
      autorizada `OFFICIAL_PREDIO`, sin exigir evidencia de que esa geometría fuera
      la del predio consultado.

Secciones: §C (C1–C6) contrato · §F (F1–F6) render · §M (M1–M9) coordenadas ·
§Q (Q1–Q5) liberación end-to-end sobre el PDF.
"""
import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "tests"))

TMP_DIR = ROOT / "tmp_pdf_03i2b"

# Identificadores oficiales del caso Golden (fixtures del caso real, no valores
# esperados: las pruebas NO dependen de que la valoración salga en un monto dado).
GOLDEN_GUID = "{GOLDEN-PREDIO-GUID}"
GOLDEN_CODIGO = "080010103000010040001908040002"
GOLDEN_NUPRE = "AFT0005BOHA"
GOLDEN_LAT, GOLDEN_LON = 10.9870, -74.8115


# ── utilidades ────────────────────────────────────────────────────────────────

def _sin_acentos(t: str) -> str:
    import unicodedata
    nfd = unicodedata.normalize("NFD", t or "")
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def _texto(pdf_path: Path) -> str:
    import pymupdf
    return " ".join(p.get_text() for p in pymupdf.open(str(pdf_path)))


def _afirmar_contiene(caso, texto: str, aguja: str):
    caso.assertIn(_sin_acentos(aguja).lower(), _sin_acentos(texto).lower(),
                  f"no se encontró {aguja!r} en el texto del dictamen")


def _afirmar_no_contiene(caso, texto: str, aguja: str):
    caso.assertNotIn(_sin_acentos(aguja).lower(), _sin_acentos(texto).lower(),
                     f"el texto del dictamen NO debía contener {aguja!r}")


def _procedencia_valida(**over) -> dict:
    """Procedencia H-1 completa de la dirección oficial ligada al predio."""
    p = {
        "source_system": "CATASTRO_MUNICIPAL_BARRANQUILLA_ARCGIS",
        "layer": "105 · direccion",
        "feature_id": GOLDEN_GUID,
        "feature_id_kind": "cr_predio_guid",
        "geometry_type": "Point",
        "resolution_method": "DIRECCION_OFICIAL_LIGADA_POR_GUID",
        "predio_globalid": GOLDEN_GUID,
        "numero_predial": GOLDEN_CODIGO,
        "nupre": GOLDEN_NUPRE,
        "link_verificado": True,
    }
    p.update(over)
    return p


def _predio_real(*, lat=GOLDEN_LAT, lon=GOLDEN_LON, origen="DIRECCION_OFICIAL_LIGADA_AL_PREDIO",
                 provenance=None, disponible=True, globalid=GOLDEN_GUID) -> dict:
    return {
        "disponible": disponible,
        "lat": lat, "lon": lon,
        "coordenada_origen": origen,
        "coordenada_provenance": (_procedencia_valida() if provenance is None
                                  else provenance),
        "direccion_oficial": "Transversal 43 100 50 TO 8 AP 430",
        "predio": {
            "globalid": globalid,
            "numero_predial_nacional": GOLDEN_CODIGO,
            "nupre": GOLDEN_NUPRE,
        },
    }


def _canonical_golden(**over) -> dict:
    """CanonicalPropertyIdentity del caso Golden (identificadores reales del caso)."""
    cid = {
        "folio_snr": "040-646406",
        "nupre": GOLDEN_NUPRE,
        "codigo_catastral": GOLDEN_CODIGO,
        "resolution_confidence": "VERIFIED_UNIT_IDENTITY",
        "identity_verified": True,
        "identificadores": {
            "nupre": {"value": GOLDEN_NUPRE, "source": "CTL (NUPRE)"},
            "codigo_catastral": {"value": GOLDEN_CODIGO,
                                 "source": "CTL (CODIGO CATASTRAL)"},
        },
    }
    cid.update(over)
    return cid


def _ubicacion(**kw):
    """resolve_market_location con valores por defecto NEUTROS (sin red)."""
    from market_context import resolve_market_location
    base = dict(
        canonical_identity={}, predio_real=None, lat_geo=None, lon_geo=None,
        db_lat=None, db_lon=None, db_direccion=None, barrio="Miramar",
        es_bogota=False, es_medellin=False, es_pasto=False,
        ciudad="barranquilla", geocoder=lambda d, ciudad=None: None)
    base.update(kw)
    return resolve_market_location(**base)


class _EntornoMixin:
    """Aísla ARHIAX_ENV, el override y las claves locales de QA durante cada prueba.

    Las claves entran en la lista porque la prueba de bloqueo en producción las
    necesita y NO deben filtrarse a otras pruebas del proceso.
    """

    VARS = ("ARHIAX_ENV", "ARHIAX_ALLOW_LEGACY_RELEASE", "ARHIAX_PERMITIR_LEGACY",
            "ARHIAX_AUTH_SECRET", "ARHIAX_ADMIN_PASSWORD")

    def setUp(self):
        self._backup = {k: os.environ.get(k) for k in self.VARS}
        for k in self.VARS:
            os.environ.pop(k, None)

    def tearDown(self):
        for k, v in self._backup.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


# ══════════════════════════════════════════════════════════════════════════════
# §C — El contrato de liberación malformado NO puede ser «no bloqueante» (R1)
# ══════════════════════════════════════════════════════════════════════════════

class TestCContratoLiberacion(_EntornoMixin, unittest.TestCase):

    def test_c1_none_no_es_decisión_válida(self):
        """C1: `None` se convierte en fallo explícito, con política del entorno."""
        from sanctions.release_gate import (EVAL_FAILED, STATUS_GATE_FAILED,
                                            MARCA_GATE_NO_EVALUABLE,
                                            validate_release_decision)
        os.environ["ARHIAX_ENV"] = "development"
        d = validate_release_decision(None)
        self.assertIs(d["contract_valid"], False)
        self.assertEqual(d["evaluation_status"], EVAL_FAILED)
        self.assertEqual(d["release_status"], STATUS_GATE_FAILED)
        self.assertEqual(d["marca"], MARCA_GATE_NO_EVALUABLE)
        # En desarrollo MARCA (no bloquea la generación) pero el PDF NO es válido.
        self.assertEqual(d["policy"], "MARK")
        self.assertIs(d["blocking"], False)
        self.assertIs(d["mark"], True)
        self.assertTrue(d["contract_problems"])
        self.assertTrue(d["reasons"])

    def test_c2_dict_vacio_o_incompleto(self):
        """C2: `{}` y un dict con campos ausentes se declaran INVÁLIDOS."""
        from sanctions.release_gate import validate_release_decision
        os.environ["ARHIAX_ENV"] = "development"
        d = validate_release_decision({})
        self.assertIs(d["contract_valid"], False)
        self.assertTrue(any("evaluation_status" in p for p in d["contract_problems"]))
        d2 = validate_release_decision({"release_status": "VALID_FOR_RELEASE"})
        self.assertIs(d2["contract_valid"], False)
        self.assertTrue(any("evaluation_status" in p for p in d2["contract_problems"]))
        self.assertTrue(any("policy" in p for p in d2["contract_problems"]))

    def test_c3_no_dict_y_produccion_bloquea(self):
        """C3: un contrato que ni siquiera es dict queda INVÁLIDO y, en producción
        (o con el entorno ausente, que es el caso conservador), BLOQUEA."""
        from sanctions.release_gate import validate_release_decision
        for valor in ("VALID_FOR_RELEASE", 1, ["VALID_FOR_RELEASE"], object()):
            d = validate_release_decision(valor)
            self.assertIs(d["contract_valid"], False, f"{valor!r} no puede ser válido")
            self.assertIs(d["blocking"], True, f"{valor!r} debe bloquear en producción")
            self.assertEqual(d["policy"], "BLOCK")
        os.environ["ARHIAX_ENV"] = "production"
        d = validate_release_decision("VALID_FOR_RELEASE")
        self.assertIs(d["contract_valid"], False)
        self.assertIs(d["blocking"], True)
        self.assertEqual(d["environment"], "production")

    def test_c4_valid_con_incoherencias_internas_es_invalido(self):
        """C4: una decisión que se declara VÁLIDA pero no cumple sus propias
        condiciones (evaluación fallida, bloqueo o marca) no se acepta jamás."""
        from sanctions.release_gate import validate_release_decision
        os.environ["ARHIAX_ENV"] = "development"
        incoherentes = [
            {"evaluation_status": "EVALUATION_FAILED", "release_status": "VALID_FOR_RELEASE",
             "policy": "MARK", "blocking": False, "mark": False, "environment": "development",
             "reasons": []},
            {"evaluation_status": "EVALUATED", "release_status": "VALID_FOR_RELEASE",
             "policy": "MARK", "blocking": True, "mark": False, "environment": "development",
             "reasons": []},
            {"evaluation_status": "EVALUATED", "release_status": "VALID_FOR_RELEASE",
             "policy": "MARK", "blocking": False, "mark": True, "environment": "development",
             "reasons": []},
            {"evaluation_status": "EVALUATED", "release_status": "VALID_FOR_RELEASE",
             "policy": "PERMISO", "blocking": False, "mark": False, "environment": "development",
             "reasons": []},
        ]
        for c in incoherentes:
            d = validate_release_decision(c)
            self.assertIs(d["contract_valid"], False, f"no puede pasar: {c}")
            self.assertIs(d["mark"], True)
            self.assertNotEqual(d["release_status"], "VALID_FOR_RELEASE")
            # Ninguna incoherencia puede degradar a «liberable» por la puerta de atrás.
            self.assertFalse(d["blocking"] and d["release_status"] == "VALID_FOR_RELEASE")

    def test_c5_contrato_valido_pasa_intacto(self):
        """C5: un contrato coherente se acepta SIN reescribir sus valores."""
        from sanctions.release_gate import (validate_release_decision, EVAL_OK,
                                           STATUS_VALID, POLICY_MARK)
        os.environ["ARHIAX_ENV"] = "development"
        valido = {"evaluation_status": EVAL_OK, "release_status": STATUS_VALID,
                  "policy": POLICY_MARK, "blocking": False, "mark": False,
                  "environment": "development", "reasons": [],
                  "core_versions": {"matcher": "sanctions-matcher/1.1.0"}}
        d = validate_release_decision(valido)
        self.assertIs(d["contract_valid"], True)
        self.assertEqual(d["contract_problems"], [])
        self.assertEqual(d["release_status"], STATUS_VALID)
        self.assertEqual(d["core_versions"], {"matcher": "sanctions-matcher/1.1.0"})

    def test_c6_override_no_convierte_un_fallo_en_válido(self):
        """C6: el override solo degrada BLOCK→MARK; nunca produce VALID_FOR_RELEASE
        ni hace desaparecer la marca de invalidez."""
        from sanctions.release_gate import validate_release_decision, STATUS_GATE_FAILED
        os.environ["ARHIAX_ENV"] = "production"
        os.environ["ARHIAX_ALLOW_LEGACY_RELEASE"] = "1"
        d = validate_release_decision(None)
        self.assertEqual(d["policy"], "MARK")
        self.assertIs(d["blocking"], False)
        self.assertIs(d["override_used"], True)
        self.assertEqual(d["release_status"], STATUS_GATE_FAILED)
        self.assertIs(d["mark"], True)
        self.assertIs(d["contract_valid"], False)
        # Y con el override activo tampoco se puede «validar» un contrato roto.
        self.assertNotEqual(d["release_status"], "VALID_FOR_RELEASE")

    def test_c7_el_compilador_valida_el_contrato(self):
        """C7: el compilador pasa SIEMPRE el resultado del wrapper por el validador
        (§B). Se comprueba con un wrapper que devuelve dicts malformados."""
        import pdf_compiler
        from sanctions import release_gate as rg
        os.environ["ARHIAX_ENV"] = "development"
        for malo in (None, {}, "VALID_FOR_RELEASE",
                     {"release_status": "VALID_FOR_RELEASE"}):
            with mock.patch.object(rg, "evaluar_release_seguro", lambda m=malo: m):
                d = pdf_compiler._gate_liberacion_inicial()
            self.assertIs(d.get("contract_valid"), False,
                          f"el compilador aceptó como válido: {malo!r}")
            self.assertIs(d.get("mark"), True)
            self.assertNotEqual(d.get("release_status"), "VALID_FOR_RELEASE")
        # El wrapper REAL sigue siendo válido (no se rompe el camino normal).
        d_ok = pdf_compiler._gate_liberacion_inicial()
        self.assertEqual(d_ok["contract_valid"], True)
        self.assertFalse(d_ok["release_status"] == "VALID_FOR_RELEASE"
                         and d_ok["mark"])


# ══════════════════════════════════════════════════════════════════════════════
# §F — El render de la clasificación no inventa el uso (R2)
# ══════════════════════════════════════════════════════════════════════════════

class TestFRenderClasificacion(unittest.TestCase):

    @staticmethod
    def _txt(**kw):
        from clasificacion import clasificar_inmueble, texto_tipologia
        return texto_tipologia(clasificar_inmueble(**kw))

    def test_f1_bodega_comercial_no_se_imprime_industrial(self):
        """F1: el defecto exacto — bodega con destino COMERCIAL."""
        t = self._txt(destino_economico="Comercial",
                      descripcion_registral="BODEGA 3 MANZANA 4")
        _afirmar_contiene(self, t, "Bodega")
        _afirmar_contiene(self, t, "Uso Comercial")
        _afirmar_no_contiene(self, t, "Industrial")

    def test_f2_bodega_sin_uso_declarado_no_inventa_uso(self):
        """F2: sin uso en la fuente no se escribe ningún uso."""
        t = self._txt(descripcion_registral="BODEGA 3 MANZANA 4")
        _afirmar_contiene(self, t, "Bodega")
        _afirmar_no_contiene(self, t, "Uso ")
        _afirmar_no_contiene(self, t, "Industrial")

    def test_f3_local_y_oficina_declaran_su_uso_real(self):
        """F3: el uso anexado es el de la fuente, no el «típico» de la tipología."""
        t_local = self._txt(destino_economico="Comercial",
                            descripcion_registral="LOCAL 5 CENTRO COMERCIAL")
        _afirmar_contiene(self, t_local, "Local")
        _afirmar_contiene(self, t_local, "Uso Comercial")
        t_of = self._txt(destino_economico="Oficina",
                         descripcion_registral="OFICINA 302 EDIFICIO")
        _afirmar_contiene(self, t_of, "Oficina")
        _afirmar_contiene(self, t_of, "Uso Oficina")

    def test_f4_ninguna_tipologia_inventa_uso(self):
        """F4: con la dimensión de uso vacía, NINGUNA tipología imprime un uso."""
        import clasificacion as cl
        for tip_txt in ("BODEGA 1", "LOCAL 2", "OFICINA 3", "GARAJE 4", "CASA 5",
                        "APARTAMENTO 6"):
            t = self._txt(descripcion_registral=tip_txt)
            _afirmar_no_contiene(self, t, "Uso ")
            _afirmar_no_contiene(self, t, "Industrial")
        # Y toda tipología con uso declarado lo imprime con la representación REAL.
        for destino in ("Comercial", "Habitacional", "Industrial", "Oficina",
                        "Parqueadero"):
            t = self._txt(destino_economico=destino, descripcion_registral="BODEGA 1")
            _afirmar_contiene(self, t, f"Uso {destino}")
        self.assertEqual(cl.uso_economico_de("Comercial"), cl.USO_COMERCIAL)

    def test_f5_conflicto_no_afirma_uso_ni_tipologia(self):
        """F5: un conflicto de régimen no habilita ningún texto afirmativo."""
        t = self._txt(condicion_juridica="Propiedad Horizontal",
                      descripcion_catastral="NO PROPIEDAD HORIZONTAL - BODEGA",
                      descripcion_registral="BODEGA 3", destino_economico="Comercial")
        _afirmar_contiene(self, t, "PENDIENTE DE VERIFICACION")
        _afirmar_no_contiene(self, t, "Uso ")
        _afirmar_no_contiene(self, t, "Bodega -- Uso")

    def test_f6_el_dictamen_impreso_no_inventa_el_uso(self):
        """F6: end-to-end — bodega con destino comercial en el PDF real."""
        pdf = _compilar("03i2b_f6.pdf", destino_capa500="Comercial",
                        destino_tematico="Comercial",
                        descripcion_ctl="BODEGA 3 MANZANA 4",
                        tipo_predio_snr="BODEGA")
        txt = _texto(pdf)
        _afirmar_contiene(self, txt, "Bodega")
        _afirmar_no_contiene(self, txt, "Bodega -- Uso Industrial")
        _afirmar_no_contiene(self, txt, "Bodega -- Uso Industrial (No Propiedad Horizontal)")


# ══════════════════════════════════════════════════════════════════════════════
# §M — H-1: la geometría oficial del predio se promueve SOLO con evidencia
# ══════════════════════════════════════════════════════════════════════════════

class TestMElegibilidadGeometriaOficial(unittest.TestCase):

    @staticmethod
    def _eval(predio_real, *, canonical=None, es_bogota=False, es_medellin=False,
              es_pasto=False, ciudad="barranquilla"):
        """Evalúa la geometría. Por defecto el canónico del caso Golden (H-1 exige
        ahora, además, binding con la identidad canónica: 03I.2B-A)."""
        from market_context import evaluar_geometria_oficial_predio
        return evaluar_geometria_oficial_predio(
            predio_real=predio_real,
            canonical_identity=_canonical_golden() if canonical is None else canonical,
            ciudad=ciudad, es_bogota=es_bogota, es_medellin=es_medellin,
            es_pasto=es_pasto)

    def test_m1_geometria_oficial_valida_es_elegible(self):
        """M1: los 7 criterios cumplidos ⇒ elegible, con procedencia declarada."""
        v = self._eval(_predio_real())
        self.assertTrue(v["eligible"], v.get("reason"))
        self.assertEqual(v["provenance"]["feature_id"], GOLDEN_GUID)
        self.assertEqual(v["provenance"]["layer"], "105 · direccion")
        self.assertEqual(v["provenance"]["geometry_type"], "Point")

    def test_m2_lat_lon_sin_origen_declarado_no_se_promueve(self):
        """M2: el defecto histórico — lat/lon del predio SIN origen declarado."""
        pr = _predio_real()
        pr.pop("coordenada_origen")
        pr.pop("coordenada_provenance")
        v = self._eval(pr)
        self.assertFalse(v["eligible"])
        self.assertIn("origen", v["reason"])
        # Y el consumidor NO lo etiqueta como oficial.
        loc = _ubicacion(predio_real=pr)
        self.assertNotEqual(loc["coordinate_source"], "OFFICIAL_PREDIO")
        self.assertIs(loc["coordinate_source_verified"], False)
        self.assertIn("origen", loc["official_predio_rejected_reason"])

    def test_m3_hint_no_es_geometria_oficial(self):
        """M3: un hint (coordenada aportada desde fuera) nunca es oficial."""
        for origen in ("HINT_NO_OFICIAL", "GEOCODE_DIRECCION", "", None):
            v = self._eval(_predio_real(origen=origen))
            self.assertFalse(v["eligible"], f"origen {origen!r} no puede ser elegible")

    def test_m4_enlace_no_verificado_no_se_promueve(self):
        """M4: si la geometría no está ligada a ESTE predio, no se promueve."""
        v = self._eval(_predio_real(provenance=_procedencia_valida(
            feature_id="{OTRO-PREDIO}", predio_globalid="{OTRO-PREDIO}")))
        self.assertFalse(v["eligible"])
        self.assertIn("enlace", v["reason"])
        v2 = self._eval(_predio_real(provenance=_procedencia_valida(
            link_verificado=False)))
        self.assertFalse(v2["eligible"])

    def test_m5_procedencia_incompleta_no_se_promueve(self):
        """M5: sin capa, sin método o sin feature no hay promoción."""
        for campo in ("source_system", "layer", "feature_id", "geometry_type",
                      "resolution_method", "predio_globalid"):
            prov = _procedencia_valida()
            prov.pop(campo)
            v = self._eval(_predio_real(provenance=prov))
            self.assertFalse(v["eligible"], f"faltando {campo} no puede ser elegible")
            self.assertIn("procedencia incompleta", v["reason"])
        pr_sin = _predio_real()
        pr_sin.pop("coordenada_provenance")
        v = self._eval(pr_sin)
        self.assertFalse(v["eligible"])
        self.assertIn("procedencia", v["reason"])

    def test_m6_metodo_y_tipo_de_geometria_admisibles(self):
        """M6: geocodificación, interpolación o centroide de referencia no pasan."""
        for metodo in ("GEOCODE_DIRECCION_DEL_FORMULARIO", "HINT_NO_OFICIAL",
                       "CENTROIDE_DE_BARRIO", "CITY_CENTROID", "PUNTO_DE_PLACA",
                       "ESTIMADO", "INTERPOLADO"):
            v = self._eval(_predio_real(provenance=_procedencia_valida(
                resolution_method=metodo)))
            self.assertFalse(v["eligible"], f"método {metodo!r} no puede ser elegible")
        for geom in ("LineString", None, "", "PointZ"):
            v = self._eval(_predio_real(provenance=_procedencia_valida(
                geometry_type=geom)))
            self.assertFalse(v["eligible"], f"geometría {geom!r} no puede ser elegible")

    def test_m7_cordura_espacial(self):
        """M7: una coordenada proyectada o fuera del municipio no es del predio."""
        v = self._eval(_predio_real(lat=1_500_000.0, lon=2_000_000.0))
        self.assertFalse(v["eligible"])
        self.assertIn("caja del municipio", v["reason"])
        v2 = self._eval(_predio_real(lat=0.0, lon=0.0))
        self.assertFalse(v2["eligible"])
        v3 = self._eval(_predio_real(lat=4.7110, lon=-74.0721))  # Bogotá en Barranquilla
        self.assertFalse(v3["eligible"])
        v4 = self._eval(_predio_real(lat=GOLDEN_LAT, lon=GOLDEN_LON))
        self.assertTrue(v4["eligible"], v4.get("reason"))

    def test_m10_medellin_declara_origen_y_solo_promueve_lo_oficial(self):
        """M10: en Medellín el productor declara el origen (H-1) y el consumidor
        promueve SOLO el punto oficial del registro, nunca el hint."""
        from catastro_predio_medellin import (enriquecer_desde_ctl,
                                              ORIGEN_GEOMETRIA_OFICIAL, ORIGEN_HINT)
        base_oficial = {
            "disponible": True, "error": None,
            "numero_predial_nacional": "050010103000000010012300001",
            "nupre": "AFT0001MDEL", "direccion_cruda": "CARRERA 70 1 100",
            "lat": 6.2442, "lon": -75.5812, "globalid": None,
            "estrato": "4", "destino_economico": "Habitacional",
        }
        with mock.patch("catastro_predio_medellin.consultar_predio_por_codigo",
                        return_value=base_oficial), \
                mock.patch("catastro_predio_medellin.consultar_entorno_urbano",
                           return_value={"disponible": False}), \
                mock.patch("catastro_predio_medellin.consultar_lote_y_construccion",
                           return_value={}), \
                mock.patch("catastro_predio_medellin.consultar_amenazas",
                           return_value={}):
            r = enriquecer_desde_ctl(codigo_catastral=base_oficial["numero_predial_nacional"])
        self.assertEqual(r["coordenada_origen"], ORIGEN_GEOMETRIA_OFICIAL)
        # 03I.2B-A: el canónico de ESTE caso declara los identificadores de Medellín.
        can_med = {"nupre": "AFT0001MDEL",
                   "codigo_catastral": "050010103000000010012300001"}
        v = self._eval(r, canonical=can_med, es_medellin=True, ciudad="medellin")
        self.assertTrue(v["eligible"], v.get("reason"))
        self.assertEqual(v["canonical_binding"]["status"], "VERIFIED")
        # Con la identidad canónica de OTRO predio, la misma geometría no promueve.
        v_otro = self._eval(r, canonical=_canonical_golden(), es_medellin=True,
                            ciudad="medellin")
        self.assertFalse(v_otro["eligible"])
        self.assertIn("CANONICAL_IDENTITY_MISMATCH", v_otro["reason"])
        # Sin punto oficial, el hint se declara y NO se promueve.
        base_sin = dict(base_oficial, lat=None, lon=None)
        with mock.patch("catastro_predio_medellin.consultar_predio_por_codigo",
                        return_value=base_sin), \
                mock.patch("catastro_predio_medellin.consultar_entorno_urbano",
                           return_value={"disponible": False}), \
                mock.patch("catastro_predio_medellin.consultar_lote_y_construccion",
                           return_value={}), \
                mock.patch("catastro_predio_medellin.consultar_amenazas",
                           return_value={}):
            r2 = enriquecer_desde_ctl(codigo_catastral=base_oficial["numero_predial_nacional"],
                                      lat_hint=6.2442, lon_hint=-75.5812)
        self.assertEqual(r2["coordenada_origen"], ORIGEN_HINT)
        self.assertFalse(self._eval(r2, es_medellin=True, ciudad="medellin")["eligible"])

    def test_m11_bogota_lote_oficial_sin_clave_canonica_no_promueve(self):
        """M11: en Bogotá el centroide del lote por LOTCODIGO es geometría oficial,
        pero la fuente abierta NO publica el número predial nacional: el binding con
        la identidad canónica queda `NOT_COMPARABLE` (que no es VERIFIED) y la
        geometría NO se promueve. El punto de placa es un hint y tampoco promueve.

        Cuando el canónico SÍ declare la clave municipal (p. ej. matrícula
        municipal), el binding se apoya en ella y lo declara con alcance
        `MUNICIPAL_KEY` (03I.2B-A §5).
        """
        import catastro_predio_bogota as cb
        with mock.patch.object(cb, "_centroide_lote_por_codigo",
                               return_value=(4.6000, -74.1000)), \
                mock.patch.object(cb, "consultar_entorno_urbano",
                                  return_value={"disponible": False}), \
                mock.patch.object(cb, "consultar_construccion", return_value={}), \
                mock.patch.object(cb, "consultar_amenazas", return_value={}):
            r = cb.enriquecer_por_punto(lat=4.5990, lon=-74.1010,
                                        codigo_lote="LOTE-12345")
        self.assertEqual(r["coordenada_origen"], cb.ORIGEN_GEOMETRIA_OFICIAL)
        # (a) canónico con número predial nacional (CTL) pero sin clave municipal:
        #     la geometría del lote no puede ligarse → NO_COMPARABLE → no promueve.
        v = self._eval(r, canonical={"codigo_catastral": "110010103000000010012300001"},
                       es_bogota=True, ciudad="bogota")
        self.assertFalse(v["eligible"])
        self.assertEqual(v["canonical_binding"]["status"], "NOT_COMPARABLE")
        self.assertEqual(v["canonical_binding"]["scope"], "MUNICIPAL_KEY")
        self.assertIn("CANONICAL_IDENTITY_NOT_COMPARABLE", v["reason"])
        # (b) canónico que SÍ declara la clave municipal: binding VERIFIED con
        #     alcance municipal declarado (no se finge un predial de 30 dígitos).
        v_mun = self._eval(r, canonical={"matricula_municipal": "LOTE-12345"},
                           es_bogota=True, ciudad="bogota")
        self.assertTrue(v_mun["eligible"], v_mun.get("reason"))
        self.assertEqual(v_mun["canonical_binding"]["status"], "VERIFIED")
        self.assertEqual(v_mun["canonical_binding"]["scope"], "MUNICIPAL_KEY")
        self.assertEqual(v_mun["provenance"]["feature_id_kind"], "LOTCODIGO")
        # (c) el punto de placa (sin lote oficial) es un hint.
        with mock.patch.object(cb, "_centroide_lote_por_codigo", return_value=None), \
                mock.patch.object(cb, "consultar_entorno_urbano",
                                  return_value={"disponible": False}), \
                mock.patch.object(cb, "consultar_construccion", return_value={}), \
                mock.patch.object(cb, "consultar_amenazas", return_value={}):
            r2 = cb.enriquecer_por_punto(lat=4.5990, lon=-74.1010,
                                         codigo_lote="LOTE-12345")
        self.assertEqual(r2["coordenada_origen"], cb.ORIGEN_HINT)
        self.assertFalse(self._eval(r2, canonical={"matricula_municipal": "LOTE-12345"},
                                    es_bogota=True, ciudad="bogota")["eligible"])

    def test_m8_golden_usa_la_geometria_oficial_y_la_declara(self):
        """M8: en el caso Golden la fuente es la geometría oficial del predio, con
        alcance explícito (no acredita la posición del apartamento) y sin depender
        del geocoder."""
        pr = _predio_real()
        loc = _ubicacion(predio_real=pr, canonical_identity=_canonical_golden(),
                         lat_geo=10.1111, lon_geo=-74.2222,
                         geocoder=lambda d, ciudad=None: self.fail(
                             "el geocoder NO debe usarse si hay geometría oficial"))
        self.assertEqual(loc["coordinate_source"], "OFFICIAL_PREDIO")
        self.assertIs(loc["coordinate_source_verified"], True)
        self.assertEqual(loc["source_feature_id"], GOLDEN_GUID)
        self.assertEqual(loc["source_layer"], "105 · direccion")
        self.assertEqual(loc["source_system"],
                         "CATASTRO_MUNICIPAL_BARRANQUILLA_ARCGIS")
        self.assertEqual(loc["matched_nupre"], GOLDEN_NUPRE)
        self.assertEqual(loc["matched_predial"], GOLDEN_CODIGO)
        self.assertIn("NO acredita", loc["coordinate_scope"])
        self.assertIsNone(loc["official_predio_rejected_reason"])
        # 03I.2B-A: la promoción exige y declara el binding con la identidad canónica.
        self.assertEqual(loc["canonical_binding_status"], "VERIFIED")
        self.assertIn("nupre", loc["canonical_binding_fields"])

    def test_m9_determinismo_y_fail_closed_sin_fuentes(self):
        """M9: con geometría oficial el resultado no depende de la red; sin ninguna
        fuente autorizada la ubicación queda NO verificada (nunca «oficial»)."""
        # (a) determinista: mismo resultado con o sin geocoder disponible.
        pr = _predio_real()
        a = _ubicacion(predio_real=pr, geocoder=lambda d, ciudad=None: None)
        b = _ubicacion(predio_real=pr, geocoder=lambda d, ciudad=None: (1.0, 2.0))
        self.assertEqual((a["coordinate_source"], a["lat"], a["lon"]),
                         (b["coordinate_source"], b["lat"], b["lon"]))
        # (b) sin fuentes: centroide NO autorizado, motivo declarado y sin promoción.
        pr_malo = _predio_real()
        pr_malo.pop("coordenada_origen")
        c = _ubicacion(predio_real=pr_malo, barrio="Centro")
        self.assertEqual(c["coordinate_source"], "CITY_CENTROID")
        self.assertFalse(c["coordinate_source_verified"])
        self.assertIsNotNone(c["official_predio_rejected_reason"])
        # (c) la procedencia viaja SIEMPRE (no puede quedar en None silencioso).
        self.assertTrue(c["coordinate_provenance"].get("resolution_method"))


# ══════════════════════════════════════════════════════════════════════════════
# §Q — Liberación end-to-end sobre el PDF real
# ══════════════════════════════════════════════════════════════════════════════

class TestQLiberacionEndToEnd(_EntornoMixin, unittest.TestCase):

    def test_q1_contrato_malformado_bloquea_en_produccion(self):
        """Q1: en producción, un contrato malformado ⇒ excepción y NINGÚN PDF."""
        from consistency import InconsistenciaBloqueante
        from sanctions import release_gate as rg
        os.environ["ARHIAX_ENV"] = "production"
        os.environ["ARHIAX_AUTH_SECRET"] = "qa-local"
        os.environ["ARHIAX_ADMIN_PASSWORD"] = "qa-local"
        out = TMP_DIR / "03i2b_q1.pdf"
        with mock.patch.object(rg, "evaluar_release_seguro", lambda: {}):
            with self.assertRaises(InconsistenciaBloqueante):
                _compilar("03i2b_q1.pdf")
        self.assertFalse(out.exists(), "no puede quedar PDF con contrato inválido")

    def test_q2_contrato_malformado_en_dev_marca_pero_no_libera(self):
        """Q2: en desarrollo el PDF sale MARCADO y declara el contrato inválido."""
        from sanctions import release_gate as rg
        os.environ["ARHIAX_ENV"] = "development"
        with mock.patch.object(rg, "evaluar_release_seguro", lambda: None):
            pdf = _compilar("03i2b_q2.pdf")
        txt = _texto(pdf)
        _afirmar_contiene(self, txt, "RELEASE GATE NOT EVALUABLE / INVALID_FOR_RELEASE")
        _afirmar_contiene(self, txt, "CONTRATO DE LIBERACION INVALIDO")
        _afirmar_contiene(self, txt, "release_gate_contract_valid")
        _afirmar_contiene(self, txt, "release_gate_status")
        # El estado impreso es el fallo del gate, nunca la liberación vigente.
        _afirmar_contiene(self, txt, "GATE_EVALUATION_FAILED")

    def test_q3_gate_real_deja_el_contrato_declarado(self):
        """Q3: con el gate real el dictamen se libera y el recibo declara el
        contrato válido (sin filas inventadas)."""
        os.environ["ARHIAX_ENV"] = "development"
        pdf = _compilar("03i2b_q3.pdf")
        txt = _texto(pdf)
        _afirmar_contiene(self, txt, "release_gate_contract_valid")
        _afirmar_contiene(self, txt, "release_gate_status")
        _afirmar_contiene(self, txt, "release_gate_evaluation_status")
        _afirmar_no_contiene(self, txt, "CONTRATO DE LIBERACION INVALIDO")

    def test_q4_el_dictamen_declara_la_procedencia_de_la_coordenada(self):
        """Q4: §N — la procedencia de la coordenada es auditable en el dictamen."""
        os.environ["ARHIAX_ENV"] = "development"
        pdf = _compilar("03i2b_q4.pdf")
        txt = _texto(pdf)
        # La fuente autorizada del caso Golden es la geometría oficial del predio.
        _afirmar_contiene(self, txt, "OFFICIAL_PREDIO")
        _afirmar_no_contiene(self, txt, "COORDINATE_SOURCE_NOT_AUTHORIZED")

    def test_q5_el_screening_no_se_toca(self):
        """Q5: regresión — el núcleo SAGRILAFT declarado sigue siendo el sancionado
        (03I.2B no modifica matcher, modelo de sujetos, parsers ni fuentes)."""
        from sanctions.release_gate import nucleo_vigente, SAGRILAFT_CORE_MIN
        nu = nucleo_vigente()
        self.assertEqual(nu.matcher, SAGRILAFT_CORE_MIN["matcher"])
        self.assertEqual(nu.subject_model, SAGRILAFT_CORE_MIN["subject_model"])
        for parser, ver in SAGRILAFT_CORE_MIN["parsers"].items():
            # El valor real viaja como «<parser>/<versión>»: se exige la versión
            # sancionada, no una cadena idéntica.
            self.assertIn(str(ver), str(nu.parsers.get(parser) or ""),
                          f"parser {parser} fuera del núcleo sancionado")
        # Las fuentes del núcleo, como CONJUNTO (el orden no es semántico).
        self.assertEqual(sorted(str(s) for s in (nu.sources or ())),
                         sorted(str(s) for s in SAGRILAFT_CORE_MIN["sources"]))


# ── compilación del Golden con fuentes mockeadas (sin red) ────────────────────

def _compilar(tmp_name="03i2b.pdf", *, destino_capa500="Habitacional",
              destino_tematico="Habitacional",
              descripcion_ctl=("APARTAMENTO 430 TORRE 8 CONJUNTO NAPOLI MIRAMAR "
                               "PROPIEDAD HORIZONTAL"),
              tipo_predio_snr="APARTAMENTO"):
    """Compila el caso Golden 040-646406 con el router de capas mockeado.

    Devuelve la ruta del PDF. NO borra el archivo: las pruebas de fail-closed
    necesitan comprobar si el PDF final existe o no.
    """
    import catastro_predio
    import geocoder
    import legal_analyzer
    import pdf_compiler
    import integrations.catastro_live as catastro_live
    from test_remediacion_03h2a import (FuentesMock, GOLDEN_CODIGO, GOLDEN_DIRECCION,
                                        GOLDEN_LAT, GOLDEN_LON, GOLDEN_NUPRE)

    fuentes = FuentesMock(destino_capa500=destino_capa500,
                          destino_tematico=destino_tematico)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    out_pdf = TMP_DIR / tmp_name
    if out_pdf.exists():
        out_pdf.unlink()

    analysis = dict(legal_analyzer.analizar_certificado(None))
    analysis.update({
        "folio": "040-646406", "direccion": GOLDEN_DIRECCION,
        "codigo_catastral": GOLDEN_CODIGO, "nupre": GOLDEN_NUPRE,
        "descripcion_ctl": descripcion_ctl,
        "texto_ctl": descripcion_ctl,
        "tipo_predio_snr": tipo_predio_snr,
    })
    record = {
        "id": 1, "folio_matricula": "040-646406", "direccion": GOLDEN_DIRECCION,
        "barrio": "Miramar", "estrato": 4, "area": 58.75,
        "valor_consolidado": None, "sombra_9am_cargada": 0,
        "sombra_3pm_cargada": 0, "mapa_cargado": 0, "acreedor_real": None,
        "certificado_path": None, "ciudad": "barranquilla",
    }
    catastro_predio._CACHE.clear()
    with mock.patch.object(legal_analyzer, "analizar_certificado", return_value=analysis), \
            mock.patch.object(catastro_predio, "_query_capa",
                              side_effect=fuentes.query_capa), \
            mock.patch.object(catastro_predio, "_query_punto",
                              side_effect=fuentes.query_punto), \
            mock.patch.object(geocoder, "geocodificar_direccion",
                              lambda d, ciudad=None: (GOLDEN_LAT, GOLDEN_LON)), \
            mock.patch.object(pdf_compiler, "generate_maps", lambda *a, **k: None), \
            mock.patch.object(catastro_live, "verificar_catastro_barranquilla",
                              lambda *a, **k: {"disponible": False, "numero_predial": None,
                                               "error": "servicio sin respuesta",
                                               "fuente": {}}), \
            mock.patch.object(pdf_compiler, "get_poi_result",
                              lambda *a, **k: {
                                  "items": {c: [] for c in ("Salud", "Educacion",
                                                            "Comercio", "Recreacion")},
                                  "category_status": {c: "NO_MATCH" for c in (
                                      "Salud", "Educacion", "Comercio", "Recreacion")},
                                  "sources_attempted": 1, "sources_succeeded": 1}):
        pdf_compiler.compile_pdf(record, str(out_pdf), assets_dir=TMP_DIR)
    return out_pdf


if __name__ == "__main__":
    unittest.main(verbosity=2)
