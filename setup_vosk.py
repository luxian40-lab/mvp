"""
Script para descargar e instalar el modelo de VOSK en español.
Ejecutar UNA SOLA VEZ después de instalar requirements.txt

Uso:
    python setup_vosk.py
"""

import os
import urllib.request
import zipfile
import sys

# Modelo pequeño de español (42 MB) - rápido y preciso para comandos cortos
MODEL_URL = "https://alphacephei.com/vosk/models/vosk-model-small-es-0.42.zip"
MODEL_NAME = "vosk-model-small-es-0.42"
MODELS_DIR = "models"

def descargar_modelo():
    """Descarga el modelo de Vosk en español"""
    print("🎤 SETUP DE VOSK - Transcripción de Audio GRATUITA")
    print("=" * 60)
    
    # Crear carpeta models si no existe
    if not os.path.exists(MODELS_DIR):
        os.makedirs(MODELS_DIR)
        print(f"✅ Carpeta '{MODELS_DIR}' creada")
    
    model_path = os.path.join(MODELS_DIR, MODEL_NAME)
    
    # Verificar si ya existe
    if os.path.exists(model_path):
        print(f"✅ El modelo ya existe en: {model_path}")
        print("\n🎉 Setup completado. No es necesario descargar de nuevo.")
        return
    
    # Descargar modelo
    zip_path = os.path.join(MODELS_DIR, f"{MODEL_NAME}.zip")
    
    print(f"\n📥 Descargando modelo de español ({MODEL_NAME})...")
    print(f"URL: {MODEL_URL}")
    print("⏳ Esto puede tomar unos minutos (42 MB)...\n")
    
    try:
        def mostrar_progreso(count, block_size, total_size):
            percent = int(count * block_size * 100 / total_size)
            sys.stdout.write(f"\rProgreso: {percent}% ")
            sys.stdout.flush()
        
        urllib.request.urlretrieve(MODEL_URL, zip_path, mostrar_progreso)
        print("\n✅ Descarga completada")
        
        # Extraer ZIP
        print(f"\n📦 Extrayendo archivos...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(MODELS_DIR)
        
        print(f"✅ Modelo extraído en: {model_path}")
        
        # Eliminar ZIP
        os.remove(zip_path)
        print("✅ Archivo ZIP eliminado")
        
        print("\n" + "=" * 60)
        print("🎉 SETUP COMPLETADO EXITOSAMENTE")
        print("=" * 60)
        print(f"\n📁 Modelo instalado en: {os.path.abspath(model_path)}")
        print("\n🚀 Ahora puedes usar transcripción de audio GRATUITA e ILIMITADA")
        print("   - Sin costos por API")
        print("   - Sin límites de uso")
        print("   - Funciona offline")
        
    except Exception as e:
        print(f"\n❌ Error descargando modelo: {e}")
        print("\n🔧 Solución alternativa:")
        print(f"1. Descarga manualmente: {MODEL_URL}")
        print(f"2. Extrae el ZIP en la carpeta '{MODELS_DIR}'")
        print(f"3. Verifica que exista: {model_path}")
        sys.exit(1)


if __name__ == "__main__":
    descargar_modelo()
