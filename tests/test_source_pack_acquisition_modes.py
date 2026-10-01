# -*- coding: utf-8 -*-
"""MODOS DE ADQUISICIÓN — pruebas BLOQUEANTES (offline, deterministas).

Cubren, sin red y sin reloj, la separación explícita de los DOS estados del pack:

  · **CONTRACT_FROZEN** — `product_role` y `acquisition_mode` en CADA fuente del registro,
    snapshots REALES descubiertos con su sha256/fecha/bytes, frescura declarada por familia,
    matriz de 11 columnas CALCULADA, licencias y precedencia intactas.
  · **OPERATIONAL_READY** — E2E de los dominios CORE con datos reales: solo dirección y solo
    matrícula alcanzan la MISMA `CanonicalPropertyIdentity`; la escalera INTENTA LIVE y cae a
    SNAPSHOT cuando procede, conservando la `authority_class` ORIGINAL.

Negativos cubiertos: predio vecino que jamás liga la identidad del Golden, `SOURCE_UNAVAILABLE`
que nunca se convierte en `NO_MATCH`, snapshot VENCIDO que no resuelve, artefacto de prueba o
sonda de vecindad que se declara NO utilizable y caso no-PH declarado.

Reproducibilidad: dos corridas con las MISMAS respuestas crudas producen los MISMOS payloads
normalizados, los MISMOS bindings, la MISMA precedencia y los MISMOS `content_hash`;
`queried_at`/`run_id` quedan FUERA de todo hash de contenido. La ventana de frescura se ancla
en la fecha de CAPTURA que el propio artefacto declara (nunca en la fecha de commit/mtime, que
es un hecho del empaquetado): un artefacto congelado no puede llevar un valor derivado de
cuándo se empaquetó (`TestFrescura` y `TestMatrizDeRoles` lo bloquean).

Nada se modifica en disco: las pruebas leen el registro, la matriz y el inventario versionados.
"""
import csv
import importlib.util
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import acquisition as acq  # noqa: E402
import dictus_sources as ds  # noqa: E402
import source_resolution as sr  # noqa: E402

DIR_PACK = ROOT / "docs" / "source_pack"
RUTA_REGISTRO = DIR_PACK / "barranquilla_sources_v1.json"
RUTA_REGISTRO_YAML = DIR_PACK / "barranquilla_sources_v1.yaml"
RUTA_MANIFEST = DIR_PACK / "BARRANQUILLA_SOURCE_PACK_MANIFEST.json"
RUTA_MATRIZ = DIR_PACK / "SOURCE_ACQUISITION_MATRIX_040-646406.csv"
RUTA_INVENTARIO = DIR_PACK / "SNAPSHOT_INVENTORY.json"
RUTA_PROBE_GEOPORTAL = DIR_PACK / "raw" / "golden" / "_layers_probe.json"
RUTA_RUN_STATE = (ROOT / "docs" / "forensics" / "040-646406" / "dictus_2b"
                  / "DICTUS_RUN_STATE_040-646406.json")
RUTA_CAPTURA_OSM = DIR_PACK / "raw" / "golden" / "osm_overpass.json"

COLUMNAS_MATRIZ = ("domain", "source_id", "product_role", "status", "binding",
                   "normalized_result", "authority", "provenance", "raw_hash",
                   "required_for_decision", "blocking_if_missing")

# Frases que delatarían que la adquisición le pide el dato a una PERSONA.
FRASES_PROHIBIDAS = ("solicitar al usuario", "requiere que el usuario", "pedir al usuario",
                     "pendiente de aporte", "complete la informaci", "ingrese la direccion",
                     "ingrese la dirección", "intervención manual", "intervencion manual",
                     "aporte el folio", "aporte la direccion", "aporte la dirección")


# ══════════════════════════════════════════════════════════════════════════════
# Utilidades de la prueba
# ══════════════════════════════════════════════════════════════════════════════
def _resultado(sid, status, *, payload=None, queried_at=""):
    """`SourceResult` determinista (sin reloj ni red)."""
    return ds.resultado(sid, status, payload_normalized=payload, queried_at=queried_at,
                        provenance={"source_id": sid})


def _live_105_documentado(golden):
    """Respuesta EN VIVO de la capa 105 para el Golden, tal como la documenta el run state.

    No se inventa nada: los campos salen de `market_context.coordinate_provenance`
    (`numero_predial`, `nupre`, `direccion_origen`, `feature_id`) y la coordenada de
    `market_context.coordinates`, que esa misma procedencia declara como geometría del
    predio en la capa 105. La prueba es offline: es la REPLA de una respuesta congelada.
    """
    prov = dict(golden.get("coordinate_provenance") or {})
    payload = {
        "direccion": prov.get("direccion_origen"),
        "numero_predial": prov.get("numero_predial"),
        "numero_predial_nacional": prov.get("numero_predial"),
        "codigo_homologado": prov.get("nupre"),
        "nupre": prov.get("nupre"),
        "cr_predio_guid": prov.get("feature_id"),
        "globalid": prov.get("predio_globalid"),
        "es_direccion_principal": True,
        "tipo_direccion": "PRINCIPAL",
        "lat": golden.get("lat"),
        "lon": golden.get("lon"),
    }
    return {"CATASTRO_BAQ_DIRECCION": ds.resultado(
        "CATASTRO_BAQ_DIRECCION", ds.DISPONIBLE, payload_normalized=payload,
        queried_at=golden.get("generated_at") or "",
        provenance={"source_id": "CATASTRO_BAQ_DIRECCION",
                    "source_name": "Dirección oficial (nomenclatura del predio)",
                    "authority_class": ds.AUTORITATIVA_OFICIAL,
                    "layer_id": 105,
                    "acquisition_mode": acq.LIVE_QUERY,
                    "evidencia": "market_context.coordinate_provenance del run state"})}


def _contexto_golden(golden):
    return {
        "punto": {"lat": golden.get("lat"), "lon": golden.get("lon")},
        "lat": golden.get("lat"),
        "lon": golden.get("lon"),
        "identificadores": {
            "numero_predial": golden.get("numero_predial"),
            "codigo_homologado": golden.get("nupre"),
            "fmi": acq.partes_del_folio(golden.get("folio")).get("fmi"),
            "barrio": golden.get("barrio"),
        },
        "barrio": golden.get("barrio"),
        "fecha": golden.get("fecha"),
    }


class BaseAdquisicion(unittest.TestCase):
    """Registro, inventario y Golden reales, leídos una sola vez."""

    @classmethod
    def setUpClass(cls):
        cls.reg = ds.cargar_registro()
        if cls.reg.get("_status") == ds.NO_SOPORTADA:
            raise unittest.SkipTest("el registro del Source Pack aún no está generado")
        cls.fuentes = cls.reg["sources"]
        cls.inv = acq.descubrir_snapshots()
        cls.ref = acq.fecha_de_referencia(cls.reg)
        cls.golden = acq.leer_golden()
        cls.contexto = _contexto_golden(cls.golden)
        cls.modos = acq.modos_por_fuente(cls.reg, fecha=cls.ref, inventario=cls.inv)
        cls.filas = acq.matriz_roles(registro=cls.reg, fecha=cls.ref, contexto=cls.contexto,
                                     inventario=cls.inv, golden=cls.golden)
        cls.consultas_congeladas = acq.consultas_de_la_corrida_congelada(
            cls.reg, fecha=cls.ref, contexto=cls.contexto)

    def _fila(self, dominio):
        for f in self.filas:
            if f["domain"] == dominio:
                return f
        self.fail(f"la matriz no declara el dominio {dominio}")

    def _en_registro(self, sid):
        """¿La fuente está en el registro VIGENTE? (el pack puede retirarla y declararlo)."""
        return sid in self.fuentes

    def _modo(self, sid):
        self.assertTrue(self._en_registro(sid),
                        f"{sid} no está en el registro vigente: la prueba del snapshot "
                        f"correspondiente se resuelve por el estado declarado del pack")
        return self.modos[sid]


