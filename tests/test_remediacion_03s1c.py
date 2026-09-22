# -*- coding: utf-8 -*-
"""
Remediation 03S.1C — VERSIONED EXECUTION IDENTITY (FINAL FREEZE).

Garantiza que dos ejecuciones capaces de producir resultados distintos NUNCA
compartan la misma identidad criptográfica de consulta:

  1. versión del matcher corregida a la implementación real;
  2. versiones reales de los parsers en el registry y en cada snapshot;
  3. `query_hash` sella también la versión del PARSER;
  4/5/6. `screening_input_hash` (inputs efectivos del matcher) dentro del
     EvidenceRecord, junto a `matcher_version`/`parser_version`;
  7. contrato de reproducibilidad ampliado;
  8-11. tests: matcher/parser/variantes cambian el hash; determinismo.

Todo offline: se siembran snapshots versionados (sin red).
"""
import os
import shutil
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "api"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(API))

os.environ["ARHIAX_SCREENING_OFFLINE"] = "1"
TMP = ROOT / "tmp_screening_03s1c"

_ANALYSIS = {
    "folio": "040-646406",
    "titulares": "DURAN BACCA ALISSON CC# 1045718995X 50%",
    "acreedor_snr": "BANCO DE BOGOTÁ S.A.NIT# 8600029644",
    "constructor": "URBANIZADORA MARIN VALENCIA / MARVAL",
}
_TODAS = ("UN_CONSOLIDATED", "OFAC_SDN", "UK_SANCTIONS_LIST")


def setUpModule():
    shutil.rmtree(TMP, ignore_errors=True)
    TMP.mkdir(parents=True, exist_ok=True)


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


def _env(nombre, tipo="cc", numero="1045718995X", variantes=()):
    from sanctions.contracts import SubjectEnvelope
    from sanctions.subjects import normalize_document_number
    return SubjectEnvelope(
        subject_id="s1", raw_name=nombre, canonical_name=nombre,
        person_type="NATURAL_PERSON", document_type=tipo, document_number=numero,
        document_normalized=normalize_document_number(tipo, numero),
        declared_name_variants=tuple(variantes))


def _outcome(**over):
    from sanctions.contracts import SourceOutcome
    base = dict(subject_id="s1", source_id="UN_CONSOLIDATED", result="NO_MATCH",
                snapshot_sha256="SNAP-SHA", snapshot_effective_date="2026-09-19",
                parser_version="onu_xml/1.1.0")
    base.update(over)
    return SourceOutcome(**base)


def _sembrar(base, por_fuente=None, *, parser_version=None):
    import datetime
    from sanctions.contracts import SanctionsSnapshot
    from sanctions.registry import get_source
    from sanctions.snapshots import SnapshotStore, snapshot_id

    if por_fuente is None:
        por_fuente = {sid: [] for sid in _TODAS}
    store = SnapshotStore(cache_dir=str(base))
    _ts = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    for sid, regs in por_fuente.items():
        d = get_source(sid)
        sha = f"fixture-{sid.lower()}-sha256"
        store.guardar(SanctionsSnapshot(
            snapshot_id=snapshot_id(sid, sha), source_id=sid, authority=d.authority,
            retrieved_at=_ts, effective_date="2026-09-19", source_url=d.official_url,
            sha256=sha, record_count=len(regs),
            parser_version=parser_version or d.parser_version,
            acquisition_status="OPERATIVA"), regs)
    return store


def _ejecutar(**kwargs):
    from sanctions.engine import ejecutar_screening
    kwargs.setdefault("source_ids", _TODAS)
    kwargs.setdefault("permitir_descarga", False)
    return ejecutar_screening(analysis=_ANALYSIS, identidad={}, **kwargs)


# ── 1/2. VERSIONES DECLARADAS == IMPLEMENTACIÓN REAL ────────────────────────

