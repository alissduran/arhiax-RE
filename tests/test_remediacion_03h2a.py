# -*- coding: utf-8 -*-
"""
Remediation 03H.2A — CADASTRAL / URBAN CONTEXT CLOSURE PATCH.

Cierra las fugas de la revisión de 03H.2:

  A. ambigüedad silenciosa de altura/tipo_tratamiento (nunca features[0])
  B. la pérdida de SOURCE_UNAVAILABLE de la capa de construcción
  C. autoridad urbana determinista (sin `setdefault` silencioso)
  D. provenance POR CAMPO de destino/condición
  E. el NUPRE (AFT...) NUNCA se consulta como número predial
  F. destino/condición temáticos aunque la capa 500 resuelva el predio
  G. origen real del destino económico en 6.1

Todo offline: las capas oficiales se sustituyen por un router de fixtures. La
validación contra las capas VIVAS sigue en `test_remediacion_03g.py` (marcada
network) — aquí se prueba la LÓGICA, no la disponibilidad de los servicios.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "api"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(API))

from market_context import (
    resolve_official_urban_context, COORD_OFFICIAL_ADDRESS_GEOCODE,
    STATUS_VERIFIED_OFFICIAL, STATUS_CONFLICT,
)

GOLDEN_CODIGO = "080010103000010040001908040002"
GOLDEN_NUPRE = "AFT0005BOHA"
GOLDEN_DIRECCION = "Transversal 43 100 50 TO 8 AP 430"
GOLDEN_LAT, GOLDEN_LON = 10.9870, -74.8115

# Entorno urbano oficial del Golden (fixture: sustituye la capa POT viva).
_URBANO_GOLDEN = {
    "disponible": True,
    "barrio": "Miramar",
    "localidad": "Norte Centro Histórico",
    "estrato": "4",
    "tratamiento": "Consolidación",
    "tipo_tratamiento": "Nivel 2",
    "altura_maxima": "11",
    "pieza_urbana": "Pieza Norte",
    "codigo_manzana": "08001010300001",
    "context_status": "OK",
    "campos_ambiguos": [],
}


def _feat(props, geometry=None):
    return {"properties": props, "geometry": geometry}


def _ok(features):
    return {"disponible": True, "features": features, "total": len(features),
            "error": None}


def _down():
    return {"disponible": False, "features": [], "error": "servicio sin respuesta"}


# ── Router de capas oficiales (fixture del caso Golden) ──────────────────────

class FuentesMock:
    """Router de capas oficiales SIN red (Barranquilla Golden 040-646406)."""

    def __init__(self, *, destino_capa500="Habitacional",
                 destino_tematico="Habitacional",
                 condicion_tematica="Propiedad Horizontal",
                 construccion="SOURCE_UNAVAILABLE",
                 entorno=None,
                 condicion_solo_exacta=False,
                 capa_500_resuelve=True,
                 todo_caido=False):
        self.destino_capa500 = destino_capa500
        self.destino_tematico = destino_tematico
        self.condicion_tematica = condicion_tematica
        self.construccion = construccion
        self.entorno = dict(entorno or _URBANO_GOLDEN)
        self.condicion_solo_exacta = condicion_solo_exacta
        # 03H.2A: en la ejecución REAL del Golden (sandbox sin acceso a ArcGIS)
        # la capa 500 no responde y la identidad sale del registro oficial de
        # adopción. `capa_500_resuelve=False` reproduce ese escenario.
        self.capa_500_resuelve = capa_500_resuelve
        # `todo_caido`: ninguna capa oficial responde (antecedente verificado de
        # la ejecución sin red). El dictamen DEBE degradar a PENDIENTE con causa.
        self.todo_caido = todo_caido
        self.wheres_terreno = []
        self.llamadas = []

    # -- catastro_predio._query_capa(base, capa, where, out_fields, ...) -------
    def query_capa(self, base, capa, where, *args, **kwargs):
        self.llamadas.append(("capa", base, capa, where))
        if self.todo_caido:
            return _down()
        if "datosabiertos" in base and capa == 500:
            if not self.capa_500_resuelve:
                return _down()
            if "numero_predial_nacional" in where or "codigo_homologado" in where:
                if "LIKE" in where:
                    return _ok([])
                return _ok([_feat({
                    "numero_predial_nacional": GOLDEN_CODIGO,
                    "codigo_homologado": GOLDEN_NUPRE,
                    "destinacion_economica": self.destino_capa500,
                    "tipo_predio": "PH",
                    "tipo_vivienda": "APARTAMENTO",
                    "estrato": None,
                    "estado_fmi": "ACTIVO",
                    "area_catastral_terreno": 22.05,
                    "globalid": "{GOLDEN-PREDIO-GUID}",
                })])
            return _ok([])
        if "datosabiertos" in base and capa == 105:
            return _ok([_feat({
                "clase_via_principal": "TRANSVERSAL", "valor_via_principal": "43",
                "letra_via_principal": "", "valor_via_generadora": "100",
                "letra_via_generadora": "", "numero_predio": "50",
                "complemento": "", "es_direccion_principal": 1,
                "cr_predio_guid": "{GOLDEN-PREDIO-GUID}",
            }, {"type": "Point", "coordinates": [GOLDEN_LON, GOLDEN_LAT]})])
        if "condicion" in base:
            self.wheres_terreno.append(where)
            return _ok([_feat({"terreno": GOLDEN_CODIGO,
                               "condicion": self.condicion_tematica, "anio": 2025})])
        if "destinoseconomicos" in base:
            self.wheres_terreno.append(where)
            return _ok([_feat({"terreno": GOLDEN_CODIGO,
                               "destino": self.destino_tematico, "anio": 2026})])
        return _down()

    # -- catastro_predio._query_punto(base, capa, lon, lat, out_fields) --------
    def query_punto(self, base, capa, lon, lat, *args, **kwargs):
        self.llamadas.append(("punto", base, capa))
        if self.todo_caido:
            return _down()
        if "datosabiertos" in base and capa == 310:
            if self.construccion == "SOURCE_UNAVAILABLE":
                return _down()
            if self.construccion == "NO_MATCH":
                return _ok([])
            return _ok([_feat({"tipo_construccion": "PH", "total_pisos": 11,
                               "altura_total_construccion": 33})])
        if "unidadesadministrativas" in base:
            if not self.entorno.get("barrio"):
                return _ok([])
            return _ok([_feat({"nombre_barrio": self.entorno["barrio"],
                               "identificador": "0800101030",
                               "localidad": self.entorno.get("localidad"),
                               "nombre_pieza": self.entorno.get("pieza_urbana")})])
        if "estratificacion" in base:
            if self.entorno.get("estrato") is None:
                return _ok([])
            return _ok([_feat({"estratificacion": self.entorno["estrato"],
                               "nombre_barrio": self.entorno["barrio"],
                               "codigo_manzana": self.entorno.get("codigo_manzana")})])
        if "planeacion" in base:
            if not self.entorno.get("tratamiento"):
                return _ok([])
            return _ok([_feat({"tratamiento": self.entorno["tratamiento"],
                               "tipo_tratamiento": self.entorno.get("tipo_tratamiento"),
                               "altura_maxima": self.entorno.get("altura_maxima")})])
        if "condicion" in base:
            if self.condicion_solo_exacta:
                return _ok([])
            return _ok([_feat({"condicion": "Propiedad Horizontal", "anio": 2025})])
        if "destinoseconomicos" in base:
            return _ok([_feat({"destino": self.destino_tematico, "anio": 2026})])
        return _down()


class _Base(unittest.TestCase):
    def setUp(self):
        import catastro_predio
        catastro_predio._CACHE.clear()


# ── A. Ambigüedad POR CAMPO (nunca features[0]) ──────────────────────────────

class TestAmbiguedadPorCampo(_Base):
    """#1/#2 (H): consolidación independiente de tratamiento/tipo/altura."""

    def _entorno(self, feats_planeacion):
        import catastro_predio
        fuentes = FuentesMock()

        def _punto(base, capa, lon, lat, *a, **kw):
            if "planeacion" in base:
                return _ok(feats_planeacion)
            return fuentes.query_punto(base, capa, lon, lat, *a, **kw)

        with mock.patch.object(catastro_predio, "_query_punto", _punto):
            return catastro_predio.consultar_entorno_urbano(GOLDEN_LAT, GOLDEN_LON)

    def test_alturas_11_y_15_no_se_elige_ninguna(self):
        """#1 (H): tratamiento igual + alturas 11/15 -> altura ambigua, NUNCA 11."""
        r = self._entorno([
            _feat({"tratamiento": "Consolidación", "tipo_tratamiento": "Nivel 2",
                   "altura_maxima": "11"}),
            _feat({"tratamiento": "Consolidación", "tipo_tratamiento": "Nivel 2",
                   "altura_maxima": "15"}),
        ])
        self.assertEqual(r["tratamiento"], "Consolidación")
        self.assertEqual(r["tipo_tratamiento"], "Nivel 2")
        self.assertIsNone(r["altura_maxima"])
        self.assertIn("altura_maxima", r["campos_ambiguos"])
        self.assertEqual(r["context_status"], "AMBIGUOUS_CONTEXT")
        # Y el consumidor NO la afirma como oficial.
        urb = resolve_official_urban_context(
            ciudad="barranquilla", lat=GOLDEN_LAT, lon=GOLDEN_LON,
            coordinate_source=COORD_OFFICIAL_ADDRESS_GEOCODE,
            consultar_entorno=lambda lat, lon: r)
        self.assertIsNone(urb["altura_maxima"])
        self.assertEqual(urb["altura_status"], STATUS_CONFLICT)
        self.assertEqual(urb["tipo_tratamiento"], "Nivel 2")
        self.assertEqual(urb["tipo_tratamiento_status"], STATUS_VERIFIED_OFFICIAL)

    def test_tipos_nivel1_y_nivel2_no_se_elige_ninguno(self):
        """#2 (H): tratamiento igual + tipos Nivel 1/Nivel 2 -> tipo ambiguo."""
        r = self._entorno([
            _feat({"tratamiento": "Consolidación", "tipo_tratamiento": "Nivel 1",
                   "altura_maxima": "11"}),
            _feat({"tratamiento": "Consolidación", "tipo_tratamiento": "Nivel 2",
                   "altura_maxima": "11"}),
        ])
        self.assertEqual(r["tratamiento"], "Consolidación")
        self.assertEqual(r["altura_maxima"], "11")
        self.assertIsNone(r["tipo_tratamiento"])
        self.assertIn("tipo_tratamiento", r["campos_ambiguos"])
        self.assertNotIn("altura_maxima", r["campos_ambiguos"])
        urb = resolve_official_urban_context(
            ciudad="barranquilla", lat=GOLDEN_LAT, lon=GOLDEN_LON,
            coordinate_source=COORD_OFFICIAL_ADDRESS_GEOCODE,
            consultar_entorno=lambda lat, lon: r)
        self.assertIsNone(urb["tipo_tratamiento"])
        self.assertEqual(urb["tipo_tratamiento_status"], STATUS_CONFLICT)
        self.assertEqual(urb["altura_maxima"], "11")
        self.assertEqual(urb["altura_status"], STATUS_VERIFIED_OFFICIAL)

    def test_tratamiento_ambiguo_no_atribuye_tipo_ni_altura(self):
        """Si el polígono no se determina, tipo/altura no son atribuibles."""
        r = self._entorno([
            _feat({"tratamiento": "Consolidación", "tipo_tratamiento": "Nivel 2",
                   "altura_maxima": "11"}),
            _feat({"tratamiento": "Renovación Urbana", "tipo_tratamiento": "Nivel 2",
                   "altura_maxima": "11"}),
        ])
        self.assertIsNone(r["tratamiento"])
        self.assertIsNone(r["tipo_tratamiento"])
        self.assertIsNone(r["altura_maxima"])
        for campo in ("tratamiento", "tipo_tratamiento", "altura_maxima"):
            self.assertIn(campo, r["campos_ambiguos"])


