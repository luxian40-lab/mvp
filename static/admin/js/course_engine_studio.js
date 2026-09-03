(function () {
  function boot() {
    var root = document.getElementById('ce-studio');
    if (!root) return;

    var studioUrl = root.getAttribute('data-studio-url');
    var csrf = root.getAttribute('data-csrf');
    var drop = document.getElementById('ce-drop');
    var fileInput = document.getElementById('ce-rag-files');
    var ragList = document.getElementById('ce-rag-list');
    var brief = document.getElementById('ce-brief');
    var foco = document.getElementById('ce-foco');
    var modulo = document.getElementById('ce-modulo');
    var btnPlan = document.getElementById('ce-plan');
    var btnGen = document.getElementById('ce-generar');
    var preview = document.getElementById('ce-preview');
    var status = document.getElementById('ce-status');
    var videoPreview = document.getElementById('ce-video-preview');
    var videoEl = document.getElementById('ce-video-el');
    var videoLink = document.getElementById('ce-video-link');
    var audioEl = document.getElementById('ce-audio-el');
    var pollTimer = null;
    var docsPollTimer = null;
    var activePlayBtn = null;

    function showStatus(msg, ok) {
      if (!status) return;
      status.hidden = false;
      status.className = 'ce-status ' + (ok ? 'ce-status--ok' : 'ce-status--err');
      status.textContent = msg;
    }

    function postForm(action, extra) {
      var body = new FormData();
      body.set('action', action);
      body.set('csrfmiddlewaretoken', csrf);
      if (modulo && modulo.value) body.set('modulo_id', modulo.value);
      if (foco && foco.value) body.set('foco', foco.value);
      if (brief && brief.value) body.set('brief', brief.value);
      if (extra) {
        Object.keys(extra).forEach(function (k) {
          var v = extra[k];
          if (v && v.forEach) v.forEach(function (f) { body.append(k, f); });
          else body.set(k, v);
        });
      }
      return fetch(studioUrl, {
        method: 'POST',
        body: body,
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      }).then(function (r) {
        return r.json().then(function (data) { return { ok: r.ok, data: data }; });
      });
    }

    function escapeHtml(s) {
      return String(s || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function badgeClass(estado) {
      if (estado === 'indexado') return 'indexado';
      if (estado === 'error') return 'error';
      return 'pendiente';
    }

    function renderRag(docs) {
      if (!ragList || !docs) return;
      if (!docs.length) {
        ragList.innerHTML = '<li class="ce-rag-list__empty">Aún no hay documentos en este curso.</li>';
        return;
      }
      ragList.innerHTML = docs.map(function (d) {
        var retry = d.estado === 'error'
          ? ' <button type="button" class="ce-rag-retry" data-reindex="' + d.id + '">Reintentar</button>'
          : '';
        var chunks = d.chunks ? '<span class="ce-rag-chunks">' + d.chunks + ' chunks</span>' : '';
        return (
          '<li class="ce-rag-list__item" data-doc-id="' + d.id + '" data-estado="' + escapeHtml(d.estado) + '">' +
          '<span class="ce-rag-list__name">' + escapeHtml(d.nombre) + '</span>' +
          '<span class="ce-rag-list__meta">' +
          '<em class="ce-rag-badge ce-rag-badge--' + badgeClass(d.estado) + '">' +
          escapeHtml(d.estado_label || d.estado) + '</em>' + chunks + retry +
          '</span></li>'
        );
      }).join('');
      bindReindex();
    }

    function bindReindex() {
      if (!ragList) return;
      ragList.querySelectorAll('[data-reindex]').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
          e.stopPropagation();
          var docId = btn.getAttribute('data-reindex');
          postForm('reindex', { doc_id: docId })
            .then(function (res) {
              if (res.data.documentos) renderRag(res.data.documentos);
              showStatus('Reindexación en cola…', true);
              startDocsPoll();
            });
        });
      });
    }

    function fetchDocs() {
      return fetch(studioUrl + '?docs=1', {
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      }).then(function (r) { return r.json(); });
    }

    function startDocsPoll() {
      if (docsPollTimer) clearInterval(docsPollTimer);
      var ticks = 0;
      docsPollTimer = setInterval(function () {
        ticks += 1;
        fetchDocs().then(function (data) {
          if (!data.ok || !data.documentos) return;
          renderRag(data.documentos);
          var pending = data.documentos.some(function (d) { return d.estado === 'pendiente'; });
          if (!pending || ticks > 45) clearInterval(docsPollTimer);
        }).catch(function () {});
      }, 3000);
    }

    function uploadFiles(files) {
      if (!files || !files.length) return;
      showStatus('Subiendo ' + files.length + ' archivo(s)…', true);
      postForm('upload_rag', { archivos: Array.prototype.slice.call(files) })
        .then(function (res) {
          if (res.data.documentos) renderRag(res.data.documentos);
          if (res.ok) {
            showStatus(
              'Subidos: ' + (res.data.creados || []).map(function (c) { return c.nombre; }).join(', ') +
              ' — indexando en segundo plano…',
              true
            );
            startDocsPoll();
          } else {
            showStatus((res.data.errores || [res.data.error || 'Error']).join(' · '), false);
          }
        })
        .catch(function () { showStatus('Error de red al subir', false); });
    }

    if (drop && fileInput) {
      drop.addEventListener('click', function () { fileInput.click(); });
      drop.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fileInput.click(); }
      });
      drop.addEventListener('dragover', function (e) {
        e.preventDefault();
        drop.classList.add('ce-drop--over');
      });
      drop.addEventListener('dragleave', function () { drop.classList.remove('ce-drop--over'); });
      drop.addEventListener('drop', function (e) {
        e.preventDefault();
        drop.classList.remove('ce-drop--over');
        uploadFiles(e.dataTransfer.files);
      });
      fileInput.addEventListener('change', function () {
        uploadFiles(fileInput.files);
        fileInput.value = '';
      });
    }

    bindReindex();

    function stopAudio() {
      if (audioEl) {
        audioEl.pause();
        audioEl.currentTime = 0;
      }
      if (activePlayBtn) {
        activePlayBtn.classList.remove('ce-wa-audio__play--playing');
        activePlayBtn = null;
      }
    }

    function resolveDemoUrl(btn) {
      var url = btn.getAttribute('data-audio-url');
      if (url) return Promise.resolve(url);
      var vid = btn.getAttribute('data-voice-id');
      return fetch(studioUrl + '?demo_voice=' + encodeURIComponent(vid) + '&generate=1', {
        credentials: 'same-origin',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.ok && data.url) {
            btn.setAttribute('data-audio-url', data.url);
            btn.disabled = false;
            return data.url;
          }
          throw new Error(data.error || 'Sin demo');
        });
    }

    document.querySelectorAll('.ce-wa-audio__play').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.stopPropagation();
        if (btn.classList.contains('ce-wa-audio__play--playing')) {
          stopAudio();
          return;
        }
        stopAudio();
        resolveDemoUrl(btn)
          .then(function (url) {
            if (!audioEl) return;
            activePlayBtn = btn;
            btn.classList.add('ce-wa-audio__play--playing');
            audioEl.src = url;
            return audioEl.play();
          })
          .catch(function () { showStatus('No hay demo de voz — ejecute seed voice demos', false); });
      });
    });

    if (audioEl) {
      audioEl.addEventListener('ended', stopAudio);
      audioEl.addEventListener('pause', function () {
        if (audioEl.currentTime === 0 || audioEl.ended) stopAudio();
      });
    }

    document.querySelectorAll('.ce-voice__pick').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var vid = btn.getAttribute('data-voice-id');
        postForm('set_voice', { voice_id: vid })
          .then(function (res) {
            if (!res.ok || !res.data.ok) {
              showStatus(res.data.error || 'No se pudo guardar la voz', false);
              return;
            }
            document.querySelectorAll('.ce-voice').forEach(function (li) {
              li.classList.toggle('ce-voice--active', li.getAttribute('data-voice-id') === vid);
            });
            document.querySelectorAll('.ce-voice__pick').forEach(function (b) {
              var on = b.getAttribute('data-voice-id') === vid;
              b.classList.toggle('ce-voice__pick--on', on);
              b.textContent = on ? '✓ Activa' : 'Usar';
            });
            showStatus('Voz del curso: ' + (res.data.voice_label || vid), true);
          });
      });
    });

    function renderPreview(data) {
      if (!preview) return;
      preview.hidden = false;
      var html = '<strong>' + escapeHtml(data.titulo || 'Plan') + '</strong>';
      (data.beats_tarjeta || []).forEach(function (b, i) {
        html += '<div class="ce-beat"><strong>Beat ' + (i + 1) + ':</strong> ' +
          escapeHtml(b.narracion || b.headline || '') + '</div>';
      });
      preview.innerHTML = html;
    }

    function showVideo(url) {
      if (!url || !videoPreview || !videoEl) return;
      videoPreview.hidden = false;
      videoEl.src = url;
      if (videoLink) {
        videoLink.innerHTML = '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener">Abrir MP4</a>';
      }
    }

    function pollStatus(runId) {
      if (pollTimer) clearInterval(pollTimer);
      pollTimer = setInterval(function () {
        fetch(studioUrl + '?status=' + encodeURIComponent(runId), {
          credentials: 'same-origin',
          headers: { 'X-Requested-With': 'XMLHttpRequest' },
        })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (!data.ok) return;
            var st = data.status || '';
            var vurl = data.video_url || data.media_url || '';
            showStatus('Demo ' + runId + ': ' + st + (vurl ? ' · listo' : ''), st === 'ok' || st === 'done');
            if (vurl && (st === 'ok' || st === 'done')) {
              showVideo(vurl);
              clearInterval(pollTimer);
            }
            if (st === 'error' || st === 'failed') clearInterval(pollTimer);
          })
          .catch(function () {});
      }, 4000);
    }

    if (btnPlan) {
      btnPlan.addEventListener('click', function () {
        btnPlan.disabled = true;
        showStatus('Calculando vista previa…', true);
        postForm('plan')
          .then(function (res) {
            if (res.ok && res.data.ok) {
              renderPreview(res.data);
              showStatus('Vista previa lista (demo máx 15 s).', true);
            } else {
              showStatus(res.data.error || 'No se pudo planificar', false);
            }
          })
          .catch(function () { showStatus('Error de red', false); })
          .finally(function () { btnPlan.disabled = false; });
      });
    }

    if (btnGen) {
      btnGen.addEventListener('click', function () {
        if (!window.confirm('¿Generar demo visual (máx 15 s)? No envía WhatsApp.')) return;
        btnGen.disabled = true;
        postForm('generar')
          .then(function (res) {
            if (res.ok && res.data.ok) {
              showStatus('Demo en cola: ' + res.data.run_id, true);
              pollStatus(res.data.run_id);
            } else {
              showStatus(res.data.error || 'No se pudo encolar', false);
            }
          })
          .catch(function () { showStatus('Error de red', false); })
          .finally(function () { btnGen.disabled = false; });
      });
    }

    var hasPending = ragList && ragList.querySelector('[data-estado="pendiente"]');
    if (hasPending) startDocsPoll();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
