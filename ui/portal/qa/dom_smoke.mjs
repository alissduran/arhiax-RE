/* QA de EJECUCIÓN del portal DICTUS.
 *
 * El QA estático (tests/test_portal_dictus_ui.py) comprueba ids, sintaxis y
 * disciplina de datos; no puede ver un `ReferenceError` dentro de una función que
 * solo corre cuando llega un dato. Este arnés ejecuta `portal.js` en un DOM mínimo
 * —construido a partir del propio `index.html`, no de una lista escrita a mano— y
 * recorre los caminos de pintado con payloads sintéticos:
 *
 *   · una resolución COMPLETA (todos los campos verificados),
 *   · una resolución VACÍA (todo UNRESOLVED con motivo: patrón «vacío explicado»),
 *   · el cambio de las cuatro perspectivas y de todas las pestañas,
 *   · la cartera con y sin casos, y la apertura de un caso.
 *
 * Falla (código 1) ante cualquier excepción o si un destino visible queda sin pintar.
 *
 * Uso:  node ui/portal/qa/dom_smoke.mjs
 */
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';

const AQUI = dirname(fileURLToPath(import.meta.url));
/* Por defecto se prueba la FUENTE (ui/portal). Con `--dir public/portal` se prueba
 * la copia desplegable, que es la que realmente ve el usuario en /portal/. */
const argDir = process.argv.indexOf('--dir');
const PORTAL = argDir > -1 ? join(process.cwd(), process.argv[argDir + 1])
  : join(AQUI, '..');
const html = readFileSync(join(PORTAL, 'index.html'), 'utf8');
const js = readFileSync(join(PORTAL, 'portal.js'), 'utf8');
console.log(`[dir] ${PORTAL}`);