# ══════════════════════════════════════════════════════════════════════════════
# 1 · VOCABULARIOS CERRADOS
# ══════════════════════════════════════════════════════════════════════════════
class TestVocabulariosCerrados(BaseAdquisicion):

    def test_los_tres_modos_de_adquisicion_son_un_vocabulario_cerrado(self):
        self.assertEqual(acq.ACQUISITION_MODES,
                         ("LIVE_QUERY", "AUTOMATED_SNAPSHOT", "AUTHORIZED_FALLBACK"))
        self.assertEqual(len(set(acq.ACQUISITION_MODES)), 3)
        for sid, m in self.modos.items():
            self.assertIn(m["acquisition_mode"], acq.ACQUISITION_MODES, sid)

    def test_los_seis_roles_de_producto_son_un_vocabulario_cerrado(self):
        self.assertEqual(acq.PRODUCT_ROLES,
                         ("CORE_IDENTITY", "CORE_NORMATIVE", "CORE_RISK", "CORE_MARKET",
                          "DECISION_CONTEXT", "OPTIONAL_ENRICHMENT"))
        for sid in self.fuentes:
            self.assertIn(acq.rol_de_fuente(sid), acq.PRODUCT_ROLES, sid)

    def test_toda_fuente_del_registro_tiene_rol_y_modo_declarados(self):
        """§B: `product_role` y `acquisition_mode` en CADA fuente del registro versionado."""
        for sid, f in self.fuentes.items():
            self.assertIn("product_role", f, f"{sid} sin product_role sellado")
            self.assertIn("acquisition_mode", f, f"{sid} sin acquisition_mode sellado")
            self.assertIn("acquisition_snapshot", f, f"{sid} sin bloque de snapshot")
            self.assertIn(f["product_role"], acq.PRODUCT_ROLES, sid)
            self.assertIn(f["acquisition_mode"], acq.ACQUISITION_MODES, sid)
            self.assertEqual(f["product_role"], acq.rol_de_fuente(sid), sid)
            self.assertEqual(f["acquisition_mode"],
                             acq.modo_declarado_de_fuente(sid, f), sid)

    def test_los_roles_core_estan_poblados(self):
        por_rol = {}
        for sid in self.fuentes:
            por_rol.setdefault(acq.rol_de_fuente(sid), []).append(sid)
        for rol in acq.ROLES_CORE:
            if rol == acq.CORE_MARKET and not por_rol.get(rol):
                # El pack puede RETIRAR una fuente y declararlo: entonces el dominio de
                # mercado queda sin fuente registrada y así debe declararse, sin inventar.
                self.assertNotIn("LONJA_MARKET_BAQ", self.fuentes)
                fila = self._fila("mercado")
                self.assertEqual(fila["product_role"], acq.CORE_MARKET)
                self.assertNotEqual(fila["status"], ds.DISPONIBLE)
                self.assertIn("registro", fila["provenance"] + fila["normalized_result"])
                continue
            self.assertTrue(por_rol.get(rol), f"ninguna fuente declara el rol {rol}")
        if por_rol.get(acq.CORE_IDENTITY):
            self.assertIn("CATASTRO_BAQ_ADOPCION_ANEXO1", por_rol[acq.CORE_IDENTITY])
        if por_rol.get(acq.CORE_NORMATIVE):
            self.assertIn("POT_BAQ_TRATAMIENTO", por_rol[acq.CORE_NORMATIVE])
        if por_rol.get(acq.CORE_RISK):
            self.assertIn("POT_BAQ_REMOCION_2024", por_rol[acq.CORE_RISK])

    def test_requisitos_derivados_del_rol_no_se_inventan(self):
        for rol in acq.ROLES_CORE:
            req = acq.requisitos_de_rol(rol)
            self.assertTrue(req["required_for_decision"], rol)
            self.assertTrue(req["blocking_if_missing"], rol)
        self.assertEqual(acq.requisitos_de_rol(acq.DECISION_CONTEXT),
                         {"required_for_decision": True, "blocking_if_missing": False})
        self.assertEqual(acq.requisitos_de_rol(acq.OPTIONAL_ENRICHMENT),
                         {"required_for_decision": False, "blocking_if_missing": False})

    def test_una_capa_historica_nunca_es_requerida_ni_bloqueante(self):
        """`precedence=HISTORICAL_REFERENCE` ⇒ es REFERENCIA, aunque su familia sea CORE."""
        historic = [sid for sid, f in self.fuentes.items()
                    if f.get("precedence") == ds.HISTORICAL_REFERENCE]
        self.assertTrue(historic, "el pack debe declarar capas históricas")
        for sid in historic:
            req = acq.requisitos_de_rol(acq.rol_de_fuente(sid),
                                        precedence=ds.HISTORICAL_REFERENCE)
            self.assertEqual(req, {"required_for_decision": False,
                                   "blocking_if_missing": False}, sid)

    def test_freshness_default_por_familia_declarada(self):
        for familia, politica in acq.FRESHNESS_DEFAULT.items():
            self.assertIsInstance(politica["dias"], int, familia)
            self.assertGreater(politica["dias"], 0, familia)
            self.assertTrue(politica["fundamento"].strip(), familia)
        for sid in self.fuentes:
            fam = acq.familia_de_fuente(sid)
            self.assertIn(fam, acq.FRESHNESS_DEFAULT, sid)
            self.assertEqual(acq.freshness_de_fuente(sid)["familia"], fam)

    def test_una_fuente_sin_familia_o_sin_rol_falla_en_vez_de_adivinar(self):
        with self.assertRaises(KeyError):
            acq.familia_de_fuente("FUENTE_INEXISTENTE_XYZ")
        with self.assertRaises(KeyError):
            acq.rol_de_fuente("FUENTE_INEXISTENTE_XYZ")


# ══════════════════════════════════════════════════════════════════════════════
# 2 · SNAPSHOTS REALES DEL REPOSITORIO
# ══════════════════════════════════════════════════════════════════════════════
class TestSnapshotsReales(BaseAdquisicion):

    def test_el_inventario_cubre_todos_los_artefactos_escaneados(self):
        self.assertGreaterEqual(len(self.inv), 6)
        declarados = [s for s in self.inv if s["declarado"]]
        self.assertEqual(len(declarados), len(acq.SNAPSHOTS_DECLARADOS))
        no_declarados = [s for s in self.inv if not s["declarado"]]
        self.assertTrue(no_declarados, "el inventario debe declarar lo hallado y no declarado")
        for s in no_declarados:
            self.assertFalse(s["usable"])
            self.assertTrue(s["motivo_no_usable"])
            self.assertIn("NO declarado", s["motivo_no_usable"])

    def test_cada_snapshot_declarado_tiene_sha256_bytes_y_fecha_REALES(self):
        for s in self.inv:
            if not s["declarado"]:
                continue
            ruta = ROOT / s["ruta"]
            self.assertTrue(ruta.exists(), f"no existe el snapshot {s['ruta']}")
            self.assertEqual(s["sha256"], acq.hash_archivo(ruta), s["ruta"])
            self.assertEqual(len(s["sha256"]), 64, s["ruta"])
            self.assertEqual(s["bytes"], ruta.stat().st_size, s["ruta"])
            self.assertIn(s["fecha_origen"], ("git_commit", "mtime_sin_commit"), s["ruta"])
            self.assertTrue(s["fecha_de_creacion"], s["ruta"])

    def test_los_snapshots_declarados_citan_su_respaldo_en_el_registro(self):
        """Ningún snapshot se usa sin respaldo declarado por el propio registro."""
        for s in self.inv:
            if not (s["declarado"] and s["usable"]):
                continue
            for sid in s["fuentes"]:
                if not self._en_registro(sid):
                    # El pack puede RETIRAR una fuente de `sources`: entonces debe declararlo.
                    texto = json.dumps(self.reg, ensure_ascii=False)
                    self.assertIn(sid, texto,
                                  f"{sid} desapareció del registro sin declararlo")
                    self.assertIn("no_fuentes_institucionales", texto)
                    continue
                f = self.fuentes[sid]
                respaldo = (str(f.get("local_fallback") or ""),
                            str(f.get("base_url") or ""))
                self.assertTrue(
                    any(s["ruta"] in r or r.startswith("local:") for r in respaldo),
                    f"el snapshot {s['ruta']} no está respaldado por {sid}: {respaldo}")

    def test_el_fixture_de_prueba_nunca_es_un_snapshot_utilizable(self):
        """`catastro_baq_predio.json` es un artefacto de PRUEBA: usarlo sería fabricar dato."""
        fixture = next(s for s in self.inv
                       if s["ruta"].endswith("catastro_baq_predio.json"))
        self.assertFalse(fixture["usable"])
        self.assertEqual(fixture["kind"], "TEST_FIXTURE")
        self.assertIn("ARTEFACTO_DE_PRUEBA", fixture["origen_declarado"])
        self.assertIn("fabricar", fixture["motivo_no_usable"])
        self.assertEqual(self.modos["CATASTRO_BAQ_PREDIO"]["snapshots_usables"], [])
        descartados = [d["ruta"] for d in
                       self.modos["CATASTRO_BAQ_PREDIO"]["snapshots_descartados"]]
        self.assertIn("docs/source_pack/raw/golden/catastro_baq_predio.json", descartados)

    def test_la_sonda_de_estrato_no_sirve_porque_seria_inferencia_de_vecindad(self):
        sonda = next(s for s in self.inv if s["kind"] == "PROBE_TRACE")
        self.assertFalse(sonda["usable"])
        self.assertEqual(sonda["atributos"], [])
        self.assertIn("BUFFER", sonda["motivo_no_usable"])
        self.assertIn("ESPACIAL", sonda["motivo_no_usable"].upper())
        self.assertEqual(self.modos["POT_BAQ_ESTRATIFICACION"]["snapshots_usables"], [])

    def test_snapshot_para_atributo_sin_snapshot_devuelve_lista_vacia(self):
        for atributo in ("uso_pot", "tratamiento", "edificabilidad_altura_normativa",
                         "inundacion", "direccion_predio"):
            self.assertEqual(acq.snapshot_para(atributo, registro=self.reg,
                                               fecha=self.ref, inventario=self.inv), [],
                             f"{atributo} no debe tener snapshot declarado")

    def test_snapshot_para_atributo_cubierto_declara_su_artefacto(self):
        remocion = acq.snapshot_para("remocion", registro=self.reg, fecha=self.ref,
                                     inventario=self.inv)
        self.assertEqual([s["artifact_id"] for s in remocion], ["SNAP_POT_REMOCION_MASA"])
        self.assertEqual(remocion[0]["modo"], acq.AUTOMATED_SNAPSHOT)
        self.assertTrue(remocion[0]["resuelve"])
        self.assertEqual(remocion[0]["sha256"],
                         acq.hash_archivo(ROOT / remocion[0]["ruta"]))

    def test_el_inventario_versionado_coincide_con_el_calculado(self):
        self.assertTrue(RUTA_INVENTARIO.exists(), "debe existir SNAPSHOT_INVENTORY.json")
        en_disco = json.loads(RUTA_INVENTARIO.read_text(encoding="utf-8"))
        self.assertEqual(en_disco["reference_date"], self.ref)
        calculado = acq.inventario_snapshots(registro=self.reg)
        self.assertEqual([s["ruta"] for s in en_disco["snapshots"]],
                         [s["ruta"] for s in calculado["snapshots"]])
        for a, b in zip(en_disco["snapshots"], calculado["snapshots"]):
            self.assertEqual(a["sha256"], b["sha256"], a["ruta"])
            self.assertEqual(a["usable"], b["usable"], a["ruta"])
            self.assertEqual(a["atributos"], b["atributos"], a["ruta"])

    def test_las_huellas_selladas_en_el_registro_son_las_de_los_archivos(self):
        for sid, f in self.fuentes.items():
            snap = f.get("acquisition_snapshot")
            if not snap:
                continue
            self.assertEqual(snap["sha256"], acq.hash_archivo(ROOT / snap["ruta"]), sid)
            self.assertEqual(snap["bytes"], (ROOT / snap["ruta"]).stat().st_size, sid)
            self.assertIn(snap["modo"], acq.ACQUISITION_MODES, sid)
            self.assertTrue(snap["atributos"], sid)


