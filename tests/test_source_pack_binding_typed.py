# -*- coding: utf-8 -*-
"""BARRANQUILLA SOURCE PACK v1.0-R1 — requisitos C, D y E (offline, sin red).

  C · BINDING TIPADO: `elegir_predio_canonico` compara cada identificador SOLO contra
      los campos de SU tipo. Un NUPRE no puede ligar contra `numero_predial` aunque el
      texto normalizado coincida; un tipo no determinable no se compara; un mismo texto
      en otra columna no liga; el orden de las features no decide nada; el binding
      espacial nunca autoriza identidad. Hay un caso positivo por cada tipo declarado.
  D · PRECEDENCIA DETERMINISTA: `resolver_precedencia` no depende del orden de entrada.
      Todas las permutaciones de una lista de candidatas eligen lo mismo; un empate de
      `source_priority` (o su ausencia) declara AMBIGUOUS_CURRENT_SOURCE; sin capa
      vigente se declara SIN_DATO y NINGUNA histórica se asciende.
  E · RIESGO BARRANQUILLA: `candidatos_riesgo_barranquilla()` declara las vigentes del
      Decreto 893 de 2024 (73, 77, 81) y las históricas (71, 75, 79) con
      `precedence` y `source_priority` explícitos, y el resultado es determinista.

No se toca la red ni ningún otro archivo del pack: sólo el contrato de `api/dictus_sources.py`.
"""
import itertools
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import dictus_sources as ds  # noqa: E402

NUPRE_VALIDO = "AFT0005BOHA"
PREDIAL_VALIDO = "080010001000100010001000"          # 24 dígitos
MUNICIPAL_KEY_VALIDA = "08001-040314248"
GUID_VALIDO = "a1b2c3d4e5f60718293a4b5c6d7e8f90"
DIRECCION_LIGADA = "TV 43 # 100 - 50"

VECINO = {"attributes": {"nupre": "AFT-OTRO", "numero_predial": "999",
                         "direccion": "CALLE 9 # 9 - 9", "objectid": 1}}
PROPIO = {"attributes": {"nupre": NUPRE_VALIDO, "numero_predial": PREDIAL_VALIDO,
                         "direccion": DIRECCION_LIGADA, "objectid": 2}}


def _huella(resultado):
    """Huella COMPLETA y comparable de un resultado de binding (sin índices de posición)."""
    return json.dumps({"binding_status": resultado["binding_status"],
                       "identifier_type": resultado["identifier_type"],
                       "matched_field": resultado["matched_field"],
                       "feature_hash": resultado["feature_hash"],
                       "matches_found": resultado["matches_found"],
                       "spatial_used_as_identity": resultado["spatial_used_as_identity"]},
                      sort_keys=True, default=str)


def _candidata(source_id, precedence, **over):
    c = {"source_id": source_id, "precedence": precedence}
    c.update(over)
    return c


