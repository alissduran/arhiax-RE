Apreciación técnica del scraper de matrícula — ARHIAX-Real-State-Agent

Módulo catastral Barranquilla — resolución de dirección a matrícula inmobiliaria

Preparado para Sinergia Consulting Group S.A.S. — 4 de julio de 2026.

1. Resumen ejecutivo

Este informe reemplaza la apreciación preliminar generada en la sesión previa de claude.ai, que se elaboró sin acceso real al código. Se leyó directamente el repositorio clonado en ...\sector inmobiliario\RE\ARHIAX-Real-State-Agent y se identificó el archivo que resuelve una dirección de Barranquilla en un número de matrícula y una referencia catastral candidatos.

Hallazgo principal: el repositorio contiene dos rutas de datos distintas y no debe evaluarse como un bloque único. La verificación de uso de suelo y avalúo (adapters/igac.py y adapters/sinupot.py) consulta servicios REST ArcGIS reales y documentados. La resolución de dirección a matrícula —el punto que Marcelo pidió revisar— vive en un archivo distinto, adapters/barranquilla_predial.py, y depende de un formulario HTML del portal predial municipal, no de una API pública.

El adaptador declara su propia limitación en un disclaimer embebido: es una fuente de descubrimiento municipal, no un dictamen legal de título, y su resultado debe verificarse contra SNR/ORIP.

La verificación SSL del cliente HTTP está deshabilitada por defecto (ARHIAX_RE_BARRANQUILLA_PREDIAL_VERIFY_SSL=false en producción), lo que expone el flujo a un ataque de intermediario si el operador no la activa explícitamente.

No existe una prueba de integración que ejercite la ruta HTTP real contra una respuesta HTML de muestra; las pruebas actuales cubren solo el modo simulado y los parsers en aislamiento.

La duda de nomenclatura del documento de traspaso queda resuelta: el remoto origin del clon local apunta a Marcelo7225/ARHIAX-Real-State-Agent (con el error tipográfico “State”), no a Mich2Dev/ARHIAX-Real-State-Agent.

2. Identificación del repositorio y resolución de la duda de nomenclatura

El clon local declara dos remotos:


`python
origin   https://github.com/Marcelo7225/ARHIAX-Real-State-Agent.git
sinergia https://github.com/raymilito/ARHIAX-Real-State-Agent.git
`

El nombre Mich2Dev/ARHIAX-Real-State-Agent mencionado al inicio de la conversación anterior no corresponde a ningún remoto configurado en este clon. Se recomienda tratar Marcelo7225/ARHIAX-Real-State-Agent como el repositorio canónico de trabajo mientras no se aporte evidencia adicional sobre Mich2Dev.

3. Arquitectura real: dos rutas de datos independientes

El flujo de dirección a matrícula recorre exactamente un adaptador, sin pasar por IGAC ni por SINUPOT. La orquestación es la siguiente:


`python
POST /v1/properties/resolve
  -> PropertyResolutionService.resolve()
     -> gateway.adapters["BARRANQUILLA_PREDIAL"].resolve()
        -> BarranquillaPredialAdapter._resolve_runtime()   (modo runtime)
        -> BarranquillaPredialAdapter._resolve_mock()      (modo mock)
`

IGAC y SINUPOT sí consultan servicios REST ArcGIS reales — por ejemplo, para Barranquilla, igac_query_profiles.json apunta a 


`python
{
  "jurisdiction": "Barranquilla",
  "supported": true,
  "query_url": "https://appbaq.barranquilla.gov.co:9191/arcgis/rest/services/panorama/ActividadesUSOS_as_UTERRENO1a/MapServer/0/query",
  "query_params": {
    "f": "json",
    "where": "1=1",
    "returnGeometry": "false",
    "resultRecordCount": "1",
    "outFields": "DEPARTAMENTO_CODIGO,MUNICIPIO_CODIGO,TIPO_AVALUO,NOMBRE_GEOGRAFICO,CODIGO_MUNICIPIO"
  },
  "notes": "Public layer query confirmed on the published panorama service."
}
`

Esa ruta pertenece a la verificación posterior de uso de suelo y avalúo dentro de VerificationRequest, un flujo distinto del que resuelve la dirección de entrada. Confundir ambas rutas fue el origen de la lectura optimista de la sesión anterior.

