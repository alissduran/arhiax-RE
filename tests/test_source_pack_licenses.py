# -*- coding: utf-8 -*-
"""SOURCE PACK v2 — pruebas del bloque de LICENCIAS de imágenes vs términos de API.

Corre **OFFLINE** por defecto: la evidencia se lee del registro del módulo (URL + fecha +
HTTP + bytes + `sha256` medidos el 2026-09-29). La red se usa **sólo** si está disponible y,
si no lo está, la prueba **degrada a estado declarado** (nunca falla por falta de red, y
nunca asume un permiso).

Qué se prueba:
  · Bloque canónico completo, con `IMAGERY_LICENSE_STATUS` y `API_TERMS_STATUS` SEPARADOS.
  · El estado de las imágenes lo dicta la EVIDENCIA, no el código (si se quita el marcador,
    el estado baja a `DECLARED`).
  · `HTTP 200` con soft-404 NO cuenta como términos consultados; el tercero corrobora, no
    verifica; sin bytes no hay hash, y sin hash no hay `VERIFIED` de esas imágenes.
  · Google Street View FAIL-CLOSED (test negativo: persistir / modificar / incrustar se
    deniegan con motivo) y sin bloquear el Source Pack (`OPTIONAL_ENRICHMENT`).
  · La Lonja **NO es una fuente**: ni en el catálogo, ni con bloque de licencia, ni con
    contrato de datos, y su ausencia no bloquea `CONTRACT_FROZEN`/`OPERATIONAL_READY`.
"""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "api"))

import source_licenses_v2 as v  # noqa: E402

RUTA_RAIZ = ROOT


def _snapshot_evidencia(caso):
    """Guarda y restaura el registro de evidencia Y el catálogo cacheado (una sola limpieza:
    el orden importa — si se refrescara antes de restaurar, el catálogo quedaría envenenado)."""
    original = copy.deepcopy(v.EVIDENCIA)

    def _restaurar():
        v.EVIDENCIA.clear()
        v.EVIDENCIA.update(original)
        v.catalogo(refrescar=True)

    caso.addCleanup(_restaurar)


# ══════════════════════════════════════════════════════════════════════════════
# 1 · BLOQUE CANÓNICO
# ══════════════════════════════════════════════════════════════════════════════
class TestBloqueCanonico(unittest.TestCase):

    def test_toda_fuente_declara_el_bloque_completo(self):
        catalogo = v.catalogo()
        self.assertEqual(set(catalogo), set(v.SOURCE_IDS))
        for sid, bloque in catalogo.items():
            self.assertEqual(v.campos_faltantes(bloque), [], f"bloque incompleto: {sid}")
            self.assertTrue(v.bloque_completo(bloque))
            self.assertEqual(bloque["source_id"], sid)
            for campo in ("can_persist", "can_modify", "can_embed", "share_alike"):
                self.assertIsInstance(bloque[campo], bool, f"{sid}.{campo} no es booleano")
            self.assertTrue(bloque["license_name"], f"{sid} sin nombre de licencia")
            self.assertIn(bloque["IMAGERY_LICENSE_STATUS"], v.ESTADOS)
            self.assertIn(bloque["API_TERMS_STATUS"], v.ESTADOS)
            self.assertIn(bloque["evidence_status"], v.EV_ESTADOS)

    def test_el_bloque_no_reintroduce_el_campo_mezclado(self):
        for sid, bloque in v.catalogo().items():
            self.assertNotIn("provider_terms_status", bloque,
                             f"{sid} vuelve a mezclar imágenes y API en un solo campo")

    def test_verificado_exige_fecha_y_hash_y_declara_lo_que_falta(self):
        for sid, bloque in v.catalogo().items():
            if bloque["IMAGERY_LICENSE_STATUS"] == v.VERIFIED:
                self.assertTrue(bloque["consulted_at"], f"{sid} VERIFIED sin fecha")
                self.assertTrue(bloque["sha256"], f"{sid} VERIFIED sin sha256")
                self.assertEqual(bloque["what_is_missing_for_verified"], [])
                self.assertTrue(bloque["verified_scope"], f"{sid} VERIFIED sin alcance declarado")
            elif bloque["IMAGERY_LICENSE_STATUS"] != v.NOT_APPLICABLE:
                self.assertTrue(bloque["what_is_missing_for_verified"],
                                f"{sid} sin VERIFIED y sin declarar qué falta")
            if bloque["sha256"] is None:
                self.assertTrue(bloque["what_is_missing_for_verified"],
                                f"{sid} sin hash y sin hueco declarado")

    def test_los_hashes_registrados_estan_bien_formados(self):
        import re
        for sid, bloque in v.catalogo().items():
            if bloque["sha256"] is not None:
                self.assertRegex(bloque["sha256"], r"^[0-9a-f]{64}$", f"{sid} sha256 raro")
        for eid, registro in v.EVIDENCIA.items():
            if registro["http_status"] == 200 and registro.get("sha256"):
                self.assertRegex(registro["sha256"], r"^[0-9a-f]{64}$", f"{eid} sha256 raro")

    def test_auditoria_del_catalogo_no_encuentra_problemas(self):
        informe = v.auditoria()
        self.assertTrue(informe["ok"], informe["problemas"])
        self.assertEqual(informe["problemas"], [])

    def test_vocabulario_coincide_con_street_imagery(self):
        self.assertTrue(v.verificar_vocabulario()["estados_coinciden"])
        if v.si is not None:
            self.assertEqual(tuple(v.ESTADOS), tuple(v.si.ESTADOS_TERMINOS))


