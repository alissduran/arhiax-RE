/* DICTUS · Portal de confianza inmobiliaria — lógica de lectura sobre la API real.
 *
 * Reglas de la casa (docs/ui/00_DECISIONES.md), aplicadas a esta pantalla:
 *   D2  todo dato sale de un contrato existente; lo que no existe se declara.
 *   D4  nunca un valor por defecto: si no hay dato, se imprime el estado y el motivo.
 *   D7  el portal LEE: la única escritura es el inicio de sesión (autenticación).
 *
 * El token de sesión vive SOLO en memoria (no se persiste en localStorage).
 */
'use strict';

/* Base de la API: por defecto el MISMO ORIGEN (producción sirve `public/` y `/api/*`
 * juntos). Para abrir este portal suelto:
 *   python -m http.server 8000 --directory ui
 *   http://localhost:8000/portal/?api=https://arhiax-re.vercel.app
 * `http://localhost:8000` está en la lista blanca de CORS del backend. */
const API = new URLSearchParams(location.search).get('api') || '';

const state = {
  token: null, usuario: null, rol: null,
  casos: [], caso: null, documentos: [],
  resolucion: null, fuentes: [], pestana: 'resumen', perspectiva: 'inmobiliaria'
};

const $ = (id) => document.getElementById(id);

/* ── Utilidades ─────────────────────────────────────────────────────────────── */

function esc(v) {
  return String(v === null || v === undefined ? '' : v)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function esVacio(v) {
  return v === null || v === undefined || v === '' ||
    String(v).trim().toLowerCase() === 'pendiente' ||
    String(v).trim().toLowerCase() === 'n/d';
}

function toast(texto) {
  const caja = $('toast');
  $('toast-text').textContent = texto;
  caja.classList.add('on');
  clearTimeout(caja._t);
  caja._t = setTimeout(() => caja.classList.remove('on'), 3400);
}

/* Estado de verdad -> clase del chip. La traducción es CONSERVADORA: un valor solo
 * se muestra como verificado si la fuente lo declara verificado. */
const CLASE_POR_ESTADO = {
  VERIFIED_OFFICIAL: ['ok', 'VERIFICADO · OFICIAL'],
  VERIFIED_REGISTRAL: ['ok', 'VERIFICADO · REGISTRAL'],
  VERIFIED_CATASTRAL: ['ok', 'VERIFICADO · CATASTRAL'],
  VERIFIED_CATASTRAL_TEMATICO: ['ok', 'VERIFICADO · TEMÁTICO'],
  VERIFIED_GEOGRAPHIC: ['ok', 'VERIFICADO · GEOGRÁFICO'],
  OK: ['ok', 'RESPONDE'],
  UNRESOLVED: ['warn', 'PENDIENTE'],
  PARTIAL: ['warn', 'PARCIAL'],
  NO_MATCH: ['warn', 'SIN COINCIDENCIA'],
  AMBIGUOUS: ['warn', 'AMBIGUO'],
  NO_PARSEABLE: ['warn', 'NO INTERPRETABLE'],
  CONFLICT: ['err', 'CONFLICTO'],
  SOURCE_UNAVAILABLE: ['info', 'FUENTE NO DISPONIBLE'],
  ERROR: ['err', 'ERROR'],
  CONTRATO_FALTANTE: ['warn', 'CONTRATO FALTANTE']
};

function chip(estado, textoAlterno) {
  const [clase, etiqueta] = CLASE_POR_ESTADO[estado] || ['info', String(estado || 'SIN ESTADO')];
  return '<span class="chip ' + clase + '">' + esc(textoAlterno || etiqueta) + '</span>';
}

/** Valor de un campo con su estado y su MOTIVO. Regla D4: el hueco se explica,
 * nunca se imprime un guion mudo ni un valor por defecto. */
function valorCampo(campo) {
  const c = campo || {};
  if (esVacio(c.value)) {
    return '<span class="mono">—</span> ' + chip(c.status || 'UNRESOLVED') +
      ' <span class="t-xs muted">' + esc(c.motivo || 'sin motivo declarado') + '</span>';
  }
  return '<span class="mono">' + esc(c.value) + '</span> ' + chip(c.status || 'UNRESOLVED');
}

async function api(ruta, opciones = {}) {
  const headers = Object.assign({ 'Accept': 'application/json' }, opciones.headers || {});
  if (state.token) headers['Authorization'] = 'Bearer ' + state.token;
  const r = await fetch(API + ruta, Object.assign({}, opciones, { headers }));
  let cuerpo = null;
  try { cuerpo = await r.json(); } catch (e) { cuerpo = null; }
  if (r.status === 401) throw new Error('401: sesión no válida o expirada');
  if (r.status === 403) throw new Error('403: el rol ' + (state.rol || '?') + ' no tiene permiso');
  if (!r.ok) {
    throw new Error(r.status + ': ' +
      ((cuerpo && (cuerpo.detail || cuerpo.error)) || 'error del servidor'));
  }
  return cuerpo;
}

/* ── Sesión ─────────────────────────────────────────────────────────────────── */

async function entrar() {
  const usuario = $('usuario').value.trim();
  const clave = $('clave').value;
  if (!usuario || !clave) { toast('Usuario y contraseña son obligatorios'); return; }
  try {
    const r = await fetch(API + '/api/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: usuario, password: clave })
    });
    const d = await r.json().catch(() => null);
    if (!r.ok || !d || !d.token) {
      throw new Error((d && (d.detail || d.error)) || 'credenciales rechazadas');
    }
    state.token = d.token;
    state.usuario = usuario;
    state.rol = d.rol || null;
    $('clave').value = '';
    $('caja-sesion').classList.add('hidden');
    $('sesion-info').classList.remove('hidden');
    $('sesion-usuario').textContent = usuario;
    $('sesion-rol').textContent = state.rol || 'sin rol';
    $('sesion-rol').className = 'chip ' + (state.rol === 'admin' ? 'ok' : 'info');
    await cargarSesion();
    await cargarCartera();
    toast('Sesión iniciada como ' + usuario);
  } catch (e) {
    toast('No se pudo iniciar sesión — ' + e.message);
  }
}