# ══════════════════════════════════════════════════════════════════════════════
# 3 · FRESCURA: UN SNAPSHOT VENCIDO NO RESUELVE
# ══════════════════════════════════════════════════════════════════════════════
class TestFrescura(BaseAdquisicion):

    def _snap(self, artifact_id):
        return next(s for s in self.inv if s["artifact_id"] == artifact_id)

    def test_snapshot_vigente_calcula_limite_por_familia(self):
        vig = acq.evaluar_vigencia(self._snap("SNAP_ADOPCION_CATASTRL_ANEXO1")
                                   if False else self._snap("SNAP_ADOPCION_CATASTRAL_ANEXO1"),
                                   self.ref, registro=self.reg)
        self.assertEqual(vig["estado"], acq.SNAPSHOT_VIGENTE)
        self.assertEqual(vig["familia"], "CATASTRO")
        self.assertEqual(vig["restriccion_dias"], acq.FRESHNESS_DEFAULT["CATASTRO"]["dias"])
        self.assertEqual(vig["limite"], "2026-12-19")
        self.assertGreater(vig["dias_restantes"], 0)

    def test_la_frescura_de_las_capas_de_riesgo_es_la_declarada_para_su_familia(self):
        vig = acq.evaluar_vigencia(self._snap("SNAP_POT_REMOCION_MASA"), self.ref,
                                   registro=self.reg)
        self.assertEqual(vig["estado"], acq.SNAPSHOT_VIGENTE)
        self.assertEqual(vig["familia"], "RIESGO")
        self.assertEqual(vig["limite"], "2027-09-01")

    def test_el_snapshot_de_la_lonja_esta_vencido_por_su_propia_vigencia(self):
        """La metodología declara vigencia hasta 2026-08-31: NO puede resolver el mercado."""
        vig = acq.evaluar_vigencia(self._snap("SNAP_LONJA_METODOLOGIA"), self.ref,
                                   registro=self.reg)
        self.assertEqual(vig["estado"], acq.SNAPSHOT_VENCIDO)
        self.assertEqual(vig["limite"], "2026-08-31")
        self.assertEqual(vig["limite_por_artefacto"], "2026-08-31")
        self.assertIn("VENCIDO", vig["motivo"])
        self.assertLess(vig["dias_restantes"], 0)
        if self._en_registro("LONJA_MARKET_BAQ"):
            self.assertEqual(self._modo("LONJA_MARKET_BAQ")["snapshots_usables"], [])

    def test_un_snapshot_vencido_no_resuelve_y_la_escalera_sigue(self):
        r = acq.resolver_con_acquisition_mode("mercado", consultas={}, registro=self.reg,
                                              fecha=self.ref, contexto=self.contexto,
                                              inventario=self.inv)
        self.assertIsNone(r["value"])
        self.assertNotEqual(r["resolution_status"], ds.SIN_COINCIDENCIA)
        self.assertEqual(acq.provenance_adquisicion(r), {})
        if not self._en_registro("LONJA_MARKET_BAQ"):
            # El pack retiró la fuente del registro: la ausencia se declara, no se maquilla.
            self.assertNotEqual(r["resolution_status"], sr.RESOLVED_PRIMARY)
            self.assertNotEqual(r["resolution_status"], sr.RESOLVED_FALLBACK)
            self.assertTrue(r["reason"])
            return
        self.assertEqual(r["resolution_status"], sr.SOURCE_UNAVAILABLE)
        vencidos = r["acquisition"]["snapshots_vencidos"]
        self.assertEqual([v["artifact_id"] for v in vencidos], ["SNAP_LONJA_METODOLOGIA"])
        self.assertEqual(vencidos[0]["estado_vigencia"], acq.SNAPSHOT_VENCIDO)
        self.assertFalse(vencidos[0]["resolve"])
        self.assertIn("VENCIDO", vencidos[0]["motivo"])

    def test_la_regla_del_snapshot_vencido_se_prueba_con_un_caso_controlado(self):
        """Regla dura, independiente de qué fuentes tenga HOY el registro real.

        Se INYECTA un registro/cobertura/inventario declarados: la fuente existe, declara un
        snapshot AUTOMÁTICO y ese snapshot está fuera de su `freshness_policy` (creado en
        2020). Debe declararse VENCIDO y NO resolver, sin sustituir el dato por otra fuente.
        """
        reg = {"registry_version": "prueba", "sources": {"FUENTE_SNAPSHOT_VENCIDO": {
            "source_id": "FUENTE_SNAPSHOT_VENCIDO", "source_name": "Fuente de prueba",
            "institution": "Prueba", "authority_class": ds.AUTORITATIVA_OFICIAL,
            "base_url": "https://ejemplo.invalido/gis", "service": "ArcGIS REST",
            "layer_id": 1, "layer_name": "capa", "geometry_type": "esriGeometryPolygon",
            "query_method": "query", "expected_fields": ["amenaza"], "primary_keys": [],
            "binding_fields": [], "spatial_reference": "EPSG:4326",
            "legal_or_normative_context": "prueba", "version_or_vigencia": "vigente",
            "precedence": ds.CURRENT_OFFICIAL, "fallback_policy": "snapshot declarado",
            "freshness_policy": "365 días", "failure_semantics": "ausencia declarada",
            "license_or_terms": "prueba", "can_persist_raw": True, "can_embed_image": False,
            "provenance_fields": ["source_id"], "enabled": True}}}
        cobertura = {"atributo_de_prueba": {
            "semantics": "SEM", "object_key": "OBJ", "campos": ["amenaza"],
            "fuentes": {"FUENTE_SNAPSHOT_VENCIDO": {}}}}
        inventario = [{
            "artifact_id": "SNAP_DE_PRUEBA", "ruta": "api/data/amenaza_remocion_masa.geojson",
            "declarado": True, "kind": "PACKAGED_GEOJSON", "bytes": 1,
            "sha256": "0" * 64, "fecha_de_creacion": "2020-01-01T00:00:00-05:00",
            "fecha_origen": "git_commit", "modo": acq.AUTOMATED_SNAPSHOT,
            "fuentes": ["FUENTE_SNAPSHOT_VENCIDO"], "atributos": ["atributo_de_prueba"],
            "consulta": acq.CONSULTA_PUNTO_EN_POLIGONO, "campo_nivel": "niveldeamenaza",
            "campo_atributo": "amenaza", "campos_clave": [], "familia": "RIESGO",
            "freshness_dias": 365, "vigencia_declarada_en_el_artefacto": {},
            "fecha_de_captura_declarada": None, "origen_declarado": "prueba",
            "usable": True, "motivo_no_usable": ""}]
        contexto = {"punto": {"lat": self.golden["lat"], "lon": self.golden["lon"]}}
        r = acq.resolver_con_acquisition_mode(
            "atributo_de_prueba", consultas={}, registro=reg, cobertura=cobertura,
            fecha="2026-09-29", contexto=contexto, inventario=inventario)
        self.assertIsNone(r["value"])
        self.assertEqual(r["resolution_status"], sr.SOURCE_UNAVAILABLE)
        self.assertNotEqual(r["resolution_status"], ds.SIN_COINCIDENCIA)
        self.assertEqual(acq.provenance_adquisicion(r), {})
        vencidos = r["acquisition"]["snapshots_vencidos"]
        self.assertEqual([v["artifact_id"] for v in vencidos], ["SNAP_DE_PRUEBA"])
        self.assertEqual(vencidos[0]["estado_vigencia"], acq.SNAPSHOT_VENCIDO)
        self.assertEqual(vencidos[0]["limite"], "2020-12-31")
        self.assertFalse(vencidos[0]["resolve"])

    def test_la_frescura_se_ancla_en_la_captura_que_declara_el_artefacto(self):
        """BLOQUEANTE · la ventana no puede depender de CUÁNDO se empaquetó el artefacto.

        `raw/golden/osm_overpass.json` declara su captura (2026-09-29) y se commiteó el
        2026-10-01: anclando en la fecha de commit, la celda congelada
        `servicios_contexto.provenance` pasaba de «hasta 2026-10-29» a «hasta 2026-10-31»
        sin que cambiara NADA del dato. El ancla declarada por el artefacto manda, y la
        fecha de creación del archivo (hecho del EMPAQUETADO) no puede desplazarla.
        """
        osm = next(s for s in self.inv if s["ruta"].endswith("osm_overpass.json"))
        captura = str(osm["fecha_de_captura_declarada"])[:10]
        self.assertEqual(captura, "2026-09-29",
                         "el artefacto debe declarar la fecha de captura de su dato")
        ancla = acq.ancla_de_frescura(osm)
        self.assertEqual(ancla["origen"], acq.ANCLA_CAPTURA_DECLARADA)
        self.assertFalse(ancla["empaquetado"], "la captura declarada no es un hecho del pack")
        self.assertEqual(ancla["fecha"].isoformat(), captura)
        vig = acq.evaluar_vigencia(osm, self.ref, registro=self.reg)
        self.assertEqual(vig["limite"], "2026-10-29", "captura declarada + CONTEXTO 30 d")
        self.assertEqual(vig["estado"], acq.SNAPSHOT_VIGENTE)
        for empaquetado in ("2026-10-01T08:44:20-05:00", "2031-01-01T00:00:00+00:00",
                            "2026-09-01T00:00:00+00:00"):
            movido = dict(osm, fecha_de_creacion=empaquetado)
            igual = acq.evaluar_vigencia(movido, self.ref, registro=self.reg)
            self.assertEqual(igual["limite"], vig["limite"],
                             f"el empaquetado {empaquetado} movió la ventana congelada")
            self.assertEqual(igual["estado"], vig["estado"], empaquetado)
            self.assertEqual(igual["dias_restantes"], vig["dias_restantes"], empaquetado)

    def test_un_snapshot_sin_fecha_no_se_da_por_vigente(self):
        inventado = {"artifact_id": "X", "ruta": "api/data/amenaza_remocion_masa.geojson",
                     "usable": True, "familia": "RIESGO", "freshness_dias": 365,
                     "fecha_de_creacion": None, "vigencia_declarada_en_el_artefacto": {}}
        vig = acq.evaluar_vigencia(inventado, self.ref, registro=self.reg)
        self.assertEqual(vig["estado"], acq.SNAPSHOT_VENCIDO)
        self.assertFalse(vig["limite"])

    def test_un_artefacto_no_utilizable_se_declara_como_tal(self):
        vig = acq.evaluar_vigencia(self._snap("SNAP_CATASTRO_PREDIO_FIXTURE"), self.ref,
                                   registro=self.reg)
        self.assertEqual(vig["estado"], acq.SNAPSHOT_NO_UTILIZABLE)
        self.assertTrue(vig["motivo"])


