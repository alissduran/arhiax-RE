# -*- coding: utf-8 -*-
"""SOURCE PACK v1.0-R1 — pruebas BLOQUEANTES de los requisitos F (mercado) y G (licencias).

Todo aquí corre OFFLINE (sin red):
  · F. **`LONJA_MARKET_BAQ` NO es una fuente de datos** (decisión de producto: la Lonja no
    aporta datos a DICTUS). Es un IDENTIFICADOR HISTÓRICO sellado que no se renombra: vive
    fuera del Source Registry como aliado institucional, con `product_role=NOT_A_SOURCE`. La
    consulta de mercado es FAIL-CLOSED: declara la ausencia (`SOURCE_UNAVAILABLE` /
    `DATOS_AUSENTES`) y nunca sirve ni sustituye un valor. El **valor declarado por la
    corrida** (constante del artefacto local de metodología) viaja ETIQUETADO y se contrasta
    con la tabla derivada y con el Golden 040-646406 (que resuelve el PARÁMETRO, no la
    fuente).
  · G. Licencias: bloque canónico completo por fuente, términos descargados/hasheados
    (evidencia registrada, no consultada en la prueba), Mapillary con lo que le falta
    para `VERIFIED`, Google fail-closed (`can_persist=False`, `can_embed=False`) y test
    negativo de incrustación (`can_embed=False` ⇒ ningún flujo incrusta).

Los valores de las tablas de PRUEBA (fixtures) son datos de laboratorio: NO son datos
del producto y nunca se mezclan con la tabla versionada real.
"""
import hashlib
import json
import shutil
import sys
import unittest
from itertools import count
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import dictus_sources as ds  # noqa: E402
import market_context as mc  # noqa: E402
import market_sources as ms  # noqa: E402
import source_licenses as sl  # noqa: E402

RUTA_TABLA = ROOT / "docs" / "source_pack" / "lonja_market_baq_v1.json"
RUTA_RUN_STATE = (ROOT / "docs" / "forensics" / "040-646406" / "dictus_2b"
                  / "DICTUS_RUN_STATE_040-646406.json")
RUTA_REGISTRO = ROOT / "docs" / "source_pack" / "barranquilla_sources_v1.json"

_CONTADOR_TMP = count()


def _tmpdir(caso) -> Path:
    """Directorio temporal DENTRO del workspace (el TMP del sistema no es escribible)."""
    carpeta = ROOT / "tmp" / f"source_pack_market_{__import__('os').getpid()}_{next(_CONTADOR_TMP)}"
    carpeta.mkdir(parents=True, exist_ok=True)
    caso.addCleanup(shutil.rmtree, carpeta, ignore_errors=True)
    return carpeta


def _fila(caso, *, sector, city="ciudad-prueba", aliases=None, typology=None, regime=None,
          use=None, area_min=None, area_max=None, valor=1_000_000, low=None, high=None,
          desde="2026-01-01", hasta="2026-12-31", sample=None, fuente=None):
    """Fila con el contrato COMPLETO de `market_sources.CONTRATO_FILA` (fixture de prueba)."""
    return {
        "city": city, "sector": sector, "neighborhood_aliases": list(aliases or []),
        "property_typology": typology, "property_regime": regime, "economic_use": use,
        "area_band": {"min": area_min, "max": area_max},
        "value_per_m2": valor, "range_low": low, "range_high": high,
        "effective_from": desde, "effective_to": hasta, "sample_size": sample,
        "methodology_version": "fixture-1.0", "source_version": "fixture/1.0",
        "source_hash": ds.hash_canonico([sector, valor]),
        "fuente_declarada": fuente,
    }


def _tabla_fixture(caso, filas, *, version="fixture-table/1.0.0"):
    """Escribe una tabla de PRUEBA (laboratorio) y la carga con el cargador REAL."""
    ruta = _tmpdir(caso) / "tabla_fixture.json"
    contenido = {
        "source_id": ms.SOURCE_ID, "product_role": ms.PRODUCT_ROLE,
        "authority_class": ms.AUTHORITY_CLASS, "table_version": version,
        "methodology_version": "fixture-1.0", "source_version": "fixture/1.0",
        "methodology_sha256": None, "generated_at": None, "vigencia": {},
        "derivation": {"metodo": "FIXTURE_DE_PRUEBA"}, "rows": filas,
        "source_hash": ds.hash_canonico(filas),
    }
    ruta.write_text(json.dumps(contenido, ensure_ascii=False, indent=1), encoding="utf-8")
    return ms.cargar_tabla(ruta)


# Fixture de laboratorio: sector con tilde + alias de barrio + restricciones declaradas
# (tipología/régimen/uso/banda) + un sector aislado con banda estricta.
def _fixture_basico(caso):
    return _tabla_fixture(caso, [
        _fila(caso, sector="Miramar Alto", aliases=["Miramar"], valor=7_000_000,
              low=6_000_000, high=8_000_000),
        _fila(caso, sector="Centro Histórico", typology="Apartamento",
              regime="Propiedad Horizontal", use="Habitacional", area_min=40, area_max=80,
              valor=4_000_000, low=3_500_000, high=4_500_000, sample=12),
        _fila(caso, sector="Solo Banda", area_min=0, area_max=50, valor=1_500_000),
    ])


# Fixture de laboratorio para AMBIGUEDAD: dos filas que casan con el mismo término y
# ninguna restricción declarada que permita decidir.
def _fixture_ambiguo(caso):
    return _tabla_fixture(caso, [
        _fila(caso, sector="Sector Gemelo", valor=5_000_000),
        _fila(caso, sector="Sector Gemelo", valor=6_000_000),
    ], version="fixture-table/ambiguo/1.0.0")


