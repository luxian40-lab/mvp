# Guia de integracion API de metricas EKI en Angular (LXP)

Fecha: 14 abril 2026

## 1) Resumen rapido

EKI ya expone la API de metricas para la LXP en esta ruta:

- GET /api/integracion/empleabilidad/metricas/

La LXP Angular debe consumir esta API para mostrar embudo y totales diarios.

## 2) Endpoint y parametros

### Endpoint base

- Produccion: https://eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com/api/integracion/empleabilidad/metricas/

### Query params soportados

- cliente_id (opcional): entero
- fecha (opcional): YYYY-MM-DD
- desde (opcional): YYYY-MM-DD
- hasta (opcional): YYYY-MM-DD

Reglas:

- Si envias fecha, consulta solo un dia.
- Si envias desde y hasta, consulta rango.
- Si envias ambos modos a la vez, se prioriza desde/hasta.

## 3) Seguridad y CORS

En backend EKI quedaron estas variables:

- INTEGRACION_API_KEY
- INTEGRACION_API_ALLOWED_ORIGINS
- INTEGRACION_API_MAX_DIAS

### Recomendado para LXP

- Enviar Authorization con Bearer TOKEN.
- Restringir CORS al dominio Angular real, por ejemplo:
  - INTEGRACION_API_ALLOWED_ORIGINS=https://lxp.tudominio.com

Si INTEGRACION_API_KEY esta vacia, el endpoint no exige token.

## 4) Ejemplos de consumo HTTP

### Dia unico

GET /api/integracion/empleabilidad/metricas/?cliente_id=8&fecha=2026-04-14

Header recomendado:

Authorization: Bearer TU_TOKEN

### Rango

GET /api/integracion/empleabilidad/metricas/?cliente_id=8&desde=2026-04-01&hasta=2026-04-14

## 5) Estructura de respuesta

La respuesta trae 3 bloques principales:

- meta: datos de rango y tenant
- resumen: totales agregados
- metrics: serie plana por dia y metrica

Ejemplo resumido:

{
  "success": true,
  "meta": {
    "schema_version": 1,
    "tenant_id": 8,
    "desde": "2026-04-01",
    "hasta": "2026-04-14",
    "dias": 14
  },
  "resumen": {
    "misiones_total": 120,
    "por_estado": {
      "descubierto": 60,
      "interesado": 30,
      "postulado": 20,
      "entrevista": 7,
      "vinculado": 3
    }
  },
  "metrics": [
    {
      "schema_version": 1,
      "metric_date": "2026-04-14",
      "tenant_id": 8,
      "metric_name": "embudo_descubierto",
      "metric_value": 5
    },
    {
      "schema_version": 1,
      "metric_date": "2026-04-14",
      "tenant_id": 8,
      "metric_name": "misiones_total",
      "metric_value": 9
    }
  ]
}

## 6) Modelos TypeScript sugeridos

```ts
export interface IntegracionMetric {
  schema_version: number;
  metric_date: string;
  tenant_id: number | null;
  metric_name: string;
  metric_value: number;
}

export interface IntegracionMeta {
  schema_version: number;
  tenant_id: number | null;
  desde: string;
  hasta: string;
  dias: number;
}

export interface IntegracionResumen {
  misiones_total: number;
  por_estado: Record<string, number>;
}

export interface IntegracionMetricasResponse {
  success: boolean;
  meta: IntegracionMeta;
  resumen: IntegracionResumen;
  metrics: IntegracionMetric[];
}
```

## 7) Servicio Angular sugerido

```ts
import { HttpClient, HttpHeaders, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
import { IntegracionMetricasResponse } from './integracion-metricas.model';

@Injectable({ providedIn: 'root' })
export class IntegracionMetricasService {
  private readonly baseUrl = 'https://eki-prod-final.eba-32krwxas.us-east-2.elasticbeanstalk.com';

  constructor(private http: HttpClient) {}

  getMetricas(options: {
    clienteId?: number;
    fecha?: string;
    desde?: string;
    hasta?: string;
    apiKey?: string;
  }): Observable<IntegracionMetricasResponse> {
    let params = new HttpParams();

    if (options.clienteId != null) params = params.set('cliente_id', String(options.clienteId));
    if (options.fecha) params = params.set('fecha', options.fecha);
    if (options.desde) params = params.set('desde', options.desde);
    if (options.hasta) params = params.set('hasta', options.hasta);

    const headers = options.apiKey
      ? new HttpHeaders({ Authorization: `Bearer ${options.apiKey}` })
      : undefined;

    return this.http.get<IntegracionMetricasResponse>(
      `${this.baseUrl}/api/integracion/empleabilidad/metricas/`,
      { params, headers }
    );
  }
}
```

## 8) Transformacion para graficas LXP

Sugerencia:

1. Filtrar metrics por metric_name que inicia con embudo_.
2. Agrupar por metric_date.
3. Armar series por estado para lineas o barras apiladas.
4. Usar misiones_total para tarjeta KPI diaria.

## 9) Errores comunes

- 401 No autorizado:
  - Token incorrecto o faltante cuando INTEGRACION_API_KEY esta configurada.

- 400 Rango maximo permitido:
  - Reducir desde/hasta segun INTEGRACION_API_MAX_DIAS.

- Error de CORS en navegador:
  - Agregar dominio Angular en INTEGRACION_API_ALLOWED_ORIGINS.

## 10) Checklist de paso a produccion

- Definir INTEGRACION_API_KEY fuerte.
- Restringir CORS a dominio LXP real.
- Probar fecha unica y rango.
- Validar que dashboard LXP pinte embudo y total diario.
- Registrar alertas si API responde 401, 400 o 5xx.

## 11) Nota de arquitectura

No necesitas crear otra API para este caso si la LXP solo requiere metricas de empleabilidad: el endpoint actual ya cubre consumo por Angular con seguridad y CORS.

Si en el futuro la LXP necesita mas dominios (educacion, certificados, campanas), se recomienda exponer un endpoint agregador con versionado de contrato.
