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

  var AVISO = {
    cola: 'Espera su turno. Puede seguir editando otros mensajes.',
    subiendo: 'Puede seguir editando otros mensajes. No cierre esta página hasta que termine la subida.',
    guardando: 'El archivo ya llegó completo. Se está guardando.',
    preparando: 'Puede cerrar esta página. El archivo se sigue preparando y verá el estado en el mensaje.',
    listo: 'El archivo está listo.',
    error: 'No se pudo subir.',
    cancelado: 'Subida cancelada. No se guardó nada.',
  };

  function sigla(nombre) {
    var n = (nombre || '').toLowerCase();
    if (/\.(mp4|m4v|mov|webm|3gp)$/.test(n)) return 'MP4';
    if (/\.(jpg|jpeg|png|webp|gif)$/.test(n)) return 'IMG';
    if (/\.(mp3|ogg|m4a|aac|amr|opus|wav)$/.test(n)) return 'AUDIO';
    if (/\.pdf$/.test(n)) return 'PDF';
    return 'FILE';
  }

  function reloj(seg) {
    var s = Math.max(0, Math.round(seg));
    var m = Math.floor(s / 60);
    return m + ':' + String(s % 60).padStart(2, '0');
  }

  function textoProgreso(loaded, total, inicio) {
    var pct = total ? Math.round((loaded / total) * 100) : 0;
    var trans = (Date.now() - inicio) / 1000;
    var espera = 'Calculando el tiempo…';
    if (loaded > 0 && total > loaded && trans > 0.4) {
      var vel = loaded / trans;
      espera = 'Quedan unos ' + reloj((total - loaded) / vel);
    }
    return {
      porcentaje: pct,
      megas: mb(loaded) + ' de ' + mb(total) + ' MB',
      espera: espera,
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

    function padre(trabajo) {
      if (typeof opciones.ancla === 'function') {
        var nodo = opciones.ancla(trabajo);
        if (nodo && nodo.appendChild) return nodo;
      }
      return objetivo;
    }

    function fila(trabajo) {
      var raiz = padre(trabajo);
      if (!raiz || !raiz.querySelector) return null;
      var item = raiz.querySelector('[data-mu-id="' + trabajo.id + '"]');
      if (item) return item;
      item = document.createElement('div');
      item.className = 'eki-mu__item eki-mu__pantalla';
      item.setAttribute('data-mu-id', String(trabajo.id));
      item.innerHTML =
        '<div class="eki-mu__cabeza">' +
        '<span class="eki-mu__tipo"></span>' +
        '<div><p class="eki-mu__nombre"></p><p class="eki-mu__peso"></p></div>' +
        '<div class="eki-mu__acciones">' +
        '<button type="button" class="eki-mu__btn" data-mu-cancelar>Cancelar</button>' +
        '<button type="button" class="eki-mu__btn" data-mu-reintentar hidden>Reintentar</button>' +
        '</div></div>' +
        '<ol class="eki-mu__pasos">' +
        '<li data-mu-paso="subiendo"><b>Subiendo</b><span>en espera</span></li>' +
        '<li data-mu-paso="guardando"><b>Guardando</b><span>en espera</span></li>' +
        '<li data-mu-paso="preparando"><b>Preparando para WhatsApp</b><span>en espera</span></li>' +
        '<li data-mu-paso="listo"><b>Listo</b><span>en espera</span></li>' +
        '</ol>' +
        '<p class="eki-mu__pct"></p>' +
        '<div class="eki-mu__barra" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><span></span></div>' +
        '<div class="eki-mu__cifras"><span class="eki-mu__mb"></span><span class="eki-mu__espera"></span></div>' +
        '<p class="eki-mu__texto" aria-live="polite"></p>';
      item.querySelector('.eki-mu__tipo').textContent = sigla(trabajo.archivo.name);
      item.querySelector('.eki-mu__nombre').textContent = trabajo.archivo.name;
      item.querySelector('.eki-mu__peso').textContent = mb(trabajo.archivo.size) + ' MB';
      item.querySelector('[data-mu-cancelar]').addEventListener('click', function () { cancelar(trabajo.id); });
      item.querySelector('[data-mu-reintentar]').addEventListener('click', function () { reintentar(trabajo.id); });
      if (raiz.firstChild) raiz.insertBefore(item, raiz.firstChild);
      else raiz.appendChild(item);
      return item;
    }

    function marcarPasos(item, campos) {
      var orden = ['subiendo', 'guardando', 'preparando', 'listo'];
      var etapa = campos.etapa || '';
      var idx = orden.indexOf(etapa);
      orden.forEach(function (nombre, i) {
        var li = item.querySelector('[data-mu-paso="' + nombre + '"]');
        if (!li) return;
        var nota = li.querySelector('span');
        li.classList.remove('is-on', 'is-ok', 'is-er');
        if (etapa === 'error') {
          if (nombre === (campos.pasoError || 'subiendo')) {
            li.classList.add('is-er');
            if (nota) nota.textContent = 'falló';
          } else if (nota) nota.textContent = 'en espera';
          return;
        }
        if (etapa === 'cancelado') {
          if (nota) nota.textContent = 'cancelada';
          return;
        }
        if (etapa === 'cola') {
          if (i === 0) li.classList.add('is-on');
          if (nota) nota.textContent = i === 0 ? 'en cola' : 'en espera';
          return;
        }
        if (i < idx) {
          li.classList.add('is-ok');
          if (nota) nota.textContent = 'completado';
        } else if (i === idx) {
          li.classList.add('is-on');
          if (!nota) return;
          if (nombre === 'subiendo' && campos.porcentaje != null) nota.textContent = campos.porcentaje + '%';
          else if (nombre === 'listo') nota.textContent = campos.notaListo || 'listo';
          else nota.textContent = 'en curso';
        } else if (nota) nota.textContent = 'en espera';
      });
    }

    function pintar(trabajo, campos) {
      var item = fila(trabajo);
      campos = campos || {};
      if (!campos.texto) campos.texto = AVISO[campos.etapa] || '';
      if (item) {
        item.setAttribute('data-mu-etapa', campos.etapa || '');
        marcarPasos(item, campos);
        var pct = item.querySelector('.eki-mu__pct');
        if (pct) {
          if (campos.etapa === 'subiendo' && campos.porcentaje != null) pct.textContent = campos.porcentaje + '%';
          else if (campos.etapa === 'listo') pct.textContent = '100%';
          else pct.textContent = '';
        }
        var mbEl = item.querySelector('.eki-mu__mb');
        var esperaEl = item.querySelector('.eki-mu__espera');
        if (mbEl) mbEl.textContent = campos.megas || '';
        if (esperaEl) esperaEl.textContent = campos.espera || '';
        var texto = item.querySelector('.eki-mu__texto');
        if (texto) texto.textContent = campos.texto || '';
        var barra = item.querySelector('[role="progressbar"]');
        if (barra) {
          var span = barra.querySelector('span');
          if (campos.porcentaje == null) {
            barra.removeAttribute('aria-valuenow');
            barra.classList.add('eki-mu__barra--indeterminada');
            if (span) span.style.width = '';
          } else {
            barra.classList.remove('eki-mu__barra--indeterminada');
            barra.setAttribute('aria-valuenow', String(campos.porcentaje));
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
      var previo = trabajo.estado;
      trabajo.estado = evento === 'upload:done' ? 'listo' : evento === 'upload:cancel' ? 'cancelado' : 'error';
      detalle = detalle || {};
      if (evento === 'upload:done') {
        var nota = detalle.apto === false ? 'no apto' : detalle.apto === true ? 'apto para WhatsApp' : 'listo';
        pintar(trabajo, {
          etapa: 'listo',
          porcentaje: 100,
          notaListo: nota,
          texto: detalle.motivo || AVISO.listo,
        });
      } else if (evento === 'upload:cancel') {
        pintar(trabajo, { etapa: 'cancelado', porcentaje: null, texto: detalle.error || AVISO.cancelado });
      } else {
        pintar(trabajo, {
          etapa: 'error',
          pasoError: previo === 'preparando' ? 'preparando' : previo === 'guardando' ? 'guardando' : 'subiendo',
          porcentaje: null,
          texto: detalle.error || AVISO.error,
        });
      }
      var raiz = padre(trabajo);
      if (raiz && raiz.querySelector) {
        var item = raiz.querySelector('[data-mu-id="' + trabajo.id + '"]');
        if (item) {
          var re = item.querySelector('[data-mu-reintentar]');
          var ca = item.querySelector('[data-mu-cancelar]');
          if (re) re.hidden = evento === 'upload:done';
          if (ca) ca.hidden = true;
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
        pintar(trabajo, { etapa: 'error', porcentaje: 0, texto: errorLocal });
        var itemError = padre(trabajo) && padre(trabajo).querySelector
          ? padre(trabajo).querySelector('[data-mu-id="' + trabajo.id + '"]')
          : null;
        if (itemError) {
          var reintento = itemError.querySelector('[data-mu-reintentar]');
          var cancelarBtn = itemError.querySelector('[data-mu-cancelar]');
          if (reintento) reintento.hidden = false;
          if (cancelarBtn) cancelarBtn.hidden = true;
        }
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
          pintar(trabajo, { etapa: 'subiendo', porcentaje: null, megas: 'Subiendo…', espera: '' });
          return;
        }
        var p = textoProgreso(ev.loaded, ev.total, trabajo.inicio);
        var etapa = ev.loaded >= ev.total ? 'guardando' : 'subiendo';
        pintar(trabajo, {
          etapa: etapa,
          porcentaje: etapa === 'guardando' ? null : p.porcentaje,
          megas: etapa === 'guardando' ? 'Guardando en el almacenamiento' : p.megas,
          espera: etapa === 'guardando' ? '' : p.espera,
        });
      };
      xhr.onload = function () {
        if (xhr.status >= 200 && xhr.status < 400) {
          trabajo.estado = 'preparando';
          var trans = Math.round((Date.now() - trabajo.inicio) / 1000);
          pintar(trabajo, {
            etapa: 'preparando',
            porcentaje: null,
            megas: 'Tiempo transcurrido: ' + trans + ' s',
            espera: 'Sin porcentaje: el servidor no informa el avance de la conversión.',
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
      pintar(trabajo, {
        etapa: 'subiendo',
        porcentaje: 0,
        megas: '0.0 de ' + mb(archivo.size) + ' MB',
        espera: 'Calculando el tiempo…',
      });
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
      pintar(trabajo, { etapa: 'cola', porcentaje: 0, megas: mb(archivo.size) + ' MB', espera: '' });
      bombear();
      return trabajo.id;
    }

    function cancelar(id) {
      var trabajo = trabajos[id];
      if (!trabajo || trabajo.estado === 'cancelado' || trabajo.estado === 'listo' || trabajo.estado === 'error') return;
      if (trabajo.xhr) {
        trabajo.estado = 'cancelado';
        trabajo.xhr.abort();
        return;
      }
      trabajo.estado = 'cancelado';
      var raiz = padre(trabajo);
      var item = raiz && raiz.querySelector ? raiz.querySelector('[data-mu-id="' + trabajo.id + '"]') : null;
      pintar(trabajo, { etapa: 'cancelado', porcentaje: null, texto: AVISO.cancelado });
      if (item) {
        var ca = item.querySelector('[data-mu-cancelar]');
        if (ca) ca.hidden = true;
      }
      emitir(objetivo, 'upload:cancel', { id: trabajo.id, archivo: trabajo.archivo.name, error: 'Subida cancelada.' });
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