# ══════════════════════════════════════════════════════════════════════════════
# C.1 · CONTRATO DE TIPOS (compatibilidad, saneado por tipo y clasificación)
# ══════════════════════════════════════════════════════════════════════════════
class TestContratoDeTipos(unittest.TestCase):

    def test_tipos_declarados_y_clasificables(self):
        for tipo in (ds.TIPO_NUPRE, ds.TIPO_NUMERO_PREDIAL, ds.TIPO_MUNICIPAL_KEY,
                     ds.TIPO_RELACION_OFICIAL, ds.TIPO_DIRECCION_LIGADA):
            self.assertIn(tipo, ds.TIPOS_IDENTIFICADOR)
        for tipo in (ds.TIPO_NUPRE, ds.TIPO_NUMERO_PREDIAL, ds.TIPO_MUNICIPAL_KEY,
                     ds.TIPO_RELACION_OFICIAL):
            self.assertIn(tipo, ds.FORMATOS_POR_TIPO)
        self.assertIn(ds.TIPO_DESCONOCIDO, ds.TIPOS_IDENTIFICADOR)
        self.assertNotIn(ds.TIPO_DESCONOCIDO, ds.FORMATOS_POR_TIPO)

    def test_direccion_y_predial_anterior_no_se_infieren_por_forma(self):
        self.assertIn(ds.TIPO_DIRECCION_LIGADA, ds.TIPOS_NO_INFERIBLES_POR_FORMA)
        self.assertIn(ds.TIPO_NUMERO_PREDIAL_ANTERIOR, ds.TIPOS_NO_INFERIBLES_POR_FORMA)
        self.assertEqual(ds.clasificar_identificador(DIRECCION_LIGADA), ds.TIPO_DESCONOCIDO)

    def test_campos_por_tipo_no_se_cruzan(self):
        self.assertEqual(ds.TIPO_A_CAMPOS[ds.TIPO_NUPRE],
                         ("codigo_homologado", "nupre"))
        self.assertEqual(ds.TIPO_A_CAMPOS[ds.TIPO_NUMERO_PREDIAL],
                         ("numero_predial", "numero_predial_nacional"))
        self.assertEqual(ds.TIPO_A_CAMPOS[ds.TIPO_MUNICIPAL_KEY], ("municipal_key",))
        self.assertEqual(ds.TIPO_A_CAMPOS[ds.TIPO_RELACION_OFICIAL],
                         ("globalid", "guid", "predio_guid"))
        self.assertEqual(ds.TIPO_A_CAMPOS[ds.TIPO_DIRECCION_LIGADA], ("direccion",))
        # Ningún campo pertenece a dos tipos.
        campos = [c for campos in ds.TIPO_A_CAMPOS.values() for c in campos]
        self.assertEqual(len(campos), len(set(campos)))

    def test_nupre_es_incompatible_con_numero_predial(self):
        self.assertFalse(ds.tipos_compatibles(ds.TIPO_NUPRE, ds.TIPO_NUMERO_PREDIAL))
        self.assertFalse(ds.tipos_compatibles(ds.TIPO_NUMERO_PREDIAL, ds.TIPO_NUPRE))
        self.assertTrue(ds.tipos_compatibles(ds.TIPO_NUPRE, ds.TIPO_NUPRE))
        for a, b in ds.PARES_INCOMPATIBLES_DECLARADOS:
            self.assertFalse(ds.tipos_compatibles(a, b), f"{a} vs {b} debería ser incompatible")
        self.assertFalse(ds.tipos_compatibles(ds.TIPO_DESCONOCIDO, ds.TIPO_NUPRE))
        self.assertFalse(ds.tipos_compatibles(ds.TIPO_NUPRE, ds.TIPO_DESCONOCIDO))

    def test_saneado_propio_de_cada_tipo(self):
        self.assertEqual(ds.normalizar_por_tipo("aft-0005/boha", ds.TIPO_NUPRE),
                         NUPRE_VALIDO)
        self.assertEqual(ds.normalizar_por_tipo("0800 100-100 100", ds.TIPO_NUMERO_PREDIAL),
                         "0800100100100")
        self.assertEqual(ds.normalizar_por_tipo("{a1b2c3d4-e5f6-0718-293a-4b5c6d7e8f90}",
                                                ds.TIPO_RELACION_OFICIAL),
                         GUID_VALIDO.upper())
        self.assertEqual(ds.normalizar_por_tipo("tv 43 # 100 - 50", ds.TIPO_DIRECCION_LIGADA),
                         DIRECCION_LIGADA)
        # Un tipo desconocido no produce valor comparable.
        self.assertEqual(ds.normalizar_por_tipo(NUPRE_VALIDO, ds.TIPO_DESCONOCIDO), "")
        # El saneado de predial NO deja letras: no puede casar con un NUPRE.
        self.assertEqual(ds.normalizar_por_tipo("AFT0005BOHA", ds.TIPO_NUMERO_PREDIAL), "")

    def test_clasificacion_por_forma(self):
        casos = ((NUPRE_VALIDO, ds.TIPO_NUPRE),
                 ("aft-otro", ds.TIPO_NUPRE),
                 (PREDIAL_VALIDO, ds.TIPO_NUMERO_PREDIAL),
                 ("0800100010001000100010001234", ds.TIPO_NUMERO_PREDIAL),
                 (MUNICIPAL_KEY_VALIDA, ds.TIPO_MUNICIPAL_KEY),
                 ("{%s}" % GUID_VALIDO.upper(), ds.TIPO_RELACION_OFICIAL),
                 ("0800", ds.TIPO_DESCONOCIDO),          # ni NUPRE ni predial válido
                 ("", ds.TIPO_DESCONOCIDO),
                 (None, ds.TIPO_DESCONOCIDO),
                 ("///", ds.TIPO_DESCONOCIDO))
        for valor, esperado in casos:
            self.assertEqual(ds.clasificar_identificador(valor), esperado, repr(valor))

    def test_conflicto_entre_forma_y_declaracion_es_unknown(self):
        info = ds.resolver_tipo_identificador(PREDIAL_VALIDO, slot="nupre")
        self.assertEqual(info["identifier_type"], ds.TIPO_DESCONOCIDO)
        self.assertTrue(info["type_conflict"])
        self.assertFalse(info["comparable"])
        # Forma no concluyente: manda la declaración explícita del llamador.
        info2 = ds.resolver_tipo_identificador("0800", slot="numero_predial")
        self.assertEqual(info2["identifier_type"], ds.TIPO_NUMERO_PREDIAL)
        self.assertFalse(info2["type_conflict"])
        # Sin forma ni declaración: UNKNOWN y no se compara.
        info3 = ds.resolver_tipo_identificador("0800")
        self.assertEqual(info3["identifier_type"], ds.TIPO_DESCONOCIDO)
        self.assertFalse(info3["comparable"])