# ── B. El estado de construcción no se puede perder ──────────────────────────

class TestConstruccionNoSePierde(_Base):
    """#3/#4 (H): SOURCE_UNAVAILABLE sobrevive y NO se convierte en NO_MATCH."""

    def _enriquecer(self, fuentes):
        import catastro_predio
        with mock.patch.object(catastro_predio, "_query_capa",
                               side_effect=fuentes.query_capa), \
                mock.patch.object(catastro_predio, "_query_punto",
                                  side_effect=fuentes.query_punto):
            return catastro_predio.enriquecer_desde_ctl(GOLDEN_CODIGO, GOLDEN_NUPRE)

    def test_source_unavailable_sobrevive_enriquecer_desde_ctl(self):
        """#3 (H): antes se descartaba el objeto y el estado se perdía."""
        r = self._enriquecer(FuentesMock(construccion="SOURCE_UNAVAILABLE"))
        self.assertTrue(r.get("disponible"))
        const = r.get("construccion")
        self.assertIsNotNone(const, "el objeto de construcción debe conservarse")
        self.assertFalse(const["disponible"])
        self.assertEqual(const["construction_status"], "SOURCE_UNAVAILABLE")
        self.assertFalse(const["source_disponible"])
        self.assertEqual(const["resolution_method"], "spatial")
        self.assertIsNotNone(const["source_error"])

    def test_http_ok_sin_features_es_no_match(self):
        """#4 (H): el servicio respondió y no hay edificación -> NO_MATCH."""
        r = self._enriquecer(FuentesMock(construccion="NO_MATCH"))
        const = r["construccion"]
        self.assertFalse(const["disponible"])
        self.assertTrue(const["source_disponible"])
        self.assertEqual(const["construction_status"], "NO_MATCH")

    def test_pdf_no_dice_no_match_ni_posible_lote(self):
        """#3 (H) a nivel de render: SOURCE_UNAVAILABLE != 'sin edificación'."""
        from edificabilidad import filas_edificabilidad, _confrontacion
        ent = dict(_URBANO_GOLDEN)
        d = dict(filas_edificabilidad("barranquilla", ent, None,
                                      "SOURCE_UNAVAILABLE"))
        txt = (d["Pisos construidos (catastro)"] + " " +
               d["Confrontación (construido vs. norma)"]).lower()
        self.assertIn("fuente de construcción", txt)
        self.assertNotIn("sin edificación", txt)
        self.assertNotIn("posible lote", txt)
        self.assertEqual(_confrontacion("barranquilla", ent, None,
                                        "SOURCE_UNAVAILABLE")[0],
                         "pendiente_fuente")
        # Y NO_MATCH sí lo dice (no se confunden entre sí).
        d_nm = dict(filas_edificabilidad("barranquilla", ent, None, "NO_MATCH"))
        self.assertIn("sin edificación registrada",
                      d_nm["Pisos construidos (catastro)"])