# ══════════════════════════════════════════════════════════════════════════════
# 4 · REGLA LIVE → SNAPSHOT SIN DEGRADAR AUTORIDAD
# ══════════════════════════════════════════════════════════════════════════════
class TestReglaDeAdquisicion(BaseAdquisicion):

    def test_live_caido_se_resuelve_desde_el_snapshot_con_autoridad_original(self):
        r = acq.resolver_con_acquisition_mode("remocion", consultas=self.consultas_congeladas,
                                              registro=self.reg, fecha=self.ref,
                                              contexto=self.contexto, inventario=self.inv)
        self.assertEqual(r["resolution_status"], sr.RESOLVED_PRIMARY)
        self.assertIn(str(r["value"]).upper(), ("MEDIA", "ALTA", "MUY ALTA", "BAJA"))
        prov = acq.provenance_adquisicion(r)
        self.assertEqual(prov["original_source"], "POT_BAQ_REMOCION_2024")
        self.assertEqual(prov["acquisition_mode"], acq.AUTOMATED_SNAPSHOT)
        self.assertEqual(prov["declared_mode"], acq.LIVE_QUERY)
        self.assertEqual(prov["live_status"], ds.FUENTE_NO_DISPONIBLE)
        self.assertEqual(prov["snapshot"], "api/data/amenaza_remocion_masa.geojson")
        self.assertEqual(prov["content_hash"],
                         acq.hash_archivo(ROOT / "api/data/amenaza_remocion_masa.geojson"))
        self.assertEqual(prov["freshness_limit"], "2027-09-01")
        self.assertEqual(prov["freshness_familia"], "RIESGO")
        self.assertTrue(prov["source_queried_at"])
        self.assertEqual(prov["provenance"]["original_authority_class"],
                         ds.AUTORITATIVA_OFICIAL)
        self.assertTrue(prov["provenance"]["autoridad_no_degradada"])

    def test_la_authority_class_del_resultado_es_la_de_la_fuente_ORIGINAL(self):
        r = acq.resolver_con_acquisition_mode("remocion", consultas=self.consultas_congeladas,
                                              registro=self.reg, fecha=self.ref,
                                              contexto=self.contexto, inventario=self.inv)
        self.assertEqual(r["provenance"]["authority_class"], ds.AUTORITATIVA_OFICIAL)
        self.assertEqual(r["provenance"]["authority_class"],
                         self.fuentes["POT_BAQ_REMOCION_2024"]["authority_class"])
        self.assertEqual(acq.provenance_adquisicion(r)["authority_class"],
                         ds.AUTORITATIVA_OFICIAL)

    def test_si_la_fuente_en_vivo_responde_el_snapshot_NO_se_usa(self):
        vivo = dict(self.consultas_congeladas)
        vivo["POT_BAQ_REMOCION_2024"] = ds.resultado(
            "POT_BAQ_REMOCION_2024", ds.DISPONIBLE,
            payload_normalized={"amenaza": "Baja"}, queried_at=f"{self.ref}T00:00:00+00:00",
            provenance={"source_id": "POT_BAQ_REMOCION_2024",
                        "authority_class": ds.AUTORITATIVA_OFICIAL})
        r = acq.resolver_con_acquisition_mode("remocion", consultas=vivo, registro=self.reg,
                                              fecha=self.ref, contexto=self.contexto,
                                              inventario=self.inv)
        self.assertEqual(r["value"], "Baja")
        prov = acq.provenance_adquisicion(r)
        self.assertEqual(prov["acquisition_mode"], acq.LIVE_QUERY)
        self.assertEqual(prov["live_status"], ds.DISPONIBLE)
        self.assertIsNone(prov["snapshot"])
        modo = r["acquisition"]["modo_por_fuente"]["POT_BAQ_REMOCION_2024"]
        self.assertTrue(modo["usado"])
        self.assertIsNone(modo["snapshot"])
        self.assertNotIn("snapshot_consultado", modo)
        self.assertIn("snapshot no se usa", modo["motivo"])

    def test_toda_ausencia_de_contrato_dispara_el_snapshot(self):
        """`SOURCE_UNAVAILABLE`, `NOT_SUPPORTED` y `QUERY_FAILED` se comportan igual."""
        esperado = None
        for estado in (ds.FUENTE_NO_DISPONIBLE, ds.NO_SOPORTADA, ds.CONSULTA_FALLIDA):
            with self.subTest(estado=estado):
                consultas = dict(self.consultas_congeladas)
                consultas["POT_BAQ_RIESGO_2024"] = _resultado("POT_BAQ_RIESGO_2024", estado,
                                                              queried_at=f"{self.ref}T00:00:00+00:00")
                r = acq.resolver_con_acquisition_mode("riesgo", consultas=consultas,
                                                      registro=self.reg, fecha=self.ref,
                                                      contexto=self.contexto,
                                                      inventario=self.inv)
                self.assertEqual(r["resolution_status"], sr.RESOLVED_PRIMARY)
                self.assertTrue(sr.valor_utilizable(r["value"]))
                prov = acq.provenance_adquisicion(r)
                self.assertEqual(prov["acquisition_mode"], acq.AUTOMATED_SNAPSHOT)
                self.assertEqual(prov["live_status"], estado)
                if esperado is None:
                    esperado = r["value"]
                self.assertEqual(r["value"], esperado)

    def test_sin_coordenada_el_snapshot_espacial_declara_la_ausencia(self):
        r = acq.resolver_con_acquisition_mode("riesgo", consultas=self.consultas_congeladas,
                                              registro=self.reg, fecha=self.ref,
                                              contexto={"identificadores": {}},
                                              inventario=self.inv)
        self.assertIsNone(r["value"])
        self.assertEqual(r["resolution_status"], sr.SOURCE_UNAVAILABLE)
        modo = r["acquisition"]["modo_por_fuente"]["POT_BAQ_RIESGO_2024"]
        self.assertTrue(modo["snapshot_consultado"])
        self.assertFalse(modo["usado"])
        self.assertEqual(modo["snapshot_status"], ds.FUENTE_NO_DISPONIBLE)
        self.assertIn("coordenada", modo["snapshot_detail"])
        self.assertIn("NO es NO_MATCH", modo["motivo"])

    def test_el_snapshot_de_identidad_usa_las_claves_EXACTAS_declaradas(self):
        r = acq.resolver_con_acquisition_mode("identidad_nupre", consultas={},
                                              registro=self.reg, fecha=self.ref,
                                              contexto=self.contexto, inventario=self.inv)
        self.assertEqual(r["resolution_status"], sr.RESOLVED_PRIMARY)
        prov = acq.provenance_adquisicion(r)
        self.assertEqual(prov["acquisition_mode"], acq.AUTHORIZED_FALLBACK)
        self.assertEqual(prov["snapshot"], "api/data/barranquilla_adopcion_anexo1.json")
        payload = acq.payload_efectivo(r)
        # El contexto trae los TRES identificadores declarados del Golden (predial, NUPRE y
        # FMI leído del folio) → coincidencia EXACTA de los tres.
        self.assertEqual(payload["match_status"], "EXACT_3")
        self.assertTrue(payload["identity_verified"])
        self.assertEqual(payload["registro"]["fmi"], "646406")
        self.assertEqual(sorted(payload["identificadores_usados"]),
                         ["codigo_homologado", "fmi", "numero_predial"])

    def test_sin_identificadores_no_se_pide_el_dato_a_una_persona(self):
        r = acq.resolver_con_acquisition_mode("identidad_nupre", consultas={},
                                              registro=self.reg, fecha=self.ref,
                                              contexto={"identificadores": {}},
                                              inventario=self.inv)
        self.assertIsNone(r["value"])
        self.assertNotEqual(r["resolution_status"], ds.SIN_COINCIDENCIA)
        intento = r["attempts"][0]
        self.assertEqual(intento["status"], ds.NO_SOPORTADA)
        efectivo = acq.resultado_efectivo(r, intento["source_id"])
        self.assertEqual(efectivo["status"], ds.NO_SOPORTADA)
        self.assertIn("no se pide el dato a una persona", efectivo["detail"])
        self.assertNotIn("NO_MATCH", intento["rejected_reason"].split(":")[0])

    def test_la_escalera_no_se_reimplementa(self):
        """El módulo de adquisición USA la escalera: no declara su propio vocabulario."""
        r = acq.resolver_con_acquisition_mode("remocion", consultas=self.consultas_congeladas,
                                              registro=self.reg, fecha=self.ref,
                                              contexto=self.contexto, inventario=self.inv)
        self.assertEqual(r["annex_reference"], sr._anexo_id("remocion"))
        for clave in ("attempts", "fallbacks_used", "resolution_status", "annex_reference",
                      "ladder_notes", "first_escalon_source"):
            self.assertIn(clave, r)
        self.assertEqual(r["acquisition"]["ladder_version"], sr.PACK_ETIQUETA)
        for intento in r["attempts"]:
            self.assertIn(intento["status"], set(ds.ESTADOS) | {sr.NOT_RUN})


