/**
 * Ecosistema eki — nodos arrastrables con aristas en vivo.
 * Posiciones en % del scene; persistencia localStorage por usuario.
 */
(function () {
  var STORAGE_KEY = 'eki_eco_layout_v1';
  var DRAG_THRESHOLD = 6;

  function clamp(n, min, max) {
    return Math.max(min, Math.min(max, n));
  }

  function loadLayout() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : {};
    } catch (e) {
      return {};
    }
  }

  function saveLayout(map) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
    } catch (e) { /* ignore quota */ }
  }

  function init(root) {
    var scene = root.querySelector('.eki-panel-eco__scene');
    var svg = root.querySelector('.eki-panel-eco__wires');
    if (!scene || !svg) return;

    var orbs = Array.prototype.slice.call(scene.querySelectorAll('.eki-panel-eco__orb[data-eco-id]'));
    var wires = Array.prototype.slice.call(svg.querySelectorAll('.eki-panel-eco__wire[data-from][data-to]'));
    if (!orbs.length) return;

    var layout = loadLayout();
    orbs.forEach(function (orb) {
      var id = orb.getAttribute('data-eco-id');
      if (layout[id] && typeof layout[id].x === 'number' && typeof layout[id].y === 'number') {
        orb.style.left = layout[id].x + '%';
        orb.style.top = layout[id].y + '%';
      }
    });

    function posOf(id) {
      var el = scene.querySelector('.eki-panel-eco__orb[data-eco-id="' + id + '"]');
      if (!el) return null;
      return {
        x: parseFloat(el.style.left) || 50,
        y: parseFloat(el.style.top) || 50,
      };
    }

    function redrawWires() {
      wires.forEach(function (line) {
        var a = posOf(line.getAttribute('data-from'));
        var b = posOf(line.getAttribute('data-to'));
        if (!a || !b) return;
        line.setAttribute('x1', a.x);
        line.setAttribute('y1', a.y);
        line.setAttribute('x2', b.x);
        line.setAttribute('y2', b.y);
      });
    }

    redrawWires();

    var resetBtn = root.querySelector('[data-eco-reset]');
    if (resetBtn) {
      resetBtn.addEventListener('click', function (ev) {
        ev.preventDefault();
        localStorage.removeItem(STORAGE_KEY);
        orbs.forEach(function (orb) {
          var dx = orb.getAttribute('data-eco-x');
          var dy = orb.getAttribute('data-eco-y');
          if (dx != null) orb.style.left = dx + '%';
          if (dy != null) orb.style.top = dy + '%';
        });
        redrawWires();
      });
    }

    orbs.forEach(function (orb) {
      var dragging = false;
      var moved = false;
      var startX = 0;
      var startY = 0;
      var originLeft = 0;
      var originTop = 0;
      var pointerId = null;

      function onPointerDown(ev) {
        if (ev.button != null && ev.button !== 0) return;
        dragging = true;
        moved = false;
        pointerId = ev.pointerId;
        startX = ev.clientX;
        startY = ev.clientY;
        originLeft = parseFloat(orb.style.left) || 50;
        originTop = parseFloat(orb.style.top) || 50;
        scene.classList.add('eki-panel-eco__scene--dragging');
        orb.classList.add('eki-panel-eco__orb--dragging');
        try {
          orb.setPointerCapture(ev.pointerId);
        } catch (e) { /* older browsers */ }
      }

      function onPointerMove(ev) {
        if (!dragging || (pointerId != null && ev.pointerId !== pointerId)) return;
        var dx = ev.clientX - startX;
        var dy = ev.clientY - startY;
        if (!moved && Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
        moved = true;
        ev.preventDefault();
        var rect = scene.getBoundingClientRect();
        if (!rect.width || !rect.height) return;
        var nx = clamp(originLeft + (dx / rect.width) * 100, 6, 94);
        var ny = clamp(originTop + (dy / rect.height) * 100, 8, 92);
        orb.style.left = nx + '%';
        orb.style.top = ny + '%';
        redrawWires();
      }

      function onPointerUp(ev) {
        if (!dragging) return;
        if (pointerId != null && ev.pointerId !== pointerId) return;
        dragging = false;
        scene.classList.remove('eki-panel-eco__scene--dragging');
        orb.classList.remove('eki-panel-eco__orb--dragging');
        try {
          orb.releasePointerCapture(ev.pointerId);
        } catch (e) { /* ignore */ }
        if (moved) {
          var id = orb.getAttribute('data-eco-id');
          layout[id] = {
            x: parseFloat(orb.style.left) || 50,
            y: parseFloat(orb.style.top) || 50,
          };
          saveLayout(layout);
        }
        pointerId = null;
      }

      function onClick(ev) {
        if (moved) {
          ev.preventDefault();
          ev.stopPropagation();
          moved = false;
        }
      }

      orb.addEventListener('pointerdown', onPointerDown);
      orb.addEventListener('pointermove', onPointerMove);
      orb.addEventListener('pointerup', onPointerUp);
      orb.addEventListener('pointercancel', onPointerUp);
      orb.addEventListener('click', onClick, true);
    });
  }

  function boot() {
    var roots = document.querySelectorAll('[data-eki-eco-graph]');
    Array.prototype.forEach.call(roots, init);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
