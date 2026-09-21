# -*- coding: utf-8 -*-
"""
Remediation 03S.1A — SANCTIONS TRUTH LAYER: INTEGRITY CLOSURE.

Cierra cuatro defectos residuales del core sancionatorio:
  1. la frescura es LOCAL A LA EJECUCIÓN (nunca se hereda del store);
  2. la evidencia no puede desaparecer en silencio (envelope siempre + estado
     explícito de la cadena HMAC);
  3. COBERTURA != DECISIÓN (una fuente caída deja la cobertura parcial);
  4. los registros multi-identificador de las fuentes oficiales no se pierden.

Todo offline: las adquisiciones se simulan parcheando `fetch_bytes`, y las
fuentes se siembran como snapshots versionados.
"""
import io
import json
import os
import re
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "api"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "screening"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(API))
sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ["ARHIAX_SCREENING_OFFLINE"] = "1"

TMP = ROOT / "tmp_screening_03s1a"

_ANALYSIS = {
    "folio": "040-646406",
    "codigo_catastral": "080010103000010040001908040002",
    "nupre": "AFT0005BOHA",
    "direccion": "TV 43 # 100-50 TO 8 AP 430",
    "titulares": "DURAN BACCA ALISSON CC# 1045718995X 50%",
    "acreedor_snr": "BANCO DE BOGOTÁ S.A.NIT# 8600029644",
    "constructor": "URBANIZADORA MARIN VALENCIA / MARVAL",
    "hipoteca_vigente": {"anotacion": "007", "acreedor": "BANCO DE BOGOTÁ S.A."},
    "anotaciones_detalle": [
        {"num": "004", "tipo": "COMPRAVENTA", "partes": "DURAN BACCA ALISSON",
         "estado": "VIGENTE", "texto": "A: DURAN BACCA ALISSON"},
    ],
}

_FUENTE_FIXTURE = {
    "UN_CONSOLIDATED": "un_consolidated_sample.xml",
    "OFAC_SDN": "ofac_sdn_sample.xml",
    "UK_SANCTIONS_LIST": "uk_sanctions_list_sample.xml",
}

_TODAS = ("UN_CONSOLIDATED", "OFAC_SDN", "UK_SANCTIONS_LIST")


def setUpModule():
    shutil.rmtree(TMP, ignore_errors=True)
    TMP.mkdir(parents=True, exist_ok=True)


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


def _fixture(nombre):
    return (FIXTURES / nombre).read_bytes()


def _descarga_falsa(source_id):
    """Simula una adquisición REAL de la fuente (sin red) para esa fuente."""
    from sanctions.registry import get_source
    nombre = _FUENTE_FIXTURE.get(source_id)
    if nombre is None:
        raise AssertionError(f"sin fixture para {source_id}")
    return _fixture(nombre)


def _parche_descargas(por_fuente=None):
    """Parchea fetch_bytes: devuelve el XML oficial (sanitizado) de cada fuente."""
    from sanctions import acquire

    def _fetch(url, timeout=90):
        for sid, nombre in _FUENTE_FIXTURE.items():
            if get_source_url(sid) == url:
                return _fixture(nombre)
        raise AssertionError(f"URL no esperada en el test: {url}")

    def get_source_url(sid):
        from sanctions.registry import get_source
        return get_source(sid).official_url

    return mock.patch.object(acquire, "fetch_bytes", _fetch)