# ══════════════════════════════════════════════════════════════════════════════
# 5 · MATRIZ DE 11 COLUMNAS (CALCULADA, NADA A MANO)
# ══════════════════════════════════════════════════════════════════════════════
class TestMatrizDeRoles(BaseAdquisicion):

    def test_cabecera_y_filas_declaradas(self):
        self.assertTrue(RUTA_MATRIZ.exists(), "debe existir la matriz de adquisición")
        with RUTA_MATRIZ.open(encoding="utf-8", newline="") as fh:
            lector = csv.reader(fh)
            filas = list(lector)
        self.assertEqual(tuple(filas[0]), COLUMNAS_MATRIZ)
        self.assertEqual(len(filas) - 1, 18, "la matriz debe tener 18 filas de datos")
        dominios = [f[0] for f in filas[1:]]
        self.assertEqual(dominios, [d["domain"] for d in acq.DOMINIOS_DECLARADOS])
        for fila in filas[1:]:
            self.assertEqual(len(fila), len(COLUMNAS_MATRIZ), fila[0])
            self.assertIn(fila[3], ds.ESTADOS, f"estado fuera del contrato en {fila[0]}")
            self.assertIn(fila[2], acq.PRODUCT_ROLES, fila[0])
            self.assertIn(fila[9], ("True", "False"), fila[0])
            self.assertIn(fila[10], ("True", "False"), fila[0])

    def test_la_matriz_es_calculada_y_coincide_con_la_corrida(self):
        """Nada hardcodeado: la matriz versionada es EXACTAMENTE la que se recalcula."""
        en_disco = acq.leer_matriz(RUTA_MATRIZ)
        self.assertEqual(len(en_disco), len(self.filas))
        for a, b in zip(en_disco, self.filas):
            for columna in COLUMNAS_MATRIZ:
                self.assertEqual(str(a[columna]), str(b.get(columna, "")),
                                 f"{a['domain']}.{columna}")

    def test_la_matriz_congelada_no_depende_de_la_fecha_de_empaquetado(self):
        """BLOQUEANTE · con el MISMO dato y OTRO commit, la matriz congelada se reproduce.

        Mueve la fecha de creación (commit/mtime) del artefacto que declara su captura y
        exige las 18 filas × 11 columnas idénticas: un artefacto congelado no puede cargar
        un valor derivado de la corrida de empaquetado.
        """
        en_disco = acq.leer_matriz(RUTA_MATRIZ)
        for empaquetado in ("2026-10-01T08:44:20-05:00", "2031-01-01T00:00:00+00:00"):
            movido = [dict(s, fecha_de_creacion=empaquetado)
                      if s["ruta"].endswith("osm_overpass.json") else s for s in self.inv]
            filas = acq.matriz_roles(registro=self.reg, fecha=self.ref,
                                     contexto=self.contexto, inventario=movido,
                                     golden=self.golden)
            self.assertEqual(len(filas), len(en_disco))
            for a, b in zip(en_disco, filas):
                for columna in COLUMNAS_MATRIZ:
                    self.assertEqual(str(a[columna]), str(b.get(columna, "")),
                                     f"{a['domain']}.{columna} con empaquetado {empaquetado}")

    def test_la_autoridad_de_cada_fila_es_la_original_y_nunca_se_degrada(self):
        for fila in self.filas:
            fuentes = acq._fuentes_del_dominio(fila["source_id"], self.reg)
            registradas = [s for s in fuentes if self._en_registro(s)]
            esperadas = list(dict.fromkeys(str(self.fuentes[s]["authority_class"])
                                           for s in registradas))
            self.assertEqual(fila["authority"].split("+") if fila["authority"] else [],
                             esperadas, fila["domain"])
            for authority in esperadas:
                self.assertIn(authority, ds.CLASES_AUTORIDAD, fila["domain"])

    def test_el_rol_de_cada_fila_es_el_de_sus_fuentes(self):
        for fila in self.filas:
            fuentes = acq._fuentes_del_dominio(fila["source_id"], self.reg)
            roles = sorted({acq.rol_de_fuente(s) for s in fuentes})
            if len(roles) == 1:
                self.assertEqual(fila["product_role"], roles[0], fila["domain"])
            else:
                self.assertEqual(fila["product_role"], "MIXED(" + "|".join(roles) + ")",
                                 fila["domain"])
            for sid in fuentes:
                if not self._en_registro(sid):
                    self.assertNotEqual(fila["status"], ds.DISPONIBLE, fila["domain"])

    def test_los_requisitos_de_cada_fila_se_derivan_del_rol(self):
        for fila in self.filas:
            if fila["product_role"] in acq.ROLES_CORE:
                self.assertTrue(fila["required_for_decision"], fila["domain"])
                self.assertTrue(fila["blocking_if_missing"], fila["domain"])
            elif fila["product_role"] == acq.DECISION_CONTEXT:
                self.assertTrue(fila["required_for_decision"], fila["domain"])
                self.assertFalse(fila["blocking_if_missing"], fila["domain"])
            else:
                self.assertFalse(fila["required_for_decision"], fila["domain"])
                self.assertFalse(fila["blocking_if_missing"], fila["domain"])

    def test_el_hash_crudo_de_cada_fila_corresponde_a_la_evidencia_usada(self):
        for fila in self.filas:
            if fila["status"] != ds.DISPONIBLE:
                self.assertEqual(fila["raw_hash"], "", fila["domain"])
                continue
            origen = fila["provenance"]
            if "snapshot=" in origen and "snapshot=None" not in origen:
                ruta = origen.split("snapshot=")[1].split(" |")[0]
                self.assertEqual(fila["raw_hash"], acq.hash_archivo(ROOT / ruta),
                                 f"{fila['domain']} no hashea su snapshot")
                self.assertEqual(len(fila["raw_hash"]), 64, fila["domain"])
            else:
                self.assertIn("modo=LIVE_QUERY", origen, fila["domain"])
                self.assertEqual(len(fila["raw_hash"]), 0, fila["domain"])

    def test_los_dominios_core_declarados_estan_en_la_matriz(self):
        roles = {f["domain"]: f["product_role"] for f in self.filas}
        for dominio in ("identidad", "direccion", "predio", "uso_pot", "tratamiento",
                        "edificabilidad", "remocion", "inundacion", "riesgo", "mercado"):
            self.assertIn(roles[dominio], acq.ROLES_CORE, dominio)

    def test_binding_tipado_solo_en_los_dominios_de_identidad(self):
        for fila in self.filas:
            if fila["domain"] in ("identidad", "direccion", "predio"):
                self.assertIn(fila["binding"], ds.PRECEDENCIA_BINDING + (ds.SIN_BINDING,),
                              fila["domain"])
            else:
                self.assertEqual(fila["binding"], "NO_APLICA_NO_AUTORIZA_IDENTIDAD",
                                 fila["domain"])
        self.assertEqual(self._fila("identidad")["binding"], ds.BINDING_NUPRE)

    def test_ninguna_ausencia_declarada_se_convierte_en_no_match_ni_en_cero(self):
        for fila in self.filas:
            if fila["status"] != ds.DISPONIBLE:
                self.assertNotEqual(fila["status"], ds.SIN_COINCIDENCIA, fila["domain"])
                self.assertTrue(fila["normalized_result"].startswith("AUSENCIA_DECLARADA:"),
                                fila["domain"])
                self.assertNotIn("NO_MATCH", fila["status"])
                self.assertEqual(fila["raw_hash"], "", fila["domain"])

    def test_los_sellos_del_registro_no_alteran_el_contrato_de_fuentes(self):
        obligatorias = ("source_id", "source_name", "institution", "authority_class",
                        "base_url", "service", "layer_id", "layer_name", "geometry_type",
                        "query_method", "expected_fields", "primary_keys", "binding_fields",
                        "spatial_reference", "legal_or_normative_context",
                        "version_or_vigency", "precedence", "fallback_policy",
                        "freshness_policy", "failure_semantics", "license_or_terms",
                        "can_persist_raw", "can_embed_image", "provenance_fields", "enabled")
        for sid, f in self.fuentes.items():
            for clave in obligatorias:
                self.assertIn(clave, f, f"{sid} perdió {clave}")

    def test_el_gemelo_yaml_tiene_el_mismo_contenido_sellado(self):
        self.assertTrue(RUTA_REGISTRO_YAML.exists())
        try:
            import yaml  # type: ignore
        except Exception:  # noqa: BLE001
            self.skipTest("sin PyYAML no se puede comparar el gemelo")
        self.assertEqual(json.loads(RUTA_REGISTRO.read_text(encoding="utf-8")),
                         yaml.safe_load(RUTA_REGISTRO_YAML.read_text(encoding="utf-8")))

    def test_el_registro_declara_su_fecha_de_referencia(self):
        self.assertEqual(self.ref, acq.REFERENCE_DATE_POR_DEFECTO)
        self.assertIn("2026-09-29", str(self.reg.get("measurement_window") or ""))

    def test_sellar_registro_es_idempotente(self):
        una = acq.sellar_registro(self.reg, inventario=self.inv)
        dos = acq.sellar_registro(una, inventario=self.inv)
        self.assertEqual(ds.hash_canonico(una), ds.hash_canonico(dos))


