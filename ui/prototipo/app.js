/* ARHIAX RE — Prototipo de la capa de interfaz (solo LECTURA sobre la API real).
 *
 * Reglas del prototipo (docs/ui/00_DECISIONES.md):
 *   D2  todo dato sale de un endpoint existente; lo que no existe se declara.
 *   D4  nunca un valor por defecto: si no hay dato, se dice el estado y el motivo.
 *   D7  sin escrituras: crear caso, subir documentos y emitir están deshabilitados.
 *
 * El token de sesión vive SOLO en memoria (no se persiste en localStorage).
 */
'use strict';

/* Base de la API. Por defecto, MISMO ORIGEN (como en producción, donde FastAPI
 * sirve `public/` y `/api/*`). Para probar el prototipo por separado:
 *   python -m http.server 8000 --directory ui/prototipo
 *   http://localhost:8000/?api=https://arhiax-re.vercel.app
 * `http://localhost:8000` está en la lista blanca de CORS del backend. */
const API = new URLSearchParams(location.search).get('api') || '';
const state = { token: null, usuario: null, rol: null, casos: [], resolucion: null };

/* ── Utilidades ──────────────────────────────────────────────────────────── */

const $ = (id) => document.getElementById(id);

function toast(texto) {
  const t = $('toast');
  $('toast-text').textContent = texto;
  t.classList.add('on');
  clearTimeout(t._t);
  t._t = setTimeout(() => t.classList.remove('on'), 3200);
}

function esc(v) {
  return String(v === null || v === undefined ? '' : v)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function esVacio(v) {
  return v === null || v === undefined || v === '' ||
    String(v).trim().toLowerCase() === 'pendiente';
}

/** Valor + estado de verdad. NUNCA inventa un valor para un hueco (D4). */
function valorConEstado(valor, { origen = null, motivo = 'sin dato en esta sesión',
                                 estado = 'UNRESOLVED' } = {}) {
  if (esVacio(valor)) {
    const clase = estado === 'SOURCE_UNAVAILABLE' ? 'info' : 'warn';
    const etiqueta = estado === 'SOURCE_UNAVAILABLE' ? 'FUENTE NO DISPONIBLE' : 'PENDIENTE';
    return `<span class="chip ${clase}" title="${esc(motivo)}">${etiqueta}</span>`;
  }
  const chip = origen ? ` <span class="chip ok">${esc(origen)}</span>` : '';
  return `<span>${esc(valor)}</span>${chip}`;
}

async function api(ruta, opciones = {}) {
  const headers = Object.assign({ 'Accept': 'application/json' }, opciones.headers || {});
  if (state.token) headers['Authorization'] = 'Bearer ' + state.token;
  const r = await fetch(API + ruta, Object.assign({}, opciones, { headers }));
  let cuerpo = null;
  try { cuerpo = await r.json(); } catch (e) { cuerpo = null; }
  if (r.status === 401) throw new Error('401: sesión no válida o expirada');
  if (r.status === 403) throw new Error('403: el rol ' + (state.rol || '?') + ' no tiene permiso');
  if (!r.ok) throw new Error(r.status + ': ' + ((cuerpo && (cuerpo.detail || cuerpo.error)) || 'error del servidor'));
  return cuerpo;
}

/* ── Sesión ──────────────────────────────────────────────────────────────── */

async function entrar() {
  const usuario = $('usuario').value.trim();
  const clave = $('clave').value;
  if (!usuario || !clave) { toast('Usuario y contraseña son obligatorios'); return; }
  try {
    const r = await fetch('/api/login', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: usuario, password: clave })
    });
    const d = await r.json().catch(() => null);
    if (!r.ok || !d || !d.token) throw new Error((d && (d.detail || d.error)) || 'credenciales rechazadas');
    state.token = d.token;
    state.usuario = usuario;
    state.rol = d.rol || null;
    $('clave').value = '';
    $('caja-sesion').classList.add('hidden');
    $('btn-salir').classList.remove('hidden');
    await cargarSesion();
    toast('Sesión iniciada como ' + usuario);
  } catch (e) {
    toast('No se pudo iniciar sesión — ' + e.message);
  }
}

function salir() {
  state.token = null; state.usuario = null; state.rol = null; state.casos = [];
  $('caja-sesion').classList.remove('hidden');
  $('btn-salir').classList.add('hidden');
  $('meta-plataforma').innerHTML = '<span>sin sesión</span><span class="sep">·</span><span>—</span>';
  $('cartera-body').innerHTML = '<tr><td colspan="8" class="muted t-sm" style="padding:var(--sp-md)">Sesión cerrada.</td></tr>';
  toast('Sesión cerrada');
}

