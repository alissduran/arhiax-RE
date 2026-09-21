# -*- coding: utf-8 -*-
"""
Remediation 03S.1 — SANCTIONS SCREENING TRUTH LAYER.

Sujetos canónicos → fuentes oficiales → snapshots versionados → matching
determinista → evidencia → dictus honesto.

Todo offline (ARHIAX_SCREENING_OFFLINE=1): las fuentes se siembran como
snapshots versionados y los parsers se prueban contra fixtures SANITIZADOS con
la estructura OFICIAL de cada lista. La verificación EN VIVO de UN/OFAC/UKSL se
ejecuta aparte con `scripts/screening_live_check.py` (§40).
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

# La suite NUNCA debe tocar la red (los tests siembran snapshots).
os.environ["ARHIAX_SCREENING_OFFLINE"] = "1"

TMP = ROOT / "tmp_screening_03s1"

# Sujetos del caso Golden 040-646406 (textos tal como los emite el CTL).
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
        {"num": "004", "fecha": "22-01-2024", "tipo": "COMPRAVENTA",
         "partes": "DURAN BACCA ALISSON", "estado": "VIGENTE",
         "texto": "A: DURAN BACCA ALISSON CC# 1045718995"},
        {"num": "007", "fecha": "22-01-2024", "tipo": "GRAVAMEN: HIPOTECA",
         "partes": "De -> BANCO DE BOGOTÁ S.A.", "estado": "VIGENTE",
         "texto": "HIPOTECA ABIERTA"},
    ],
}


def setUpModule():
    shutil.rmtree(TMP, ignore_errors=True)
    TMP.mkdir(parents=True, exist_ok=True)


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


def _cargar_fixture(nombre: str) -> bytes:
    return (FIXTURES / nombre).read_bytes()


def _sembrar_snapshots(base: Path, *, por_fuente=None, ttl_ok=True):
    """Siembra snapshots versionados (CURRENT) en el store de sanciones.

    `por_fuente`: {source_id: [registros]} — si no se indica, se parsean los
    fixtures oficiales sanitizados.
    """
    from sanctions.parsers import parse
    from sanctions.registry import get_source
    from sanctions.snapshots import SnapshotStore, snapshot_id
    from sanctions.contracts import SanctionsSnapshot

    por_fuente = por_fuente if por_fuente is not None else {
        "UN_CONSOLIDATED": parse("onu_xml", _cargar_fixture("un_consolidated_sample.xml")),
        "OFAC_SDN": parse("ofac_sdn_xml", _cargar_fixture("ofac_sdn_sample.xml")),
        "UK_SANCTIONS_LIST": parse("uk_sanctions_list_xml",
                                   _cargar_fixture("uk_sanctions_list_sample.xml")),
    }
    store = SnapshotStore(cache_dir=str(base))
    import datetime
    _ts = datetime.datetime.now(datetime.timezone.utc)
    if not ttl_ok:  # snapshot viejo: fuera de TTL
        _ts = _ts - datetime.timedelta(days=9)
    for sid, regs in por_fuente.items():
        d = get_source(sid)
        sha = f"fixture-{sid.lower()}-sha256"
        snap = SanctionsSnapshot(
            snapshot_id=snapshot_id(sid, sha), source_id=sid, authority=d.authority,
            retrieved_at=_ts.isoformat().replace("+00:00", "Z"),
            effective_date="2026-09-19", source_url=d.official_url, sha256=sha,
            record_count=len(regs), parser_version=d.parser_version,
            acquisition_status="OPERATIVA")
        store.guardar(snap, regs)
    return store


def _ejecutar(**kwargs):
    from sanctions.engine import ejecutar_screening
    kwargs.setdefault("source_ids", ("UN_CONSOLIDATED", "OFAC_SDN", "UK_SANCTIONS_LIST"))
    kwargs.setdefault("permitir_descarga", False)   # suite offline: sin red
    return ejecutar_screening(analysis=_ANALYSIS, identidad={},
                              encadenar_evidencia=False, **kwargs)


# ── §7/§8/§9 — parsers contra fixtures con formato OFICIAL ───────────────────

class TestParsersOficiales(unittest.TestCase):
    """§39: cada parser se prueba con un fixture sanitizado del formato oficial."""

    def test_parser_onu(self):
        from sanctions.parsers import parse_un_consolidated
        regs = parse_un_consolidated(_cargar_fixture("un_consolidated_sample.xml"))
        self.assertEqual(len(regs), 2)
        indiv = next(r for r in regs if "PETROV" in r.nombre)
        self.assertIn("IVAN", indiv.nombre)
        self.assertIn("IVAN PETROVICH", indiv.alias)
        self.assertEqual(indiv.fecha_nacimiento, "1965-04-12")
        self.assertTrue(indiv.programas)

    def test_parser_ofac_sdn(self):
        from sanctions.parsers import parse_ofac_sdn
        regs = parse_ofac_sdn(_cargar_fixture("ofac_sdn_sample.xml"))
        self.assertEqual(len(regs), 2)
        ind = next(r for r in regs if "KOVALENKO" in r.nombre)
        self.assertEqual(ind.tipo_documento, "pasaporte")
        self.assertEqual(ind.numero_documento, "UA112233")
        self.assertIn("ANDREY KOVALENKO", " ".join(ind.alias))
        self.assertEqual(ind.fecha_nacimiento, "12 Mar 1971")

    def test_parser_uk_sanctions_list(self):
        from sanctions.parsers import parse_uk_sanctions_list
        regs = parse_uk_sanctions_list(_cargar_fixture("uk_sanctions_list_sample.xml"))
        self.assertEqual(len(regs), 2)
        ent = next(r for r in regs if r.id == "uk-AFG0001")
        self.assertEqual(ent.nombre, "HAJI KHAIRULLAH HAJI SATTAR MONEY EXCHANGE")
        self.assertIn("Haji Alim Hawala", ent.alias)
        self.assertEqual(ent.tipo_documento, "nit")   # IndividualEntityShip: Entity
        ind = next(r for r in regs if r.id == "uk-AFG0006")
        self.assertEqual(ind.nombre, "MOHAMMAD HASSAN AKHUND")
        self.assertEqual(ind.numero_documento, "AF1234567")
        self.assertEqual(ind.tipo_documento, "pasaporte")
        self.assertEqual(ind.fecha_nacimiento, "dd/mm/1945")

    def test_estructura_no_reconocida_falla(self):
        from sanctions.parsers import parse_uk_sanctions_list, FuenteEstructuraNoReconocida
        with self.assertRaises(FuenteEstructuraNoReconocida):
            parse_uk_sanctions_list(b"<OtraCosa/>")


# ── §6/§9/§10/§11 — SourceRegistry ──────────────────────────────────────────

class TestSourceRegistry(unittest.TestCase):

    def test_uk_vigente_es_la_uk_sanctions_list(self):
        """§33: current(UK) == UK_SANCTIONS_LIST. Nunca ConList.xml."""
        from sanctions.registry import current_source_id, get_source
        self.assertEqual(current_source_id("uk"), "UK_SANCTIONS_LIST")
        vigente = get_source("UK_SANCTIONS_LIST")
        self.assertEqual(vigente.current_or_historical, "CURRENT")
        self.assertIn("fcdo.gov.uk", vigente.official_url)

    def test_conlist_es_historico_y_no_vigente(self):
        from sanctions.registry import (get_source, current_source_id,
                                        UK_OFSI_CONLIST_HISTORICAL)
        self.assertIsNone(current_source_id("uk_ofsi"))
        hist = get_source("UK_OFSI_CONLIST_HISTORICAL")
        self.assertEqual(hist.current_or_historical, "HISTORICAL")
        self.assertFalse(hist.es_screening)
        self.assertIn("ConList.xml", UK_OFSI_CONLIST_HISTORICAL.official_url)

    def test_uiaf_no_es_fuente_de_screening(self):
        """§10: UIAF/SIREL es REGULATORY_REPORTING, fuera de las fuentes."""
        from sanctions.registry import (UIAF_SIREL, screening_sources,
                                        out_of_scope_sources)
        self.assertEqual(UIAF_SIREL.category, "REGULATORY_REPORTING")
        self.assertEqual(UIAF_SIREL.acquisition_policy, "OUT_OF_SCOPE_FOR_SCREENING")
        self.assertFalse(UIAF_SIREL.es_screening)
        self.assertNotIn("UIAF_SIREL", [s.source_id for s in screening_sources()])
        self.assertIn("UIAF_SIREL", [s.source_id for s in out_of_scope_sources()])

    def test_cobertura_no_afirma_ofac_completo_sin_nonsdn(self):
        """§8: con solo SDN, la cobertura NO puede decir 'OFAC completo'."""
        from sanctions.registry import cobertura_declarada
        txt = cobertura_declarada(["UN_CONSOLIDATED", "OFAC_SDN", "UK_SANCTIONS_LIST"])
        self.assertIn("OFAC — SDN (solo SDN)", txt)
        txt2 = cobertura_declarada(["OFAC_SDN", "OFAC_NON_SDN"])
        self.assertIn("+ listas no-SDN consolidadas", txt2)

    def test_core_sources_sin_uiaf(self):
        from sanctions.registry import CORE_SOURCE_IDS
        self.assertEqual(set(CORE_SOURCE_IDS),
                         {"UN_CONSOLIDATED", "OFAC_SDN", "UK_SANCTIONS_LIST"})


# ── §1–§5 — Sujetos canónicos ───────────────────────────────────────────────

class TestSubjectEnvelope(unittest.TestCase):

    def _env(self, **over):
        from sanctions.subjects import build_subject_envelopes
        a = dict(_ANALYSIS)
        a.update(over)
        return build_subject_envelopes(a, over.pop("identidad", {}) if False else {})

    def test_titular_es_persona_natural(self):
        """§29: DURAN BACCA ALISSON CC ... -> NATURAL_PERSON, nunca LEGAL_ENTITY."""
        envs = self._env()
        tit = next(e for e in envs if "TITULAR_ACTUAL" in e.roles)
        self.assertEqual(tit.canonical_name, "DURAN BACCA ALISSON")
        self.assertEqual(tit.person_type, "NATURAL_PERSON")
        self.assertEqual(tit.document_type, "cc")
        self.assertEqual(tit.document_number, "1045718995X")
        self.assertEqual(tit.participation, "50%")

    def test_banco_es_persona_juridica(self):
        """§30: BANCO DE BOGOTÁ S.A. NIT 8600029644 -> LEGAL_ENTITY."""
        envs = self._env()
        banco = next(e for e in envs if "ACREEDOR_HIPOTECARIO" in e.roles)
        self.assertEqual(banco.canonical_name, "BANCO DE BOGOTÁ S.A.")
        self.assertEqual(banco.person_type, "LEGAL_ENTITY")
        self.assertEqual(banco.document_type, "nit")
        self.assertEqual(banco.document_number, "8600029644")

    def test_constructor_no_desaparece(self):
        """§31: el constructor/enajenante está en el MISMO set canónico."""
        envs = self._env()
        const = next(e for e in envs if "CONSTRUCTOR_ENAJENANTE" in e.roles)
        self.assertEqual(const.person_type, "LEGAL_ENTITY")  # URBANIZADORA -> jurídica
        self.assertIn("MULTIPLE_NAME_VARIANTS_NOT_FUSED", const.identity_warnings)
        self.assertIn("DOCUMENT_MISSING", const.identity_warnings)

    def test_invariante_sujetos_cuadra(self):
        """§5/§31: declarados == screeningados + no_screeningados_con_motivo."""
        from sanctions.subjects import invitantes, verificar_invariante
        envs = self._env()
        verificar_invariante(envs)
        c = invitantes(envs)
        self.assertEqual(c["subjects_declared"], 3)
        self.assertEqual(c["subjects_screened"], 3)
        self.assertEqual(c["subjects_not_screened_with_reason"], 0)

    def test_sujeto_inservible_no_desaparece(self):
        """§5: un sujeto con nombre inservible se declara NO screeningado CON motivo."""
        from sanctions.subjects import invitantes
        envs = self._env(titulares="N/D CC# 123", acreedor_snr=None, constructor=None)
        c = invitantes(envs)
        self.assertEqual(c["subjects_declared"],
                         c["subjects_screened"] + c["subjects_not_screened_with_reason"])
        self.assertEqual(c["subjects_declared"], 1)
        self.assertEqual(c["subjects_not_screened_with_reason"], 1)
        self.assertTrue(envs[0].not_screened_reason)

    def test_placeholder_no_crea_sujeto(self):
        """Un marcador ('PENDIENTE DE VERIFICACION') NO es un sujeto: no se inventa."""
        from sanctions.subjects import invitantes
        envs = self._env(titulares="PENDIENTE DE VERIFICACION",
                         acreedor_snr=None, constructor=None)
        self.assertEqual(invitantes(envs)["subjects_declared"], 0)

    def test_sin_documento_no_se_asume_persona_natural(self):
        """§3: sin documento y sin forma societaria -> UNKNOWN (nunca 'natural')."""
        envs = self._env(titulares="PEREZ GOMEZ JUAN", acreedor_snr=None,
                         constructor=None)
        self.assertEqual(envs[0].person_type, "UNKNOWN")
        self.assertIn("PERSON_TYPE_UNKNOWN", envs[0].identity_warnings)

    def test_tipo_resuelto_por_modelo_canonico_manda(self):
        from sanctions.subjects import build_subject_envelopes
        a = dict(_ANALYSIS)
        a["titulares"] = "DURAN BACCA ALISSON CC# 1045718995X 50%"
        envs = build_subject_envelopes(a, {"titular": {
            "nombre": "DURAN BACCA ALISSON", "tipo_documento": "cc",
            "numero_documento": "1045718995", "tipo_persona": "NATURAL_PERSON"}})
        tit = next(e for e in envs if "TITULAR_ACTUAL" in e.roles)
        self.assertEqual(tit.person_type, "NATURAL_PERSON")


# ── §17/§18/§19/§36 — Matching ──────────────────────────────────────────────

class TestMatching(unittest.TestCase):

    def _env(self, nombre, tipo_doc=None, numero=None, persona="NATURAL_PERSON"):
        from sanctions.contracts import SubjectEnvelope
        from sanctions.subjects import normalize_document_number
        return SubjectEnvelope(
            subject_id="s1", raw_name=nombre, canonical_name=nombre,
            person_type=persona, document_type=tipo_doc, document_number=numero,
            document_normalized=normalize_document_number(tipo_doc, numero))

    def _reg(self, id, nombre, tipo_doc=None, numero=None, alias=(), dob=None):
        return {"id": id, "nombre": nombre, "alias": list(alias),
                "tipo_documento": tipo_doc, "numero_documento": numero,
                "fecha_nacimiento": dob}

    def test_documento_exacto_es_exact_match(self):
        from sanctions.matching import consultar
        r = consultar(self._env("DURAN BACCA ALISSON", "cc", "1045718995X"),
                      [self._reg("L1", "OTRO NOMBRE", "cc", "1045718995X")])
        self.assertEqual(r.result, "EXACT_MATCH")
        self.assertEqual(r.matched_record_ids, ("L1",))

    def test_nombre_exacto_con_corroboracion_es_strong_match(self):
        from sanctions.matching import consultar
        r = consultar(self._env("DURAN BACCA ALISSON"),
                      [self._reg("L2", "ALISSON DURAN BACCA", alias=["DURAN BACCA ALISSON"])])
        self.assertEqual(r.result, "STRONG_MATCH")
        self.assertTrue(r.requiere_revision)

    def test_fuzzy_solo_nombre_nunca_confirma(self):
        """§36: name-only fuzzy -> POTENTIAL/REVIEW_REQUIRED, nunca MATCH."""
        from sanctions.matching import consultar
        r = consultar(self._env("JUAN CARLOS PEREZ GOMEZ"),
                      [self._reg("L3", "JUAN CARLOS PEREZ GOMES")])
        self.assertIn(r.result, ("POTENTIAL_MATCH", "REVIEW_REQUIRED"))
        self.assertTrue(r.requiere_revision)
        self.assertNotIn(r.result, ("EXACT_MATCH", "STRONG_MATCH"))

    def test_conflicto_de_identificadores_no_confirma(self):
        """§19: nombre exacto + documento/DOB incompatible -> REVIEW_REQUIRED."""
        from sanctions.matching import consultar
        env = self._env("JUAN PEREZ", "cc", "12345")
        r = consultar(env, [self._reg("L4", "JUAN PEREZ", "pasaporte", "99999",
                                      dob="01/01/1980")])
        self.assertEqual(r.result, "REVIEW_REQUIRED")
        self.assertTrue(r.conflict)
        self.assertTrue(any("conflicto" in x for x in r.reasons))

    def test_sin_similitud_es_no_match(self):
        from sanctions.matching import consultar
        r = consultar(self._env("DURAN BACCA ALISSON"),
                      [self._reg("L5", "EMPRESA MINERA DEL SUR SAS", "nit", "800111222")])
        self.assertEqual(r.result, "NO_MATCH")

    def test_alias_exacto_con_atributo_corroborante(self):
        from sanctions.matching import consultar
        r = consultar(self._env("BANCO DE BOGOTA S.A.", "nit", "8600029644"),
                      [self._reg("L6", "BANCO DE BOGOTA SA", "nit", "8600029644",
                                 alias=["BANCO DE BOGOTA"])])
        self.assertEqual(r.result, "EXACT_MATCH")


    def test_nucleo_distinto_no_coincide_por_documento(self):
        """Dos documentos DISTINTOS no se "corrigen": no hay coincidencia."""
        from sanctions.matching import consultar
        r = consultar(self._env("DURAN BACCA ALISSON", "cc", "1045718995X"),
                      [self._reg("L8", "OTRA PERSONA", "cc", "9988776655")])
        self.assertEqual(r.result, "NO_MATCH")

    def test_variante_de_formato_de_documento_queda_en_revision(self):
        """1045718995X vs 1045718995: coincide, pero NUNCA como exacto silencioso."""
        from sanctions.matching import consultar
        r = consultar(self._env("DURAN BACCA ALISSON", "cc", "1045718995X"),
                      [self._reg("L7", "ALISSON DURAN", "cc", "1045718995")])
        self.assertEqual(r.result, "STRONG_MATCH")
        self.assertTrue(r.requiere_revision)
        self.assertIn("variante de formato", " ".join(r.reasons))


# ── §13–§16/§34 — Snapshots, frescura y semántica de "en vivo" ──────────────

class TestSnapshotsYFrescura(unittest.TestCase):

    def test_snapshot_guardado_y_historia_preservada(self):
        """§14: guardar no borra la historia; el CURRENT apunta al último."""
        from sanctions.contracts import SanctionsSnapshot
        from sanctions.snapshots import SnapshotStore, snapshot_id
        base = TMP / "historia"
        store = SnapshotStore(cache_dir=str(base))
        for sha in ("aaa", "bbb", "ccc"):
            store.guardar(SanctionsSnapshot(
                snapshot_id=snapshot_id("OFAC_SDN", sha), source_id="OFAC_SDN",
                authority="OFAC", retrieved_at="2026-09-01T00:00:00Z", sha256=sha,
                record_count=1), [{"id": "x", "nombre": "X"}])
        hist = store.historial("OFAC_SDN")
        self.assertEqual(len(hist), 3)                      # historia completa
        self.assertEqual(store.current_sha("OFAC_SDN"), "ccc")   # puntero vigente
        # Y se puede reproducir un dictamen viejo contra el snapshot viejo.
        assert store.cargar("OFAC_SDN", "aaa") is not None

    def test_cache_no_dice_en_vivo(self):
        """§16/§34: snapshot del store -> 'snapshot oficial versionado', NUNCA 'en vivo'."""
        from sanctions.acquire import es_en_vivo, es_cache, adquirir_fuente
        store = _sembrar_snapshots(TMP / "cache_dice")
        snap, regs = adquirir_fuente("UN_CONSOLIDATED", store=store,
                                     permitir_descarga=False)
        self.assertEqual(snap.freshness, "CACHED_FRESH")
        self.assertFalse(es_en_vivo(snap))
        self.assertTrue(es_cache(snap))
        from sanctions.contracts import freshness_label
        self.assertIn("snapshot oficial versionado", freshness_label(snap.freshness))
        self.assertNotIn("en vivo", freshness_label(snap.freshness))

    def test_freshness_estados(self):
        from sanctions.snapshots import evaluar_frescura
        from sanctions.contracts import SanctionsSnapshot
        snap = SanctionsSnapshot(snapshot_id="s", source_id="x", authority="a",
                                 retrieved_at="2026-09-20T00:00:00Z", sha256="h")
        import datetime
        _ahora = datetime.datetime(2026, 9, 20, 6, 0, tzinfo=datetime.timezone.utc).timestamp()
        self.assertEqual(evaluar_frescura(snap, ahora=_ahora, ttl_segundos=86400),
                         "CACHED_FRESH")
        _viejo = datetime.datetime(2026, 9, 25, 0, 0, tzinfo=datetime.timezone.utc).timestamp()
        self.assertEqual(evaluar_frescura(snap, ahora=_viejo, ttl_segundos=86400,
                                          permitir_stale=True), "STALE_ALLOWED")
        self.assertEqual(evaluar_frescura(snap, ahora=_viejo, ttl_segundos=86400,
                                          permitir_stale=False), "STALE_NOT_ALLOWED")
        self.assertEqual(evaluar_frescura(None), "NO_SNAPSHOT")

    def test_offline_sin_snapshot_no_inventa(self):
        from sanctions.acquire import adquirir_fuente, fuente_disponible
        from sanctions.snapshots import SnapshotStore
        base = TMP / "vacio"
        store = SnapshotStore(cache_dir=str(base))
        snap, regs = adquirir_fuente("OFAC_SDN", store=store, permitir_descarga=False)
        self.assertEqual(regs, [])
        self.assertEqual(snap.acquisition_status, "SOURCE_UNAVAILABLE")
        self.assertFalse(fuente_disponible(snap))
        self.assertIn("offline", (snap.error or "").lower())


# ── §25/§35 — Estado global y degradación honesta ───────────────────────────

class TestEstadoGlobal(unittest.TestCase):

    def test_upstream_fresh_uk_unavailable_es_partial(self):
        """§35: ONU+OFAC disponibles y UK no -> SCREENING_PARTIAL con la causa."""
        store = _sembrar_snapshots(TMP / "partial", por_fuente={
            "UN_CONSOLIDATED": [{"id": "u1", "nombre": "NADIE PARECIDO"}],
            "OFAC_SDN": [{"id": "o1", "nombre": "NADIE PARECIDO"}],
        })
        s = _ejecutar(cache_dir=str(TMP / "partial"))
        self.assertEqual(s.status, "SCREENING_PARTIAL")
        self.assertIn("UK_SANCTIONS_LIST", s.sources_unavailable)
        self.assertIn("Sin coincidencias en las fuentes efectivamente consultadas", s.reason)
        self.assertIn("UKSL no estuvo disponible", s.reason)

    def test_completo_cuando_todas_responden(self):
        _sembrar_snapshots(TMP / "completo")
        s = _ejecutar(cache_dir=str(TMP / "completo"))
        self.assertEqual(s.status, "SCREENING_COMPLETE")
        self.assertTrue(s.executed)
        self.assertEqual(s.subjects_declared, 3)
        self.assertEqual(s.subjects_screened, 3)
        self.assertEqual(s.subjects_not_screened, 0)

    def test_not_executed_sin_fuentes(self):
        _sembrar_snapshots(TMP / "nada", por_fuente={})
        s = _ejecutar(cache_dir=str(TMP / "nada"))
        self.assertEqual(s.status, "SCREENING_NOT_EXECUTED")
        self.assertFalse(s.executed)
        self.assertIn("ninguna fuente oficial", s.reason)

    def test_review_required_con_candidato(self):
        store = _sembrar_snapshots(TMP / "review", por_fuente={
            "UN_CONSOLIDATED": [{"id": "u1", "nombre": "DURAN BACCA ALISON",
                                 "alias": [], "tipo_documento": None,
                                 "numero_documento": None}],
            "OFAC_SDN": [{"id": "o1", "nombre": "NADIE PARECIDO"}],
            "UK_SANCTIONS_LIST": [{"id": "k1", "nombre": "NADIE PARECIDO"}],
        })
        s = _ejecutar(cache_dir=str(TMP / "review"))
        self.assertEqual(s.status, "SCREENING_REVIEW_REQUIRED")
        self.assertTrue(s.review_required_subjects)
        self.assertFalse(s.matched_subjects)   # un candidato NO es una coincidencia

    def test_coincidencia_por_documento_marca_matched(self):
        store = _sembrar_snapshots(TMP / "match", por_fuente={
            "UN_CONSOLIDATED": [{"id": "u1", "nombre": "DURAN BACCA ALISSON",
                                 "alias": [], "tipo_documento": "cc",
                                 "numero_documento": "1045718995X"}],
            "OFAC_SDN": [{"id": "o1", "nombre": "NADIE PARECIDO"}],
            "UK_SANCTIONS_LIST": [{"id": "k1", "nombre": "NADIE PARECIDO"}],
        })
        s = _ejecutar(cache_dir=str(TMP / "match"))
        self.assertTrue(s.matched_subjects)
        self.assertEqual(s.status, "SCREENING_REVIEW_REQUIRED")
        _o = next(o for o in s.outcomes
                  if o.source_id == "UN_CONSOLIDATED"
                  and o.subject_id.startswith("titular"))
        self.assertEqual(_o.result, "EXACT_MATCH")

    def test_snapshot_por_fuente_en_no_match(self):
        """§41.I: cada NO MATCH tiene fuente + snapshot + hash."""
        _sembrar_snapshots(TMP / "trazable")
        s = _ejecutar(cache_dir=str(TMP / "trazable"))
        for o in s.outcomes:
            if o.result == "NO_MATCH":
                self.assertTrue(o.source_id)
                self.assertTrue(o.snapshot_sha256)
                self.assertTrue(o.snapshot_effective_date)
                snap = s.snapshot(o.source_id)
                self.assertIsNotNone(snap)
                self.assertEqual(snap.record_count > 0, True)

    def test_cobertura_completa_vs_revision(self):
        """Cobertura completa (todas las fuentes consultadas) != sin revisión.

        Un candidato exige revisión humana pero NO deja el screening "incompleto":
        antes eso producía un PREANALISIS_INCOMPLETO engañoso.
        """
        _sembrar_snapshots(TMP / "cobertura", por_fuente={
            "UN_CONSOLIDATED": [{"id": "u1", "nombre": "DURAN BACCA ALISON",
                                 "alias": [], "tipo_documento": None,
                                 "numero_documento": None}],
            "OFAC_SDN": [{"id": "o1", "nombre": "NADIE PARECIDO"}],
            "UK_SANCTIONS_LIST": [{"id": "k1", "nombre": "NADIE PARECIDO"}],
        })
        s = _ejecutar(cache_dir=str(TMP / "cobertura"))
        self.assertEqual(s.status, "SCREENING_REVIEW_REQUIRED")
        self.assertFalse(s.completo)
        self.assertTrue(s.cobertura_completa)

    def test_receipts_consumen_el_mismo_resumen(self):
        """§38: el receipt técnico reporta el mismo estado que los capítulos."""
        from receipts import _screening_receipt
        _sembrar_snapshots(TMP / "receipt")
        s = _ejecutar(cache_dir=str(TMP / "receipt"))
        r = _screening_receipt({"screening_summary": s.to_dict(),
                                "screening_agregado": "sinCoincidencia"})
        self.assertEqual(r["status"], s.status)
        self.assertEqual(r["etiqueta"], s.etiqueta)
        self.assertEqual(r["sujetos_screeningados"], s.subjects_screened)
        self.assertEqual([f["source_id"] for f in r["fuentes"]], list(s.sources))
        self.assertTrue(all(f["sha256"] for f in r["fuentes"]))


# ── §20/§21 — Evidencia y semántica de hashes ───────────────────────────────

class TestEvidencia(unittest.TestCase):

    def test_envelope_de_evidencia_completo(self):
        from sanctions.contracts import SourceOutcome
        from sanctions.evidence import build_evidence
        from sanctions.subjects import build_subject_envelopes
        env = build_subject_envelopes(_ANALYSIS, {})[0]
        out = SourceOutcome(subject_id=env.subject_id, source_id="UN_CONSOLIDATED",
                            result="NO_MATCH", snapshot_sha256="abc123",
                            snapshot_effective_date="2026-09-19")
        rec = build_evidence(env, out)
        d = rec.to_dict()
        for k in ("evidence_id", "subject_id", "canonical_name", "document_type",
                  "document_number_masked", "source_id", "snapshot_sha256",
                  "snapshot_effective_date", "query_hash", "screened_at",
                  "algorithm_version", "result", "score", "matched_record_ids",
                  "matching_reasons", "review_status"):
            self.assertIn(k, d)
        # El documento va ENMASCARADO en la evidencia.
        self.assertNotIn("1045718995X", d["document_number_masked"])
        self.assertIn("*", d["document_number_masked"])

    def test_hashes_distintos_y_semantica_declarada(self):
        from sanctions.contracts import SourceOutcome
        from sanctions.evidence import (build_evidence, SEMANTICA_HASH,
                                        subject_hash, query_hash)
        from sanctions.subjects import build_subject_envelopes
        env = build_subject_envelopes(_ANALYSIS, {})[0]
        out = SourceOutcome(subject_id=env.subject_id, source_id="OFAC_SDN",
                            result="NO_MATCH", snapshot_sha256="snap-sha")
        rec = build_evidence(env, out)
        self.assertNotEqual(rec.subject_hash, rec.query_hash)
        self.assertNotEqual(rec.query_hash, rec.evidence_hash)
        # El snapshot_hash es el de la fuente, no el del sujeto.
        self.assertEqual(rec.snapshot_sha256, "snap-sha")
        self.assertIn("NO que la información de origen sea verdadera", SEMANTICA_HASH)
        # La semántica se declara en el PDF (no se afirma "los nombres no se alteran").
        self.assertNotIn("los nombres no se alteren", SEMANTICA_HASH)


# ── §12/§37 — Aislamiento de datos de demostración ─────────────────────────

class TestDemoIsolation(unittest.TestCase):
    """§37: los registros de muestra no pueden llegar al dictamen productivo."""

    _IDS = ("uiaf-001", "ue-001", "pep-001", "int-001")

    def test_ids_demo_no_estan_en_el_codigo_productivo(self):
        hallazgos = []
        for p in API.rglob("*.py"):
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:  # noqa: BLE001
                continue
            for i in self._IDS:
                if i in txt:
                    hallazgos.append(f"{p.name}:{i}")
        self.assertEqual(hallazgos, [], f"registros de demostración en api/: {hallazgos}")

    def test_fixture_esta_fuera_de_api(self):
        datos = json.loads((FIXTURES / "muestras_sinteticas.json").read_text(encoding="utf-8"))
        self.assertIn("SYNTHETIC_TEST_FIXTURE", datos["_aviso"])
        ids = [r["id"] for regs in datos["fuentes"].values() for r in regs]
        for i in self._IDS:
            self.assertIn(i, ids)

    def test_fuentes_productivas_no_incluyen_muestras(self):
        from sanctions.registry import screening_sources
        ids = {s.source_id for s in screening_sources()}
        for prohibido in ("UIAF_SIREL", "PEP_COLOMBIA", "UK_OFSI_CONLIST_HISTORICAL"):
            self.assertNotIn(prohibido, ids)

    def test_ingest_no_tiene_muestras(self):
        from arhia_sag_screen.ingest.sources import FUENTES
        for clave, cat in FUENTES.items():
            self.assertNotIn("muestra", cat, f"{clave} conserva registros de muestra")


# ── §22/§23/§32/§38/§41 — Dictamen ──────────────────────────────────────────

def _compilar_con_screening(tmp_name="pdf_03s1.pdf", *, store_base=None,
                            por_fuente=None, todos_caidos=False, **fuentes_kw):
    """Compila el Golden (con CTL adjunto y sujetos reales) y screening sembrado.

    Sin red: las capas del catastro/POT y las fuentes de sanciones se sustituyen
    por fixtures. El screening corre contra SNAPSHOTS del store (no en vivo).
    """
    import shutil
    from io import BytesIO
    import catastro_predio
    import geocoder
    import legal_analyzer
    import pdf_compiler
    import integrations.catastro_live as catastro_live
    from legal_analyzer import analizar_certificado
    from reportlab.pdfgen import canvas
    import test_remediacion_03h2a as H

    if store_base is not None:
        os.environ["ARHIA_LISTAS_CACHE"] = str(store_base)
        if por_fuente is not None:
            _sembrar_snapshots(store_base, por_fuente=por_fuente)

    fuentes = H.FuentesMock(capa_500_resuelve=False, todo_caido=todos_caidos)
    out_dir = ROOT / "tmp_pdf_03s1"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_pdf = out_dir / tmp_name

    # CTL de prueba (el screening solo corre si hay CTL adjunto).
    buf = BytesIO()
    _c = canvas.Canvas(buf)
    _c.drawString(50, 780, "CERTIFICADO DE TRADICION Y LIBERTAD (PRUEBA)")
    _c.drawString(50, 760, "MATRICULA INMOBILIARIA: 040-646406")
    _c.drawString(50, 740, "DIRECCION: TV 43 # 100-50 TO 8 AP 430")
    _c.drawString(50, 720, "TITULAR: DURAN BACCA ALISSON CC# 1045718995X 50%")
    _c.drawString(50, 700, "ACREEDOR: BANCO DE BOGOTA S.A. NIT# 8600029644")
    _c.save()
    ctl_path = out_dir / "ctl_prueba.pdf"
    ctl_path.write_bytes(buf.getvalue())

    analysis = dict(analizar_certificado(None))
    analysis.update({
        "folio": "040-646406", "direccion": "TV 43 # 100-50 TO 8 AP 430",
        "codigo_catastral": "080010103000010040001908040002",
        "nupre": "AFT0005BOHA",
        "titulares": _ANALYSIS["titulares"],
        "acreedor_snr": _ANALYSIS["acreedor_snr"],
        "constructor": _ANALYSIS["constructor"],
        "hipoteca_vigente": dict(_ANALYSIS["hipoteca_vigente"]),
        "anotaciones_detalle": [dict(a) for a in _ANALYSIS["anotaciones_detalle"]],
        "descripcion_ctl": ("APARTAMENTO 430 TORRE 8 CONJUNTO NAPOLI MIRAMAR "
                            "PROPIEDAD HORIZONTAL"),
        "texto_ctl": "APARTAMENTO 430 - PROPIEDAD HORIZONTAL",
    })
    record = {
        "id": 1, "folio_matricula": "040-646406",
        "direccion": "TV 43 # 100-50 TO 8 AP 430", "barrio": "Miramar", "estrato": 4,
        "area": 58.75, "sombra_9am_cargada": 0, "sombra_3pm_cargada": 0,
        "mapa_cargado": 0, "acreedor_real": None,
        "certificado_path": str(ctl_path), "ciudad": "barranquilla",
    }
    catastro_predio._CACHE.clear()
    with mock.patch.object(legal_analyzer, "analizar_certificado",
                           return_value=analysis), \
            mock.patch.object(catastro_predio, "_query_capa",
                              side_effect=fuentes.query_capa), \
            mock.patch.object(catastro_predio, "_query_punto",
                              side_effect=fuentes.query_punto), \
            mock.patch.object(geocoder, "geocodificar_direccion",
                              lambda d, ciudad=None: (10.9870, -74.8115)), \
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


def _texto(pdf_bytes):
    import io as _io
    import pypdf
    r = pypdf.PdfReader(_io.BytesIO(pdf_bytes))
    _t = " ".join((p.extract_text() or "") for p in r.pages).lower()
    # Las celdas del PDF parten las frases en varias lineas: se normaliza el
    # espaciado para poder afirmar sobre el TEXTO, no sobre el salto de linea.
    return re.sub(r"\s+", " ", _t)


class TestDictamenScreening(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        base = TMP / "pdf_store"
        _sembrar_snapshots(base)
        cls.store_base = base
        cls.pdf = _compilar_con_screening(store_base=base)
        cls.txt = _texto(cls.pdf)
        _i = cls.txt.find("09 - screening de contrapartes")
        cls.sec09 = cls.txt[_i:cls.txt.find("10 - hallazgos", _i)]

    def test_seccion_09_renombrada(self):
        """§22: la sección se llama screening de contrapartes, no 'cumplimiento SAGRILAFT'."""
        self.assertIn("09 - screening de contrapartes y debida diligencia", self.txt)
        self.assertIn("apoyo automatizado al proceso la/ft/sagrilaft", self.txt)
        self.assertNotIn("09 - cumplimiento sagrilaft", self.txt)

    def test_no_hay_columna_ni_lista_uiaf(self):
        """§32/§10: ni columna UIAF en la tabla de screening ni 'lista UIAF'."""
        _cab = self.sec09[self.sec09.find("09.1 resultado"):self.sec09.find("09.2 versión")]
        self.assertNotIn("uiaf", _cab)
        self.assertNotIn("lista uiaf", self.txt)
        self.assertNotIn("screening onu/ofac/uiaf", self.txt)
        # La explicación de alcance SÍ puede nombrar UIAF/SIREL (no es lista).
        self.assertIn("no es una lista de screening", self.txt)

    def test_tabla_con_tipo_documento_y_rol(self):
        """§23: Sujeto | Tipo | Documento | Rol | fuentes | Resultado."""
        self.assertIn("documento", self.txt)
        self.assertIn("titular_actual", self.txt)
        self.assertIn("acreedor_hipotecario", self.txt)
        self.assertIn("constructor_enajenante", self.txt)

    def test_personas_con_tipo_correcto(self):
        """§41.A/B: banco jurídica, titular natural."""
        self.assertIn("banco de bogotá s.a.", self.txt)
        self.assertIn("natural", self.txt)
        self.assertIn("jurídica", self.txt)

    def test_constructor_no_desaparece(self):
        """§41.C"""
        self.assertIn("urbanizadora marin valencia", self.txt)

    def test_documentos_extraidos(self):
        """§41.D"""
        self.assertIn("1045718995x", self.txt)
        self.assertIn("8600029644", self.txt)

    def test_fuente_y_version_trazables(self):
        """§41.I: cada resultado trae fuente, versión (hash) y fecha efectiva."""
        self.assertIn("uk_sanctions_list", self.txt)
        self.assertIn("ofac_sdn", self.txt)
        self.assertIn("un_consolidated", self.txt)
        self.assertIn("2026-09-19", self.txt)     # fecha efectiva del snapshot
        self.assertIn("fixture-", self.txt)       # sha256 truncado del snapshot

    def test_no_dice_en_vivo_con_snapshot(self):
        """§41.G/§34: con snapshots sembrados NO puede afirmar 'en vivo'."""
        _i = self.txt.find("09 - screening de contrapartes")
        _sec09 = self.txt[_i:self.txt.find("10 - hallazgos", _i)]
        self.assertNotIn("en vivo", _sec09)
        self.assertIn("snapshot oficial versionado", _sec09)

    def test_estado_cross_chapter_coherente(self):
        """§38/§25: 09, 16 y 16.b reportan el MISMO estado."""
        self.assertIn("screening completo", self.txt)
        _i16 = self.txt.find("16 - declaraci")
        _sec16 = self.txt[_i16:]
        # 16 declara el MISMO estado que el 09 (antes decia "NO EJECUTADA" fijo).
        self.assertIn("screening de contrapartes ejecutado", _sec16)
        self.assertNotIn("screening de contrapartes no ejecutado", _sec16)
        # 16.b (receipts) con el mismo estado
        self.assertIn("screening de contrapartes completo", self.txt)

    def test_semantica_de_hash_declarada(self):
        """§21: el dictamen precisa qué sella cada hash y qué NO prueba."""
        self.assertIn("sella un artefacto", self.txt)
        self.assertIn("no prueba que la información de origen", self.txt)
        self.assertNotIn("garantiza que los nombres no se alteren", self.txt)

    def test_algoritmo_declarado(self):
        self.assertIn("sanctions-matcher", self.txt)

    def test_sin_numerales_no_verificados(self):
        """§27: no se imprimen numerales de la CBJ sin verificar."""
        for num in ("9.17", "9.22", "9.15.1", "9.14.1", "9.19", "9.20"):
            self.assertNotIn(num, self.txt, f"numeral no verificado impreso: {num}")


class TestDictamenConCoincidencia(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        base = TMP / "pdf_match_store"
        _sembrar_snapshots(base, por_fuente={
            "UN_CONSOLIDATED": [{"id": "u1", "nombre": "DURAN BACCA ALISSON",
                                 "alias": [], "tipo_documento": "cc",
                                 "numero_documento": "1045718995X",
                                 "fecha_nacimiento": None}],
            "OFAC_SDN": [{"id": "o1", "nombre": "NADIE PARECIDO"}],
            "UK_SANCTIONS_LIST": [{"id": "k1", "nombre": "NADIE PARECIDO"}],
        })
        cls.txt = _texto(_compilar_con_screening(tmp_name="pdf_match.pdf",
                                                 store_base=base))

    def test_coincidencia_se_reporta_sin_acusar(self):
        _i = self.txt.find("09 - screening de contrapartes")
        _sec09 = self.txt[_i:self.txt.find("10 - hallazgos", _i)]
        self.assertIn("coincidencia en listas de sanciones", _sec09)
        self.assertIn("no califica a la persona", _sec09)
        self.assertIn("revisión humana", _sec09)

    def test_resultado_por_fuente_distingue_match_y_no_match(self):
        _i = self.txt.find("09 - screening de contrapartes")
        _sec09 = self.txt[_i:self.txt.find("10 - hallazgos", _i)]
        self.assertIn("match", _sec09)
        self.assertIn("no match", _sec09)
        self.assertIn("snapshot oficial versionado", _sec09)


class TestDictamenSinFuentes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        base = TMP / "pdf_vacio_store"
        _sembrar_snapshots(base, por_fuente={})
        cls.txt = _texto(_compilar_con_screening(tmp_name="pdf_vacio.pdf",
                                                 store_base=base))

    def test_screening_no_ejecutado_declarado(self):
        """§41: sin fuentes, el dictamen NO afirma nada y lo declara."""
        self.assertIn("no ejecutado", self.txt)
        self.assertNotIn("sin coincidencias en las fuentes", self.txt)


if __name__ == "__main__":
    unittest.main()
