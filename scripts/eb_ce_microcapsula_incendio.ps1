# Microcápsula incendios forestales (~20s) en EB + envío WA solo a TEL_QA.
param(
    [string]$Environment = "eki-prod-final",
    [string]$TelQa = "573026480629",
    [int]$CursoId = 22
)

$script = Get-Content "$PSScriptRoot\eb_ce_microcapsula_incendio.sh" -Raw -Encoding UTF8
$prefijo = "export TEL_QA='$TelQa'`nexport CE_CURSO_ID='$CursoId'`n"
$bash = ($prefijo + $script) -replace "`r`n", "`n"
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
& eb ssh $Environment --command "echo $b64 | base64 -d | bash"
