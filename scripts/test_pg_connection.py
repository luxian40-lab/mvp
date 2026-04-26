"""
Prueba conexión TCP a PostgreSQL usando las mismas variables que la app.
Uso (desde la raíz del repo): .venv\\Scripts\\python scripts\\test_pg_connection.py

Requiere: DATABASE_URL o DB_HOST + DB_USER + DB_PASSWORD + DB_NAME
Opcional: POSTGRES_CONNECT_TIMEOUT (default 20), PGSSLMODE (ej. require)
"""
from __future__ import annotations

import os
import sys
import urllib.parse
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

try:
    from dotenv import load_dotenv

    load_dotenv(REPO / '.env')
    load_dotenv(REPO / '.env.local', override=False)
except ImportError:
    pass


def _params():
    url = os.environ.get('DATABASE_URL', '').strip()
    if url:
        p = urllib.parse.urlparse(url)
        return {
            'host': p.hostname or 'localhost',
            'port': p.port or 5432,
            'user': p.username or '',
            'password': p.password or '',
            'dbname': p.path.lstrip('/') or 'postgres',
        }
    h = os.environ.get('DB_HOST')
    u = os.environ.get('DB_USER')
    pw = os.environ.get('DB_PASSWORD')
    n = os.environ.get('DB_NAME')
    if h and u and pw and n:
        return {
            'host': h,
            'port': int(os.environ.get('DB_PORT', '5432')),
            'user': u,
            'password': pw,
            'dbname': n,
        }
    return None


def main() -> int:
    import psycopg2

    params = _params()
    if not params:
        print(
            '[ERROR] No hay credenciales. Definí en .env o en el entorno:\n'
            '  DATABASE_URL=postgresql://USER:PASS@HOST:5432/DBNAME\n'
            '  o DB_HOST, DB_USER, DB_PASSWORD, DB_NAME (y opcional DB_PORT)'
        )
        return 2

    timeout = int(os.environ.get('POSTGRES_CONNECT_TIMEOUT', '20'))
    sslmode = os.environ.get('PGSSLMODE', '').strip() or None

    kw = {
        'host': params['host'],
        'port': params['port'],
        'user': params['user'],
        'password': params['password'],
        'dbname': params['dbname'],
        'connect_timeout': timeout,
    }
    if sslmode:
        kw['sslmode'] = sslmode

    print(f"[INFO] Conectando a {params['user']}@{params['host']}:{params['port']}/{params['dbname']} (timeout={timeout}s)...")
    try:
        conn = psycopg2.connect(**kw)
        cur = conn.cursor()
        cur.execute('SELECT 1')
        cur.fetchone()
        cur.close()
        conn.close()
    except Exception as e:
        print(f'[ERROR] No se pudo conectar: {e}\n')
        print(
            'Comprobaciones típicas:\n'
            '  - Security group del RDS: inbound TCP 5432 desde tu IP pública actual.\n'
            '  - VPN si el RDS es solo en VPC privada.\n'
            '  - Si AWS exige SSL: PGSSLMODE=require (o verify-full según política).\n'
            '  - POSTGRES_CONNECT_TIMEOUT=45 si el enlace es lento.\n'
        )
        return 1

    print('[OK] Conexión a PostgreSQL correcta. Podés ejecutar: .\\scripts\\migrate.ps1')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
