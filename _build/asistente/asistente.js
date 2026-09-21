'use strict';

/* ---------- utilidades ---------- */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const sinRepetidos = (l) => [...new Set(l)];
const CARPETA = { venta: 'ventas', alquiler: 'alquileres' };
const PREFIJO = { venta: 'ven_', alquiler: 'alq_' };
const EXTRAS = '__extras';

const S = {
  vista: 'lista', filtro: 'todas', props: [], opciones: { items: {} }, opiniones: null, op: null,
  grupos: [], sinPublicar: false, acciones: [], E: null, publicacion: null, commit: '',
};

async function api(ruta, cuerpo, { crudo = false } = {}) {
  const opciones = { headers: { 'X-Asistente': '1' } };
  if (cuerpo !== undefined) {
    opciones.method = 'POST';
    opciones.body = crudo ? cuerpo : JSON.stringify(cuerpo);
    opciones.headers['Content-Type'] = crudo ? 'application/octet-stream' : 'application/json';
  }
  const r = await fetch('/asistente/api/' + ruta, opciones);
  const datos = await r.json().catch(() => ({ error: 'La respuesta del asistente no se entendió.' }));
  if (!r.ok) {
    const e = new Error(datos.error || 'Algo falló.');
    e.datos = datos;
    throw e;
  }
  return datos;
}

function aviso(texto, tipo = 'ok') {
  const el = document.createElement('div');
  el.className = 'aviso ' + (tipo === 'error' ? 'error' : '');
  el.textContent = texto;
  $('#avisos').appendChild(el);
  setTimeout(() => el.remove(), tipo === 'error' ? 7000 : 3500);
}

const precioTexto = (p) => (p.moneda === 'USD' ? 'U$D ' : '$ ') + Number(p.precio).toLocaleString('es-AR');
const urlPagina = (p) => `/${CARPETA[p.operacion]}/${PREFIJO[p.operacion]}${p.id}.html`;

function preguntar({ titulo, texto = '', valor = null, tipo = 'text', casilla = '', ok = 'Aceptar', peligro = false }) {
  return new Promise((resolver) => {
    const d = $('#dialogo');
    d.innerHTML = `<h3>${esc(titulo)}</h3><p class="ayuda">${texto}</p>
      ${valor !== null ? `<input id="dlg-valor" type="${tipo}" ${tipo === 'number' ? 'step="any" min="0"' : ''} value="${esc(valor)}">` : ''}
      ${casilla ? `<label class="casilla"><input type="checkbox" id="dlg-casilla"> ${esc(casilla)}</label>` : ''}
      <div class="pie"><button class="btn" data-r="no">Cancelar</button><button class="btn ${peligro ? 'btn-rojo' : 'btn-rojo'}" data-r="si">${esc(ok)}</button></div>`;
    const cerrar = (si) => {
      const res = { ok: si, valor: $('#dlg-valor') ? $('#dlg-valor').value : null, marcado: $('#dlg-casilla') ? $('#dlg-casilla').checked : false };
      d.close();
      d.onclick = null;
      resolver(res);
    };
    d.onclick = (e) => { const b = e.target.closest('[data-r]'); if (b) cerrar(b.dataset.r === 'si'); };
    d.oncancel = (e) => { e.preventDefault(); cerrar(false); };
    d.showModal();
    if ($('#dlg-valor')) $('#dlg-valor').select();
  });
}

function mostrarProgreso(texto) {
  const d = $('#dialogo');
  d.innerHTML = `<h3>Un momento…</h3><p class="ayuda">${esc(texto)}</p>`;
  d.onclick = null;
  d.oncancel = (e) => e.preventDefault();
  if (!d.open) d.showModal();
}
const cerrarProgreso = () => { if ($('#dialogo').open) $('#dialogo').close(); };

/* ---------- carga y navegación ---------- */
async function cargar() {
  const { propiedades, ...resto } = await api('estado');
  Object.assign(S, resto, { props: propiedades });
  S.op = JSON.parse(JSON.stringify(S.opiniones));
}

async function irA(vista) {
  if (S.E && S.E.sucio && !(await preguntar({ titulo: 'Hay cambios sin guardar', texto: 'Si salís ahora, se pierden los datos que cargaste.', ok: 'Salir sin guardar' })).ok) return;
  S.E = null;
  S.vista = vista;
  if (vista === 'publicar') await cargarCommit();
  render();
  window.scrollTo(0, 0);
}

async function cargarCommit() {
  S.commit = (await api('commit')).mensaje;
}

