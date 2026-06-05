/**
 * eki admin UI: menú lateral (barra superior) y salto de secciones en formularios acordeón.
 */
(function () {
    'use strict';

    var COLLAPSIBLE_MODELS = ['model-cliente', 'model-estudiante', 'model-curso'];

    function enhancePushmenu() {
        var pushmenu = document.querySelector('[data-widget="pushmenu"]');
        if (!pushmenu) {
            return;
        }
        pushmenu.setAttribute('title', 'Ocultar o mostrar menú lateral');
        pushmenu.setAttribute('aria-label', 'Menú lateral');
        pushmenu.classList.add('eki-pushmenu-btn');
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
            var card = cards[idx];
            var panel = card.querySelector('.panel-collapse');
            if (panel && !panel.classList.contains('show')) {
                var header = card.querySelector('.collapsible-header');
                if (header) {
                    header.click();
                }
            }
            card.scrollIntoView({ behavior: 'smooth', block: 'start' });
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

    onReady(function () {
        enhancePushmenu();
        if (isCollapsibleChangeForm()) {
            initSectionNav();
        }
    });
})();
