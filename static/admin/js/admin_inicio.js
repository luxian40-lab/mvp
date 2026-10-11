/* Carga estado y calidad de las líneas sin bloquear el inicio. */
function ekiInicioLineas() {
  return {
    listo: false,
    porId: {},
    cargar: function () {
      var url = this.$el.getAttribute('data-url');
      var self = this;
      if (!url) {
        self.listo = true;
        return;
      }
      fetch(url, { credentials: 'same-origin' })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var mapa = {};
          (data.lineas || []).forEach(function (fila) {
            mapa[fila.id] = fila;
          });
          self.porId = mapa;
          self.listo = true;
        })
        .catch(function () {
          self.listo = true;
        });
    },
    texto: function (id, campo) {
      if (!this.listo) return '';
      var fila = this.porId[id];
      if (!fila || !fila[campo]) return 'Sin dato';
      return fila[campo];
    },
    chip: function (id) {
      var estado = this.texto(id, 'estado');
      if (estado === 'Conectada') return 'eki-inicio__chip eki-inicio__chip--ok';
      if (estado === 'Con problema') return 'eki-inicio__chip eki-inicio__chip--mal';
      return 'eki-inicio__chip';
    }
  };
}