# ── C. Precedencia determinista de la autoridad urbana ───────────────────────

class TestPrecedenciaDeterminista(_Base):
    """#5 (H): legacy 5 + oficial VERIFIED_OFFICIAL 11 -> nunca queda 5."""

    def _oficial(self):
        return resolve_official_urban_context(
            ciudad="barranquilla", lat=GOLDEN_LAT, lon=GOLDEN_LON,
            coordinate_source=COORD_OFFICIAL_ADDRESS_GEOCODE,
            consultar_entorno=lambda lat, lon: dict(_URBANO_GOLDEN))

    def test_altura_legacy_no_sobrevive(self):
        from pdf_compiler import _merge_contexto_urbano_oficial
        ent, trat, prov = _merge_contexto_urbano_oficial(
            {"tratamiento": "Consolidación", "altura_maxima": "5"},
            self._oficial(), "Consolidación")
        self.assertEqual(ent["altura_maxima"], "11")
        self.assertEqual(trat, "Consolidación")
        self.assertTrue(any(c["campo"] == "altura_maxima"
                            for c in prov["conflictos"]))
        # El render 6.3 muestra la altura OFICIAL, no la legacy.
        from edificabilidad import filas_edificabilidad
        d = dict(filas_edificabilidad("barranquilla", ent, None, "NO_MATCH"))
        self.assertIn("11", str(d["Altura normativa máxima"]))
        self.assertNotIn("5 pisos", str(d["Altura normativa máxima"]))