4. Código real: adaptador Barranquilla Predial

Archivo completo, sin alterar, con la explicación por bloques a continuación.

src/arhiax_real_estate/adapters/barranquilla_predial.py


`python
"""Barranquilla municipal predial resolver.
 
This adapter is a discovery aid: address -> candidate folio/cadastral ids.
It is not a legal source of title truth and must be cross-checked with SNR/ORIP.
"""
 
from __future__ import annotations
 
import re
from html import unescape
from urllib.parse import urljoin
 
import httpx
 
from arhiax_real_estate.models import PropertyResolveRequest, Severity, VerificationRequest
 
from .base import AdapterAccessError, SourceAdapter
from .credentials import SourceCredential
 
 
BARRANQUILLA_PREDIAL_DISCLAIMER = (
    "Barranquilla Predial is used only as a municipal discovery source to locate "
    "candidate property identifiers from an address. It is not a legal title "
    "dictamen and must be verified against SNR/ORIP and cadastral authority records."
)
 
 
class BarranquillaPredialAdapter(SourceAdapter):
    source_name = "BARRANQUILLA_PREDIAL"
    criticality = Severity.MEDIUM
    required_scopes = ("barranquilla_predial.read",)
 
    def validate_access(self, request: VerificationRequest | PropertyResolveRequest, credential: SourceCredential | None) -> None:
        super().validate_access(request, credential)  # type: ignore[arg-type]
        city = request.property.city.strip().lower()
        municipality_code = request.property.municipality_code.strip()
        if city != "barranquilla" or municipality_code != "08001":
            raise AdapterAccessError("BARRANQUILLA_PREDIAL is enabled only for Barranquilla municipality_code 08001.")
 
    def _fetch(self, request: VerificationRequest, credential: SourceCredential | None) -> dict:
        raise AdapterAccessError("BARRANQUILLA_PREDIAL must be used through /v1/properties/resolve.")
 
    def resolve(self, request: PropertyResolveRequest, credential: SourceCredential | None = None) -> dict:
        self.validate_access(request, credential)
        if self.settings.mode == "mock":
            return self._resolve_mock(request)
        return self._resolve_runtime(request)
 
    def _resolve_mock(self, request: PropertyResolveRequest) -> dict:
        folio = request.simulation.get("predial_folio_number", "040-SYNTHETIC")
        cadastral = request.simulation.get("predial_cadastral_code", "080010001000100010001000")
        return {
            "source_execution_mode": "mock",
            "normalized_address": _normalize_address(request.property.address),
            "folio_number": folio,
            "cadastral_code": cadastral,
            "municipal_status": request.simulation.get("predial_municipal_status"),
            "confidence": float(request.simulation.get("predial_confidence", 0.82)),
            "warnings": ["Mock Barranquilla predial resolver output; not legal evidence."],
            "disclaimer": BARRANQUILLA_PREDIAL_DISCLAIMER,
        }
 
    def _resolve_runtime(self, request: PropertyResolveRequest) -> dict:
        if not self.settings.barranquilla_predial_base_url:
            raise AdapterAccessError("Barranquilla predial runtime requires ARHIAX_RE_BARRANQUILLA_PREDIAL_BASE_URL.")
        url = self._runtime_url()
        try:
            with httpx.Client(
                headers={"User-Agent": "Mozilla/5.0 ARHIAX-RE/0.2"},
                timeout=self.settings.live_source_timeout_seconds,
                follow_redirects=True,
                verify=self.settings.barranquilla_predial_verify_ssl,
            ) as client:
                landing = client.get(url)
                landing.raise_for_status()
                action_url = _form_action_url(url, landing.text) or url
                response = client.post(
                    action_url,
                    data={
                        "txtTipoBusqueda": "PorDireccion",
                        self.settings.barranquilla_predial_address_param: request.property.address,
                        "txtDato": request.property.address,
                    },
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise AdapterAccessError(f"Barranquilla predial resolver query failed: {exc}") from exc
 
        text = response.text
        folio = _first_match(
            text,
            (
                r"(?:matr[ií]cula(?:\s+inmobiliaria)?|matricula)\D{0,40}([0-9]{3}[-\s]?[0-9A-Za-z]{3,})",
                r"\b(040[-\s]?[0-9A-Za-z]{3,})\b",
            ),
        )
        cadastral = _first_match(
            text,
            (
                r"(?:referencia|registro|c[oó]digo|ref\.?)\s+catastral\D{0,80}([0-9-]{12,30})",
                r"\b(08001[0-9-]{8,25})\b",
                r"\b([0-9]{20,30})\b",
            ),
        )
        folio = _clean_identifier(folio)
        cadastral = _clean_identifier(cadastral)
        municipal_status = _municipal_status(text)
        if not folio and not cadastral:
            if municipal_status:
                return {
                    "source_execution_mode": "runtime",
                    "normalized_address": _normalize_address(request.property.address),
                    "folio_number": None,
                    "cadastral_code": None,
                    "municipal_status": municipal_status,
                    "confidence": 0.50,
                    "query_url": url,
                    "raw_response_retained": False,
                    "warnings": ["Municipal status found without cadastral reference; verify manually."],
                    "disclaimer": BARRANQUILLA_PREDIAL_DISCLAIMER,
                }
            raise AdapterAccessError("Barranquilla predial resolver returned no cadastral reference or folio identifier.")
        return {
            "source_execution_mode": "runtime",
            "normalized_address": _normalize_address(request.property.address),
            "folio_number": folio,
            "cadastral_code": cadastral,
            "municipal_status": municipal_status,
            "confidence": 0.74 if folio and cadastral else 0.60,
            "query_url": url,
            "raw_response_retained": False,
            "warnings": ["Municipal discovery result; verify against SNR/ORIP before legal reliance."],
            "disclaimer": BARRANQUILLA_PREDIAL_DISCLAIMER,
        }
 
    def _runtime_url(self) -> str:
        if not self.settings.barranquilla_predial_query_path:
            return self.settings.barranquilla_predial_base_url
        return urljoin(
            self.settings.barranquilla_predial_base_url.rstrip("/") + "/",
            self.settings.barranquilla_predial_query_path.lstrip("/"),
        )
 
 
def _first_match(text: str, patterns: tuple[str, ...]) -> str | None:
    plain = unescape(re.sub(r"<[^>]+>", " ", text))
    for pattern in patterns:
        match = re.search(pattern, plain, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None
 
 
def _form_action_url(base_url: str, html: str) -> str | None:
    match = re.search(r"<form[^>]+name=[\"']FrmBuscarPredio[\"'][^>]+action=[\"']([^\"']+)[\"']", html, flags=re.IGNORECASE)
    if not match:
        match = re.search(r"<form[^>]+action=[\"']([^\"']*BuscarPredioLiq\.do[^\"']*)[\"']", html, flags=re.IGNORECASE)
    if not match:
        return None
    return urljoin(base_url, unescape(match.group(1)))
 
 
def _clean_identifier(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().replace(" ", "").replace("\xa0", "")
    if "X" in cleaned.upper():
        return None
    return cleaned
 
 
def _municipal_status(text: str) -> str | None:
    plain = unescape(re.sub(r"<[^>]+>", " ", text)).lower()
    if "paz y salvo" in plain:
        return "PAZ_Y_SALVO"
    if any(term in plain for term in ("deuda", "debe", "saldo pendiente", "mora")):
        return "PENDING_BALANCE"
    return None
 
 
def _normalize_address(value: str) -> str:
    return " ".join(value.strip().upper().split())
`

