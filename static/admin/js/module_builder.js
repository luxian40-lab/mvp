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
      if (el.type === 'radio' && !el.checked) return;
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

  function markStatus(label, isDirty) {
    if (typeof setDirtyState === 'function') setDirtyState(label, !!isDirty);
  }

  function revertSortable(evt) {
    if (!evt || !evt.from || !evt.item || evt.oldIndex == null) return;
    var parent = evt.from;
    var item = evt.item;
    parent.removeChild(item);
    var ref = parent.children[evt.oldIndex];
    if (ref) parent.insertBefore(item, ref);
    else parent.appendChild(item);
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
      if (el.type === 'radio') {
        if (el.checked) body.set(el.name, el.value);
        return;
      }
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

    function finishSave(err) {
      shell.classList.remove('is-saving');
      shell.removeAttribute('aria-busy');
      shell.querySelectorAll('.eki-mb-save-one').forEach(function (btn) {
        btn.disabled = false;
      });
      if (err) setState(err.message || 'No se pudo guardar', true);
      else setState('Guardado', false);
    }

    function runSave(options) {
      shell.classList.add('is-saving');
      shell.setAttribute('aria-busy', 'true');
      setState('Guardando…', true);
      postSave(shell, options)
        .then(function (data) {
          if (data && data.ok === false) {
            throw new Error(data.error || 'No se pudo guardar');
          }
          finishSave(null);
        })
        .catch(finishSave);
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
        runSave({ action: 'save_modulo', pasoId: pid });
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
          if (evt.oldIndex === evt.newIndex) return;
          var orden = idsFromList(sectionsWrap, 'data-seccion').join(',');
          var run = function () {
            markStatus('Guardando orden…', true);
            postReorder(shell, 'reorder_secciones', { orden: orden })
              .then(function (data) {
                applyOrdenFromResponse(data);
                markStatus('Orden guardado', false);
              })
              .catch(function () {
                revertSortable(evt);
                markStatus('No se guardó el orden. Volvió al lugar anterior.', true);
              });
          };
          if (!dirty) {
            run();
            return;
          }
          markStatus('Guardando cambios y luego el orden…', true);
          postSave(shell, { action: 'save_modulo' })
            .then(function () {
              markStatus('Guardado', false);
              run();
            })
            .catch(function () {
              revertSortable(evt);
              markStatus('No se pudieron guardar los cambios. El bloque volvió a su sitio.', true);
            });
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
        onEnd: function (evt) {
          if (evt.oldIndex === evt.newIndex) return;
          var sid = list.getAttribute('data-seccion');
          var orden = idsFromList(list, 'data-paso').join(',');
          var run = function () {
            markStatus('Guardando orden…', true);
            postReorder(shell, 'reorder_micros', { seccion_id: sid, orden: orden })
              .then(function (data) {
                applyOrdenFromResponse(data);
                markStatus('Orden guardado', false);
              })
              .catch(function () {
                revertSortable(evt);
                markStatus('No se guardó el orden. El paso volvió a su sitio.', true);
              });
          };
          if (!dirty) {
            run();
            return;
          }
          markStatus('Guardando cambios y luego el orden…', true);
          postSave(shell, { action: 'save_modulo' })
            .then(function () {
              markStatus('Guardado', false);
              run();
            })
            .catch(function () {
              revertSortable(evt);
              markStatus('No se pudieron guardar los cambios. El paso volvió a su sitio.', true);
            });
        },
      });
    });
  }

  function applyEncodeRows(shell, pasos) {
    (pasos || []).forEach(function (p) {
      var row = shell.querySelector('.eki-mb__row[data-paso="' + p.id + '"]');
      if (!row) return;
      var badge = row.querySelector('.eki-mb__badge--warn, .eki-mb__badge--bad, .eki-mb__badge--ok');
      if (!badge) return;
      if (p.status === 'pending' || p.status === 'running') {
        badge.className = 'eki-mb__badge eki-mb__badge--warn';
        badge.textContent = 'Procesando video…';
        return;
      }
      if (p.status === 'error') {
        badge.className = 'eki-mb__badge eki-mb__badge--bad';
        badge.textContent = 'Video no apto para WhatsApp';
        return;
      }
      if (p.media_wa_apto === true || (p.media_url && !p.status)) {
        badge.className = 'eki-mb__badge eki-mb__badge--ok';
        badge.textContent = 'Listo para WhatsApp';
      }
    });
  }

  function fetchEncodeStatus(shell) {
    var body = new URLSearchParams();
    body.set('action', 'encode_status');
    body.set('ajax', '1');
    body.set('csrfmiddlewaretoken', csrfToken());
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
    })
      .then(parseJsonResponse)
      .then(function (data) {
        applyEncodeRows(shell, data && data.pasos);
        return data;
      });
  }

  function initEncodePoll(shell) {
    shell.querySelectorAll('.eki-mb-refresh-state').forEach(function (btn) {
      btn.addEventListener('click', function () {
        markStatus('Actualizando video…', false);
        fetchEncodeStatus(shell)
          .then(function () {
            markStatus('Estado del video actualizado', false);
          })
          .catch(function () {
            markStatus('No se pudo leer el estado del video', true);
          });
      });
    });
    if (!shell.querySelector('.eki-mb__badge--warn')) return;
    var polls = 0;
    var timer = window.setInterval(function () {
      polls += 1;
      if (polls > 12 || !shell.querySelector('.eki-mb__badge--warn')) {
        window.clearInterval(timer);
        return;
      }
      fetchEncodeStatus(shell).catch(function () {});
    }, 20000);
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
            var row = document.getElementById('paso-' + data.paso_id);
            if (row) {
              var preview = row.querySelector('.eki-mb__row-preview--muted');
              if (preview) preview.hidden = true;
            }
            var edit = document.querySelector(
              '.eki-mb__row-edit[data-paso-edit="' + data.paso_id + '"]'
            );
            if (edit) {
              edit.querySelectorAll(
                '.eki-mb__thumb, .eki-mb__media-url, .eki-mb-delete-media'
              ).forEach(function (el) {
                el.hidden = true;
              });
              var clear = edit.querySelector('[name$="_clear_media"]');
              if (clear) {
                clear.checked = false;
                var lab = clear.closest('label');
                if (lab) lab.hidden = true;
              }
            }
            markStatus('Archivo quitado. El texto se conserva.', false);
          })
          .catch(function (err) {
            markStatus(err.message || 'No se pudo quitar el archivo.', true);
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