# ══════════════════════════════════════════════════════════════════════════════
# 2 · IMÁGENES ≠ API (la separación exigida)
# ══════════════════════════════════════════════════════════════════════════════
class TestSeparacionImagenesApi(unittest.TestCase):

    def test_mapillary_separa_los_dos_estados(self):
        bloque = v.bloque_licencia(v.SOURCE_MAPILLARY)
        self.assertEqual(bloque["IMAGERY_LICENSE_STATUS"], v.VERIFIED)
        self.assertEqual(bloque["API_TERMS_STATUS"], v.DECLARED)
        self.assertIn(v.SOURCE_MAPILLARY, v.resumen()["separados"])
        # Cada columna trae su propia evidencia y su propio motivo.
        self.assertTrue(bloque["imagery_license"]["motivo"])
        self.assertTrue(bloque["api_terms"]["motivo"])
        self.assertIn("MAPILLARY_TERMS_OF_USE", bloque["imagery_license"].get(
            "evidence_ids", bloque["evidence_ids"]))

    def test_la_licencia_de_imagenes_es_la_que_dicta_los_derechos(self):
        bloque = v.bloque_licencia(v.SOURCE_MAPILLARY)
        self.assertTrue(bloque["can_persist"])
        self.assertTrue(bloque["can_modify"])
        self.assertTrue(bloque["can_embed"])
        self.assertTrue(bloque["share_alike"])
        permiso = v.autorizar_incrustacion(v.SOURCE_MAPILLARY)
        self.assertTrue(permiso["permitido"])
        self.assertIn("Mapillary", permiso["attribution_text"])
        self.assertIn("CC BY-SA", permiso["conditions"][2])

    def test_un_api_verified_no_abre_la_matriz_de_imagenes(self):
        """OSM tiene API_TERMS_STATUS=VERIFIED y aun así NO se incrusta imagen suya."""
        bloque = v.bloque_licencia(v.SOURCE_OSM)
        self.assertEqual(bloque["API_TERMS_STATUS"], v.VERIFIED)
        self.assertEqual(bloque["IMAGERY_LICENSE_STATUS"], v.NOT_APPLICABLE)
        permiso = v.autorizar_incrustacion(v.SOURCE_OSM)
        self.assertFalse(permiso["permitido"], "un VERIFIED de API no puede abrir imágenes")
        self.assertEqual(permiso["flujo"], "NINGUNO")

    def test_la_api_de_mapillary_no_otorga_derechos_sobre_las_imagenes(self):
        api = v.evaluar_terminos_api_mapillary()
        self.assertEqual(api["estado"], v.DECLARED)
        self.assertIn("NO otorga ni amplía derechos", api["efecto"])
        self.assertTrue(api["obligaciones_declaradas"])
        self.assertTrue(any("client_id" in o for o in api["obligaciones_declaradas"]))
        self.assertTrue(any("sin scraping" in o or "no scraping" in o
                            for o in api["obligaciones_declaradas"]))
        self.assertTrue(api["faltantes"], "la API no puede quedar VERIFIED sin declarar huecos")

    def test_el_resumen_expone_las_dos_columnas_por_separado(self):
        resumen = v.resumen()
        self.assertEqual(resumen["total_fuentes"], len(v.SOURCE_IDS))
        self.assertIn(v.VERIFIED, resumen["IMAGERY_LICENSE_STATUS"])
        self.assertIn(v.DECLARED, resumen["API_TERMS_STATUS"])
        self.assertFalse(resumen["congelado_por_licencia"])