# ══════════════════════════════════════════════════════════════════════════════
# C.2 · UN CASO POSITIVO POR CADA TIPO DECLARADO
# ══════════════════════════════════════════════════════════════════════════════
class TestBindingTipadoPositivo(unittest.TestCase):

    def setUp(self):
        self.features = [VECINO, PROPIO]

    def test_nupre_por_la_columna_nupre(self):
        r = ds.elegir_predio_canonico(self.features, nupre="aft0005boha")
        self.assertEqual(r["binding_status"], ds.BINDING_NUPRE)
        self.assertEqual(r["identifier_type"], ds.TIPO_NUPRE)
        self.assertEqual(r["matched_field"], "nupre")
        self.assertTrue(ds.identidad_autorizada_por_binding(r["binding_status"]))

    def test_nupre_por_codigo_homologado(self):
        r = ds.elegir_predio_canonico(self.features, codigo_homologado=GUID_VALIDO)
        self.assertIsNone(r["feature"])       # no hay columna de código homologado
        r2 = ds.elegir_predio_canonico([{"attributes": {"codigo_homologado": NUPRE_VALIDO}}],
                                       codigo_homologado=NUPRE_VALIDO)
        self.assertEqual(r2["binding_status"], ds.BINDING_NUPRE)
        self.assertEqual(r2["identifier_type"], ds.TIPO_NUPRE)
        self.assertEqual(r2["matched_field"], "codigo_homologado")

    def test_numero_predial_por_la_columna_numero_predial(self):
        r = ds.elegir_predio_canonico(self.features, numero_predial=PREDIAL_VALIDO)
        self.assertEqual(r["binding_status"], ds.BINDING_PREDIAL)
        self.assertEqual(r["identifier_type"], ds.TIPO_NUMERO_PREDIAL)
        self.assertEqual(r["matched_field"], "numero_predial")

    def test_numero_predial_por_la_columna_nacional(self):
        r = ds.elegir_predio_canonico(
            [{"attributes": {"numero_predial_nacional": PREDIAL_VALIDO}}],
            numero_predial=PREDIAL_VALIDO)
        self.assertEqual(r["binding_status"], ds.BINDING_PREDIAL)
        self.assertEqual(r["identifier_type"], ds.TIPO_NUMERO_PREDIAL)
        self.assertEqual(r["matched_field"], "numero_predial_nacional")

    def test_clave_municipal(self):
        r = ds.elegir_predio_canonico(
            [{"attributes": {"municipal_key": MUNICIPAL_KEY_VALIDA}}],
            municipal_key=MUNICIPAL_KEY_VALIDA)
        self.assertEqual(r["binding_status"], ds.BINDING_MUNICIPAL_KEY)
        self.assertEqual(r["identifier_type"], ds.TIPO_MUNICIPAL_KEY)
        self.assertEqual(r["matched_field"], "municipal_key")
        self.assertTrue(ds.identidad_autorizada_por_binding(r["binding_status"]))

    def test_relacion_oficial_por_guid(self):
        r = ds.elegir_predio_canonico(
            [{"attributes": {"guid": GUID_VALIDO, "nupre": "AFT-OTRO"}}],
            relacionados=["{%s}" % GUID_VALIDO.upper()])
        self.assertEqual(r["binding_status"], ds.BINDING_RELACION)
        self.assertEqual(r["identifier_type"], ds.TIPO_RELACION_OFICIAL)
        self.assertEqual(r["matched_field"], "guid")

    def test_relacion_oficial_que_aporta_un_identificador_canonico(self):
        r = ds.elegir_predio_canonico(self.features, relacionados=["AFT-OTRO"])
        self.assertEqual(r["binding_status"], ds.BINDING_RELACION)
        self.assertEqual(r["identifier_type"], ds.TIPO_NUPRE)
        self.assertEqual(r["matched_field"], "nupre")

    def test_direccion_ligada_por_el_servicio(self):
        r = ds.elegir_predio_canonico(self.features, direccion_ligada="tv 43 # 100 - 50")
        self.assertEqual(r["binding_status"], ds.BINDING_DIRECCION)
        self.assertEqual(r["identifier_type"], ds.TIPO_DIRECCION_LIGADA)
        self.assertEqual(r["matched_field"], "direccion")