function salir() {
  state.token = null; state.usuario = null; state.rol = null;
  state.casos = []; state.caso = null; state.documentos = [];
  $('caja-sesion').classList.remove('hidden');
  $('sesion-info').classList.add('hidden');
  $('meta-plataforma').innerHTML = '<span>sin sesión</span>';
  $('cartera-body').innerHTML =
    '<tr><td colspan="8" class="muted t-sm" style="padding:var(--sp-md)">Sesión cerrada.</td></tr>';
  $('cartera-caption').textContent = 'Inicie sesión para leer la cartera.';
  pintarMetricasCartera();
  toast('Sesión cerrada');
}

async function cargarSesion() {
  try {
    const me = await api('/api/me');
    const cfg = await api('/api/config').catch(() => null);
    const partes = ['<span>' + esc(me.username || me.usuario || state.usuario) + '</span>'];
    if (cfg) {
      const v = cfg.versionado || cfg.versions || cfg;
      const linea = v.version_line || [v.ARHIAX_RE_VERSION,
        v.GIT_COMMIT_SHA ? 'commit ' + String(v.GIT_COMMIT_SHA).slice(0, 8) : null]
        .filter(Boolean).join(' · ');
      if (linea) partes.push('<span>·</span><span>' + esc(linea) + '</span>');
    }
    $('meta-plataforma').innerHTML = partes.join(' ');
  } catch (e) {
    $('meta-plataforma').innerHTML =
      '<span class="chip warn">sin /api/me — ' + esc(e.message) + '</span>';
  }
}

/* ── Verificación de un inmueble (lectura real) ─────────────────────────────── */

async function buscar() {
  const direccion = $('direccion').value.trim();
  const nupre = $('nupre').value.trim();
  const ciudad = $('ciudad').value;
  const caja = $('buscar-estado');
  if (!direccion && !nupre) { toast('Escriba una dirección o un NUPRE'); return; }

  caja.className = 'state info';
  caja.innerHTML = '<div class="t-sm">Consultando las capas oficiales…</div>' +
    '<div class="why">GET /api/resolver-matricula</div>';
  $('ribbon-ciudad').textContent = ciudad;

  try {
    const d = await api('/api/resolver-matricula?direccion=' +
      encodeURIComponent(direccion || nupre) + '&ciudad=' + encodeURIComponent(ciudad));
    state.resolucion = d;
    const campos = d.campos || {};
    const identidad = campos.numero_predial || campos.folio_matricula || campos.nupre;
    const resuelto = identidad && !esVacio(identidad.value);

    caja.className = 'state ' + (resuelto ? 'ok' : 'warn');
    caja.innerHTML =
      '<div class="t-sm">' + (resuelto
        ? 'Consulta ejecutada · la capa oficial devolvió un predio'
        : 'Consulta ejecutada · sin predio único para esta placa') + '</div>' +
      '<div class="why">' + esc((d.consulta && d.consulta.normalizada) || direccion || nupre) +
      ' · fuentes consultadas: ' + esc(String((d.fuentes || []).length)) + '</div>';

    pintarResolucion(d);
    await emparejarCaso(campos, direccion);
    await cargarSelloDictus((campos.folio_matricula || {}).value || null);
  } catch (e) {
    caja.className = 'state err';
    caja.innerHTML = '<div class="t-sm">Error de consulta</div>' +
      '<div class="why">' + esc(e.message) + '</div>';
  }
}

