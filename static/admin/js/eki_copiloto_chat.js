/**
 * Chat copiloto ops — cajón en el header, no pestaña.
 */
(function () {
  function qs(id) {
    return document.getElementById(id);
  }

  function csrf() {
    var el = document.querySelector('#eki-copiloto-form [name=csrfmiddlewaretoken]');
    if (el && el.value) return el.value;
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  function appendMsg(role, text) {
    var box = qs('eki-copiloto-msgs');
    if (!box) return;
    var div = document.createElement('div');
    div.className = 'eki-copiloto-msg eki-copiloto-msg--' + role;
    div.textContent = text;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
  }

  function openDrawer() {
    var d = qs('eki-copiloto-drawer');
    var btn = qs('eki-copiloto-open');
    if (!d) return;
    d.hidden = false;
    if (btn) btn.setAttribute('aria-expanded', 'true');
    var input = qs('eki-copiloto-input');
    if (input) input.focus();
    var box = qs('eki-copiloto-msgs');
    if (box) box.scrollTop = box.scrollHeight;
  }

  function closeDrawer() {
    var d = qs('eki-copiloto-drawer');
    var btn = qs('eki-copiloto-open');
    if (d) d.hidden = true;
    if (btn) btn.setAttribute('aria-expanded', 'false');
  }

  function ask(pregunta) {
    pregunta = (pregunta || '').trim();
    if (!pregunta) return;
    appendMsg('user', pregunta);
    var input = qs('eki-copiloto-input');
    if (input) input.value = '';
    fetch('/admin/copiloto/ask/', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf(),
      },
      body: JSON.stringify({ pregunta: pregunta }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data && data.ok) {
          appendMsg('assistant', data.respuesta || '');
        } else {
          appendMsg('assistant', (data && data.error) || 'No pude responder.');
        }
      })
      .catch(function () {
        appendMsg('assistant', 'Error de red. Intente de nuevo.');
      });
  }

  function boot() {
    var openBtn = qs('eki-copiloto-open');
    var closeBtn = qs('eki-copiloto-close');
    var form = qs('eki-copiloto-form');
    if (!openBtn || !form) return;
    openBtn.addEventListener('click', function (ev) {
      ev.preventDefault();
      var d = qs('eki-copiloto-drawer');
      if (d && !d.hidden) closeDrawer();
      else openDrawer();
    });
    if (closeBtn) closeBtn.addEventListener('click', closeDrawer);
    form.addEventListener('submit', function (ev) {
      ev.preventDefault();
      ask((qs('eki-copiloto-input') || {}).value);
    });
    document.querySelectorAll('.eki-copiloto-chip').forEach(function (chip) {
      chip.addEventListener('click', function () {
        openDrawer();
        ask(chip.getAttribute('data-q') || chip.textContent);
      });
    });
    var input = qs('eki-copiloto-input');
    if (input) {
      input.addEventListener('keydown', function (ev) {
        if (ev.key === 'Enter' && !ev.shiftKey) {
          ev.preventDefault();
          ask(input.value);
        }
      });
    }
    try {
      if (new URLSearchParams(window.location.search).get('copiloto') === '1') {
        openDrawer();
      }
    } catch (e) { /* ignore */ }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