function render() {
  $$('#nav button').forEach((b) => b.classList.toggle('activa', b.dataset.vista === (S.vista === 'editor' ? 'lista' : S.vista)));
  $('#pendiente').hidden = !S.sinPublicar;
  const vistas = { lista: vistaLista, opiniones: vistaOpiniones, publicar: vistaPublicar, editor: vistaEditor };
  $('#app').innerHTML = vistas[S.vista]();
  if (S.vista === 'editor') iniciarEditor();
}

/* ---------- lista de propiedades ---------- */
function vistaLista() {
  const lista = S.props.filter((p) => S.filtro === 'todas' || p.operacion === S.filtro);
  const cuenta = (f) => S.props.filter((p) => f === 'todas' || p.operacion === f).length;
  const pestana = (f, t) => `<button class="${S.filtro === f ? 'activa' : ''}" data-accion="filtro" data-f="${f}">${t} (${cuenta(f)})</button>`;
  return `
    ${S.sinPublicar ? `<div class="aviso-cambios"><span><strong>Hay cambios sin generar.</strong> El sitio todavía no refleja lo último que hiciste.</span><button class="btn btn-rojo btn-chico" data-accion="ir-publicar">Ir a Publicar</button></div>` : ''}
    <div class="cabecera"><h2>Propiedades</h2><button class="btn btn-rojo" data-accion="nueva">＋ Nueva propiedad</button></div>
    <div class="pestanas">${pestana('todas', 'Todas')}${pestana('venta', 'Venta')}${pestana('alquiler', 'Alquiler')}</div>
    ${lista.map(fila).join('') || '<div class="vacio">No hay propiedades en esta lista.</div>'}`;
}

function fila(p) {
  const estados = ['disponible', 'reservada', 'vendida'];
  return `<div class="fila estado-${p.estado}">
    <img class="mini" src="/assets/img/${CARPETA[p.operacion]}/${p.id}/thumbs/01.jpg" alt="" onerror="this.style.visibility='hidden'">
    <div class="info"><strong>${esc(p.titulo)}</strong><small>${esc(p.barrio)} · ${esc(p.tipo)} · ${p.operacion === 'venta' ? 'Venta' : 'Alquiler'}</small></div>
    <div class="precio">${esc(precioTexto(p))}</div>
    <select data-accion="estado" data-id="${p.id}">${estados.map((e) => `<option value="${e}" ${e === p.estado ? 'selected' : ''}>${e[0].toUpperCase() + e.slice(1)}</option>`).join('')}</select>
    <div class="acciones">
      <button class="btn btn-chico" data-accion="precio" data-id="${p.id}">Precio</button>
      <button class="btn btn-chico" data-accion="editar" data-id="${p.id}">Editar</button>
      <a class="btn btn-chico" href="${urlPagina(p)}" target="_blank" rel="noopener">Ver</a>
      <button class="btn btn-chico btn-peligro" data-accion="quitar" data-id="${p.id}">Quitar</button>
    </div></div>`;
}

async function accionRapida(id, campo, valor, mensaje) {
  try {
    await api('rapida', { id, campo, valor });
    await cargar();
    render();
    aviso(mensaje);
  } catch (e) { aviso(e.message, 'error'); render(); }
}

/* ---------- editor ---------- */
const CAMPOS_MEDIDAS = [
  ['sup_total', 'Superficie total (m²)', 'Todo el terreno o lote.'],
  ['sup_cubierta', 'Superficie cubierta (m²)', 'Lo construido. Es la que se muestra en el listado.'],
  ['ambientes', 'Ambientes', 'Se usa en los filtros del listado.'],
  ['dormitorios', 'Dormitorios', ''],
  ['banos', 'Baños', ''],
  ['cocheras', 'Cocheras', ''],
  ['antiguedad', 'Antigüedad (años)', ''],
];

function propiedadVacia() {
  return { id: '', operacion: 'venta', estado: 'disponible', titulo: '', zona: '', direccion: '', barrio: '', partido: '', tipo: '',
    moneda: 'USD', precio: '', expensas: '', sup_total: '', sup_cubierta: '', ambientes: '', dormitorios: '', banos: '', cocheras: '',
    antiguedad: '', extras: [], descripcion: [], caracteristicas: {}, mapa: '' };
}

function nuevaPropiedad() {
  S.E = { nueva: true, p: propiedadVacia(), desc: '', fotos: [], fotosOriginales: [], idManual: false, mostrar: false, sucio: false, temporizador: null };
  S.vista = 'editor';
  render();
  window.scrollTo(0, 0);
}