def _sembrar(base, por_fuente=None, *, edad_dias=0):
    """Siembra snapshots versionados (por defecto, los fixtures de las 3 fuentes)."""
    import datetime
    from sanctions.contracts import SanctionsSnapshot
    from sanctions.parsers import parse
    from sanctions.registry import get_source
    from sanctions.snapshots import SnapshotStore, snapshot_id

    if por_fuente is None:
        por_fuente = {
            "UN_CONSOLIDATED": parse("onu_xml", _fixture("un_consolidated_sample.xml")),
            "OFAC_SDN": parse("ofac_sdn_xml", _fixture("ofac_sdn_sample.xml")),
            "UK_SANCTIONS_LIST": parse("uk_sanctions_list_xml",
                                       _fixture("uk_sanctions_list_sample.xml")),
        }
    store = SnapshotStore(cache_dir=str(base))
    _ts = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=edad_dias)
    for sid, regs in por_fuente.items():
        d = get_source(sid)
        sha = f"fixture-{sid.lower()}-sha256"
        store.guardar(SanctionsSnapshot(
            snapshot_id=snapshot_id(sid, sha), source_id=sid, authority=d.authority,
            retrieved_at=_ts.isoformat().replace("+00:00", "Z"),
            effective_date="2026-09-19", source_url=d.official_url, sha256=sha,
            record_count=len(regs), parser_version=d.parser_version,
            acquisition_status="OPERATIVA"), regs)
    return store


def _ejecutar(**kwargs):
    from sanctions.engine import ejecutar_screening
    kwargs.setdefault("source_ids", _TODAS)
    kwargs.setdefault("permitir_descarga", False)
    kwargs.setdefault("encadenar_evidencia", True)
    return ejecutar_screening(analysis=_ANALYSIS, identidad={}, **kwargs)


# ── 1. FRESHNESS IS EXECUTION-LOCAL ─────────────────────────────────────────

class TestFrescuraLocalALaEjecucion(unittest.TestCase):
    """§ 03S.1A-1: LIVE_FRESH solo en la rama que descargó AHORA."""

    def test_a_descarga_real_es_live_y_b_segunda_ejecucion_es_cache(self):
        from sanctions.acquire import adquirir_fuente, es_en_vivo, es_cache
        from sanctions.snapshots import SnapshotStore

        base = TMP / "fresh_ab"
        store = SnapshotStore(cache_dir=str(base))

        # A) descarga real (simulada de forma determinista) -> LIVE_FRESH
        with _parche_descargas():
            snap_a, regs_a = adquirir_fuente("UN_CONSOLIDATED", store=store,
                                             force_refresh=True)
        self.assertEqual(snap_a.freshness, "LIVE_FRESH")
        self.assertTrue(es_en_vivo(snap_a))
        self.assertTrue(regs_a)

        # B) segunda ejecución, mismo snapshot, SIN descarga -> CACHED_FRESH
        snap_b, regs_b = adquirir_fuente("UN_CONSOLIDATED", store=store,
                                         permitir_descarga=False)
        self.assertEqual(snap_b.sha256, snap_a.sha256)      # mismo snapshot
        self.assertEqual(snap_b.freshness, "CACHED_FRESH")
        self.assertFalse(es_en_vivo(snap_b))
        self.assertTrue(es_cache(snap_b))
        self.assertTrue(regs_b)

    def test_c_ttl_vence_despues_de_la_descarga(self):
        from sanctions.acquire import adquirir_fuente
        from sanctions.snapshots import SnapshotStore

        base = TMP / "fresh_ttl"
        store = SnapshotStore(cache_dir=str(base))
        with _parche_descargas():
            snap, _ = adquirir_fuente("OFAC_SDN", store=store, force_refresh=True)
        self.assertEqual(snap.freshness, "LIVE_FRESH")

        # Mismo snapshot, pero con antigüedad > TTL: ya NO es fresco.
        _viejo = _reemplazar_fecha(snap, dias=5)
        store.guardar(_viejo, _fixture_regs("OFAC_SDN"))
        snap_stale, regs = adquirir_fuente("OFAC_SDN", store=store,
                                           permitir_descarga=False,
                                           ttl_segundos=24 * 3600, permitir_stale=True)
        self.assertEqual(snap_stale.freshness, "STALE_ALLOWED")
        self.assertFalse(snap_stale.freshness == "LIVE_FRESH")
        self.assertTrue(regs)   # la evidencia histórica no se destruye

        snap_no, regs_no = adquirir_fuente("OFAC_SDN", store=store,
                                           permitir_descarga=False,
                                           ttl_segundos=24 * 3600, permitir_stale=False)
        self.assertEqual(snap_no.freshness, "STALE_NOT_ALLOWED")
        self.assertEqual(regs_no, [])   # no se usan datos vencidos si no se admite

    def test_evaluar_frescura_nunca_devuelve_live(self):
        from sanctions.contracts import SanctionsSnapshot
        from sanctions.snapshots import evaluar_frescura
        import datetime
        snap = SanctionsSnapshot(
            snapshot_id="s", source_id="X", authority="a", sha256="h",
            retrieved_at="2026-09-20T00:00:00Z", freshness="LIVE_FRESH")
        _ts = datetime.datetime(2026, 9, 20, 0, 0,
                                tzinfo=datetime.timezone.utc).timestamp()
        self.assertNotEqual(evaluar_frescura(snap, ahora=_ts + 3600), "LIVE_FRESH")
        self.assertEqual(evaluar_frescura(snap, ahora=_ts + 3600), "CACHED_FRESH")
        # Vencido: el TTL manda y la política decide.
        _viejo = _ts + 10 * 86400
        self.assertEqual(evaluar_frescura(snap, ahora=_viejo, permitir_stale=True),
                         "STALE_ALLOWED")
        self.assertEqual(evaluar_frescura(snap, ahora=_viejo, permitir_stale=False),
                         "STALE_NOT_ALLOWED")

    def test_dictamen_sin_vivo_cuando_viene_del_store(self):
        _sembrar(TMP / "fresh_pdf")
        s = _ejecutar(cache_dir=str(TMP / "fresh_pdf"))
        self.assertEqual((s.extra or {}).get("en_vivo") or [], [])
        self.assertTrue((s.extra or {}).get("desde_snapshot"))
        for snap in s.snapshots:
            self.assertNotEqual(snap.freshness, "LIVE_FRESH")


