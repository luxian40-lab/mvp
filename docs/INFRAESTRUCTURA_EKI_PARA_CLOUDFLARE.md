# eki — Infraestructura actual y guía para Cloudflare / dominio custom

Documento para compartir con ChatGPT (u otro asesor) con **respuestas concretas** sobre dónde está alojado el proyecto y cómo encaja con el plan de subdominios (`app.eki.technology`, `admin.eki.technology`, etc.).

**Última actualización:** junio 2026  
**Repositorio:** `eki_mvp` (Django monolito)  
**Producción actual:** AWS Elastic Beanstalk `eki-prod-final`

---

## 1. Qué es eki (contexto del producto)

**eki** es una plataforma de formación y operación para el sector agro / cooperativas en Colombia. Un mismo backend Django sirve varios “productos”:

| Superficie | Ruta base | Usuarios | Función |
|------------|-----------|----------|---------|
| **Admin operativo eki** | `/admin/` | Staff eki | Cursos, estudiantes, WhatsApp, certificados, drip, GEI, gamificación, etc. |
| **Portal B2B (clientes)** | `/portal/` | Organizaciones cliente (admin / viewer / profesor) | Métricas, estudiantes, cursos, conversaciones, certificados, GEI, empleabilidad |
| **Aula web (aparte)** | `/aprende/` | Estudiantes (cédula + teléfono) y profesores | Lecciones web; **no** vive dentro del portal B2B |
| **Webhooks WhatsApp** | `/webhook/whatsapp/` (y rutas en `integrations/`) | Twilio / Meta | Bot educativo, certificados, onboarding |
| **Health check** | `/health/` | AWS EB | Monitoreo del load balancer |

**Stack aplicación**

- **Django 5** (Python 3.11), monolito modular: `core`, `portal`, `aprende`, `learning`, `integrations`, `formulario`, etc.
- **PostgreSQL** (RDS) — datos transaccionales.
- **Redis local** en la instancia EB — broker Celery (colas async).
- **Celery** worker + beat — tareas en background (webhooks opcionales async, jobs pesados).
- **Gunicorn** — WSGI (`Procfile`: 2 workers × 6 threads).
- **Nginx** — reverse proxy delante de Gunicorn (configurado por Elastic Beanstalk, no por `sites-enabled` manual en VPS).
- **AWS S3** — archivos media (PDFs, audios, certificados, uploads de módulos).
- **Twilio** — WhatsApp HSM y mensajería.
- **OpenAI** — tutor IA, evaluaciones, Nat comercial (según módulo).

**Dominio objetivo:** `eki.technology` (ya comprado). La landing/marketing suele ir en **CloudFront** (o Vercel); la app Django en **AWS**.

---

## 2. Respuestas a las 3 preguntas de ChatGPT

### ¿Dónde está alojado Django?

**AWS Elastic Beanstalk** (no EC2 “a mano”, no Lightsail, no Hostinger VPS).

| Concepto | Valor |
|----------|--------|
| Entorno EB | `eki-prod-final` |
| Región | `us-east-2` (Ohio) |
| URL pública actual (CNAME EB) | `http://eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com` |
| Plataforma | Python 3.11 on Amazon Linux 2023 |
| Deploy | `eb deploy eki-prod-final` desde el repo local |
| Settings prod | `DJANGO_SETTINGS_MODULE=mvp_project.settings_production` |

**PostgreSQL** no está en la misma máquina que Django:

- **Amazon RDS** (`DATABASE_URL` en variables de entorno EB).
- Host referenciado en settings: `eki-database.*.us-east-2.rds.amazonaws.com` / base `ekidb`.

**Archivos media:** bucket S3 `eki-produccion` (región `us-east-2`), vía `django-storages` (`USE_S3=True` en producción).

**Archivos static:** `collectstatic` en deploy EB → servidos por WhiteNoise / configuración de staticfiles en producción (no un bucket S3 dedicado solo para static del portal hoy).

---

### ¿Usas Nginx o Apache delante de Django?

**Nginx** (gestionado por Elastic Beanstalk) → **Gunicorn** → **Django**.

No hay Apache. Tampoco hay en el servidor archivos tipo `/etc/nginx/sites-enabled/app.conf` editados a mano como en un VPS clásico; EB inyecta configuración (ej. `.ebextensions/nginx.config` para timeouts y `client_max_body_size 200M`).

Flujo real en prod:

```
Internet → ALB (Elastic Beanstalk) → Nginx (instancia) → Gunicorn :8000 → Django
                                              ↓
                                    Celery worker/beat (misma instancia)
                                              ↓
                                    Redis localhost (broker)
```

---

### ¿La landing en CloudFront y Django están en servidores distintos?

**Sí, en la arquitectura objetivo son cosas separadas** (y es lo recomendable):

| Componente | Dónde suele vivir | Notas |
|------------|-------------------|--------|
| **Landing** `eki.technology` / `www` | **CloudFront** (+ S3 o Vercel como origen) | Marketing, SEO, sin tocar Django |
| **App Django** | **Elastic Beanstalk** (mismo entorno para admin + portal + aprende + webhooks) | Un solo despliegue, varias rutas |
| **DNS** | **Cloudflare** (o Route 53) | Apunta subdominios al ALB de EB o a CloudFront |