async function editar(id) {
  const p = JSON.parse(JSON.stringify(S.props.find((x) => x.id === id)));
  for (const c of ['expensas', 'sup_total', 'sup_cubierta', 'ambientes', 'dormitorios', 'banos', 'cocheras', 'antiguedad', 'mapa']) if (p[c] === null) p[c] = '';
  const r = await api(`fotos?operacion=${p.operacion}&id=${p.id}`);
  S.E = { nueva: false, p, desc: p.descripcion.join('\n\n'), fotos: r.fotos.map((f) => ({ tipo: 'e', nombre: f.nombre, url: f.url })),
    fotosOriginales: r.fotos.map((f) => f.nombre), idManual: true, mostrar: false, sucio: false, temporizador: null };
  S.vista = 'editor';
  render();
  window.scrollTo(0, 0);
}

function campo({ c, t, ph = '', tipo = 'text', lista = '', ancho = 6, req = false, ayuda = '', bloqueado = false }) {
  const v = S.E.p[c] ?? '';
  return `<div class="c${ancho}" data-wrap="${c}">
    <label class="${req ? 'req' : ''}" for="f-${c}">${t}</label>
    <input id="f-${c}" type="${tipo}" ${tipo === 'number' ? 'step="any" min="0" inputmode="decimal"' : ''} data-campo="${c}" value="${esc(v)}" placeholder="${esc(ph)}" ${lista ? `list="${lista}"` : ''} ${bloqueado ? 'disabled' : ''} autocomplete="off">
    <div class="msg-campo" data-msg="${c}"></div>${ayuda ? `<div class="pista">${ayuda}</div>` : ''}</div>`;
}

