# eki — Git, ramas y pipeline semanal

Documento operativo para PM, CTO, Dev, Dev 2 y QA. Actualizado: 2026-08-29.

## Estado actual del repo

| Ref | Commit (corto) | Notas |
|-----|----------------|-------|
| `spike/django-unfold` (local) | `65a7831b` | Rama de trabajo con deploy prod reciente |
| `origin/main` (remoto) | `a816bc45` | **Atrasado** vs spike (~15+ commits) |
| `main` (local) | `fc1d086a` | **Desincronizado** con origin y spike |

**Acción P0 git:** consolidar `spike/django-unfold` → `main` → push `origin/main` antes de abrir ramas feature.

## Limpieza de archivos (Nivel A — hecho)

| Item | Estado |
|------|--------|
| `tmp/` (~158 MB) | Eliminado del disco |
| `test_media_drag/` | Eliminado del disco |
| `.gitignore` | Añadido `tmp/`, `test_media_drag/`, `scripts/_qa_*`, `scripts/_ops_*` |
| `scripts/_qa_*` (21) | En disco, **ignorados por git** |
| `scripts/_ops_*` (4) | En disco, **ignorados por git** |

### Nivel B (opcional)

Borrar físicamente `scripts/_qa_*` y `scripts/_ops_*` si ya no se usan en local. No afecta prod.

### No versionar nunca

`.env*`, `*.pem`, `media/`, `chroma_db/`, `eb_*.txt`, credenciales admin.

## Modelo de ramas (equipo futuro)

```
main          ← prod estable; protegida; solo merge vía PR
├── feat/course-engine-tts    ← Dev 2 (esta semana)
├── feat/course-engine-models ← Dev 2 / Dev 1 según slice
├── fix/impulso-m8m9-media    ← Dev 1 ops
└── spike/*                   ← experimentos; no deploy directo
```

### Reglas

1. **`main`** = lo desplegable. Tag o versión EB `main-YYYYMMDD-HHMMSS`.
2. **Feature branches** desde `main` actualizado; vida corta (<1 semana ideal).
3. **No push directo a `main`** cuando haya equipo (GitHub branch protection).
4. **Hotfix prod:** `fix/<desc>` desde `main`, merge rápido + QA smoke obligatorio.

### Acceso dividido (GitHub — cuando haya equipo)

| Rol | Permiso repo | Ramas |
|-----|--------------|-------|
| Lead / Dev 1 | Admin o Maintain | merge `main`, deploy EB |
| Dev 2 | Write | `feat/*`, PRs |
| QA / PM | Read o Triage | issues, reviews |
| Ops | Read + secrets limitados | sin push |

Usar **CODEOWNERS** en paths sensibles: `core/views.py`, `core/bot_comercial/`, `mvp_project/settings_production.py`, `.elasticbeanstalk/`.

## Pipeline semanal (PM → CTO → Dev → QA)

### Semana 2026-08-25 — 2026-09-05

| Día | PM | CTO | Dev 1 | Dev 2 | QA |
|-----|----|----|-------|-------|-----|
| Lun | Consolidar git P0; CA TTS | Aprobar estructura `course_engine/` | Merge spike→main; Impulso M8/M9 re-upload ops | — | — |
| Mar–Mié | Scope TTS MVP | OpenAI TTS + S3; sin WA send aún | Celery estable / alertas si P0 | `feat/course-engine-tts` | — |
| Jue | Review PR TTS | — | Review PR Dev 2 | PR + tests | pytest + audit URL audio |
| Vie | Go/no-go deploy | Condicionado QA_PASS | Deploy solo si pedido | — | smoke remoto si deploy |

### Prioridad P0 (esta semana)

1. **Git:** subir `main` alineado con prod actual.
2. **Impulso:** re-subir 3 videos M8/M9 (ops, Module Builder).
3. **TTS MVP:** generación audio outbound (Dev 2).

### Prioridad P1

- Modelos `CourseGenerationRun` / `MediaAsset` (stub, sin UI completa).
- Branch protection en GitHub.

### Fuera de scope semana

- Video generativo IA.
- Meta outbound migration.
- Infra Chroma worker dedicado.

## Gates de merge / deploy

```
Dev / Dev 2 → PR → QA (PASS/FAIL) → [Sec si webhooks/auth] → PM autoriza → deploy
```

| Gate | Comando / criterio |
|------|-------------------|
| QA unit | `pytest core/tests_*` del área |
| QA Nat | `python scripts/smoke_nat_celery.py` |
| QA media | `python manage.py audit_media_wa --curso-id N` |
| QA post-deploy | `python scripts/smoke_nat_celery.py --remote eki-prod-final` |
| Sec | Sin Critical/High en paths tocados |

**Deploy:** solo con pedido explícito + QA_PASS.

## Comandos git — consolidar main (Lead)

```powershell
cd c:\Users\luxia\OneDrive\Escritorio\eki_mvp
git fetch origin
git checkout spike/django-unfold
git status   # revisar diff; commit limpieza .gitignore si aplica

# Opción A: fast-forward main local al spike y push
git checkout main
git merge spike/django-unfold
git push origin main

# Opción B (si main local divergió): reset main a spike tras backup
git branch backup/pre-main-sync
git checkout main
git reset --hard spike/django-unfold
git push origin main
```

Usar **Opción B** solo si PM/Lead confirma; requiere force push si `origin/main` tiene commits únicos no deseados.

## Dev 2 — arrancar TTS

```powershell
git fetch origin
git checkout main
git pull origin main
git checkout -b feat/course-engine-tts
```

Entregable mínimo: servicio TTS + test + management command `generate_tts_smoke`.

## Referencias

- Skills: `.cursor/skills/eki-dev/`, `.cursor/skills/eki-dev-2/`
- Audio inbound hoy: `core/audio_processor.py` (Whisper)
- Media WA: `core/twilio_media.py`
