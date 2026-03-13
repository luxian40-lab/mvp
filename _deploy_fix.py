import subprocess
import os

os.chdir(r'c:\Users\luxia\OneDrive\Escritorio\eki_mvp')

print('=== Step 1: Check Python syntax ===')
result = subprocess.run(['python', '-m', 'py_compile', r'core\views.py'], capture_output=True, text=True)
if result.returncode == 0:
    print('OK: Python syntax check passed')
else:
    print('ERROR:', result.stderr)

print('\n=== Step 2: Git status ===')
result = subprocess.run(['git', 'status', '--short'], capture_output=True, text=True)
print(result.stdout)

print('=== Step 3: Git diff summary ===')
result = subprocess.run(['git', 'diff', '--stat'], capture_output=True, text=True)
print(result.stdout)

print('=== Step 4: Stage and commit ===')
subprocess.run(['git', 'add', r'core\views.py'], capture_output=True, text=True)

commit_msg = """fix: audio messages not transcribed in Dario/reto agent states

- _transcribir_audio_twilio now returns None on failure instead of 'listo'
- Allow valid 'listo' audio transcription through (was being blocked)
- Add [AUDIO_NO_TRANSCRITO] handling in all agent states (Dario, reto, tutor, progreso, modulo)
- Mark WhatsappLog with es_audio=True for incoming audio messages
- Show user-friendly retry message when audio cannot be transcribed

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"""

result = subprocess.run(['git', 'commit', '-m', commit_msg], capture_output=True, text=True)
print(result.stdout or result.stderr)

print('\n=== Step 5: Push to remote ===')
result = subprocess.run(['git', 'push'], capture_output=True, text=True, timeout=120)
print(result.stdout or result.stderr)

print('\n=== Step 6: EB Deploy ===')
result = subprocess.run(['eb', 'deploy'], capture_output=True, text=True, timeout=600)
print(result.stdout or result.stderr)