def _reemplazar_fecha(snap, dias):
    import datetime
    from sanctions.contracts import SanctionsSnapshot
    d = snap.to_dict()
    _ts = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=dias)
    d["retrieved_at"] = _ts.isoformat().replace("+00:00", "Z")
    d["freshness"] = "LIVE_FRESH"   # ¡el store lo dice! aun así no puede reclamarlo
    return SanctionsSnapshot(**d)


def _fixture_regs(source_id):
    from sanctions.parsers import parse
    return parse({"UN_CONSOLIDATED": "onu_xml", "OFAC_SDN": "ofac_sdn_xml",
                  "UK_SANCTIONS_LIST": "uk_sanctions_list_xml"}[source_id],
                 _fixture(_FUENTE_FIXTURE[source_id]))


# ── 2. EVIDENCE CANNOT SILENTLY DISAPPEAR ───────────────────────────────────

class TestEvidenciaNoDesaparece(unittest.TestCase):
    """§ 03S.1A-2: un EvidenceRecord por outcome + estado de cadena explícito."""

    def test_evidencia_cuenta_igual_a_outcomes(self):
        _sembrar(TMP / "ev_ok")
        s = _ejecutar(cache_dir=str(TMP / "ev_ok"))
        self.assertEqual(s.evidence_expected_count, len(s.outcomes))
        self.assertEqual(s.evidence_created_count, len(s.outcomes))
        self.assertEqual(s.evidence_expected_count, 9)      # 3 sujetos × 3 fuentes
        self.assertTrue(s.evidence_complete)
        self.assertEqual(s.evidence_chain_status, "SEALED")
        self.assertTrue(s.evidence_reproducible)
        for e in s.evidence_records:
            for k in ("evidence_id", "subject_id", "source_id", "snapshot_sha256",
                      "query_hash", "evidence_hash", "result", "document_number_masked"):
                self.assertIn(k, e)
            _mask = e["document_number_masked"] or ""
            self.assertTrue(_mask == "N/D" or "*" in _mask)   # N/D o enmascarado
            self.assertNotIn("1045718995X", _mask)            # nunca en claro

    def test_cadena_fallida_es_visible_y_no_declara_sellado(self):
        _sembrar(TMP / "ev_fail")
        with mock.patch("sanctions.engine.encadenar_eventos", return_value=()):
            s = _ejecutar(cache_dir=str(TMP / "ev_fail"))
        self.assertEqual(s.evidence_chain_status, "FAILED")
        self.assertFalse(s.evidence_sealed)
        # Los envelopes SIGUEN existiendo (no desaparecen) y son reproducibles
        # por sus hashes, pero NO están sellados.
        self.assertTrue(s.evidence_reproducible)
        self.assertEqual(s.evidence_created_count, 9)
        self.assertEqual(len(s.evidence_records), 9)
        # El motivo lo declara y no hay afirmación de "sin coincidencias" pelada.
        self.assertIn("no pudo sellarse", s.reason)

    def test_produccion_fail_closed_sin_clave_de_evidencia(self):
        """En producción, sin clave HMAC la cadena falla y NO se declara completo."""
        _sembrar(TMP / "ev_prod")
        _entorno = {"ARHIAX_ENV": "production"}
        with mock.patch.dict(os.environ, _entorno, clear=False):
            for _k in ("ARHIAX_EVIDENCE_HMAC_KEY", "ARHIA_HMAC_KEY"):
                os.environ.pop(_k, None)
            try:
                s = _ejecutar(cache_dir=str(TMP / "ev_prod"))
            finally:
                pass
        self.assertEqual(s.evidence_chain_status, "FAILED")
        self.assertNotEqual(s.status, "SCREENING_COMPLETE")
        self.assertIn("no se declara completo", s.reason)
        self.assertFalse(s.evidence_sealed)

    def test_produccion_con_clave_sella_la_cadena(self):
        _sembrar(TMP / "ev_prod_ok")
        with mock.patch.dict(os.environ, {
                "ARHIAX_ENV": "production",
                "ARHIAX_EVIDENCE_HMAC_KEY": "clave-de-prueba-para-el-test"}, clear=False):
            s = _ejecutar(cache_dir=str(TMP / "ev_prod_ok"))
        self.assertEqual(s.evidence_chain_status, "SEALED")
        self.assertTrue(s.evidence_sealed)
        self.assertTrue(s.evidence_reproducible)
        self.assertEqual(s.status, "SCREENING_COMPLETE")

    def test_not_required_dev_es_explicito(self):
        _sembrar(TMP / "ev_dev")
        s = _ejecutar(cache_dir=str(TMP / "ev_dev"), encadenar_evidencia=False)
        self.assertEqual(s.evidence_chain_status, "NOT_REQUIRED_DEV")
        self.assertEqual(s.evidence_created_count, 9)   # la evidencia existe igual