async function cargarSesion() {
  try {
    const me = await api('/api/me');
    const cfg = await api('/api/config').catch(() => null);
    const partes = [
      `<span>${esc(me.username || me.usuario || state.usuario)}</span>`,
      `<span class="chip ${state.rol === 'admin' ? 'ok' : 'info'}">${esc(state.rol || 'sin rol')}</span>`
    ];
    if (cfg) {
      const v = cfg.versionado || cfg.versions || cfg;
      const linea = v.version_line || [v.ARHIAX_RE_VERSION, v.GIT_COMMIT_SHA ? 'commit ' + String(v.GIT_COMMIT_SHA).slice(0, 8) : null]
        .filter(Boolean).join(' · ');
      if (linea) partes.push(`<span class="sep">·</span><span>${esc(linea)}</span>`);
    }
    $('meta-plataforma').innerHTML = partes.join('');
  } catch (e) {
    $('meta-plataforma').innerHTML = `<span class="chip warn">sin /api/me — ${esc(e.message)}</span>`;
  }
}

/* ── V1 · Resolución de dirección (solo lectura) ─────────────────────────── */

async function resolver() {
  const direccion = $('direccion').value.trim();
  if (!direccion) { toast('Escriba una dirección'); return; }
  const caja = $('resolver-estado');
  caja.className = 'state info';
  caja.innerHTML = '<div class="t-sm">Consultando…</div><div class="why">GET /api/resolver-matricula</div>';
  try {
    const d = await api('/api/resolver-matricula?direccion=' + encodeURIComponent(direccion));
    state.resolucion = d;

    const folio = d.folio_matricula, barrio = d.barrio, estrato = d.estrato;
    const folioOk = !esVacio(folio);

    caja.className = 'state ' + (folioOk ? 'ok' : 'warn');
    caja.innerHTML =
      `<div class="t-sm">${folioOk ? 'Resuelto' : 'No resuelto'} · respuesta cruda del endpoint</div>` +
      `<div class="why">folio=${esc(folio)} · barrio=${esc(barrio || '—')} · estrato=${esc(estrato)}</div>`;

    // Tabla de trazabilidad: se muestra lo que el endpoint devolvió, con su
    // estado deducido de forma conservadora (nunca "verificado" sin fuente).
    const filas = [
      ['folio_matricula', folio, folioOk ? ['info', 'DEVUELTO POR EL ENDPOINT', 'el endpoint no declara fuente ni método'] : ['warn', 'PENDIENTE', 'el endpoint respondió "Pendiente"']],
      ['barrio', barrio, esVacio(barrio) ? ['warn', 'PENDIENTE', 'sin barrio en la respuesta'] : ['info', 'DEVUELTO', 'sin declaración de fuente']],
      ['estrato', estrato, ['err', 'NO CONFIABLE', 'C-01: el endpoint devuelve 4 por defecto; no se muestra como dato del predio']]
    ];
    $('trace-body').innerHTML = filas.map(([campo, valor, [clase, etiqueta, motivo]]) =>
      `<tr><td class="mono-sm">${esc(campo)}</td><td class="mono">${esc(valor === null || valor === undefined ? '—' : valor)}</td>` +
      `<td><span class="chip ${clase}" title="${esc(motivo)}">${esc(etiqueta)}</span></td></tr>`).join('');

    // Ficha: solo lo que el endpoint realmente aporta; lo demás queda explicado.
    $('f-folio').innerHTML = valorConEstado(folio, { origen: folioOk ? 'endpoint' : null });
    $('f-barrio').innerHTML = valorConEstado(barrio);
    $('f-estrato').innerHTML = '<span class="chip err" title="C-01: valor por defecto del endpoint">NO CONFIABLE</span>';
    $('f-predial').innerHTML = valorConEstado(null, { estado: 'SOURCE_UNAVAILABLE', motivo: 'requiere C-02 (ficha de verificación)' });
    $('f-nupre').innerHTML = valorConEstado(null, { estado: 'SOURCE_UNAVAILABLE', motivo: 'requiere C-02 (ficha de verificación)' });
    $('f-area').innerHTML = valorConEstado(null, { estado: 'SOURCE_UNAVAILABLE', motivo: 'se extrae del CTL al generar; requiere C-02' });
    $('f-coord').innerHTML = valorConEstado(null, { estado: 'SOURCE_UNAVAILABLE', motivo: 'se resuelve al generar; requiere C-02' });
    $('chip-ficha').className = 'chip ' + (folioOk ? 'warn' : 'info');
    $('chip-ficha').textContent = folioOk ? 'PARCIAL · CONTRATO C-02 PENDIENTE' : 'SIN RESOLVER';

    $('trace-sello').textContent = 'sello: — (el sello se emite al generar el dictamen)';
    $('paso-2').className = 'step' + (folioOk ? ' done' : '');
    actualizarEmision(folioOk, d);
  } catch (e) {
    caja.className = 'state err';
    caja.innerHTML = `<div class="t-sm">Error de consulta</div><div class="why">${esc(e.message)}</div>`;
    actualizarEmision(false, null);
  }
}

