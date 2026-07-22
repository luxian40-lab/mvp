/* Editor de cursos eki_ops — JS-first */
(function () {
  const root = document.getElementById('curso-editor');
  if (!root) return;

  const csrf = root.dataset.csrf;
  const apiOrgs = root.dataset.apiOrgs;
  const apiCursos = root.dataset.apiCursos;

  const elOrg = document.getElementById('ce-org');
  const elCursos = document.getElementById('ce-cursos');
  const elMods = document.getElementById('ce-modulos');
  const elDetalle = document.getElementById('ce-detalle');
  const toast = document.getElementById('ce-toast');

  let state = {
    orgId: '',
    cursoId: null,
    moduloId: null,
    cursos: [],
    modulos: [],
    secciones: [],
    pasos: [],
  };

  function showToast(msg, isErr) {
    toast.textContent = msg;
    toast.className = 'ce-toast' + (isErr ? ' err' : '');
    toast.style.display = 'block';
    setTimeout(() => { toast.style.display = 'none'; }, 2800);
  }

  async function api(url, opts) {
    const options = Object.assign({
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'X-CSRFToken': csrf,
      },
      credentials: 'same-origin',
    }, opts || {});
    const res = await fetch(url, options);
    let data = {};
    try { data = await res.json(); } catch (e) { /* ignore */ }
    if (!res.ok || data.ok === false) {
      throw new Error((data && data.error) || ('Error ' + res.status));
    }
    return data;
  }

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  async function loadOrgs() {
    const data = await api(apiOrgs);
    elOrg.innerHTML = '<option value="">Todas / elegir para crear</option>' +
      (data.orgs || []).map(o => `<option value="${o.id}">${esc(o.nombre)}</option>`).join('');
  }

  async function loadCursos() {
    const q = state.orgId ? ('?org=' + encodeURIComponent(state.orgId)) : '';
    const data = await api(apiCursos + q);
    state.cursos = data.cursos || [];
    elCursos.innerHTML = state.cursos.map(c => `
      <li><button type="button" data-id="${c.id}" class="${state.cursoId === c.id ? 'active' : ''}">
        <strong>${esc(c.nombre)}</strong>
        <div class="muted" style="font-size:11px;">${esc(c.cliente_nombre)} · ${c.modulos_count || 0} mód.</div>
      </button></li>`).join('') || '<li class="ce-empty">Sin cursos</li>';
  }

  async function loadModulos() {
    if (!state.cursoId) {
      elMods.innerHTML = '<li class="ce-empty">Elija un curso</li>';
      elDetalle.innerHTML = '<p class="ce-empty">Seleccione un módulo para editar bloques y microcontenidos.</p>';
      return;
    }
    const data = await api('/portal/ops/api/cursos/' + state.cursoId + '/');
    state.modulos = data.modulos || [];
    elMods.innerHTML = state.modulos.map(m => `
      <li><button type="button" data-id="${m.id}" class="${state.moduloId === m.id ? 'active' : ''}">
        M${esc(m.numero)} · ${esc(m.titulo)}
      </button></li>`).join('') || '<li class="ce-empty">Sin módulos</li>';
  }

  async function loadDetalle() {
    if (!state.moduloId) {
      elDetalle.innerHTML = '<p class="ce-empty">Seleccione un módulo.</p>';
      return;
    }
    const data = await api('/portal/ops/api/modulos/' + state.moduloId + '/');
    state.secciones = data.secciones || [];
    state.pasos = data.pasos || [];
    renderDetalle(data.modulo);
  }

  function pasosDeSeccion(sid) {
    return state.pasos.filter(p => p.seccion_id === sid).sort((a, b) => a.orden - b.orden);
  }

  function renderPaso(p) {
    const isEval = p.tipo === 'evaluacion_opciones';
    return `
      <div class="ce-paso" data-paso-id="${p.id}">
        <div class="ce-paso__bar">
          <strong>#${p.orden} · ${esc(p.tipo)}</strong>
          <span class="ce-actions">
            <button type="button" class="btn btn-outline ce-paso-up" data-id="${p.id}">↑</button>
            <button type="button" class="btn btn-outline ce-paso-down" data-id="${p.id}">↓</button>
            <button type="button" class="btn btn-outline ce-paso-del" data-id="${p.id}">Borrar</button>
          </span>
        </div>
        <div class="ce-field"><label>Título interno</label>
          <input data-f="titulo" value="${esc(p.titulo)}"></div>
        <div class="ce-field"><label>Tipo</label>
          <select data-f="tipo">
            <option value="contenido" ${p.tipo === 'contenido' ? 'selected' : ''}>Contenido</option>
            <option value="evaluacion_opciones" ${p.tipo === 'evaluacion_opciones' ? 'selected' : ''}>Evaluación opciones</option>
          </select></div>
        <div class="ce-field"><label>Contenido / pregunta</label>
          <textarea data-f="contenido" rows="3">${esc(p.contenido)}</textarea></div>
        <div class="ce-field"><label>Media URL (opcional)</label>
          <input data-f="media_url" value="${esc(p.media_url)}"></div>
        <div class="ce-eval" style="${isEval ? '' : 'display:none'}">
          <div class="ce-field"><label>Opción A</label><input data-f="eval_opcion_a" value="${esc(p.eval_opcion_a)}"></div>
          <div class="ce-field"><label>Opción B</label><input data-f="eval_opcion_b" value="${esc(p.eval_opcion_b)}"></div>
          <div class="ce-field"><label>Opción C</label><input data-f="eval_opcion_c" value="${esc(p.eval_opcion_c)}"></div>
          <div class="ce-field"><label>Opción D</label><input data-f="eval_opcion_d" value="${esc(p.eval_opcion_d)}"></div>
          <div class="ce-field"><label>Correcta (A–D)</label><input data-f="respuesta_correcta" maxlength="1" value="${esc(p.respuesta_correcta)}"></div>
          <div class="ce-field"><label>Feedback correcto</label><textarea data-f="feedback_correcto" rows="2">${esc(p.feedback_correcto)}</textarea></div>
          <div class="ce-field"><label>Feedback incorrecto</label><textarea data-f="feedback_incorrecto" rows="2">${esc(p.feedback_incorrecto)}</textarea></div>
        </div>
        <div class="ce-actions">
          <button type="button" class="btn ce-paso-save" data-id="${p.id}">Guardar paso</button>
        </div>
      </div>`;
  }

  function renderDetalle(mod) {
    const modo = mod.modo_entrega || 'auto';
    elDetalle.innerHTML = `
      <div class="ce-row" style="justify-content:space-between;align-items:flex-start;">
        <h2 style="margin:0;">M${esc(mod.numero)} · ${esc(mod.titulo)}</h2>
      </div>

      <div class="ce-sec open" style="margin-top:12px;">
        <div class="ce-sec__head" style="cursor:default;">
          <span><strong>Contenido del módulo</strong> <span class="muted">(sin bloques — envío completo / legacy)</span></span>
        </div>
        <div class="ce-sec__body" style="display:block;">
          <div class="ce-field"><label>Modo de entrega</label>
            <select id="ce-mod-modo">
              <option value="auto" ${modo === 'auto' ? 'selected' : ''}>Automático (pasos si hay; si no, completo)</option>
              <option value="legacy" ${modo === 'legacy' ? 'selected' : ''}>Todo de una vez (contenido completo)</option>
              <option value="pasos" ${modo === 'pasos' ? 'selected' : ''}>Por microcontenidos (*listo*)</option>
            </select>
          </div>
          <div class="ce-field"><label>Descripción corta</label>
            <textarea id="ce-mod-desc" rows="2">${esc(mod.descripcion || '')}</textarea></div>
          <div class="ce-field"><label>Contenido completo (WhatsApp / legacy)</label>
            <textarea id="ce-mod-contenido" rows="8" placeholder="Texto que recibe el estudiante si el módulo va completo…">${esc(mod.contenido || '')}</textarea></div>
          <div class="ce-field"><label>Video URL</label>
            <input id="ce-mod-video" value="${esc(mod.video_url || '')}" placeholder="https://…"></div>
          <div class="ce-field"><label>PDF URL</label>
            <input id="ce-mod-pdf" value="${esc(mod.archivo_pdf_url || '')}" placeholder="https://…"></div>
          <div class="ce-field"><label>Imagen portada URL</label>
            <input id="ce-mod-img" value="${esc(mod.imagen_portada_url || '')}" placeholder="https://…"></div>
          <div class="ce-actions">
            <button type="button" class="btn" id="ce-mod-guardar">Guardar contenido del módulo</button>
          </div>
          <p class="ce-empty" style="margin-top:8px;">
            Si el curso no usa microcontenidos, basta con rellenar este bloque y modo «Todo de una vez» o «Automático».
          </p>
        </div>
      </div>

      <div class="ce-row" style="justify-content:space-between;margin-top:16px;">
        <h2 style="margin:0;font-size:0.95rem;">Microcontenidos (bloques → pasos)</h2>
        <button type="button" class="btn btn-outline" id="ce-sec-crear">+ Bloque</button>
      </div>
      <div id="ce-secciones">
        ${state.secciones.map(s => `
          <div class="ce-sec open" data-sec-id="${s.id}">
            <div class="ce-sec__head">
              <span><strong>Bloque ${s.orden}</strong> — <input data-sec-titulo="${s.id}" value="${esc(s.titulo)}" style="max-width:220px;padding:4px 8px;border:1px solid var(--borde);border-radius:6px;"></span>
              <span class="ce-actions">
                <button type="button" class="btn btn-outline ce-sec-save" data-id="${s.id}">Guardar</button>
                <button type="button" class="btn btn-outline ce-paso-add" data-sec="${s.id}">+ Paso</button>
              </span>
            </div>
            <div class="ce-sec__body">
              ${pasosDeSeccion(s.id).map(renderPaso).join('') || '<p class="ce-empty">Sin pasos</p>'}
            </div>
          </div>`).join('') || '<p class="ce-empty">Sin bloques. Opcional si usa solo contenido completo arriba.</p>'}
      </div>`;
  }

  function collectPasoFields(box) {
    const out = {};
    box.querySelectorAll('[data-f]').forEach(el => {
      out[el.getAttribute('data-f')] = el.value;
    });
    return out;
  }

  elOrg.addEventListener('change', async () => {
    state.orgId = elOrg.value;
    state.cursoId = null;
    state.moduloId = null;
    await loadCursos();
    await loadModulos();
  });

  elCursos.addEventListener('click', async (e) => {
    const btn = e.target.closest('button[data-id]');
    if (!btn) return;
    state.cursoId = parseInt(btn.dataset.id, 10);
    state.moduloId = null;
    await loadCursos();
    await loadModulos();
  });

  elMods.addEventListener('click', async (e) => {
    const btn = e.target.closest('button[data-id]');
    if (!btn) return;
    state.moduloId = parseInt(btn.dataset.id, 10);
    await loadModulos();
    await loadDetalle();
  });

  document.getElementById('ce-curso-crear').addEventListener('click', async () => {
    const nombre = document.getElementById('ce-curso-nombre').value.trim();
    if (!nombre) return showToast('Escriba el nombre del curso', true);
    if (!state.orgId) return showToast('Elija una organización', true);
    try {
      const data = await api(apiCursos, {
        method: 'POST',
        body: JSON.stringify({ nombre, cliente_id: parseInt(state.orgId, 10), activo: true }),
      });
      document.getElementById('ce-curso-nombre').value = '';
      state.cursoId = data.curso.id;
      await loadCursos();
      await loadModulos();
      showToast('Curso creado');
    } catch (err) { showToast(err.message, true); }
  });

  document.getElementById('ce-mod-crear').addEventListener('click', async () => {
    if (!state.cursoId) return showToast('Elija un curso', true);
    const titulo = document.getElementById('ce-mod-titulo').value.trim();
    if (!titulo) return showToast('Título del módulo', true);
    try {
      const data = await api('/portal/ops/api/cursos/' + state.cursoId + '/modulos/', {
        method: 'POST',
        body: JSON.stringify({ titulo, modo_entrega: 'pasos' }),
      });
      document.getElementById('ce-mod-titulo').value = '';
      state.moduloId = data.modulo.id;
      await loadModulos();
      await loadDetalle();
      showToast('Módulo creado');
    } catch (err) { showToast(err.message, true); }
  });

  elDetalle.addEventListener('click', async (e) => {
    const t = e.target;
    try {
      if (t.id === 'ce-mod-guardar') {
        const payload = {
          modo_entrega: document.getElementById('ce-mod-modo').value,
          descripcion: document.getElementById('ce-mod-desc').value,
          contenido: document.getElementById('ce-mod-contenido').value,
          video_url: document.getElementById('ce-mod-video').value,
          archivo_pdf_url: document.getElementById('ce-mod-pdf').value,
          imagen_portada_url: document.getElementById('ce-mod-img').value,
        };
        await api('/portal/ops/api/modulos/' + state.moduloId + '/', {
          method: 'PATCH', body: JSON.stringify(payload),
        });
        showToast('Contenido del módulo guardado');
        return;
      }
      if (t.id === 'ce-sec-crear') {
        await api('/portal/ops/api/modulos/' + state.moduloId + '/secciones/', {
          method: 'POST', body: JSON.stringify({}),
        });
        await loadDetalle();
        showToast('Bloque creado');
        return;
      }
      if (t.classList.contains('ce-sec-save')) {
        const id = t.dataset.id;
        const input = elDetalle.querySelector('[data-sec-titulo="' + id + '"]');
        await api('/portal/ops/api/secciones/' + id + '/', {
          method: 'PATCH', body: JSON.stringify({ titulo: input ? input.value : '' }),
        });
        showToast('Bloque guardado');
        return;
      }
      if (t.classList.contains('ce-paso-add')) {
        await api('/portal/ops/api/secciones/' + t.dataset.sec + '/pasos/', {
          method: 'POST',
          body: JSON.stringify({ tipo: 'contenido', contenido: '', titulo: '' }),
        });
        await loadDetalle();
        showToast('Paso agregado');
        return;
      }
      if (t.classList.contains('ce-paso-save')) {
        const box = t.closest('.ce-paso');
        const payload = collectPasoFields(box);
        await api('/portal/ops/api/pasos/' + t.dataset.id + '/', {
          method: 'PATCH', body: JSON.stringify(payload),
        });
        await loadDetalle();
        showToast('Paso guardado');
        return;
      }
      if (t.classList.contains('ce-paso-del')) {
        if (!confirm('¿Borrar este paso?')) return;
        await api('/portal/ops/api/pasos/' + t.dataset.id + '/', { method: 'DELETE' });
        await loadDetalle();
        showToast('Paso borrado');
        return;
      }
      if (t.classList.contains('ce-paso-up') || t.classList.contains('ce-paso-down')) {
        const ids = state.pasos.slice().sort((a, b) => a.orden - b.orden).map(p => p.id);
        const id = parseInt(t.dataset.id, 10);
        const idx = ids.indexOf(id);
        if (idx < 0) return;
        const j = t.classList.contains('ce-paso-up') ? idx - 1 : idx + 1;
        if (j < 0 || j >= ids.length) return;
        const tmp = ids[idx]; ids[idx] = ids[j]; ids[j] = tmp;
        await api('/portal/ops/api/modulos/' + state.moduloId + '/reordenar-pasos/', {
          method: 'POST', body: JSON.stringify({ orden_ids: ids }),
        });
        await loadDetalle();
        return;
      }
    } catch (err) { showToast(err.message, true); }
  });

  elDetalle.addEventListener('change', (e) => {
    if (e.target.getAttribute('data-f') === 'tipo') {
      const box = e.target.closest('.ce-paso');
      const evalBox = box && box.querySelector('.ce-eval');
      if (evalBox) evalBox.style.display = e.target.value === 'evaluacion_opciones' ? '' : 'none';
    }
  });

  (async function init() {
    try {
      await loadOrgs();
      await loadCursos();
      await loadModulos();
    } catch (err) {
      showToast(err.message || 'No se pudo cargar el editor', true);
    }
  })();
})();
