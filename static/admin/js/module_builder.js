/**
 * Module Builder WA — drag, guardar módulo, estado dirty, panel lateral.
 */
(function () {
  var dirty = false;
  var setDirtyState = null;
  var syncCalendarioHidden = null;

  var GENERAL_MODULO_FIELDS = {
    modulo_descripcion: 1,
    modulo_modo_entrega: 1,
    modulo_duracion_dias: 1,
    modulo_habilitado_desde: 1,
    modulo_facilitador_checkpoint: 1,
    modulo_publicado_wa: 1,
    modulo_examen_obligatorio: 1,
    modulo_puntaje_minimo_aprobacion: 1,
  };

  function readCalendarioPostValue() {
    var fecha = document.getElementById('eki-mb-habilitado-fecha');
    var hora = document.getElementById('eki-mb-habilitado-hora');
    var hidden = document.getElementById('eki-mb-habilitado');
    if (!fecha || !hidden) return '';
    var f = (fecha.value || '').trim();
    if (!f) {
      hidden.value = '';
      return '';
    }
    if (hora) hora.disabled = false;
    var h = (hora && hora.value ? hora.value : '08:00').trim().slice(0, 5);
    if (!h) h = '08:00';
    var combined = f + 'T' + h;
    hidden.value = combined;
    return combined;
  }

  function ensureCalendarioSynced() {
    if (typeof syncCalendarioHidden === 'function') {
      syncCalendarioHidden();
      return;
    }
    readCalendarioPostValue();
  }

  function csrfToken() {
    var el = document.getElementById('eki-mb-csrf') || document.querySelector('[name=csrfmiddlewaretoken]');
    if (el && el.value) return el.value;
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  function appendBuilderFieldsToParams(shell, body, options) {
    options = options || {};
    var includeModuloTitulo = options.includeModuloTitulo !== false;
    var includeSecciones = options.includeSecciones !== false;
    var includeConfigGeneral = options.includeConfigGeneral !== false;
    var includePasos = options.includePasos !== false;
    var pasoId = options.pasoId ? String(options.pasoId) : '';
    ensureCalendarioSynced();
    shell.querySelectorAll('[name^="modulo_"], [name^="seccion_"], [name^="paso_"]').forEach(function (el) {
      if (el.type === 'file' || !el.name) return;
      if (el.name === 'modulo_titulo' && !includeModuloTitulo) return;
      if (GENERAL_MODULO_FIELDS[el.name] && !includeConfigGeneral) return;
      if (el.name.indexOf('seccion_') === 0 && !includeSecciones) return;
      if (el.name.indexOf('paso_') === 0) {
        if (!includePasos) return;
        if (pasoId) {
          var m = el.name.match(/^paso_(\d+)_/);
          if (!m || m[1] !== pasoId) return;
        }
      }
      if (el.type === 'checkbox') {
        body.set(el.name, el.checked ? el.value || '1' : '0');
      } else {
        body.set(el.name, el.value);
      }
    });
  }

  function appendBuilderFieldsToForm(shell, form, options) {
    if (!form || !shell) return;
    form.querySelectorAll('input[data-eki-mb-draft-clone]').forEach(function (n) {
      n.remove();
    });
    var body = new URLSearchParams();
    appendBuilderFieldsToParams(shell, body, options);
    body.forEach(function (value, name) {
      var hidden = document.createElement('input');
      hidden.type = 'hidden';
      hidden.name = name;
      hidden.value = value;
      hidden.setAttribute('data-eki-mb-draft-clone', '1');
      form.appendChild(hidden);
    });
  }

  function postReorder(shell, action, fields) {
    var body = new URLSearchParams();
    body.set('action', action);
    body.set('ajax', '1');
    body.set('csrfmiddlewaretoken', csrfToken());
    if (document.getElementById('eki-mb-builder-flag')) {
      body.set('builder', '1');
    }
    appendBuilderFieldsToParams(shell, body, {
      includeModuloTitulo: false,
      includeConfigGeneral: false,
    });
    Object.keys(fields).forEach(function (k) {
      body.set(k, fields[k]);
    });
    return fetch(window.location.pathname + window.location.search, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': csrfToken(),
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
      credentials: 'same-origin',
      body: body.toString(),
    }).then(parseJsonResponse);
  }

  function applyOrdenFromResponse(data) {
    if (!data || !data.orden) return;
    Object.keys(data.orden).forEach(function (pid) {
      var row = document.querySelector('.eki-mb__row[data-paso="' + pid + '"]');
      if (!row) return;
      var num = row.querySelector('.eki-mb__step-num');
      if (num) num.textContent = String(data.orden[pid]);
    });
  }

  function idsFromList(listEl, attr) {
    return Array.prototype.map
      .call(listEl.querySelectorAll(':scope > [' + attr + ']'), function (n) {
        return n.getAttribute(attr);
      })
      .filter(Boolean);
  }

  function collectPasoFields(shell, body, pasoId) {
    var prefix = pasoId ? 'paso_' + pasoId + '_' : 'paso_';
    shell.querySelectorAll('[name^="' + prefix + '"]').forEach(function (el) {
      if (el.type === 'checkbox') {
        body.set(el.name, el.checked ? el.value || '1' : '0');
      } else if (el.type !== 'file') {
        body.set(el.name, el.value);
      }
    });
  }

  function collectSaveFields(shell, body, options) {
    options = options || {};
    var calendario = readCalendarioPostValue();
    shell.querySelectorAll('[name^="modulo_"], [name^="seccion_"]').forEach(function (el) {
      if (el.name === 'modulo_habilitado_desde') return;
      if (el.type === 'checkbox') {
        body.set(el.name, el.checked ? el.value || '1' : '0');
      } else if (el.type !== 'file' && el.name) {
        body.set(el.name, el.value);
      }
    });
    body.set('modulo_habilitado_desde', calendario);
    collectPasoFields(shell, body, options.pasoId || null);
  }

  function submitSaveForm(shell, options) {
    options = options || {};
    ensureCalendarioSynced();
    var form = document.createElement('form');
    form.method = 'POST';
    form.action = window.location.pathname + window.location.search;
    form.style.display = 'none';
    document.body.appendChild(form);

    function addField(name, value) {
      var inp = document.createElement('input');
      inp.type = 'hidden';
      inp.name = name;
      inp.value = value == null ? '' : String(value);
      form.appendChild(inp);
    }

    addField('csrfmiddlewaretoken', csrfToken());
    addField('action', options.action || 'save_modulo');
    if (document.getElementById('eki-mb-builder-flag')) {
      addField('builder', '1');
    }
    if (options.pasoId) {
      addField('paso_id', String(options.pasoId));
    }

    var body = new URLSearchParams();
    collectSaveFields(shell, body, options);
    body.forEach(function (value, name) {
      addField(name, value);
    });
    form.submit();
  }

  function parseJsonResponse(r) {
    return r.text().then(function (text) {
      if (!text) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return {};
      }
      if (text.charAt(0) === '<') {
        throw new Error(
          'Sesión expirada o respuesta HTML. Recargue (Ctrl+F5) e inicie sesión de nuevo.'
        );
      }
      var data;
      try {
        data = JSON.parse(text);
      } catch (e) {
        throw new Error(
          'Respuesta inválida del servidor. Recargue (Ctrl+F5) e intente de nuevo.'
        );
      }
      if (!r.ok) {
        throw new Error((data && data.error) || 'HTTP ' + r.status);
      }
      return data;
    });
  }

  function postSave(shell, options) {
    options = options || {};
    var body = new URLSearchParams();
    body.set('action', options.action || 'save_modulo');
    body.set('ajax', '1');
    body.set('csrfmiddlewaretoken', csrfToken());
    if (document.getElementById('eki-mb-builder-flag')) {
      body.set('builder', '1');
    }
    if (options.pasoId) {
      body.set('paso_id', String(options.pasoId));
    }
    collectSaveFields(shell, body, options);
    return fetch(window.location.pathname + window.location.search, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': csrfToken(),
        Accept: 'application/json',
        'X-Requested-With': 'XMLHttpRequest',
      },
      credentials: 'same-origin',
      body: body.toString(),
    }).then(parseJsonResponse);
  }

  function initUploadDraftPreserve(shell) {
    shell
      .querySelectorAll('.eki-mb__add-micro, .eki-mb__upload-replace, .eki-mb__add-sec, .eki-mb__inline-form')
      .forEach(function (form) {
        form.addEventListener('submit', function (ev) {
          if (form.dataset.ekiMbBypass === '1') {
            return;
          }
          if (dirty) {
            ev.preventDefault();
            if (
              !window.confirm(
                'Hay cambios sin guardar. Se guardarán junto con esta acción. ¿Continuar?'
              )
            ) {
              return;
            }
          }
          var draftOpts = {
            includeModuloTitulo: false,
            includeConfigGeneral: !!dirty,
          };
          var pasoField = form.querySelector('input[name="paso_id"]');
          if (pasoField && pasoField.value && form.classList.contains('eki-mb__upload-replace')) {
            draftOpts.pasoId = pasoField.value;
            draftOpts.includeSecciones = false;
          }
          appendBuilderFieldsToForm(shell, form, draftOpts);
          if (draftOpts.includeConfigGeneral) {
            var pg = document.createElement('input');
            pg.type = 'hidden';
            pg.name = 'persist_general';
            pg.value = '1';
            pg.setAttribute('data-eki-mb-draft-clone', '1');
            form.appendChild(pg);
          }
          if (dirty) {
            form.dataset.ekiMbBypass = '1';
            form.submit();
          }
        });
      });
  }

  function initDirty(shell) {
    var stateEls = [
      document.getElementById('eki-mb-save-state'),
      document.getElementById('eki-mb-save-state-top'),
    ].filter(Boolean);
    var saveBtns = shell.querySelectorAll('.eki-mb-save-trigger');
    var pubLink = document.getElementById('eki-mb-publicar');

    function setState(label, isDirty) {
      dirty = !!isDirty;
      shell.dataset.ekiMbDirty = dirty ? '1' : '0';
      stateEls.forEach(function (el) {
        el.textContent = label;
      });
      saveBtns.forEach(function (btn) {
        btn.disabled = !dirty && label === 'Guardado';
      });
      if (pubLink) {
        if (dirty) pubLink.classList.add('eki-mb-sticky__pub--disabled');
        else pubLink.classList.remove('eki-mb-sticky__pub--disabled');
      }
    }
    setDirtyState = setState;

    shell.querySelectorAll('.eki-mb-track-dirty').forEach(function (el) {
      el.addEventListener('input', function () {
        setState('Sin guardar', true);
      });
      el.addEventListener('change', function () {
        setState('Sin guardar', true);
      });
    });

    shell.querySelectorAll('.eki-mb__activo-check').forEach(function (el) {
      el.addEventListener('change', function () {
        var edit = el.closest('.eki-mb__row-edit');
        var hint = edit ? edit.querySelector('.eki-mb__activo-hint') : null;
        if (!hint) return;
        if (el.checked) {
          var contenido = edit.querySelector('[name$="_contenido"]');
          var hasMedia = edit.querySelector('.eki-mb__media-url');
          var cVal = contenido ? contenido.value.trim() : '';
          hint.hidden = !!(cVal || hasMedia);
        } else {
          hint.hidden = true;
        }
      });
    });

    window.addEventListener('beforeunload', function (e) {
      if (!dirty) return;
      e.preventDefault();
      e.returnValue = '';
    });

    function runSave(options) {
      ensureCalendarioSynced();
      shell.classList.add('is-saving');
      shell.setAttribute('aria-busy', 'true');
      setState('Guardando…', true);
      submitSaveForm(shell, options);
    }

    saveBtns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        runSave({ action: 'save_modulo' });
      });
    });

    shell.querySelectorAll('.eki-mb-save-one').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var pid = btn.getAttribute('data-paso-id');
        if (!pid) return;
        btn.disabled = true;
        submitSaveForm(shell, { action: 'save_modulo', pasoId: pid });
      });
    });

    setState('Sin cambios', false);
  }

  function initProbLinks(shell) {
    shell.querySelectorAll('.eki-mb__prob-link').forEach(function (a) {
      a.addEventListener('click', function (ev) {
        var target = document.querySelector(a.getAttribute('href'));
        if (!target) return;
        ev.preventDefault();
        target.classList.add('eki-mb__row--highlight');
        target.scrollIntoView({ behavior: 'smooth', block: 'center' });
        setTimeout(function () {
          target.classList.remove('eki-mb__row--highlight');
        }, 2200);
      });
    });
  }

  function initDrag(shell) {
    if (typeof Sortable === 'undefined') return;

    var sectionsWrap = shell.querySelector('#eki-mb-sections');
    if (sectionsWrap) {
      Sortable.create(sectionsWrap, {
        animation: 160,
        handle: '.eki-mb__drag-handle--sec',
        draggable: '.eki-mb__sec',
        ghostClass: 'eki-mb__sec--ghost',
        onEnd: function (evt) {
          var orden = idsFromList(sectionsWrap, 'data-seccion').join(',');
          var doReorder = function () {
            postReorder(shell, 'reorder_secciones', { orden: orden })
              .then(function (data) {
                applyOrdenFromResponse(data);
                if (setDirtyState) setDirtyState('Orden guardado', false);
              })
              .catch(function () {
                window.alert('No se pudo guardar el orden. Recargue la página.');
                window.location.reload();
              });
          };
          if (!dirty) {
            doReorder();
            return;
          }
          if (
            !window.confirm(
              'Hay cambios sin guardar. Se guardarán al reordenar. ¿Continuar?'
            )
          ) {
            window.location.reload();
            return;
          }
          doReorder();
        },
      });
    }

    shell.querySelectorAll('.eki-mb__list[data-seccion]').forEach(function (list) {
      Sortable.create(list, {
        animation: 140,
        handle: '.eki-mb__drag-handle--micro',
        draggable: '.eki-mb__row[data-paso]',
        ghostClass: 'sortable-ghost',
        group: { name: 'mb-sec-' + list.getAttribute('data-seccion'), pull: false, put: false },
        onEnd: function () {
          var sid = list.getAttribute('data-seccion');
          var orden = idsFromList(list, 'data-paso').join(',');
          var doReorder = function () {
            postReorder(shell, 'reorder_micros', { seccion_id: sid, orden: orden })
              .then(function (data) {
                applyOrdenFromResponse(data);
                if (setDirtyState) setDirtyState('Orden guardado', false);
              })
              .catch(function () {
                window.alert('No se pudo guardar el orden. Recargue la página.');
                window.location.reload();
              });
          };
          if (!dirty) {
            doReorder();
            return;
          }
          if (
            !window.confirm(
              'Hay cambios sin guardar. Se guardarán al reordenar. ¿Continuar?'
            )
          ) {
            window.location.reload();
            return;
          }
          doReorder();
        },
      });
    });
  }

  function initEncodePoll(shell) {
    shell.querySelectorAll('.eki-mb-refresh-state').forEach(function (btn) {
      btn.addEventListener('click', function () {
        window.location.reload();
      });
    });
    var processing = shell.querySelector('.eki-mb__badge--warn');
    if (!processing || processing.textContent.indexOf('Procesando') === -1) return;
    var polls = 0;
    var maxPolls = 8;
    var timer = window.setInterval(function () {
      polls += 1;
      if (polls >= maxPolls) {
        window.clearInterval(timer);
        return;
      }
      window.location.reload();
    }, 45000);
  }

  function updateWaPreview(editEl) {
    if (!editEl) return;
    var preview = editEl.querySelector('[data-wa-preview]');
    if (!preview) return;
    var titulo = editEl.querySelector('[name$="_titulo"]');
    var contenido = editEl.querySelector('[name$="_contenido"]');
    var stepType = editEl.getAttribute('data-step-type') || '';
    if (!stepType) {
      var pasoId = editEl.getAttribute('data-paso-edit');
      var row = pasoId
        ? document.querySelector('.eki-mb__row[data-paso="' + pasoId + '"]')
        : null;
      stepType = row ? row.getAttribute('data-step-type') || '' : '';
    }
    var tEl = preview.querySelector('.eki-mb-wa-preview__titulo');
    var bEl = preview.querySelector('.eki-mb-wa-preview__body');
    var tVal = titulo ? titulo.value.trim() : '';
    var cVal = contenido ? contenido.value.trim() : '';
    if (tEl) tEl.textContent = tVal || '(sin título)';
    if (bEl) bEl.textContent = cVal || '';
    if (stepType === 'mensaje' || cVal) {
      preview.hidden = false;
    } else if (stepType === 'video' || stepType === 'lectura') {
      preview.hidden = false;
      if (bEl && !cVal) {
        bEl.textContent =
          stepType === 'video'
            ? 'El estudiante recibirá el video en WhatsApp.'
            : 'Contenido de lectura / archivo en el curso.';
      }
    } else {
      preview.hidden = true;
    }
  }

  function syncRowPreview(shell, pasoId) {
    var edit = shell.querySelector('[data-paso-edit="' + pasoId + '"]');
    var row = shell.querySelector('[data-paso="' + pasoId + '"]');
    if (!edit || !row) return;
    var preview = row.querySelector('.eki-mb__row-preview');
    if (!preview) return;
    var contenido = edit.querySelector('[name$="_contenido"]');
    var cVal = contenido ? contenido.value.trim() : '';
    if (cVal) {
      preview.textContent = cVal.length > 100 ? cVal.slice(0, 100) + '…' : cVal;
      preview.classList.remove('eki-mb__row-preview--muted');
    }
  }

  function selectPaso(shell, pasoId) {
    var placeholder = document.getElementById('eki-mb-panel-placeholder');
    shell.querySelectorAll('.eki-mb__row--selected').forEach(function (r) {
      r.classList.remove('eki-mb__row--selected');
    });
    shell.querySelectorAll('.eki-mb__row-edit.is-panel-active').forEach(function (el) {
      el.classList.remove('is-panel-active');
    });
    var row = shell.querySelector('[data-paso="' + pasoId + '"]');
    if (!row) return;
    var edit = shell.querySelector('[data-paso-edit="' + pasoId + '"]');
    if (!edit) return;
    row.classList.add('eki-mb__row--selected');
    edit.classList.add('is-panel-active');
    if (placeholder) placeholder.hidden = true;
    updateWaPreview(edit);
    var panel = document.getElementById('eki-mb-panel');
    if (panel && window.matchMedia('(max-width: 960px)').matches) {
      panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    try {
      window.sessionStorage.setItem('eki-mb-selected', String(pasoId));
    } catch (e) {}
    row.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function initStepPanel(shell) {
    var panel = document.getElementById('eki-mb-panel');
    if (!panel) return;

    shell.querySelectorAll('[data-paso-select]').forEach(function (btn) {
      btn.addEventListener('click', function (ev) {
        ev.preventDefault();
        var pid = btn.getAttribute('data-paso-select');
        if (pid) selectPaso(shell, pid);
      });
    });

    shell.querySelectorAll('.eki-mb__row-edit').forEach(function (edit) {
      var pid = edit.getAttribute('data-paso-edit');
      edit.querySelectorAll('.eki-mb-preview-src, [name$="_contenido"], [name$="_titulo"]').forEach(function (inp) {
        inp.addEventListener('input', function () {
          if (edit.classList.contains('is-panel-active')) {
            updateWaPreview(edit);
            if (pid) syncRowPreview(shell, pid);
          }
        });
      });
    });

    var first = shell.querySelector('[data-paso-select]');
    var saved = null;
    try {
      saved = window.sessionStorage.getItem('eki-mb-selected');
    } catch (e) {}
    if (saved && shell.querySelector('[data-paso="' + saved + '"]')) {
      selectPaso(shell, saved);
    } else if (first) {
      selectPaso(shell, first.getAttribute('data-paso-select'));
    }
  }

  function initCalendarioGlobal(shell) {
    var fecha = document.getElementById('eki-mb-habilitado-fecha');
    var hora = document.getElementById('eki-mb-habilitado-hora');
    var hidden = document.getElementById('eki-mb-habilitado');
    var clearBtn = document.getElementById('eki-mb-habilitado-clear');
    if (!fecha || !hora || !hidden) return;

    function syncHidden() {
      readCalendarioPostValue();
    }

    function clearCalendario() {
      fecha.value = '';
      hora.value = '08:00';
      hora.disabled = true;
      hidden.value = '';
      if (typeof setDirtyState === 'function') {
        setDirtyState('Sin guardar', true);
      }
      fecha.dispatchEvent(new Event('change', { bubbles: true }));
    }

    if (hidden.value && hidden.value.indexOf('T') > 0) {
      var parts = hidden.value.split('T');
      fecha.value = parts[0] || '';
      hora.value = (parts[1] || '08:00').slice(0, 5);
    } else if (fecha.value) {
      readCalendarioPostValue();
    } else {
      if (!hora.value) hora.value = '08:00';
      hidden.value = '';
    }
    hora.disabled = !fecha.value;

    syncCalendarioHidden = syncHidden;

    fecha.addEventListener('change', function () {
      syncHidden();
      if (typeof setDirtyState === 'function') setDirtyState('Sin guardar', true);
    });
    fecha.addEventListener('input', function () {
      syncHidden();
      if (typeof setDirtyState === 'function') setDirtyState('Sin guardar', true);
    });
    hora.addEventListener('change', function () {
      syncHidden();
      if (typeof setDirtyState === 'function') setDirtyState('Sin guardar', true);
    });
    hora.addEventListener('input', function () {
      syncHidden();
      if (typeof setDirtyState === 'function') setDirtyState('Sin guardar', true);
    });
    if (clearBtn) {
      clearBtn.addEventListener('click', clearCalendario);
    }
    syncHidden();
  }

  function initDeleteMedia(shell) {
    shell.querySelectorAll('.eki-mb-delete-media').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var pasoId = btn.getAttribute('data-paso-id');
        if (!pasoId) return;
        if (!window.confirm('¿Quitar este archivo del paso? El texto se conserva.')) {
          return;
        }
        var body = new URLSearchParams();
        body.set('action', 'delete_media');
        body.set('ajax', '1');
        body.set('paso_id', pasoId);
        body.set('csrfmiddlewaretoken', csrfToken());
        if (document.getElementById('eki-mb-builder-flag')) {
          body.set('builder', '1');
        }
        fetch(window.location.pathname + window.location.search, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': csrfToken(),
            Accept: 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
          },
          credentials: 'same-origin',
          body: body.toString(),
        })
          .then(parseJsonResponse)
          .then(function (data) {
            if (!data || !data.ok) {
              throw new Error((data && data.error) || 'No se pudo quitar el archivo.');
            }
            window.location.reload();
          })
          .catch(function (err) {
            window.alert(err.message || 'No se pudo quitar el archivo.');
          });
      });
    });
  }

  function boot() {
    var shell = document.getElementById('eki-mb-shell') || document.querySelector('.eki-mb-shell');
    if (!shell) return;
    initDrag(shell);
    initDirty(shell);
    initCalendarioGlobal(shell);
    initProbLinks(shell);
    initEncodePoll(shell);
    initStepPanel(shell);
    initUploadDraftPreserve(shell);
    initDeleteMedia(shell);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