# ══════════════════════════════════════════════════════════════════════════════
# C.3 · NEGATIVOS OBLIGATORIOS (nunca comparar tipos incompatibles)
# ══════════════════════════════════════════════════════════════════════════════
class TestBindingTipadoNegativo(unittest.TestCase):

    def test_nupre_con_forma_de_predial_no_liga_contra_numero_predial(self):
        """`nupre="0800…"` NO puede ligar por la columna `numero_predial`."""
        # (a) forma de predial completa → conflicto de tipo declarado vs forma.
        r = ds.elegir_predio_canonico([{"attributes": {"numero_predial": PREDIAL_VALIDO}}],
                                      nupre=PREDIAL_VALIDO)
        self.assertIsNone(r["feature"])
        self.assertEqual(r["binding_status"], ds.SIN_BINDING)
        self.assertEqual(r["identifier_type"], ds.TIPO_DESCONOCIDO)
        self.assertNotEqual(r["binding_status"], ds.BINDING_PREDIAL)
        intento = r["attempted_identifiers"][0]
        self.assertTrue(intento["type_conflict"])
        self.assertEqual(intento["fields_allowed"], [])
        self.assertEqual(intento["matches"], 0)
        # (b) valor corto declarado como NUPRE (forma no concluyente): se compara SOLO
        #     contra las columnas de tipo NUPRE, jamás contra `numero_predial`.
        r2 = ds.elegir_predio_canonico([{"attributes": {"numero_predial": "0800"}}],
                                       nupre="0800")
        self.assertIsNone(r2["feature"])
        self.assertEqual(r2["binding_status"], ds.SIN_BINDING)
        campos = r2["attempted_identifiers"][0]["fields_allowed"]
        self.assertEqual(sorted(campos), ["codigo_homologado", "nupre"])
        self.assertNotIn("numero_predial", campos)
        self.assertNotIn("numero_predial_nacional", campos)

    def test_mismo_texto_en_otra_columna_nunca_liga(self):
        """El vecino con el MISMO texto en otra columna no liga (ida y vuelta)."""
        # NUPRE buscado que sólo existe en la columna numero_predial.
        vecino = {"attributes": {"numero_predial": NUPRE_VALIDO,
                                 "direccion": NUPRE_VALIDO}}
        r = ds.elegir_predio_canonico([vecino], nupre=NUPRE_VALIDO)
        self.assertIsNone(r["feature"])
        self.assertEqual(r["binding_status"], ds.SIN_BINDING)
        # Número predial buscado que sólo existe en la columna nupre.
        r2 = ds.elegir_predio_canonico([{"attributes": {"nupre": PREDIAL_VALIDO}}],
                                       numero_predial=PREDIAL_VALIDO)
        self.assertIsNone(r2["feature"])
        self.assertEqual(r2["binding_status"], ds.SIN_BINDING)
        self.assertNotEqual(r2["binding_status"], ds.BINDING_NUPRE)
        # Y la dirección ligada sólo liga por `direccion`, no por otras columnas.
        r3 = ds.elegir_predio_canonico([{"attributes": {"nupre": "AFT-OTRO"}}],
                                       direccion_ligada="AFT-OTRO")
        self.assertIsNone(r3["feature"])
        self.assertEqual(r3["binding_status"], ds.SIN_BINDING)

    def test_tipo_desconocido_no_liga(self):
        """Referencia sin forma reconocible y sin declaración: no se compara a ciegas."""
        r = ds.elegir_predio_canonico([{"attributes": {"numero_predial": "0042",
                                                       "direccion": "0042"}}],
                                      relacionados=["0042"])
        self.assertIsNone(r["feature"])
        self.assertEqual(r["binding_status"], ds.SIN_BINDING)
        intento = r["attempted_identifiers"][0]
        self.assertEqual(intento["shape_identifier_type"], ds.TIPO_DESCONOCIDO)
        self.assertNotIn("numero_predial", intento["fields_allowed"])
        self.assertNotIn("direccion", intento["fields_allowed"])
        # Valor sin nada comparable: tampoco liga, ni revienta.
        r2 = ds.elegir_predio_canonico([{"attributes": {"nupre": "///"}}], nupre="///")
        self.assertIsNone(r2["feature"])
        self.assertEqual(r2["binding_status"], ds.SIN_BINDING)
        self.assertEqual(r2["attempted_identifiers"][0]["matches"], 0)

    def test_el_numero_predial_anterior_no_autoriza_identidad(self):
        r = ds.elegir_predio_canonico(
            [{"attributes": {"numero_predial_anterior": PREDIAL_VALIDO}}],
            numero_predial=PREDIAL_VALIDO)
        self.assertIsNone(r["feature"])
        self.assertEqual(r["binding_status"], ds.SIN_BINDING)
        self.assertNotIn("numero_predial_anterior",
                         r["attempted_identifiers"][0]["fields_allowed"])

    def test_orden_de_features_no_decide(self):
        """Ninguna permutación cambia el resultado, ni con filas duplicadas."""
        duplicado_a = {"attributes": {"nupre": NUPRE_VALIDO, "extra": "A"}}
        duplicado_b = {"attributes": {"nupre": NUPRE_VALIDO, "extra": "B"}}
        features = [VECINO, duplicado_a, duplicado_b]
        huellas = set()
        for permutacion in itertools.permutations(features):
            r = ds.elegir_predio_canonico(list(permutacion), nupre=NUPRE_VALIDO)
            self.assertEqual(r["binding_status"], ds.BINDING_NUPRE)
            self.assertNotEqual(r["feature"].get("nupre"), "AFT-OTRO")
            huellas.add(_huella(r))
        self.assertEqual(len(huellas), 1, "el resultado depende del orden de features")
        # La fila duplicada se declara como ambigua y NO se elige por posición.
        r = ds.elegir_predio_canonico(features, nupre=NUPRE_VALIDO)
        self.assertTrue(r["ambiguous_match"])
        self.assertEqual(r["matches_found"], 2)

    def test_binding_espacial_nunca_autoriza_identidad(self):
        features = [{"attributes": {"objectid": 7},
                     "geometry": {"x": -74.7813, "y": 10.9685, "spatialReference": 4326}},
                    {"attributes": {"objectid": 8},
                     "geometry": {"x": -74.7813, "y": 10.9685, "spatialReference": 4326}}]
        r = ds.elegir_predio_canonico(features)
        self.assertIsNone(r["feature"])
        self.assertEqual(r["binding_status"], ds.SIN_BINDING)
        self.assertFalse(r["spatial_used_as_identity"])
        self.assertFalse(ds.identidad_autorizada_por_binding(r["binding_status"]))
        self.assertIn(ds.BINDING_ESPACIAL_CONTEXTO, r["reason"])

    def test_sin_features_ni_identificadores_no_inventa_nada(self):
        r = ds.elegir_predio_canonico([], nupre=NUPRE_VALIDO)
        self.assertIsNone(r["feature"])
        self.assertEqual(r["binding_status"], ds.SIN_BINDING)
        self.assertEqual(r["matches_found"], 0)
        self.assertFalse(r["silent_choice"])
        for permutacion in itertools.permutations([VECINO, PROPIO]):
            self.assertEqual(
                ds.elegir_predio_canonico(list(permutacion),
                                          nupre="AFT-INEXISTENTE")["binding_status"],
                ds.SIN_BINDING)


