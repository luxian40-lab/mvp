/* Vista previa en vivo. Alpine ya viene con Unfold. SortableJS, el mismo del constructor. */
(function () {
  function tecnico(nombre) {
    var bruto = (nombre || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    bruto = bruto.toLowerCase().replace(/[\s-]+/g, '_').replace(/[^a-z0-9_]/g, '');
    return bruto.slice(0, 512);
  }

  function numeros(texto) {
    var vistos = [];
    var re = /\{\{(\d+)\}\}/g;
    var match;
    while ((match = re.exec(texto || ''))) {
      var n = parseInt(match[1], 10);
      if (vistos.indexOf(n) === -1) vistos.push(n);
    }
    return vistos;
  }

  function escapar(texto) {
    return (texto || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }

  document.addEventListener('alpine:init', function () {
    Alpine.data('plantillaEditor', function (inicial) {
      return {
        tipo: inicial.tipo || 'TEXTO',
        nombre: inicial.nombre || '',
        metaName: inicial.metaName || '',
        metaBloqueado: !!inicial.metaBloqueado,
        categoria: inicial.categoria || 'UTILITY',
        idioma: inicial.idioma || 'es',
        cuerpo: inicial.cuerpo || '',
        footer: inicial.footer || '',
        notas: inicial.notas || '',
        boton1: inicial.boton1 || '',
        boton2: inicial.boton2 || '',
        botonVer: inicial.botonVer || 'Ver curso',
        botonInfo: inicial.botonInfo || 'Más información',
        pestana: 'mensaje',
        previewCard: 0,
        soloLectura: !!inicial.soloLectura,
        metaGuardado: inicial.metaName || '',
        appId: !!inicial.appId,
        tarjetas: inicial.tarjetas || [],
        origenes: inicial.origenes || {},
        ejemplos: inicial.ejemplos || {},
        opcionesOrigen: inicial.opcionesOrigen || [],
        tipos: inicial.tipos || [],
        alta: inicial.alta || ['TEXTO', 'CARRUSEL'],
        init: function () {
          var self = this;
          this.$nextTick(function () {
            var lista = self.$root.querySelector('[data-pm-cards]');
            if (!lista || typeof Sortable === 'undefined') return;
            Sortable.create(lista, {
              handle: '.pm-mover',
              animation: 120,
              onEnd: function () {
                var orden = [];
                lista.querySelectorAll('[data-pm-card]').forEach(function (nodo) {
                  orden.push(self.tarjetas[parseInt(nodo.getAttribute('data-pm-card'), 10)]);
                });
                self.tarjetas = orden.filter(Boolean);
              },
            });
          });
        },
        elegir: function (tipo) {
          if (this.soloLectura) return;
          this.tipo = tipo;
          if (tipo === 'CARRUSEL') {
            while (this.tarjetas.length < 2) this.agregarTarjeta();
          }
        },
        esAlta: function () {
          return (this.alta || []).indexOf(this.tipo) !== -1;
        },
        alNombre: function () {
          if (!this.metaBloqueado) this.metaName = tecnico(this.nombre);
        },
        variables: function () {
          return numeros(this.cuerpo);
        },
        agregarVariable: function () {
          var nums = this.variables();
          var siguiente = nums.length ? Math.max.apply(null, nums) + 1 : 1;
          var extra = '{{' + siguiente + '}}';
          var campo = this.$refs.cuerpo;
          if (!campo) {
            this.cuerpo = (this.cuerpo || '') + ' ' + extra;
            return;
          }
          var inicio = campo.selectionStart || this.cuerpo.length;
          var fin = campo.selectionEnd || inicio;
          this.cuerpo = this.cuerpo.slice(0, inicio) + extra + this.cuerpo.slice(fin);
        },
        ejemplo: function (n) {
          return this.ejemplos[String(n)] || '';
        },
        fijarEjemplo: function (n, valor) {
          this.ejemplos[String(n)] = valor;
        },
        origen: function (n) {
          return this.origenes[String(n)] || 'texto_fijo';
        },
        fijarOrigen: function (n, valor) {
          this.origenes[String(n)] = valor;
        },
        syncScroll: function () {
          if (this.$refs.hl && this.$refs.cuerpo) {
            this.$refs.hl.scrollTop = this.$refs.cuerpo.scrollTop;
          }
        },
        cuerpoHtml: function () {
          return escapar(this.cuerpo || 'Su mensaje se ve aquí').replace(
            /\{\{(\d+)\}\}/g,
            function (todo) {
              return '<span class="pm-var-chip">' + todo + '</span>';
            }
          );
        },
        moverPreview: function (delta) {
          var siguiente = this.previewCard + delta;
          if (siguiente < 0) siguiente = 0;
          if (siguiente > this.tarjetas.length - 1) siguiente = Math.max(0, this.tarjetas.length - 1);
          this.previewCard = siguiente;
          var cinta = this.$refs.snap;
          if (!cinta || !cinta.children[siguiente]) return;
          cinta.children[siguiente].scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
        },
        reglas: function () {
          var lista = [];
          var meta = this.metaName || tecnico(this.nombre);
          lista.push({
            ok: /^[a-z0-9_]+$/.test(meta),
            texto: 'Nombre técnico en minúsculas, números y guion bajo.',
          });
          var cuerpo = (this.cuerpo || '').trim();
          var alBorde = cuerpo.charAt(0) === '{' || cuerpo.slice(-1) === '}';
          lista.push({
            ok: !alBorde && cuerpo.length <= 1024,
            texto: alBorde
              ? 'El mensaje no puede empezar ni terminar con una variable.'
              : 'El mensaje cabe en 1024 caracteres.',
          });
          lista.push({
            ok: (this.footer || '').length <= 60,
            texto: 'El pie cabe en 60 caracteres.',
          });
          lista.push({
            ok: (this.boton1 || '').length <= 25 && (this.boton2 || '').length <= 25,
            texto: 'Cada botón cabe en 25 caracteres.',
          });
          var faltan = this.variables().some(function (n) {
            return !(this.ejemplos[String(n)] || '').trim();
          }, this);
          lista.push({
            ok: !faltan,
            texto: faltan ? 'Falta el ejemplo de una variable.' : 'Cada variable tiene ejemplo.',
          });
          if (this.tipo === 'CARRUSEL') {
            var n = this.tarjetas.length;
            lista.push({
              ok: n >= 2 && n <= 10,
              texto: 'El carrusel necesita entre 2 y 10 tarjetas.',
            });
          }
          if (!this.esAlta()) {
            lista.push({
              ok: false,
              texto: 'El alta automática cubre Texto y Carrusel. Guarde el borrador: este formato queda como registro.',
            });
          } else if (this.tipo === 'CARRUSEL' && !this.appId) {
            lista.push({
              ok: false,
              texto: 'Para el carrusel hace falta WHATSAPP_APP_ID. Texto sigue disponible.',
            });
          }
          return lista;
        },
        puedeEnviar: function () {
          return this.reglas().every(function (regla) { return regla.ok; });
        },
        motivoEnvio: function () {
          var falla = this.reglas().find(function (regla) { return !regla.ok; });
          return falla ? falla.texto : '';
        },
        agregarTarjeta: function () {
          if (this.tarjetas.length >= 10) return;
          this.tarjetas.push({
            titulo: '',
            cuerpo: '',
            imagen_url: '',
            boton_ver_texto: 'Ver curso',
            boton_info_texto: 'Más información',
          });
        },
        quitarTarjeta: function (indice) {
          if (this.tarjetas.length <= 2) return;
          this.tarjetas.splice(indice, 1);
        },
      };
    });
  });
})();