# ── D. Provenance por campo en destino/condición ─────────────────────────────

class TestProvenancePorCampo(_Base):
    """#6 (H): condición exacta + destino espacial con procedencia INDEPENDIENTE."""

    def test_condicion_exacta_destino_espacial(self):
        import catastro_predio

        def _capa(base, capa, where, *a, **kw):
            if "condicion" in base:
                return _ok([_feat({"condicion": "Propiedad Horizontal", "anio": 2025})])
            if "destinoseconomicos" in base:
                return _ok([])          # el exacto NO trae destino
            return _down()

        def _punto(base, capa, lon, lat, *a, **kw):
            if "destinoseconomicos" in base:
                return _ok([_feat({"destino": "Habitacional", "anio": 2026})])
            return _ok([])

        with mock.patch.object(catastro_predio, "_query_capa", _capa), \
                mock.patch.object(catastro_predio, "_query_punto", _punto):
            r = catastro_predio.consultar_condicion_destino(
                GOLDEN_CODIGO, GOLDEN_LAT, GOLDEN_LON)

        self.assertEqual(r["condicion"]["value"], "Propiedad Horizontal")
        self.assertEqual(r["condicion"]["resolution_method"], "exact_identifier")
        self.assertEqual(r["condicion"]["status"], "VERIFIED_CATASTRAL")
        self.assertTrue(r["condicion"]["source"])
        self.assertEqual(r["destino"]["value"], "Habitacional")
        self.assertEqual(r["destino"]["resolution_method"], "spatial")
        self.assertEqual(r["destino"]["status"], "VERIFIED_CATASTRAL")
        # NO se etiquetan ambos como exact_identifier.
        self.assertNotEqual(r["condicion"]["resolution_method"],
                            r["destino"]["resolution_method"])

    def test_sin_respuesta_distingue_unresolved_de_source_unavailable(self):
        import catastro_predio
        with mock.patch.object(catastro_predio, "_query_capa",
                               lambda *a, **k: _down()), \
                mock.patch.object(catastro_predio, "_query_punto",
                                  lambda *a, **k: _down()):
            r = catastro_predio.consultar_condicion_destino(
                GOLDEN_CODIGO, GOLDEN_LAT, GOLDEN_LON)
        self.assertEqual(r["condicion"]["status"], "SOURCE_UNAVAILABLE")
        self.assertEqual(r["destino"]["status"], "SOURCE_UNAVAILABLE")
        self.assertIsNone(r["condicion"]["value"])

        # Servicio que responde sin coincidencia -> UNRESOLVED (no SOURCE_UNAVAILABLE)
        catastro_predio._CACHE.clear()
        with mock.patch.object(catastro_predio, "_query_capa",
                               lambda *a, **k: _ok([])), \
                mock.patch.object(catastro_predio, "_query_punto",
                                  lambda *a, **k: _ok([])):
            r2 = catastro_predio.consultar_condicion_destino(
                GOLDEN_CODIGO, GOLDEN_LAT, GOLDEN_LON)
        self.assertEqual(r2["condicion"]["status"], "UNRESOLVED")
        self.assertEqual(r2["destino"]["status"], "UNRESOLVED")