/* ── Índice de elementos a partir del HTML real ─────────────────────────────── */
const elementos = [];
for (const m of html.matchAll(/<([a-zA-Z][\w-]*)((?:\s+[\w:-]+(?:="[^"]*")?)*)\s*\/?>/g)) {
  const attrs = {};
  for (const a of (m[2] || '').matchAll(/([\w:-]+)(?:="([^"]*)")?/g)) {
    attrs[a[1]] = a[2] === undefined ? '' : a[2];
  }
  elementos.push({ tag: m[1].toLowerCase(), attrs, id: attrs.id });
}

function crearElemento(attrs = {}) {
  const clases = new Set(String(attrs.class || '').split(/\s+/).filter(Boolean));
  const dataset = {};
  for (const [k, v] of Object.entries(attrs)) {
    if (k.startsWith('data-')) dataset[k.slice(5).replace(/-([a-z])/g, (_, c) => c.toUpperCase())] = v;
  }
  const el = {
    tag: attrs.tag || 'div',
    id: attrs.id || '',
    dataset,
    textContent: '',
    innerHTML: '',
    className: attrs.class || '',
    value: attrs.value || '',
    handlers: {},
    classList: {
      add: (c) => clases.add(c),
      remove: (c) => clases.delete(c),
      contains: (c) => clases.has(c),
      toggle: (c, on) => (on === undefined ? (clases.has(c) ? clases.delete(c) : clases.add(c))
        : (on ? clases.add(c) : clases.delete(c)))
    },
    setAttribute: (k, v) => { el.attrs[k] = String(v); },
    getAttribute: (k) => el.attrs[k],
    addEventListener: (ev, fn) => { (el.handlers[ev] = el.handlers[ev] || []).push(fn); },
    attrs: { ...attrs }
  };
  el.className = attrs.class || '';
  return el;
}

const porId = new Map();
for (const e of elementos) {
  if (!e.id) continue;
  const el = crearElemento({ ...e.attrs, tag: e.tag });
  // `innerHTML`/`textContent` se guardan en campos de respaldo: asignar a la misma
  // propiedad dentro de su propio setter sería una recursión infinita.
  let _html = '';
  let _txt = '';
  Object.defineProperty(el, 'innerHTML', {
    get: () => _html,
    set: (v) => { _html = String(v); },
    enumerable: true
  });
  Object.defineProperty(el, 'textContent', {
    get: () => _txt,
    set: (v) => { _txt = String(v); },
    enumerable: true
  });
  porId.set(e.id, el);
}

const porSelector = (sel) => {
  const todos = elementos.map((e) => porId.get(e.id) || crearElemento({ ...e.attrs, tag: e.tag }));
  if (sel === '.persp-btn') return todos.filter((e) => (e.attrs.class || '').includes('persp-btn'));
  if (sel === '.tabpanel') return todos.filter((e) => (e.attrs.class || '').includes('tabpanel'));
  if (sel === '[data-go]') return todos.filter((e) => 'data-go' in (e.attrs || {}));
  if (sel === '[data-abrir]') return todos.filter((e) => 'data-abrir' in (e.attrs || {}));
  if (sel === '.rail-item') return todos.filter((e) => (e.attrs.class || '').includes('rail-item'));
  return [];
};

const problemas = [];
const document = {
  getElementById: (id) => {
    if (!porId.has(id)) {
      problemas.push(`el guion pidió un id inexistente: ${id}`);
      return null;
    }
    return porId.get(id);
  },
  querySelectorAll: porSelector,
  addEventListener: (ev, fn) => { (document._h = document._h || {})[ev] = fn; },
  documentElement: { dataset: {} },
  body: { dataset: {}, classList: { add() {}, remove() {}, toggle() {}, contains: () => false } }
};

const respuestas = new Map();
const sandbox = {
  document,
  location: { search: '' },
  URLSearchParams,
  console,
  setTimeout: (fn) => { fn(); return 1; },
  clearTimeout: () => {},
  fetch: async (url) => {
    const ruta = String(url).split('?')[0];
    const cuerpo = respuestas.has(ruta) ? respuestas.get(ruta) : {};
    return {
      ok: true, status: 200,
      json: async () => cuerpo
    };
  }
};
sandbox.window = sandbox;

vm.runInNewContext(js, sandbox, { filename: 'portal.js' });

/* ── Payloads sintéticos (SIN valores de negocio: solo estados) ─────────────── */
const campo = (value, status, source, motivo) => ({ value, status, source, motivo });
const RESOLUCION_COMPLETA = {
  consulta: { normalizada: 'CL 00 00 00', ciudad: 'barranquilla', hora: '2026-01-01T00:00:00Z' },
  campos: {
    numero_predial: campo('000000000000000000000000000001', 'VERIFIED_CATASTRAL', 'capa predio'),
    nupre: campo('AFT0000TEST', 'VERIFIED_OFFICIAL', 'registro de adopción'),
    folio_matricula: campo('000-000000', 'VERIFIED_REGISTRAL', 'SNR'),
    barrio: campo('BARRIO PRUEBA', 'VERIFIED_OFFICIAL', 'unidades administrativas'),
    localidad: campo('LOCALIDAD PRUEBA', 'VERIFIED_OFFICIAL', 'unidades administrativas'),
    estrato: campo('1', 'VERIFIED_OFFICIAL', 'estratificación'),
    coordenada: campo('0.0000, 0.0000', 'VERIFIED_OFFICIAL', 'geocoder catastral')
  },
  fuentes: [
    { id: 'geocoder_catastro_baq', status: 'OK', detalle: 'coincidencia única' },
    { id: 'ordenamiento_urbano', status: 'OK', detalle: 'punto en polígono' },
    { id: 'registro_adopcion', status: 'NO_MATCH', detalle: 'sin adopción para el predial' }
  ],
  candidatos: []
};
const RESOLUCION_VACIA = {
  consulta: { normalizada: 'CL 00 00 00', ciudad: 'barranquilla', hora: '2026-01-01T00:00:00Z' },
  campos: Object.fromEntries(['folio_matricula', 'numero_predial', 'nupre', 'barrio',
    'localidad', 'estrato', 'coordenada'].map((c) => [c, campo(null, 'UNRESOLVED', null,
    `motivo declarado para ${c}`)])),
  fuentes: [{ id: 'geocoder_catastro_baq', status: 'SOURCE_UNAVAILABLE', detalle: 'sin respuesta' }],
  candidatos: []
};
const CASO = {
  id: 7, folio_matricula: '000-000000', direccion: 'CL 00 00 00', ciudad: 'barranquilla',
  barrio: 'BARRIO PRUEBA', area: 1, estrato: 1, certificado_cargado: 1,
  pdf_path: '/tmp/dictamen.pdf'
};

respuestas.set('/api/login', { token: 'qa-token', rol: 'admin' });
respuestas.set('/api/me', { username: 'qa-portal' });
respuestas.set('/api/config', { version_line: 'QA v0' });
respuestas.set('/api/dictamenes', [CASO]);
respuestas.set('/api/dictamenes/7/documentos', [
  { id: 1, nombre: 'certificado.pdf', tipo: 'CTL', creado: '2026-01-01' }
]);
respuestas.set('/api/v1/geo/ciudades', {
  ciudades: [{ ciudad: 'barranquilla', estado: 'disponible' }], nacionales: {}
});
respuestas.set('/api/v1/pdf/estado', { ok: true });
respuestas.set('/api/v1/status', { ciudades: ['barranquilla'] });
respuestas.set('/api/resolver-matricula', RESOLUCION_COMPLETA);

/* ── Ejercicio de los caminos de pintado ───────────────────────────────────── */
const pasos = [];
async function paso(nombre, fn) {
  try {
    await fn();
    pasos.push([nombre, true, '']);
  } catch (e) {
    const primera = String((e && e.stack) || '').split('\n').slice(1, 3).join(' | ');
    pasos.push([nombre, false, `${e && e.name}: ${e && e.message} · ${primera}`]);
  }
}

await paso('arranque (DOMContentLoaded)', async () => {
  await document._h.DOMContentLoaded();
});
await paso('resolución completa → tarjetas, tablas y ledger', async () => {
  sandbox.pintarResolucion(RESOLUCION_COMPLETA);
  const esperados = ['k-identidad-v', 'k-valor-v', 'k-legal-v', 'k-territorio-v',
    'k-contrapartes-v', 'prop-body', 'terr-body', 'ledger-body', 'banner-chips'];
  for (const id of esperados) {
    const el = porId.get(id);
    if (!el || !(el.innerHTML || el.textContent)) {
      throw new Error(`el elemento ${id} quedó vacío tras pintar la resolución`);
    }
  }
  if (!porId.get('ledger-body').innerHTML.includes('geocoder_catastro_baq')) {
    throw new Error('el ledger no pintó las fuentes consultadas');
  }
  if (!porId.get('banner-chips').innerHTML.includes('AFT0000TEST')) {
    throw new Error('el banner no pintó el NUPRE devuelto por la fuente');
  }
});
await paso('resolución vacía → estados explicados, sin valores inventados', async () => {
  sandbox.pintarResolucion(RESOLUCION_VACIA);
  const cuerpo = porId.get('prop-body').innerHTML;
  if (!cuerpo.includes('PENDIENTE')) throw new Error('no se declaró el estado PENDIENTE');
  if (!cuerpo.includes('motivo declarado para')) {
    throw new Error('el vacío no llevó su motivo (patrón «vacío explicado»)');
  }
});
await paso('cuatro perspectivas', async () => {
  for (const p of ['inmobiliaria', 'titulux', 'lonja', 'tecnico']) {
    sandbox.setPerspectiva(p);
    if (document.body.dataset.persp !== p) throw new Error(`no se aplicó la perspectiva ${p}`);
    if (!porId.get('persp-nota').textContent) throw new Error(`perspectiva ${p} sin nota`);
  }
});
await paso('todas las pestañas del riel y de la barra', async () => {
  const destinos = new Set(porSelector('[data-go]').map((e) => e.attrs['data-go']));
  for (const d of destinos) {
    sandbox.setPestana(d);
    const panel = porId.get(`p-${d}`);
    if (!panel) throw new Error(`falta el panel #p-${d}`);
    if (panel.classList.contains('hidden')) throw new Error(`el panel #p-${d} quedó oculto estando activo`);
  }
});
await paso('cartera con casos + apertura de caso', async () => {
  porId.get('usuario').value = 'qa-portal';
  porId.get('clave').value = 'qa-clave';
  await sandbox.entrar();               // única escritura del portal: autenticarse
  if (!porId.get('sesion-info').classList.contains('hidden') === false &&
      !porId.get('sesion-usuario').textContent) {
    throw new Error('la sesión no se reflejó en el mástil');
  }
  if (!porId.get('cartera-body').innerHTML.includes('000-000000')) {
    throw new Error('la cartera no pintó el caso del endpoint');
  }
  await sandbox.abrirCaso(7, true);
  if (!porId.get('docs-body').innerHTML.includes('certificado.pdf')) {
    throw new Error('la pestaña de documentos no pintó el adjunto del endpoint');
  }
  if (!porId.get('exp-doc').innerHTML.includes('/pdf')) {
    throw new Error('el expediente no enlazó el dictamen emitido');
  }
});
await paso('cartera sin casos (no inventa filas)', async () => {
  respuestas.set('/api/dictamenes', []);
  await sandbox.cargarCartera();
  const cuerpo = porId.get('cartera-body').innerHTML;
  if (!cuerpo.includes('Sin casos')) throw new Error('la cartera vacía no se declaró');
});await paso('diagnóstico de contratos', async () => {
  await sandbox.consultarFuentes();
  if (!porId.get('fuentes-body').innerHTML.includes('/api/config')) {
    throw new Error('el diagnóstico no listó los contratos');
  }
});

/* ── Informe ───────────────────────────────────────────────────────────────── */
let fallos = 0;
for (const [nombre, ok, err] of pasos) {
  console.log(`${ok ? '[OK]  ' : '[FAIL]'} ${nombre}${err ? ' · ' + err : ''}`);
  if (!ok) fallos += 1;
}
for (const p of problemas) { console.log(`[FAIL] ${p}`); fallos += 1; }
console.log(fallos
  ? `\n[FAIL] ${fallos} problema(s) en la ejecución del portal`
  : `\n[OK] ${pasos.length} caminos de pintado ejecutados sin errores`);
process.exit(fallos ? 1 : 0);