function actualizarEmision(hayIdentidad, d) {
  const btn = $('btn-emitir');
  const nota = $('emitir-motivo');
  // D7: la acción de escritura queda deshabilitada en el prototipo, pero el motivo
  // que se explica es el REAL del producto (identidad / gate), no el del prototipo.
  btn.disabled = true;
  if (!state.token) {
    nota.textContent = 'Inicie sesión para emitir.';
  } else if (!hayIdentidad) {
    nota.textContent = 'Identidad no resuelta: el motor no emite sin identidad autorizada.';
  } else {
    const estrato = d && d.estrato;
    nota.innerHTML = 'Identidad resuelta. Con el contrato C-01 corregido, el motor abriría el gate de ' +
      'contexto de mercado con el estrato <b>verificado</b> (hoy el endpoint devuelve ' +
      esc(estrato) + ' por defecto: no se usa). Emisión deshabilitada en el prototipo (D7).';
  }
}

/* ── V2 · Cartera (solo lectura) ────────────────────────────────────────── */

async function cargarCartera() {
  const cap = $('cartera-caption');
  const body = $('cartera-body');
  if (!state.token) { cap.textContent = 'Inicie sesión para leer la cartera.'; return; }
  cap.textContent = 'Cargando…';
  try {
    const casos = await api('/api/dictamenes');
    state.casos = Array.isArray(casos) ? casos : (casos && casos.items) || [];
    pintarMetricas();
    pintarCartera();
  } catch (e) {
    cap.textContent = 'No se pudo leer la cartera.';
    body.innerHTML = `<tr><td colspan="8" class="muted t-sm" style="padding:var(--sp-md)">` +
      `<span class="chip err">ERROR</span> ${esc(e.message)} — <button class="btn sm" onclick="cargarCartera()">Reintentar</button></td></tr>`;
  }
}

function pintarMetricas() {
  const c = state.casos;
  $('m-total').textContent = c.length;
  $('m-ctl').textContent = c.filter(x => Number(x.certificado_cargado) === 1).length;
  $('m-pdf').textContent = c.filter(x => x.pdf_path).length;
  const ciudades = Array.from(new Set(c.map(x => x.ciudad).filter(Boolean)));
  $('f-ciudad').innerHTML = '<option value="">Toda ciudad</option>' +
    ciudades.map(x => `<option value="${esc(x)}">${esc(x)}</option>`).join('');
}

function pintarCartera() {
  const q = $('q').value.trim().toLowerCase();
  const ciudad = $('f-ciudad').value;
  const filas = state.casos.filter(x => {
    const texto = [x.folio_matricula, x.direccion, x.barrio].join(' ').toLowerCase();
    return (!q || texto.indexOf(q) >= 0) && (!ciudad || x.ciudad === ciudad);
  });
  $('cartera-caption').textContent = filas.length + ' de ' + state.casos.length + ' casos.';
  if (!filas.length) {
    $('cartera-body').innerHTML = '<tr><td colspan="8" class="muted t-sm" style="padding:var(--sp-md)">' +
      (state.casos.length ? 'Ningún caso coincide con el filtro.' :
        'Sin casos en la cartera: se crean desde la consola (acción deshabilitada en el prototipo).') + '</td></tr>';
    return;
  }
  $('cartera-body').innerHTML = filas.map(x => {
    const aptitud = x.pdf_path ? ['ok', 'EMITIDO'] :
      (Number(x.certificado_cargado) === 1 ? ['warn', 'EN PROCESO'] : ['info', 'SIN CTL']);
    return `<tr>` +
      `<td class="mono">${esc(x.folio_matricula || '—')}</td>` +
      `<td>${esc(x.direccion || '—')}</td>` +
      `<td class="mono-sm">${esc(x.ciudad || 'barranquilla')}</td>` +
      `<td class="num">${esVacio(x.area) ? '<span class="chip warn">PENDIENTE</span>' : esc(x.area) + ' m²'}</td>` +
      `<td class="num">${esVacio(x.estrato) ? '<span class="chip warn">PENDIENTE</span>' : esc(x.estrato)}</td>` +
      `<td><span class="chip ${aptitud[0]}">${aptitud[1]}</span></td>` +
      `<td>${x.pdf_path ? `<a class="btn sm" href="/api/dictamenes/${esc(x.id)}/pdf">PDF</a>` : '<span class="chip info">NO EMITIDO</span>'}</td>` +
      `<td class="row"><button class="btn sm" disabled title="Requiere C-02 (ficha de verificación)">Abrir</button>` +
      `<button class="btn sm" disabled title="Deshabilitado en el prototipo (D7)">Editar</button></td>` +
      `</tr>`;
  }).join('');
}