function vistaEditor() {
  const E = S.E, p = E.p, o = S.opciones;
  const lista = (id, valores) => `<datalist id="${id}">${(valores || []).map((v) => `<option value="${esc(v)}">`).join('')}</datalist>`;
  return `
    <div class="cabecera"><h2>${E.nueva ? 'Nueva propiedad' : 'Editar: ' + esc(p.titulo)}</h2><button class="btn" data-accion="cancelar">← Volver a la lista</button></div>
    <div class="editor"><div>
      <section class="panel"><h3>1. ¿Qué vas a cargar?</h3>
        <p class="ayuda">${E.nueva ? 'Elegí si es una venta o un alquiler.' : 'El tipo de operación no se puede cambiar una vez creada la propiedad.'}</p>
        <div class="rejilla"><div class="c6"><div class="segmentado">
          <label class="${E.nueva ? '' : 'bloqueado'}"><input type="radio" name="operacion" value="venta" data-campo="operacion" ${p.operacion === 'venta' ? 'checked' : ''} ${E.nueva ? '' : 'disabled'}><span>Venta</span></label>
          <label class="${E.nueva ? '' : 'bloqueado'}"><input type="radio" name="operacion" value="alquiler" data-campo="operacion" ${p.operacion === 'alquiler' ? 'checked' : ''} ${E.nueva ? '' : 'disabled'}><span>Alquiler</span></label>
        </div></div>
        <div class="c6"><label for="f-estado">Estado</label><select id="f-estado" data-campo="estado">
          ${['disponible', 'reservada', 'vendida'].map((e) => `<option value="${e}" ${p.estado === e ? 'selected' : ''}>${e[0].toUpperCase() + e.slice(1)}</option>`).join('')}</select>
          <div class="pista">«Reservada» muestra una etiqueta. «Vendida» la saca del listado.</div></div></div>
      </section>

      <section class="panel" data-wrap="fotos"><h3>2. Fotos <small id="cant-fotos"></small></h3>
        <p class="ayuda">La <strong>primera foto es la portada</strong>. Se achican y se ordenan solas, y se les borra la ubicación GPS. Podés reordenarlas con las flechas.</p>
        <div class="fotos" id="fotos"></div>
        <div class="soltar" id="soltar">Arrastrá las fotos acá o <button class="btn btn-chico" data-accion="elegir-fotos">Elegir fotos</button>
          <input type="file" id="archivos" multiple accept="image/*,.heic,.heif" hidden></div>
        <div class="msg-campo" data-msg="fotos"></div>
      </section>

      <section class="panel"><h3>3. Datos principales</h3>
        <p class="ayuda">Lo que se ve en el listado y en el título de la página.</p>
        <div class="rejilla">
          ${campo({ c: 'titulo', t: 'Título', ph: 'Ej: PH 3 Amb Al Frente con Cochera Cubierta', ancho: 12, req: true, ayuda: 'Es el título de la publicación. Evitá escribirlo todo en mayúsculas.' })}
          ${campo({ c: 'tipo', t: 'Tipo de propiedad', ph: 'PH, Casa, Departamento…', lista: 'dl-tipos', ancho: 4, req: true })}
          ${campo({ c: 'precio', t: 'Precio', tipo: 'number', ancho: 4, req: true, ayuda: 'Solo el número, sin puntos ni símbolo. Ej: 69000' })}
          <div class="c4"><label for="f-moneda">Moneda</label><select id="f-moneda" data-campo="moneda"><option value="USD" ${p.moneda === 'USD' ? 'selected' : ''}>Dólares (U$D)</option><option value="ARS" ${p.moneda === 'ARS' ? 'selected' : ''}>Pesos ($)</option></select></div>
          ${campo({ c: 'expensas', t: 'Expensas (en pesos)', tipo: 'number', ancho: 4, ayuda: 'Dejalo vacío si no tiene.' })}
          ${campo({ c: 'id', t: 'Identificador', ph: 'ej: melo', ancho: 8, req: true, bloqueado: !E.nueva, ayuda: E.nueva ? 'Nombre corto para la carpeta de fotos y la dirección de la página. Se sugiere solo; no se puede cambiar después.' : 'No se puede cambiar.' })}
        </div>
      </section>

      <section class="panel"><h3>4. Ubicación</h3>
        <p class="ayuda">Se muestra como «dirección, barrio, partido». La zona se usa para el filtro del listado.</p>
        <div class="rejilla">
          ${campo({ c: 'direccion', t: 'Dirección', ph: 'Ej: Melo 557', ancho: 6, req: true })}
          ${campo({ c: 'barrio', t: 'Barrio', lista: 'dl-barrios', ancho: 6, req: true })}
          ${campo({ c: 'partido', t: 'Partido o ciudad', lista: 'dl-partidos', ancho: 6, req: true })}
          ${campo({ c: 'zona', t: 'Zona (para el filtro)', lista: 'dl-zonas', ancho: 6, req: true, ayuda: 'Elegí una de las existentes para que se agrupe bien.' })}
          ${campo({ c: 'mapa', t: 'Mapa de Google', tipo: 'text', ancho: 12, ph: 'Pegá acá el código de «Insertar un mapa»', ayuda: 'En Google Maps: buscá la dirección → Compartir → Insertar un mapa → Copiar HTML. Pegalo entero, yo extraigo el enlace.' })}
        </div>
      </section>

      <section class="panel"><h3>5. Medidas</h3>
        <p class="ayuda">Completá lo que sepas; lo que no, dejalo vacío.</p>
        <div class="rejilla">${CAMPOS_MEDIDAS.map(([c, t, a]) => campo({ c, t, tipo: 'number', ancho: 3, ayuda: a })).join('')}</div>
      </section>

      <section class="panel" data-wrap="descripcion"><h3>6. Descripción</h3>
        <p class="ayuda">Separá los párrafos con una línea en blanco. Escribila en minúscula normal (no todo en mayúsculas).</p>
        <textarea id="f-desc" data-campo="__desc" placeholder="PH 3 amb en planta baja al frente en excelente estado...">${esc(E.desc)}</textarea>
        <div class="msg-campo" data-msg="descripcion"></div>
      </section>

      <section class="panel"><h3>7. Características</h3>
        <p class="ayuda">Tocá las opciones que correspondan. Si falta una, escribila en «+ otra…» y apretá Enter.</p>
        <div class="grupo"><h4>Etiquetas del resumen <span class="pista">(las que se ven como botoncitos arriba del contacto)</span></h4><div class="chips" data-chips="${EXTRAS}"></div></div>
        ${S.grupos.map((g) => `<div class="grupo"><h4>${esc(g)}</h4><div class="chips" data-chips="${esc(g)}"></div></div>`).join('')}
      </section>
    </div>

    <aside class="lado">
      <div class="panel"><h3>Así se ve en el listado</h3><iframe id="prev" class="prev" title="Vista previa"></iframe></div>
      <div class="panel"><h3>Revisión</h3><ul class="revision" id="revision"><li class="av">Revisando…</li></ul></div>
      <div class="botones-lado">
        <button class="btn btn-rojo" data-accion="guardar">Guardar</button>
        <button class="btn" data-accion="guardar-publicar">Guardar y generar las páginas</button>
      </div>
    </aside></div>
    ${lista('dl-tipos', o.tipos)}${lista('dl-barrios', o.barrios)}${lista('dl-partidos', o.partidos)}${lista('dl-zonas', o.zonas)}`;
}

function iniciarEditor() {
  renderFotos();
  $$('[data-chips]').forEach((c) => renderChips(c.dataset.chips));
  programarRevision(0);
}

function seleccion(grupo) {
  const p = S.E.p;
  if (grupo === EXTRAS) return p.extras;
  return (p.caracteristicas[grupo] = p.caracteristicas[grupo] || []);
}

