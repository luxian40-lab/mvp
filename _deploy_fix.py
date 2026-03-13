import subprocess
import os
import sys

os.chdir(r'c:\Users\luxia\OneDrive\Escritorio\eki_mvp')

print('=== Step 1: Check Python syntax ===')
result = subprocess.run([sys.executable, '-m', 'py_compile', r'core\views.py'], capture_output=True, text=True)
if result.returncode == 0:
    print('OK: Python syntax check passed')
else:
    print('ERROR:', result.stderr)
    sys.exit(1)

print('\n=== Step 2: Git status ===')
result = subprocess.run(['git', 'status', '--short'], capture_output=True, text=True)
print(result.stdout)

print('=== Step 3: Git diff summary ===')
result = subprocess.run(['git', 'diff', '--stat'], capture_output=True, text=True)
print(result.stdout)

print('=== Step 4: Stage and commit ===')
subprocess.run(['git', 'add', r'core\views.py'], capture_output=True, text=True)

commit_msg = """fix: audio transcription broken - Whisper first, remove listo bias

Root causes fixed:
- _transcribir_con_vosk returned 'listo' on empty text, causing Dario to skip
- Whisper prompt biased transcription toward 'listo'
- Vosk model not deployed to EB, always failing silently
- Prioritize Whisper (works on EB) over Vosk (needs local model)
- _transcribir_audio_twilio returns None on failure (not 'listo')
- Handle [AUDIO_NO_TRANSCRITO] in all agent states with retry message
- Mark WhatsappLog with es_audio=True for audio messages

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"""

result = subprocess.run(['git', 'commit', '-m', commit_msg], capture_output=True, text=True)
print(result.stdout or result.stderr)

print('\n=== Step 5: Push to remote ===')
result = subprocess.run(['git', 'push'], capture_output=True, text=True, timeout=120)
print(result.stdout or result.stderr)

print('\n=== Step 6: EB Deploy ===')
result = subprocess.run(['eb', 'deploy'], capture_output=True, text=True, timeout=600)
print(result.stdout or result.stderr)