# ── 3. COVERAGE != DECISION ─────────────────────────────────────────────────

class TestCoberturaVsDecision(unittest.TestCase):
    """§ 03S.1A-3"""

    def test_review_mas_fuente_caida_es_cobertura_parcial(self):
        _sembrar(TMP / "cov_partial", por_fuente={
            "UN_CONSOLIDATED": [{"id": "u1", "nombre": "DURAN BACCA ALISON",
                                 "alias": [], "tipo_documento": None,
                                 "numero_documento": None, "identifiers": ()}],
            "OFAC_SDN": [{"id": "o1", "nombre": "NADIE PARECIDO",
                          "alias": [], "identifiers": ()}],
        })
        s = _ejecutar(cache_dir=str(TMP / "cov_partial"))
        self.assertEqual(s.status, "SCREENING_REVIEW_REQUIRED")
        self.assertEqual(s.decision_status, "SCREENING_REVIEW_REQUIRED")
        self.assertFalse(s.coverage_complete)
        self.assertEqual(s.coverage_status, "COVERAGE_PARTIAL")
        self.assertEqual(s.sources_unavailable, ("UK_SANCTIONS_LIST",))
        # El motivo declara AMBAS cosas.
        self.assertIn("revisión humana", s.reason)
        self.assertIn("UKSL no estuvo disponible", s.reason)
        self.assertIn("Cobertura PARCIAL", s.reason)

    def test_cobertura_completa_solo_sin_pendientes(self):
        _sembrar(TMP / "cov_full")
        s = _ejecutar(cache_dir=str(TMP / "cov_full"))
        self.assertEqual(s.status, "SCREENING_COMPLETE")
        self.assertTrue(s.coverage_complete)
        self.assertEqual(s.coverage_status, "COVERAGE_COMPLETE")
        self.assertIn("Cobertura completa", s.reason)

    def test_cobertura_no_depende_del_status(self):
        """REVIEW_REQUIRED con todas las fuentes consultadas = cobertura completa."""
        _sembrar(TMP / "cov_review", por_fuente={
            "UN_CONSOLIDATED": [{"id": "u1", "nombre": "DURAN BACCA ALISON",
                                 "alias": [], "identifiers": ()}],
            "OFAC_SDN": [{"id": "o1", "nombre": "NADIE PARECIDO", "alias": [],
                          "identifiers": ()}],
            "UK_SANCTIONS_LIST": [{"id": "k1", "nombre": "NADIE PARECIDO",
                                   "alias": [], "identifiers": ()}],
        })
        s = _ejecutar(cache_dir=str(TMP / "cov_review"))
        self.assertEqual(s.status, "SCREENING_REVIEW_REQUIRED")
        self.assertTrue(s.coverage_complete)
        self.assertEqual(s.coverage_status, "COVERAGE_COMPLETE")

    def test_receipt_declara_decision_y_cobertura(self):
        from receipts import _screening_receipt
        _sembrar(TMP / "cov_receipt", por_fuente={
            "UN_CONSOLIDATED": [{"id": "u1", "nombre": "NADIE PARECIDO", "alias": [],
                                 "identifiers": ()}],
        })
        s = _ejecutar(cache_dir=str(TMP / "cov_receipt"))
        r = _screening_receipt({"screening_summary": s.to_dict()})
        self.assertEqual(r["decision_status"], s.status)
        self.assertEqual(r["coverage_status"], "COVERAGE_PARTIAL")
        self.assertFalse(r["coverage_complete"])
        self.assertEqual(r["evidence_expected"], 9)
        self.assertEqual(r["evidence_created"], 9)


