# eki Studio — guía técnica y operativa

**eki Studio** (`studio.eki.technology`) es el producto de **descubrimiento e inscripción**: catálogo público, login estudiante e inscripción a cursos.

**Aula virtual** (`aprende.eki.technology`) es solo **estudio**: módulos, biblioteca, tareas, ranking y perfil.

Mismo backend Django, mismo deploy en Elastic Beanstalk (`eki-prod-final`), rutas y templates distintos. Opción de arquitectura **B**: dos productos, un motor de contenido.

---

## Flujo del estudiante

```
1. Entra a studio.eki.technology/studio/
2. Explora catálogo (cursos con **PublicacionStudio** + `visible_en_studio`; no programas B2B solo por flag)
3. Registro / login: correo + contraseña (o WhatsApp B2B legacy)
4. Inscribe curso (gratis o pago Wompi) → ProgresoEstudiante
5. Estudia en aprende.eki.technology/aprende/estudiante/
```

## Cuentas web (`CuentaAula`)

Separado de `Estudiante` (WhatsApp) y de `PortalUsuario` (staff B2B).

- **Login / registro:** solo en Studio → `/studio/cuenta/login/` y `/studio/cuenta/registro/`
- **Aula** (`/aprende/estudiante/login/`): solo cédula + teléfono WhatsApp (programa ya inscrito)
- Tras entrar por Studio, la sesión permite abrir el aula sin volver a autenticarse

Cada cuenta web crea un `Estudiante` vinculado (progreso, puntos, ranking).

## Creadores y pagos Wompi

| Modelo | Rol |
|--------|-----|
| `CreadorStudio` | Instructor (activar en admin) |
| `PublicacionStudio` | Precio COP del curso en Studio |
| `AccesoCursoPagado` | Referencia + estado del pago |

Curso de pago → checkout → webhook `/studio/webhook/wompi/` → solo con `aprobado` se inscribe en aula.

Variables EB: `WOMPI_PUBLIC_KEY`, `WOMPI_PRIVATE_KEY`, `WOMPI_INTEGRITY_SECRET`.

---

## Rutas (`studio/`)

| Ruta | Vista | Descripción |
|------|-------|-------------|
| `/studio/` | `inicio` | Landing Studio |
| `/studio/cursos/` | `catalogo` | Listado de cursos publicados |
| `/studio/cuenta/registro/` | Registro correo |
| `/studio/cuenta/login/` | Login correo |
| `/studio/creador/registro/` | Alta creador |
| `/studio/creador/panel/` | Panel creador |
| `/studio/pagar/<ref>/` | Checkout |
| `/studio/webhook/wompi/` | Webhook pagos |
| `/studio/inscribir/<curso_id>/` | `inscribir` | POST inscripción |
| `/studio/creador/` | `creador` | Página creadores (roadmap) |

Enrutamiento por host en `mvp_project/urls.py`: `studio.eki.technology` redirige la raíz a `/studio/`.

---

## Admin — publicar curso en Studio

El catálogo marketplace **solo** lista cursos con `PublicacionStudio` (creador o alta manual en admin) y `visible_en_studio=True`.  
Marcar solo el flag en un curso B2B existente **ya no** lo pone en Studio.

1. Preferido: panel creador → crea curso nuevo + publicación.
2. Alternativa admin: crear `PublicacionStudio` para un curso general (`cliente` vacío) y marcar **Publicado en eki Studio**.
3. Carrito: `/studio/carrito/` — varios cursos pagos → un checkout Wompi (`OrdenStudio`).

Servicio: `studio/catalogo_service.py`.

---

## Cloudflare — DNS `studio.eki.technology`

Igual que `aprende` y `app`:

1. [Cloudflare](https://dash.cloudflare.com) → dominio **eki.technology** → **DNS** → **Records**.
2. **Add record**
   - **Type:** `CNAME`
   - **Name:** `studio`
   - **Target:** `eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com` (mismo CNAME que app/admin/aprende)
   - **Proxy status:** Proxied (nube naranja)
3. **SSL/TLS** → mismo modo que los otros subdominios (Full o Flexible según origen EB).

---

## AWS Elastic Beanstalk — variables obligatorias

En **Configuration → Software → Environment properties**:

```
EKI_ALLOWED_HOSTS=...,studio.eki.technology,...
CSRF_TRUSTED_ORIGINS=...,https://studio.eki.technology,...
```

Si falta el host → Django responde **400 DISALLOWED_HOST** (no es un error de Cloudflare).

Después: `eb deploy eki-prod-final` (o solo reinicio si solo cambiaste variables).

### Verificación

```powershell
curl -s -o NUL -w "%{http_code}" https://studio.eki.technology/studio/
# Esperado: 200
```

---

## Diseño visual

Templates en `studio/templates/studio/`:

- `base.html` — tema **neon morado** futurista (grid, glow)
- `inicio.html`, `catalogo.html`, `creador.html`

El aula (`aprende/templates/`) no se modifica para mantener identidad académica sobria.

---

## Tests

```bash
python manage.py test studio.tests aprende.tests -v 1
```

---

## Roadmap Studio

| Fase | Qué |
|------|-----|
| **Ahora** | Cuentas correo, catálogo neon, creador, pagos MVP + webhook Wompi |
| **Siguiente** | Widget Wompi real, split a creador, panel ingresos |

---

## Documentos relacionados

| Documento | Contenido |
|-----------|-----------|
| `docs/GUIA_PLATAFORMA_EKI.md` | Guía completa: aula, tareas, ranking, Studio, operación |
| `docs/INFRAESTRUCTURA_EKI_PARA_CLOUDFLARE.md` | DNS y arquitectura de dominios |
| `docs/CHECKLIST_PRE_DEPLOY.md` | Smoke tests pre-deploy |
