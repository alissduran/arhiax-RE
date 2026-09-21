# -*- coding: utf-8 -*-
"""
Remediation 03S.1B — MATCHING SAFETY MICRO-CLOSURE.

Cierra cuatro defectos residuales del core antes de congelarlo:

  1/2/3. Mismo VALOR no es identificador COMPATIBLE: la unidad de comparación es
         (tipo-compatible, valor normalizado). Cédula 12345678 vs pasaporte
         12345678 -> REVIEW_REQUIRED con IDENTIFIER_TYPE_MISMATCH, nunca
         EXACT/STRONG "por documento coincidente".
  4.     Test específico de nombre exacto + tipo incompatible.
  5.     Control multi-ID: un ID incompatible adicional NO invalida uno
         compatible exacto.
  6.     `force_refresh` fallido: la frescura se reevalúa por EDAD (una caché
         vigente sigue siendo CACHED_FRESH) y el fallo se declara en
         `refresh_error`.
  7.     Semántica de evidencia separada: complete / sealed / reproducible.
  8.     Creación de evidencia AISLADA por outcome, con `evidence_errors`.

Todo offline: las descargas se simulan parcheando `fetch_bytes`.
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
sys.path.insert(0, str(Path(__file__).resolve().parent))

os.environ["ARHIAX_SCREENING_OFFLINE"] = "1"

TMP = ROOT / "tmp_screening_03s1b"

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


# ── utilidades de sujeto/registro ───────────────────────────────────────────

def _env(nombre, tipo, numero):
    from sanctions.contracts import SubjectEnvelope
    from sanctions.subjects import normalize_document_number
    return SubjectEnvelope(
        subject_id=f"s-{nombre}", raw_name=nombre, canonical_name=nombre,
        person_type="NATURAL_PERSON", document_type=tipo, document_number=numero,
        document_normalized=normalize_document_number(tipo, numero))


def _reg(nombre, ids, rid="L1"):
    return {"id": rid, "nombre": nombre, "alias": [],
            "identifiers": tuple({"type": t, "value": v, "source_field": "test"}
                                 for t, v in ids)}


def _sembrar(base, por_fuente=None, *, edad_segundos=0):
    """Siembra snapshots versionados (por defecto, uno vacío por fuente)."""
    import datetime
    from sanctions.contracts import SanctionsSnapshot
    from sanctions.registry import get_source
    from sanctions.snapshots import SnapshotStore, snapshot_id

    if por_fuente is None:
        por_fuente = {sid: [] for sid in _TODAS}
    store = SnapshotStore(cache_dir=str(base))
    _ts = datetime.datetime.now(datetime.timezone.utc) - \
        datetime.timedelta(seconds=edad_segundos)
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


def _descarga_que_falla(url, timeout=90):
    raise OSError("fallo de red simulado")


# ── 1/2/3/4. Mismo valor != identificador compatible ────────────────────────

class TestMismoValorNoEsCompatible(unittest.TestCase):
    """BLOCKER: nombre exacto + mismo número + tipo incompatible."""

    def test_a_nombre_exacto_mismo_valor_tipo_incompatible(self):
        """§4/§9.A: JUAN PEREZ cc 12345678 vs JUAN PEREZ pasaporte 12345678."""
        from sanctions.matching import consultar
        r = consultar(_env("JUAN PEREZ", "cc", "12345678"),
                      [_reg("JUAN PEREZ", [("pasaporte", "12345678")])])
        self.assertEqual(r.result, "REVIEW_REQUIRED")
        self.assertTrue(r.conflict)
        self.assertNotIn(r.result, ("EXACT_MATCH", "STRONG_MATCH"))
        self.assertIn("IDENTIFIER_TYPE_MISMATCH", " ".join(r.reasons))
        # Y NUNCA se corrobora "por documento coincidente".
        self.assertNotIn("documento coincidente", " ".join(r.reasons))

    def test_b_mismo_valor_tipo_compatible_es_exacto(self):
        """§9.B"""
        from sanctions.matching import consultar
        r = consultar(_env("JUAN PEREZ", "cc", "12345678"),
                      [_reg("OTRO NOMBRE DISTINTO", [("cc", "12345678")])])
        self.assertEqual(r.result, "EXACT_MATCH")

    def test_c_un_id_incompatible_no_invalida_uno_compatible(self):
        """§5/§9.C: pasaporte ZZ999 + cc DOC-2, sujeto cc DOC-2 -> EXACT."""
        from sanctions.matching import consultar
        r = consultar(_env("JUAN PEREZ", "cc", "DOC-2"),
                      [_reg("OTRO NOMBRE DISTINTO",
                            [("pasaporte", "ZZ999"), ("cc", "DOC-2")])])
        self.assertEqual(r.result, "EXACT_MATCH")
        self.assertFalse(r.conflict)

    def test_nombre_exacto_solo_corrobora_con_tipo_compatible(self):
        """§3: la corroboración por documento exige tipo compatible."""
        from sanctions.matching import consultar
        # Tipo compatible: nombre exacto + documento compatible -> STRONG.
        r_ok = consultar(_env("JUAN PEREZ", "cc", "12345678"),
                         [_reg("JUAN PEREZ", [("cc", "12345678")])])
        self.assertEqual(r_ok.result, "EXACT_MATCH")
        # Tipo incompatible: nunca corroboración.
        r_no = consultar(_env("JUAN PEREZ", "cc", "12345678"),
                         [_reg("JUAN PEREZ", [("pasaporte", "12345678")])])
        self.assertTrue(r_no.conflict)
        self.assertNotEqual(r_no.result, "STRONG_MATCH")

    def test_mismo_tipo_distinto_valor_sigue_siendo_conflicto(self):
        from sanctions.matching import consultar
        r = consultar(_env("JUAN PEREZ", "cc", "12345678"),
                      [_reg("JUAN PEREZ", [("cc", "99999999")])])
        self.assertEqual(r.result, "REVIEW_REQUIRED")
        self.assertTrue(r.conflict)
        self.assertIn("DOCUMENT_MISMATCH", " ".join(r.reasons))

    def test_tipo_no_declarado_en_la_lista_es_comodin(self):
        """Si la fuente no declara el tipo, el valor idéntico sí confirma."""
        from sanctions.matching import consultar
        r = consultar(_env("JUAN PEREZ", "cc", "12345678"),
                      [_reg("OTRO NOMBRE DISTINTO", [("", "12345678")])])
        self.assertEqual(r.result, "EXACT_MATCH")

    def test_variante_de_formato_con_tipo_incompatible_no_confirma(self):
        from sanctions.matching import consultar
        r = consultar(_env("JUAN PEREZ", "cc", "12345678X"),
                      [_reg("JUAN PEREZ", [("pasaporte", "12345678")])])
        self.assertNotIn(r.result, ("EXACT_MATCH", "STRONG_MATCH"))


# ── 6. force_refresh fallido: la frescura es EDAD ───────────────────────────

class TestRefreshFallido(unittest.TestCase):
    """§9.D/§9.E: freshness = edad, no éxito del refresh."""

    def test_d_refresh_falla_con_cache_vigente_sigue_cached_fresh(self):
        from sanctions.acquire import adquirir_fuente, es_cache, es_en_vivo
        base = TMP / "refresh_vigente"
        store = _sembrar(base, {"UN_CONSOLIDATED": [{"id": "u1", "nombre": "X",
                                                     "alias": [], "identifiers": ()}]},
                          edad_segundos=300)     # 5 minutos
        with mock.patch("sanctions.acquire.fetch_bytes", _descarga_que_falla):
            snap, regs = adquirir_fuente("UN_CONSOLIDATED", store=store,
                                         force_refresh=True, permitir_descarga=True)
        self.assertEqual(snap.freshness, "CACHED_FRESH")
        self.assertFalse(es_en_vivo(snap))
        self.assertTrue(es_cache(snap))
        self.assertIsNotNone(snap.refresh_error)
        self.assertIn("fallo de red simulado", snap.refresh_error)
        self.assertTrue(regs)                   # los datos siguen sirviendo
        self.assertIsNone(snap.error)           # hay dato: no es "sin dato"

    def test_e_refresh_falla_con_cache_vencida_aplica_politica(self):
        from sanctions.acquire import adquirir_fuente
        base = TMP / "refresh_vencido"
        _sembrar(base, {"OFAC_SDN": [{"id": "o1", "nombre": "X", "alias": [],
                                      "identifiers": ()}]},
                 edad_segundos=5 * 24 * 3600)
        from sanctions.snapshots import SnapshotStore
        store = SnapshotStore(cache_dir=str(base))

        with mock.patch("sanctions.acquire.fetch_bytes", _descarga_que_falla):
            snap_ok, regs_ok = adquirir_fuente("OFAC_SDN", store=store,
                                               force_refresh=True,
                                               ttl_segundos=24 * 3600,
                                               permitir_stale=True)
            snap_no, regs_no = adquirir_fuente("OFAC_SDN", store=store,
                                               force_refresh=True,
                                               ttl_segundos=24 * 3600,
                                               permitir_stale=False)
        self.assertEqual(snap_ok.freshness, "STALE_ALLOWED")
        self.assertTrue(regs_ok)
        self.assertEqual(snap_no.freshness, "STALE_NOT_ALLOWED")
        self.assertEqual(regs_no, [])
        for s in (snap_ok, snap_no):
            self.assertIsNotNone(s.refresh_error)
            self.assertIn("fallo de red simulado", s.refresh_error)

    def test_sin_intento_de_descarga_no_hay_refresh_error(self):
        from sanctions.acquire import adquirir_fuente
        base = TMP / "refresh_no_intentado"
        store = _sembrar(base, {"UK_SANCTIONS_LIST": []}, edad_segundos=60)
        snap, _ = adquirir_fuente("UK_SANCTIONS_LIST", store=store,
                                  permitir_descarga=False)
        self.assertEqual(snap.freshness, "CACHED_FRESH")
        self.assertIsNone(snap.refresh_error)


# ── 7/8. Semántica de evidencia y aislamiento ───────────────────────────────

class TestEvidenciaSemanticaYAislamiento(unittest.TestCase):

    def test_f_not_required_dev_complete_pero_no_sellada(self):
        """§9.F: en dev la evidencia es completa y reproducible, pero NO sellada."""
        _sembrar(TMP / "ev_dev")
        s = _ejecutar(cache_dir=str(TMP / "ev_dev"), encadenar_evidencia=False)
        self.assertEqual(s.evidence_chain_status, "NOT_REQUIRED_DEV")
        self.assertTrue(s.evidence_complete)
        self.assertFalse(s.evidence_sealed)          # NOT_REQUIRED_DEV != sellado
        self.assertTrue(s.evidence_reproducible)     # hashes presentes

    def test_sellada_exige_cadena_sealed(self):
        _sembrar(TMP / "ev_sealed")
        s = _ejecutar(cache_dir=str(TMP / "ev_sealed"))
        self.assertEqual(s.evidence_chain_status, "SEALED")
        self.assertTrue(s.evidence_sealed)
        self.assertTrue(s.evidence_complete)
        self.assertTrue(s.evidence_reproducible)

    def test_g_un_fallo_no_aborta_los_demas_envelopes(self):
        """§9.G: si un outcome falla, los demás envelopes se crean igual."""
        from sanctions import engine as _engine
        from sanctions.evidence import build_evidence as _real
        base = TMP / "ev_parcial"
        _sembrar(base)
        _objetivo = {"n": 0}

        def _falla_en_uno(env, outcome, **kw):
            _objetivo["n"] += 1
            if _objetivo["n"] == 4:      # el 4.º de 9 falla
                raise RuntimeError("fallo simulado de evidencia")
            return _real(env, outcome, **kw)

        with mock.patch.object(_engine, "build_evidence", _falla_en_uno):
            s = _ejecutar(cache_dir=str(base))
        self.assertEqual(s.evidence_expected_count, 9)
        self.assertEqual(s.evidence_created_count, 8)      # no se abortó
        self.assertEqual(len(s.evidence_records), 8)
        self.assertEqual(len(s.evidence_errors), 1)
        _e = s.evidence_errors[0]
        for k in ("subject_id", "source_id", "error"):
            self.assertIn(k, _e)
        self.assertIn("fallo simulado", _e["error"])
        self.assertFalse(s.evidence_complete)
        self.assertEqual(s.evidence_chain_status, "FAILED")
        self.assertFalse(s.evidence_sealed)
        self.assertIn("no se pudieron crear", s.reason)
        # Conjunto incompleto -> NO reproducible como conjunto, aunque cada uno de
        # los 8 envelopes conserva sus hashes (reproducibilidad individual).
        self.assertFalse(s.evidence_reproducible)
        for e in s.evidence_records:
            self.assertTrue(e["query_hash"] and e["evidence_hash"]
                            and e["snapshot_sha256"] and e["subject_hash"])

    def test_reproducible_exige_los_tres_hashes(self):
        from sanctions.contracts import ScreeningSummary
        base = dict(evidence_created_count=1, evidence_expected_count=1,
                    evidence_chain_status="NOT_REQUIRED_DEV")
        ok = ScreeningSummary(evidence_records=(
            {"query_hash": "q", "evidence_hash": "e", "snapshot_sha256": "s",
             "subject_hash": "h"},), **base)
        self.assertTrue(ok.evidence_reproducible)
        malo = ScreeningSummary(evidence_records=(
            {"query_hash": "q", "evidence_hash": "", "snapshot_sha256": "s",
             "subject_hash": "h"},), **base)
        self.assertFalse(malo.evidence_reproducible)


# ── Snapshots serializados: refresh_error sobrevive ─────────────────────────

class TestSnapshotRefreshErrorPersistido(unittest.TestCase):

    def test_refresh_error_se_relee_del_store(self):
        from sanctions.acquire import adquirir_fuente
        from sanctions.snapshots import SnapshotStore
        base = TMP / "refresh_persistido"
        store = _sembrar(base, {"UN_CONSOLIDATED": []}, edad_segundos=120)
        with mock.patch("sanctions.acquire.fetch_bytes", _descarga_que_falla):
            snap, _ = adquirir_fuente("UN_CONSOLIDATED", store=store,
                                      force_refresh=True)
        self.assertIsNotNone(snap.refresh_error)
        # El store mantiene el snapshot original; el refresh_error es de la
        # ejecución (no contamina el artefacto guardado).
        _otro = SnapshotStore(cache_dir=str(base)).ultimo("UN_CONSOLIDATED")
        self.assertIsNone(_otro[0].refresh_error)

    def test_extra_del_resumen_declara_refresh_errors(self):
        base = TMP / "refresh_extra"
        store = _sembrar(base, {"UN_CONSOLIDATED": []}, edad_segundos=60)
        with mock.patch("sanctions.acquire.fetch_bytes", _descarga_que_falla):
            from sanctions.acquire import adquirir_fuente
            snap, _ = adquirir_fuente("UN_CONSOLIDATED", store=store,
                                      force_refresh=True)
        self.assertIn("fallo de red simulado", snap.refresh_error or "")


if __name__ == "__main__":
    unittest.main()