Hoy en producción **todo Django** (admin, portal, aprende, webhooks) comparte **un solo hostname EB**. El dominio `eki.technology` aún puede no estar enlazado al EB; se accede por la URL `.elasticbeanstalk.com`.

---

## 3. Mapa de arquitectura (estado actual vs objetivo)

### Hoy (simplificado)

```
Usuario / Twilio
      │
      ▼
Elastic Beanstalk (eki-prod-final)
  ALB → Nginx → Gunicorn → Django
      │                        ├── /admin/
      │                        ├── /portal/
      │                        ├── /aprende/
      │                        └── /webhook/...
      │
      ├── Celery + Redis (misma instancia)
      │
RDS PostgreSQL ◄────────────────┘
      │
S3 (media) ◄── uploads / certificados / audios
```

### Objetivo con Cloudflare + dominio (recomendado para eki)

```
                    Cloudflare (DNS + proxy opcional)
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
 eki.technology          app.eki.technology    admin.eki.technology
 (opcional www)          (portal B2B)          (mismo EB, path /admin/)
        │                     │                     │
        ▼                     └──────────┬──────────┘
   CloudFront                           ▼
   (landing estática)          Elastic Beanstalk ALB
                                        │
                               Nginx → Gunicorn → Django
                                        │
                               RDS + S3 + Redis/Celery
```

**Importante:** `app.eki.technology` y `admin.eki.technology` pueden apuntar al **mismo** load balancer de EB. No hace falta duplicar Gunicorn ni dos `sites-enabled` en un VPS: Cloudflare solo cambia el **hostname**; Django sigue sirviendo `/portal/` y `/admin/` como hoy.

Opcional más adelante:

- `api.eki.technology` → mismo EB, rutas webhook (`/webhook/whatsapp/`).
- `aprende.eki.technology` → mismo EB, rutas `/aprende/` (aula: estudiar y tareas).
- `studio.eki.technology` → mismo EB, rutas `/studio/` (catálogo e inscripción; creadores).

---

## 4. URLs de producción (referencia)

Base actual: `http://eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com`

| Qué | Ruta |
|-----|------|
| Login portal clientes | `/portal/login/` |
| Dashboard portal | `/portal/dashboard/` |
| Admin Django / Jazzmin | `/admin/` |
| Gamificación manual (staff) | `/admin/gamificacion-ajuste/` |
| Aula web | `/aprende/` |
| eki Studio | `/studio/` |
| Health | `/health/` |

Tras dominio custom (ejemplo):

- `https://app.eki.technology/portal/login/`
- `https://admin.eki.technology/admin/` (mismo servidor; solo DNS distinto)

---

## 5. Configuración Django relevante para dominios

En **producción** (`mvp_project/settings_production.py`):

- `EKI_ALLOWED_HOSTS` — lista explícita de hostnames (recomendado Fase 1).
- `CSRF_TRUSTED_ORIGINS` — obligatorio con cada origen HTTPS.
- `EKI_BEHIND_CLOUDFLARE=true` (default) — cookies seguras + `X-Forwarded-Proto`.
- `SECURE_SSL_REDIRECT = False` — Cloudflare termina HTTPS; origen EB single instance = HTTP:80.
- Media en **S3**, no en disco de EB.

**Entorno actual:** Single Instance (sin ALB). CNAME EB → IP EC2 `3.148.13.164`.

### Sprint 1 — variables en EB (Configuration → Software → Environment properties)

```env
EKI_ALLOWED_HOSTS=app.eki.technology,admin.eki.technology,aprende.eki.technology,aula.eki.technology,studio.eki.technology,eki.technology,eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com
CSRF_TRUSTED_ORIGINS=https://app.eki.technology,https://admin.eki.technology,https://aprende.eki.technology,https://aula.eki.technology,https://studio.eki.technology,https://eki.technology
EKI_BEHIND_CLOUDFLARE=true
```

Después: `eb deploy eki-prod-final` (para cargar `settings_production.py` actualizado).

### Sprint 1 — Cloudflare DNS

| Name | Type | Target | Proxy |
|------|------|--------|-------|
| `app` | CNAME | `eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com` | Proxied |
| `admin` | CNAME | mismo CNAME EB | Proxied |
| `aprende` (o `aula`) | CNAME | mismo CNAME EB | Proxied |
| `studio` | CNAME | mismo CNAME EB | Proxied |

`eki.technology` → sin cambios (landing CloudFront).

### SSL en Cloudflare (single instance, sin cert en origen)

