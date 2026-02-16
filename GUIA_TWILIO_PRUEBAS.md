# 🚀 Guía para Probar Twilio WhatsApp en Producción

## 📋 Configuración Actual

Tu aplicación está configurada para usar Twilio WhatsApp con las siguientes variables de entorno:

```bash
TWILIO_ACCOUNT_SID=tu_account_sid
TWILIO_AUTH_TOKEN=tu_auth_token
TWILIO_PHONE_NUMBER=whatsapp:+14155238886  # Número de Twilio Sandbox
```

## 🔧 Paso 1: Configurar Variables en AWS Elastic Beanstalk

### Opción A: Desde la terminal (recomendado)

```powershell
# Ver configuración actual
C:/Users/luxia/OneDrive/Escritorio/eki_mvp/.venv-py314/Scripts/eb.exe printenv

# Configurar Twilio
C:/Users/luxia/OneDrive/Escritorio/eki_mvp/.venv-py314/Scripts/eb.exe setenv `
    TWILIO_ACCOUNT_SID=tu_account_sid_aqui `
    TWILIO_AUTH_TOKEN=tu_auth_token_aqui `
    TWILIO_PHONE_NUMBER=whatsapp:+14155238886
```

### Opción B: Desde la consola de AWS

1. Ve a **Elastic Beanstalk** → **eki-prod-final**
2. Click en **Configuration** → **Software** → **Edit**
3. En **Environment properties**, agrega:
   - `TWILIO_ACCOUNT_SID` = tu Account SID
   - `TWILIO_AUTH_TOKEN` = tu Auth Token
   - `TWILIO_PHONE_NUMBER` = `whatsapp:+14155238886`
4. Click **Apply**

## 📱 Paso 2: Obtener Credenciales de Twilio

### 1. Ir a Twilio Console
- URL: https://console.twilio.com/
- Busca **Account SID** y **Auth Token** en el dashboard

### 2. Para usar WhatsApp Sandbox (Pruebas GRATIS)
- Ve a: https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn
- Sigue las instrucciones para conectar tu WhatsApp personal
- Envía el código desde tu WhatsApp al número de sandbox

**Ejemplo de conexión:**
```
Enviar mensaje a: +1 415 523 8886
Texto: join <tu-codigo-sandbox>
```

## 🧪 Paso 3: Hacer Pruebas

### Prueba 1: Verificar Conexión Twilio

Crea un archivo temporal para probar:

```python
# test_twilio.py
from twilio.rest import Client

account_sid = 'tu_account_sid'
auth_token = 'tu_auth_token'
client = Client(account_sid, auth_token)

message = client.messages.create(
    from_='whatsapp:+14155238886',
    to='whatsapp:+57TU_NUMERO',  # Tu número con código de país
    body='✅ Prueba de Twilio desde EKI MVP!'
)

print(f'✅ Mensaje enviado: {message.sid}')
```

Ejecutar:
```powershell
python test_twilio.py
```

### Prueba 2: Probar desde el Admin de Django

1. Ve a: http://eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com/admin/
2. Login: `admin` / `admin123`
3. Ve a **Estudiantes** → Selecciona un estudiante
4. En **Actions**, elige "📢 Megáfono: Enviar mensaje a seleccionados"
5. Escribe un mensaje de prueba
6. Click **Enviar mensajes**

### Prueba 3: Crear un Estudiante de Prueba

```python
# En el shell de Django (eb ssh)
from core.models import Estudiante, Cliente

# Crear cliente de prueba
cliente = Cliente.objects.first()  # O crea uno nuevo

# Crear estudiante con tu número
estudiante = Estudiante.objects.create(
    cedula='123456789',
    nombre='Usuario Prueba',
    telefono='+57TU_NUMERO',  # Tu número de WhatsApp
    cliente=cliente,
    activo=True,
    acepto_terminos=True
)