# ── E. El NUPRE no es número predial ─────────────────────────────────────────

class TestNupreNoEsCodigo(_Base):
    """#7 (H): solo NUPRE AFT... -> NO se consulta terreno='AFT...'."""

    def test_nupre_no_se_usa_como_terreno(self):
        import catastro_predio
        vistas = []

        def _capa(base, capa, where, *a, **kw):
            vistas.append(where)
            if "condicion" in base or "destinoseconomicos" in base:
                return _ok([_feat({"condicion": "Propiedad Horizontal",
                                   "destino": "Habitacional"})])
            return _down()

        def _punto(base, capa, lon, lat, *a, **kw):
            if "destinoseconomicos" in base:
                return _ok([_feat({"destino": "Habitacional"})])
            return _ok([])

        with mock.patch.object(catastro_predio, "_query_capa", _capa), \
                mock.patch.object(catastro_predio, "_query_punto", _punto):
            r = catastro_predio.consultar_condicion_destino(
                GOLDEN_NUPRE, GOLDEN_LAT, GOLDEN_LON)

        self.assertFalse(any("terreno='AFT" in w for w in vistas),
                         f"se consultó el NUPRE como número predial: {vistas}")
        self.assertEqual(r["identificador_rechazado"], GOLDEN_NUPRE)
        self.assertIsNone(r["identificador_exacto_usado"])
        # Sin identificador predial NO hay falso "exacto": el dato solo puede
        # venir del contexto espacial (o quedar UNRESOLVED).
        self.assertIsNone(r["condicion"]["value"])
        self.assertEqual(r["condicion"]["status"], "UNRESOLVED")
        self.assertEqual(r["destino"]["value"], "Habitacional")
        self.assertEqual(r["destino"]["resolution_method"], "spatial")

    def test_codigo_valido_si_se_usa(self):
        import catastro_predio
        vistas = []

        def _capa(base, capa, where, *a, **kw):
            vistas.append(where)
            if "condicion" in base or "destinoseconomicos" in base:
                return _ok([_feat({"condicion": "Propiedad Horizontal",
                                   "destino": "Habitacional"})])
            return _down()

        with mock.patch.object(catastro_predio, "_query_capa", _capa), \
                mock.patch.object(catastro_predio, "_query_punto",
                                  lambda *a, **k: _ok([])):
            catastro_predio.consultar_condicion_destino(
                GOLDEN_CODIGO, GOLDEN_LAT, GOLDEN_LON)
        self.assertTrue(any(f"terreno='{GOLDEN_CODIGO}'" in w for w in vistas))


