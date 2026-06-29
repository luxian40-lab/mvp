# Checklist pre-deploy eki

Usar antes de `eb deploy eki-prod-final` para evitar regresiones en prod.

## 1. Tests locales (rápido)

```bash
python manage.py check
python manage.py test aprende.tests aprende.tests_admin core.tests_module_steps core.tests_export_estudiantes portal.tests_branding -v 1
```

Si tocaste admin o cursos:

```bash
python manage.py test core.tests_module_steps core.tests_gamificacion_ajuste -v 1
```

## 2. Migraciones

```bash
python manage.py makemigrations --check --dry-run
python manage.py showmigrations --plan | findstr "\[ \]"
```

En prod las migraciones corren en `.platform/hooks/predeploy/02_migrate.sh`.

## 3. Smoke HTTP (tras deploy)

Sustituir dominio si pruebas contra prod:

```bash
curl -4 -s -o NUL -w "health: %{http_code}\n" "https://admin.eki.technology/health/"
curl -4 -s -o NUL -w "portal: %{http_code}\n" "https://app.eki.technology/portal/login/"
curl -4 -s -o NUL -w "aprende: %{http_code}\n" "https://aprende.eki.technology/aprende/"
curl -4 -s -o NUL -w "admin: %{http_code}\n" "https://admin.eki.technology/admin/login/"
```

Esperado: **200** en health, portal, aprende; **302** en admin login (sin sesión).

## 4. Smoke funcional (manual, 5 min)

| Qué | URL / acción |
|-----|----------------|
| Admin carga | `/admin/` → login staff |
| Aula web hub | `/admin/aula-web/` |
| Portal login | `/portal/login/` |
| Aula estudiante | `/aprende/estudiante/login/` |
| Catálogo cursos | login estudiante → ver cursos/tareas |

## 5. WhatsApp (opcional, número prueba)

Número de prueba equipo: **3026480629** (formato WA: `573026480629`).

- Enviar mensaje al bot desde ese número
- Confirmar respuesta en &lt; 30 s
- Si no responde: revisar logs EB / Celery worker

## 6. Deploy

```bash
git status
git push origin HEAD
eb deploy eki-prod-final
eb status eki-prod-final
```

## 7. Rollback si algo falla

```bash
eb deploy eki-prod-final --version <version-anterior>
```

Versión anterior visible en `eb status` o consola EB → Application versions.

## Notas

- **Favicon / static:** preferir data URI inline en templates (evita `Missing staticfiles manifest entry` en prod).
- **CSRF / hosts:** si añades subdominio, actualizar `EKI_ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS` en EB antes del deploy.
