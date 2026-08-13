/**
 * Ecosistema eki — nodos arrastrables + pan + zoom + cables curvos.
 * Posiciones en % del scene; persistencia localStorage.
 */
(function () {
  var STORAGE_KEY = 'eki_eco_layout_v4';
  var DRAG_THRESHOLD = 6;

  function clamp(n, min, max) {
    return Math.max(min, Math.min(max, n));
  }

  function loadLayout() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      if (raw) return JSON.parse(raw);
      var legacy = localStorage.getItem('eki_eco_layout_v2')
        || localStorage.getItem('eki_eco_layout_v1');
      return legacy ? JSON.parse(legacy) : {};
    } catch (e) {
      return {};
    }
  }

  function saveLayout(map) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
    } catch (e) { /* ignore quota */ }
  }

  function curvePath(a, b) {
    var mx = (a.x + b.x) / 2;
    var my = (a.y + b.y) / 2;
    var dx = b.x - a.x;
    var dy = b.y - a.y;
    var len = Math.hypot(dx, dy) || 1;
    // Perpendicular bulge toward centroide (50,50) feel
    var nx = -dy / len;
    var ny = dx / len;
    var bulge = clamp(len * 0.18, 4, 14);
    var cx = mx + nx * bulge;
    var cy = my + ny * bulge;
    return 'M ' + a.x + ' ' + a.y + ' Q ' + cx + ' ' + cy + ' ' + b.x + ' ' + b.y;
  }

  function init(root) {
    var scene = root.querySelector('.eki-panel-eco__scene');
    var svg = root.querySelector('.eki-panel-eco__wires');
    if (!scene || !svg) return;

    var orbs = Array.prototype.slice.call(scene.querySelectorAll('.eki-panel-eco__orb[data-eco-id]'));
    var wires = Array.prototype.slice.call(svg.querySelectorAll('.eki-panel-eco__wire[data-from][data-to]'));
    if (!orbs.length) return;

    var layout = loadLayout();
    var scale = (layout._zoom && typeof layout._zoom === 'number') ? layout._zoom : 1;
    scale = clamp(scale, 0.72, 1.35);

    orbs.forEach(function (orb) {
      var id = orb.getAttribute('data-eco-id');
      if (layout[id] && typeof layout[id].x === 'number' && typeof layout[id].y === 'number') {
        orb.style.left = layout[id].x + '%';
        orb.style.top = layout[id].y + '%';
      }
    });
    if (layout._pan && typeof layout._pan.x === 'number') {
      scene.style.translate = layout._pan.x + 'px ' + (layout._pan.y || 0) + 'px';
    }
    scene.style.setProperty('--eki-eco-zoom', String(scale));

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
        if (line.tagName && line.tagName.toLowerCase() === 'path') {
          line.setAttribute('d', curvePath(a, b));
        } else {
          line.setAttribute('x1', a.x);
          line.setAttribute('y1', a.y);
          line.setAttribute('x2', b.x);
          line.setAttribute('y2', b.y);
        }
      });
    }

    redrawWires();

    var resetBtn = root.querySelector('[data-eco-reset]');
    if (resetBtn) {
      resetBtn.addEventListener('click', function (ev) {
        ev.preventDefault();
        localStorage.removeItem(STORAGE_KEY);
        localStorage.removeItem('eki_eco_layout_v3');
        localStorage.removeItem('eki_eco_layout_v2');
        localStorage.removeItem('eki_eco_layout_v1');
        orbs.forEach(function (orb) {
          var dx = orb.getAttribute('data-eco-x');
          var dy = orb.getAttribute('data-eco-y');
          if (dx != null) orb.style.left = dx + '%';
          if (dy != null) orb.style.top = dy + '%';
        });
        scene.style.translate = '';
        scale = 1;
        scene.style.setProperty('--eki-eco-zoom', '1');
        layout = {};
        redrawWires();
      });
    }

    // Zoom con rueda (Ctrl opcional no requerido — el stage lo captura)
    root.addEventListener('wheel', function (ev) {
      if (!root.contains(ev.target)) return;
      ev.preventDefault();
      var delta = ev.deltaY > 0 ? -0.06 : 0.06;
      scale = clamp(scale + delta, 0.72, 1.35);
      scene.style.setProperty('--eki-eco-zoom', String(scale));
      layout._zoom = scale;
      saveLayout(layout);
    }, { passive: false });

    // Pan del escenario completo (fondo)
    (function bindPan() {
      var panning = false;
      var moved = false;
      var startX = 0;
      var startY = 0;
      var originX = 0;
      var originY = 0;
      var pointerId = null;

      function parsePan() {
        var t = scene.style.translate || '0px 0px';
        var parts = t.replace(/px/g, '').trim().split(/\s+/);
        return { x: parseFloat(parts[0]) || 0, y: parseFloat(parts[1]) || 0 };
      }

      root.addEventListener('pointerdown', function (ev) {
        if (ev.button != null && ev.button !== 0) return;
        if (ev.target.closest && ev.target.closest('.eki-panel-eco__orb')) return;
        if (ev.target.closest && ev.target.closest('[data-eco-reset]')) return;
        panning = true;
        moved = false;
        pointerId = ev.pointerId;
        startX = ev.clientX;
        startY = ev.clientY;
        var p = parsePan();
        originX = p.x;
        originY = p.y;
        root.classList.add('eki-panel-eco__stage--panning');
        scene.classList.add('eki-panel-eco__scene--dragging');
        try { root.setPointerCapture(ev.pointerId); } catch (e) {}
      });

      root.addEventListener('pointermove', function (ev) {
        if (!panning || (pointerId != null && ev.pointerId !== pointerId)) return;
        var dx = ev.clientX - startX;
        var dy = ev.clientY - startY;
        if (!moved && Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
        moved = true;
        ev.preventDefault();
        var nx = clamp(originX + dx, -160, 160);
        var ny = clamp(originY + dy, -110, 110);
        scene.style.translate = nx + 'px ' + ny + 'px';
      });

      function endPan(ev) {
        if (!panning) return;
        if (pointerId != null && ev.pointerId !== pointerId) return;
        panning = false;
        root.classList.remove('eki-panel-eco__stage--panning');
        scene.classList.remove('eki-panel-eco__scene--dragging');
        try { root.releasePointerCapture(ev.pointerId); } catch (e) {}
        if (moved) {
          var p = parsePan();
          layout._pan = { x: p.x, y: p.y };
          saveLayout(layout);
        }
        pointerId = null;
      }
      root.addEventListener('pointerup', endPan);
      root.addEventListener('pointercancel', endPan);
    })();

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
        var nx = clamp(originLeft + (dx / rect.width) * 100, 4, 96);
        var ny = clamp(originTop + (dy / rect.height) * 100, 6, 94);
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
