(function () {
    function urls() {
        var nodo = document.getElementById('eki-alta-urls');
        if (!nodo) return null;
        try { return JSON.parse(nodo.textContent); } catch (e) { return null; }
    }

    function iniciales(nombre) {
        var partes = (nombre || '').trim().split(/\s+/).filter(Boolean);
        if (!partes.length) return '?';
        if (partes.length === 1) return partes[0].slice(0, 1).toUpperCase();
        return (partes[0].slice(0, 1) + partes[1].slice(0, 1)).toUpperCase();
    }

    function texto(id, valor) {
        var nodo = document.getElementById(id);
        if (nodo) nodo.textContent = valor || 'Sin dato';
    }

    function cursosMarcados() {
        return Array.prototype.map.call(
            document.querySelectorAll('input[name="cursos_a_inscribir"]:checked'),
            function (input) { return input.value; }
        );
    }

    function nombresCursos() {
        var nombres = Array.prototype.map.call(
            document.querySelectorAll('input[name="cursos_a_inscribir"]:checked'),
            function (input) {
                var carta = input.closest('.eki-curso-card');
                var nombre = carta && carta.querySelector('.eki-curso-nombre');
                return nombre ? nombre.textContent : '';
            }
        ).filter(Boolean);
        return nombres.length ? nombres.join(', ') : 'Sin curso por ahora';
    }

    function pintarPanel(data) {
        if (!data) return;
        texto('eki-alta-org', data.organizacion || 'Sin organización');
        texto('eki-alta-plan', data.plan || 'Sin plan');
        document.body.dataset.ekiDrip = data.drip ? '1' : '0';
        var cupo = document.getElementById('eki-alta-cupo');
        if (cupo) cupo.hidden = !(data.aviso_cupo && cursosMarcados().length);
        if (!data.drip) {
            var general = document.querySelector('a[href="#general"]');
            if (general && document.body.__x) general.click();
        }
        var grupo = document.getElementById('id_grupo');
        if (grupo && data.grupos) {
            var actual = grupo.value;
            grupo.innerHTML = '<option value="">Seleccione un grupo</option>';
            data.grupos.forEach(function (fila) {
                var opcion = document.createElement('option');
                opcion.value = fila.id;
                opcion.textContent = fila.label;
                if (String(fila.id) === String(actual)) opcion.selected = true;
                grupo.appendChild(opcion);
            });
        }
        texto('eki-alta-cursos', nombresCursos());
    }

    function refrescar() {
        var cfg = urls();
        var cliente = document.getElementById('id_cliente');
        if (!cfg || !cliente) return;
        var antes = cursosMarcados();
        var grupo = document.getElementById('id_grupo');
        var params = new URLSearchParams();
        params.set('cliente', cliente.value || '');
        params.set('grupo', grupo ? grupo.value : '');
        antes.forEach(function (id) { params.append('cursos', id); });
        fetch(cfg.contexto + '?' + params.toString(), { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var caja = document.querySelector('[data-eki-cursos]');
                if (caja && data.html) {
                    var padre = caja.parentNode;
                    var envoltorio = document.createElement('div');
                    envoltorio.innerHTML = data.html;
                    var nuevo = envoltorio.firstElementChild;
                    padre.replaceChild(nuevo, caja);
                    engancharCursos();
                }
                var quedan = cursosMarcados();
                var aviso = document.getElementById('eki-alta-quito');
                if (aviso) aviso.hidden = quedan.length >= antes.length;
                pintarPanel(data);
            })
            .catch(function () {});
    }

    function engancharCursos() {
        document.querySelectorAll('input[name="cursos_a_inscribir"]').forEach(function (input) {
            input.addEventListener('change', function () {
                texto('eki-alta-cursos', nombresCursos());
                var cupo = document.getElementById('eki-alta-cupo');
                var plan = document.getElementById('eki-alta-plan');
                if (cupo && plan) {
                    cupo.hidden = !(cursosMarcados().length && plan.textContent.indexOf('OP3') === -1 && plan.textContent !== 'Sin plan');
                }
            });
        });
        var ninguno = document.querySelector('.eki-curso-ninguno');
        if (ninguno) {
            ninguno.addEventListener('click', function () {
                document.querySelectorAll('input[name="cursos_a_inscribir"]').forEach(function (input) {
                    input.checked = false;
                });
                texto('eki-alta-cursos', 'Sin curso por ahora');
                var cupo = document.getElementById('eki-alta-cupo');
                if (cupo) cupo.hidden = true;
            });
        }
        var buscar = document.querySelector('.eki-cursos-buscar');
        if (buscar) {
            buscar.addEventListener('input', function () {
                var q = buscar.value.toLowerCase();
                document.querySelectorAll('.eki-curso-card').forEach(function (carta) {
                    carta.hidden = q && carta.textContent.toLowerCase().indexOf(q) === -1;
                });
            });
        }
    }

    function avisarDocumento() {
        var cfg = urls();
        var campo = document.getElementById('id_cedula');
        if (!cfg || !campo) return;
        var params = new URLSearchParams();
        params.set('numero', campo.value || '');
        if (cfg.excluir) params.set('excluir', cfg.excluir);
        fetch(cfg.documento + '?' + params.toString(), { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                var previo = document.getElementById('eki-aviso-documento');
                if (previo) previo.remove();
                if (!data.existe) return;
                var aviso = document.createElement('p');
                aviso.id = 'eki-aviso-documento';
                aviso.className = 'eki-alta-quito';
                aviso.innerHTML = 'Ese documento ya está: ' + data.nombre + ' · ' + data.organizacion + '. ';
                var enlace = document.createElement('a');
                enlace.href = data.url;
                enlace.textContent = 'Abrir ficha';
                aviso.appendChild(enlace);
                campo.insertAdjacentElement('afterend', aviso);
            })
            .catch(function () {});
    }

    function avisarTelefono() {
        var cfg = urls();
        var campo = document.getElementById('id_telefono');
        if (!cfg || !campo) return;
        var params = new URLSearchParams();
        params.set('telefono', campo.value || '');
        if (cfg.excluir) params.set('excluir', cfg.excluir);
        fetch(cfg.telefono + '?' + params.toString(), { credentials: 'same-origin' })
            .then(function (r) { return r.json(); })
            .then(function (data) {
                texto('eki-alta-telefono', data.formato || 'Sin dato');
                var previo = document.getElementById('eki-aviso-telefono');
                if (previo) previo.remove();
                if (!data.existe) return;
                var aviso = document.createElement('p');
                aviso.id = 'eki-aviso-telefono';
                aviso.className = 'eki-alta-quito';
                aviso.textContent = 'Ese teléfono ya está: ' + data.nombre + ' · ' + data.organizacion + '.';
                campo.insertAdjacentElement('afterend', aviso);
            })
            .catch(function () {});
    }

    function arrancar() {
        if (window.django && django.jQuery && django.jQuery.fn.select2) {
            django.jQuery.fn.select2.defaults.set('language', {
                errorLoading: function () { return 'No se pudo cargar.'; },
                inputTooShort: function () { return 'Escriba para buscar'; },
                noResults: function () { return 'Sin resultados'; },
                searching: function () { return 'Buscando…'; }
            });
            django.jQuery(document).on('select2:open', function () {
                var campo = document.querySelector('.select2-container--open .select2-search__field');
                if (campo && !campo.getAttribute('placeholder')) {
                    campo.setAttribute('placeholder', 'Escriba para buscar');
                }
            });
        }
        var cliente = document.getElementById('id_cliente');
        if (cliente && window.django && django.jQuery) {
            django.jQuery(cliente).on('change', refrescar);
        } else if (cliente) {
            cliente.addEventListener('change', refrescar);
        }
        var grupo = document.getElementById('id_grupo');
        if (grupo) grupo.addEventListener('change', refrescar);
        var nombre = document.getElementById('id_nombre');
        if (nombre) {
            nombre.addEventListener('input', function () {
                texto('eki-alta-nombre', nombre.value || 'Sin dato');
                texto('eki-alta-iniciales', iniciales(nombre.value));
            });
        }
        var cedula = document.getElementById('id_cedula');
        if (cedula) cedula.addEventListener('input', avisarDocumento);
        var telefono = document.getElementById('id_telefono');
        if (telefono) telefono.addEventListener('input', avisarTelefono);
        engancharCursos();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', arrancar);
    } else {
        arrancar();
    }
})();