# ══════════════════════════════════════════════════════════════════════════════
# F · LA PIEZA **NO ES UNA FUENTE** (decisión de producto)
# ══════════════════════════════════════════════════════════════════════════════
class TestNoEsFuente(unittest.TestCase):

    def test_identidad_historica_del_identificador_sellado(self):
        # El identificador NO se renombra (viaja en hashes), pero se declara lo que es.
        self.assertEqual(ms.SOURCE_ID, "LONJA_MARKET_BAQ")
        self.assertEqual(ms.SOURCE_ID_HISTORICO, "LONJA_MARKET_BAQ")
        self.assertEqual(ms.PRODUCT_ROLE, "NOT_A_SOURCE")
        self.assertEqual(ms.PRODUCT_ROLE_HISTORICO, "CORE_MARKET")
        self.assertFalse(ms.ES_FUENTE_DE_DATOS)
        self.assertFalse(ms.EN_SOURCE_REGISTRY)
        self.assertFalse(ms.APORTA_DATOS_A_DICTUS)
        # La identidad declarada ya no afirma una institución proveedora ni una Lonja.
        for texto in (ms.SOURCE_NAME, ms.INSTITUTION):
            self.assertNotIn("Lonja", texto)
            self.assertNotIn("LONJA", texto)
        self.assertIn("sin institución proveedora verificada", ms.INSTITUTION)

    def test_autoridad_declarada_no_es_oficial_y_es_normativa(self):
        # Sostiene la metodología de valoración (normativa), NUNCA una capa oficial.
        self.assertIn(ms.AUTHORITY_CLASS, ds.CLASES_NORMATIVAS)
        self.assertNotEqual(ms.AUTHORITY_CLASS, ds.AUTORITATIVA_OFICIAL)
        self.assertTrue(ms.ES_AUTORIDAD_NORMATIVA)

    def test_la_pieza_esta_fuera_del_registro_y_declarada_como_no_fuente(self):
        registro = json.loads(RUTA_REGISTRO.read_text(encoding="utf-8"))
        fuentes = registro["sources"]
        self.assertNotIn(ms.SOURCE_ID, fuentes, "no puede ser `source_id` del registro")
        self.assertFalse(ms.en_source_registry())
        no_fuentes = registro["no_fuentes_institucionales"]
        lonja = no_fuentes["aliados"]["LONJA_BAQ"]
        self.assertEqual(lonja["source_id_historico"], ms.SOURCE_ID)
        self.assertFalse(lonja["es_fuente_de_datos"])
        self.assertFalse(lonja["en_source_registry"])
        self.assertEqual(lonja["product_role"], ms.PRODUCT_ROLE)
        self.assertTrue(lonja["retirada_del_registro"])
        self.assertIsNone(lonja["authority_class"])
        mercado = no_fuentes["valor_de_mercado"]
        self.assertFalse(mercado["es_fuente_de_datos"])
        self.assertFalse(mercado["fuente_externa_verificable"])
        self.assertEqual(mercado["etiqueta"], "parámetros declarados por la corrida")

    def test_la_pieza_no_toca_la_red(self):
        """F se resuelve con la tabla local: no hay transporte de red en el módulo."""
        fuente = Path(ms.__file__).read_text(encoding="utf-8")
        for prohibido in ("urllib", "requests", "socket", "http.client"):
            self.assertNotIn(prohibido, fuente, f"mercado no debe usar red ({prohibido})")

    def test_estados_de_mercado_se_dictan_al_vocabulario_cerrado(self):
        self.assertEqual(set(ms.ESTADOS_MERCADO) - set(ms.MAPA_ESTADOS), set())
        for estado, cerrado in ms.MAPA_ESTADOS.items():
            self.assertIn(cerrado, ds.ESTADOS, f"{estado} → {cerrado} fuera de §27")
        # La ambigüedad NUNCA se degrada a «no hay mercado».
        self.assertNotEqual(ms.MAPA_ESTADOS[ms.AMBIGUO], ds.SIN_COINCIDENCIA)
        self.assertNotEqual(ms.MAPA_ESTADOS[ms.DATOS_AUSENTES], ds.SIN_COINCIDENCIA)