/* ── V3 · Fuentes (solo lectura; requiere rol admin) ────────────────────── */

async function consultarFuentes() {
  const body = $('fuentes-body');
  body.innerHTML = '<tr><td colspan="4" class="muted t-sm" style="padding:var(--sp-md)">Consultando…</td></tr>';
  const fuentes = [];
  let configCrudo = null;

  async function probar(nombre, contrato, fn) {
    try {
      const d = await fn();
      fuentes.push([nombre, contrato, ['ok', 'RESPONDE'], JSON.stringify(d).slice(0, 260)]);
      return d;
    } catch (e) {
      const sinPermiso = /403/.test(e.message);
      fuentes.push([nombre, contrato, [sinPermiso ? 'warn' : 'err', sinPermiso ? 'SIN PERMISO' : 'NO DISPONIBLE'], e.message]);
      return null;
    }
  }

  configCrudo = await probar('Plataforma', 'GET /api/config', () => api('/api/config'));
  await probar('Estado', 'GET /api/v1/status', () => api('/api/v1/status'));
  await probar('Cola de PDF', 'GET /api/v1/pdf/estado', () => api('/api/v1/pdf/estado'));
  await probar('Listas restrictivas', 'POST /api/v1/listas/refrescar',
    () => api('/api/v1/listas/refrescar', { method: 'POST' }));
  await probar('Catastro en vivo', 'GET /api/v1/geo/ciudades', () => api('/api/v1/geo/ciudades'));

  body.innerHTML = fuentes.map(([n, c, [clase, etq], det]) =>
    `<tr><td>${esc(n)}</td><td class="mono-sm">${esc(c)}</td>` +
    `<td><span class="chip ${clase}">${esc(etq)}</span></td><td class="mono-xs">${esc(det)}</td></tr>`).join('');

  if (configCrudo) {
    $('kv-config').innerHTML = Object.keys(configCrudo).slice(0, 12).map(k =>
      `<dt>${esc(k)}</dt><dd>${esc(typeof configCrudo[k] === 'object'
        ? JSON.stringify(configCrudo[k]) : configCrudo[k])}</dd>`).join('');
  } else {
    $('kv-config').innerHTML = '<dt>estado</dt><dd>sin datos (ver tabla de fuentes)</dd>';
  }
  try { $('pre-pdf').textContent = JSON.stringify(await api('/api/v1/pdf/estado'), null, 1); }
  catch (e) { $('pre-pdf').textContent = 'no disponible — ' + e.message; }
}

/* ── Navegación ─────────────────────────────────────────────────────────── */

function mostrar(vista) {
  ['v1', 'v2', 'v3', 'v4'].forEach(v => {
    const panel = $('view-' + v), tab = $('tab-' + v);
    if (!panel || !tab) return;
    const activo = v === vista;
    panel.classList.toggle('hidden', !activo);
    tab.setAttribute('aria-selected', String(activo));
  });
  if (vista === 'v2') cargarCartera();
  if (vista === 'v3') consultarFuentes();
}

/* ── Arranque ───────────────────────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.tab').forEach(t => {
    t.addEventListener('click', () => mostrar(t.dataset.view));
  });
  $('btn-entrar').addEventListener('click', entrar);
  $('btn-salir').addEventListener('click', salir);
  $('btn-resolver').addEventListener('click', resolver);
  $('btn-refrescar').addEventListener('click', cargarCartera);
  $('btn-fuentes').addEventListener('click', consultarFuentes);
  $('q').addEventListener('input', pintarCartera);
  $('f-ciudad').addEventListener('change', pintarCartera);
  $('direccion').addEventListener('keydown', (e) => { if (e.key === 'Enter') resolver(); });
  $('ciudad').addEventListener('change', (e) => {
    $('ciudad-nota').innerHTML = `<span>Jurisdicción seleccionada: <b>${esc(e.target.value)}</b>. ` +
      'Las capas oficiales se consultan al generar el dictamen (no en el prototipo).</span>';
  });
});