function renderChips(grupo) {
  const sugeridos = grupo === EXTRAS ? S.opciones.extras : (S.opciones.items[grupo] || []);
  const elegidos = seleccion(grupo);
  const todos = sinRepetidos([...sugeridos, ...elegidos]);
  const cont = $(`[data-chips="${CSS.escape(grupo)}"]`);
  if (!cont) return;
  cont.innerHTML = todos.map((t) => `<button type="button" class="chip ${elegidos.includes(t) ? 'on' : ''}" data-accion="chip" data-grupo="${esc(grupo)}" data-valor="${esc(t)}">${esc(t)}</button>`).join('')
    + `<input type="text" class="chip-nuevo" data-grupo="${esc(grupo)}" placeholder="+ otra…">`;
}

function renderFotos() {
  const E = S.E;
  $('#cant-fotos').textContent = E.fotos.length ? `(${E.fotos.length})` : '';
  $('#fotos').innerHTML = E.fotos.map((f, i) => `<div class="foto">
    <img src="${esc(f.url)}" alt="">${i === 0 ? '<span class="marca">Portada</span>' : ''}${f.tipo === 'u' ? '<span class="marca nueva">Nueva</span>' : ''}
    <div class="herramientas">
      <button data-accion="foto-izq" data-i="${i}" title="Mover hacia adelante" ${i === 0 ? 'disabled' : ''}>◀</button>
      <button data-accion="foto-portada" data-i="${i}" title="Hacer portada" ${i === 0 ? 'disabled' : ''}>★</button>
      <button data-accion="foto-quitar" data-i="${i}" title="Quitar">✕</button>
      <button data-accion="foto-der" data-i="${i}" title="Mover hacia atrás" ${i === E.fotos.length - 1 ? 'disabled' : ''}>▶</button>
    </div></div>`).join('') || '<p class="ayuda">Todavía no cargaste fotos.</p>';
}

function agregarArchivos(archivos) {
  const imagenes = [...archivos].filter((f) => /^image\//.test(f.type) || /\.(jpe?g|png|webp|heic|heif)$/i.test(f.name));
  imagenes.sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
  imagenes.forEach((f) => S.E.fotos.push({ tipo: 'u', file: f, url: URL.createObjectURL(f) }));
  if (imagenes.length) { S.E.sucio = true; renderFotos(); programarRevision(); }
}

function mover(i, j) {
  const f = S.E.fotos;
  if (j < 0 || j >= f.length) return;
  [f[i], f[j]] = [f[j], f[i]];
  S.E.sucio = true;
  renderFotos();
  programarRevision();
}

const slug = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');

function sugerirId() {
  const p = S.E.p;
  const base = slug(p.direccion.replace(/\d+/g, ' ').replace(/\b(av|avenida|calle|pje|pasaje|ruta)\b\.?/gi, ' ')) || slug(p.barrio) || 'propiedad';
  const usados = S.props.map((x) => x.id);
  let id = base, n = 2;
  while (usados.includes(id)) id = `${base}_${n++}`;
  return id;
}

function armar() {
  const E = S.E, p = JSON.parse(JSON.stringify(E.p));
  p.id = p.id.trim().toLowerCase();
  p.descripcion = E.desc.split(/\n\s*\n/).map((x) => x.replace(/\s*\n\s*/g, ' ').trim()).filter(Boolean);
  return p;
}

function programarRevision(espera = 350) {
  const E = S.E;
  if (!E) return;
  clearTimeout(E.temporizador);
  E.temporizador = setTimeout(revisar, espera);
}

async function revisar() {
  const E = S.E;
  if (!E) return;
  try {
    const carga = { propiedad: armar(), nueva: E.nueva, nFotos: E.fotos.length };
    const [chequeo, tarjeta] = await Promise.all([api('validar', carga), api('tarjeta', carga)]);
    if (S.E !== E) return;
    pintarRevision(chequeo);
    pintarTarjeta(tarjeta.html);
  } catch (e) { /* la revisión es solo una ayuda */ }
}

function pintarRevision({ errores, avisos }) {
  const E = S.E;
  const claseError = E.mostrar ? 'err' : 'pend';
  const lis = [...errores.map((x) => `<li class="${claseError}">${esc(x.mensaje)}</li>`), ...avisos.map((x) => `<li class="av">${esc(x.mensaje)}</li>`)];
  lis.push(!errores.length && !avisos.length ? '<li class="ok">Todo en orden</li>' : !errores.length ? '<li class="ok">Se puede guardar (los avisos son sugerencias)</li>' : '');
  $('#revision').innerHTML = lis.join('');
  $$('[data-wrap]').forEach((w) => {
    const c = w.dataset.wrap;
    const e = errores.find((x) => x.campo === c);
    const mostrar = !!(e && E.mostrar);
    w.classList.toggle('campo-error', mostrar);
    const m = w.querySelector('[data-msg]');
    if (m) m.textContent = mostrar ? e.mensaje : '';
  });
}

function pintarTarjeta(html) {
  const portada = S.E.fotos[0] ? S.E.fotos[0].url : null;
  const marco = html
    ? html.replace(/url\([^)]*thumbs\/01\.jpg\)/, portada ? `url(${portada})` : 'none')
    : '<p style="font-family:sans-serif;color:#6b7280;padding:20px">Completá título, tipo, precio y ubicación para ver la tarjeta.</p>';
  const iframe = $('#prev');
  iframe.srcdoc = `<!doctype html><html><head><meta charset="utf-8">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@4.6.0/dist/css/bootstrap.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Fjalla+One&family=Noto+Sans&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="/style.css">
    <style>html,body{overflow:hidden}body{background:#f4f5f7;margin:0;padding:14px}.tarjeta-propiedad{flex:0 0 100%;max-width:100%;padding:0}</style></head>
    <body><div class="row m-0">${marco}</div></body></html>`;
  const ajustar = () => { try { iframe.style.height = Math.max(200, iframe.contentDocument.body.scrollHeight + 4) + 'px'; } catch (e) { /* nada */ } };
  iframe.onload = () => { ajustar(); setTimeout(ajustar, 400); setTimeout(ajustar, 1200); };
}