# ══════════════════════════════════════════════════════════════════════════════
# F · TABLA VERSIONADA (sin valores pegados a mano)
# ══════════════════════════════════════════════════════════════════════════════
class TestTablaVersionada(unittest.TestCase):

    def test_tabla_existe_y_verifica_su_hash(self):
        tabla = ms.cargar_tabla()
        self.assertEqual(tabla["estado"], ms.TABLA_OK, tabla["motivo"])
        self.assertTrue(tabla["hash_verificado"])
        self.assertEqual(tabla["hash_declarado"], tabla["hash_recalculado"])
        self.assertGreaterEqual(len(tabla["rows"]), 1)

    def test_cada_fila_cumple_el_contrato(self):
        for fila in ms.cargar_tabla()["rows"]:
            for campo in ms.CONTRATO_FILA:
                self.assertIn(campo, fila, f"la fila {fila.get('sector')} no declara {campo}")

    def test_valores_derivados_del_producto_y_no_inventados(self):
        """La tabla versionada es EXACTAMENTE la que se deriva del artefacto del producto."""
        en_disco = ms.cargar_tabla()["rows"]
        derivada = ms.derivar_tabla_desde_producto()["rows"]
        self.assertEqual(ds.hash_canonico(en_disco), ds.hash_canonico(derivada))
        metodologia = json.loads(json.dumps(
            mc._load_lonja().get("valor_suelo_por_sector") or {}, default=str))
        for fila in en_disco:
            declarado = metodologia[fila["sector"]]
            self.assertEqual(fila["value_per_m2"], declarado["valor_central_m2"])
            self.assertEqual(fila["range_low"], declarado["rango_min_m2"])
            self.assertEqual(fila["range_high"], declarado["rango_max_m2"])
            self.assertEqual(fila["source_hash"], mc.market_methodology()["sha256"])
            self.assertEqual(fila["methodology_version"],
                             mc.market_methodology()["version"])

    def test_la_tabla_declara_los_atributos_ausentes_del_producto(self):
        tabla = ms.cargar_tabla()
        for atributo in ("neighborhood_aliases", "property_typology", "property_regime",
                         "economic_use", "area_band", "sample_size"):
            self.assertIn(atributo, tabla["atributos_ausentes"])
            for fila in tabla["rows"]:
                self.assertIn(atributo, fila["atributos_ausentes_en_la_fila"])
        # Ausente = `null` declarado, NUNCA un valor supuesto.
        for fila in tabla["rows"]:
            self.assertIsNone(fila["property_typology"])
            self.assertIsNone(fila["economic_use"])
            self.assertIsNone(fila["sample_size"])
            self.assertEqual(fila["neighborhood_aliases"], [])

    def test_tabla_ausente_se_declara_sin_inventar(self):
        tabla = ms.cargar_tabla(_tmpdir(self) / "no_existe.json")
        self.assertEqual(tabla["estado"], ms.TABLA_AUSENTE)
        self.assertEqual(tabla["rows"], [])
        self.assertTrue(tabla["motivo"])
        resultado = ms.consultar_mercado(sector="Miramar", fecha_corrida="2026-06-01",
                                        tabla=tabla)
        self.assertEqual(resultado["status"], ds.FUENTE_NO_DISPONIBLE)
        self.assertIsNone(resultado["payload_normalized"]["value_per_m2"])

    def test_tabla_manipulada_no_se_usa(self):
        datos = json.loads(RUTA_TABLA.read_text(encoding="utf-8"))
        datos["rows"][0]["value_per_m2"] = 999_999_999      # valor pegado a mano
        ruta = _tmpdir(self) / "tabla_manipulada.json"
        ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
        tabla = ms.cargar_tabla(ruta)
        self.assertEqual(tabla["estado"], ms.TABLA_INCOMPLETA)
        self.assertFalse(tabla["hash_verificado"])
        self.assertIn("source_hash", tabla["motivo"])
        resultado = ms.consultar_mercado(sector="Miramar", tabla=tabla)
        # El estado CERRADO es el de la doctrina (la pieza no es fuente) y el estado de
        # MERCADO declara el problema de la tabla: en ningún caso se usa el valor pegado.
        self.assertEqual(resultado["status"], ds.FUENTE_NO_DISPONIBLE)
        self.assertEqual(resultado["payload_normalized"]["market_status"],
                         ms.DATOS_AUSENTES)
        self.assertIsNone(resultado["payload_normalized"]["value_per_m2"])
        self.assertIsNone(resultado["payload_normalized"]["valor_declarado_por_la_corrida"]
                          ["value_per_m2"])

    def test_tabla_sin_contrato_por_fila_no_se_usa(self):
        filas = ms.derivar_tabla_desde_producto()["rows"]
        for fila in filas:
            fila.pop("sample_size")
        ruta = _tmpdir(self) / "tabla_incompleta.json"
        ruta.write_text(json.dumps({"rows": filas, "source_hash": ds.hash_canonico(filas)}),
                        encoding="utf-8")
        tabla = ms.cargar_tabla(ruta)
        self.assertEqual(tabla["estado"], ms.TABLA_INCOMPLETA)
        self.assertIn("sample_size", tabla["campos_faltantes"])


# ══════════════════════════════════════════════════════════════════════════════
# F · RESOLUCIÓN AUTOMÁTICA (sector · alias · tipología · régimen · uso · banda)
# ══════════════════════════════════════════════════════════════════════════════
class TestResolucionAutomatica(unittest.TestCase):

    def setUp(self):
        self.tabla = _fixture_basico(self)

    def test_normaliza_acentos_mayusculas_y_separadores(self):
        r = ms.resolver_sector(tabla=self.tabla, sector="CENTRO HISTORICO",
                               typology="apartamento", regime="propiedad horizontal",
                               economic_use="habitacional", area_m2=60)
        self.assertEqual(r["estado"], ms.RESUELTO)
        self.assertEqual(r["sector"], "Centro Histórico")
        self.assertEqual(r["match_type"], ms.MATCH_NORMALIZED_EXACT)
        self.assertEqual(r["fila"]["value_per_m2"], 4_000_000)

    def test_resuelve_por_alias_de_barrio(self):
        r = ms.resolver_sector(tabla=self.tabla, barrio="miramar")
        self.assertEqual(r["estado"], ms.RESUELTO)
        self.assertEqual(r["match_type"], ms.MATCH_ALIAS)
        self.assertEqual(r["alias_usado"], "Miramar")
        self.assertEqual(r["fila"]["value_per_m2"], 7_000_000)
        # `_` y espacio son el mismo separador
        self.assertEqual(ms.resolver_sector(tabla=self.tabla,
                                            sector="MIRAMAR_ALTO")["estado"], ms.RESUELTO)

    def test_resuelve_vacio_sin_termino_no_elige_fila(self):
        r = ms.resolver_sector(tabla=self.tabla)
        self.assertEqual(r["estado"], ms.DATOS_AUSENTES)
        self.assertIsNone(r["fila"])
        self.assertTrue(r["motivos"])

    def test_sector_inexistente_es_no_match_sin_valor(self):
        r = ms.resolver_sector(tabla=self.tabla, sector="Sector Inexistente")
        self.assertEqual(r["estado"], ms.SIN_COINCIDENCIA)
        self.assertEqual(r["match_type"], ms.MATCH_NO_MATCH)
        self.assertIsNone(r["fila"])
        self.assertEqual(r["datos_ausentes"], [])
        motivos = " ".join(r["motivos"])
        self.assertIn("no resuelve ninguna fila", motivos)
        self.assertIn("valor por defecto", motivos)

    def test_ambiguedad_devuelve_ambiguous_con_candidatos(self):
        tabla = _fixture_ambiguo(self)
        r = ms.resolver_sector(tabla=tabla, sector="Sector Gemelo")
        self.assertEqual(r["estado"], ms.AMBIGUO)
        self.assertIsNone(r["fila"], "una ambigüedad NUNCA elige fila en silencio")
        self.assertEqual(len(r["candidatos"]), 2)
        self.assertEqual({c["sector"] for c in r["candidatos"]}, {"Sector Gemelo"})
        for candidato in r["candidatos"]:
            self.assertNotIn("fila", candidato)
        self.assertIn("AMBIGUOUS", " ".join(r["motivos"]))
        # La ambigüedad no se degrada: no es «sin coincidencia».
        self.assertNotEqual(r["estado"], ms.SIN_COINCIDENCIA)

    def test_restriccion_exigida_por_la_fila_se_declara_y_no_se_rellena(self):
        # La fila de "Centro Histórico" exige área 40–80, tipología, régimen y uso; la
        # consulta NO los declara ⇒ esa fila se DESCARTA con motivo y no hay valor.
        r = ms.resolver_sector(tabla=self.tabla, sector="Centro Historico")
        self.assertEqual(r["estado"], ms.SIN_COINCIDENCIA)
        self.assertIsNone(r["fila"])
        self.assertEqual([d["sector"] for d in r["descartadas"]], ["Centro Histórico"])
        motivos = " ".join(r["descartadas"][0]["motivos"])
        self.assertIn("no la declara", motivos)
        self.assertIn("banda de área", motivos)
        self.assertIn("no puede afirmarse coincidencia", motivos)

    def test_banda_de_area_filtra_y_descarta_fuera_de_rango(self):
        dentro = ms.resolver_sector(tabla=self.tabla, sector="Centro Historico",
                                    typology="Apartamento", regime="Propiedad Horizontal",
                                    economic_use="Habitacional", area_m2=60)
        self.assertEqual(dentro["estado"], ms.RESUELTO)
        self.assertEqual(dentro["fila"]["value_per_m2"], 4_000_000)
        fuera = ms.resolver_sector(tabla=self.tabla, sector="Solo Banda", area_m2=500)
        self.assertEqual(fuera["estado"], ms.SIN_COINCIDENCIA)
        self.assertIsNone(fuera["fila"])
        self.assertIn("fuera de la banda declarada",
                      " ".join(fuera["descartadas"][0]["motivos"]))
        self.assertEqual(ms.resolver_sector(tabla=self.tabla, sector="Solo Banda",
                                            area_m2=30)["estado"], ms.RESUELTO)

    def test_los_atributos_no_declarados_por_la_tabla_se_listan(self):
        r = ms.resolver_sector(tabla=self.tabla, barrio="miramar")
        for atributo in ("property_typology", "property_regime", "economic_use",
                         "area_band", "sample_size"):
            self.assertIn(atributo, r["datos_ausentes"])
            self.assertIn(atributo, r["atributos_no_declarados_por_la_tabla"])
        # Una fila que SÍ declara atributos no los reporta como ausentes.
        r2 = ms.resolver_sector(tabla=self.tabla, sector="Solo Banda", area_m2=30)
        self.assertNotIn("area_band", r2["datos_ausentes"])
        self.assertIn("property_typology", r2["datos_ausentes"])