# ══════════════════════════════════════════════════════════════════════════════
# D · PRECEDENCIA DETERMINISTA (independiente del orden de entrada)
# ══════════════════════════════════════════════════════════════════════════════
class TestPrecedenciaDeterminista(unittest.TestCase):

    def _claves_obligatorias(self, r):
        for clave in ("selected", "displaced", "precedence_order", "status",
                      "ambiguous_candidates", "reason", "silent_override"):
            self.assertIn(clave, r, f"falta {clave} en el resultado de precedencia")
        self.assertFalse(r["silent_override"])
        self.assertEqual(r["precedence_order"], list(ds.PRECEDENCIA_RIESGO))

    def test_todas_las_permutaciones_eligen_lo_mismo(self):
        base = [_candidata("NORM_A", ds.CURRENT_NORMATIVE, source_priority=3),
                _candidata("NORM_B", ds.CURRENT_NORMATIVE, source_priority=7),
                _candidata("OFICIAL", ds.CURRENT_OFFICIAL, source_priority=1),
                _candidata("HIST", ds.HISTORICAL_REFERENCE)]
        huellas = set()
        for permutacion in itertools.permutations(base):
            r = ds.resolver_precedencia(list(permutacion))
            self._claves_obligatorias(r)
            self.assertEqual(r["selected"]["source_id"], "NORM_A")
            self.assertEqual(r["status"], ds.PRECEDENCIA_RESUELTA)
            self.assertEqual([d["source_id"] for d in r["displaced"]],
                             ["NORM_B", "OFICIAL", "HIST"])
            self.assertEqual(r["source_priority_used"], 3)
            huellas.add(json.dumps([r["selected_source_id"], r["status"],
                                    [d["source_id"] for d in r["displaced"]]]))
        self.assertEqual(len(huellas), 1, "la precedencia depende del orden de entrada")

    def test_una_sola_current_normative_se_selecciona_sin_prioridad(self):
        r = ds.resolver_precedencia([_candidata("UNICA", ds.CURRENT_NORMATIVE),
                                     _candidata("HIST", ds.HISTORICAL_REFERENCE)])
        self.assertEqual(r["selected"]["source_id"], "UNICA")
        self.assertEqual(r["status"], ds.PRECEDENCIA_RESUELTA)
        self.assertIsNone(r["source_priority_used"])
        self.assertEqual(r["selected_tier"], ds.CURRENT_NORMATIVE)
        self.assertEqual([d["source_id"] for d in r["displaced"]], ["HIST"])

    def test_empate_de_prioridad_es_ambiguo_en_cualquier_orden(self):
        base = [_candidata("NORM_A", ds.CURRENT_NORMATIVE, source_priority=5),
                _candidata("NORM_B", ds.CURRENT_NORMATIVE, source_priority=5),
                _candidata("OFICIAL", ds.CURRENT_OFFICIAL, source_priority=0)]
        for permutacion in itertools.permutations(base):
            r = ds.resolver_precedencia(list(permutacion))
            self.assertIsNone(r["selected"])
            self.assertEqual(r["status"], ds.PRECEDENCIA_AMBIGUA)
            self.assertEqual(sorted(c["source_id"] for c in r["ambiguous_candidates"]),
                             ["NORM_A", "NORM_B"])
            # No se cae en la capa oficial: una vigente ambigua no se sustituye.
            self.assertEqual(r["ambiguous_tier"], ds.CURRENT_NORMATIVE)
            self.assertEqual(sorted(d["source_id"] for d in r["displaced"]),
                             ["NORM_A", "NORM_B", "OFICIAL"])
            self.assertIn("source_priority", r["reason"])

    def test_prioridad_no_declarada_es_ambiguo(self):
        base = [_candidata("NORM_A", ds.CURRENT_NORMATIVE, source_priority=1),
                _candidata("NORM_B", ds.CURRENT_NORMATIVE)]
        for permutacion in itertools.permutations(base):
            r = ds.resolver_precedencia(list(permutacion))
            self.assertIsNone(r["selected"])
            self.assertEqual(r["status"], ds.PRECEDENCIA_AMBIGUA)
            self.assertEqual(sorted(c["source_id"] for c in r["ambiguous_candidates"]),
                             ["NORM_A", "NORM_B"])

    def test_source_priority_rompe_el_empate_de_forma_estable(self):
        base = [_candidata("NORM_ALTA", ds.CURRENT_NORMATIVE, source_priority="20"),
                _candidata("NORM_BAJA", ds.CURRENT_NORMATIVE, source_priority=10)]
        for permutacion in itertools.permutations(base):
            r = ds.resolver_precedencia(list(permutacion))
            self.assertEqual(r["selected"]["source_id"], "NORM_BAJA")   # menor = prioridad
            self.assertEqual(r["source_priority_used"], 10)
            self.assertEqual([d["source_id"] for d in r["displaced"]], ["NORM_ALTA"])

    def test_sin_current_normative_usa_current_official_con_la_misma_regla(self):
        una = ds.resolver_precedencia([_candidata("OFICIAL", ds.CURRENT_OFFICIAL),
                                       _candidata("HIST", ds.HISTORICAL_REFERENCE)])
        self.assertEqual(una["selected"]["source_id"], "OFICIAL")
        self.assertEqual(una["selected_tier"], ds.CURRENT_OFFICIAL)
        self.assertEqual(una["status"], ds.PRECEDENCIA_RESUELTA)
        base = [_candidata("OFICIAL_A", ds.CURRENT_OFFICIAL, source_priority=9),
                _candidata("OFICIAL_B", ds.CURRENT_OFFICIAL, source_priority=4)]
        for permutacion in itertools.permutations(base):
            r = ds.resolver_precedencia(list(permutacion))
            self.assertEqual(r["selected"]["source_id"], "OFICIAL_B")
        empate = ds.resolver_precedencia([_candidata("OFICIAL_A", ds.CURRENT_OFFICIAL),
                                          _candidata("OFICIAL_B", ds.CURRENT_OFFICIAL)])
        self.assertIsNone(empate["selected"])
        self.assertEqual(empate["status"], ds.PRECEDENCIA_AMBIGUA)
        self.assertEqual(empate["ambiguous_tier"], ds.CURRENT_OFFICIAL)

    def test_sin_capa_vigente_ni_oficial_es_sin_dato(self):
        historicas = [_candidata("HIST_71", ds.HISTORICAL_REFERENCE),
                      _candidata("HIST_75", ds.HISTORICAL_REFERENCE),
                      _candidata("CONTEXTUAL", "CONTEXTUAL_REFERENCE")]
        for permutacion in itertools.permutations(historicas):
            r = ds.resolver_precedencia(list(permutacion))
            self._claves_obligatorias(r)
            self.assertIsNone(r["selected"])
            self.assertEqual(r["status"], ds.SIN_DATO)
            self.assertIn("SIN DATO", r["reason"])
            # Las históricas se conservan SOLO como referencia comparativa.
            self.assertEqual(sorted(c["source_id"] for c in r["historical_reference"]),
                             ["HIST_71", "HIST_75"])
            self.assertEqual(sorted(d["source_id"] for d in r["displaced"]),
                             ["CONTEXTUAL", "HIST_71", "HIST_75"])
            self.assertFalse(any(d["source_id"].startswith("HIST")
                                 for d in [r["selected"]] if d))
        vacio = ds.resolver_precedencia([])
        self.assertIsNone(vacio["selected"])
        self.assertEqual(vacio["status"], ds.SIN_DATO)
        self.assertEqual(vacio["displaced"], [])

    def test_una_historica_jamas_se_asciende_aunque_venga_primero(self):
        r = ds.resolver_precedencia([_candidata("HIST", ds.HISTORICAL_REFERENCE),
                                     _candidata("VIGENTE", ds.CURRENT_NORMATIVE)])
        self.assertEqual(r["selected"]["source_id"], "VIGENTE")
        self.assertNotEqual(r["selected"]["precedence"], ds.HISTORICAL_REFERENCE)
        self.assertFalse(r["silent_override"])