function pintarResolucion(d) {
  const campos = d.campos || {};
  const fuentes = d.fuentes || [];
  state.fuentes = fuentes;

  /* Banner del inmueble activo */
  const predial = (campos.numero_predial || {}).value;
  $('banner').classList.remove('hidden');
  $('banner-direccion').textContent =
    (d.consulta && d.consulta.normalizada) || $('direccion').value.trim() || 'Consulta por identificador';
  $('banner-sub').textContent = (d.consulta && d.consulta.ciudad ? d.consulta.ciudad + ' · ' : '') +
    'consulta ' + ((d.consulta && d.consulta.hora) || 'sin fecha declarada');
  const chips = [];
  if (!esVacio(predial)) chips.push('<span class="tag"><span class="k">predial</span>' + esc(predial) + '</span>');
  if (campos.nupre && !esVacio(campos.nupre.value)) chips.push('<span class="tag"><span class="k">nupre</span>' + esc(campos.nupre.value) + '</span>');
  if (campos.folio_matricula && !esVacio(campos.folio_matricula.value)) chips.push('<span class="tag"><span class="k">folio</span>' + esc(campos.folio_matricula.value) + '</span>');
  chips.push(chip(fuentes.length ? 'OK' : 'SOURCE_UNAVAILABLE',
    fuentes.length ? fuentes.length + ' FUENTES' : 'SIN FUENTES'));
  $('banner-chips').innerHTML = chips.join('');

  /* Tarjeta 1 · Identidad (datos reales y su estado) */
  const identVal = !esVacio(predial) ? predial
    : ((campos.folio_matricula && campos.folio_matricula.value) || null);
  const kV = $('k-identidad-v');
  kV.textContent = identVal ? identVal : 'PENDIENTE';
  kV.className = 'kpi-v' + (identVal ? '' : ' is-text');
  $('k-identidad-s').innerHTML = 'Matrícula, número predial y NUPRE resueltos contra las fuentes oficiales.';
  const fuentesOk = fuentes.filter((f) => f.status === 'OK').length;
  $('k-identidad-f').textContent = fuentes.length
    ? fuentesOk + ' de ' + fuentes.length + ' fuentes con coincidencia'
    : 'sin fuentes consultadas';

  /* Tarjeta 2 · Estimación económica: contrato C-02 (no se inventa un monto) */
  const vV = $('k-valor-v');
  vV.textContent = 'CONTRATO C-02';
  vV.className = 'kpi-v is-text';
  $('k-valor-f').textContent = state.caso && state.caso.pdf_path
    ? 'dictamen emitido: el valor viaja en el documento' : 'sin dictamen emitido';

  /* Tarjeta 3 · Legal y títulos */
  const legalV = $('k-legal-v');
  const conCtl = state.caso && Number(state.caso.certificado_cargado) === 1;
  legalV.textContent = conCtl ? 'CERTIFICADO CARGADO' : 'SIN CERTIFICADO';
  legalV.className = 'kpi-v is-text';
  $('k-legal-f').textContent = state.caso
    ? 'caso ' + (state.caso.folio_matricula || state.caso.id)
    : 'sin caso abierto';

  /* Tarjeta 4 · Territorio y riesgos (campos reales del resolver) */
  const barrio = campos.barrio || {};
  const estrato = campos.estrato || {};
  const terrVal = !esVacio(barrio.value) ? barrio.value
    : (!esVacio(estrato.value) ? 'ESTRATO ' + estrato.value : null);
  const tV = $('k-territorio-v');
  tV.textContent = terrVal || 'PENDIENTE';
  tV.className = 'kpi-v' + (terrVal ? ' is-text' : '');
  $('k-territorio-f').textContent = (!esVacio(estrato.value) && estrato.status === 'VERIFIED_OFFICIAL')
    ? 'estrato ' + estrato.value + ' · fuente oficial' : 'estrato no verificado en esta consulta';

  /* Tarjeta 5 · Contrapartes: se declara el contrato faltante */
  const cV = $('k-contrapartes-v');
  cV.textContent = 'CONTRATO C-03';
  cV.className = 'kpi-v is-text';
  $('k-contrapartes-f').textContent = 'consulta y evidencia en el dictamen emitido';

  /* Tabla de campos del predio: valor+estado+motivo en una celda (regla D4) */
  const orden = ['numero_predial', 'nupre', 'folio_matricula', 'barrio', 'localidad',
    'estrato', 'coordenada'];
  $('prop-body').innerHTML = orden.map((k) => {
    const c = campos[k] || {};
    return '<tr><td class="mono-sm">' + esc(k) + '</td>' +
      '<td>' + valorCampo(c) + '</td>' +
      '<td class="t-xs muted">' + esc(c.source || 'sin declaración de fuente') + '</td></tr>';
  }).join('');
  $('prop-chip').className = 'chip ' + (esVacio(predial) ? 'warn' : 'ok');
  $('prop-chip').textContent = esVacio(predial) ? 'SIN PREDIO ÚNICO' : 'PREDIO RESUELTO';

  /* Tabla territorial */
  $('terr-body').innerHTML = ['barrio', 'localidad', 'estrato'].map((k) => {
    const c = campos[k] || {};
    return '<tr><td class="mono-sm">' + esc(k) + '</td>' +
      '<td>' + valorCampo(c) + '</td>' +
      '<td class="t-xs muted">' + esc(c.source || '—') + '</td></tr>';
  }).join('');
  $('terr-caption').textContent = 'consulta ' + ((d.consulta && d.consulta.ciudad) || '—');

  /* Candidatos */
  const cands = d.candidatos || [];
  $('cand-caption').textContent = cands.length + ' candidato(s)';
  $('cand-body').innerHTML = cands.length
    ? cands.map((c) => '<div class="state info"><div class="t-sm mono">' +
        esc(c.numero_predial || c.codigo || c.id || JSON.stringify(c).slice(0, 80)) + '</div>' +
        '<div class="why">' + esc(c.detalle || c.motivo || 'candidato devuelto por la fuente') + '</div></div>').join('')
    : '<div class="state info"><div class="t-sm">Sin candidatos en esta consulta</div>' +
      '<div class="why">Cuando la capa oficial devuelve más de un predio posible, se listan aquí para revisión: la interfaz no elige por su cuenta.</div></div>';

  /* Ledger de procedencia (fail-closed: cada fuente con su resultado real) */
  $('ledger-caption').textContent = fuentes.length + ' fuente(s)';
  $('ledger-body').innerHTML = fuentes.length
    ? fuentes.map((f) => '<tr><td class="mono-sm">' + esc(f.id) + '</td>' +
        '<td>' + chip(f.status) + '</td>' +
        '<td class="t-xs muted">' + esc(f.detalle || '—') + '</td></tr>').join('')
    : '<tr><td colspan="3" class="muted t-sm" style="padding:var(--sp-md)">La consulta no declaró fuentes.</td></tr>';

  /* Coordenada */
  const coord = campos.coordenada || {};
  pintarGeometria(coord, campos);
  pintarTriada();
}