# ══════════════════════════════════════════════════════════════════════════════
# F · CONSULTA DE MERCADO (SourceResult §27 · fail-closed por doctrina)
# ══════════════════════════════════════════════════════════════════════════════
class TestConsultarMercado(unittest.TestCase):

    def test_no_sirve_el_valor_como_dato_de_fuente_y_declara_la_ausencia(self):
        r = ms.consultar_mercado(sector="Miramar", fecha_corrida="2026-06-01",
                                 area_m2=58.75)
        self.assertIn(r["status"], ds.ESTADOS)
        # DOCTRINA: la pieza no está en el Source Registry ⇒ la fuente no está disponible.
        self.assertEqual(r["status"], ds.FUENTE_NO_DISPONIBLE)
        self.assertNotEqual(r["status"], ds.SIN_COINCIDENCIA)
        self.assertEqual(r["source_id"], ms.SOURCE_ID)
        prov = r["provenance"]
        for campo in ("source_id", "authority_class", "product_role", "source_version",
                      "methodology_version", "methodology_sha256", "source_hash",
                      "source_hash_verificado", "effective_from", "effective_to",
                      "fecha_corrida", "vigencia_ok", "vigencia_motivo", "match_type"):
            self.assertIn(campo, prov, f"falta {campo} en la procedencia de mercado")
        self.assertEqual(prov["authority_class"], ds.AUTORITATIVA_CONTRACTUAL)
        self.assertEqual(prov["product_role"], ms.PRODUCT_ROLE)
        self.assertEqual(prov["product_role"], "NOT_A_SOURCE")
        self.assertFalse(prov["es_fuente_de_datos"])
        self.assertFalse(prov["en_source_registry"])
        self.assertTrue(prov["source_hash_verificado"])
        self.assertTrue(prov["procedencia_declarada"]["fuente_externa_verificable"] is False)
        self.assertTrue(r["raw_hash"])
        # No se escribe crudo: `raw/` queda intocable.
        self.assertFalse(r["raw_persisted"])
        self.assertIsNone(r["raw_path"])
        self.assertIn("FUENTE NO DISPONIBLE", r["detail"])
        # La procedencia declarada NO atribuye el valor a la Lonja. (El identificador
        # sellado `LONJA_MARKET_BAQ` y la explicación de la doctrina sí pueden nombrarla:
        # justamente para decir que NO es una fuente.)
        self.assertNotIn("Lonja", prov["source_name"])
        self.assertNotIn("Lonja", prov["institution"])
        self.assertNotIn("Lonja", prov["license_or_terms"])
        self.assertNotIn("Lonja", r["payload_normalized"]["fuente_declarada"])

    def test_el_parametro_declarado_por_la_corrida_viaja_etiquetado(self):
        r = ms.consultar_mercado(sector="Miramar", fecha_corrida="2026-06-01")
        payload = r["payload_normalized"]
        # El valor NO se sirve como dato de fuente…
        self.assertIsNone(payload["value_per_m2"])
        self.assertIsNone(payload["range_low"])
        self.assertIsNone(payload["range_high"])
        self.assertFalse(ms.mercado_utilizable(r))
        # …pero no se oculta: se declara como PARÁMETRO de la corrida, con su etiqueta.
        declarado = payload["valor_declarado_por_la_corrida"]
        self.assertFalse(declarado["es_fuente_de_datos"])
        self.assertEqual(declarado["etiqueta"], "parámetros declarados por la corrida")
        self.assertEqual(declarado["value_per_m2"], 6_800_000)
        self.assertEqual((declarado["range_low"], declarado["range_high"]),
                         (5_500_000, 8_000_000))
        self.assertEqual(declarado["sector"], "Miramar")
        self.assertEqual(payload["market_status"], ms.RESUELTO)
        # La fuente declarada por el artefacto local ya no atribuye nada a la Lonja.
        self.assertNotIn("Lonja", json.dumps(declarado, ensure_ascii=False))

    def test_vigencia_vencida_se_declara_aunque_el_parametro_exista(self):
        r = ms.consultar_mercado(sector="Miramar", fecha_corrida="2026-09-28")
        self.assertEqual(r["status"], ds.FUENTE_NO_DISPONIBLE)
        payload = r["payload_normalized"]
        self.assertFalse(payload["vigencia_ok"])              # …pero NO está vigente
        self.assertEqual(payload["vigencia_estado"], ms.VENCIDA)
        self.assertIn("VIGENCIA VENCIDA", r["detail"])
        self.assertFalse(payload["valor_declarado_por_la_corrida"]["vigencia_ok"])
        self.assertFalse(ms.mercado_utilizable(r))

    def test_sin_fecha_de_corrida_la_vigencia_no_se_afirma(self):
        r = ms.consultar_mercado(sector="Miramar")
        self.assertFalse(r["payload_normalized"]["vigencia_ok"])
        self.assertEqual(r["payload_normalized"]["vigencia_estado"], ms.VIGENCIA_DESCONOCIDA)
        self.assertFalse(ms.mercado_utilizable(r))

    def test_sin_fechas_en_la_fila_la_vigencia_no_se_afirma(self):
        tabla = _tabla_fixture(self, [_fila(self, sector="Sin Fechas", desde=None,
                                            hasta=None, valor=2_000_000)])
        r = ms.consultar_mercado(sector="Sin Fechas", fecha_corrida="2026-06-01",
                                 tabla=tabla)
        self.assertEqual(r["status"], ds.FUENTE_NO_DISPONIBLE)
        self.assertFalse(r["payload_normalized"]["vigencia_ok"])
        self.assertIn("effective_from", r["payload_normalized"]["vigencia_motivo"])

    def test_no_match_no_inventa_valor(self):
        r = ms.consultar_mercado(sector="Sector Inexistente", fecha_corrida="2026-06-01")
        payload = r["payload_normalized"]
        # El estado de mercado sigue dictándose aparte (no se degrada a «no hay mercado»
        # ni a NO_MATCH del contrato) y el estado CERRADO es la doctrina: sin fuente.
        self.assertEqual(payload["market_status"], ms.SIN_COINCIDENCIA)
        self.assertEqual(r["status"], ds.FUENTE_NO_DISPONIBLE)
        self.assertNotEqual(r["status"], ds.SIN_COINCIDENCIA)
        self.assertIsNone(payload["value_per_m2"])
        self.assertIsNone(payload["range_low"])
        self.assertIsNone(payload["valor_declarado_por_la_corrida"]["value_per_m2"])
        self.assertTrue(r["detail"])

    def test_ambiguedad_no_es_no_match_ni_valor_elegido(self):
        tabla = _fixture_ambiguo(self)
        r = ms.consultar_mercado(barrio="Sector Gemelo", fecha_corrida="2026-06-01",
                                 tabla=tabla)
        payload = r["payload_normalized"]
        self.assertEqual(payload["market_status"], ms.AMBIGUO)
        self.assertNotEqual(r["status"], ds.SIN_COINCIDENCIA)
        self.assertEqual(len(payload["candidatos"]), 2)
        self.assertIsNone(payload["value_per_m2"])
        self.assertFalse(ms.mercado_utilizable(r))

    def test_todos_los_estados_pertenecen_al_vocabulario_cerrado(self):
        tabla_ausente = ms.cargar_tabla(_tmpdir(self) / "no_existe.json")
        casos = [
            dict(sector="Miramar", fecha_corrida="2026-06-01"),        # parámetro declarado
            dict(sector="Nada", fecha_corrida="2026-06-01"),           # NO_MATCH
            dict(sector="Miramar", fecha_corrida="2026-06-01", tabla=tabla_ausente),
        ]
        for caso in casos:
            self.assertIn(ms.consultar_mercado(**caso)["status"], ds.ESTADOS)
        self.assertEqual(ms.MAPA_ESTADOS[ms.FUENTE_NO_DISPONIBLE], ds.FUENTE_NO_DISPONIBLE)
        self.assertEqual(ms.MAPA_ESTADOS[ms.DATOS_AUSENTES], ds.NO_SOPORTADA)