4.1 Explicación por bloques

Encabezado y disclaimer (líneas 1–25)

El docstring del módulo ya advierte que se trata de “un asistente de descubrimiento” y no de una fuente legal de título. BARRANQUILLA_PREDIAL_DISCLAIMER se reutiliza más abajo en el payload de respuesta y en PropertyResolutionService, de modo que el consumidor de la API siempre recibe la advertencia.

Validación de acceso (líneas 33–38)

Se sobreescribe validate_access para añadir, sobre la validación genérica de SourceAdapter, una restricción geográfica dura: solo se acepta city == "barranquilla" y municipality_code == "08001". Cualquier otra ciudad recibe un AdapterAccessError, que main.py traduce a un HTTP 403.

Bloqueo del flujo de verificación (líneas 40–41)

_fetch —el método que usan los demás adaptadores dentro de una verificación completa— está deshabilitado deliberadamente. Este adaptador solo se puede invocar a través de resolve(), es decir, únicamente desde el endpoint de resolución de propiedad. Es una decisión de diseño correcta: impide que el scraper se dispare como efecto colateral de otra operación.

Selección de modo (líneas 43–47)

Cuando settings.mode == "mock" se devuelve una respuesta simulada y determinista; en cualquier otro modo se ejecuta _resolve_runtime, que es donde ocurre el scraping real.