print(f'✅ Estudiante creado: {estudiante.nombre}')
```

### Prueba 4: Enviar Mensaje Directo desde Views

Usa el endpoint de test del dashboard:

```bash
# Desde tu navegador o Postman
GET http://eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com/api/test-twilio/
```

## 🔍 Verificar Estado de Mensajes

### Ver logs en Twilio Console
1. Ve a: https://console.twilio.com/us1/monitor/logs/messages
2. Verás todos los mensajes enviados con su estado:
   - ✅ **delivered** = Entregado
   - ⏳ **sent** = Enviado pero no entregado aún
   - ❌ **failed** = Falló
   - ⚠️ **undelivered** = No se pudo entregar

### Ver logs en tu aplicación
```powershell
# Ver logs de la aplicación en AWS
C:/Users/luxia/OneDrive/Escritorio/eki_mvp/.venv-py314/Scripts/eb.exe logs --stream
```

### Ver en el Admin
1. Ve a: http://eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com/admin/core/whatsapplog/
2. Verás todos los mensajes enviados/recibidos

## ⚠️ Limitaciones del Sandbox (Modo Prueba)

### ❌ Restricciones:
- Solo puedes enviar a números que se hayan unido al sandbox
- Máximo 5 números en el sandbox
- Los mensajes tienen prefijo de Twilio
- No puedes usar plantillas personalizadas

### ✅ Beneficios:
- **GRATIS** para pruebas
- Ilimitados mensajes de prueba
- Perfecto para desarrollo

## 🚀 Para Producción Real (Cuando estés listo)

### 1. Verificar tu número de Twilio
- Compra un número de Twilio: ~$5/mes USD
- Habilita WhatsApp Business API: Requiere aprobación de Meta
- URL: https://console.twilio.com/us1/develop/sms/settings/whatsapp-sender-registration

### 2. Costos de Producción
- **Mensajes entrantes:** $0.005 USD por mensaje
- **Mensajes salientes (conversación):** $0.0042 USD por mensaje
- **Número de teléfono:** ~$5/mes USD
- **Primera conversación del mes:** Gratis (hasta 1,000 conversaciones)

### 3. Cambiar a número real
```powershell
# Una vez tengas tu número aprobado
C:/Users/luxia/OneDrive/Escritorio/eki_mvp/.venv-py314/Scripts/eb.exe setenv `
    TWILIO_PHONE_NUMBER=whatsapp:+1TU_NUMERO_TWILIO
```

## 🎯 Script de Prueba Rápida

Crea este archivo y ejecútalo para probar todo:

```python
# prueba_twilio_completa.py
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mvp_project.settings_production')
os.environ['DATABASE_URL'] = 'postgresql://ekiadmin:ekisoluciones123@eki-database.c5awuis82zet.us-east-2.rds.amazonaws.com:5432/ekidb'

import django
django.setup()

from twilio.rest import Client
from django.conf import settings

print('🔍 Verificando configuración Twilio...\n')

account_sid = settings.TWILIO_ACCOUNT_SID
auth_token = settings.TWILIO_AUTH_TOKEN
phone_number = settings.TWILIO_PHONE_NUMBER

print(f'Account SID: {account_sid[:10]}...' if account_sid else '❌ No configurado')
print(f'Auth Token: {"✅ Configurado" if auth_token else "❌ No configurado"}')
print(f'Phone Number: {phone_number if phone_number else "❌ No configurado"}')

if account_sid and auth_token:
    try:
        client = Client(account_sid, auth_token)
        account = client.api.accounts(account_sid).fetch()
        print(f'\n✅ Conexión exitosa!')
        print(f'Account Name: {account.friendly_name}')
        print(f'Status: {account.status}')
        
        # Listar últimos mensajes
        messages = client.messages.list(limit=5)
        print(f'\n📨 Últimos {len(messages)} mensajes:')
        for msg in messages:
            print(f'  - {msg.direction}: {msg.to} → {msg.status}')
        
        print('\n✅ Todo configurado correctamente!')
        print('📱 Ahora puedes enviar mensajes de prueba.')
        
    except Exception as e:
        print(f'\n❌ Error: {str(e)}')
else:
    print('\n❌ Faltan credenciales de Twilio')
```

## 📞 Soporte

Si tienes problemas:
1. Verifica que las variables de entorno estén configuradas en EB
2. Revisa los logs: `eb logs`
3. Verifica en Twilio Console que las credenciales sean correctas
4. Asegúrate de que tu número esté unido al sandbox (para pruebas)

## 🎓 Próximos Pasos

1. ✅ Configurar variables de Twilio en EB
2. ✅ Unir tu número al sandbox de Twilio
3. ✅ Hacer prueba enviando mensaje desde el admin
4. ✅ Verificar logs en Twilio Console
5. 🚀 Cuando funcione, decidir si quieres pasar a producción real
