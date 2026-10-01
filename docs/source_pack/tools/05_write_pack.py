"""STEP 3 — Write the Source Pack (final).

For every business concept requested, this resolves the requested layer id against the REAL
captured layer/table index, records the verdict with evidence, and attaches the REAL layer(s)
that serve that concept — with their real field lists and one real sample row each.

Nothing is synthesised: field lists, aliases and sample rows come from captured responses;
absences are backed by the captured index and by concrete ArcGIS error responses.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import _fetch  # noqa: E402
from _fetch import CACHE, _looks_like_arcgis, fetch  # noqa: E402

_fetch.MIN_GAP = 0.25
ORDER = ["allorigins"] * 6 + ["codetabs", "cors_eu_org"]
GOLD = Path(__file__).resolve().parents[1] / "raw" / "golden"

CAT_FS = "https://miciudad.barranquilla.gov.co/gis/rest/services/catastro/datosabiertos/FeatureServer"
CAT_MS = "https://miciudad.barranquilla.gov.co/gis/rest/services/catastro/datosabiertos/MapServer"
UNI = "https://miciudad.barranquilla.gov.co/gis/rest/services/ordenamiento/unidadesadministrativas/MapServer"
PLA = "https://miciudad.barranquilla.gov.co/gis/rest/services/ordenamiento/planeacion/MapServer"
AME = "https://miciudad.barranquilla.gov.co/gis/rest/services/riesgos/amenazas/MapServer"
EST = "https://miciudad.barranquilla.gov.co/gis/rest/services/ordenamiento/estratificacion/MapServer"
DIR = "https://miciudad.barranquilla.gov.co/gis/rest/services/ordenamiento/direcciones/MapServer"
EPU = "https://miciudad.barranquilla.gov.co/gis/rest/services/espaciopublico/infraestructuraespaciopublico/MapServer"
EDU = "https://miciudad.barranquilla.gov.co/gis/rest/services/educacion/infraestructuraeducativa/MapServer"
SAL = "https://miciudad.barranquilla.gov.co/gis/rest/services/salud/infraestructurasalud/MapServer"
DEP = "https://miciudad.barranquilla.gov.co/gis/rest/services/recreacionydeporte/infraestructuradeporte/MapServer"
SIT = "https://miciudad.barranquilla.gov.co/gis/rest/services/sitios/sitiosdeinteres/MapServer"

# business key fields the requester asked about
KEY_FIELDS = ["numero_predial", "numero_predial_anterior", "condicion_predio", "tipo_predio",
              "estado_predio", "destinacion_economica", "clase_suelo", "categoria_suelo",
              "codigo_homologado", "vigencia", "fecha_inscripcion", "area_catastral_terreno",
              "aplica_efectos_registrales", "simb_activ", "actividad", "poligono", "nombre_uso",
              "etiqueta", "tratamient", "tipo_trata", "altura_max", "nivel", "zona", "riesedif",
              "riespers", "riesmit", "nombre", "localidad"]

# (file, concept, requested_id, alternate requested ids, [(service, layer_id, label), ...])
SPECS = [
    ("direccion.json", "Direcciones / gerencia", 0, [], [
        (CAT_FS, 105, "Direccion (punto de direccion oficial)"),
        (CAT_FS, 110, "Nomenclatura vial"),
        (DIR, 1, "Codigo postal")]),
    ("terreno.json", "Terreno", 3, [], [
        (CAT_FS, 315, "Terreno (poligono)"),
        (CAT_FS, 205, "TerrenoL (lineas catastrales)")]),
    ("construccion.json", "Construccion", 4, [], [
        (CAT_FS, 310, "Construccion (poligono)"),
        (CAT_FS, 305, "Unidad de Construccion")]),
    ("catastro_predio.json", "Predio (tabla)", 100, [], [
        (CAT_FS, 500, "Predio (tabla)"),
        (CAT_FS, 505, "Caracteristicas Unidad de Construccion"),
        (CAT_FS, 545, "Datos Adicionales de Levantamiento Catastral")]),
    ("barrios.json", "Barrios (division territorial POT)", 91, [], [
        (UNI, 1, "Barrios")]),
    ("localidades.json", "Localidades (division territorial POT)", 92, [], [
        (UNI, 3, "Localidades"),
        (UNI, 4, "Municipios")]),
    ("uso.json", "Areas de actividad / uso del suelo (POT)", 85, [87], [
        (PLA, 2, "Norma uso suelo"),
        (PLA, 1, "Clases de suelo")]),
    ("tratamiento.json", "Tratamiento urbanistico (POT)", 83, [], [
        (PLA, 4, "Tratamientos urbanisticos")]),
    ("edificabilidad.json", "Edificabilidad (POT)", 89, [], [
        (PLA, 2, "Norma uso suelo (edificabilidad en atributos)"),
        (PLA, 5, "Planes de reordenamiento")]),
    ("remocion.json", "Remocion en masa", 73, [71], [
        (AME, 2, "Amenaza por remocion en masa")]),
    ("inundacion.json", "Inundacion", 77, [75], [
        (AME, 1, "Amenaza por inundacion")]),
    ("riesgo.json", "Riesgo", 81, [79], [
        (AME, 1, "Amenaza por inundacion"),
        (AME, 2, "Amenaza por remocion en masa")]),
]

EQUIP = ("equipment.json", "Equipamiento oficial", [18, 20, 21, 22, 23, 24, 25, 26, 27], [
    (EPU, 4, "Nodos de equipamientos"),
    (EPU, 3, "Espacio publico"),
    (EPU, 2, "Parques"),
    (EDU, 1, "Instituciones de educacion superior"),
    (EDU, 2, "Educacion basica y media"),
    (SAL, 1, "Salud privada"),
    (SAL, 2, "Mi Red Barranquilla IPS"),
    (DEP, 1, "Canchas"),
    (DEP, 2, "Escenarios deportivos"),
    (SIT, 2, "Sitios de interes")])


def load_index() -> tuple[dict, list]:
    idx: dict[int, list] = {}
    services = []
    for f in sorted(CACHE.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not d.get("ok") or not _looks_like_arcgis(d.get("data")):
            continue
        url = (d.get("provenance") or {}).get("requested_url", "")
        data = d["data"]
        if not isinstance(data, dict):
            continue
        if "layers" in data or ("tables" in data and "currentVersion" in data):
            if isinstance(data.get("error"), dict):
                continue
            svc = url.replace("?f=json", "")
            services.append({"service_url": svc, "n_layers": len(data.get("layers") or []),
                             "n_tables": len(data.get("tables") or []),
                             "currentVersion": data.get("currentVersion"),
                             "spatialReference": data.get("spatialReference"),
                             "maxRecordCount": data.get("maxRecordCount"),
                             "capabilities": data.get("capabilities")})
            for kind in ("layers", "tables"):
                for l in data.get(kind) or []:
                    if l.get("id") is None:
                        continue
                    idx.setdefault(l["id"], []).append(
                        {"service_url": svc, "layer_id": l["id"], "name": l.get("name"),
                         "kind": kind[:-1], "is_group": bool(l.get("subLayerIds"))})
    return idx, services


def capture(service_url: str, layer_id: int) -> dict:
    md = fetch(f"{service_url}/{layer_id}?f=json", budget=26, timeout=25, order=ORDER)
    sq = fetch(f"{service_url}/{layer_id}/query?where=1=1&resultRecordCount=1&outFields=*&f=json",
               budget=26, timeout=25, order=ORDER)
    d = md["data"] if md["ok"] and isinstance(md["data"], dict) else None
    out = {"service_url": service_url, "layer_id": layer_id,
           "layer_metadata_url": f"{service_url}/{layer_id}?f=json",
           "layer_metadata_provenance": md["provenance"],
           "sample_query_url": (f"{service_url}/{layer_id}/query?where=1=1"
                                "&resultRecordCount=1&outFields=*&f=json"),
           "sample_query_provenance": sq["provenance"]}
    if d is not None and isinstance(d.get("error"), dict):
        out["_status"] = "LAYER_METADATA_ERROR"
        out["arcgis_error"] = d["error"]
    elif d is not None:
        out["_status"] = "OK"
        out["layer_name"] = d.get("name")
        out["layer_type"] = d.get("type")
        out["geometry_type"] = d.get("geometryType")
        out["display_field"] = d.get("displayField")
        out["object_id_field"] = d.get("objectIdField")
        out["max_record_count"] = d.get("maxRecordCount")
        out["field_count"] = len(d.get("fields") or [])
        out["fields"] = [{"name": fl.get("name"), "alias": fl.get("alias"),
                          "type": fl.get("type"), "length": fl.get("length")}
                         for fl in (d.get("fields") or [])]
        out["raw_layer_metadata"] = d
    else:
        out["_status"] = "LAYER_METADATA_UNAVAILABLE"
    s = sq["data"] if sq["ok"] else None
    if isinstance(s, dict) and isinstance(s.get("error"), dict):
        out["sample_query"] = None
        out["sample_query_arcgis_error"] = s["error"]
    else:
        out["sample_query"] = s
    if not sq["ok"]:
        out["sample_query_note"] = "no transport returned a valid query response"
    return out


def key_field_hits(field_names: list[str]) -> dict:
    present, absent = {}, []
    lowered = {f.lower(): f for f in field_names}
    for k in KEY_FIELDS:
        hit = next((orig for low, orig in lowered.items() if k in low), None)
        if hit:
            present[k] = hit
        else:
            absent.append(k)
    return {"present": present, "absent": absent}


def main() -> None:
    idx, services = load_index()
    print(f"readable service roots: {len(services)}  distinct layer/table ids: {len(idx)}")
    ids_sorted = sorted(idx.keys())
    (GOLD / "_real_layer_inventory.json").write_text(json.dumps(
        {"generated_from": "raw/golden/_raw_cache (raw ArcGIS REST responses)",
         "readable_services": services, "ids": {str(k): v for k, v in sorted(idx.items())}},
        indent=2, ensure_ascii=False), encoding="utf-8")

    matrix = {}
    report = {"specs": [], "equipment": None, "ids_in_captured_index": ids_sorted}

    def build(fname, concept, rids, alts, equivs, out_doc):
        real = []
        for svc, lid, label in equivs:
            entry = {"label": label, "resolved": (idx.get(lid) or [{}])[0] if idx.get(lid) else None,
                     "captured": capture(svc, lid)}
            fields = [f["name"] for f in (entry["captured"].get("fields") or [])]
            entry["key_fields"] = key_field_hits(fields)
            real.append(entry)
            n = len(fields)
            print(f"     {label:52s} {entry['captured']['_status']:26s} fields={n}")
            matrix.setdefault(fname, {})[label] = {"service_url": svc, "layer_id": lid,
                                                   "status": entry["captured"]["_status"],
                                                   "field_count": n,
                                                   "key_fields_present": entry["key_fields"]["present"],
                                                   "key_fields_absent": entry["key_fields"]["absent"]}
        out_doc["real_equivalents"] = real
        (GOLD / fname).write_text(json.dumps(out_doc, indent=2, ensure_ascii=False), encoding="utf-8")

    for fname, concept, rid, alts, equivs in SPECS:
        exists = idx.get(rid)
        doc = {"source_id": fname.replace(".json", ""), "business_concept": concept,
               "requested_layer_id": rid, "alternate_requested_ids": alts}
        if exists and not all(e["is_group"] for e in exists):
            doc["_status"] = "SUPPORTED"
            doc["resolved"] = exists
            print(f"  SUPPORTED           {fname:22s} id={rid} -> {exists[0]['service_url']} "
                  f":: {exists[0]['name']}")
        elif exists:
            doc["_status"] = "ID_EXISTS_DIFFERENT_LAYER"
            doc["resolved"] = exists
            doc["reason"] = (f"Id {rid} exists but is a group layer named "
                             f"{exists[0]['name']!r}, not the layer this business concept needs; "
                             "group layers carry no fields of their own.")
            print(f"  ID_EXISTS_GROUP     {fname:22s} id={rid} -> {exists[0]['name']!r}")
        else:
            doc["_status"] = "NOT_SUPPORTED"
            doc["reason"] = (f"No service in the Barranquilla ArcGIS tree exposes layer/table id "
                             f"{rid}. The service exposes ids {ids_sorted}. Verdict is based on the "
                             "captured root metadata of every service that could be read.")
            print(f"  NOT_SUPPORTED       {fname:22s} id={rid}")
        doc["evidence"] = {
            "ids_present_in_captured_index": ids_sorted,
            "requested_id_present": bool(exists),
            "requested_id_present_meaning": exists[0] if exists else None,
            "readable_services_count": len(services),
            "readable_services": [s["service_url"] for s in services],
            "note": ("catastro/datosabiertos/MapServer answers code 500 'Service ... not started' "
                     "for every layer/table, so its layer metadata is served by the FeatureServer "
                     "of the same service instead."),
        }
        build(fname, concept, [rid], alts, equivs, doc)
        report["specs"].append({"file": fname, "requested_id": rid, "status": doc["_status"],
                                "real_equivalents": len(equivs)})

    fname, concept, rids, equivs = EQUIP
    doc = {"source_id": "equipment", "business_concept": concept, "requested_layer_ids": rids}
    present = [r for r in rids if idx.get(r)]
    doc["_status"] = "PARTIAL" if present else "NOT_SUPPORTED"
    doc["requested_ids_present"] = present
    doc["requested_ids_absent"] = [r for r in rids if not idx.get(r)]
    doc["reason"] = (f"None of the requested equipment ids {rids} exist in the captured "
                     f"layer/table index (which holds ids {ids_sorted}). The service models "
                     "official equipment as named layers inside sectoral services.")
    doc["evidence"] = {"ids_present_in_captured_index": ids_sorted,
                       "readable_services_count": len(services)}
    print(f"  equipment.json -> {doc['_status']}")
    build(fname, concept, rids, [], equivs, doc)
    report["equipment"] = {"status": doc["_status"], "real_equivalents": len(equivs)}

    # domain metadata files
    def pick(patterns):
        return [s for s in services if any(p in s["service_url"].lower() for p in patterns)]

    for fn, pats in (("catastro_metadata.json", ["catastro"]),
                     ("pot_metadata.json", ["ordenamiento"]),
                     ("riesgo_metadata.json", ["riesgo", "amenaza"]),
                     ("equipment_metadata.json", ["espaciopublico", "educacion", "salud",
                                                  "recreacionydeporte", "sitios"])):
        picked = pick(pats)
        d = {"generated_from": "raw/golden/_raw_cache", "match_patterns": pats,
             "services_readable": len(picked), "services": picked,
             "layer_table_index": {str(k): [e for e in v if e["service_url"] in
                                            [s["service_url"] for s in picked]]
                                   for k, v in sorted(idx.items())}}
        d["layer_table_index"] = {k: v for k, v in d["layer_table_index"].items() if v}
        (GOLD / fn).write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  {fn}: {len(picked)} services")

    (GOLD / "_key_fields_matrix.json").write_text(json.dumps(matrix, indent=2, ensure_ascii=False),
                                                  encoding="utf-8")
    (GOLD / "_resolution_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                                  encoding="utf-8")
    print("\nwrote _key_fields_matrix.json, _resolution_report.json, _real_layer_inventory.json")


if __name__ == "__main__":
    main()