- Probar primero **Full** como sugiere el asesor.
- Si ves **522 / 525**, el origen EB solo escucha **HTTP:80** → usar **Flexible** temporalmente *o* instalar [Cloudflare Origin Certificate](https://developers.cloudflare.com/ssl/origin-configuration/origin-ca/) en Nginx del EB.
- **No** usar IP `3.148.13.164` en DNS (cambia si EB reemplaza la instancia).

Si Twilio webhooks usan dominio propio, incluir también ese host en `ALLOWED_HOSTS` / URLs configuradas en Twilio.

---

## 6. Qué encaja del plan ChatGPT y qué adaptar

### Encaja bien

- DNS en **Cloudflare** con subdominios.
- **Landing** en CloudFront separada de Django.
- **HTTPS** + certificado **ACM** en el ALB de Elastic Beanstalk.
- Servir **static** vía CDN/S3 a medio plazo.
- **Media** ya está en S3.
- Redirecciones 301 de URLs viejas si cambian paths.
- Rate limiting en Cloudflare para `/portal/login/` y `/admin/`.

### Hay que adaptar (no es un VPS con Nginx manual)

| Idea ChatGPT | Realidad eki |
|--------------|--------------|
| `sites-enabled/landing.conf`, `app.conf`, `admin.conf` | EB gestiona Nginx; no se crean vhosts por subdominio en disco salvo customización avanzada (`.platform/nginx/`). |
| Mover `/portal/login/` → `/login/` en Fase 4 | **Cambio grande de código** (`portal/urls.py`, templates, emails, Twilio links). **No recomendado** en la primera migración de dominio. Primero: mismo paths, nuevo hostname. |
| `admin.eki.technology` = instancia Nginx distinta | Mismo EB; solo DNS + opcional regla Cloudflare; Django ya expone `/admin/`. |
| Zero-downtime | EB rolling deploy ya lo da; dominio custom es cambio DNS (propagación minutos–horas). |

### Orden de migración recomendado (pragmático)

1. **ACM** certificado en `us-east-2` para `*.eki.technology` o nombres concretos.
2. **ALB EB** listener HTTPS 443 con ese certificado.
3. **Cloudflare DNS:** CNAME `app` → `eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com` (proxy naranja según necesidad SSL).
4. Variables **CSRF_TRUSTED_ORIGINS** en EB.
5. Probar portal, admin, webhooks Twilio, `/aprende/`.
6. **Landing** `eki.technology` → CloudFront (sin tocar Django).
7. (Opcional) `admin.eki.technology` CNAME al mismo EB.
8. (Futuro) CDN para static; refactor URLs solo si el negocio lo exige.

---

## 7. Seguridad (estado y mejoras)

| Tema | Hoy | Mejora con Cloudflare + dominio |
|------|-----|----------------------------------|
| Admin expuesto | `/admin/` en URL pública EB | Subdominio `admin.*` + WAF / rate limit Cloudflare |
| HTTPS | HTTP al EB; SSL en ALB pendiente de configurar | Forzar HTTPS en ALB + Cloudflare “Full (strict)” |
| HSTS | Desactivado en settings prod | Activar tras SSL estable |
| Portal login | Sin rate limit app-level | Cloudflare rate limiting en `app.*/portal/login/` |
| Staff vs portal | `PortalUsuario` no es `is_staff` | Separación ya existe; admin solo staff Django |

---

## 8. Texto listo para pegar en ChatGPT

Copia el bloque siguiente como primer mensaje:

---

**Contexto:** Proyecto **eki**, Django monolito educativo + WhatsApp + portal B2B Colombia.

**Respuestas:**

1. **¿Dónde está Django?** AWS **Elastic Beanstalk** entorno `eki-prod-final`, región **us-east-2**. URL: `eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com`. PostgreSQL en **RDS** (no en la misma VM). Media en **S3** (`eki-produccion`). Celery + Redis en la misma instancia EB.

2. **¿Nginx o Apache?** **Nginx** (reverse proxy de EB) → **Gunicorn** → Django. No Apache. No es un VPS con `sites-enabled` manual.

3. **¿Landing y Django separados?** **Sí.** Landing/marketing en **CloudFront** (o Vercel); Django solo en EB. Dominio comprado: **eki.technology**. Queremos: `app.eki.technology` (portal `/portal/`), `admin.eki.technology` (mismo EB, `/admin/`), raíz `eki.technology` → landing CloudFront.

**Restricciones:** No quiero reescribir URLs de `/portal/*` a `/*` en la primera fase. Mismas rutas, nuevos hostnames. Webhooks Twilio deben seguir funcionando. Deploy con `eb deploy`.

**Pídeme:** paso a paso Cloudflare DNS + ACM + listener HTTPS en ALB de Elastic Beanstalk + variables `CSRF_TRUSTED_ORIGINS` para Django, sin downtime.

---

## 9. Contacto técnico interno

- Deploy prod: `eb deploy eki-prod-final`
- Settings prod: `mvp_project/settings_production.py`
- URLs raíz: `mvp_project/urls.py`
- Extensión Nginx EB: `.ebextensions/nginx.config`
- Procfile: Gunicorn + Celery worker + Celery beat

---

*Documento generado para alinear migración de dominio con la infraestructura real de eki (EB + RDS + S3), no con un VPS genérico.*