# ── 4. MULTI-IDENTIFIER RECORDS ─────────────────────────────────────────────

class TestMultiIdentificador(unittest.TestCase):

    def test_onu_multi_identificador(self):
        from sanctions.parsers import parse_un_consolidated
        regs = parse_un_consolidated(_fixture("un_consolidated_sample.xml"))
        ind = next(r for r in regs if "PETROV" in r.nombre)
        valores = [i["value"] for i in ind.identifiers]
        self.assertIn("PA998877", valores)
        self.assertIn("DOC-2", valores)
        self.assertIn("DOC-3", valores)          # el 3.º tampoco se pierde
        ent = next(r for r in regs if r.id == "onu-9000002")
        self.assertIn("NIT-900123456", [i["value"] for i in ent.identifiers])
        self.assertEqual(ind.tipo_documento, "pasaporte")
        self.assertEqual(ind.numero_documento, "PA998877")

    def test_ofac_todos_los_ids(self):
        from sanctions.parsers import parse_ofac_sdn
        regs = parse_ofac_sdn(_fixture("ofac_sdn_sample.xml"))
        ind = next(r for r in regs if "KOVALENKO" in r.nombre)
        valores = [i["value"] for i in ind.identifiers]
        self.assertEqual(valores, ["UA112233", "DOC-2", "DOC-3"])
        self.assertEqual(ind.numero_documento, "UA112233")
        ent = next(r for r in regs if "MINERA" in r.nombre)
        self.assertIn("BR-770011", [i["value"] for i in ent.identifiers])

    def test_uksl_todos_los_identificadores(self):
        from sanctions.parsers import parse_uk_sanctions_list
        regs = parse_uk_sanctions_list(_fixture("uk_sanctions_list_sample.xml"))
        ind = next(r for r in regs if r.id == "uk-AFG0006")
        valores = [i["value"] for i in ind.identifiers]
        self.assertIn("AF1234567", valores)   # passport 1
        self.assertIn("DOC-2", valores)       # passport 2
        self.assertIn("DOC-3", valores)       # national identifier
        ent = next(r for r in regs if r.id == "uk-AFG0001")
        self.assertIn("BR-770011", [i["value"] for i in ent.identifiers])
        self.assertIn("BR-770012", [i["value"] for i in ent.identifiers])

    def _env(self, numero, tipo="cc"):
        from sanctions.contracts import SubjectEnvelope
        from sanctions.subjects import normalize_document_number
        return SubjectEnvelope(
            subject_id="s1", raw_name="SUJETO DE PRUEBA",
            canonical_name="SUJETO DE PRUEBA", person_type="NATURAL_PERSON",
            document_type=tipo, document_number=numero,
            document_normalized=normalize_document_number(tipo, numero))

    def _reg(self, ids):
        return {"id": "L1", "nombre": "OTRO NOMBRE COMPLETAMENTE DISTINTO",
                "alias": [],
                "identifiers": tuple({"type": t, "value": v, "source_field": "test"}
                                     for t, v in ids)}

    def test_segundo_identificador_confirma(self):
        """DOC-1 / DOC-2 / DOC-3: el sujeto con DOC-2 confirma por el 2.º."""
        from sanctions.matching import consultar
        r = consultar(self._env("DOC-2"),
                      [self._reg([("cc", "DOC-1"), ("cc", "DOC-2"), ("cc", "DOC-3")])])
        self.assertEqual(r.result, "EXACT_MATCH")
        self.assertIn("DOC-2", " ".join(r.reasons))

    def test_primer_id_incompatible_segundo_exacto(self):
        """El primer identificador es de otro tipo; el segundo coincide -> EXACT."""
        from sanctions.matching import consultar
        r = consultar(self._env("DOC-2", "cc"),
                      [self._reg([("pasaporte", "ZZ999"), ("cc", "DOC-2")])])
        self.assertEqual(r.result, "EXACT_MATCH")

    def test_identificador_de_tipo_incompatible_no_confirma(self):
        """Cédula vs pasaporte con el mismo número NO confirma por sí solo."""
        from sanctions.matching import consultar
        r = consultar(self._env("1234567890", "cc"),
                      [self._reg([("pasaporte", "1234567890")])])
        self.assertNotEqual(r.result, "EXACT_MATCH")

    def test_matcher_sigue_leyendo_registros_legacy(self):
        """Compatibilidad: registros sin `identifiers` (tipo/número legacy)."""
        from sanctions.matching import consultar
        r = consultar(self._env("8600029644", "nit"),
                      [{"id": "L9", "nombre": "OTRA EMPRESA SAS", "alias": [],
                        "tipo_documento": "nit", "numero_documento": "8600029644"}])
        self.assertEqual(r.result, "EXACT_MATCH")


