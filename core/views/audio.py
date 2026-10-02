import os
import tempfile

from django.conf import settings

def _audio_path_para_whisper(audio_path: str, mime_base: str) -> str:
    """Ogg/opus de WhatsApp a wav si pydub/ffmpeg están; si no, el original."""
    low = (mime_base or '').lower()
    if not any(x in low for x in ('ogg', 'opus', 'amr', 'aac')):
        return audio_path
    try:
        from pydub import AudioSegment

        audio = AudioSegment.from_file(audio_path)
        wav_path = audio_path.rsplit('.', 1)[0] + '_w.wav'
        audio.export(wav_path, format='wav')
        try:
            os.remove(audio_path)
        except OSError:
            pass
        return wav_path
    except Exception as exc:
        print(f"⚠️ Conversión audio→wav omitida: {exc}")
        return audio_path


def _transcribir_audio_twilio(media_url, media_type='audio/ogg'):
    """
    Transcribe un audio de Twilio.
    
    Prioridad: OpenAI Whisper (confiable en producción), luego VOSK (offline).
    
    Args:
        media_url: URL del audio en Twilio
        media_type: MIME type del audio
    
    Returns:
        str: Texto transcrito o None si falla
    """
    if media_url and not str(media_url).startswith(('http://', 'https://')):
        from core.sandbox_canal import transcribir_audio_meta

        return transcribir_audio_meta(media_url, media_type)
    try:
        from core.twilio_inbound_media import descargar_bytes_twilio

        audio_bytes, ctype_dl = descargar_bytes_twilio(media_url, timeout=25)
        if not audio_bytes:
            print("⚠️ Audio Twilio vacío tras descarga")
            return None
        if ctype_dl and (not media_type or media_type in ('', 'application/octet-stream')):
            media_type = ctype_dl

        audio_size = len(audio_bytes)
        print(f"🎤 Transcribiendo audio ({audio_size} bytes)...")
        
        # Guardar temporalmente con extensión acorde al MIME enviado por Twilio
        # Normalizar: quitar parámetros MIME (e.g. "audio/ogg; codecs=opus" → "audio/ogg")
        mime_base = (media_type or '').split(';')[0].strip().lower()
        suffix_map = {
            'audio/ogg': '.ogg',
            'audio/opus': '.ogg',
            'audio/mpeg': '.mp3',
            'audio/mp3': '.mp3',
            'audio/mp4': '.m4a',
            'audio/aac': '.ogg',   # Whisper no soporta .aac, guardar como .ogg
            'audio/amr': '.ogg',   # Whisper no soporta .amr, guardar como .ogg
            'audio/webm': '.webm',
            'audio/wav': '.wav',
        }
        suffix = suffix_map.get(mime_base, '.ogg')

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_file.write(audio_bytes)
            audio_path = tmp_file.name
        audio_path = _audio_path_para_whisper(audio_path, mime_base)
        
        try:
            # OPCIÓN 1: WHISPER (OpenAI — confiable en producción)
            openai_api_key = getattr(settings, 'OPENAI_API_KEY', '')
            if openai_api_key:
                max_whisper_size = 20 * 1024 * 1024  # 20MB
                if audio_size <= max_whisper_size:
                    print(f"🎤 Transcribiendo con Whisper (archivo: {suffix}, {audio_size} bytes)...")
                    try:
                        from openai import OpenAI
                        client = OpenAI(api_key=openai_api_key)

                        with open(audio_path, 'rb') as audio_file:
                            transcription = client.audio.transcriptions.create(
                                model="whisper-1",
                                file=audio_file,
                                language="es",
                            )

                        texto = (transcription.text or '').strip()
                        print(f"✅ Whisper transcribió: '{texto}'")
                        return texto if texto else None
                    except Exception as whisper_error:
                        print(f"❌ Error Whisper: {whisper_error}")
                        import traceback; traceback.print_exc()
                else:
                    print(f"⚠️ Audio demasiado grande para Whisper ({audio_size} bytes)")
            else:
                print(f"⚠️ OPENAI_API_KEY no configurada — Whisper no disponible")

            # OPCIÓN 2: VOSK (gratuito, offline — si modelo disponible)
            try:
                texto = _transcribir_con_vosk(audio_path)
                if texto:
                    print(f"✅ Vosk transcribió: '{texto}'")
                    return texto
                print(f"⚠️ Vosk retornó vacío")
            except Exception as vosk_error:
                print(f"⚠️ Vosk no disponible: {vosk_error}")
            
            # OPCIÓN 3: FALLBACK — no se pudo transcribir
            print("⚠️ Sin transcripción disponible - retornando None")
            return None
            
        finally:
            # Eliminar archivo temporal
            if os.path.exists(audio_path):
                os.remove(audio_path)
    
    except Exception as e:
        print(f"❌ Error en transcripción: {e}")
        return None


def _transcribir_con_vosk(audio_path):
    """
    Transcribe audio usando VOSK (gratuito, offline).
    
    Instalación requerida:
    - pip install vosk
    - Descargar modelo: https://alphacephei.com/vosk/models
    - Colocar en: models/vosk-model-small-es-0.42/
    """
    try:
        import json
        from vosk import Model, KaldiRecognizer
        from pydub import AudioSegment
        import wave
        
        # Ruta al modelo de Vosk (configurar en settings)
        model_path = getattr(settings, 'VOSK_MODEL_PATH', 'models/vosk-model-small-es-0.42')
        
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Modelo Vosk no encontrado en {model_path}")
        
        # Cargar modelo (se cachea automáticamente)
        model = Model(model_path)
        
        # Convertir audio a formato WAV 16kHz mono (requerido por Vosk)
        audio = AudioSegment.from_file(audio_path)
        audio = audio.set_frame_rate(16000).set_channels(1)

        # Guardar como WAV temporal — SIEMPRE en ruta distinta al original
        base, _ = os.path.splitext(audio_path)
        wav_path = base + '_vosk.wav'
        audio.export(wav_path, format='wav')

        try:
            # Transcribir usando wave module (más confiable)
            recognizer = KaldiRecognizer(model, 16000)

            wf = wave.open(wav_path, "rb")

            # Procesar por chunks
            while True:
                data = wf.readframes(4000)
                if len(data) == 0:
                    break
                recognizer.AcceptWaveform(data)

            wf.close()

            # Obtener resultado final
            result = json.loads(recognizer.FinalResult())
            texto = result.get('text', '').strip()

            print(f"✅ Vosk transcribió: '{texto}'")
            return texto if texto else None
        finally:
            # Limpiar archivo WAV temporal (siempre, incluso en error)
            if os.path.exists(wav_path):
                os.remove(wav_path)

    except Exception as e:
        print(f"❌ Error Vosk: {e}")
        raise  # Re-lanzar para que el fallback funcione
