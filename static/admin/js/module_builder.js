/**
 * Module Builder WA — drag, guardar módulo, estado dirty, scroll a problemas.
 */
(function () {
  function csrfToken() {
    var el = document.querySelector('[name=csrfmiddlewaretoken]');
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

  function initDirty(shell) {
    var stateEl = document.getElementById('eki-mb-save-state');
    var saveBtn = document.getElementById('eki-mb-save-all');
    var pubLink = document.getElementById('eki-mb-publicar');
    var dirty = false;

    function setState(label, isDirty) {
      dirty = !!isDirty;
      if (stateEl) stateEl.textContent = label;
      if (saveBtn) saveBtn.disabled = !dirty && label === 'Guardado';
      if (pubLink && dirty) pubLink.classList.add('eki-mb-sticky__pub--disabled');
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

    if (saveBtn) {
      saveBtn.addEventListener('click', function () {
        setState('Guardando…', false);
        var body = new URLSearchParams();
        body.set('action', 'save_modulo');
        body.set('csrfmiddlewaretoken', csrfToken());
        if (shell.querySelector('[name=builder]')) {
          body.set('builder', '1');
        }
        shell.querySelectorAll('[name^="paso_"]').forEach(function (el) {
          if (el.type === 'checkbox') {
            if (el.checked) body.set(el.name, el.value || '1');
          } else if (el.type !== 'file') {
            body.set(el.name, el.value);
          }
        });
        fetch(window.location.pathname + window.location.search, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': csrfToken(),
          },
          credentials: 'same-origin',
          body: body.toString(),
        })
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
      });
    }

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

  function boot() {
    var shell = document.getElementById('eki-mb-shell') || document.querySelector('.eki-mb-shell');
    if (!shell) return;
    initDrag(shell);
    initDirty(shell);
    initProbLinks(shell);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