# ── 5. NAME VARIANTS ────────────────────────────────────────────────────────

class TestVariantesDeclaradas(unittest.TestCase):

    def test_variantes_se_consultan_independientemente(self):
        from sanctions.subjects import build_subject_envelopes
        envs = build_subject_envelopes(_ANALYSIS, {})
        const = next(e for e in envs if "CONSTRUCTOR_ENAJENANTE" in e.roles)
        self.assertEqual(const.canonical_name, "URBANIZADORA MARIN VALENCIA / MARVAL")
        self.assertIn("URBANIZADORA MARIN VALENCIA", const.declared_name_variants)
        self.assertIn("MARVAL", const.declared_name_variants)
        self.assertEqual(len(const.nombres_a_consultar), 3)

    def test_punto_final_no_crea_una_variante_espuria(self):
        """'BANCO DE BOGOTÁ S.A.' NO debe generar una variante sin el punto."""
        from sanctions.subjects import build_subject_envelopes, variantes_declaradas
        self.assertEqual(variantes_declaradas("BANCO DE BOGOTÁ S.A."), ())
        envs = build_subject_envelopes(_ANALYSIS, {})
        banco = next(e for e in envs if "ACREEDOR_HIPOTECARIO" in e.roles)
        self.assertEqual(banco.declared_name_variants, ())
        self.assertEqual(banco.nombres_a_consultar, ("BANCO DE BOGOTÁ S.A.",))

    def test_variante_declarada_produce_resultado_conservador(self):
        """Un registro que coincide SOLO con la variante 'MARVAL' se reporta."""
        _sembrar(TMP / "var_marval", por_fuente={
            "UN_CONSOLIDATED": [{"id": "u1", "nombre": "MARVAL", "alias": [],
                                 "identifiers": ()}],
        })
        s = _ejecutar(cache_dir=str(TMP / "var_marval"))
        _o = next(o for o in s.outcomes
                  if o.source_id == "UN_CONSOLIDATED"
                  and o.subject_id.startswith("constructor"))
        self.assertEqual(_o.result, "POTENTIAL_MATCH")
        self.assertIn("variante declarada 'MARVAL'", " ".join(_o.matching_reasons))

    def test_persona_juridica_no_se_fusiona_por_nombre(self):
        """Dos personas jurídicas con nombre parecido NO se fusionan."""
        from sanctions.subjects import build_subject_envelopes
        a = dict(_ANALYSIS)
        a["constructor"] = "URBANIZADORA MARIN VALENCIA SAS"
        a["acreedor_snr"] = "URBANIZADORA MARIN SAS NIT# 900111222"
        envs = build_subject_envelopes(a, {})
        const = next(e for e in envs if "CONSTRUCTOR_ENAJENANTE" in e.roles)
        acre = next(e for e in envs if "ACREEDOR_HIPOTECARIO" in e.roles)
        self.assertNotEqual(const.subject_id, acre.subject_id)
        self.assertEqual(len([e for e in envs if "URBANIZADORA" in e.canonical_name]), 2)