class TestVersionesDeclaradas(unittest.TestCase):

    def test_matcher_version_actualizada(self):
        """§1: el matching cambió en 03S.1A/1B -> la versión NO puede ser 1.0."""
        from sanctions.matching import ALGORITHM_VERSION
        self.assertEqual(ALGORITHM_VERSION, "sanctions-matcher/1.1.0")
        self.assertNotEqual(ALGORITHM_VERSION, "sanctions-matcher/1.0")

    def test_parser_versions_reales_por_fuente(self):
        """§2: registry == implementación real (multi-identificador -> 1.1.0)."""
        from sanctions.parsers import PARSER_VERSIONS
        from sanctions.registry import (get_source, UN_CONSOLIDATED, OFAC_SDN,
                                        UK_SANCTIONS_LIST)
        self.assertEqual(UN_CONSOLIDATED.parser_version, PARSER_VERSIONS["onu_xml"])
        self.assertEqual(OFAC_SDN.parser_version, PARSER_VERSIONS["ofac_sdn_xml"])
        self.assertEqual(UK_SANCTIONS_LIST.parser_version,
                         PARSER_VERSIONS["uk_sanctions_list_xml"])
        for sid, parser in (("UN_CONSOLIDATED", "onu_xml"),
                            ("OFAC_SDN", "ofac_sdn_xml"),
                            ("UK_SANCTIONS_LIST", "uk_sanctions_list_xml")):
            self.assertEqual(get_source(sid).parser_version,
                             f"{parser}/1.1.0")
            self.assertNotIn("/1.0", get_source(sid).parser_version)

    def test_snapshot_declara_la_version_del_parser_usado(self):
        base = TMP / "snap_parser"
        _sembrar(base)
        from sanctions.snapshots import SnapshotStore
        snap, _ = SnapshotStore(cache_dir=str(base)).ultimo("OFAC_SDN")
        self.assertEqual(snap.parser_version, "ofac_sdn_xml/1.1.0")


# ── 3/4/5/6. IDENTIDAD CRIPTOGRÁFICA DE LA CONSULTA ─────────────────────────

