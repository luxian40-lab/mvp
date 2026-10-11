# Propuesta 5B — subida directa a S3

No está implementada. Sirve para decidir después.

Hoy el archivo viaja navegador, servidor de eki, y de ahí a S3 por el mismo `replace_media`. En 5B el navegador subiría el binario al bucket y el servidor solo autorizaría y registraría la URL.

## URLs prefirmadas, multipart

1. `POST /admin/module-builder/<modulo_id>/subida/iniciar/`  
   Cuerpo JSON: nombre, tamaño, tipo. Respuesta: `uploadId`, `key` bajo el prefijo que ya usa el Builder (`modulos/pasos`, `modulo_<id>`), y una lista de URLs prefirmadas `PUT` (una por parte, por ejemplo 8 MB).
2. El navegador hace `PUT` de cada parte a su URL y guarda el `ETag`.
3. `POST /admin/module-builder/<modulo_id>/subida/cerrar/`  
   Cuerpo: `uploadId`, `key`, partes `{partNumber, etag}`. El servidor completa el multipart en S3 y escribe `PasoModulo.media_url` como hoy, sin inventar otro path.
4. `POST .../subida/abortar/` si la persona cancela.

Esas tres rutas serían nuevas. `replace_media` se quedaría para archivos chicos y para la interfaz de hoy.

## CORS del bucket

Habría que agregar, solo al bucket de media, una regla que permita desde `https://admin.eki.technology`:

- Métodos: `PUT`, `GET`, `HEAD`
- Headers de request: `Content-Type`, `Content-MD5` si se usa
- Exponer: `ETag`
- Sin `*`. Sin otro origen.

No se cambia esa regla en este trabajo.