# ── 6. TAXONOMÍA PEP ────────────────────────────────────────────────────────

class TestTaxonomiaPEP(unittest.TestCase):

    def test_pep_es_categoria_pep_y_sigue_fuera_de_alcance(self):
        from sanctions.registry import PEP_COLOMBIA, screening_sources, out_of_scope_sources
        self.assertEqual(PEP_COLOMBIA.category, "PEP_REGISTRY")
        self.assertNotEqual(PEP_COLOMBIA.category, "REGULATORY_REPORTING")
        self.assertEqual(PEP_COLOMBIA.acquisition_policy, "OUT_OF_SCOPE_FOR_SCREENING")
        self.assertFalse(PEP_COLOMBIA.es_screening)
        self.assertIn("PEP_COLOMBIA", [s.source_id for s in out_of_scope_sources()])
        self.assertNotIn("PEP_COLOMBIA", [s.source_id for s in screening_sources()])

    def test_uiaf_sigue_siendo_reporte_regulatorio(self):
        from sanctions.registry import UIAF_SIREL
        self.assertEqual(UIAF_SIREL.category, "REGULATORY_REPORTING")


# ── 7. DICTAMEN: la evidencia se declara ────────────────────────────────────

def _texto(pdf_bytes):
    import pypdf
    r = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    _t = " ".join((p.extract_text() or "") for p in r.pages).lower()
    return re.sub(r"\s+", " ", _t)


class TestDictamenEvidencia(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import test_remediacion_03s1 as _s31
        base = TMP / "pdf_ev_store"
        _sembrar(base)
        cls.txt = _texto(_s31._compilar_con_screening(tmp_name="pdf_ev.pdf",
                                                      store_base=base))

    def test_declara_conteo_y_cadena_de_evidencia(self):
        self.assertIn("09.3 evidencia de las consultas", self.txt)
        self.assertIn("envelopes de evidencia creados", self.txt)
        self.assertIn("evidencia sellada", self.txt)
        self.assertIn("sellada", self.txt)
        self.assertIn("reproducible con lo registrado", self.txt)

    def test_declara_cobertura(self):
        self.assertIn("cobertura completa", self.txt)


if __name__ == "__main__":
    unittest.main()