# ══════════════════════════════════════════════════════════════════════════════
# 3 · LA EVIDENCIA MANDA (nada se inventa)
# ══════════════════════════════════════════════════════════════════════════════
class TestEvidenciaManda(unittest.TestCase):

    def test_la_evidencia_de_imagenes_del_proveedor_sostiene_lo_declarado(self):
        terms = v.EVIDENCIA["MAPILLARY_TERMS_OF_USE"]
        self.assertEqual(terms["http_status"], 200)
        self.assertTrue(terms["bytes"] and terms["sha256"])
        self.assertEqual(terms["evidence_status"], v.EV_ACCESIBLE)
        self.assertTrue(terms["marcadores"]["cc_by_sa_texto"])
        self.assertTrue(terms["marcadores"]["attribution_required"])
        self.assertGreaterEqual(terms["marcadores"]["cc_by_sa_4_0_enlaces"], 1,
                                "sin enlace al deed 4.0 no hay versión evidenciada")
        self.assertFalse(terms["marcadores"]["prohibicion_persistir"])

    def test_sin_marcador_de_licencia_el_estado_baja_a_declared(self):
        """El estado lo dicta el contenido: quitado el marcador, no hay VERIFIED."""
        _snapshot_evidencia(self)
        v.EVIDENCIA["MAPILLARY_TERMS_OF_USE"]["marcadores"]["cc_by_sa_texto"] = False
        v.catalogo(refrescar=True)
        bloque = v.bloque_licencia(v.SOURCE_MAPILLARY)
        self.assertEqual(bloque["IMAGERY_LICENSE_STATUS"], v.DECLARED)
        self.assertTrue(bloque["what_is_missing_for_verified"])
        self.assertIn("CC BY-SA", bloque["what_is_missing_for_verified"][0])

    def test_sin_el_enlace_a_la_version_no_hay_verified(self):
        _snapshot_evidencia(self)
        v.EVIDENCIA["MAPILLARY_TERMS_OF_USE"]["marcadores"]["cc_by_sa_4_0_enlaces"] = 0
        v.EVIDENCIA["MAPILLARY_TERMS_OF_USE"]["marcadores"]["cc_by_sa_4_0_texto"] = False
        v.catalogo(refrescar=True)
        bloque = v.bloque_licencia(v.SOURCE_MAPILLARY)
        self.assertEqual(bloque["IMAGERY_LICENSE_STATUS"], v.DECLARED)
        self.assertIn("versión", " ".join(bloque["what_is_missing_for_verified"]).lower())

    def test_una_prohibicion_explicita_cierra_la_matriz(self):
        _snapshot_evidencia(self)
        v.EVIDENCIA["MAPILLARY_TERMS_OF_USE"]["marcadores"]["prohibicion_persistir"] = True
        v.catalogo(refrescar=True)
        bloque = v.bloque_licencia(v.SOURCE_MAPILLARY)
        self.assertEqual(bloque["IMAGERY_LICENSE_STATUS"], v.RESTRICTED)
        self.assertFalse(v.autorizar_persistencia(v.SOURCE_MAPILLARY)["permitido"])

    def test_http_200_con_soft_404_no_es_evidencia(self):
        for eid in ("MAPILLARY_TERMS_API", "MAPILLARY_TERMS_DATA"):
            registro = v.EVIDENCIA[eid]
            self.assertEqual(registro["http_status"], 200)
            self.assertEqual(registro["evidence_status"], v.EV_SOFT_404)
            self.assertTrue("soft-404" in registro["nota"] or "no encontrada" in registro["nota"],
                            registro["nota"])
            self.assertIn("HTTP 200", registro["nota"])
            self.assertNotEqual(registro["evidence_status"], v.EV_ACCESIBLE)
        # Y no sostiene ningún VERIFIED: el hueco de API queda escrito.
        bloque = v.bloque_licencia(v.SOURCE_MAPILLARY)
        self.assertNotEqual(bloque["API_TERMS_STATUS"], v.VERIFIED)
        self.assertTrue(any("soft-404" in f for f in bloque["api_terms"]["faltantes"]))

    def test_la_pagina_del_proveedor_que_fija_la_version_sigue_inaccesible(self):
        registro = v.EVIDENCIA["MAPILLARY_HELP_CC_BY_SA_4_0"]
        self.assertEqual(registro["http_status"], 403)
        self.assertIsNone(registro["bytes"], "un 403 no tiene bytes")
        self.assertIsNone(registro["sha256"], "un 403 no puede tener hash inventado")
        self.assertEqual(registro["evidence_status"], v.EV_INACCESIBLE)
        self.assertTrue(registro["nota"])

    def test_la_copia_archivada_se_declara_como_tal(self):
        registro = v.EVIDENCIA["MAPILLARY_HELP_CC_BY_SA_4_0_ARCHIVO"]
        self.assertEqual(registro["evidence_status"], v.EV_ARCHIVADA)
        self.assertTrue(registro["es_copia_archivada"])
        self.assertEqual(registro["http_status"], 200)
        self.assertTrue(registro["sha256"])

    def test_un_tercero_corrobra_pero_no_verifica(self):
        self.assertIn("MAPILLARY_WIKI_TERCEROS", v.EVIDENCIA_SOLO_CORROBORA)
        self.assertFalse(v.EVIDENCIA["MAPILLARY_WIKI_TERCEROS"]["del_proveedor"])
        # Ningún estado del bloque se apoya en la evidencia de tercero.
        bloque = v.bloque_licencia(v.SOURCE_MAPILLARY)
        self.assertNotIn("MAPILLARY_WIKI_TERCEROS", bloque["evidence_ids"])

    def test_pagina_accesible_sin_marcadores_no_sostiene_verified(self):
        for eid in ("MAPILLARY_OPEN_DATA", "MAPILLARY_DATASETS", "MAPILLARY_API_DOC"):
            self.assertEqual(v.EVIDENCIA[eid]["evidence_status"], v.EV_SIN_MARCADORES)

    def test_las_paginas_dinamicas_declaran_sus_hashes_observados(self):
        terms = v.EVIDENCIA["MAPILLARY_TERMS_OF_USE"]
        self.assertTrue(terms["pagina_dinamica"])
        self.assertGreaterEqual(len(terms["hashes_observados"]), 2,
                                "una página dinámica debe declarar los hashes observados")

    def test_sin_red_no_se_toca_la_red_y_se_declara(self):
        """Transporte inyectado que falla: estado declarado, nunca un hash inventado."""
        def _sin_red(url, timeout):
            raise OSError("sin red (prueba offline)")

        registro = v.descargar_evidencia("https://x.test/terms", transporte=_sin_red)
        self.assertFalse(registro["descargado"])
        self.assertIsNone(registro["sha256"])
        self.assertIsNone(registro["bytes"])
        self.assertTrue(registro["motivo"])
        verificacion = v.verificar_evidencia_registrada(
            "OSM_COPYRIGHT", transporte=_sin_red)
        self.assertFalse(verificacion["coincide"])
        self.assertEqual(verificacion["estado_declarado"], v.DECLARED)
        self.assertTrue(verificacion["motivo"])

    def test_la_evidencia_registrada_es_reproducible_o_se_declara(self):
        """Con el mismo contenido, coincidencia exacta; con otro, discrepancia DECLARADA."""
        _snapshot_evidencia(self)
        contenido = b"<html>creative commons by-sa/4.0 CC BY-SA attribution</html>"
        import hashlib
        registrado = hashlib.sha256(contenido).hexdigest()
        v.EVIDENCIA["OSM_COPYRIGHT"]["sha256"] = registrado
        coincide = v.verificar_evidencia_registrada(
            "OSM_COPYRIGHT", transporte=lambda url, timeout: contenido)
        self.assertTrue(coincide["coincide"])
        self.assertEqual(coincide["estado_declarado"], v.VERIFIED)
        distinto = v.verificar_evidencia_registrada(
            "OSM_COPYRIGHT", transporte=lambda url, timeout: contenido + b" cambiado")
        self.assertFalse(distinto["coincide"])
        self.assertEqual(distinto["estado_declarado"], v.DECLARED)
        self.assertIn("cambió", distinto["motivo"])
        self.assertEqual(v.EVIDENCIA["OSM_COPYRIGHT"]["sha256"], registrado,
                         "la instantánea registrada no se toca al verificar")

    def test_consulta_viva_solo_si_hay_red_y_degrada_a_declarado(self):
        """Red OPCIONAL: si no hay, se declara; si hay, coincide o se declara el cambio."""
        if not v.red_disponible(timeout=8.0):
            self.skipTest("sin red disponible: la evidencia queda en estado DECLARADO "
                          "(degradación declarada, no fallo)")
        verificacion = v.verificar_evidencia_registrada("MAPILLARY_TERMS_OF_USE", timeout=30.0)
        self.assertTrue(verificacion["motivo"])
        if verificacion["coincide"]:
            self.assertEqual(verificacion["estado_declarado"], v.VERIFIED)
        else:
            # Página dinámica: el cambio se DECLARA, jamás se finge que sigue igual.
            self.assertEqual(verificacion["estado_declarado"], v.DECLARED)
            self.assertTrue(verificacion["pagina_dinamica"])
            self.assertTrue(verificacion["hash_registrado"])

    def test_analizar_contenido_detecta_la_version_por_enlace(self):
        contenido = (b'<html>Your use of User Content is subject to the '
                     b'<a href="http://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA '
                     b'license</a>. You must adhere to the attribution requirements</html>')
        marcas = v.analizar_contenido(contenido)
        self.assertTrue(marcas["cc_by_sa_texto"])
        self.assertEqual(marcas["cc_by_sa_4_0_enlaces"], 1)
        self.assertTrue(marcas["attribution_required"])