Modo simulado (líneas 49–61)

Genera una matrícula y una referencia catastral sintéticas a partir de request.simulation, con valores por defecto (040-SYNTHETIC) si el llamador no los provee. Útil para pruebas, inútil para producción.

Petición HTTP real (líneas 63–87)

La secuencia es la de un scraper de formulario clásico, no la de un consumo de API:

client.get(url) descarga la página de aterrizaje del portal (Predial/Liq100.jsp por defecto).

_form_action_url busca con una expresión regular el atributo action del formulario FrmBuscarPredio (o, en su defecto, cualquier acción que contenga BuscarPredioLiq.do). Si el portal cambia el nombre del formulario o su marcado, esta búsqueda deja de encontrar coincidencias y el flujo cae al url original como respaldo silencioso.

client.post(action_url, data={...}) envía la dirección como si fuera un usuario llenando el formulario: "txtTipoBusqueda": "PorDireccion" y el parámetro de dirección configurable (direccion por defecto).

Cualquier error HTTP se recoge en un único except httpx.HTTPError y se relanza como AdapterAccessError, que el endpoint traduce a 403 en lugar de a un 502 o 504 más preciso para un fallo de origen externo.

Extracción por expresiones regulares (líneas 89–122)

La respuesta HTML se limpia de etiquetas (re.sub(r"<[^>]+>", " ", text)) y se busca sobre el texto plano con patrones alternativos:

para la matrícula: variantes de “matrícula inmobiliaria” seguidas de dígitos, o un patrón genérico 040-...;

para la referencia catastral: variantes de “referencia/registro/código catastral”, o un patrón genérico que empieza en 08001, o —como último recurso— cualquier secuencia de 20 a 30 dígitos, lo que puede confundir otros identificadores numéricos largos presentes en la página con la referencia catastral;

si no aparece ni matrícula ni referencia pero sí un estado municipal (“paz y salvo” o deuda pendiente), se devuelve un resultado parcial con confianza baja (0.50) en lugar de fallar;

si no se encuentra nada, se lanza AdapterAccessError con el mensaje “no cadastral reference or folio identifier”.

Limpieza de identificadores (líneas 163–169)

_clean_identifier descarta cualquier valor que contenga la letra “X”, previsto para los casos en que el portal enmascara el dato con marcadores de posición (por ejemplo, 040-XXXXXX), tal como confirma la prueba test_predial_parser_rejects_masked_placeholder_identifiers.

Normalización de dirección (línea 181–182)

