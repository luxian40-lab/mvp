(function () {
  'use strict';

  const app = document.getElementById('cm-app');
  if (!app) return;

  const CSRF = app.dataset.csrf;
  const API = {
    calcular: '/calculadora-margen/api/calcular/',
    recomendaciones: '/calculadora-margen/api/recomendaciones/',
    simular: '/calculadora-margen/api/simular-precio/',
    evento: '/calculadora-margen/api/evento/',
  };

  const qs = new URLSearchParams(window.location.search);
  const attrQuery = new URLSearchParams();
  ['org', 't', 'token', 'cliente', 'curso'].forEach((k) => {
    const v = qs.get(k);
    if (v) attrQuery.set(k === 'token' ? 't' : k, v);
  });
  const attrSuffix = attrQuery.toString() ? ('?' + attrQuery.toString()) : '';

  function trackEvento(evento, extra) {
    const body = Object.assign({ evento: evento }, extra || {});
    postJson(API.evento, body).catch(function () {});
  }

  let state = { resultado: null, wizardStep: 1 };

  const $ = (sel) => app.querySelector(sel);
  const $$ = (sel) => app.querySelectorAll(sel);

  function fmtMoney(n) {
    if (n == null || isNaN(n)) return '—';
    return '$' + Math.round(n).toLocaleString('es-CO');
  }

  function fmtPct(n) {
    if (n == null || isNaN(n)) return '—';
    return n.toFixed(1).replace('.', ',') + '%';
  }

  function getFormData() {
    const names = [
      'producto', 'cantidad_producida', 'unidad',
      'materias_primas', 'mano_obra', 'transporte', 'empaque', 'otros_costos',
      'costos_fijos', 'precio_actual',
    ];
    const data = {};
    names.forEach((name) => {
      const el = app.querySelector('[name="' + name + '"]');
      data[name] = el ? el.value : '';
    });
    return data;
  }

  function withAttr(url) {
    if (!attrSuffix) return url;
    return url + attrSuffix;
  }

  function postJson(url, body) {
    return fetch(withAttr(url), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': CSRF,
      },
      credentials: 'same-origin',
      body: JSON.stringify(body),
    }).then((r) => r.json().then((j) => ({ ok: r.ok, status: r.status, data: j })));
  }

  function showScreen(id) {
    $$('.cm-screen').forEach((s) => {
      s.classList.remove('cm-screen--active');
      s.hidden = true;
    });
    const el = document.getElementById(id);
    if (el) {
      el.hidden = false;
      el.classList.add('cm-screen--active');
    }
    window.scrollTo(0, 0);
  }

  function setWizardStep(step) {
    state.wizardStep = step;
    $$('[data-step-panel]').forEach((panel) => {
      const n = parseInt(panel.dataset.stepPanel, 10);
      panel.hidden = n !== step;
      panel.classList.toggle('cm-step--active', n === step);
    });
    $$('.cm-progress__step').forEach((dot) => {
      const n = parseInt(dot.dataset.step, 10);
      dot.classList.toggle('cm-progress__step--active', n === step);
      dot.classList.toggle('cm-progress__step--done', n < step);
    });
  }

  function validateStep(step) {
    if (step === 1) {
      const p = app.querySelector('[name="producto"]');
      const c = app.querySelector('[name="cantidad_producida"]');
      if (!p.value.trim()) { p.focus(); return false; }
      if (!c.value || parseFloat(c.value) <= 0) { c.focus(); return false; }
    }
    if (step === 3) {
      const pr = app.querySelector('[name="precio_actual"]');
      if (!pr.value || parseFloat(pr.value) < 0) { pr.focus(); return false; }
    }
    return true;
  }

  const ALERTS = {
    bajo: '⚠️ Tu margen está bajo. Estás trabajando mucho y quizá no te está dejando la ganancia que mereces. Revisa costos y precio.',
    medio: 'ℹ️ Tu margen es aceptable, pero hay espacio para mejorar. Mira las recomendaciones de abajo.',
    saludable: '✅ ¡Buen margen! Sigue cuidando costos y busca escalar sin perder rentabilidad.',
  };

  function renderResultado(r) {
    $('#cm-res-producto').textContent = r.producto;
    $('#cm-val-costo').textContent = fmtMoney(r.costo_unitario);
    $('#cm-val-precio').textContent = fmtMoney(r.precio_actual);
    $('#cm-val-margen').textContent = fmtPct(r.margen_actual);
    $('#cm-val-sugerido').textContent = fmtMoney(r.precio_sugerido_25);

    const cardMargen = $('#cm-card-margen');
    cardMargen.classList.remove('cm-card--bajo', 'cm-card--medio', 'cm-card--saludable');
    cardMargen.classList.add('cm-card--' + r.nivel_alerta);

    const alert = $('#cm-alert');
    alert.textContent = ALERTS[r.nivel_alerta] || '';
    alert.className = 'cm-alert cm-alert--visible cm-alert--' + r.nivel_alerta;
  }

  function loadRecomendaciones(r) {
    const loading = $('#cm-recs-loading');
    const resumen = $('#cm-recs-resumen');
    const list = $('#cm-recs-list');
    const err = $('#cm-recs-error');
    loading.hidden = false;
    resumen.hidden = true;
    list.hidden = true;
    err.hidden = true;

    postJson(API.recomendaciones, { datos: r }).then(({ ok, data }) => {
      loading.hidden = true;
      if (!ok || !data.success) {
        err.textContent = data.error || 'No pudimos cargar recomendaciones.';
        err.hidden = false;
        return;
      }
      if (data.resumen) {
        resumen.textContent = data.resumen;
        resumen.hidden = false;
      }
      list.innerHTML = '';
      (data.recomendaciones || []).forEach((t) => {
        const li = document.createElement('li');
        li.textContent = t;
        list.appendChild(li);
      });
      list.hidden = false;
      trackEvento('recomendaciones_ok');
    });
  }

  function onCalcular() {
    if (!validateStep(3)) return;
    const btn = $('#cm-btn-calcular');
    btn.disabled = true;
    btn.textContent = 'Calculando…';

    postJson(API.calcular, getFormData()).then(({ ok, data }) => {
      btn.disabled = false;
      btn.textContent = 'Ver cuánto gano';
      if (!ok || !data.success) {
        alert(data.error || 'Revisa los datos e intenta de nuevo.');
        return;
      }
      state.resultado = data;
      renderResultado(data);
      document.body.classList.remove('cm-body--wizard');
      showScreen('cm-screen-4');
      trackEvento('resultado_visto', { margen_rango: data.nivel_alerta });
      loadRecomendaciones(data);
    });
  }

  function openSimular() {
    const r = state.resultado;
    if (!r) return;
    const modal = $('#cm-modal-simular');
    const slider = $('#cm-sim-slider');
    const input = $('#cm-sim-input');
    const max = Math.max(r.precio_actual * 2, r.precio_sugerido_25 * 1.5, 10000);
    slider.max = Math.ceil(max);
    slider.value = r.precio_actual;
    input.value = r.precio_actual;
    updateSimMargen(r.precio_actual);
    modal.showModal();
  }

  function updateSimMargen(precio) {
    const r = state.resultado;
    if (!r) return;
    const margen = r.costo_unitario > 0 && precio > 0
      ? ((precio - r.costo_unitario) / precio * 100)
      : 0;
    $('#cm-sim-margen').textContent = fmtPct(margen);
  }

  function openCostos() {
    const r = state.resultado;
    if (!r || !r.desglose_costos) return;
    const bars = $('#cm-bars');
    bars.innerHTML = '';
    const total = r.total_variable || 1;
    const sorted = [...r.desglose_costos].sort((a, b) => b.monto - a.monto);
    sorted.forEach((item, i) => {
      const pct = total > 0 ? (item.monto / total * 100) : 0;
      const row = document.createElement('div');
      row.className = 'cm-bar-row' + (i === 0 ? ' cm-bar-row--top' : '');
      row.innerHTML =
        '<div class="cm-bar-row__head"><span>' + item.rubro + '</span><span>' + pct.toFixed(1) + '%</span></div>' +
        '<div class="cm-bar-row__track"><div class="cm-bar-row__fill" style="width:' + pct + '%"></div></div>';
      bars.appendChild(row);
    });
    $('#cm-modal-costos').showModal();
  }

  $('#cm-btn-empezar').addEventListener('click', () => {
    trackEvento('inicio_wizard');
    document.body.classList.add('cm-body--wizard');
    showScreen('cm-wizard');
    setWizardStep(1);
  });

  $$('[data-next]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const next = parseInt(btn.dataset.next, 10);
      if (!validateStep(state.wizardStep)) return;
      setWizardStep(next);
    });
  });

  $$('[data-prev]').forEach((btn) => {
    btn.addEventListener('click', () => setWizardStep(parseInt(btn.dataset.prev, 10)));
  });

  $('#cm-btn-calcular').addEventListener('click', onCalcular);

  $('#cm-btn-simular').addEventListener('click', openSimular);
  $('#cm-btn-costos').addEventListener('click', openCostos);
  $('#cm-modal-simular-cerrar').addEventListener('click', () => $('#cm-modal-simular').close());
  $('#cm-modal-costos-cerrar').addEventListener('click', () => $('#cm-modal-costos').close());

  const slider = $('#cm-sim-slider');
  const simInput = $('#cm-sim-input');
  slider.addEventListener('input', () => {
    simInput.value = slider.value;
    updateSimMargen(parseFloat(slider.value));
    trackEvento('simulo_precio');
  });
  simInput.addEventListener('input', () => {
    slider.value = simInput.value;
    updateSimMargen(parseFloat(simInput.value) || 0);
  });

  $('#cm-btn-reiniciar').addEventListener('click', () => {
    state.resultado = null;
    document.body.classList.remove('cm-body--wizard');
    showScreen('cm-screen-0');
    setWizardStep(1);
    $$('.cm-input').forEach((inp) => {
      if (inp.name === 'unidad') inp.value = 'kg';
      else if (inp.type === 'number' && inp.name !== 'cantidad_producida' && inp.name !== 'precio_actual') inp.value = '0';
      else if (inp.name !== 'unidad') inp.value = '';
    });
    $('#cm-recs-loading').hidden = false;
    $('#cm-recs-resumen').hidden = true;
    $('#cm-recs-list').hidden = true;
    $('#cm-recs-error').hidden = true;
  });
})();