function pintarGeometria(coord, campos) {
  const tags = [];
  if (!esVacio(coord.value)) {
    tags.push('<span class="tag"><span class="k">coordenada</span>' + esc(coord.value) + '</span>');
  }
  tags.push('<span class="tag"><span class="k">estado</span>' +
    esc((CLASE_POR_ESTADO[coord.status] || [null, 'SIN ESTADO'])[1]) + '</span>');
  if (coord.source) tags.push('<span class="tag"><span class="k">fuente</span>' + esc(coord.source) + '</span>');
  const estrato = campos.estrato || {};
  if (estrato.source) tags.push('<span class="tag"><span class="k">estrato</span>' + esc(estrato.source) + '</span>');
  $('geom-tags').innerHTML = tags.join('');
  $('geom-chip').textContent = esVacio(coord.value) ? 'SIN COORDENADA' : 'COORDENADA DECLARADA';
  $('geom-chip').className = 'lbl';

  /* La parcela se dibuja centrada: es un MARCO de referencia, no un levantamiento. */
  const parcela = $('geom-parcela');
  if (parcela) {
    parcela.setAttribute('points', esVacio(coord.value)
      ? '' : '120,60 200,60 200,140 120,140');
  }
}

/* ── Sello maestro publicado (DICTUS 2.0B §12) ───────────────────────────────
 * El manifest se publica con la aplicación al emitir el expediente
 * (`public/dictus/DICTUS_MANIFEST_<folio>.json`). Si no existe, se declara: el portal
 * NUNCA inventa un hash ni muestra el hash del PDF como si fuera el maestro. */
const MANIFEST_BASE = (API || '') + '/dictus/DICTUS_MANIFEST_';
let _manifestActual = null;

function folioActivo() {
  const c = state.caso || {};
  const campos = (state.resolucion || {}).campos || {};
  return c.folio_matricula || (campos.folio_matricula || {}).value || null;
}

function chipMini(estado) {
  const ok = /SELLADO/.test(String(estado));
  return '<span class="chip ' + (ok ? 'ok' : 'warn') + '">' + esc(estado || 'sin estado') + '</span>';
}

async function cargarSelloDictus(folio) {
  const chip = $('sello-chip');
  const nota = $('sello-nota');
  if (!folio) {
    chip.className = 'chip info';
    chip.textContent = 'SIN FOLIO';
    nota.textContent = 'Verifique un inmueble o abra un caso para leer su sello.';
    return;
  }
  try {
    const r = await fetch(MANIFEST_BASE + encodeURIComponent(folio) + '.json',
                          { headers: { 'Accept': 'application/json' } });
    if (!r.ok) throw new Error('HTTP ' + r.status);
    const m = await r.json();
    _manifestActual = m;
    const ev = m.evidence_manifest || {};
    $('sello-id').textContent = m.dictus_id || '—';
    $('sello-fecha').textContent = m.generated_at || '—';
    $('sello-estado').innerHTML = chipMini(ev.estado) + ' · ' +
      (ev.evidence_count != null ? ev.evidence_count + ' evidencia(s)' : 'sin conteo');
    $('sello-hash').innerHTML = '<span class="mono">' + esc(m.master_hash || '—') + '</span>';
    chip.className = 'chip ' + (/SELLADO/.test(String(ev.estado)) ? 'ok' : 'warn');
    chip.textContent = 'MANIFEST PUBLICADO · ' + (m.master_manifest_version || '');
    nota.textContent = 'Hash maestro visible: ' + (m.master_hash_abreviado || '—') +
      ' · el hash del PDF no se usa como sello del expediente.';
  } catch (e) {
    _manifestActual = null;
    $('sello-id').textContent = '—';
    $('sello-fecha').textContent = '—';
    $('sello-estado').textContent = '—';
    $('sello-hash').textContent = '—';
    chip.className = 'chip warn';
    chip.textContent = 'SIN MANIFEST PUBLICADO';
    nota.textContent = 'Este expediente no tiene manifest publicado con hash maestro (' +
      e.message + ').';
  }
}

function verTrazabilidad() {
  const caja = $('sello-detalle');
  const cuerpo = $('sello-detalle-cuerpo');
  if (!caja || !cuerpo) return;
  if (!_manifestActual) {
    caja.classList.remove('hidden');
    cuerpo.textContent = 'Sin manifest publicado para este expediente: no hay trazabilidad ' +
      'maestra que mostrar.';
    return;
  }
  const m = _manifestActual;
  const lineas = [
    'DICTUS ID          : ' + (m.dictus_id || '—'),
    'Run ID             : ' + (m.run_id || '—'),
    'Generado (UTC)     : ' + (m.generated_at || '—'),
    'Master manifest    : ' + (m.master_manifest_version || '—'),
    'DICTUS_MASTER_HASH : ' + (m.master_hash || '—'),
    'Evidencias         : ' + ((m.evidence_manifest || {}).evidence_count || 0) +
      ' (' + ((m.evidence_manifest || {}).estado || '—') + ')',
    '',
    'Evidencias:'
  ];
  for (const e of ((m.evidence_manifest || {}).evidencias || [])) {
    lineas.push('  · ' + String(e.evidence_id || '').padEnd(16) + ' ' +
      (e.evidence_type || '') + ' | ' + (e.source || '—') + ' | ' + (e.status || '—'));
  }
  caja.classList.remove('hidden');
  cuerpo.textContent = lineas.join('\n');
}