# ══════════════════════════════════════════════════════════════════════════════
# 6 · E2E · SOLO DIRECCIÓN
# ══════════════════════════════════════════════════════════════════════════════
class TestE2ESoloDireccion(BaseAdquisicion):

    def _entrada(self):
        self.assertTrue(self.golden.get("direccion"),
                        "el run state del Golden debe aportar la dirección real")
        return {"direccion": self.golden["direccion"]}

    def _correr(self, consultas):
        return acq.resolver_identidad_canonica(self._entrada(), consultas=consultas,
                                               registro=self.reg, fecha=self.ref,
                                               contexto={"punto": {"lat": self.golden.get("lat"),
                                                                   "lon": self.golden.get("lon")},
                                                          "identificadores": {}},
                                               inventario=self.inv)

    def test_la_escalera_intenta_LIVE_registra_cada_fuente_y_no_pide_nada_a_personas(self):
        r = self._correr(dict(self.consultas_congeladas))
        self.assertFalse(r["intervencion_manual"])
        self.assertFalse(r["requiere_identificadores_manuales"])
        self.assertTrue(r["motivo"], "la ausencia debe declararse, no silenciarse")
        dir_res = r["resoluciones"]["direccion_predio"]
        intentos = {i["source_id"]: i for i in dir_res["attempts"]}
        self.assertEqual(intentos["CATASTRO_BAQ_DIRECCION"]["status"],
                         ds.FUENTE_NO_DISPONIBLE)
        efectivo_dir = acq.resultado_efectivo(dir_res, "CATASTRO_BAQ_DIRECCION")
        self.assertEqual(efectivo_dir["status"], ds.FUENTE_NO_DISPONIBLE)
        self.assertIn("403", efectivo_dir["detail"])
        self.assertIn("Cloudflare", efectivo_dir["detail"])
        self.assertEqual(intentos["CATASTRO_BAQ_DIRECCION"]["ladder_role"], "NO_SELECCIONADA")
        self.assertEqual(dir_res["resolution_status"], sr.SOURCE_UNAVAILABLE)
        self.assertIsNone(dir_res["value"])
        id_res = r["resoluciones"]["identidad_nupre"]
        sids = [i["source_id"] for i in id_res["attempts"]]
        self.assertIn("CATASTRO_BAQ_ADOPCION_ANEXO1", sids)
        self.assertNotEqual(id_res["resolution_status"], ds.SIN_COINCIDENCIA)
        texto = json.dumps(r, ensure_ascii=False, default=str).lower()
        for frase in FRASES_PROHIBIDAS:
            self.assertNotIn(frase.lower(), texto)

    def test_con_la_respuesta_documentada_de_la_capa_105_alcanza_la_identidad(self):
        r = self._correr(_live_105_documentado(self.golden))
        self.assertFalse(r["intervencion_manual"])
        self.assertFalse(r["requiere_identificadores_manuales"])
        dir_res = r["resoluciones"]["direccion_predio"]
        self.assertEqual(dir_res["resolution_status"], sr.RESOLVED_PRIMARY)
        self.assertEqual(acq.provenance_adquisicion(dir_res)["acquisition_mode"],
                         acq.LIVE_QUERY)
        self.assertIn("Transversal 43", str(dir_res["value"]))
        # Cae a SNAPSHOT donde procede: la identidad se confirma por el modo autorizado.
        prov_id = acq.provenance_adquisicion(r["resoluciones"]["identidad_nupre"])
        self.assertEqual(prov_id["original_source"], "CATASTRO_BAQ_ADOPCION_ANEXO1")
        self.assertNotEqual(prov_id["acquisition_mode"], acq.LIVE_QUERY)
        self.assertEqual(prov_id["provenance"]["original_authority_class"],
                         ds.AUTORITATIVA_OFICIAL)
        # Y la amenaza/riesgo del predio se resuelven desde los snapshots automáticos.
        ctx = dict(self.contexto)
        ctx["punto"] = {"lat": self.golden.get("lat"), "lon": self.golden.get("lon")}
        remocion = acq.resolver_con_acquisition_mode("remocion", consultas={},
                                                     registro=self.reg, fecha=self.ref,
                                                     contexto=ctx, inventario=self.inv)
        prov_rem = acq.provenance_adquisicion(remocion)
        self.assertEqual(prov_rem["acquisition_mode"], acq.AUTOMATED_SNAPSHOT)
        self.assertEqual(prov_rem["live_status"], None)
        self.assertIsNotNone(r["canonical_property_identity"])

    def test_la_identidad_alcanzada_declara_su_grado_y_su_regla(self):
        r = self._correr(_live_105_documentado(self.golden))
        cid = r["canonical_property_identity"]
        adq = r["adquisicion_de_identidad"]
        self.assertEqual(cid["nupre"], self.golden["nupre"])
        self.assertEqual(cid["codigo_catastral"], self.golden["numero_predial"])
        self.assertEqual(cid["folio_snr"], self.golden["folio"])
        self.assertEqual(adq["match_status"], "EXACT_2")
        self.assertEqual(adq["match_degree"], 2)
        self.assertIn("claves EXACTAS", adq["regla_de_confianza"])
        self.assertIn("DIRECCION", adq["entrada_declarada"])
        self.assertEqual(cid["resolution_confidence"], "VERIFIED_UNIT_IDENTITY")


# ══════════════════════════════════════════════════════════════════════════════
# 7 · E2E · SOLO CTL / MATRÍCULA
# ══════════════════════════════════════════════════════════════════════════════
class TestE2ESoloMatricula(BaseAdquisicion):

    def _entrada(self):
        self.assertTrue(self.golden.get("folio"), "el run state debe aportar el folio")
        return {"folio": self.golden["folio"]}

    def test_solo_matricula_alcanza_la_MISMA_identidad_que_solo_direccion(self):
        por_matricula = acq.resolver_identidad_canonica(
            self._entrada(), consultas={}, registro=self.reg, fecha=self.ref,
            contexto={"identificadores": {}}, inventario=self.inv)
        por_direccion = acq.resolver_identidad_canonica(
            {"direccion": self.golden["direccion"]},
            consultas=_live_105_documentado(self.golden), registro=self.reg, fecha=self.ref,
            contexto={"punto": {"lat": self.golden.get("lat"), "lon": self.golden.get("lon")},
                      "identificadores": {}}, inventario=self.inv)
        self.assertIsNotNone(por_matricula["canonical_property_identity"])
        self.assertIsNotNone(por_direccion["canonical_property_identity"])
        self.assertEqual(json.dumps(por_matricula["canonical_property_identity"],
                                    ensure_ascii=False, sort_keys=True),
                         json.dumps(por_direccion["canonical_property_identity"],
                                    ensure_ascii=False, sort_keys=True),
                         "el MISMO inmueble debe dar la MISMA identidad por las dos entradas")
        self.assertEqual(por_matricula["adquisicion_de_identidad"]["match_status"],
                         por_direccion["adquisicion_de_identidad"]["match_status"])
        for r in (por_matricula, por_direccion):
            self.assertFalse(r["intervencion_manual"])
            self.assertFalse(r["requiere_identificadores_manuales"])

    def test_la_matricula_entra_por_sus_DOS_partes_registrales(self):
        self.assertEqual(acq.partes_del_folio(self.golden["folio"]),
                         {"codigo_registral": "040", "fmi": "646406"})
        r = acq.resolver_identidad_canonica(self._entrada(), consultas={}, registro=self.reg,
                                            fecha=self.ref, contexto={"identificadores": {}},
                                            inventario=self.inv)
        claves = r["adquisicion_de_identidad"]["claves_exactas_usadas"]
        self.assertEqual(claves, ["codigo_registral", "fmi"])
        self.assertEqual(r["registro_de_adopcion"]["match_status"], "EXACT_2")
        self.assertEqual(r["registro_de_adopcion"]["registro"]["numero_predial"],
                         self.golden["numero_predial"])

    def test_sin_matricula_ni_direccion_no_se_alcanza_identidad_pero_se_declara(self):
        r = acq.resolver_identidad_canonica({}, consultas={}, registro=self.reg,
                                            fecha=self.ref, contexto={"identificadores": {}},
                                            inventario=self.inv)
        self.assertIsNone(r["canonical_property_identity"])
        self.assertTrue(r["motivo"])
        self.assertFalse(r["intervencion_manual"])
        self.assertNotEqual(r["resoluciones"]["identidad_nupre"]["resolution_status"],
                            ds.SIN_COINCIDENCIA)


