"""Clasificación de régimen SAGRILAFT+PTEE — motor de aplicabilidad determinable (P0-4).

Corrige el proxy anterior (solo ingresos/activos/sector). Ahora exige hechos verificables
(supervisor, CIIU, tamaño) y, si falta alguno, retorna **NO_DETERMINABLE** en lugar de un
verdicto. El régimen solo se declara cuando el alcance está confirmado:
    - Supervisor = Supersociedades (si se conoce y es otro, queda fuera de este régimen).
    - CIIU sectorial (inmobiliario 68xx, construcción, comercio de vehículos) o dato de tamaño.
    - Umbrales UVB versionados.
"""
from dataclasses import dataclass

# Umbrales en UVB (Circular 100-000020, Cap. IX). UVB 2026 = $12.110 (Res. 3488/2025).
UMBRALES_UVB = {
    "pleno_general": 4_929_017,
    "pleno_reforzado": 3_696_762,
    "rmm_ingresos": 369_676,
    "rmm_activos": 616_127,
}

SUPERVISOR_SUPERSOCIEDADES = ("supersociedades",)

# CIIUs / sectores del articulado (9.5.1/9.5.5/9.5.6, 9.6.1).
CIIU_INMOBILIARIO = ("681", "682")
CIIU_CONSTRUCCION = ("411", "4120", "4290", "451")
CIIU_COMERCIO_VEHICULOS = ("4511", "4512", "4540")
SECTORES_REFORZADOS = {"inmobiliario", "construccion", "comercializacion", "vehiculos"}


@dataclass(frozen=True)
class ClasificacionRegimen:
    regimen: str  # pleno_general | pleno_reforzado | rmm | no_obligado | no_determinable
    fundamento: str
    umbral_aplicado: str


def _nod(fundamento):
    return ClasificacionRegimen("no_determinable", fundamento, "hechos insuficientes")


def _sectorial(ciiu, sector):
    c = (ciiu or "").strip()
    s = (sector or "").strip().lower()
    if c.startswith(CIIU_INMOBILIARIO) or s in ("inmobiliario",):
        return "inmobiliario"
    if c.startswith(CIIU_CONSTRUCCION) or s in ("construccion",):
        return "construccion"
    if c.startswith(CIIU_COMERCIO_VEHICULOS) or s in ("vehiculos", "comercializacion"):
        return "vehiculos"
    return ""


def clasificar_regimen(ingresos, activos, sector, *, uvb=12110.0, supervisor=None, ciiu=None):
    """Devuelve el régimen estimado o NO_DETERMINABLE si el alcance no está confirmado."""
    supervisor = (supervisor or "").strip() or None
    ciiu = (ciiu or "").strip() or None
    # 1) Superbase conocida y distinta a Supersociedades -> fuera de alcance de esta Circular.
    if supervisor is not None and str(supervisor).strip().lower() not in SUPERVISOR_SUPERSOCIEDADES:
        return _nod("supervisado por " + str(supervisor) + " (régimen de otra superintendencia)")

    # 2) Sin hechos mínimos -> no determinar.
    if ciiu is None and supervisor is None and ingresos is None and activos is None:
        return _nod("sin supervisor, CIIU ni tamaño para determinar el régimen")

    s = _sectorial(ciiu, sector)
    ing_uvb = (ingresos or 0.0) / uvb
    act_uvb = (activos or 0.0) / uvb

    # Sin tamaño ni sector/ciiu conocido -> no determina.
    if (ingresos is None and activos is None) and not s:
        return _nod("sin tamaño ni sector/CIIU para aplicar umbrales")

    umbral_pleno = (UMBRALES_UVB["pleno_reforzado"] if s in SECTORES_REFORZADOS
                    else UMBRALES_UVB["pleno_general"])
    if ing_uvb >= umbral_pleno or act_uvb >= umbral_pleno:
        regimen = "pleno_reforzado" if s in SECTORES_REFORZADOS else "pleno_general"
        return ClasificacionRegimen(regimen, "supera umbral pleno (UVB)", f"{umbral_pleno} UVB")
    if ing_uvb >= UMBRALES_UVB["rmm_ingresos"] or act_uvb >= UMBRALES_UVB["rmm_activos"]:
        return ClasificacionRegimen("rmm", "dentro de medidas mínimas (UVB)",
                                    f"{UMBRALES_UVB['rmm_ingresos']} ingresos / {UMBRALES_UVB['rmm_activos']} activos UVB")
    # Solo se declara no_obligado si el sujeto está dentro del alcance (sector/CIIU) pero bajo umbral.
    if s:
        return ClasificacionRegimen("no_obligado", "en alcance sectorial pero bajo umbral RMM", "bajo RMM UVB")
    return _nod("sin sector/CIIU confirmado; verificar alcance")
