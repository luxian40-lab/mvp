import boto3
import os
import mimetypes
import requests

# Configuración
BUCKET_NAME = 'eki-public'
REGION = 'us-east-1'

# Requiere AWS_ACCESS_KEY_ID y AWS_SECRET_ACCESS_KEY en el entorno

def subir_archivo_s3(ruta_local, nombre_destino=None):
    s3 = boto3.client('s3', region_name=REGION)
    if not nombre_destino:
        nombre_destino = os.path.basename(ruta_local)
    content_type, _ = mimetypes.guess_type(nombre_destino)
    extra_args = {'ACL': 'public-read'}
    if content_type:
        extra_args['ContentType'] = content_type
    s3.upload_file(ruta_local, BUCKET_NAME, nombre_destino, ExtraArgs=extra_args)
    url_publica = f'https://{BUCKET_NAME}.s3.{REGION}.amazonaws.com/{nombre_destino}'
    return url_publica

def validar_url_publica(url):
    try:
        r = requests.head(url, timeout=10)
        if r.status_code == 200:
            print(f'URL válida: {url}')
            print(f'Content-Type: {r.headers.get("Content-Type")}, Content-Length: {r.headers.get("Content-Length")}')
            return True
        else:
            print(f'Error: status {r.status_code} para {url}')
            return False
    except Exception as e:
        print(f'Error validando {url}: {e}')
        return False

if __name__ == '__main__':
    ruta = input('Ruta local del archivo: ')
    nombre = input('Nombre destino en S3 (opcional): ').strip() or None
    url = subir_archivo_s3(ruta, nombre)
    print(f'URL pública generada: {url}')
    validar_url_publica(url)