# ══════════════════════════════════════════════════════════════════════════════
# F · GOLDEN 040-646406 (resuelve o declara exactamente por qué no)
# ══════════════════════════════════════════════════════════════════════════════
class TestGolden(unittest.TestCase):

    def test_el_golden_declara_que_no_hay_fuente_de_mercado(self):
        g = ms.resolver_mercado_golden()
        # La FUENTE no resuelve (no existe): se declara.
        self.assertFalse(g["resuelve"])
        self.assertFalse(g["es_fuente_de_datos"])
        self.assertFalse(g["en_source_registry"])
        self.assertEqual(g["status_source_result"], ds.FUENTE_NO_DISPONIBLE)
        self.assertIn("FUENTE NO DISPONIBLE", g["motivo"])
        self.assertIn("FUENTE NO DISPONIBLE", g["motivo_no_resuelve"])
        self.assertFalse(ms.mercado_utilizable(g["resultado"]))

    def test_el_golden_resuelve_el_parametro_declarado_por_la_corrida(self):
        g = ms.resolver_mercado_golden()
        # El PARÁMETRO declarado sí resuelve por lookup, y coincide con el run state.
        self.assertTrue(g["parametro_declarado"]["resuelve"], g["motivo"])
        self.assertEqual(g["parametro_declarado"]["etiqueta"],
                         "parámetros declarados por la corrida")
        self.assertFalse(g["parametro_declarado"]["fuente_externa_verificable"])
        self.assertEqual(g["estado"], ms.RESUELTO)
        self.assertEqual(g["sector"], "Miramar")
        self.assertEqual(g["valor_m2"], 6_800_000)
        self.assertEqual(g["banda"], {"low": 5_500_000, "high": 8_000_000})
        # La resolución se hace por el BARRIO declarado, no por la respuesta previa.
        self.assertIn("barrio", g["campo_de_resolucion"])
        # Nada de esto se atribuye a la Lonja como fuente del valor.
        declarado = g["resultado"]["payload_normalized"]["valor_declarado_por_la_corrida"]
        self.assertNotIn("Lonja", declarado["fuente_declarada"])

    def test_el_golden_declara_la_vigencia_vencida(self):
        g = ms.resolver_mercado_golden()
        self.assertFalse(g["vigencia_ok"])
        self.assertEqual(g["vigencia_estado"], ms.VENCIDA)
        self.assertIn("VIGENCIA VENCIDA", g["motivo"])
        self.assertFalse(ms.mercado_utilizable(g["resultado"]))

    def test_el_golden_declara_los_datos_ausentes_del_producto(self):
        g = ms.resolver_mercado_golden()
        for atributo in ("neighborhood_aliases", "property_typology", "property_regime",
                         "economic_use", "area_band", "sample_size"):
            self.assertIn(atributo, g["datos_ausentes"])
        self.assertTrue(g["atributos_no_declarados_por_la_tabla"])

    def test_las_entradas_vienen_del_run_state_real(self):
        g = ms.resolver_mercado_golden()
        run_state = json.loads(RUTA_RUN_STATE.read_text(encoding="utf-8"))
        self.assertEqual(g["entradas"]["barrio"], run_state["urban_context"]["barrio"])
        self.assertEqual(g["entradas"]["area_m2"], run_state["urban_context"]["area"])
        self.assertEqual(g["entradas"]["fecha_corrida"], run_state["generated_at"])
        self.assertEqual(g["entradas"]["folio"],
                         run_state["property_identity"]["folio"])
        self.assertTrue(g["contraste_con_run_state"]["coincide_sector"])
        self.assertTrue(g["contraste_con_run_state"]["coincide_valor"])

    def test_el_valor_no_se_copia_del_run_state(self):
        """Con el sector/valor del run state MANIPULADO, el parámetro declarado no cambia.

        El parámetro se resuelve por lookup contra la tabla derivada del artefacto local;
        el run state sólo se usa para CONTRASTAR (y el contraste declara el desvío).
        """
        run_state = json.loads(RUTA_RUN_STATE.read_text(encoding="utf-8"))
        sector_met = run_state["market_context"]["sector_metodologico"]
        sector_met["matched_sector"] = "Sector Inventado"
        sector_met["value_m2"] = 1
        ruta = _tmpdir(self) / "run_state_manipulado.json"
        ruta.write_text(json.dumps(run_state, ensure_ascii=False), encoding="utf-8")
        g = ms.resolver_mercado_golden(ruta)
        self.assertFalse(g["resuelve"], "la fuente de mercado no existe: no puede resolver")
        self.assertTrue(g["parametro_declarado"]["resuelve"], g["motivo"])
        self.assertEqual(g["sector"], "Miramar")
        self.assertEqual(g["valor_m2"], 6_800_000)
        self.assertFalse(g["contraste_con_run_state"]["coincide_sector"])
        self.assertFalse(g["contraste_con_run_state"]["coincide_valor"])

    def test_sin_run_state_declara_el_motivo_y_no_inventa(self):
        g = ms.resolver_mercado_golden(_tmpdir(self) / "no_existe.json")
        self.assertFalse(g["resuelve"])
        self.assertEqual(g["estado"], ms.FUENTE_NO_DISPONIBLE)
        self.assertIsNone(g["valor_m2"])
        self.assertIsNone(g["sector"])
        self.assertIn("No existe el estado de corrida", g["motivo"])

    def test_sin_barrio_en_el_run_state_declara_el_motivo(self):
        run_state = json.loads(RUTA_RUN_STATE.read_text(encoding="utf-8"))
        run_state["urban_context"].pop("barrio", None)
        run_state["market_context"]["barrio"] = {"value": None, "status": "UNRESOLVED",
                                                 "source": None}
        ruta = _tmpdir(self) / "run_state_sin_barrio.json"
        ruta.write_text(json.dumps(run_state, ensure_ascii=False), encoding="utf-8")
        g = ms.resolver_mercado_golden(ruta)
        self.assertFalse(g["resuelve"])
        self.assertEqual(g["estado"], ms.DATOS_AUSENTES)
        self.assertIsNone(g["valor_m2"])
        self.assertTrue(g["motivo_no_resuelve"])
        self.assertIn("sector ni barrio", g["motivo_no_resuelve"])

    def test_el_golden_sin_red(self):
        """La resolución del Golden es 100 % local: ningún transporte de red."""
        fuente = Path(ms.__file__).read_text(encoding="utf-8")
        self.assertNotIn("urllib", fuente)
        self.assertNotIn("socket", fuente)