# ══════════════════════════════════════════════════════════════════════════════
# 8 · NEGATIVOS
# ══════════════════════════════════════════════════════════════════════════════
class TestNegativos(BaseAdquisicion):

    def _registros(self):
        doc = json.loads((ROOT / "api/data/barranquilla_adopcion_anexo1.json")
                         .read_text(encoding="utf-8"))
        return [dict(r) for r in doc["registros"]]

    def _propio_y_vecino(self):
        """Separa el registro del Golden del registro VECINO del mismo snapshot real."""
        registros = self._registros()
        self.assertEqual(len(registros), 2, "el registro de adopción declara 2 predios")
        propio = [r for r in registros
                  if r["numero_predial"] == self.golden["numero_predial"]]
        vecino = [r for r in registros
                  if r["numero_predial"] != self.golden["numero_predial"]]
        self.assertEqual(len(propio), 1)
        self.assertEqual(len(vecino), 1)
        return propio[0], vecino[0]

    def test_el_predio_vecino_jamas_liga_la_identidad_del_golden(self):
        propio, vecino = self._propio_y_vecino()
        self.assertEqual(vecino["numero_predial"], "080010103000010040001908040003")
        self.assertEqual(vecino["codigo_homologado"], "AFT0005BORE")
        self.assertEqual(propio["fmi"], acq.partes_del_folio(self.golden["folio"])["fmi"])
        # El predio del Golden va SEGUNDO: elegir la primera fila daría el vecino.
        r = ds.elegir_predio_canonico([{"attributes": vecino}, {"attributes": propio}],
                                      nupre=self.golden["nupre"],
                                      numero_predial=self.golden["numero_predial"])
        self.assertEqual(r["binding_status"], ds.BINDING_NUPRE)
        self.assertEqual(r["feature"]["fmi"], "646406")
        self.assertEqual(r["feature"]["numero_predial"], self.golden["numero_predial"])
        # Con los identificadores del VECINO nunca se liga el predio del Golden.
        r_vecino = ds.elegir_predio_canonico([{"attributes": vecino}, {"attributes": propio}],
                                            nupre=vecino["codigo_homologado"],
                                            numero_predial=vecino["numero_predial"])
        self.assertEqual(r_vecino["feature"]["numero_predial"], vecino["numero_predial"])
        self.assertNotEqual(r_vecino["feature"]["numero_predial"],
                            self.golden["numero_predial"])
        self.assertNotEqual(r_vecino["feature"]["fmi"], propio["fmi"])
        # El orden de las features no decide nada.
        invertido = ds.elegir_predio_canonico([{"attributes": propio}, {"attributes": vecino}],
                                              nupre=self.golden["nupre"])
        self.assertEqual(invertido["feature"]["fmi"], r["feature"]["fmi"])

    def test_un_predio_vecino_no_hereda_la_identidad_por_el_registro_de_adopcion(self):
        _, vecino = self._propio_y_vecino()
        contexto = dict(self.contexto)
        contexto["identificadores"] = {"numero_predial": vecino["numero_predial"],
                                       "codigo_homologado": vecino["codigo_homologado"]}
        r = acq.resolver_con_acquisition_mode("identidad_nupre", consultas={},
                                              registro=self.reg, fecha=self.ref,
                                              contexto=contexto, inventario=self.inv)
        payload = acq.payload_efectivo(r)
        self.assertEqual(payload["registro"]["fmi"], vecino["fmi"])
        self.assertEqual(payload["registro"]["numero_predial"], vecino["numero_predial"])
        self.assertNotEqual(payload["registro"]["numero_predial"],
                            self.golden["numero_predial"])
        self.assertNotEqual(payload["registro"]["codigo_homologado"], self.golden["nupre"])

    def test_identificadores_disjuntos_son_conflicto_y_no_eligen_en_silencio(self):
        contexto = dict(self.contexto)
        contexto["identificadores"] = {"numero_predial": self.golden["numero_predial"],
                                       "codigo_homologado": "AFT0005BORE"}
        r = acq.resolver_con_acquisition_mode("identidad_nupre", consultas={},
                                              registro=self.reg, fecha=self.ref,
                                              contexto=contexto, inventario=self.inv)
        self.assertIsNone(r["value"])
        self.assertNotEqual(r["resolution_status"], ds.SIN_COINCIDENCIA)
        intento = r["attempts"][0]
        efectivo = acq.resultado_efectivo(r, intento["source_id"])
        self.assertEqual(efectivo["status"], ds.CONSULTA_FALLIDA)
        self.assertIn("CONFLICT", efectivo["detail"])
        self.assertIn("no se elige uno en silencio", efectivo["detail"])

    def test_una_fuente_SOURCE_UNAVAILABLE_jamas_se_convierte_en_NO_MATCH(self):
        consultas = {sid: _resultado(sid, ds.FUENTE_NO_DISPONIBLE,
                                     queried_at=f"{self.ref}T00:00:00+00:00")
                     for sid in self.fuentes}
        for atributo in sr.atributos_declarados():
            with self.subTest(atributo=atributo):
                r = acq.resolver_con_acquisition_mode(atributo, consultas=consultas,
                                                      registro=self.reg, fecha=self.ref,
                                                      contexto=self.contexto,
                                                      inventario=self.inv)
                self.assertNotEqual(r["resolution_status"], ds.SIN_COINCIDENCIA)
                for intento in r["attempts"]:
                    if intento["status"] in ds.ESTADOS_SIN_DATO:
                        self.assertNotEqual(intento["status"], ds.SIN_COINCIDENCIA)
                        self.assertTrue(intento["rejected_reason"])
                if not sr.valor_utilizable(r["value"]):
                    self.assertIsNone(r["value"])

    def test_una_ausencia_nunca_produce_valor_cero(self):
        consultas = {sid: _resultado(sid, ds.CONSULTA_FALLIDA,
                                     queried_at=f"{self.ref}T00:00:00+00:00")
                     for sid in self.fuentes}
        for atributo in ("remocion", "riesgo", "mercado"):
            r = acq.resolver_con_acquisition_mode(atributo, consultas=consultas,
                                                  registro=self.reg, fecha=self.ref,
                                                  contexto={"identificadores": {}},
                                                  inventario=self.inv)
            self.assertIsNone(r["value"])
            self.assertEqual(acq.provenance_adquisicion(r), {})

    def test_caso_no_PH_declarado_no_exige_identidad_de_unidad(self):
        sys.path.insert(0, str(ROOT / "api"))
        from canonical import build_canonical_property_identity, identity_authorized
        cid = build_canonical_property_identity(
            analysis={"direccion": "CARRERA 1 # 2 - 3", "nupre": "AFT0005BORE",
                      "codigo_catastral": "080010103000010040001908040003"},
            folio="040-646407",
            predio_real={"predio": {"numero_predial_nacional":
                                    "080010103000010040001908040003",
                                    "codigo_homologado": "AFT0005BORE"},
                         "condicion": {"condicion_juridica": "NO PROPIEDAD HORIZONTAL"},
                         "entorno": {}},
            nom=None, identidad=None, ciudad="barranquilla", metodo_resolucion="nupre")
        self.assertFalse(cid["propiedad_horizontal"])
        self.assertTrue(identity_authorized(cid), "sin PH la identidad no bloquea")
        self.assertFalse(cid["identity_verified"])
        # Y el caso PH del Golden SÍ exige la unidad verificada.
        r = acq.resolver_identidad_canonica({"folio": self.golden["folio"]}, consultas={},
                                            registro=self.reg, fecha=self.ref,
                                            contexto={"identificadores": {}}, inventario=self.inv)
        cid_ph = r["canonical_property_identity"]
        self.assertTrue(cid_ph["propiedad_horizontal"])
        self.assertTrue(identity_authorized(cid_ph))
        self.assertEqual(cid_ph["resolution_confidence"], "VERIFIED_UNIT_IDENTITY")


# ══════════════════════════════════════════════════════════════════════════════
# 9 · REPRODUCIBILIDAD
# ══════════════════════════════════════════════════════════════════════════════
class TestReproducibilidad(BaseAdquisicion):

    def test_dos_corridas_con_las_mismas_respuestas_dan_el_mismo_resultado(self):
        firma = lambda filas: json.dumps(  # noqa: E731
            [{k: f[k] for k in COLUMNAS_MATRIZ} for f in filas],
            ensure_ascii=False, sort_keys=True)
        una = acq.matriz_roles(registro=self.reg, fecha=self.ref, contexto=self.contexto,
                               inventario=self.inv, golden=self.golden)
        otra = acq.matriz_roles(registro=self.reg, fecha=self.ref, contexto=self.contexto,
                                inventario=self.inv, golden=self.golden)
        self.assertEqual(firma(una), firma(otra))

    def test_queried_at_queda_FUERA_de_todo_hash_de_contenido(self):
        a = {"atributo": "remocion", "valor": "Media", "queried_at": "2026-09-29T00:00:00Z",
             "run_id": "uno"}
        b = {"atributo": "remocion", "valor": "Media", "queried_at": "2030-01-01T09:09:09Z",
             "run_id": "dos"}
        self.assertEqual(acq.hash_contenido(a), acq.hash_contenido(b))
        self.assertNotEqual(acq.hash_contenido(a),
                            acq.hash_contenido({**a, "valor": "Alta"}))

    def test_el_payload_normalizado_y_el_hash_crudo_no_dependen_de_la_corrida(self):
        primero = acq.resolver_con_acquisition_mode("remocion",
                                                    consultas=self.consultas_congeladas,
                                                    registro=self.reg, fecha=self.ref,
                                                    contexto=self.contexto,
                                                    inventario=self.inv)
        segundo = acq.resolver_con_acquisition_mode("remocion",
                                                    consultas=self.consultas_congeladas,
                                                    registro=self.reg, fecha=self.ref,
                                                    contexto=self.contexto,
                                                    inventario=self.inv)
        self.assertEqual(primero["value"], segundo["value"])
        self.assertEqual(acq.provenance_adquisicion(primero)["content_hash"],
                         acq.provenance_adquisicion(segundo)["content_hash"])
        self.assertEqual(acq.hash_contenido(acq.payload_efectivo(primero)),
                         acq.hash_contenido(acq.payload_efectivo(segundo)))
        self.assertEqual(primero["selected_source"], segundo["selected_source"])

    def test_el_orden_de_las_consultas_no_cambia_la_precedencia(self):
        import itertools
        sids = ["POT_BAQ_REMOCION_2024", "POT_BAQ_REMOCION_HIST"]
        referencia = None
        for orden in itertools.permutations(sids):
            consultas = {sid: self.consultas_congeladas.get(sid)
                         for sid in orden}
            r = acq.resolver_con_acquisition_mode("remocion", consultas=consultas,
                                                  registro=self.reg, fecha=self.ref,
                                                  contexto=self.contexto, inventario=self.inv)
            if referencia is None:
                referencia = r
            self.assertEqual(r["selected_source"], "POT_BAQ_REMOCION_2024")
            self.assertEqual(r["value"], referencia["value"])
            self.assertEqual(r["resolution_status"], referencia["resolution_status"])

    def test_la_identidad_es_reproducible_por_las_dos_entradas(self):
        def firma(r):
            return acq.hash_contenido({"cid": r["canonical_property_identity"],
                                       "match": r["adquisicion_de_identidad"]["match_status"]})
        dir_a = acq.resolver_identidad_canonica({"direccion": self.golden["direccion"]},
                                               consultas=_live_105_documentado(self.golden),
                                               registro=self.reg, fecha=self.ref,
                                               contexto={"punto": {"lat": self.golden["lat"],
                                                                   "lon": self.golden["lon"]},
                                                          "identificadores": {}},
                                               inventario=self.inv)
        dir_b = acq.resolver_identidad_canonica({"direccion": self.golden["direccion"]},
                                               consultas=_live_105_documentado(self.golden),
                                               registro=self.reg, fecha=self.ref,
                                               contexto={"punto": {"lat": self.golden["lat"],
                                                                   "lon": self.golden["lon"]},
                                                          "identificadores": {}},
                                               inventario=self.inv)
        ctl = acq.resolver_identidad_canonica({"folio": self.golden["folio"]}, consultas={},
                                              registro=self.reg, fecha=self.ref,
                                              contexto={"identificadores": {}},
                                              inventario=self.inv)
        self.assertEqual(firma(dir_a), firma(dir_b))
        self.assertEqual(firma(dir_a), firma(ctl))