class TestIdentidadDeEjecucion(unittest.TestCase):

    def test_8_matcher_version_cambia_query_hash(self):
        """§8: mismo sujeto/snapshot/parser, matcher 1.0 vs 1.1 -> hash distinto."""
        from sanctions.evidence import query_hash
        env = _env("JUAN PEREZ")
        h10 = query_hash(env, "UN_CONSOLIDATED", "SNAP", "onu_xml/1.1.0",
                         "sanctions-matcher/1.0")
        h11 = query_hash(env, "UN_CONSOLIDATED", "SNAP", "onu_xml/1.1.0",
                         "sanctions-matcher/1.1.0")
        self.assertNotEqual(h10, h11)

    def test_9_parser_version_cambia_query_hash(self):
        """§9: mismo XML (mismo sha) y mismo matcher, parser 1.0 vs 1.1."""
        from sanctions.evidence import query_hash
        env = _env("JUAN PEREZ")
        h10 = query_hash(env, "UN_CONSOLIDATED", "MISMO-SHA", "onu_xml/1.0.0",
                         "sanctions-matcher/1.1.0")
        h11 = query_hash(env, "UN_CONSOLIDATED", "MISMO-SHA", "onu_xml/1.1.0",
                         "sanctions-matcher/1.1.0")
        self.assertNotEqual(h10, h11)

    def test_10_variantes_declaradas_cambian_el_input(self):
        """§10: mismas canonical_name, variantes distintas -> hash distinto."""
        from sanctions.evidence import query_hash, screening_input_hash
        a = _env("URBANIZADORA MARIN VALENCIA / MARVAL")
        b = _env("URBANIZADORA MARIN VALENCIA / MARVAL",
                 variantes=("URBANIZADORA MARIN VALENCIA", "MARVAL"))
        self.assertEqual(a.canonical_name, b.canonical_name)
        self.assertNotEqual(screening_input_hash(a), screening_input_hash(b))
        self.assertNotEqual(query_hash(a, "UN_CONSOLIDATED", "SNAP"),
                            query_hash(b, "UN_CONSOLIDATED", "SNAP"))

    def test_11_determinismo(self):
        """§11: mismos inputs -> mismos hashes; content_hash reproducible."""
        from sanctions.evidence import build_evidence, query_hash, screening_input_hash
        env = _env("DURAN BACCA ALISSON", numero="1045718995X")
        o1, o2 = _outcome(), _outcome()
        self.assertEqual(screening_input_hash(env), screening_input_hash(env))
        self.assertEqual(query_hash(env, "UN_CONSOLIDATED", "SNAP"),
                         query_hash(env, "UN_CONSOLIDATED", "SNAP"))
        e1 = build_evidence(env, o1, screened_at="2026-09-22T00:00:00Z")
        e2 = build_evidence(env, o2, screened_at="2026-09-22T00:00:00Z")
        self.assertEqual(e1.evidence_hash, e2.evidence_hash)
        self.assertEqual(e1.evidence_content_hash, e2.evidence_content_hash)

    def test_11_evidence_hash_varia_solo_por_timestamp(self):
        """§11 documentado: content_hash estable; evidence_hash incluye el sello."""
        from sanctions.evidence import build_evidence
        env = _env("DURAN BACCA ALISSON")
        e1 = build_evidence(env, _outcome(), screened_at="2026-09-22T00:00:00Z")
        e2 = build_evidence(env, _outcome(), screened_at="2026-09-22T00:00:01Z")
        self.assertNotEqual(e1.evidence_hash, e2.evidence_hash)      # timestamp
        self.assertEqual(e1.evidence_content_hash, e2.evidence_content_hash)

    def test_cambio_de_identificadores_cambia_input(self):
        """Cambiar el documento/identificadores SÍ cambia el input efectivo."""
        from sanctions.evidence import screening_input_hash
        a = _env("JUAN PEREZ", "cc", "12345678")
        b = _env("JUAN PEREZ", "pasaporte", "12345678")
        c = _env("JUAN PEREZ", "cc", "87654321")
        self.assertNotEqual(screening_input_hash(a), screening_input_hash(b))
        self.assertNotEqual(screening_input_hash(a), screening_input_hash(c))

    def test_subject_hash_no_sustituye_al_input_hash(self):
        """§4: subject_hash conserva la identidad; el input es la autoridad."""
        from sanctions.evidence import screening_input_hash, subject_hash
        a = _env("URBANIZADORA MARIN VALENCIA / MARVAL")
        b = _env("URBANIZADORA MARIN VALENCIA / MARVAL",
                 variantes=("MARVAL",))
        # Misma identidad canónica declarada -> subject_hash igual...
        self.assertEqual(subject_hash(a), subject_hash(b))
        # ...pero los INPUTS efectivos del matcher difieren.
        self.assertNotEqual(screening_input_hash(a), screening_input_hash(b))


# ── 5/6/7. EVIDENCE RECORD Y CONTRATO DE REPRODUCIBILIDAD ───────────────────