function fotosCambiaron() {
  const E = S.E;
  return E.fotos.some((f) => f.tipo === 'u') || E.fotos.map((f) => f.nombre).join() !== E.fotosOriginales.join();
}

async function guardar(publicar) {
  const E = S.E;
  E.mostrar = true;
  let chequeo;
  try { chequeo = await api('validar', { propiedad: armar(), nueva: E.nueva, nFotos: E.fotos.length }); } catch (e) { return aviso(e.message, 'error'); }
  pintarRevision(chequeo);
  if (chequeo.errores.length) {
    aviso('Hay datos para corregir: mirá la revisión a la derecha.', 'error');
    const wrap = $(`[data-wrap="${chequeo.errores[0].campo}"]`);
    if (wrap) wrap.scrollIntoView({ behavior: 'smooth', block: 'center' });
    return;
  }
  try {
    if (fotosCambiaron()) {
      const nuevas = E.fotos.filter((f) => f.tipo === 'u');
      let hechas = 0;
      for (const f of nuevas) {
        mostrarProgreso(`Subiendo foto ${++hechas} de ${nuevas.length}…`);
        f.token = (await api('subir?nombre=' + encodeURIComponent(f.file.name), f.file, { crudo: true })).token;
      }
      mostrarProgreso('Guardando las fotos…');
      await api('fotos_aplicar', { operacion: E.p.operacion, id: E.p.id.trim().toLowerCase(), orden: E.fotos.map((f) => (f.tipo === 'e' ? { e: f.nombre } : { u: f.token })) });
    }
    mostrarProgreso('Guardando los datos…');
    await api('guardar', { propiedad: armar(), nueva: E.nueva });
    if (publicar) {
      mostrarProgreso('Generando las páginas del sitio…');
      S.publicacion = await api('publicar', {});
    }
    cerrarProgreso();
    await cargar();
    if (publicar) await cargarCommit();
    S.E = null;
    S.vista = publicar ? 'publicar' : 'lista';
    render();
    window.scrollTo(0, 0);
    aviso(publicar ? 'Guardado y páginas generadas.' : 'Guardado. Falta generar las páginas (Publicar).');
  } catch (e) {
    cerrarProgreso();
    aviso(e.message, 'error');
    if (e.datos && e.datos.errores) pintarRevision(e.datos);
  }
}