# ══════════════════════════════════════════════════════════════════════════════
# 10 · ESTADO: CONTRACT_FROZEN vs OPERATIONAL_READY
# ══════════════════════════════════════════════════════════════════════════════
class TestEstadoDeAceptacion(BaseAdquisicion):

    def setUp(self):
        self.estado = acq.estado_operativo(registro=self.reg, fecha=self.ref,
                                          filas=self.filas, contexto=self.contexto,
                                          inventario=self.inv)

    def test_el_contrato_esta_congelado_con_sus_criterios(self):
        bloque = self.estado["contract_frozen"]
        self.assertEqual(bloque["estado"], "CONTRACT_FROZEN")
        criterios = [c["criterio"] for c in bloque["criterios"]]
        for exigido in ("registro_completo", "metadata_real", "market_formalizada",
                        "binding_tipado", "precedencia_determinista", "escalera_por_atributo",
                        "licencias_documentadas", "modos_de_adquisicion",
                        "snapshots_descubiertos", "gemelos_identicos"):
            self.assertIn(exigido, criterios)
        for c in bloque["criterios"]:
            self.assertTrue(c["evidencia"].strip())

    def test_el_veredicto_se_deriva_de_la_cobertura_CORE(self):
        operational = self.estado["operational_ready"]
        core = {f["domain"] for f in self.filas if f["product_role"] in acq.ROLES_CORE}
        self.assertEqual(set(operational["core_cubiertos"]) |
                         set(operational["core_no_cubiertos"]), core)
        self.assertEqual(operational["listo"], not operational["core_no_cubiertos"])
        if operational["listo"]:
            self.assertEqual(self.estado["veredicto"], "PRODUCTION_READY")
        else:
            self.assertEqual(self.estado["veredicto"],
                             "CONTRACT_FROZEN / OPERATIONAL_NOT_READY")
            self.assertTrue(operational["dominios_bloqueantes"])
            self.assertIn("NO tiene ruta automática válida", self.estado["justificacion"])

    def test_los_dominios_core_cubiertos_lo_estan_por_una_ruta_declarada(self):
        for dominio in self.estado["operational_ready"]["core_cubiertos"]:
            fila = self._fila(dominio)
            self.assertEqual(fila["status"], ds.DISPONIBLE)
            self.assertTrue(fila["provenance"], dominio)
            self.assertIn("modo=", fila["provenance"], dominio)
            if "snapshot=" in fila["provenance"] and "snapshot=None" not in fila["provenance"]:
                ruta = fila["provenance"].split("snapshot=")[1].split(" |")[0]
                vig = acq.evaluar_vigencia(
                    next(s for s in self.inv if s["ruta"] == ruta), self.ref,
                    registro=self.reg)
                self.assertEqual(vig["estado"], acq.SNAPSHOT_VIGENTE,
                                 f"{dominio} resuelve con un snapshot no vigente")

    def test_los_dominios_core_no_cubiertos_declaran_la_ausencia_sin_maquillar(self):
        for dominio in self.estado["operational_ready"]["core_no_cubiertos"]:
            fila = self._fila(dominio)
            self.assertNotEqual(fila["status"], ds.DISPONIBLE)
            self.assertTrue(fila["normalized_result"].startswith("AUSENCIA_DECLARADA:"))
            self.assertTrue(fila["provenance"], dominio)

    def test_el_403_del_geoportal_esta_VERIFICADO_en_la_evidencia(self):
        self.assertTrue(RUTA_PROBE_GEOPORTAL.exists())
        probe = json.loads(RUTA_PROBE_GEOPORTAL.read_text(encoding="utf-8"))
        resultados = probe["results"]
        self.assertEqual(len(resultados), 150)
        self.assertEqual({str(v.get("status")) for v in resultados.values()}, {"403"})
        self.assertTrue(self.estado["operational_ready"]["fuentes_en_vivo_sin_snapshot"])
        for sid in self.estado["operational_ready"]["fuentes_en_vivo_sin_snapshot"]:
            self.assertTrue(str(self.fuentes[sid]["base_url"]).startswith("http"))
            self.assertEqual(self.modos[sid]["snapshots_usables"], [])

    def test_el_manifest_publica_los_dos_estados(self):
        man = json.loads(RUTA_MANIFEST.read_text(encoding="utf-8"))
        self.assertIn("operational_readiness", man)
        self.assertIn("acquisition_modes", man)
        self.assertIn("product_roles", man)
        self.assertEqual(man["operational_readiness"]["veredicto"], self.estado["veredicto"])
        self.assertTrue(man["operational_readiness"]["geoportal_http_403_verificado"])
        self.assertEqual(sorted(man["acquisition_modes"]["modes"]),
                         sorted(acq.ACQUISITION_MODES))
        self.assertEqual(man["acquisition_modes"]["reference_date"], self.ref)
        self.assertEqual(sorted(man["product_roles"]["vocabulary"]),
                         sorted(acq.PRODUCT_ROLES))

    def test_la_matriz_de_adquisicion_no_sustituye_a_la_del_contrato(self):
        """La matriz de 7 columnas del contrato queda intacta y sigue siendo válida."""
        ruta = DIR_PACK / "SOURCE_COVERAGE_MATRIX_040-646406.csv"
        with ruta.open(encoding="utf-8", newline="") as fh:
            filas = list(csv.reader(fh))
        self.assertEqual(filas[0], ["row", "source", "status", "value_or_result", "authority",
                                    "provenance", "hash"])
        self.assertEqual(len(filas) - 1, 18)
        self.assertNotEqual(RUTA_MATRIZ.name, ruta.name)


# ══════════════════════════════════════════════════════════════════════════════
# 11 · CONGRUENCIA CON EL PACK EXISTENTE
# ══════════════════════════════════════════════════════════════════════════════
class TestCongruenciaConElPack(BaseAdquisicion):

    def _modulo_cobertura(self):
        ruta = ROOT / "scripts" / "source_pack_coverage.py"
        spec = importlib.util.spec_from_file_location("sp_coverage_adq", ruta)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return modulo

    def test_el_adaptador_de_snapshot_da_el_mismo_veredicto_que_el_script_del_pack(self):
        """El adaptador de la capa de adquisición reproduce EXACTO el veredicto del pack."""
        cov = self._modulo_cobertura()
        esperado = cov.identidad_adopcion(self.golden)
        contexto = dict(self.contexto)
        contexto["identificadores"] = {"numero_predial": self.golden["numero_predial"],
                                       "codigo_homologado": self.golden["nupre"],
                                       "fmi": acq.partes_del_folio(self.golden["folio"])["fmi"]}
        r = acq.resolver_con_acquisition_mode("identidad_nupre", consultas={},
                                              registro=self.reg, fecha=self.ref,
                                              contexto=contexto, inventario=self.inv)
        payload = acq.payload_efectivo(r)
        self.assertEqual(payload["match_status"], esperado["payload"]["match_status"])
        self.assertEqual(payload["identity_verified"], esperado["payload"]["identity_verified"])
        self.assertEqual(payload["registro"], esperado["payload"]["registro"])
        self.assertEqual(payload["match_status"], "EXACT_3")
        self.assertEqual(r["resolution_status"], sr.RESOLVED_PRIMARY)

    def test_los_identificadores_del_golden_se_leen_del_run_state(self):
        self.assertTrue(RUTA_RUN_STATE.exists())
        rs = json.loads(RUTA_RUN_STATE.read_text(encoding="utf-8"))
        ident = rs["property_identity"]
        self.assertEqual(self.golden["direccion"], ident["direccion_raw"])
        self.assertEqual(self.golden["folio"], ident["folio"])
        self.assertEqual(self.golden["nupre"], ident["nupre"])
        self.assertEqual(self.golden["numero_predial"], ident["codigo_catastral"])
        self.assertTrue(self.golden["run_id"])

    def test_el_snapshot_de_contexto_de_OSM_conserva_su_autoridad_contextual(self):
        r = acq.resolver_con_acquisition_mode("servicios_de_contexto", consultas={},
                                              registro=self.reg, fecha=self.ref,
                                              contexto=self.contexto, inventario=self.inv)
        prov = acq.provenance_adquisicion(r)
        self.assertEqual(prov["acquisition_mode"], acq.AUTOMATED_SNAPSHOT)
        self.assertEqual(prov["provenance"]["original_authority_class"],
                         ds.CONTEXTUAL_EXTERNA)
        self.assertEqual(prov["snapshot"], "docs/source_pack/raw/golden/osm_overpass.json")
        self.assertEqual(prov["content_hash"], acq.hash_archivo(RUTA_CAPTURA_OSM))
        self.assertNotIn(ds.CONTEXTUAL_EXTERNA, ds.CLASES_NORMATIVAS)

    def test_las_fuentes_deshabilitadas_se_declaran_NOT_SUPPORTED(self):
        deshabilitadas = [sid for sid, f in self.fuentes.items() if f.get("enabled") is False]
        self.assertTrue(deshabilitadas)
        for sid in deshabilitadas:
            res = self.consultas_congeladas[sid]
            self.assertEqual(res["status"], ds.NO_SOPORTADA, sid)
            self.assertNotEqual(res["status"], ds.SIN_COINCIDENCIA, sid)


if __name__ == "__main__":
    unittest.main()
