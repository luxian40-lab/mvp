/**
 * Module Builder WA — drag con rieles (SortableJS).
 * Tonos = admin completo (eki_admin_tones.js).
 * Riel: micros no cruzan de sección; secciones se reordenan enteras.
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
    var shell = document.querySelector('.eki-mb-shell');
    if (!shell) return;
    initDrag(shell);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