# ══════════════════════════════════════════════════════════════════════════════
# 4 · GOOGLE: FAIL-CLOSED PROBADO (test negativo)
# ══════════════════════════════════════════════════════════════════════════════
class TestGoogleFailClosed(unittest.TestCase):

    def test_la_matriz_esta_cerrada(self):
        bloque = v.bloque_licencia(v.SOURCE_GOOGLE)
        self.assertFalse(bloque["can_persist"])
        self.assertFalse(bloque["can_modify"])
        self.assertFalse(bloque["can_embed"])
        self.assertFalse(bloque["share_alike"])
        self.assertEqual(bloque["IMAGERY_LICENSE_STATUS"], v.RESTRICTED)
        self.assertEqual(bloque["API_TERMS_STATUS"], v.RESTRICTED)
        self.assertTrue(bloque["sha256"], "la evidencia de Google sí se descargó")
        self.assertTrue(bloque["what_is_missing_for_verified"])

    def test_es_enriquecimiento_opcional_y_no_bloquea_nada(self):
        bloque = v.bloque_licencia(v.SOURCE_GOOGLE)
        self.assertEqual(bloque["product_role"], v.PRODUCT_ROLE_OPTIONAL_ENRICHMENT)
        self.assertFalse(bloque["bloquea_source_pack"])
        self.assertFalse(v.bloquea_source_pack(v.SOURCE_GOOGLE))
        resumen = v.resumen()
        self.assertFalse(resumen["bloquea_contract_frozen"])
        self.assertFalse(resumen["bloquea_operational_ready"])
        self.assertIn(v.SOURCE_GOOGLE, resumen["no_bloquean_el_pack"])

    def test_intento_de_persistir_es_denegado_con_motivo(self):
        permiso = v.autorizar_persistencia(v.SOURCE_GOOGLE)
        self.assertFalse(permiso["permitido"])
        self.assertEqual(permiso["flujo"], "NINGUNO")
        self.assertIsNone(permiso["attribution_text"])
        self.assertIn("can_persist=False", permiso["motivo"])
        self.assertIn("RESTRICTED", permiso["motivo"])

    def test_intento_de_modificar_es_denegado_con_motivo(self):
        permiso = v.autorizar_modificacion(v.SOURCE_GOOGLE)
        self.assertFalse(permiso["permitido"])
        self.assertIn("can_modify=False", permiso["motivo"])
        self.assertEqual(permiso["conditions"], [])

    def test_intento_de_incrustar_es_denegado_con_motivo(self):
        permiso = v.autorizar_incrustacion(v.SOURCE_GOOGLE, destino="PDF")
        self.assertFalse(permiso["permitido"])
        self.assertEqual(permiso["destino"], "PDF")
        self.assertIn("can_embed=False", permiso["motivo"])
        self.assertEqual(permiso["API_TERMS_STATUS"], v.RESTRICTED)

    def test_desde_el_registro_alternativo_tampoco_se_abre(self):
        """Importar el bloque por su `source_id` real de imagen no cambia nada."""
        for sid in ("IMAGERY_GOOGLE_STREET_VIEW", "GOOGLE", "google_street_view"):
            permiso = v.autorizar_incrustacion(sid)
            self.assertFalse(permiso["permitido"], f"{sid} no puede incrustar")
            self.assertEqual(permiso["flujo"], "NINGUNO")

    def test_la_evidencia_de_google_imprime_la_prohibicion(self):
        politicas = v.EVIDENCIA["GOOGLE_STREETVIEW_POLICIES"]
        self.assertTrue(politicas["marcadores"]["prohibicion_persistir"])
        self.assertIn("generally prohibited", politicas["cita_prohibicion"])
        self.assertEqual(v.EVIDENCIA["GOOGLE_MAPS_PLATFORM_TERMS"]["http_status"], 200)