# ── F. Destino temático también cuando la capa 500 resuelve el predio ────────

class TestDestinoTematicoConPredioReal(_Base):
    """#8 (H): predio_real disponible + destino_economico None + destino_vigente."""

    def _enriquecer(self, fuentes):
        import catastro_predio
        with mock.patch.object(catastro_predio, "_query_capa",
                               side_effect=fuentes.query_capa), \
                mock.patch.object(catastro_predio, "_query_punto",
                                  side_effect=fuentes.query_punto):
            return catastro_predio.enriquecer_desde_ctl(GOLDEN_CODIGO, GOLDEN_NUPRE)

    def test_condicion_tematica_visible_en_el_predio_real(self):
        r = self._enriquecer(FuentesMock(destino_capa500=None,
                                         destino_tematico="Habitacional"))
        self.assertTrue(r["disponible"])
        p = r["predio"]
        self.assertIsNone(p["destino_economico"], "la capa 500 no trae destino")
        self.assertEqual(r["condicion"]["destino_vigente"], "Habitacional")
        self.assertEqual(r["condicion"]["destino"]["resolution_method"],
                         "exact_identifier")
        self.assertTrue(r["condicion"]["destino"]["source"])

    def test_pdf_usa_el_destino_tematico_con_su_procedencia(self):
        """#8 (H) E2E: sin destino en capa 500, 6.1 muestra el temático."""
        pdf = _compilar_golden(destino_capa500=None)
        txt = _texto_pdf(pdf)
        self.assertIn("habitacional", txt)
        self.assertIn("servicio destinos economicos", txt.replace("—", "--").replace("ó", "o"))
        self.assertNotIn("pendiente de verificacion (requiere consulta catastral del predio)",
                         txt)


# ── G. Semántica del estrato (H #9/#10) ──────────────────────────────────────

class TestEstratoSemantico(_Base):
    def _destino(self, estrato, destino):
        from dictamen_data import get_catastral_dt
        return dict(get_catastral_dt("Miramar", 58.75, destino_economico=destino,
                                     estrato=estrato))

    def test_sin_estrato_y_sin_destino_pendiente(self):
        """#9 (H)"""
        self.assertEqual(self._destino(None, None)["Estrato"],
                         "PENDIENTE DE VERIFICACIÓN")

    def test_sin_estrato_con_destino_habitacional_pendiente_residencial(self):
        """#10 (H): la ausencia del estrato NO implica uso no residencial."""
        t = self._destino(None, "Habitacional")["Estrato"]
        self.assertIn("PENDIENTE", t)
        self.assertIn("residencial", t)

    def test_origen_real_del_destino_en_6_1(self):
        """#G: no se atribuye a la Capa Predio lo que vino del servicio temático."""
        from dictamen_data import get_catastral_dt
        d = dict(get_catastral_dt("Miramar", 58.75, destino_economico="Habitacional",
                                  destino_source="thematic_spatial"))
        self.assertIn("contexto espacial", d["Destino economico catastral"])
        self.assertNotIn("Capa Predio", d["Destino economico catastral"])
        d2 = dict(get_catastral_dt("Miramar", 58.75, destino_economico="Habitacional",
                                   destino_source="capa_predio"))
        self.assertIn("Capa Predio GC-BAQ", d2["Destino economico catastral"])
        # Origen no declarado: NO se atribuye a una capa concreta.
        d3 = dict(get_catastral_dt("Miramar", 58.75, destino_economico="Habitacional"))
        self.assertNotIn("Capa Predio", d3["Destino economico catastral"])


