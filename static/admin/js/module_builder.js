/**
 * Module Builder WA — drag, guardar módulo, estado dirty, scroll a problemas.
 */
(function () {
  function csrfToken() {
    var el = document.getElementById('eki-mb-csrf') || document.querySelector('[name=csrfmiddlewaretoken]');
    if (el && el.value) return el.value;
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  function postReorder(action, fields) {
    var body = new URLSearchParams();
    body.set('action', action);
    body.set('csrfmiddlewaretoken', csrfToken());
    Object.keys(fields).forEach(function (k) {
      body.set(k, fields[k]);
    });
    return fetch(window.location.pathname + window.location.search, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': csrfToken(),
      },
      credentials: 'same-origin',
      body: body.toString(),
    }).then(function (r) {
      if (r.redirected || r.ok) {
        window.location.reload();
        return;
      }
      throw new Error('HTTP ' + r.status);
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
        if (el.checked) body.set(el.name, el.value || '1');
      } else if (el.type !== 'file') {
        body.set(el.name, el.value);
      }
    });
  }

  function postSave(shell, options) {
    options = options || {};
    var body = new URLSearchParams();
    body.set('action', options.action || 'save_modulo');
    body.set('csrfmiddlewaretoken', csrfToken());
    if (document.getElementById('eki-mb-builder-flag')) {
      body.set('builder', '1');
    }
    if (options.pasoId) {
      body.set('paso_id', String(options.pasoId));
      collectPasoFields(shell, body, options.pasoId);
    } else {
      collectPasoFields(shell, body, null);
    }
    return fetch(window.location.pathname + window.location.search, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': csrfToken(),
      },
      credentials: 'same-origin',
      body: body.toString(),
    });
  }

  function initDirty(shell) {
    var stateEls = [
      document.getElementById('eki-mb-save-state'),
      document.getElementById('eki-mb-save-state-top'),
    ].filter(Boolean);
    var saveBtns = shell.querySelectorAll('.eki-mb-save-trigger');
    var pubLink = document.getElementById('eki-mb-publicar');
    var dirty = false;

    function setState(label, isDirty) {
      dirty = !!isDirty;
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

    shell.querySelectorAll('.eki-mb-track-dirty').forEach(function (el) {
      el.addEventListener('input', function () {
        setState('Sin guardar', true);
      });
      el.addEventListener('change', function () {
        setState('Sin guardar', true);
      });
    });

    window.addEventListener('beforeunload', function (e) {
      if (!dirty) return;
      e.preventDefault();
      e.returnValue = '';
    });

    function runSave(options) {
      setState('Guardando…', false);
      postSave(shell, options)
        .then(function (r) {
          if (r.redirected) {
            window.location.href = r.url;
            return;
          }
          if (r.ok) {
            window.location.reload();
            return;
          }
          throw new Error('HTTP ' + r.status);
        })
        .catch(function () {
          setState('Error al guardar', true);
          window.alert('No se pudo guardar. Reintente.');
        });
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
        postSave(shell, { action: 'save_modulo', pasoId: pid })
          .then(function (r) {
            if (r.redirected) {
              window.location.href = r.url;
              return;
            }
            if (r.ok) {
              window.location.reload();
              return;
            }
            throw new Error('HTTP ' + r.status);
          })
          .catch(function () {
            btn.disabled = false;
            window.alert('No se pudo guardar este micro. Reintente.');
          });
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
        onEnd: function () {
          var orden = idsFromList(sectionsWrap, 'data-seccion').join(',');
          postReorder('reorder_secciones', { orden: orden }).catch(function () {
            window.location.reload();
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
        onEnd: function () {
          var sid = list.getAttribute('data-seccion');
          var orden = idsFromList(list, 'data-paso').join(',');
          postReorder('reorder_micros', { seccion_id: sid, orden: orden }).catch(function () {
            window.location.reload();
          });
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

  function boot() {
    var shell = document.getElementById('eki-mb-shell') || document.querySelector('.eki-mb-shell');
    if (!shell) return;
    initDrag(shell);
    initDirty(shell);
    initProbLinks(shell);
    initEncodePoll(shell);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
