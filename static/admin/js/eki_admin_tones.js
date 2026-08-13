/**
 * Apariencia admin eki — Cielo / Marca / Oscuro (keys: manana / tarde / noche).
 * Persistencia: localStorage eki-admin-tone
 */
(function () {
  var KEY = 'eki-admin-tone';
  var TONES = ['manana', 'tarde', 'noche'];
  var LEGACY = {
    cielo: 'manana',
    marca: 'tarde',
    oscuro: 'noche',
    manana: 'manana',
    tarde: 'tarde',
    noche: 'noche',
  };

  function migrateLegacy() {
    try {
      if (!localStorage.getItem(KEY) && localStorage.getItem('eki-mb-tone')) {
        localStorage.setItem(KEY, localStorage.getItem('eki-mb-tone'));
      }
      var cur = localStorage.getItem(KEY);
      if (cur && LEGACY[cur]) {
        localStorage.setItem(KEY, LEGACY[cur]);
      }
    } catch (e) {}
  }

  function markActive(tone) {
    document.querySelectorAll('.eki-tone-btn[data-tone]').forEach(function (btn) {
      var on = btn.getAttribute('data-tone') === tone;
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
      btn.classList.toggle('text-primary-600', on);
      btn.classList.toggle('dark:text-primary-500', on);
    });
  }

  function applyTone(tone) {
    tone = LEGACY[tone] || tone;
    if (TONES.indexOf(tone) < 0) tone = 'tarde';
    document.documentElement.setAttribute('data-eki-tone', tone);
    try {
      localStorage.setItem(KEY, tone);
    } catch (e) {}

    var oscuro = tone === 'noche';
    try {
      if (oscuro) {
        document.documentElement.classList.add('dark');
        document.documentElement.setAttribute('data-theme', 'dark');
      } else {
        document.documentElement.classList.remove('dark');
        document.documentElement.setAttribute('data-theme', 'light');
      }
    } catch (e2) {}

    markActive(tone);
    return tone;
  }

  window.ekiSetAdminTone = applyTone;

  function removeLegacyBar() {
    var bar = document.getElementById('eki-tone-bar');
    if (bar && bar.parentNode) bar.parentNode.removeChild(bar);
  }

  function boot() {
    migrateLegacy();
    removeLegacyBar();
    var saved = 'tarde';
    try {
      saved = localStorage.getItem(KEY) || 'tarde';
      saved = LEGACY[saved] || saved;
    } catch (e) {}
    applyTone(saved);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
