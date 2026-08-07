/**
 * Tonos admin eki (mañana / tarde / noche) — en el nav (palette).
 * Persistencia: localStorage eki-admin-tone
 */
(function () {
  var KEY = 'eki-admin-tone';
  var TONES = ['manana', 'tarde', 'noche'];

  function migrateLegacy() {
    try {
      if (!localStorage.getItem(KEY) && localStorage.getItem('eki-mb-tone')) {
        localStorage.setItem(KEY, localStorage.getItem('eki-mb-tone'));
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
    if (TONES.indexOf(tone) < 0) tone = 'tarde';
    document.documentElement.setAttribute('data-eki-tone', tone);
    try {
      localStorage.setItem(KEY, tone);
    } catch (e) {}

    var noche = tone === 'noche';
    try {
      if (noche) {
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
    } catch (e) {}
    applyTone(saved);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
