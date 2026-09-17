# -*- coding: utf-8 -*-
"""Verificación EN VIVO del caso de aceptación 240-211101 (Pasto).

Comprueba, contra el geoportal municipal de Pasto, que la DIRECCIÓN del CTL
resuelve el NUPRE correcto (…116) y que el modelo canónico queda coherente.
NO genera PDF: solo valida la resolución de identidad + contexto administrativo.

Resultado esperado (verificado EN VIVO 2026-09-18):
  nomenclatura 'K 26 21 47 AP 101' -> NUPRE 520010102000000440902900000116
  (coincide_unidad=True, ph=True, comuna='Comuna 1', estrato=3).
  canonical_identity.estado = MATCH_BY_NOMENCLATURA (el municipio NO publica
  matrícula para la UNIDAD de PH, solo la tabla de nomenclatura la contiene).
  NOTA: para la UNIDAD, las capas de POLÍGONO (tratamientos/áreas/riesgos) dan
  NO_MATCH (la unidad no tiene polígono, solo el edificio/parcela madre); el
  riesgo volcánico se evalúa aparte por PUNTO (SGC).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))

from pasto_territorio import nupre_por_nomenclatura, consultar_pasto
from canonical import build_canonical_property_identity, build_administrative_context

DIR = "K 26 21 47 AP 101"
print(f"[1] nupre_por_nomenclatura({DIR!r})")
cands = nupre_por_nomenclatura(DIR)
for c in cands:
    print("   candidato:", c["nupre"], "| coincide_unidad=", c["coincide_unidad"],
          "| ph=", c["es_ph"], "| comuna=", c.get("comuna"), "| estrato=", c.get("estrato"),
          "| nom=", repr(c["nomenclatura"])[:70])

if not cands:
    print("   SIN candidatos por nomenclatura")
    sys.exit(2)

nom = next((c for c in cands if c["coincide_unidad"]), None) or cands[0]
print(f"[2] mejor candidato NUPRE = {nom['nupre']}")

res = consultar_pasto(codigo_predial=nom["nupre"])
print(f"[3] consultar_pasto disponible={res['disponible']} resolucion={res['resolucion']}")
print("    predio:", json.dumps(res.get("predio", {}), ensure_ascii=False))
print("    entorno:", json.dumps(res.get("entorno", {}), ensure_ascii=False))
print("    riesgos:", json.dumps(res.get("riesgos", {}), ensure_ascii=False))
print("    capas:", json.dumps(res.get("capas", {}), ensure_ascii=False))

analysis = {
    "folio": "240-211101",
    "codigo_catastral": None, "nupre": None,
    "direccion": DIR,
    "titulares": "CABRERA VIVEROS JUAN SEBASTIAN",
    "anotaciones_detalle": [
        {"num": "001", "tipo": "COMPRAVENTA", "estado": "VIGENTE",
         "texto": "A: CABRERA VIVEROS JUAN SEBASTIAN CC 87070538"},
    ],
    "hipoteca_vigente": None, "acreedor_snr": None,
}
cid = build_canonical_property_identity(
    analysis=analysis, folio="240-211101", predio_real=res if res.get("disponible") else None,
    nom=nom, identidad={"estado": None}, ciudad="pasto")
ctx = build_administrative_context(ciudad="pasto", predio_real=res, nom=nom,
                                   barrio=(res.get("entorno") or {}).get("barrio") or "",
                                   estrato=(res.get("entorno") or {}).get("estrato"))
print("[4] canonical_identity.estado =", cid["estado"])
print("    nupre =", cid["nupre"])
print("    folio_snr =", cid["folio_snr"])
print("    matricula_municipal =", cid["matricula_municipal"])
print("    titular =", cid["titular"]["nombre"], cid["titular"]["tipo_persona"], cid["titular"]["numero_documento"])
print("[5] administrative_context =", json.dumps({k: v for k, v in ctx.items() if k != "trazas"}, ensure_ascii=False))
