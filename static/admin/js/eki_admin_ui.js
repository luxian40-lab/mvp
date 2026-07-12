/**
 * eki admin UI: menú lateral (barra superior) y salto de secciones en formularios acordeón.
 */
(function () {
    'use strict';

    var COLLAPSIBLE_MODELS = ['model-cliente', 'model-estudiante', 'model-curso', 'model-modulo'];
    var MODULO_AUTO_OPEN = ['Bloques', 'Microcontenidos'];

    function enhancePushmenu() {
        var pushmenu = document.querySelector('[data-widget="pushmenu"]');
        if (!pushmenu) {
            return;
        }
        pushmenu.setAttribute('title', 'Ocultar o mostrar menú lateral');
        pushmenu.setAttribute('aria-label', 'Menú lateral');
        pushmenu.classList.add('eki-pushmenu-btn');
    }

    function openCollapsibleCard(card, opts) {
        if (!card) {
            return;
        }
        opts = opts || {};
        var panel = card.querySelector('.panel-collapse');
        if (panel && !panel.classList.contains('show')) {
            panel.classList.add('show');
            panel.classList.add('in');
        }
        if (opts.scroll !== false) {
            card.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    function findCardByTitle(title) {
        var collapsible = document.getElementById('jazzy-collapsible');
        if (!collapsible || !title) {
            return null;
        }
        var cards = collapsible.querySelectorAll('.card');
        var needle = title.trim().toLowerCase();
        for (var i = 0; i < cards.length; i++) {
            var titleEl = cards[i].querySelector('.card-title');
            if (titleEl && titleEl.textContent.trim().toLowerCase() === needle) {
                return cards[i];
            }
        }
        return null;
    }

    function findCardByPanelId(panelId) {
        if (!panelId) {
            return null;
        }
        var panel = document.getElementById(panelId.replace(/^#/, ''));
        if (!panel) {
            return null;
        }
        return panel.closest ? panel.closest('.card') : panel.parentElement;
    }

    function initSectionNav() {
        var select = document.getElementById('eki-form-section-select');
        var collapsible = document.getElementById('jazzy-collapsible');
        if (!select || !collapsible) {
            return;
        }

        var cards = collapsible.querySelectorAll('.card');
        cards.forEach(function (card, index) {
            var titleEl = card.querySelector('.card-title');
            if (!titleEl) {
                return;
            }
            var option = document.createElement('option');
            option.value = String(index);
            option.textContent = titleEl.textContent.trim();
            select.appendChild(option);
        });

        select.addEventListener('change', function () {
            var idx = parseInt(select.value, 10);
            if (isNaN(idx) || !cards[idx]) {
                return;
            }
            openCollapsibleCard(cards[idx]);
        });
    }

    function initModuloSectionJumps() {
        if (!document.body.classList.contains('model-modulo')) {
            return;
        }
        MODULO_AUTO_OPEN.forEach(function (title) {
            openCollapsibleCard(findCardByTitle(title), { scroll: false });
        });

        document.querySelectorAll('.eki-modulo-jump a').forEach(function (link) {
            link.addEventListener('click', function (ev) {
                ev.preventDefault();
                var byTitle = findCardByTitle(link.getAttribute('data-eki-open-section'));
                var byHref = findCardByPanelId(link.getAttribute('href'));
                openCollapsibleCard(byTitle || byHref);
            });
        });
    }

    function isCollapsibleChangeForm() {
        if (!document.body.classList.contains('change-form')) {
            return false;
        }
        return COLLAPSIBLE_MODELS.some(function (cls) {
            return document.body.classList.contains(cls);
        });
    }

    function onReady(fn) {
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', fn);
        } else {
            fn();
        }
    }

    function initThemeToggle() {
        var KEY = 'eki-admin-theme';
        var html = document.documentElement;
        var stored = localStorage.getItem(KEY);
        if (stored === 'dark' || (!stored && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
            html.setAttribute('data-eki-theme', 'dark');
        }

        var nav = document.querySelector('.main-header .navbar-nav');
        if (!nav || document.getElementById('eki-theme-toggle')) {
            return;
        }
        var li = document.createElement('li');
        li.className = 'nav-item';
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.id = 'eki-theme-toggle';
        btn.className = 'eki-theme-toggle nav-link';
        btn.setAttribute('title', 'Modo nocturno');
        btn.setAttribute('aria-label', 'Cambiar tema claro/oscuro');
        function label() {
            btn.textContent = html.getAttribute('data-eki-theme') === 'dark' ? '☀' : '🌙';
        }
        label();
        btn.addEventListener('click', function () {
            var dark = html.getAttribute('data-eki-theme') === 'dark';
            if (dark) {
                html.removeAttribute('data-eki-theme');
                localStorage.setItem(KEY, 'light');
            } else {
                html.setAttribute('data-eki-theme', 'dark');
                localStorage.setItem(KEY, 'dark');
            }
            label();
        });
        li.appendChild(btn);
        nav.insertBefore(li, nav.firstChild);
    }

    onReady(function () {
        enhancePushmenu();
        initThemeToggle();
        if (isCollapsibleChangeForm()) {
            initSectionNav();
            initModuloSectionJumps();
        }
    });
})();
