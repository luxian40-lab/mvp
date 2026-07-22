## Cuándo SÍ o SÍ usar ElastiCache (Redis gestionado)

Hoy (pocos usuarios, **1 instancia EB**): Redis local está bien. No hace falta pagar ~US$10–12/mes.

### Activar ElastiCache cuando ocurra CUALQUIERA de estos:

1. **Escala a 2+ instancias EB** (load balancer / Auto Scaling > 1)  
   Con Redis local cada caja tiene su propia cola → campañas, drip y RAG se parten. **Bloqueante.**

2. **Pérdidas o fallos repetidos de Celery tras deploy/replace**  
   Si ves tareas perdidas, beat/drip que no corre, o `diagnostico_infra --ping` fallando tras rebuilds de instancia → ElastiCache.

3. **Tráfico sostenido de colas**  
   Orientativo: **> ~50–100 tareas Celery/hora de forma habitual** (campañas masivas, indexación RAG frecuente, muchos drips) **o** picos de campañas a **>500 destinatarios** con workers saturados. No es magia de número de “usuarios WhatsApp”, es presión sobre el broker.

4. **SLA / clientes B2B que no toleran huecos**  
   Si un replace de EC2 no puede dejar colas en cero (ej. campaña programada crítica a las 6am) → sacar Redis de la caja.

5. **Antes de multi-AZ / alta disponibilidad**  
   Cuando el plan de negocio diga “prod no puede caer con la instancia”.

### Checklist al activarlo (ver `docs/RUNBOOK_REDIS_CHROMA.md`)

```
CELERY_BROKER_URL=redis://ENDPOINT:6379/0
CELERY_RESULT_BACKEND=redis://ENDPOINT:6379/0
USE_LOCAL_REDIS=0
```

Luego: `python manage.py diagnostico_infra --ping` y probar una campaña + indexación Nat.

### Qué NO obliga ElastiCache

- Más orgs en el portal  
- Más chats Nati (eso carga LLM/DB, no tanto Redis)  
- Solo “por si acaso” con 1 instancia estable  

**Regla corta:** 1 caja + poco Celery → local. **2 cajas o Celery crítico que no puede morir con el EC2 → ElastiCache sí o sí.**