# ── I. Golden E2E (capas oficiales sustituidas por fixtures) ─────────────────

def _compilar_golden(tmp_name="pdf_03h2a.pdf", **fuentes_kw):
    """Compila el PDF del caso Golden con las capas oficiales mockeadas."""
    import shutil
    import catastro_predio
    import geocoder
    import legal_analyzer
    import pdf_compiler
    import integrations.catastro_live as catastro_live
    from legal_analyzer import analizar_certificado

    fuentes = FuentesMock(**fuentes_kw)
    out_dir = ROOT / "tmp_pdf_03h2a"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_pdf = out_dir / tmp_name

    analysis = dict(analizar_certificado(None))
    analysis.update({
        "folio": "040-646406", "direccion": GOLDEN_DIRECCION,
        "codigo_catastral": GOLDEN_CODIGO, "nupre": GOLDEN_NUPRE,
        "descripcion_ctl": ("APARTAMENTO 430 TORRE 8 CONJUNTO NAPOLI MIRAMAR "
                            "PROPIEDAD HORIZONTAL"),
        "texto_ctl": "APARTAMENTO 430 - PROPIEDAD HORIZONTAL",
        "tipo_predio_snr": "APARTAMENTO",
    })
    record = {
        "id": 1, "folio_matricula": "040-646406", "direccion": GOLDEN_DIRECCION,
        "barrio": "Miramar", "estrato": 4, "area": 58.75,
        "valor_consolidado": None, "sombra_9am_cargada": 0,
        "sombra_3pm_cargada": 0, "mapa_cargado": 0, "acreedor_real": None,
        "certificado_path": None, "ciudad": "barranquilla",
    }
    catastro_predio._CACHE.clear()
    with mock.patch.object(legal_analyzer, "analizar_certificado",
                           return_value=analysis), \
            mock.patch.object(catastro_predio, "_query_capa",
                              side_effect=fuentes.query_capa), \
            mock.patch.object(catastro_predio, "_query_punto",
                              side_effect=fuentes.query_punto), \
            mock.patch.object(geocoder, "geocodificar_direccion",
                              lambda d, ciudad=None: (GOLDEN_LAT, GOLDEN_LON)), \
            mock.patch.object(pdf_compiler, "generate_maps",
                              lambda *a, **k: None), \
            mock.patch.object(catastro_live, "verificar_catastro_barranquilla",
                              lambda *a, **k: {"disponible": False,
                                               "numero_predial": None,
                                               "error": "servicio sin respuesta",
                                               "fuente": {}}), \
            mock.patch.object(pdf_compiler, "get_poi_result",
                              lambda *a, **k: {
                                  "items": {c: [] for c in ("Salud", "Educacion",
                                                            "Comercio", "Recreacion")},
                                  "category_status": {c: "NO_MATCH" for c in (
                                      "Salud", "Educacion", "Comercio", "Recreacion")},
                                  "sources_attempted": 1, "sources_succeeded": 1}):
        pdf_compiler.compile_pdf(record, str(out_pdf), assets_dir=out_dir)
    data = out_pdf.read_bytes() if out_pdf.exists() else b""
    shutil.rmtree(out_dir, ignore_errors=True)
    return data


def _texto_pdf(pdf_bytes):
    import io
    import pypdf
    r = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    return " ".join((p.extract_text() or "") for p in r.pages).lower()


