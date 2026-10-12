(function () {
  function iniciar() {
  var raiz = document.getElementById('eki-cm');
  if (!raiz) return;

  var personas = document.getElementById('eki-cm-personas');
  var grupos = document.getElementById('eki-cm-grupos');
  var inputPersonas = document.getElementById('id_personas_ids');
  var inputGrupos = document.getElementById('id_grupos_ids');
  var inputReglas = document.getElementById('id_reglas_json');
  var timer = null;

  function idsDe(contenedor) {
    if (!contenedor) return [];
    return Array.prototype.map.call(contenedor.querySelectorAll('[data-id]'), function (nodo) {
      return nodo.getAttribute('data-id');
    });
  }

  function escribirOcultos() {
    if (inputPersonas && personas) inputPersonas.value = idsDe(personas).join(',');
    if (inputGrupos && grupos) inputGrupos.value = idsDe(grupos).join(',');
    if (inputReglas) inputReglas.value = JSON.stringify(leerReglas());
  }

  function leerReglas() {
    var reglas = {};
    raiz.querySelectorAll('.eki-cm-var').forEach(function (fila) {
      var n = fila.getAttribute('data-n');
      var origen = fila.querySelector('[data-origen]').value;
      var si = fila.querySelector('[data-si-falta]').value;
      var texto = fila.querySelector('[data-texto]').value;
      reglas[n] = {
        origen: origen,
        si_falta: si,
        respaldo: origen === 'fijo' ? '' : texto,
        texto: origen === 'fijo' ? texto : ''
      };
    });
    return reglas;
  }

  function chip(contenedor, id, etiqueta, tipo) {
    if (contenedor.querySelector('[data-id="' + id + '"]')) return;
    var nodo = document.createElement('span');
    nodo.className = 'eki-cm-chip';
    nodo.setAttribute('data-id', id);
    nodo.appendChild(document.createTextNode(etiqueta + ' '));
    var boton = document.createElement('button');
    boton.type = 'button';
    boton.setAttribute('data-quitar', tipo);
    boton.textContent = 'Quitar';
    nodo.appendChild(boton);
    contenedor.appendChild(nodo);
  }

  function pintarConteo(resumen) {
    if (!resumen) return;
    Object.keys(resumen).forEach(function (clave) {
      raiz.querySelectorAll('[data-k="' + clave + '"]').forEach(function (nodo) {
        nodo.textContent = resumen[clave];
      });
    });
    var lado = raiz.querySelector('[data-k="reciben-side"]');
    if (lado) lado.textContent = resumen.reciben;
    var oculto = raiz.querySelector('[data-k="reciben-input"]');
    if (oculto) oculto.value = resumen.reciben;
    var texto = document.getElementById('eki-cm-confirmacion');
    if (texto && resumen.confirmacion) texto.textContent = resumen.confirmacion;
  }

  function programarGuardado() {
    escribirOcultos();
    if (!raiz.getAttribute('data-autoguardar')) return;
    window.clearTimeout(timer);
    timer = window.setTimeout(guardar, 500);
  }

  function guardar() {
    var url = raiz.getAttribute('data-autoguardar');
    if (!url) return;
    var datos = new FormData();
    var token = document.querySelector('[name=csrfmiddlewaretoken]');
    if (token) datos.append('csrfmiddlewaretoken', token.value);
    ['nombre', 'cliente', 'plantilla', 'phone_number_id', 'fecha_programada', 'dias_repeticion', 'personas_ids', 'grupos_ids', 'reglas_json'].forEach(function (nombre) {
      var campo = document.getElementById('id_' + nombre);
      if (campo) datos.append(nombre, campo.value);
    });
    fetch(url, { method: 'POST', body: datos, credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (cuerpo) {
        if (!cuerpo || !cuerpo.ok) return;
        pintarConteo(cuerpo.resumen);
        var confirmacion = document.getElementById('eki-cm-confirmacion');
        if (confirmacion) confirmacion.textContent = cuerpo.confirmacion || '';
        if (cuerpo.previa) {
          var cuerpoPrev = raiz.querySelector('[data-preview="cuerpo"]');
          if (cuerpoPrev) cuerpoPrev.textContent = cuerpo.previa.cuerpo || '';
          var persona = raiz.querySelector('[data-preview="persona"]');
          if (persona) persona.textContent = cuerpo.previa.persona || '';
        }
      })
      .catch(function () {});
  }

  function buscar(url, q, lista, tipo, contenedor) {
    var cliente = document.getElementById('id_cliente');
    var params = new URLSearchParams();
    params.set('q', q);
    if (cliente && cliente.value) params.set('cliente', cliente.value);
    fetch(url + '?' + params.toString(), { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (cuerpo) {
        lista.innerHTML = '';
        (cuerpo.resultados || []).forEach(function (fila) {
          var item = document.createElement('li');
          var boton = document.createElement('button');
          boton.type = 'button';
          boton.textContent = fila.etiqueta;
          boton.addEventListener('click', function () {
            chip(contenedor, String(fila.id), fila.etiqueta, tipo);
            lista.hidden = true;
            programarGuardado();
          });
          item.appendChild(boton);
          lista.appendChild(item);
        });
        var filas = cuerpo.resultados || [];
        if (!filas.length) {
          var vacio = document.createElement('li');
          vacio.textContent = tipo === 'grupo' ? 'Ningún grupo coincide.' : 'Nadie coincide.';
          lista.appendChild(vacio);
        }
        lista.hidden = false;
      })
      .catch(function () {
        lista.innerHTML = '';
        var fallo = document.createElement('li');
        fallo.textContent = 'No se pudo buscar.';
        lista.appendChild(fallo);
        lista.hidden = false;
      });
  }

  function engancharBusqueda(inputId, listaId, url, tipo, contenedor) {
    var input = document.getElementById(inputId);
    var lista = document.getElementById(listaId);
    if (!input || !lista || !url) return;
    var espera = null;
    input.addEventListener('keydown', function (evento) {
      if (evento.key === 'Enter') evento.preventDefault();
    });
    input.addEventListener('input', function () {
      window.clearTimeout(espera);
      var q = input.value.trim();
      if (q.length < 2) {
        lista.hidden = true;
        return;
      }
      espera = window.setTimeout(function () {
        buscar(url, q, lista, tipo, contenedor);
      }, 200);
    });
  }

  raiz.addEventListener('click', function (evento) {
    var boton = evento.target.closest('[data-quitar]');
    if (!boton) return;
    var chipNodo = boton.closest('[data-id]');
    if (chipNodo) chipNodo.remove();
    programarGuardado();
  });

  raiz.addEventListener('change', function (evento) {
    if (evento.target.closest('.eki-cm-var') || evento.target.id === 'id_plantilla' || evento.target.id === 'id_dias_repeticion' || evento.target.id === 'id_phone_number_id' || evento.target.id === 'id_fecha_programada') {
      if (evento.target.id === 'id_plantilla') reconstruirVariables();
      programarGuardado();
    }
  });

  function reconstruirVariables() {
    var select = document.getElementById('id_plantilla');
    var caja = document.getElementById('eki-cm-variables');
    if (!select || !caja || !select.value) return;
    var base = raiz.getAttribute('data-variables').replace('/0/', '/' + select.value + '/');
    fetch(base, { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (cuerpo) {
        caja.innerHTML = '';
        var reglas = cuerpo.reglas || {};
        Object.keys(reglas).forEach(function (numero) {
          var regla = reglas[numero];
          var fila = document.createElement('div');
          fila.className = 'eki-cm-var';
          fila.setAttribute('data-n', numero);
          fila.innerHTML = '<span>Variable ' + numero + '</span>';
          fila.appendChild(selector('Origen', 'data-origen', [
            ['nombre', 'Nombre'],
            ['organizacion', 'Organización'],
            ['curso', 'Curso'],
            ['fijo', 'Texto fijo']
          ], regla.origen));
          fila.appendChild(selector('Si falta', 'data-si-falta', [
            ['respaldo', 'Usar un texto de respaldo'],
            ['excluir', 'Excluir a la persona']
          ], regla.si_falta));
          var label = document.createElement('label');
          label.appendChild(document.createTextNode('Texto fijo o de respaldo'));
          var input = document.createElement('input');
          input.type = 'text';
          input.setAttribute('data-texto', '');
          input.value = regla.origen === 'fijo' ? (regla.texto || '') : (regla.respaldo || '');
          label.appendChild(input);
          fila.appendChild(label);
          caja.appendChild(fila);
        });
        programarGuardado();
      })
      .catch(function () {});
  }

  function selector(titulo, attr, opciones, actual) {
    var label = document.createElement('label');
    label.appendChild(document.createTextNode(titulo));
    var select = document.createElement('select');
    select.setAttribute(attr, '');
    opciones.forEach(function (par) {
      var opcion = document.createElement('option');
      opcion.value = par[0];
      opcion.textContent = par[1];
      if (par[0] === actual) opcion.selected = true;
      select.appendChild(opcion);
    });
    label.appendChild(select);
    return label;
  }

  engancharBusqueda('eki-cm-grupo-q', 'eki-cm-grupo-opciones', raiz.getAttribute('data-buscar-grupos'), 'grupo', grupos);
  engancharBusqueda('eki-cm-persona-q', 'eki-cm-persona-opciones', raiz.getAttribute('data-buscar-personas'), 'persona', personas);

  var abrir = document.getElementById('eki-cm-abrir-envio');
  var dialog = document.getElementById('eki-cm-dialog');
  var cerrar = document.getElementById('eki-cm-cerrar');
  if (abrir && dialog) abrir.addEventListener('click', function () { dialog.showModal(); });
  if (cerrar && dialog) cerrar.addEventListener('click', function () { dialog.close(); });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', iniciar);
  } else {
    iniciar();
  }
})();
