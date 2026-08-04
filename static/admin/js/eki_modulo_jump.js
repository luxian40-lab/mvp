/**
 * Salto rápido en changeform de Módulo (Unfold).
 * Sticky: Datos · Estructura · Microcontenidos · Multimedia · Examen
 * Con inlines en pestañas Unfold, activa Alpine `activeTab` antes de scrollear.
 */
(function () {
  'use strict';

  var TAB_SLUG = {
    datos: 'general',
    secciones: 'secciones',
    micro: 'pasos',
    media: 'archivos_multimedia',
    examen: 'preguntas',
  };

  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  function findById(id) {
    return document.getElementById(id);
  }

  function findFieldsetByTitle(needle) {
    var lower = needle.toLowerCase();
    var nodes = document.querySelectorAll('fieldset, .aligned, [class*="fieldset"]');
    for (var i = 0; i < nodes.length; i++) {
      var h = nodes[i].querySelector('h2, legend, summary, .fieldset-heading');
      if (h && h.textContent && h.textContent.toLowerCase().indexOf(lower) !== -1) {
        return nodes[i];
      }
    }
    return null;
  }

  function setUnfoldActiveTab(slug) {
    if (!slug) {
      return;
    }
    try {
      var stack = document.body && document.body._x_dataStack;
      if (stack && stack[0] && typeof stack[0].activeTab !== 'undefined') {
        stack[0].activeTab = slug;
      }
    } catch (e) { /* ignore */ }
    var link = document.querySelector('#tabs-items a[href="#' + slug + '"]');
    if (link) {
      link.click();
    }
  }

  function resolveTarget(key) {
    var map = {
      datos: function () {
        return (
          findFieldsetByTitle('datos') ||
          findFieldsetByTitle('informacion del modulo') ||
          findFieldsetByTitle('información del módulo') ||
          document.querySelector('#modulo_form') ||
          document.querySelector('form')
        );
      },
      secciones: function () {
        return findById('secciones-group') || findById('seccionmodulo_set-group');
      },
      micro: function () {
        return findById('pasos-group') || findById('pasomodulo_set-group');
      },
      media: function () {
        return (
          findById('archivos_multimedia-group') || findById('archivomodulo_set-group')
        );
      },
      examen: function () {
        return (
          findById('preguntas-group') ||
          findById('preguntamodulo_set-group') ||
          findFieldsetByTitle('examen')
        );
      },
    };
    return map[key] ? map[key]() : null;
  }

  function jumpTo(key) {
    setUnfoldActiveTab(TAB_SLUG[key] || 'general');
    window.setTimeout(function () {
      var el = resolveTarget(key);
      if (!el) {
        return;
      }
      if (!el.id) {
        el.id = 'eki-jump-' + key;
      }
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
      try {
        history.replaceState(null, '', '#' + el.id);
      } catch (e) { /* ignore */ }
    }, 40);
  }

  function buildNav() {
    if (document.getElementById('eki-modulo-jump')) {
      return;
    }
    var body = document.body;
    if (!body || body.className.indexOf('model-modulo') === -1) {
      return;
    }
    if (body.className.indexOf('change-form') === -1 && body.className.indexOf('changeform') === -1) {
      if (!document.querySelector('#modulo_form, form')) {
        return;
      }
    }

    var bar = document.createElement('nav');
    bar.id = 'eki-modulo-jump';
    bar.className = 'eki-modulo-jump';
    bar.setAttribute('aria-label', 'Ir a sección del módulo');
    bar.innerHTML =
      '<span class="eki-modulo-jump__label">Ir a</span>' +
      '<button type="button" data-jump="datos" class="eki-modulo-jump__btn">Datos</button>' +
      '<button type="button" data-jump="secciones" class="eki-modulo-jump__btn">Estructura</button>' +
      '<button type="button" data-jump="micro" class="eki-modulo-jump__btn">Microcontenidos</button>' +
      '<button type="button" data-jump="media" class="eki-modulo-jump__btn">Multimedia</button>' +
      '<button type="button" data-jump="examen" class="eki-modulo-jump__btn">Examen</button>';

    bar.addEventListener('click', function (ev) {
      var btn = ev.target.closest('[data-jump]');
      if (!btn) {
        return;
      }
      ev.preventDefault();
      jumpTo(btn.getAttribute('data-jump'));
    });

    var mount =
      document.querySelector('#content-main') ||
      document.querySelector('main') ||
      document.querySelector('#content') ||
      document.body;
    mount.insertBefore(bar, mount.firstChild);

    [
      'secciones-group',
      'pasos-group',
      'archivos_multimedia-group',
      'preguntas-group',
      'seccionmodulo_set-group',
      'pasomodulo_set-group',
      'archivomodulo_set-group',
      'preguntamodulo_set-group',
    ].forEach(function (id) {
      var el = findById(id);
      if (el) {
        el.style.scrollMarginTop = '72px';
      }
    });
  }

  ready(buildNav);
})();
