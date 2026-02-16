# Crear venv con Python 3.14 (intenta varios comandos)
$pyCmd = $null
try { py -3.14 --version; $pyCmd = 'py -3.14' } catch {}
if (-not $pyCmd) { try { python3.14 --version; $pyCmd = 'python3.14' } catch {} }
if (-not $pyCmd) { try { python --version; $pyCmd = 'python' } catch {} }

if (-not $pyCmd) {
    Write-Host 'No se encontró Python 3.14 ni python disponible. Abortando.'
    exit 2
}

Write-Host "Usando: $pyCmd"
& $pyCmd -m venv .venv-py314
. .\.venv-py314\Scripts\Activate.ps1

Write-Host 'Versión de Python en venv:'
python --version

pip install --upgrade pip
pip install pip-tools

if (Test-Path requirements-constraints.txt) { Remove-Item requirements-constraints.txt -Force }

Write-Host 'Ejecutando pip-compile...'
pip-compile --output-file=requirements-constraints.txt requirements.txt

Write-Host 'Probando instalación con constraints (salida en pip-install.log)'
pip install -c requirements-constraints.txt -r requirements.txt 2>&1 | Tee-Object pip-install.log

Write-Host 'Fin del script. Revisa pip-install.log para errores.'