/* ── Tríada estratégica (lo que habilita, con el estado real) ───────────────── */

function pintarTriada() {
  const caso = state.caso;
  const emitido = !!(caso && caso.pdf_path);
  const conCtl = !!(caso && Number(caso.certificado_cargado) === 1);
  const fuentes = state.fuentes || [];
  const fuentesOk = fuentes.filter((f) => f.status === 'OK').length;

  const linea = (etiqueta, valor, estado) => '<div class="linea"><span>' + esc(etiqueta) + '</span>' +
    (estado ? chip(estado) : '<b>' + esc(valor) + '</b>') + '</div>';

  $('tri-cv-body').innerHTML = [
    linea('Identidad del predio', (state.resolucion && !esVacio(((state.resolucion.campos || {}).numero_predial || {}).value) ? 'resuelta' : 'pendiente'),
      (state.resolucion && !esVacio(((state.resolucion.campos || {}).numero_predial || {}).value)) ? 'VERIFIED_CATASTRAL' : 'UNRESOLVED'),
    linea('Fuentes oficiales consultadas', fuentesOk + ' / ' + fuentes.length, fuentes.length ? 'OK' : 'SOURCE_UNAVAILABLE'),
    linea('Dictamen emitido', emitido ? 'disponible' : 'pendiente', emitido ? 'OK' : 'PARTIAL')
  ].join('');
  $('tri-cv-chip').textContent = emitido ? 'LISTO PARA REVISIÓN' : 'EN PREPARACIÓN';

  $('tri-ht-body').innerHTML = [
    linea('Estimación económica', 'contrato C-02', 'CONTRATO_FALTANTE'),
    linea('Certificado de tradición', conCtl ? 'cargado' : 'pendiente', conCtl ? 'OK' : 'UNRESOLVED'),
    linea('Documento para el banco', emitido ? 'disponible' : 'pendiente', emitido ? 'OK' : 'PARTIAL')
  ].join('');
  $('tri-ht-chip').textContent = emitido ? 'EXPEDIENTE DISPONIBLE' : 'SIN EXPEDIENTE';

  $('tri-st-body').innerHTML = [
    linea('Trazabilidad de fuentes', fuentes.length ? fuentes.length + ' consultas' : 'sin consultas',
      fuentes.length ? 'OK' : 'SOURCE_UNAVAILABLE'),
    linea('Evidencia sellada', emitido ? 'en el dictamen' : 'pendiente', emitido ? 'OK' : 'PARTIAL'),
    linea('Sello de ejecución', estadoSelloReducido(), emitido ? 'OK' : 'UNRESOLVED')
  ].join('');
  $('tri-st-chip').textContent = emitido ? 'REUTILIZABLE' : 'SIN EXPEDIENTE';
}

function estadoSelloReducido() {
  const d = (state.resolucion && state.resolucion.consulta) || {};
  return d.hora ? 'consulta ' + String(d.hora).slice(0, 10) : 'sin sello de consulta';
}

/* ── Cartera y caso abierto ─────────────────────────────────────────────────── */

async function cargarCartera() {
  const body = $('cartera-body');
  if (!state.token) { $('cartera-caption').textContent = 'Inicie sesión para leer la cartera.'; return; }
  $('cartera-estado').textContent = 'cargando…';
  try {
    const casos = await api('/api/dictamenes');
    state.casos = Array.isArray(casos) ? casos : ((casos && casos.items) || []);
    $('cartera-estado').textContent = state.casos.length + ' caso(s)';
    pintarMetricasCartera();
    pintarCartera();
  } catch (e) {
    $('cartera-estado').textContent = 'error';
    body.innerHTML = '<tr><td colspan="8" class="muted t-sm" style="padding:var(--sp-md)">' +
      '<span class="chip err">ERROR</span> ' + esc(e.message) +
      ' — <button class="btn sm" id="btn-reintentar" type="button">Reintentar</button></td></tr>';
    const b = $('btn-reintentar');
    if (b) b.addEventListener('click', cargarCartera);
  }
}

function pintarMetricasCartera() {
  const c = state.casos || [];
  $('m-total').textContent = c.length;
  $('m-ctl').textContent = c.filter((x) => Number(x.certificado_cargado) === 1).length;
  $('m-pdf').textContent = c.filter((x) => x.pdf_path).length;
  const ciudades = Array.from(new Set(c.map((x) => x.ciudad).filter(Boolean)));
  $('m-ciudades').textContent = ciudades.length;
  const sel = $('f-ciudad');
  const actual = sel.value;
  sel.innerHTML = '<option value="">Toda ciudad</option>' +
    ciudades.map((x) => '<option value="' + esc(x) + '">' + esc(x) + '</option>').join('');
  sel.value = actual;
}