Convierte la dirección a mayúsculas y colapsa espacios múltiples; no traduce el formato coloquial (“Cl 72 # 43-15”) a la nomenclatura oficial que espera el formulario, contra lo que recomendaba el flujo ideal de la sesión anterior.

5. Configuración runtime asociada

Extracto de src/arhiax_real_estate/config.py con los parámetros que gobiernan el comportamiento del adaptador:


`python
barranquilla_predial_base_url: str = os.getenv(
    "ARHIAX_RE_BARRANQUILLA_PREDIAL_BASE_URL",
    "https://orion.barranquilla.gov.co:8787/Predial/Liq100.jsp",
)
barranquilla_predial_query_path: str = os.getenv("ARHIAX_RE_BARRANQUILLA_PREDIAL_QUERY_PATH", "")
barranquilla_predial_address_param: str = os.getenv("ARHIAX_RE_BARRANQUILLA_PREDIAL_ADDRESS_PARAM", "direccion")
barranquilla_predial_verify_ssl: bool = (
    os.getenv("ARHIAX_RE_BARRANQUILLA_PREDIAL_VERIFY_SSL", "false").lower() == "true"
)
`

Observación de seguridad: la verificación SSL queda deshabilitada salvo que el operador fije explícitamente ARHIAX_RE_BARRANQUILLA_PREDIAL_VERIFY_SSL=true. Dado que el dominio por defecto (orion.barranquilla.gov.co:8787) usa un puerto no estándar, es razonable sospechar que el certificado del portal municipal presenta problemas de validación y que esta bandera se introdujo como salida rápida; conviene documentar la causa raíz antes de aceptar el riesgo en producción.

6. Orquestación: servicio y endpoint

src/arhiax_real_estate/services/property_resolution.py


`python
"""Address-to-property identifier resolution."""
 
from __future__ import annotations
 
from arhiax_real_estate.adapters.barranquilla_predial import BARRANQUILLA_PREDIAL_DISCLAIMER
from arhiax_real_estate.adapters.sources import SourceGateway, stable_hash
from arhiax_real_estate.models import (
    PropertyResolveRequest,
    PropertyResolveResponse,
    ResolvedPropertyCandidate,
)
 
 
class PropertyResolutionService:
    """Resolves address-only Barranquilla properties into candidate identifiers."""
 
    def __init__(self, gateway: SourceGateway):
        self.gateway = gateway
 
    def resolve(self, request: PropertyResolveRequest) -> PropertyResolveResponse:
        adapter = self.gateway.adapters["BARRANQUILLA_PREDIAL"]
        credential = self.gateway.credential_provider.resolve(
            request=request,  # type: ignore[arg-type]
            source="BARRANQUILLA_PREDIAL",
            required=adapter.requires_credentials,
        )
        payload = adapter.resolve(request, credential)  # type: ignore[attr-defined]
        payload_hash = stable_hash(payload)
        candidate = ResolvedPropertyCandidate(
            folio_number=payload.get("folio_number"),
            cadastral_code=payload.get("cadastral_code"),
            normalized_address=payload["normalized_address"],
            municipal_status=payload.get("municipal_status"),
            confidence=payload["confidence"],
            source_payload_hash=payload_hash,
            warnings=payload.get("warnings", []),
            verification_seed={
                "folio_number": payload.get("folio_number"),
                "cadastral_code": payload.get("cadastral_code"),
                "address": payload["normalized_address"],
                "city": "Barranquilla",
                "municipality_code": "08001",
                "municipal_status": payload.get("municipal_status"),
            },
        )
        status = "RESOLVED" if candidate.folio_number or candidate.cadastral_code else "RESOLVED_PARTIAL"
        return PropertyResolveResponse(
            request_id=request.request_id,
            status=status,
            candidates=[candidate] if status == "RESOLVED" else [],
            source_hashes={"BARRANQUILLA_PREDIAL": payload_hash},
            disclaimer=BARRANQUILLA_PREDIAL_DISCLAIMER,
        )
`

PropertyResolutionService.resolve calcula un hash estable del payload crudo (stable_hash) y lo adjunta como source_hashes, lo que da trazabilidad de qué respuesta concreta del portal originó cada candidato — un mecanismo de proveniencia consistente con el estándar de gobernanza ARHIAX. El estado de la respuesta es RESOLVED solo si aparece folio o referencia catastral; en caso contrario es RESOLVED_PARTIAL sin candidatos, lo que empuja correctamente la decisión hacia el consumidor de la API.

El endpoint expuesto en main.py es:


`python
@app.post("/v1/properties/resolve", response_model=PropertyResolveResponse)
def resolve_property(request: PropertyResolveRequest) -> PropertyResolveResponse:
    try:
        return property_resolution.resolve(request)
    except (AdapterAccessError, CredentialResolutionError) as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
`

Toda excepción de acceso o de credenciales se traduce a HTTP 403, incluidos los fallos de red hacia el portal municipal (ver sección 4, bloque de petición HTTP). Un timeout o una caída del portal de Barranquilla se reportan hoy como un problema de autorización del cliente, lo cual puede inducir a error a quien integra la API.

7. Cobertura de pruebas existente

El archivo tests/test_barranquilla_predial_resolver.py cubre:

la resolución exitosa en modo simulado contra el endpoint /v1/properties/resolve;

el rechazo con 422 cuando la ciudad no es Barranquilla;

el rechazo con 403 cuando el cliente no tiene autorizada la fuente;

la presencia del adaptador en /v1/compliance/posture;

los parsers _first_match, _clean_identifier y _municipal_status en aislamiento, con fragmentos de HTML de muestra.

Vacío identificado: no hay ninguna prueba que ejecute _resolve_runtime de extremo a extremo con un servidor HTTP simulado (por ejemplo, con respx o httpx.MockTransport). La lógica de descubrimiento del formulario (_form_action_url) y la secuencia GET seguida de POST nunca se ejercitan contra una página de aterrizaje realista, de modo que un cambio en el HTML del portal podría romper el flujo sin que ninguna prueba lo detecte.

8. Escenario A frente a escenario B, aplicado al caso real


`python
Dimensión
Situación real en el repositorio
Lectura
Punto de entrada de dirección
Ruta HTML del formulario predial (“Liq100.jsp” + “BuscarPredioLiq.do”)
Escenario B: depende del marcado HTML y del nombre del formulario
Verificación posterior de uso de suelo
ArcGIS REST MapServer documentado (IGAC/SINUPOT)
Escenario A: contrato estable, versionado
Estabilidad del dato de matrícula
Regex sobre texto plano, con patrón genérico de último recurso (20 a 30 dígitos)
Riesgo de falso positivo si la página cambia de estructura
Seguridad de transporte
SSL deshabilitado por defecto
Riesgo de intermediario si no se activa la bandera
Gobernanza y trazabilidad
Hash estable del payload y disclaimer explícito en cada respuesta
Alineado con el estándar ARHIAX de proveniencia
`

9. Recomendaciones de optimización

Priorizadas por relación entre esfuerzo e impacto, referidas al código real leído en esta sesión:

Activar la verificación SSL por defecto. Cambiar el valor por defecto de ARHIAX_RE_BARRANQUILLA_PREDIAL_VERIFY_SSL a true e investigar la causa del problema de certificado del portal en lugar de desactivar la validación de forma permanente.

Diferenciar los códigos de error. En main.py, distinguir un fallo de origen externo (portal caído, timeout) de un fallo de autorización del cliente, en vez de mapear ambos a 403.

Añadir una prueba de integración con servidor simulado. Ejercitar _resolve_runtime completo —GET de aterrizaje, descubrimiento del formulario y POST— contra fixtures de HTML representativos del portal real, incluida una variante donde el formulario cambia de nombre.

Acotar el patrón de referencia catastral. El patrón de último recurso (\b([0-9]{20,30})\b) puede capturar cualquier número largo presente en la página que no sea la referencia catastral; conviene exigir contexto textual mínimo o descartarlo si aparece más de una coincidencia.

Normalizar la dirección de entrada contra la nomenclatura oficial. Antes de enviarla al formulario, convertir abreviaturas coloquiales (“Cl”, “Kr”, “#”) al formato que espera el portal, para reducir resultados vacíos por variación de escritura.

Evaluar una vía de datos abiertos como respaldo. El hallazgo de la sesión anterior sobre el servicio ArcGIS de datos abiertos del área metropolitana sigue siendo válido como posible fuente alterna de descubrimiento, aunque no reemplaza la vía predial actual sin una prueba de correspondencia de campos.

Documentar el disclaimer en la capa de integración del cliente. El disclaimer ya existe en el backend; conviene asegurarse de que cualquier interfaz o reporte que consuma este endpoint lo muestre de forma igual de visible.

10. Conclusión

El adaptador de matrícula por dirección para Barranquilla existe, funciona bajo el diseño previsto y ya incorpora salvaguardas de gobernanza —disclaimer, hash de proveniencia, restricción geográfica estricta—. Su punto débil no es de gobernanza sino de robustez técnica: depende de un formulario HTML sujeto a cambio, con verificación SSL deshabilitada por defecto y sin prueba de integración que detecte una ruptura del portal. Las recomendaciones de la sección 9 atienden exactamente esos tres puntos, en orden de urgencia.

Fin del informe.