# ══════════════════════════════════════════════════════════════════════════════
# G · LICENCIAS
# ══════════════════════════════════════════════════════════════════════════════
class TestBloquesDeLicencia(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.catalogo = sl.catalogo_licencias()

    def test_cada_fuente_tiene_el_bloque_completo(self):
        self.assertGreaterEqual(len(self.catalogo), 15)
        for sid, bloque in self.catalogo.items():
            self.assertEqual(sl.campos_faltantes(bloque), [], f"bloque incompleto: {sid}")
            self.assertTrue(sl.bloque_completo(bloque))
            self.assertEqual(bloque["source_id"], sid)
            self.assertIn(bloque["provider_terms_status"], sl.ESTADOS_PROVIDER_TERMS)
            for campo in ("can_persist", "can_modify", "can_embed", "share_alike"):
                self.assertIsInstance(bloque[campo], bool, f"{sid}.{campo} no es booleano")
            self.assertTrue(bloque["license_name"], f"{sid} sin nombre de licencia")

    def test_el_catalogo_cubre_todas_las_fuentes_del_registro(self):
        fuentes = json.loads(RUTA_REGISTRO.read_text(encoding="utf-8"))["sources"]
        self.assertEqual(set(fuentes) - set(self.catalogo), set())

    def test_terminos_sin_hash_exigen_motivo(self):
        for sid, bloque in self.catalogo.items():
            if bloque["terms_hash"] is None:
                self.assertTrue(bloque["terms_hash_reason"],
                                f"{sid} no declara por qué no hay hash de términos")
            if bloque["provider_terms_status"] == sl.VERIFIED:
                self.assertTrue(bloque["terms_hash"], f"{sid} VERIFIED sin hash")
                self.assertTrue(bloque["consulted_at"], f"{sid} VERIFIED sin fecha")

    def test_lo_que_falta_para_verified_se_declara(self):
        for sid, bloque in self.catalogo.items():
            if bloque["provider_terms_status"] != sl.VERIFIED \
                    and bloque["provider_terms_status"] != sl.NOT_APPLICABLE:
                self.assertTrue(bloque["gap_para_verified"],
                                f"{sid} no declara qué falta para VERIFIED")
        resumen = sl.resumen()
        self.assertEqual(resumen["total_fuentes"], len(self.catalogo))
        self.assertFalse(resumen["congelado_por_licencia"])
        self.assertIn(sl.FUENTE_MAPILLARY, resumen["pendientes_de_verified"])
        self.assertTrue(resumen["huecos_para_verified"])

    def test_vocabulario_coincide_con_street_imagery(self):
        self.assertTrue(sl.verificar_vocabulario()["estados_coinciden"])
        if sl.si is not None:
            self.assertEqual(tuple(sl.ESTADOS_PROVIDER_TERMS), tuple(sl.si.ESTADOS_TERMINOS))
            self.assertEqual(sl.VERIFIED, sl.si.TERMS_VERIFIED)
            self.assertEqual(sl.DECLARED, sl.si.TERMS_DECLARED)
            self.assertEqual(sl.UNVERIFIED, sl.si.TERMS_UNVERIFIED)
            self.assertEqual(sl.RESTRICTED, sl.si.TERMS_RESTRICTED)
            self.assertEqual(sl.NOT_APPLICABLE, sl.si.TERMS_NOT_APPLICABLE)


class TestMapillaryYGoogle(unittest.TestCase):

    def test_mapillary_declara_url_fecha_y_hash_de_lo_descargado(self):
        bloque = sl.licencia(sl.FUENTE_MAPILLARY)
        self.assertEqual(bloque["provider_terms_status"], sl.DECLARED)
        self.assertEqual(bloque["terms_url"], "https://www.mapillary.com/terms")
        self.assertTrue(bloque["consulted_at"])
        self.assertEqual(len(bloque["terms_hash"]), 64)
        self.assertEqual(bloque["consulted_http_status"], 200)
        self.assertGreater(bloque["consulted_bytes"], 0)
        self.assertTrue(bloque["can_persist"])
        self.assertTrue(bloque["share_alike"])
        self.assertIn("Mapillary", bloque["attribution_text"])

    def test_mapillary_no_declara_verified_y_dice_que_falta(self):
        bloque = sl.licencia(sl.FUENTE_MAPILLARY)
        self.assertNotEqual(bloque["provider_terms_status"], sl.VERIFIED)
        self.assertIsNone(bloque["license_version"],
                          "la versión NO se imprime en los términos consultados")
        hueco = bloque["gap_para_verified"]
        self.assertIn("VERSIÓN", hueco)
        self.assertIn("403", hueco + bloque["notes"])

    def test_mapillary_no_congela_el_pack(self):
        resumen = sl.resumen()
        self.assertFalse(resumen["congelado_por_licencia"])
        self.assertFalse(resumen["por_estado"].get(sl.RESTRICTED, 0) > 1)

    def test_google_fail_closed_siempre(self):
        bloque = sl.licencia(sl.FUENTE_GOOGLE)
        self.assertFalse(bloque["can_persist"])
        self.assertFalse(bloque["can_embed"])
        self.assertFalse(bloque["can_modify"])
        self.assertFalse(bloque["share_alike"])
        self.assertIn(bloque["provider_terms_status"], (sl.RESTRICTED, sl.UNVERIFIED))
        self.assertTrue(bloque["terms_hash"], "la evidencia de Google sí se descargó")
        self.assertTrue(bloque["terms_hash_reason"])

    def test_google_solo_se_abriria_con_evidencia_que_lo_habilite(self):
        bloque = sl.licencia(sl.FUENTE_GOOGLE)
        if bloque["provider_terms_status"] == sl.VERIFIED:
            self.assertTrue(bloque["evidence_ids"],
                            "una apertura VERIFIED exige evidencia de términos registrada")
            self.assertTrue(bloque["notes"])
        else:
            self.assertFalse(bloque["can_persist"])
            self.assertFalse(bloque["can_embed"])

    def test_la_evidencia_registrada_es_reproducible_o_se_declara(self):
        """Re-descarga inyectada: coincidencia exacta cuando el contenido es el mismo."""
        contenido = b"<html>terminos de prueba</html>"
        sha = hashlib.sha256(contenido).hexdigest()
        original = sl.EVIDENCIA["OSM_COPYRIGHT"]["sha256"]
        sl.EVIDENCIA["OSM_COPYRIGHT"]["sha256"] = sha
        self.addCleanup(sl.EVIDENCIA["OSM_COPYRIGHT"].__setitem__, "sha256", original)
        coincide = sl.verificar_evidencia_registrada(
            "OSM_COPYRIGHT", transporte=lambda url, timeout: contenido)
        self.assertTrue(coincide["coincide"])
        self.assertTrue(coincide["motivo"])
        distinto = sl.verificar_evidencia_registrada(
            "OSM_COPYRIGHT", transporte=lambda url, timeout: contenido + b" cambiado")
        self.assertFalse(distinto["coincide"])
        self.assertTrue(distinto["motivo"])

    def test_terminos_sin_evidencia_no_son_verified(self):
        """Sin descarga no hay hash ni VERIFIED: fail-closed declarado."""
        def _explota(url, timeout):
            raise OSError("sin red (prueba offline)")
        r = sl.verificar_terminos("https://x.test/terms", transporte=_explota)
        self.assertEqual(r["provider_terms_status"], sl.UNVERIFIED)
        self.assertIsNone(r["terms_hash"])
        self.assertFalse(r["descargado"])
        self.assertTrue(r["motivo"])
        self.assertTrue(r["faltantes_para_verified"])

    def test_terminos_sin_licencia_en_su_contenido_no_son_verified(self):
        contenido = b"<html><body>Terms of use. We may change these terms.</body></html>"
        r = sl.verificar_terminos("https://x.test/terms",
                                  transporte=lambda url, timeout: contenido)
        self.assertEqual(r["provider_terms_status"], sl.DECLARED)
        self.assertEqual(r["terms_hash"], hashlib.sha256(contenido).hexdigest())
        self.assertTrue(r["faltantes_para_verified"])

    def test_terminos_prohibitivos_cierran_la_matriz(self):
        contenido = (b"<html>Content pre-fetching, indexing, storing, or caching is "
                     b"generally prohibited.</html>")
        r = sl.verificar_terminos("https://x.test/terms",
                                  transporte=lambda url, timeout: contenido)
        self.assertEqual(r["provider_terms_status"], sl.RESTRICTED)

    def test_terminos_explicitos_alcanzan_verified(self):
        contenido = (b"<html>Licensed under the Creative Commons CC BY-SA 4.0 license. "
                     b"You are free to copy, distribute and adapt this data.</html>")
        r = sl.verificar_terminos("https://x.test/terms",
                                  transporte=lambda url, timeout: contenido)
        self.assertEqual(r["provider_terms_status"], sl.VERIFIED)
        self.assertEqual(r["faltantes_para_verified"], [])

    def test_google_con_prohibicion_viva_sigue_cerrado(self):
        contenido = (b"<html>No Caching. Customer will not cache Google Maps Content. "
                     b"No Scraping: pre-fetch, index, store, reshare, or rehost</html>")
        r = sl.verificar_terminos_google(transporte=lambda url, timeout: contenido)
        self.assertEqual(r["provider_terms_status"], sl.RESTRICTED)
        self.assertFalse(r.get("can_persist", False))
        self.assertFalse(r.get("can_embed", False))

    def test_terminos_de_mapillary_sin_version_quedan_en_declared(self):
        contenido = (b"<html>Your use of User Content is subject to the Creative Commons "
                     b"Share Alike (CC BY-SA) license, unless we indicate otherwise."
                     b"</html>")
        r = sl.verificar_terminos_mapillary(transporte=lambda url, timeout: contenido)
        self.assertEqual(r["provider_terms_status"], sl.DECLARED)
        self.assertEqual(r["terms_hash"], hashlib.sha256(contenido).hexdigest())
        self.assertEqual(r["url"], "https://www.mapillary.com/terms")
        self.assertIn("VERSIÓN", " ".join(r["faltantes_para_verified"]))

    def test_sin_red_no_se_toca_la_red(self):
        """La consulta viva solo ocurre si se pide: el transporte se inyecta aquí."""
        llamadas = []

        def _espia(url, timeout):
            llamadas.append(url)
            return b"<html>CC BY-SA 4.0 You are free to copy, distribute</html>"

        r = sl.verificar_terminos_mapillary(transporte=_espia)
        self.assertEqual(llamadas, ["https://www.mapillary.com/terms"])
        self.assertEqual(r["provider_terms_status"], sl.VERIFIED)


class TestIncrustacionFailClosed(unittest.TestCase):

    def test_can_embed_false_implica_que_ningun_flujo_incrusta(self):
        catalogo = sl.catalogo_licencias()
        sin_permiso = [sid for sid, b in catalogo.items() if not b["can_embed"]]
        self.assertGreaterEqual(len(sin_permiso), 1)
        for sid in sin_permiso:
            permiso = sl.autorizar_incrustacion(sid)
            self.assertFalse(permiso["permitido"], f"{sid} no puede incrustar")
            self.assertEqual(permiso["flujo"], "NINGUNO")
            self.assertIsNone(permiso["attribution_text"])
            self.assertTrue(permiso["motivo"])

    def test_google_no_puede_incrustar(self):
        permiso = sl.autorizar_incrustacion(sl.FUENTE_GOOGLE)
        self.assertFalse(permiso["permitido"])
        self.assertEqual(permiso["flujo"], "NINGUNO")
        self.assertIn("can_embed=False", permiso["motivo"])

    def test_fuente_desconocida_falla_cerrado(self):
        permiso = sl.autorizar_incrustacion("FUENTE_INEXISTENTE")
        self.assertFalse(permiso["permitido"])
        self.assertEqual(permiso["flujo"], "NINGUNO")
        self.assertTrue(permiso["motivo"])

    def test_incrustacion_exige_permiso_declarado(self):
        permiso = sl.autorizar_incrustacion(sl.FUENTE_MAPILLARY)
        self.assertTrue(permiso["permitido"])
        self.assertEqual(permiso["flujo"], "COPIAR_CON_ATRIBUCION")
        self.assertIn("Mapillary", permiso["attribution_text"])
        # Una fuente sin permiso declarado (p. ej. Google) nunca lo obtiene.
        self.assertFalse(sl.autorizar_incrustacion(sl.FUENTE_GOOGLE)["permitido"])

    def test_matriz_de_persistencias(self):
        matriz = sl.persistencias_permitidas()
        self.assertFalse(matriz[sl.FUENTE_GOOGLE]["can_persist"])
        self.assertFalse(matriz[sl.FUENTE_GOOGLE]["can_embed"])
        self.assertTrue(matriz[sl.FUENTE_MAPILLARY]["can_persist"])
        self.assertFalse(matriz["CATASTRO_BAQ_PREDIO"]["can_embed"])


if __name__ == "__main__":
    unittest.main()