function pintarCartera() {
  const q = $('q').value.trim().toLowerCase();
  const ciudad = $('f-ciudad').value;
  const filas = (state.casos || []).filter((x) => {
    const texto = [x.folio_matricula, x.direccion, x.barrio].join(' ').toLowerCase();
    return (!q || texto.indexOf(q) >= 0) && (!ciudad || x.ciudad === ciudad);
  });
  $('cartera-caption').textContent = filas.length + ' de ' + (state.casos || []).length + ' casos.';
  if (!filas.length) {
    $('cartera-body').innerHTML = '<tr><td colspan="8" class="muted t-sm" style="padding:var(--sp-md)">' +
      ((state.casos || []).length ? 'Ningún caso coincide con el filtro.'
        : 'Sin casos en la cartera para este usuario.') + '</td></tr>';
    return;
  }
  $('cartera-body').innerHTML = filas.map((x) => {
    const aptitud = x.pdf_path ? ['ok', 'EMITIDO']
      : (Number(x.certificado_cargado) === 1 ? ['warn', 'EN PROCESO'] : ['info', 'SIN CERTIFICADO']);
    const doc = x.pdf_path
      ? '<a class="btn sm" href="' + API + '/api/dictamenes/' + encodeURIComponent(x.id) + '/pdf" target="_blank" rel="noopener">Ver dictamen</a>'
      : '<span class="chip info">NO EMITIDO</span>';
    return '<tr>' +
      '<td class="mono">' + esc(x.folio_matricula || '—') + '</td>' +
      '<td>' + esc(x.direccion || '—') + '</td>' +
      '<td class="mono-sm">' + esc(x.ciudad || '—') + '</td>' +
      '<td class="num">' + (esVacio(x.area) ? '<span class="chip warn">PENDIENTE</span>' : esc(x.area)) + '</td>' +
      '<td class="num">' + (esVacio(x.estrato) ? '<span class="chip warn">PENDIENTE</span>' : esc(x.estrato)) + '</td>' +
      '<td>' + chip(aptitud[0] === 'ok' ? 'OK' : (aptitud[0] === 'warn' ? 'PARTIAL' : 'UNRESOLVED'), aptitud[1]) + '</td>' +
      '<td>' + doc + '</td>' +
      '<td class="row"><button class="btn sm" type="button" data-abrir="' + esc(x.id) + '">Abrir</button></td>' +
      '</tr>';
  }).join('');
  Array.prototype.forEach.call(document.querySelectorAll('[data-abrir]'), (b) => {
    b.addEventListener('click', () => abrirCaso(Number(b.dataset.abrir)));
  });
}

/** Empareja la consulta con un caso de la cartera (por folio o por predial). */
async function emparejarCaso(campos, direccion) {
  if (!state.token) return;
  if (!state.casos.length) await cargarCartera().catch(() => null);
  const folio = ((campos.folio_matricula || {}).value || '').trim();
  const predial = ((campos.numero_predial || {}).value || '').trim();
  const dir = (direccion || '').trim().toLowerCase();
  const hallado = (state.casos || []).find((x) =>
    (folio && x.folio_matricula === folio) ||
    (predial && String(x.numero_predial || '') === predial) ||
    (dir && String(x.direccion || '').toLowerCase() === dir));
  if (hallado) {
    await abrirCaso(hallado.id, true);
  } else {
    state.caso = null;
    state.documentos = [];
    $('exp-chip').className = 'chip warn';
    $('exp-chip').textContent = 'SIN EXPEDIENTE EMITIDO';
    $('exp-sello').textContent = estadoSelloReducido();
    $('exp-doc').innerHTML = '<span class="chip info">NO EMITIDO PARA ESTE PREDIO</span>' +
      ' <span class="t-xs muted">el expediente se emite al generar el dictamen del caso</span>';
    $('legal-docs-body').innerHTML = '<tr><td colspan="3" class="muted t-sm" style="padding:var(--sp-md)">Sin caso abierto para este predio.</td></tr>';
    $('legal-docs-count').textContent = '—';
    $('docs-body').innerHTML = '<tr><td colspan="4" class="muted t-sm" style="padding:var(--sp-md)">Sin caso abierto para este predio.</td></tr>';
    $('docs-caption').textContent = 'sin caso';
    pintarTriada();
    actualizarExpediente();
  }
}

async function abrirCaso(id, silencioso) {
  const caso = (state.casos || []).find((x) => Number(x.id) === Number(id));
  if (!caso) { toast('Caso no encontrado en la cartera'); return; }
  state.caso = caso;
  $('banner').classList.remove('hidden');
  $('banner-direccion').textContent = caso.direccion || caso.folio_matricula || ('Caso ' + caso.id);
  $('banner-sub').textContent = [caso.ciudad, caso.barrio].filter(Boolean).join(' · ') ||
    'sin barrio declarado en la cartera';
  $('banner-chips').innerHTML = [
    caso.folio_matricula ? '<span class="tag"><span class="k">folio</span>' + esc(caso.folio_matricula) + '</span>' : '',
    caso.estrato ? '<span class="tag"><span class="k">estrato</span>' + esc(caso.estrato) + '</span>' : '',
    chip(caso.pdf_path ? 'OK' : 'PARTIAL', caso.pdf_path ? 'DICTAMEN EMITIDO' : 'EN PROCESO')
  ].join('');

  $('k-legal-v').textContent = Number(caso.certificado_cargado) === 1 ? 'CERTIFICADO CARGADO' : 'SIN CERTIFICADO';
  $('k-legal-v').className = 'kpi-v is-text';
  $('k-legal-f').textContent = 'caso ' + (caso.folio_matricula || caso.id);
  $('v-area').textContent = esVacio(caso.area) ? '—' : caso.area + ' m²';

  try {
    const docs = await api('/api/dictamenes/' + encodeURIComponent(caso.id) + '/documentos');
    state.documentos = Array.isArray(docs) ? docs : [];
  } catch (e) {
    state.documentos = [];
    $('docs-body').innerHTML = '<tr><td colspan="4" class="muted t-sm" style="padding:var(--sp-md)">' +
      '<span class="chip warn">NO DISPONIBLE</span> ' + esc(e.message) + '</td></tr>';
  }
  pintarDocumentos();
  pintarLegalDocumentos();
  await cargarSelloDictus(caso.folio_matricula || null);
  actualizarExpediente();
  pintarTriada();
  if (!silencioso) { setPestana('propiedad'); toast('Caso abierto: ' + (caso.folio_matricula || caso.id)); }
}