/* ---------- opiniones ---------- */
function vistaOpiniones() {
  const o = S.op;
  return `<div class="cabecera"><h2>Opiniones de clientes</h2></div>
    <section class="panel"><h3>Puntaje en Google</h3>
      <p class="ayuda">Se muestra en el Home y en Quiénes somos. Actualizalo cuando cambie en Google Maps.</p>
      <div class="rejilla">
        <div class="c3"><label>Puntaje (0 a 5)</label><input type="number" step="0.1" min="0" max="5" data-op="puntaje" value="${esc(o.puntaje)}"></div>
        <div class="c3"><label>Cantidad de opiniones</label><input type="number" min="0" data-op="cantidad" value="${esc(o.cantidad)}"></div>
        <div class="c6"><label>Enlace a las opiniones en Google</label><input type="text" data-op="url" value="${esc(o.url)}"></div>
      </div></section>
    <section class="panel"><h3>Opiniones que se muestran</h3>
      <p class="ayuda">Solo el nombre de pila. Copiá el texto tal cual lo escribió el cliente.</p>
      ${o.opiniones.map((r, i) => `<div class="rejilla" style="margin-bottom:14px">
        <div class="c3"><label>Nombre</label><input type="text" data-op-r="${i}" data-k="nombre" value="${esc(r.nombre)}"></div>
        <div class="c8"><label>Opinión</label><textarea style="min-height:70px" data-op-r="${i}" data-k="texto">${esc(r.texto)}</textarea></div>
        <div class="c1" style="grid-column: span 1; align-self:end"><button class="btn btn-chico btn-peligro" data-accion="op-quitar" data-i="${i}">Quitar</button></div></div>`).join('')}
      <button class="btn btn-chico" data-accion="op-agregar">＋ Agregar opinión</button></section>
    <button class="btn btn-rojo" data-accion="op-guardar">Guardar opiniones</button>`;
}

/* ---------- publicar ---------- */
function vistaPublicar() {
  const pub = S.publicacion;
  const msg = S.commit || 'Actualizar propiedades';
  return `<div class="cabecera"><h2>Publicar cambios</h2></div>
    <section class="panel"><h3>1. Generar las páginas</h3>
      <p class="ayuda">${S.sinPublicar ? '<strong>Hay cambios pendientes.</strong> ' : 'No hay cambios pendientes. '}Esto actualiza en tu computadora las fichas, los listados, el Home y el sitemap.</p>
      <button class="btn btn-rojo" data-accion="publicar">Generar las páginas ahora</button>
      ${pub ? `<p style="margin:16px 0 6px"><strong>${pub.ok ? '✓ Listo.' : '✗ Hubo un problema:'}</strong></p><pre class="registro">${esc(pub.log)}</pre>` : ''}
    </section>
    <section class="panel"><h3>2. Revisar cómo quedó</h3>
      <p class="ayuda">Antes de subirlo, mirá el sitio en tu computadora.</p>
      <a class="btn" href="/" target="_blank">Home</a> <a class="btn" href="/ventas.html" target="_blank">Ventas</a> <a class="btn" href="/alquileres.html" target="_blank">Alquileres</a></section>
    <section class="panel"><h3>3. Comitear y subir</h3>
      <p class="ayuda">Desde la carpeta del repositorio. Este es un mensaje de commit sugerido, según lo que hiciste:</p>
      <textarea class="mensaje-commit" id="msg-commit">${esc(msg)}</textarea>
      <p style="margin:10px 0"><button class="btn btn-chico" data-accion="copiar-commit">Copiar mensaje</button></p>
      <div class="bloque-codigo">git add -A
git commit -m "..."
git push</div></section>`;
}