class TestGoldenPdf(_Base):
    """#11 (H/I): 6.1 y 6.3 del Golden, sin contradicciones.

    Reproduce el escenario REAL del caso (capa 500 sin respuesta en esta
    ejecución -> identidad por registro oficial de adopción) con las capas POT
    y los servicios temáticos sustituidos por FIXTURES (sin red). Esto valida que
    el render conecta y etiqueta bien lo que la fuente devuelve, NO que la fuente
    viva responda: eso queda en la prueba network de 03G y en la regeneración del
    Golden contra los servicios reales.
    """

    @classmethod
    def setUpClass(cls):
        cls.txt = _texto_pdf(_compilar_golden(capa_500_resuelve=False))

    def test_61_datos_catastrales(self):
        self.assertIn("barrio / sector oficial", self.txt)
        self.assertIn("miramar", self.txt)
        self.assertIn("habitacional", self.txt)
        self.assertIn("propiedad horizontal", self.txt)

    def test_61_estrato_verificado(self):
        # 6.1 = estrato oficial 4 (no un default legacy)
        _i = self.txt.index("estrato")
        self.assertTrue("estrato" in self.txt and "4" in self.txt[_i:_i + 40])

    def test_61_destino_con_su_origen_real(self):
        """#G: el destino se etiqueta con el servicio que realmente lo devolvió."""
        _i = self.txt.index("destino económico catastral")
        _frag = self.txt[_i:_i + 160]
        self.assertIn("habitacional", _frag)
        self.assertIn("servicio destinos economicos", _frag.replace("ó", "o"))
        self.assertNotIn("capa predio", _frag)

    def test_63_tratamiento_y_altura_normativa(self):
        self.assertIn("consolidación", self.txt)
        self.assertIn("nivel 2", self.txt)
        self.assertIn("hasta 11 pisos", self.txt)

    def test_63_no_dice_posible_lote_ni_sin_edificacion(self):
        """#3 (H) en el PDF: SOURCE_UNAVAILABLE != 'sin edificación'."""
        self.assertNotIn("posible lote", self.txt)
        self.assertNotIn("sin edificación registrada", self.txt)
        self.assertIn("fuente de construcción", self.txt)

    def test_sin_contradicciones_de_tasa(self):
        """K: si el contexto está completo, la tasa es la del sector del predio."""
        # Contexto resuelto (fixture) -> la tasa aplicada es la de Miramar.
        self.assertIn("6.800.000", self.txt)
        # Y NO se declara "no autorizada" contradiciendo el contexto completo.
        self.assertNotIn("valoración no autorizada", self.txt)
        self.assertNotIn("contexto de mercado: incompleto", self.txt)

    def test_tipologia_no_atribuye_al_ctl_lo_que_vino_del_catastro(self):
        """#G: la condición es catastral, no una inferencia del CTL adjunto."""
        self.assertIn("propiedad horizontal (condición catastral)", self.txt)
        self.assertNotIn("propiedad horizontal (inferido del ctl)", self.txt)

    def test_localidad_del_contexto_oficial_no_queda_n_d(self):
        _i = self.txt.index("comuna/localidad")
        self.assertIn("norte centro histórico", self.txt[_i:_i + 60])

    def test_identidad_y_contexto_coherentes(self):
        """K: 07 no puede decir INCOMPLETO si 6.1/6.3 traen los datos verificados."""
        self.assertNotIn("contexto de mercado: incompleto", self.txt)
        self.assertNotIn("estimación referencial no emitida", self.txt)


class TestGoldenSinFuentes(_Base):
    """I: si las fuentes NO responden, el dictamen muestra PENDIENTE con causa.

    No se fuerza el Golden: sin capas oficiales no se afirma barrio/estrato/
    destino/tratamiento y la valoración queda BLOQUEADA (fail-closed).
    """

    @classmethod
    def setUpClass(cls):
        cls.txt = _texto_pdf(_compilar_golden(tmp_name="pdf_caido.pdf",
                                              todo_caido=True))

    def test_destino_y_estrato_pendientes(self):
        _i = self.txt.index("destino económico catastral")
        self.assertIn("pendiente", self.txt[_i:_i + 200])
        _j = self.txt.index("estrato")
        self.assertIn("pendiente", self.txt[_j:_j + 200])

    def test_condicion_y_tratamiento_no_se_inventan(self):
        _i = self.txt.index("condición jurídica")
        self.assertIn("pendiente", self.txt[_i:_i + 120])
        # 6.3 sin norma resuelta: no se afirma tratamiento ni altura.
        self.assertNotIn("hasta 11 pisos", self.txt)

    def test_construccion_pendiente_por_fuente(self):
        self.assertIn("fuente de construcción", self.txt)
        self.assertNotIn("sin edificación registrada", self.txt)
        self.assertNotIn("posible lote", self.txt)

    def test_valoracion_bloqueada_con_motivo(self):
        self.assertIn("valoración no autorizada", self.txt)
        self.assertNotIn("6.800.000", self.txt)


if __name__ == "__main__":
    unittest.main()
