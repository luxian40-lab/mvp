/*
 * Subida con progreso. No importa el constructor de módulos ni el admin.
 * Emite upload:progress, upload:done, upload:error y upload:cancel
 * sobre el elemento objetivo.
 */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.EkiMediaUploader = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  var activos = 0;

  function avisarSalida(e) {
    if (!activos) return;
    e.preventDefault();
    e.returnValue = '';
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('beforeunload', avisarSalida);
  }

  function emitir(objetivo, nombre, detalle) {
    if (!objetivo || !objetivo.dispatchEvent) return;
    objetivo.dispatchEvent(new CustomEvent(nombre, { detail: detalle, bubbles: true }));
  }

  function mb(bytes) {
    return (Number(bytes) / (1024 * 1024)).toFixed(1);
  }

  function textoProgreso(loaded, total, inicio) {
    var pct = total ? Math.round((loaded / total) * 100) : 0;
    var trans = (Date.now() - inicio) / 1000;
    var resta = '';
    if (loaded > 0 && total > loaded && trans > 0.4) {
      var vel = loaded / trans;
      var seg = Math.round((total - loaded) / vel);
      resta = seg < 60 ? seg + ' s restantes' : Math.ceil(seg / 60) + ' min restantes';
    }
    return {
      porcentaje: pct,
      texto: mb(loaded) + ' de ' + mb(total) + ' MB' + (resta ? '. ' + resta : ''),
    };
  }

  function crear(opciones) {
    opciones = opciones || {};
    var objetivo = opciones.objetivo;
    var colaMax = opciones.colaMax || 2;
    var cola = [];
    var corriendo = 0;
    var trabajos = {};
    var seq = 0;

    function fila(trabajo) {
      if (!objetivo || !objetivo.querySelector) return null;
      var item = objetivo.querySelector('[data-mu-id="' + trabajo.id + '"]');
      if (item) return item;
      item = document.createElement('div');
      item.className = 'eki-mu__item';
      item.setAttribute('data-mu-id', String(trabajo.id));
      item.innerHTML =
        '<p class="eki-mu__nombre"></p>' +
        '<div class="eki-mu__barra" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><span></span></div>' +
        '<p class="eki-mu__texto" aria-live="polite"></p>' +
        '<div class="eki-mu__acciones">' +
        '<button type="button" class="eki-mu__btn" data-mu-cancelar>Cancelar</button>' +
        '<button type="button" class="eki-mu__btn" data-mu-reintentar hidden>Reintentar</button>' +
        '</div>';
      item.querySelector('.eki-mu__nombre').textContent = trabajo.archivo.name;
      item.querySelector('[data-mu-cancelar]').addEventListener('click', function () { cancelar(trabajo.id); });
      item.querySelector('[data-mu-reintentar]').addEventListener('click', function () { reintentar(trabajo.id); });
      objetivo.appendChild(item);
      return item;
    }

    function pintar(trabajo, campos) {
      var item = fila(trabajo);
      if (item) {
        var barra = item.querySelector('[role="progressbar"]');
        var texto = item.querySelector('.eki-mu__texto');
        if (texto) texto.textContent = (campos.etapa || '') + '. ' + (campos.texto || '');
        if (barra) {
          if (campos.porcentaje == null) {
            barra.removeAttribute('aria-valuenow');
          } else {
            barra.setAttribute('aria-valuenow', String(campos.porcentaje));
            var span = barra.querySelector('span');
            if (span) span.style.width = campos.porcentaje + '%';
          }
        }
      }
      emitir(objetivo, 'upload:progress', Object.assign({ id: trabajo.id, archivo: trabajo.archivo.name }, campos));
    }

    function validar(archivo) {
      if (typeof opciones.validar === 'function') return opciones.validar(archivo) || '';
      return '';
    }

    function terminar(trabajo, evento, detalle) {
      corriendo = Math.max(0, corriendo - 1);
      activos = Math.max(0, activos - 1);
      trabajo.estado = evento === 'upload:done' ? 'listo' : evento === 'upload:cancel' ? 'cancelado' : 'error';
      if (objetivo && objetivo.querySelector) {
        var item = objetivo.querySelector('[data-mu-id="' + trabajo.id + '"]');
        if (item) {
          var re = item.querySelector('[data-mu-reintentar]');
          var ca = item.querySelector('[data-mu-cancelar]');
          if (re) re.hidden = evento === 'upload:done';
          if (ca) ca.hidden = true;
          var texto = item.querySelector('.eki-mu__texto');
          if (texto && detalle && detalle.error) texto.textContent = detalle.error;
          if (texto && evento === 'upload:done') {
            var motivo = detalle && detalle.motivo ? detalle.motivo : '';
            texto.textContent = motivo ? 'Listo. ' + motivo : 'Listo.';
          }
        }
      }
      emitir(objetivo, evento, Object.assign({ id: trabajo.id, archivo: trabajo.archivo.name }, detalle || {}));
      bombear();
    }

    function enviar(trabajo) {
      var archivo = trabajo.archivo;
      var errorLocal = validar(archivo);
      if (errorLocal) {
        corriendo = Math.max(0, corriendo - 1);
        activos = Math.max(0, activos - 1);
        trabajo.estado = 'error';
        emitir(objetivo, 'upload:error', { id: trabajo.id, archivo: archivo.name, error: errorLocal });
        bombear();
        return;
      }
      var xhr = new XMLHttpRequest();
      trabajo.xhr = xhr;
      trabajo.inicio = Date.now();
      trabajo.estado = 'subiendo';
      xhr.open('POST', opciones.url || window.location.href);
      xhr.timeout = opciones.tiempoMs || 120000;
      xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
      var cuerpo = new FormData();
      var campos = opciones.campos ? opciones.campos(trabajo) : trabajo.campos || {};
      Object.keys(campos).forEach(function (k) {
        if (campos[k] != null) cuerpo.append(k, campos[k]);
      });
      cuerpo.append(opciones.nombreArchivo || 'media_file', archivo, archivo.name);
      xhr.upload.onprogress = function (ev) {
        if (!ev.lengthComputable) {
          pintar(trabajo, { etapa: 'subiendo', porcentaje: null, texto: 'Subiendo…' });
          return;
        }
        var p = textoProgreso(ev.loaded, ev.total, trabajo.inicio);
        var etapa = ev.loaded >= ev.total ? 'guardando' : 'subiendo';
        pintar(trabajo, { etapa: etapa, porcentaje: etapa === 'guardando' ? null : p.porcentaje, texto: etapa === 'guardando' ? 'Guardando' : p.texto });
      };
      xhr.onload = function () {
        if (xhr.status >= 200 && xhr.status < 400) {
          trabajo.estado = 'preparando';
          var trans = Math.round((Date.now() - trabajo.inicio) / 1000);
          pintar(trabajo, {
            etapa: 'preparando',
            porcentaje: null,
            texto: 'Preparando para WhatsApp. Tiempo transcurrido: ' + trans + ' s.',
          });
          var despues = opciones.despues;
          var hecho = function (info) {
            terminar(trabajo, 'upload:done', info || { apto: null, motivo: '' });
          };
          if (typeof despues === 'function') {
            Promise.resolve(despues(trabajo, xhr)).then(hecho).catch(function () {
              hecho({ apto: null, motivo: 'No se pudo leer el estado. El archivo ya se guardó.' });
            });
          } else {
            hecho({ apto: null, motivo: '' });
          }
          return;
        }
        var msg = 'Error del servidor.';
        if (xhr.status === 413) msg = 'El archivo es demasiado grande.';
        terminar(trabajo, 'upload:error', { error: msg, status: xhr.status });
      };
      xhr.onerror = function () {
        terminar(trabajo, 'upload:error', { error: 'Se cayó la red. Puede reintentar.' });
      };
      xhr.ontimeout = function () {
        terminar(trabajo, 'upload:error', { error: 'Se agotó el tiempo de espera.' });
      };
      xhr.onabort = function () {
        terminar(trabajo, 'upload:cancel', { error: 'Subida cancelada.' });
      };
      pintar(trabajo, { etapa: 'subiendo', porcentaje: 0, texto: '0.0 de ' + mb(archivo.size) + ' MB' });
      xhr.send(cuerpo);
    }

    function bombear() {
      while (corriendo < colaMax && cola.length) {
        var trabajo = cola.shift();
        if (trabajo.estado === 'cancelado') continue;
        corriendo += 1;
        activos += 1;
        enviar(trabajo);
      }
    }

    function encolar(archivo, campos) {
      seq += 1;
      var trabajo = { id: seq, archivo: archivo, campos: campos || {}, estado: 'cola', xhr: null };
      trabajos[trabajo.id] = trabajo;
      cola.push(trabajo);
      emitir(objetivo, 'upload:progress', { id: trabajo.id, archivo: archivo.name, etapa: 'cola', porcentaje: 0, texto: 'En cola' });
      bombear();
      return trabajo.id;
    }

    function cancelar(id) {
      var trabajo = trabajos[id];
      if (!trabajo) return;
      trabajo.estado = 'cancelado';
      if (trabajo.xhr) trabajo.xhr.abort();
      else terminar(trabajo, 'upload:cancel', { error: 'Subida cancelada.' });
    }

    function reintentar(id) {
      var previo = trabajos[id];
      if (!previo) return null;
      return encolar(previo.archivo, previo.campos);
    }

    return { encolar: encolar, cancelar: cancelar, reintentar: reintentar };
  }

  return { crear: crear };
});