# ══════════════════════════════════════════════════════════════════════════════
# E · RIESGO BARRANQUILLA (73/77/81 vigentes · 71/75/79 referencia histórica)
# ══════════════════════════════════════════════════════════════════════════════
class TestRiesgoBarranquilla(unittest.TestCase):

    def setUp(self):
        self.candidatas = ds.candidatos_riesgo_barranquilla()

    def _por_id(self, source_id):
        return next(c for c in self.candidatas if c["source_id"] == source_id)

    def test_declara_vigentes_e_historicas_con_prioridad_explicita(self):
        vigentes = [c for c in self.candidatas if c["precedence"] == ds.CURRENT_NORMATIVE]
        historicas = [c for c in self.candidatas
                      if c["precedence"] == ds.HISTORICAL_REFERENCE]
        self.assertEqual(sorted(c["layer_id"] for c in vigentes), [73, 77, 81])
        self.assertEqual(sorted(c["layer_id"] for c in historicas), [71, 75, 79])
        for c in vigentes:
            self.assertEqual(c["legal_or_normative_context"], ds.NORMA_POT_2024)
            self.assertIsInstance(c["source_priority"], int)
        for c in historicas:
            self.assertIsInstance(c["source_priority"], int)
            self.assertIn(c["referencia_de"],
                          [v["source_id"] for v in vigentes])
        prioridades = [c["source_priority"] for c in self.candidatas]
        self.assertEqual(len(prioridades), len(set(prioridades)))
        self.assertEqual(self._por_id("POT_BAQ_REMOCION_2024")["layer_id"], 73)
        self.assertEqual(self._por_id("POT_BAQ_INUNDACION_2024")["layer_id"], 77)
        self.assertEqual(self._por_id("POT_BAQ_RIESGO_2024")["layer_id"], 81)

    def test_resultado_determinista_en_todas_las_permutaciones(self):
        huellas = set()
        for permutacion in itertools.permutations(self.candidatas):
            r = ds.resolver_precedencia(list(permutacion))
            self.assertEqual(r["status"], ds.PRECEDENCIA_RESUELTA)
            self.assertEqual(r["selected_tier"], ds.CURRENT_NORMATIVE)
            huellas.add(json.dumps([r["selected_source_id"], r["status"],
                                    [c["source_id"] for c in r["displaced"]],
                                    [c["source_id"] for c in r["historical_reference"]]],
                                   sort_keys=True))
        self.assertEqual(len(huellas), 1, "el resultado depende del orden de las candidatas")

    def test_ninguna_historica_se_selecciona(self):
        historicas = {c["source_id"] for c in self.candidatas
                      if c["precedence"] == ds.HISTORICAL_REFERENCE}
        for permutacion in itertools.permutations(self.candidatas):
            r = ds.resolver_precedencia(list(permutacion))
            self.assertNotIn(r["selected_source_id"], historicas)
            self.assertEqual(r["selected_source_id"], "POT_BAQ_REMOCION_2024")
            self.assertNotIn(r["selected_source_id"],
                             [c["source_id"] for c in r["ambiguous_candidates"]])

    def test_cada_amenaza_resuelve_con_su_propia_capa_vigente(self):
        esperado = {"REMOCION_EN_MASA": ("POT_BAQ_REMOCION_2024", "POT_BAQ_REMOCION_HIST"),
                    "INUNDACION": ("POT_BAQ_INUNDACION_2024", "POT_BAQ_INUNDACION_HIST"),
                    "RIESGO_MULTIPLE": ("POT_BAQ_RIESGO_2024", "POT_BAQ_RIESGO_HIST")}
        for amenaza, (vigente, historica) in esperado.items():
            grupo = ds.candidatos_riesgo_barranquilla(amenaza=amenaza)
            self.assertEqual(sorted(c["source_id"] for c in grupo),
                             sorted([vigente, historica]))
            for permutacion in itertools.permutations(grupo):
                r = ds.resolver_precedencia(list(permutacion))
                self.assertEqual(r["selected_source_id"], vigente)
                self.assertEqual([d["source_id"] for d in r["displaced"]], [historica])
                self.assertEqual(r["status"], ds.PRECEDENCIA_RESUELTA)

    def test_con_solo_historicas_es_sin_dato(self):
        solo_historicas = [c for c in self.candidatas
                           if c["precedence"] == ds.HISTORICAL_REFERENCE]
        r = ds.resolver_precedencia(solo_historicas)
        self.assertEqual(r["status"], ds.SIN_DATO)
        self.assertIsNone(r["selected"])
        self.assertEqual(len(r["historical_reference"]), 3)
        self.assertIn("SIN DATO", r["reason"])

    def test_no_muta_el_estado_del_modulo(self):
        primera = ds.candidatos_riesgo_barranquilla()
        primera[0]["source_priority"] = -999
        primera[0]["precedence"] = ds.HISTORICAL_REFERENCE
        segunda = ds.candidatos_riesgo_barranquilla()
        self.assertEqual(segunda[0]["source_priority"], 10)
        self.assertEqual(segunda[0]["precedence"], ds.CURRENT_NORMATIVE)
        self.assertEqual(ds.resolver_precedencia(segunda)["selected_source_id"],
                         "POT_BAQ_REMOCION_2024")


if __name__ == "__main__":
    unittest.main()