# ══════════════════════════════════════════════════════════════════════════════
# 5 · MAPILLARY: PERMISOS CON CONDICIÓN (por imagen)
# ══════════════════════════════════════════════════════════════════════════════
class TestMapillaryCondiciones(unittest.TestCase):

    def test_la_condicion_por_imagen_se_declara(self):
        bloque = v.bloque_licencia(v.SOURCE_MAPILLARY)
        self.assertTrue(bloque["conditions"])
        self.assertEqual(len(bloque["conditions"]), 5)
        unida = " ".join(bloque["conditions"])
        self.assertIn("POR IMAGEN", unida)
        self.assertIn("ATRIBUCIÓN VISIBLE", unida)
        self.assertIn("SHARE-ALIKE", unida)
        self.assertIn("ADQUISICIÓN", unida)

    def test_imagen_con_cc_by_sa_se_persiste_con_atribucion(self):
        permiso = v.permitir_persistencia_imagen(v.SOURCE_MAPILLARY,
                                                 licencia_de_la_imagen="CC BY-SA 4.0")
        self.assertTrue(permiso["permitido_para_esta_imagen"])
        self.assertEqual(permiso["flujo"], "COPIAR_CON_ATRIBUCION")
        self.assertIn("Mapillary", permiso["attribution_text"])

    def test_imagen_sin_licencia_no_se_persiste(self):
        permiso = v.permitir_persistencia_imagen(v.SOURCE_MAPILLARY,
                                                 licencia_de_la_imagen=None)
        self.assertFalse(permiso["permitido_para_esta_imagen"])
        self.assertEqual(permiso["flujo"], "NINGUNO")
        self.assertIsNone(permiso["attribution_text"])
        self.assertIn("no declara licencia", permiso["motivo"])
        self.assertIn("fail-closed", permiso["motivo"])

    def test_imagen_sin_metadata_no_se_persiste(self):
        permiso = v.permitir_persistencia_imagen(v.SOURCE_MAPILLARY,
                                                 licencia_de_la_imagen="CC BY-SA 4.0",
                                                 tiene_metadata=False)
        self.assertFalse(permiso["permitido_para_esta_imagen"])

    def test_imagen_con_licencia_nc_no_se_persiste(self):
        permiso = v.permitir_persistencia_imagen(v.SOURCE_MAPILLARY,
                                                 licencia_de_la_imagen="CC BY-NC-SA 4.0")
        self.assertFalse(permiso["permitido_para_esta_imagen"])
        self.assertIn("no es CC BY-SA", permiso["motivo"])

    def test_la_imagen_de_google_nunca_se_persiste(self):
        permiso = v.permitir_persistencia_imagen(v.SOURCE_GOOGLE,
                                                 licencia_de_la_imagen="CC BY-SA 4.0")
        self.assertFalse(permiso["permitido_para_esta_imagen"])

    def test_el_modo_estricto_cierra_lo_declarado(self):
        permiso = v.autorizar_incrustacion(v.SOURCE_MAPILLARY, estricto=True)
        self.assertTrue(permiso["permitido"], "las imágenes están VERIFIED")
        # Un estado DECLARED no incrusta en modo estricto: se prueba sobre el catálogo real
        # degradando la evidencia de imágenes.
        _snapshot_evidencia(self)
        v.EVIDENCIA["MAPILLARY_TERMS_OF_USE"]["marcadores"]["cc_by_sa_texto"] = False
        v.catalogo(refrescar=True)
        self.assertEqual(v.bloque_licencia(v.SOURCE_MAPILLARY)["IMAGERY_LICENSE_STATUS"],
                         v.DECLARED)
        self.assertFalse(v.autorizar_incrustacion(v.SOURCE_MAPILLARY,
                                                  estricto=True)["permitido"])


