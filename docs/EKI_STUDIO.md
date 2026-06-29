# eki Studio — arquitectura y DNS

**eki Studio** (`studio.eki.technology`) es el producto de **descubrimiento e inscripción** (catálogo, creadores).  
**Aula virtual** (`aprende.eki.technology`) es solo **estudio**: módulos, biblioteca, tareas, perfil.

Mismo backend Django, mismo deploy EB, rutas distintas.

## Cloudflare — crear `studio.eki.technology`

Igual que `aprende` y `app`:

1. Entra a [Cloudflare](https://dash.cloudflare.com) → dominio **eki.technology** → **DNS** → **Records**.
2. **Add record**
   - **Type:** `CNAME`
   - **Name:** `studio`
   - **Target:** `eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com` (mismo CNAME que app/admin/aprende)
   - **Proxy status:** Proxied (nube naranja)
3. **SSL/TLS** → mismo modo que los otros subdominios (Full o Flexible según tu origen EB).
4. En **AWS EB** → Configuration → Software → Environment properties, añade:
   - `studio.eki.technology` a `EKI_ALLOWED_HOSTS`
   - `https://studio.eki.technology` a `CSRF_TRUSTED_ORIGINS`
5. `eb deploy eki-prod-final`
6. Verificar: `curl -s -o NUL -w "%{http_code}" https://studio.eki.technology/studio/`

## Admin — publicar curso en Studio

En **Cursos** → marcar **Publicado en eki Studio** (`visible_en_studio`).

Tras inscribirse en Studio, el estudiante estudia en `/aprende/`.

## Roadmap Studio (CTO)

| Fase | Qué |
|------|-----|
| **Ahora** | Catálogo, login estudiante, inscripción → aula |
| **Siguiente** | Onboarding creador self-service, vitrina por instructor |
| **Después** | Pagos (Stripe/Wompi), comisión eki, suscripciones |

Ver también `docs/INFRAESTRUCTURA_EKI_PARA_CLOUDFLARE.md`.
