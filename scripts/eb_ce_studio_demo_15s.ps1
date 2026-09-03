# Ejecuta el demo 15s del Course Engine Studio en la instancia EB y lo envia a WhatsApp.
param(
    [string]$Environment = "eki-prod-final",
    [string]$TelQa = "573026480629",
    [int]$CursoId = 22,
    [string]$VoiceId = "",
    [string]$Foco = ""
)

$script = Get-Content "$PSScriptRoot\eb_ce_studio_demo_15s.sh" -Raw
$prefijo = "export TEL_QA='$TelQa'`nexport CE_CURSO_ID='$CursoId'`n"
if ($VoiceId) { $prefijo += "export CE_VOICE_ID='$VoiceId'`n" }
if ($Foco) { $prefijo += "export CE_FOCO='$Foco'`n" }

$bash = ($prefijo + $script) -replace "`r`n", "`n"
$b64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($bash))
& eb ssh $Environment --command "echo $b64 | base64 -d | bash"