# ══════════════════════════════════════════════════════════════════════════════
# 6 · LA LONJA **NO ES UNA FUENTE**
# ══════════════════════════════════════════════════════════════════════════════
class TestLonjaNoEsFuente(unittest.TestCase):

    def test_no_hay_ningun_artefacto_de_lonja_en_este_bloque(self):
        for ruta in ("api/lonja_contract.py",
                     "docs/source_pack/LONJA_DATASET_CONTRACT.md",
                     "docs/source_pack/lonja_dataset_contract_v1.json"):
            self.assertFalse((RUTA_RAIZ / ruta).exists(),
                             f"no debe existir un artefacto de Lonja: {ruta}")

    def test_la_lonja_no_esta_en_el_catalogo_de_licencias(self):
        ids = set(v.catalogo())
        self.assertFalse([sid for sid in ids if "LONJA" in sid.upper()])
        self.assertFalse(v.es_fuente_de_datos("LONJA_MARKET_BAQ"))
        self.assertFalse(v.es_fuente_de_datos("LONJA_BAQ"))
        # El catálogo v2 sólo reconoce sus propias fuentes (y ninguna es la Lonja).
        self.assertTrue(v.es_fuente_de_datos(v.SOURCE_MAPILLARY))
        self.assertEqual(sorted(ids), sorted(v.SOURCE_IDS))

    def test_es_aliado_institucional_fuera_del_registry(self):
        self.assertTrue(v.es_aliado_institucional("LONJA_BAQ"))
        partner = v.partners_institucionales()["LONJA_BAQ"]
        self.assertFalse(partner["es_fuente_de_datos"])
        self.assertFalse(partner["aporta_datos_a_dictus"])
        self.assertFalse(partner["en_source_registry"])
        self.assertFalse(partner["tiene_bloque_de_licencia"])
        self.assertIsNone(partner["authority_class"])
        self.assertEqual(partner["product_role"], v.PRODUCT_ROLE_NOT_A_SOURCE)
        for tipo in ("institutional_partner", "distribution_partner", "stakeholder"):
            self.assertIn(tipo, partner["tipos"])
        self.assertIn("NO es una fuente de datos", partner["nota"])

    def test_la_auditoria_confirma_que_no_es_fuente(self):
        lonja = v.auditoria_no_lonja()
        self.assertTrue(lonja["ok"], lonja["sospechosos"])
        self.assertFalse(lonja["lonja_como_fuente"])
        self.assertEqual(lonja["sospechosos"], [])
        self.assertEqual(lonja["partners_institucionales"], ["LONJA_BAQ"])
        self.assertEqual(lonja["source_ids"], sorted(v.SOURCE_IDS))

    def test_no_bloquea_contract_frozen_ni_operational_ready(self):
        partner = v.partners_institucionales()["LONJA_BAQ"]
        self.assertFalse(partner["bloquea_source_pack"])
        self.assertFalse(partner["bloquea_contract_frozen"])
        self.assertFalse(partner["bloquea_operational_ready"])
        resumen = v.resumen()
        self.assertFalse(resumen["bloquea_contract_frozen"])
        self.assertFalse(resumen["bloquea_operational_ready"])
        self.assertFalse(resumen["lonja_como_fuente"])
        self.assertEqual(resumen["aliados_institucionales"], ["LONJA_BAQ"])

    def test_la_lonja_no_tiene_estado_de_licencia_ni_permisos(self):
        for candidato in ("LONJA_BAQ", "LONJA_MARKET_BAQ", "LONJA"):
            self.assertIsNone(v.bloque_licencia(candidato))
            permiso = v.autorizar_persistencia(candidato)
            self.assertFalse(permiso["permitido"])
            self.assertTrue(permiso["motivo"])
        matriz = v.matriz_permisos()
        self.assertFalse([sid for sid in matriz if "LONJA" in sid.upper()])

    def test_el_documento_de_aliados_existe_y_es_explicito(self):
        documento = RUTA_RAIZ / "docs" / "source_pack" / "INSTITUTIONAL_PARTNERS.md"
        self.assertTrue(documento.exists())
        texto = documento.read_text(encoding="utf-8")
        for frase in ("la Lonja no es una fuente de datos",
                      "`es_fuente_de_datos`", "institutional_partner",
                      "distribution_partner", "stakeholder",
                      "CONTRACT_FROZEN", "OPERATIONAL_READY"):
            self.assertIn(frase, texto)

    def test_el_registro_del_pack_v1_ya_no_la_declara_fuente(self):
        """RECONCILIACIÓN EJECUTADA: el pack v1 adoptó la doctrina de esta pieza.

        Antes había divergencia (el pack v1 la listaba en `sources` con `CORE_MARKET`). Hoy
        `LONJA_MARKET_BAQ` está FUERA de `sources` y declarada como aliado institucional, así
        que el conjunto de pruebas de los dos packs dice lo mismo.
        """
        import json
        ruta = RUTA_RAIZ / "docs" / "source_pack" / "barranquilla_sources_v1.json"
        registro = json.loads(ruta.read_text(encoding="utf-8"))
        self.assertNotIn("LONJA_MARKET_BAQ", registro["sources"])
        lonja = registro["no_fuentes_institucionales"]["aliados"]["LONJA_BAQ"]
        self.assertFalse(lonja["es_fuente_de_datos"])
        self.assertFalse(lonja["aporta_datos_a_dictus"])
        self.assertFalse(lonja["en_source_registry"])
        self.assertEqual(lonja["product_role"], v.PRODUCT_ROLE_NOT_A_SOURCE)
        self.assertIsNone(lonja["authority_class"])
        mercado = registro["no_fuentes_institucionales"]["valor_de_mercado"]
        self.assertFalse(mercado["es_fuente_de_datos"])
        self.assertFalse(mercado["fuente_externa_verificable"])