/* ---------- eventos ---------- */
document.addEventListener('click', async (ev) => {
  const nav = ev.target.closest('#nav button');
  if (nav) return irA(nav.dataset.vista);
  const el = ev.target.closest('[data-accion]');
  if (!el) return;
  const a = el.dataset.accion, E = S.E;
  const id = el.dataset.id, i = Number(el.dataset.i);
  if (a === 'filtro') { S.filtro = el.dataset.f; render(); }
  else if (a === 'ir-publicar') irA('publicar');
  else if (a === 'nueva') nuevaPropiedad();
  else if (a === 'editar') editar(id);
  else if (a === 'cancelar') irA('lista');
  else if (a === 'precio') {
    const p = S.props.find((x) => x.id === id);
    const r = await preguntar({ titulo: 'Cambiar el precio', texto: `${esc(p.titulo)}<br>Precio actual: <strong>${esc(precioTexto(p))}</strong>`, valor: p.precio, tipo: 'number', ok: 'Guardar precio' });
    if (r.ok) accionRapida(id, 'precio', r.valor, 'Precio actualizado.');
  } else if (a === 'quitar') {
    const p = S.props.find((x) => x.id === id);
    const r = await preguntar({ titulo: 'Quitar la propiedad', texto: `Se quita <strong>${esc(p.titulo)}</strong> del sitio. Los links que ya se compartieron dejarán de funcionar.`, casilla: 'Mover también sus fotos a una carpeta temporal', ok: 'Quitar', peligro: true });
    if (r.ok) {
      try { await api('quitar', { id, borrarFotos: r.marcado }); await cargar(); render(); aviso('Propiedad quitada.'); } catch (e) { aviso(e.message, 'error'); }
    }
  } else if (a === 'chip') {
    const sel = seleccion(el.dataset.grupo), v = el.dataset.valor;
    const pos = sel.indexOf(v);
    if (pos >= 0) sel.splice(pos, 1); else sel.push(v);
    E.sucio = true; renderChips(el.dataset.grupo); programarRevision();
  } else if (a === 'elegir-fotos') $('#archivos').click();
  else if (a === 'foto-izq') mover(i, i - 1);
  else if (a === 'foto-der') mover(i, i + 1);
  else if (a === 'foto-portada') { const [f] = E.fotos.splice(i, 1); E.fotos.unshift(f); E.sucio = true; renderFotos(); programarRevision(); }
  else if (a === 'foto-quitar') { E.fotos.splice(i, 1); E.sucio = true; renderFotos(); programarRevision(); }
  else if (a === 'guardar') guardar(false);
  else if (a === 'guardar-publicar') guardar(true);
  else if (a === 'op-agregar') S.op.opiniones.push({ nombre: '', texto: '' }), render();
  else if (a === 'op-quitar') S.op.opiniones.splice(i, 1), render();
  else if (a === 'op-guardar') {
    try { await api('opiniones', S.op); await cargar(); render(); aviso('Opiniones guardadas. Falta generar las páginas (Publicar).'); } catch (e) { aviso(e.message, 'error'); }
  } else if (a === 'publicar') {
    mostrarProgreso('Generando las páginas del sitio…');
    try { S.publicacion = await api('publicar', {}); await cargar(); await cargarCommit(); } catch (e) { aviso(e.message, 'error'); }
    cerrarProgreso(); render();
  } else if (a === 'copiar-commit') {
    const t = $('#msg-commit'); t.select();
    try { await navigator.clipboard.writeText(t.value); aviso('Mensaje copiado.'); } catch (e) { document.execCommand('copy'); aviso('Mensaje copiado.'); }
  }
});

document.addEventListener('change', (ev) => {
  const t = ev.target;
  if (t.dataset.accion === 'estado') return accionRapida(t.dataset.id, 'estado', t.value, 'Estado actualizado.');
  if (t.id === 'archivos') { agregarArchivos(t.files); t.value = ''; }
});

document.addEventListener('input', (ev) => {
  const t = ev.target, E = S.E;
  if (t.dataset.op) { S.op[t.dataset.op] = t.value; return; }
  if (t.dataset.opR !== undefined) { S.op.opiniones[Number(t.dataset.opR)][t.dataset.k] = t.value; return; }
  if (!E || !t.dataset.campo) return;
  const c = t.dataset.campo;
  if (c === '__desc') E.desc = t.value;
  else if (c === 'operacion') { if (t.checked) { E.p.operacion = t.value; if (!E.p.precio) E.p.moneda = t.value === 'venta' ? 'USD' : 'ARS'; const m = $('#f-moneda'); if (m) m.value = E.p.moneda; } }
  else if (c === 'mapa') E.p.mapa = t.value;
  else E.p[c] = t.value;
  if (c === 'id') E.idManual = true;
  if (E.nueva && !E.idManual && (c === 'direccion' || c === 'barrio')) { E.p.id = sugerirId(); const f = $('#f-id'); if (f) f.value = E.p.id; }
  E.sucio = true;
  programarRevision();
});

document.addEventListener('keydown', (ev) => {
  const t = ev.target;
  if (ev.key === 'Enter' && t.classList && t.classList.contains('chip-nuevo')) {
    ev.preventDefault();
    const v = t.value.trim();
    if (!v) return;
    const sel = seleccion(t.dataset.grupo);
    if (!sel.includes(v)) sel.push(v);
    S.E.sucio = true;
    renderChips(t.dataset.grupo);
    programarRevision();
  }
});

['dragover', 'dragleave', 'drop'].forEach((tipo) => document.addEventListener(tipo, (ev) => {
  const zona = ev.target.closest && ev.target.closest('#soltar');
  if (!zona) return;
  ev.preventDefault();
  zona.classList.toggle('encima', tipo === 'dragover');
  if (tipo === 'drop') agregarArchivos(ev.dataTransfer.files);
}));

window.addEventListener('beforeunload', (ev) => { if (S.E && S.E.sucio) { ev.preventDefault(); ev.returnValue = ''; } });

(async () => {
  try {
    await cargar();
    render();
  } catch (e) {
    $('#app').innerHTML = `<div class="panel"><h3>No pude conectarme con el asistente</h3><p class="ayuda">${esc(e.message)}. Volvé a abrirlo con <code>python _build/asistente.py</code>.</p></div>`;
  }
})();
