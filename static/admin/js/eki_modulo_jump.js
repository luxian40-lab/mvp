/**
 * Salto rápido en changeform de Módulo (Unfold).
 * Sticky: Clase · Avanzado (Estructura / Micros / Multimedia / Examen)
 * P0: errores → pestaña correcta + banner.
 * Preferencia: abrir «Clase» por defecto (modo clases / 1 micro).
 */
(function () {
  'use strict';

  var TAB_SLUG = {
    clase: 'clase',
    datos: 'avanzado-datos',
    secciones: 'secciones',
    micro: 'pasos',
    media: 'archivos_multimedia',
    examen: 'preguntas',
  };

  var GROUP_TO_JUMP = [
    { ids: ['pasos-group', 'pasomodulo_set-group'], jump: 'micro', slug: 'pasos' },
    { ids: ['secciones-group', 'seccionmodulo_set-group'], jump: 'secciones', slug: 'secciones' },
    {
      ids: ['archivos_multimedia-group', 'archivomodulo_set-group'],
      jump: 'media',
      slug: 'archivos_multimedia',
    },
    { ids: ['preguntas-group', 'preguntamodulo_set-group'], jump: 'examen', slug: 'preguntas' },
  ];

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

  function findTabSlugByLabel(needle) {
    var lower = needle.toLowerCase();
    var links = document.querySelectorAll('#tabs-items a[href^="#"]');
    for (var i = 0; i < links.length; i++) {
      var t = (links[i].textContent || '').toLowerCase().replace(/\s+/g, ' ').trim();
      if (t.indexOf(lower) !== -1) {
        return (links[i].getAttribute('href') || '').replace(/^#/, '');
      }
    }
    return null;
  }

  function resolveClaseSlug() {
    return (
      findTabSlugByLabel('clase') ||
      findTabSlugByLabel('clase simple') ||
      TAB_SLUG.clase
    );
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
      clase: function () {
        return (
          findFieldsetByTitle('clase') ||
          document.querySelector('#modulo_form') ||
          document.querySelector('form')
        );
      },
      datos: function () {
        return (
          findFieldsetByTitle('avanzado') ||
          findFieldsetByTitle('datos') ||
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
    var slug = TAB_SLUG[key] || 'clase';
    if (key === 'clase') {
      slug = resolveClaseSlug();
    } else if (key === 'datos') {
      slug = findTabSlugByLabel('avanzado · datos') || findTabSlugByLabel('datos') || slug;
    } else if (key === 'secciones') {
      slug = findTabSlugByLabel('estructura') || slug;
    } else if (key === 'micro') {
      slug = findTabSlugByLabel('microcontenidos') || slug;
    } else if (key === 'media') {
      slug = findTabSlugByLabel('multimedia') || slug;
    } else if (key === 'examen') {
      slug = findTabSlugByLabel('mini examen') || findTabSlugByLabel('examen') || slug;
    }
    setUnfoldActiveTab(slug);
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

  function markTabHasError(slug) {
    var link = document.querySelector('#tabs-items a[href="#' + slug + '"]');
    if (!link) {
      return;
    }
    link.classList.add('eki-tab-has-error');
    if (!link.querySelector('.eki-tab-error-dot')) {
      var dot = document.createElement('span');
      dot.className = 'eki-tab-error-dot';
      dot.setAttribute('aria-hidden', 'true');
      link.appendChild(dot);
    }
  }

  function groupContainsError(el) {
    if (!el) {
      return false;
    }
    return !!(
      el.querySelector('.errorlist, .errors, .errornote, .text-red-600, [class*="error"] ul') ||
      el.querySelector('.eki-paso-file-input.errors')
    );
  }

  function focusFirstValidationError() {
    var body = document.body;
    if (!body || body.className.indexOf('model-modulo') === -1) {
      return true;
    }

    var firstError = null;
    var jumpKey = null;
    var slug = null;

    var claseFs = findFieldsetByTitle('clase');
    if (claseFs && groupContainsError(claseFs)) {
      jumpKey = 'clase';
      slug = resolveClaseSlug();
      markTabHasError(slug);
      firstError = claseFs.querySelector('.errorlist, ul.errorlist, .errors') || claseFs;
    }

    for (var i = 0; i < GROUP_TO_JUMP.length; i++) {
      var g = GROUP_TO_JUMP[i];
      var groupEl = null;
      for (var j = 0; j < g.ids.length; j++) {
        groupEl = findById(g.ids[j]);
        if (groupEl) {
          break;
        }
      }
      if (!groupEl) {
        continue;
      }
      var err = groupEl.querySelector('.errorlist, ul.errorlist, .errors');
      if (err || groupContainsError(groupEl)) {
        markTabHasError(g.slug);
        if (!firstError) {
          firstError = err || groupEl;
          jumpKey = g.jump;
          slug = g.slug;
        }
      }
    }

    var pageErrors = document.querySelectorAll(
      '.errornote, .messagelist .error, ul.errorlist'
    );
    if (!jumpKey && pageErrors.length > 0) {
      jumpKey = 'clase';
      slug = resolveClaseSlug();
      markTabHasError(slug);
      firstError = pageErrors[0];
    }

    if (!jumpKey) {
      return true;
    }

    setUnfoldActiveTab(slug || resolveClaseSlug());
    window.setTimeout(function () {
      var target = firstError || resolveTarget(jumpKey);
      if (!target) {
        return;
      }
      target.scrollIntoView({ behavior: 'smooth', block: 'center' });
      try {
        var input = target.closest('.form-row, .inline-related, fieldset');
        var focusable = input && input.querySelector('input, select, textarea');
        if (focusable && typeof focusable.focus === 'function') {
          focusable.focus({ preventScroll: true });
        }
      } catch (e) { /* ignore */ }
    }, 80);
    return false;
  }

  function openDefaultTab() {
    var prefs = document.getElementById('eki-modulo-prefs');
    var prefer = !prefs || prefs.getAttribute('data-prefer-simple') !== '0';
    if (!prefer) {
      return;
    }
    setUnfoldActiveTab(resolveClaseSlug());
  }

  function buildErrorBanner() {
    var body = document.body;
    if (!body || body.className.indexOf('model-modulo') === -1) {
      return;
    }
    if (document.getElementById('eki-modulo-error-banner')) {
      return;
    }

    var texts = [];
    var seen = {};
    function addText(t) {
      t = (t || '').replace(/\s+/g, ' ').trim();
      if (!t || seen[t]) {
        return;
      }
      if (/^corrija\b/i.test(t) && t.length < 40) {
        return;
      }
      seen[t] = true;
      texts.push(t);
    }

    document.querySelectorAll('.errornote, .messagelist .error, ul.errorlist li, .errorlist li').forEach(
      function (el) {
        addText(el.textContent);
      }
    );

    if (!texts.length) {
      return;
    }

    var banner = document.createElement('div');
    banner.id = 'eki-modulo-error-banner';
    banner.className = 'eki-modulo-error-banner';
    banner.setAttribute('role', 'alert');
    var html =
      '<strong>No se pudo guardar.</strong> Detalle:' +
      '<ul>';
    for (var i = 0; i < texts.length && i < 8; i++) {
      html += '<li>' + texts[i].replace(/</g, '&lt;') + '</li>';
    }
    html += '</ul>';
    banner.innerHTML = html;

    var mount =
      document.querySelector('#content-main') ||
      document.querySelector('main') ||
      document.querySelector('#content') ||
      document.body;
    var jump = document.getElementById('eki-modulo-jump');
    if (jump && jump.parentNode === mount) {
      mount.insertBefore(banner, jump.nextSibling);
    } else {
      mount.insertBefore(banner, mount.firstChild);
    }
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
      '<button type="button" data-jump="clase" class="eki-modulo-jump__btn eki-modulo-jump__btn--primary">Clase</button>' +
      '<button type="button" data-jump="secciones" class="eki-modulo-jump__btn">Estructura</button>' +
      '<button type="button" data-jump="micro" class="eki-modulo-jump__btn">Materiales</button>' +
      '<button type="button" data-jump="media" class="eki-modulo-jump__btn">Media</button>' +
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

  ready(function () {
    buildNav();
    var noErrors = focusFirstValidationError();
    if (noErrors !== false) {
      openDefaultTab();
    }
    buildErrorBanner();
  });
})();
