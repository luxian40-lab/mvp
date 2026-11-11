# Entorno de pruebas local — eki

RDS no se alcanza desde el PC. No se intenta. Los tests hablan con Docker.
El puerto **5432** de esta máquina es otra base: no se toca, no se mapea, no se usa en eki.

## Qué levantar

```
docker compose -f docker-compose.test.yml up -d
```

| Servicio | Contenedor | Puerto en el PC |
| --- | --- | --- |
| PostgreSQL 15 | `eki-test-pg` | **5433** → 5432 del contenedor |
| Redis 7 | `eki-test-redis` | 6379 |

Si Docker Desktop está apagado, los tests de área fallan. No hay plan B a SQLite para la suite (`mvp_project.settings_test`). El `runserver` del admin puede seguir en SQLite: no es el entorno de las pruebas.

## Cómo correr tests

Python 3.11 del venv del repo. Nunca el 3.14 del sistema.

```
$env:POSTGRES_HOST = "localhost"
$env:POSTGRES_PORT = "5433"
$env:POSTGRES_DB = "eki_test"
$env:POSTGRES_USER = "postgres"
$env:POSTGRES_PASSWORD = "postgres"

python manage.py test core.tests_postgres_prueba --settings=mvp_project.settings_test --keepdb -v1
```

`pytest` ya carga `settings_test`. El default del puerto, si no hay variable, es 5433. CI en GitHub pone `POSTGRES_PORT=5432` porque ahí el servicio Postgres sí está en 5432.

Si `POSTGRES_HOST` parece RDS (`rds.amazonaws.com`), Django no arranca los tests.

## Qué no hacer

- `EKI_USE_REMOTE_DB=1` para “probar como prod”. Esa variable abre RDS. Desde aquí no llega y no se usa.
- Apuntar tests al 5432. Ahí hay otra aplicación.
- Meter secretos de producción en este compose. Usuario y clave de prueba: `postgres` / `postgres`, base `eki_test`.
- Desplegar este archivo. No cambia Elastic Beanstalk ni a los estudiantes.