function pintarDocumentos() {
  const c = state.caso;
  if (!c) return;
  $('docs-caption').textContent = (state.documentos || []).length + ' documento(s) · caso ' + (c.folio_matricula || c.id);
  const filas = (state.documentos || []).map((d) =>
    '<tr><td>' + esc(d.nombre || '—') + '</td><td class="mono-sm">' + esc(d.tipo || '—') + '</td>' +
    '<td class="mono-sm">' + esc(d.creado || '—') + '</td>' +
    '<td><a class="btn sm" href="' + API + '/api/dictamenes/' + encodeURIComponent(c.id) +
    '/documentos/' + encodeURIComponent(d.id) + '" target="_blank" rel="noopener">Abrir</a></td></tr>');
  if (c.pdf_path) {
    filas.push('<tr><td>Dictamen emitido (PDF)</td><td class="mono-sm">dictamen</td>' +
      '<td class="mono-sm">' + esc(c.pdf_path) + '</td>' +
      '<td><a class="btn sm" href="' + API + '/api/dictamenes/' + encodeURIComponent(c.id) +
      '/pdf" target="_blank" rel="noopener">Ver</a></td></tr>');
  }
  $('docs-body').innerHTML = filas.length ? filas.join('')
    : '<tr><td colspan="4" class="muted t-sm" style="padding:var(--sp-md)">El caso no tiene documentos adjuntos ni dictamen emitido.</td></tr>';
}

function pintarLegalDocumentos() {
  const filas = (state.documentos || []).map((d) =>
    '<tr><td>' + esc(d.nombre || '—') + '</td><td class="mono-sm">' + esc(d.tipo || '—') + '</td>' +
    '<td>' + chip('OK', String(d.creado || '').slice(0, 10)) + '</td></tr>');
  $('legal-docs-count').textContent = (state.documentos || []).length + ' adjunto(s)';
  $('legal-docs-body').innerHTML = filas.length ? filas.join('')
    : '<tr><td colspan="3" class="muted t-sm" style="padding:var(--sp-md)">Sin adjuntos en este caso.</td></tr>';
}

function actualizarExpediente() {
  const c = state.caso;
  const emitido = !!(c && c.pdf_path);
  $('exp-chip').className = 'chip ' + (emitido ? 'ok' : 'warn');
  $('exp-chip').textContent = emitido ? 'EMITIDO' : 'SIN EXPEDIENTE EMITIDO';
  $('exp-sello').textContent = estadoSelloReducido();
  $('exp-casos').textContent = (state.casos || []).length + ' en cartera';
  $('exp-docs').textContent = (state.documentos || []).length + ' adjunto(s)' + (emitido ? ' + dictamen' : '');
  $('exp-hora').textContent = ((state.resolucion || {}).consulta || {}).hora || 'sin consulta en esta sesión';
  $('exp-doc').innerHTML = emitido
    ? '<a class="btn sm" href="' + API + '/api/dictamenes/' + encodeURIComponent(c.id) + '/pdf" target="_blank" rel="noopener">Abrir dictamen emitido</a>'
    : '<span class="chip warn">NO EMITIDO</span> <span class="t-xs muted">se emite al generar el dictamen del caso</span>';
}

/* ── Perspectivas y navegación ─────────────────────────────────────────────── */

const NOTA_PERSPECTIVA = {
  inmobiliaria: 'Vista inmobiliaria: el expediente completo para el equipo comercial.',
  titulux: 'Titulux: el foco está en la revisión jurídica, los títulos y las contrapartes.',
  lonja: 'Portal Lonja: el foco está en la estimación económica y el contexto territorial.',
  tecnico: 'Técnico: contratos, estados por fuente y payloads tal como responden.'
};

function setPerspectiva(p) {
  state.perspectiva = p;
  document.body.dataset.persp = p;
  document.documentElement.dataset.persp = p;
  Array.prototype.forEach.call(document.querySelectorAll('.persp-btn'), (b) => {
    b.setAttribute('aria-selected', String(b.dataset.persp === p));
  });
  $('persp-nota').textContent = NOTA_PERSPECTIVA[p] || '';
  if (p === 'tecnico') { setPestana('diagnostico'); consultarFuentes(); }
  if (p === 'titulux') setPestana('legal');
  if (p === 'lonja') setPestana('valor');
  if (p === 'inmobiliaria') setPestana('resumen');
}

function setPestana(id) {
  state.pestana = id;
  Array.prototype.forEach.call(document.querySelectorAll('.tabpanel'), (s) => {
    s.classList.toggle('hidden', s.id !== 'p-' + id);
  });
  // Los botones del riel son navegación (`aria-current`); las pestañas son
  // `role=tab` (`aria-selected`). Un mismo estado, dos semánticas.
  Array.prototype.forEach.call(document.querySelectorAll('[data-go]'), (b) => {
    const activo = b.dataset.go === id;
    if (b.classList.contains('rail-item')) {
      b.setAttribute('aria-current', String(activo));
    } else {
      b.setAttribute('aria-selected', String(activo));
    }
  });
  if (id === 'diagnostico') consultarFuentes();
  if (id === 'territorio') cargarCapas();
}

