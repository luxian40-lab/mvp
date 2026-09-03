(function () {
  const app = document.getElementById('mg-app');
  if (!app) return;
  const csrf = app.dataset.csrf || '';
  const state = {
    extraccion: {},
    segmentos: [],
    escenario: null,
  };

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

  function showScreen(name) {
    $$('.mg-screen').forEach((el) => {
      const on = el.dataset.screen === name;
      el.hidden = !on;
      el.classList.toggle('mg-screen--active', on);
    });
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function showStep(n) {
    $$('.mg-step').forEach((el) => {
      const on = Number(el.dataset.step) === n;
      el.hidden = !on;
      el.classList.toggle('is-on', on);
    });
    $$('.mg-progress span').forEach((el) => {
      el.classList.toggle('is-on', Number(el.dataset.p) === n);
    });
  }

  function money(n) {
    const v = Number(n) || 0;
    return new Intl.NumberFormat('es-CO', {
      style: 'currency', currency: 'COP', maximumFractionDigits: 0,
    }).format(v);
  }

  async function post(url, body) {
    const res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf,
      },
      credentials: 'same-origin',
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.success === false) {
      throw new Error(data.error || 'Algo falló. Intenta de nuevo.');
    }
    return data;
  }

  function fillFromExtraccion(ex) {
    const map = {
      producto: ex.producto,
      categoria: ex.categoria,
      presentacion: ex.presentacion,
      unidad_venta: ex.unidad_venta || 'unidad',
      ubicacion_actual: ex.ubicacion_actual,
      mercado_objetivo: ex.mercado_objetivo,
    };
    Object.keys(map).forEach((k) => {
      const el = $(`[name="${k}"]`);
      if (el && map[k]) el.value = map[k];
    });
  }

  function collectWizard() {
    const val = (name) => {
      const el = $(`[name="${name}"]`);
      return el ? el.value.trim() : '';
    };
    const alcanceEl = $('input[name="alcance"]:checked');
    return {
      producto: val('producto'),
      categoria: val('categoria'),
      presentacion: val('presentacion'),
      precio: val('precio') || 0,
      unidad_venta: val('unidad_venta') || 'unidad',
      ubicacion_actual: val('ubicacion_actual'),
      mercado_objetivo: val('mercado_objetivo'),
      alcance: alcanceEl ? alcanceEl.value : 'local',
      segmentos_cliente: state.segmentos.slice(),
      ticket_mensual_estimado: val('ticket_mensual') || 0,
      ticket_no_se: !!($('#mg-ticket-nose') && $('#mg-ticket-nose').checked),
      capacidad_mensual_maxima: val('capacidad') || null,
      extraccion: state.extraccion,
      guardar: true,
    };
  }

  function tipoBadge(traza) {
    if (!traza || !traza.tipo) return '';
    const t = traza.tipo;
    if (t === 'dato') return 'dato';
    if (t === 'estimacion') return 'estimación';
    return 'supuesto';
  }

  function renderResultado(esc) {
    state.escenario = esc;
    $('#mg-res-titulo').textContent = esc.nombre_escenario || 'Tu mercado estimado';
    $('#mg-confianza').textContent = esc.nota_confianza || '';

    const cards = [
      { k: 'TAM', v: esc.tam, key: 'tam', n: 'Mercado total estimado / mes' },
      { k: 'SAM', v: esc.sam, key: 'sam', n: 'Mercado al que sí puedes aspirar / mes' },
      { k: 'SOM base', v: esc.som_base, key: 'som_base', n: 'Lo realista capturable / mes' },
    ];
    const box = $('#mg-cards-tss');
    box.innerHTML = cards.map((c) => {
      const tr = (esc.trazabilidad || {})[c.key] || {};
      const cls = tr.tipo === 'supuesto' ? 'mg-card mg-card--supuesto' : 'mg-card';
      return `<article class="${cls}"><div class="mg-card__k">${c.k} · ${tipoBadge(tr)}</div>
        <div class="mg-card__v">${money(c.v)}</div>
        <div class="mg-card__n">${c.n}</div></article>`;
    }).join('');

    $('#mg-funnel').innerHTML = `
      <div style="width:100%">TAM ${money(esc.tam)}</div>
      <div style="width:78%;margin:0 auto">SAM ${money(esc.sam)}</div>
      <div style="width:52%;margin:0 auto">SOM cons. ${money(esc.som_conservador)}</div>
      <div style="width:58%;margin:0 auto">SOM base ${money(esc.som_base)}</div>
      <div style="width:64%;margin:0 auto">SOM amb. ${money(esc.som_ambicioso)}</div>`;

    const body = $('#mg-traza-body');
    const lines = Object.entries(esc.trazabilidad || {}).map(([k, t]) => {
      return `<p><strong>${k}</strong>: ${money(t.valor)} · <em>${t.tipo}</em>
        · ${t.fuente || ''} · ${t.formula || ''}</p>`;
    });
    body.innerHTML = lines.join('') || '<p>Sin detalle.</p>';

    // prep sim
    $('#sim-ticket').value = esc.ticket_mensual_estimado || '';
    $('#sim-precio').value = esc.precio || '';
    $('#sim-cap').value = esc.capacidad_mensual_maxima || '';
  }

  function renderGtm(data) {
    const g = data.gtm || {};
    const seg = data.segmento_recomendado || {};
    const plan = g.plan_30_dias || {};
    let html = '';
    if (data.explicacion_embudo) {
      html += `<p>${escapeHtml(data.explicacion_embudo)}</p>`;
    }
    if (seg.nombre) {
      html += `<h3>Segmento recomendado</h3><p><strong>${escapeHtml(seg.nombre)}</strong> — ${escapeHtml(seg.por_que || '')}</p>`;
    }
    if (data.recomienda_calculadora_margen) {
      html += `<div class="mg-warn">${escapeHtml(data.nota_margen || 'Usa la Calculadora de margen de eki antes de fijar precio.')}
        <br><a href="/calculadora-margen/">Abrir calculadora de margen →</a></div>`;
    }
    const cp = g.cliente_prioritario || {};
    html += `<h3>1. Cliente prioritario</h3><p>${escapeHtml(cp.quien || '')}<br><span class="mg-hint">${escapeHtml(cp.por_que || '')}</span></p>`;
    html += `<h3>2. Oferta inicial</h3><p>${escapeHtml(g.oferta_inicial || '')}</p>`;
    const canales = Array.isArray(g.canal_prioritario) ? g.canal_prioritario.join(', ') : (g.canal_prioritario || '');
    html += `<h3>3. Canal prioritario</h3><p>${escapeHtml(canales)}</p>`;
    html += `<h3>4. Mensaje comercial</h3><div class="mg-msg-box"><div id="mg-msg-txt">${escapeHtml(g.mensaje_comercial || '')}</div>
      <button type="button" id="mg-copy">Copiar</button></div>`;
    html += `<h3>5. Meta comercial (30 días)</h3><p>${escapeHtml(g.meta_comercial || '')}</p>`;
    html += `<h3>6. Plan 30 días</h3>`;
    ['semana_1', 'semana_2', 'semana_3', 'semana_4'].forEach((k, i) => {
      const acts = plan[k] || [];
      html += `<p><strong>Semana ${i + 1}</strong></p><ul>${acts.map((a) => `<li>${escapeHtml(a)}</li>`).join('')}</ul>`;
    });
    $('#mg-gtm-body').innerHTML = html;
    const copyBtn = $('#mg-copy');
    if (copyBtn) {
      copyBtn.onclick = () => {
        const t = $('#mg-msg-txt');
        if (t) navigator.clipboard.writeText(t.textContent || '');
      };
    }
  }

  function escapeHtml(s) {
    return String(s || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // Espejo JS del simulador (mismas fórmulas que backend)
  function simLocal() {
    const esc = state.escenario || {};
    const sam = Number(esc.sam) || 0;
    const clientes = Number($('#sim-clientes').value) || 0;
    const ticket = Number($('#sim-ticket').value) || 0;
    const precio = Number($('#sim-precio').value) || 0;
    let part = Number($('#sim-part').value) || 0;
    if (part > 1) part = part / 100;
    const capU = Number($('#sim-cap').value) || 0;
    const ventas = clientes * ticket;
    let capVal = null;
    if (capU > 0 && precio > 0) capVal = capU * precio;
    let som = sam * part;
    if (capVal != null) som = Math.min(som, capVal);
    const pct = sam > 0 ? (som / sam) * 100 : 0;
    $('#mg-sim-out').innerHTML = `
      <div>Ventas mensuales (clientes × ticket): <strong>${money(ventas)}</strong></div>
      <div>Ventas anuales: <strong>${money(ventas * 12)}</strong></div>
      <div>SOM simulado: <strong>${money(som)}</strong>${capVal != null ? ' <em>(topeado por capacidad)</em>' : ''}</div>
      <div>% del SAM: <strong>${pct.toFixed(2)}%</strong></div>`;
  }

  // Events
  $('#mg-empezar').addEventListener('click', async () => {
    const err = $('#mg-entrada-err');
    err.hidden = true;
    const texto = ($('#mg-texto').value || '').trim();
    if (texto.length < 8) {
      err.textContent = 'Cuéntanos un poco más: qué vendes y dónde quieres venderlo.';
      err.hidden = false;
      return;
    }
    $('#mg-empezar').disabled = true;
    try {
      const data = await post('/mercado-gtm/api/extraer/', { texto });
      state.extraccion = data.extraccion || {};
      fillFromExtraccion(state.extraccion);
      showScreen('wizard');
      showStep(1);
    } catch (e) {
      // Si IA falla, igual dejamos pasar al wizard vacío
      err.textContent = e.message + ' Puedes llenar el wizard a mano.';
      err.hidden = false;
      showScreen('wizard');
      showStep(1);
    } finally {
      $('#mg-empezar').disabled = false;
    }
  });

  $$('[data-next]').forEach((btn) => {
    btn.addEventListener('click', () => showStep(Number(btn.dataset.next)));
  });
  $$('[data-prev]').forEach((btn) => {
    btn.addEventListener('click', () => showStep(Number(btn.dataset.prev)));
  });
  $$('[data-back]').forEach((btn) => {
    btn.addEventListener('click', () => showScreen(btn.dataset.back));
  });

  $$('#mg-segmentos .mg-chip').forEach((btn) => {
    btn.addEventListener('click', () => {
      const seg = btn.dataset.seg;
      const i = state.segmentos.indexOf(seg);
      if (i >= 0) state.segmentos.splice(i, 1);
      else state.segmentos.push(seg);
      btn.classList.toggle('is-on', i < 0);
    });
  });

  $('#mg-calcular').addEventListener('click', async () => {
    const err = $('#mg-wizard-err');
    err.hidden = true;
    const payload = collectWizard();
    if (!payload.producto) {
      err.textContent = 'Indica el producto.';
      err.hidden = false;
      return;
    }
    $('#mg-calcular').disabled = true;
    try {
      const data = await post('/mercado-gtm/api/calcular/', payload);
      renderResultado(data);
      showScreen('resultado');
    } catch (e) {
      err.textContent = e.message;
      err.hidden = false;
    } finally {
      $('#mg-calcular').disabled = false;
    }
  });

  $('#mg-btn-gtm').addEventListener('click', async () => {
    const err = $('#mg-res-err');
    err.hidden = true;
    try {
      const data = await post('/mercado-gtm/api/gtm/', {
        id: state.escenario && state.escenario.id,
        escenario: state.escenario,
        recomendar_margen: !(state.escenario && Number(state.escenario.precio) > 0),
      });
      renderGtm(data);
      showScreen('gtm');
    } catch (e) {
      err.textContent = e.message;
      err.hidden = false;
    }
  });

  $('#mg-btn-sim').addEventListener('click', () => {
    showScreen('sim');
    simLocal();
  });
  ['sim-clientes', 'sim-ticket', 'sim-precio', 'sim-part', 'sim-cap'].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', simLocal);
  });

  $('#mg-btn-chat').addEventListener('click', () => showScreen('chat'));
  $('#mg-btn-otro').addEventListener('click', () => {
    state.escenario = null;
    showScreen('entrada');
  });

  async function sendChat(q) {
    if (!q) return;
    const log = $('#mg-chat-log');
    log.insertAdjacentHTML('beforeend', `<div class="mg-bubble mg-bubble--user">${escapeHtml(q)}</div>`);
    try {
      const data = await post('/mercado-gtm/api/preguntar/', {
        pregunta: q,
        id: state.escenario && state.escenario.id,
        escenario: state.escenario,
      });
      log.insertAdjacentHTML('beforeend', `<div class="mg-bubble">${escapeHtml(data.respuesta || '')}</div>`);
    } catch (e) {
      log.insertAdjacentHTML('beforeend', `<div class="mg-bubble">${escapeHtml(e.message)}</div>`);
    }
  }

  $('#mg-chat-send').addEventListener('click', () => {
    const inp = $('#mg-chat-input');
    const q = (inp.value || '').trim();
    inp.value = '';
    sendChat(q);
  });
  $$('#mg-quick button').forEach((b) => {
    b.addEventListener('click', () => sendChat(b.dataset.q));
  });
})();
