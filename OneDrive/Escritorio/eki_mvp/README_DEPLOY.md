# 🚀 Guía de Deploy en Render

## Paso 1: Preparar el repositorio GitHub

```bash
# Si aún no tienes repo, crea uno
git init
git add .
git commit -m "Initial commit: Eki MVP with WhatsApp bot"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/eki_mvp.git
git push -u origin main
```

---

## Paso 2: Crear cuenta en Render

1. Ve a https://render.com
2. Haz clic en **Sign up**
3. Conecta tu cuenta GitHub
4. Autoriza Render para acceder a tus repositorios

---

## Paso 3: Crear Web Service

1. En el dashboard de Render, haz clic en **+ New**
2. Selecciona **Web Service**
3. Selecciona tu repositorio `eki_mvp`
4. Configura:
   - **Name**: `eki-mvp` (o lo que prefieras)
   - **Region**: `us-east` (o el más cercano)
   - **Branch**: `main`
   - **Runtime**: `Python 3.11`
   - **Build Command**: `./build.sh`
   - **Start Command**: `gunicorn mvp_project.wsgi`

---

## Paso 4: Configurar Variables de Entorno

En la sección **Environment**, añade:

```
DEBUG=False
SECRET_KEY=tu-clave-secreta-segura-aqui
ALLOWED_HOSTS=localhost,127.0.0.1,eki-mvp.onrender.com
WHATSAPP_API_VERSION=v19.0
WHATSAPP_TOKEN=tu_token_aqui
WHATSAPP_PHONE_ID=tu_phone_id_aqui
WHATSAPP_VERIFY_TOKEN=eki_whatsapp_verify_token_2025
CSRF_TRUSTED_ORIGINS=https://eki-mvp.onrender.com
```

⚠️ **IMPORTANTE**: Cambia `WHATSAPP_TOKEN` y `WHATSAPP_PHONE_ID` con tus credenciales reales.

---

## Paso 5: Crear el Web Service

1. Haz clic en **Create Web Service**
2. Render desplegará automáticamente
3. Espera a que termine (verás "Service is live")

Tu URL será: `https://eki-mvp.onrender.com` (o lo que hayas puesto en Name)

---

## Paso 6: Configurar Webhook en Meta

1. Ve a Meta Developers → tu app → WhatsApp → Configuration
2. En **Webhook configuration**, haz clic en **Edit**
3. Completa:
   - **Callback URL**: `https://eki-mvp.onrender.com/webhook/whatsapp/`
   - **Verify Token**: `eki_whatsapp_verify_token_2025`
4. Haz clic en **Verify and Save**

---

## Paso 7: Suscribirse a eventos

En la misma página, bajo **Webhook fields**:
- ✅ `messages`
- ✅ `message_status`

---

## Prueba

Abre WhatsApp en tu celular y envía un mensaje al número configurado. Deberías recibir una respuesta automática.

---

## Monitorear Logs

En el dashboard de Render, haz clic en tu servicio y ve a **Logs** para ver errores en tiempo real.

---

## Tips

- **Free tier de Render**: Auto-pausa después de 15 minutos sin actividad. Para producción, considera upgrade.
- **Base de datos**: Ahora usa SQLite local. Para escalar, migra a PostgreSQL.
- **Redeploy**: Cada push a `main` despliega automáticamente.
- **Variables secretas**: Nunca las commits, siempre en Render Environment.

---

## Troubleshooting

| Problema | Solución |
|----------|----------|
| "Verify and Save" falla | Espera a que Render termine el deploy (puede tardar 2-5 min) |
| Webhook no recibe eventos | Revisa que Callback URL esté correcta y sin errores en Logs |
| Error 500 en webhook | Ve a Logs en Render para ver el error completo |
| Token inválido | Regenera token en Meta con scopes correctos |

---

**¡Listo! Tu bot WhatsApp está vivo en producción.** 🎉