/* ── Diagnóstico (contratos de lectura) ────────────────────────────────────── */

async function consultarFuentes() {
  const body = $('fuentes-body');
  body.innerHTML = '<tr><td colspan="3" class="muted t-sm" style="padding:var(--sp-md)">Consultando…</td></tr>';
  const filas = [];
  let config = null;

  async function probar(contrato, fn, soloAdmin) {
    if (!state.token) { filas.push([contrato, ['info', 'SIN SESIÓN'], 'inicie sesión para consultar']); return null; }
    try {
      const d = await fn();
      filas.push([contrato, ['ok', 'RESPONDE'], JSON.stringify(d).slice(0, 220)]);
      return d;
    } catch (e) {
      const sinPermiso = /403/.test(e.message);
      filas.push([contrato, [sinPermiso ? 'warn' : 'err', sinPermiso ? 'SIN PERMISO' : 'NO DISPONIBLE'],
        e.message + (soloAdmin ? ' (requiere rol admin)' : '')]);
      return null;
    }
  }

  config = await probar('GET /api/config', () => api('/api/config'));
  await probar('GET /api/me', () => api('/api/me'));
  const st = await probar('GET /api/v1/status (admin)', () => api('/api/v1/status'), true);
  await probar('GET /api/v1/geo/ciudades', () => api('/api/v1/geo/ciudades'));
  await probar('GET /api/v1/pdf/estado', () => api('/api/v1/pdf/estado'));

  body.innerHTML = filas.map(([c, [clase, etq], det]) =>
    '<tr><td class="mono-sm">' + esc(c) + '</td><td><span class="chip ' + clase + '">' + esc(etq) +
    '</span></td><td class="t-xs muted">' + esc(det) + '</td></tr>').join('');
  $('chip-fuentes').textContent = filas.filter((f) => f[1][0] === 'ok').length + ' / ' + filas.length + ' responden';

  $('kv-config').innerHTML = config
    ? Object.keys(config).slice(0, 12).map((k) => '<dt>' + esc(k) + '</dt><dd>' + esc(
        typeof config[k] === 'object' ? JSON.stringify(config[k]) : config[k]) + '</dd>').join('')
    : '<dt>estado</dt><dd>sin datos (ver tabla de contratos)</dd>';
  $('pre-status').textContent = st ? JSON.stringify(st, null, 1) : 'no disponible (requiere rol admin)';
}

let capasCargadas = false;
async function cargarCapas() {
  if (capasCargadas || !state.token) return;
  try {
    const d = await api('/api/v1/geo/ciudades');
    const ciudades = (d && d.ciudades) || [];
    $('capas-body').innerHTML = ciudades.length ? ciudades.map((c) => {
      const nombre = c.ciudad || c.nombre || c.id || '—';
      const estado = c.estado || c.status || '—';
      const capas = c.capas ? Object.keys(c.capas).join(' · ') : (c.layers ? c.layers.join(' · ') : '—');
      return '<tr><td class="mono-sm">' + esc(nombre) + '</td><td>' +
        chip(/disponible|activa|ok/i.test(String(estado)) ? 'OK' : 'PARTIAL', String(estado).toUpperCase()) +
        '</td><td class="t-xs muted">' + esc(capas) + '</td></tr>';
    }).join('') : '<tr><td colspan="3" class="muted t-sm" style="padding:var(--sp-md)">La respuesta no declaró ciudades.</td></tr>';
    $('capas-chip').textContent = ciudades.length + ' ciudad(es)';
    $('capas-chip').className = 'chip ' + (ciudades.length ? 'ok' : 'warn');
    capasCargadas = true;
  } catch (e) {
    $('capas-body').innerHTML = '<tr><td colspan="3" class="muted t-sm" style="padding:var(--sp-md)">' +
      '<span class="chip warn">NO DISPONIBLE</span> ' + esc(e.message) + '</td></tr>';
  }
}

/* ── Arranque ──────────────────────────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
  document.body.dataset.persp = state.perspectiva;
  setPerspectiva('inmobiliaria');

  Array.prototype.forEach.call(document.querySelectorAll('.persp-btn'), (b) => {
    b.addEventListener('click', () => setPerspectiva(b.dataset.persp));
  });
  Array.prototype.forEach.call(document.querySelectorAll('[data-go]'), (b) => {
    b.addEventListener('click', () => setPestana(b.dataset.go));
  });

  $('btn-entrar').addEventListener('click', entrar);
  $('btn-salir').addEventListener('click', salir);
  $('btn-buscar').addEventListener('click', buscar);
  $('btn-refrescar').addEventListener('click', cargarCartera);
  $('btn-trazabilidad').addEventListener('click', verTrazabilidad);
  $('btn-fuentes').addEventListener('click', consultarFuentes);
  $('q').addEventListener('input', pintarCartera);
  $('f-ciudad').addEventListener('change', pintarCartera);

  ['direccion', 'nupre'].forEach((id) => {
    $(id).addEventListener('keydown', (e) => { if (e.key === 'Enter') buscar(); });
  });
  $('ciudad').addEventListener('change', (e) => {
    $('ribbon-ciudad').textContent = e.target.value;
  });
  $('clave').addEventListener('keydown', (e) => { if (e.key === 'Enter') entrar(); });
});