class TestEvidenceRecordVersionado(unittest.TestCase):

    def test_envelope_lleva_matcher_parser_input(self):
        from sanctions.evidence import build_evidence
        env = _env("DURAN BACCA ALISSON")
        d = build_evidence(env, _outcome(
            parser_version="uk_sanctions_list_xml/1.1.0")).to_dict()
        self.assertEqual(d["matcher_version"], "sanctions-matcher/1.1.0")
        self.assertEqual(d["parser_version"], "uk_sanctions_list_xml/1.1.0")
        for k in ("subject_hash", "screening_input_hash", "snapshot_sha256",
                  "query_hash", "evidence_hash", "evidence_content_hash"):
            self.assertTrue(d.get(k), f"falta {k}")

    def test_evidence_hash_cambia_con_matcher_y_parser(self):
        """§6: cualquier cambio material altera evidence_hash."""
        from sanctions.evidence import build_evidence
        env = _env("DURAN BACCA ALISSON")
        base = build_evidence(env, _outcome()).evidence_hash
        otro_parser = build_evidence(env, _outcome(
            parser_version="onu_xml/1.0.0")).evidence_hash
        otro_matcher = build_evidence(
            env, _outcome(), algorithm_version="sanctions-matcher/1.0").evidence_hash
        otro_snapshot = build_evidence(env, _outcome(
            snapshot_sha256="OTRO-SHA")).evidence_hash
        for otro in (otro_parser, otro_matcher, otro_snapshot):
            self.assertNotEqual(base, otro)

    def test_reproducible_exige_identidad_de_ejecucion_completa(self):
        """§7: sin parser_version/matcher_version/screening_input_hash NO es
        reproducible aunque estén los cuatro hashes antiguos."""
        from sanctions.contracts import ScreeningSummary
        _completo = {
            "subject_hash": "h", "screening_input_hash": "i",
            "snapshot_sha256": "s", "parser_version": "p",
            "matcher_version": "m", "query_hash": "q", "evidence_hash": "e"}
        ok = ScreeningSummary(evidence_records=({"subject_id": "x", **_completo},),
                              evidence_expected_count=1, evidence_created_count=1,
                              evidence_chain_status="NOT_REQUIRED_DEV")
        self.assertTrue(ok.evidence_reproducible)
        for falta in ("parser_version", "matcher_version", "screening_input_hash"):
            _parcial = dict(_completo)
            _parcial[falta] = ""
            s = ScreeningSummary(evidence_records=({"subject_id": "x", **_parcial},),
                                 evidence_expected_count=1, evidence_created_count=1,
                                 evidence_chain_status="NOT_REQUIRED_DEV")
            self.assertFalse(s.evidence_reproducible, f"sin {falta} no es reproducible")


# ── 12/13. INTEGRACIÓN: el snapshot viaja hasta la evidencia ────────────────

class TestIntegracionVersionada(unittest.TestCase):

    def test_evidence_de_la_ejecucion_lleva_las_versiones_reales(self):
        _sembrar(TMP / "integracion")
        s = _ejecutar(cache_dir=str(TMP / "integracion"))
        self.assertEqual(s.evidence_created_count, 9)
        self.assertTrue(s.evidence_reproducible)
        for e in s.evidence_records:
            self.assertEqual(e["matcher_version"], "sanctions-matcher/1.1.0")
            self.assertTrue(e["parser_version"].endswith("/1.1.0"))
            self.assertTrue(e["screening_input_hash"])
            self.assertTrue(e["snapshot_sha256"])
            self.assertTrue(e["query_hash"])
            self.assertTrue(e["evidence_hash"])

    def test_parser_version_viene_del_snapshot_no_del_registry(self):
        """§12: si el snapshot histórico usó otro parser, se conserva ESE."""
        _sembrar(TMP / "snap_historico", parser_version="onu_xml/0.9.0-hist")
        s = _ejecutar(cache_dir=str(TMP / "snap_historico"),
                      source_ids=("UN_CONSOLIDATED",))
        _ev = [e for e in s.evidence_records
               if e["source_id"] == "UN_CONSOLIDATED"]
        self.assertTrue(_ev)
        for e in _ev:
            self.assertEqual(e["parser_version"], "onu_xml/0.9.0-hist")
        # Y el outcome también lo declara.
        for o in s.outcomes:
            if o.source_id == "UN_CONSOLIDATED":
                self.assertEqual(o.parser_version, "onu_xml/0.9.0-hist")

    def test_receipt_declara_versiones(self):
        from receipts import _screening_receipt
        _sembrar(TMP / "receipt")
        s = _ejecutar(cache_dir=str(TMP / "receipt"))
        r = _screening_receipt({"screening_summary": s.to_dict()})
        self.assertEqual(r["matcher_version"], "sanctions-matcher/1.1.0")
        self.assertEqual(r["parser_versions"]["OFAC_SDN"], "ofac_sdn_xml/1.1.0")
        self.assertTrue(r["evidence_reproducible"])


if __name__ == "__main__":
    unittest.main()
