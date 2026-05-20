# Runbook: main -> EB (`eki-prod-final`)

## Objetivo
Estandarizar un flujo semi-automatico de despliegue con guardrails para `main`.

## Flujo operativo
1. Actualizar rama:
   - `git checkout main`
   - `git pull`
2. Asegurar **migraciones** aplicables en el commit (Django: `formulario` y dependencias; ver `INSTRUCTIVO_EKI_RECOLECCION_GEI.md` si se usa recolección Ficha GEI).
3. Ejecutar prechecks:
   - `.\scripts\eb_precheck_main.ps1`
4. Desplegar:
   - `.\scripts\eb_deploy_main.ps1`
5. Verificar:
   - `eb status eki-prod-final`
   - `eb health eki-prod-final`
   - smoke test `http://<cname>/health/`
   - Tras un cambio con modelos nuevos, confirmar en logs o consola que **`migrate`** corrió en el entorno (Beanstalk) o ejecutarlo de forma controlada en RDS.

## Rollback rapido
1. Identificar version previa:
   - `eb status eki-prod-final` (campo `Deployed Version`)
2. Re-deploy de version estable:
   - `eb deploy eki-prod-final --version <version_label_previa>`
3. Validar salud:
   - `eb health eki-prod-final`
   - smoke test `/health/`

## Diagnostico de incidentes
- Logs en tiempo real: `eb logs -f eki-prod-final`
- Estado detallado: `eb events -f eki-prod-final`
- Salud del entorno: `eb health eki-prod-final`

## Notas de seguridad
- Nunca incluir `.env` o secretos en git.
- Cambios de variables sensibles: usar `eb setenv` fuera del repo.

---

## Despliegue Nat + Filtro Cliente Formulario + API LXP GEI

Este bloque cubre el roll-out del trabajo del Track A:
- FK `cliente` opcional en `TipoFormulario` (filtro por cliente con prioridad específico > global).
- Bot comercial **Nat** (identidad colombiana editable por cliente).
- Endpoints LXP `/api/integracion/gei/detalle/` y `/api/integracion/gei/exportar/` + bloque `formularios_gei` en métricas educativas.
- Métricas extendidas en dashboard admin (`fichas_completas/parciales/pendientes`, `campo_con_menor_completitud`, `tiempo_promedio_completar_min`).
- Comando `cargar_flujo_gei` para sembrar el TipoFormulario + 7 pasos.

### 1. Migraciones nuevas (auto-aplicadas en deploy)
- `core/migrations/0078_cliente_nombre_bot_cliente_system_prompt_extra.py` — `AddField` simples (reversibles).
- `formulario/migrations/0002_tipoformulario_cliente.py` — `AddField` FK nullable (reversible).

`.ebextensions/01_django.config` ya corre `python manage.py migrate --noinput` con `leader_only: true`. **No se requiere cambio en el config.**

### 2. Variables de entorno (eb setenv)
Variables nuevas (opcionales — solo si se va a usar el comando `cargar_flujo_gei`):

```powershell
eb setenv `
  CURSO_GEI_ID=<id_curso_pivot> `
  MODULO_GEI_ID=<id_modulo_disparador>
```

**No** se necesitan API keys nuevas: la API LXP reusa `INTEGRACION_API_KEY` y `INTEGRACION_API_ALLOWED_ORIGINS` ya existentes.

Si quieres ajustar globalmente el tono del bot comercial (compat retro):

```powershell
eb setenv BOT_COMERCIAL_SYSTEM_PROMPT_EXTRA="Tu instruccion global aqui"
```

Para ajustar el tono **por cliente** (recomendado): hacelo desde el admin Django: `Cliente → Bot Comercial / Nat → Instrucciones extra`.

### 3. Pasos manuales post-deploy

```powershell
# 1. Deploy
.\scripts\eb_deploy_main.ps1

# 2. Esperar healthy (verificar dashboard EB o):
eb health eki-prod-final

# 3. Conectarse al instance (Windows PowerShell con eb-cli):
eb ssh eki-prod-final

# Dentro de la instancia:
source /var/app/venv/*/bin/activate
cd /var/app/current

# 4. Sembrar el flujo GEI global (aplica a todos los clientes que NO tengan
#    un TipoFormulario específico para ese curso/módulo).
python manage.py cargar_flujo_gei <CURSO_GEI_ID> <MODULO_GEI_ID>

# 5. (Opcional) Sembrar un flujo específico por cliente.
#    Si después se usa --reset, se reescriben los 7 pasos (no toca otros TipoFormulario).
python manage.py cargar_flujo_gei <CURSO_GEI_ID> <MODULO_GEI_ID> --cliente_id <ID_CLIENTE>

# 6. Verificar logs por keywords críticos
eb logs --all | Select-String -Pattern "(ERROR|formulario|Nat|integracion)"
```

### 4. Smoke test API LXP

```powershell
$cname = (eb status eki-prod-final | Select-String -Pattern "CNAME:\s*(.+)$").Matches[0].Groups[1].Value.Trim()
$key = "<INTEGRACION_API_KEY>"
$today = (Get-Date).ToString("yyyy-MM-dd")

# 4.1 Métricas educativas (debe traer bloque formularios_gei)
curl.exe -s -H "Authorization: Bearer $key" `
  "https://$cname/api/integracion/educativa/metricas/?desde=$today&hasta=$today" `
  | ConvertFrom-Json | Select-Object -ExpandProperty formularios_gei

# 4.2 Detalle paginado
curl.exe -s -H "Authorization: Bearer $key" `
  "https://$cname/api/integracion/gei/detalle/?page=1&page_size=10&desde=$today&hasta=$today"

# 4.3 Exportación XLSX (debe descargar binario PK..)
curl.exe -s -H "Authorization: Bearer $key" `
  -o fichas.xlsx `
  "https://$cname/api/integracion/gei/exportar/?desde=$today&hasta=$today"
```

### 5. Smoke test del Bot Comercial (Nat)
1. Enviar un WhatsApp al número del bot comercial: "hola".
2. Verificar respuesta natural y firmada con el `nombre_bot` del Cliente configurado en `BOT_COMERCIAL_CLIENTE_ID`.
3. En admin: `Cliente → <ese cliente> → Bot Comercial / Nat → Instrucciones extra`. Cambiar y enviar otro mensaje, validar que el tono se ajustó (sin redeploy — el system prompt se construye dinámicamente).

### 6. Rollback parcial

Si Nat responde extraño tras el deploy:
- **Vacía** `Cliente.system_prompt_extra` desde admin.
- O `eb setenv BOT_COMERCIAL_SYSTEM_PROMPT_EXTRA=""` para anular el extra global.

Si el filtro por cliente del formulario causa problemas:
- En admin: `Tipos de formulario → marcar como inactivo` el TipoFormulario problemático.

Si la API LXP responde error:
- `INTEGRACION_API_KEY` debe estar set en `eb setenv` (verificar con `eb printenv`).
- `INTEGRACION_API_ALLOWED_ORIGINS` debe incluir el dominio del consumidor.

### 7. Validación pre-deploy en local
```powershell
python -m pytest formulario/tests.py core/tests_Nat.py core/tests_api_lxp.py -q
```
Debe pasar todo (algunos tests skipean si `openai` no está instalado en local — ok, en EB sí está).