# ══════════════════════════════════════════════════════════════════════════════
# 7 · COBERTURA DE LA EVIDENCIA REGISTRADA
# ══════════════════════════════════════════════════════════════════════════════
class TestRegistroDeEvidencia(unittest.TestCase):

    def test_toda_evidencia_declara_url_fecha_http_y_estado(self):
        for eid, registro in v.EVIDENCIA.items():
            self.assertTrue(registro.get("url"), f"{eid} sin URL")
            self.assertEqual(registro.get("consulted_at"), v.FECHA_CONSULTA, f"{eid} sin fecha")
            self.assertIn(registro.get("evidence_status"), v.EV_ESTADOS, f"{eid} estado raro")
            if registro["http_status"] == 200:
                self.assertTrue(registro["bytes"], f"{eid} 200 sin bytes")
                self.assertTrue(registro["sha256"], f"{eid} 200 sin sha256")
            else:
                self.assertIsNone(registro["bytes"], f"{eid} con bytes sin 200")
            self.assertTrue(registro.get("nota") or registro.get("motivo"),
                            f"{eid} sin nota ni motivo")

    def test_la_evidencia_de_imagenes_esta_separada_de_la_de_api(self):
        self.assertNotEqual(set(v.EVIDENCIA_IMAGERY), set(v.EVIDENCIA_API))
        self.assertIn("MAPILLARY_TERMS_API", v.EVIDENCIA_API)
        for eid in v.EVIDENCIA_IMAGERY + v.EVIDENCIA_API:
            self.assertIn(eid, v.EVIDENCIA)

    def test_el_resumen_clasifica_la_evidencia(self):
        resumen = v.resumen()
        self.assertIn("MAPILLARY_TERMS_OF_USE", resumen["evidencia_accesible"])
        self.assertIn("MAPILLARY_HELP_CC_BY_SA_4_0", resumen["evidencia_inaccesible"])
        self.assertIn("MAPILLARY_TERMS_API", resumen["evidencia_soft_404"])
        self.assertIn("MAPILLARY_HELP_CC_BY_SA_4_0_ARCHIVO", resumen["evidencia_archivada"])
        self.assertEqual(resumen["evidencia_registrada"], len(v.EVIDENCIA))

    def test_los_documentos_declarados_existen(self):
        for nombre in ("IMAGERY_LICENSES.md", "INSTITUTIONAL_PARTNERS.md",
                       "LICENSES_EVIDENCE.md", "SOURCE_LICENSES.md"):
            self.assertTrue((RUTA_RAIZ / "docs" / "source_pack" / nombre).exists(), nombre)
        texto = (RUTA_RAIZ / "docs" / "source_pack" / "IMAGERY_LICENSES.md").read_text(
            encoding="utf-8")
        for frase in ("IMAGERY_LICENSE_STATUS", "API_TERMS_STATUS", "SOFT_404",
                      "OPTIONAL_ENRICHMENT"):
            self.assertIn(frase, texto)
        anexo = (RUTA_RAIZ / "docs" / "source_pack" / "LICENSES_EVIDENCE.md").read_text(
            encoding="utf-8")
        self.assertIn("ANEXO v2", anexo)
        self.assertIn("no es una fuente", anexo)


if __name__ == "__main__":
    unittest.main()
