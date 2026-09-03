# Política de retención de versiones EB — evita límite 1000 Application Versions.
# Uso: .\scripts\eb_appversion_lifecycle.ps1
#      .\scripts\eb_appversion_lifecycle.ps1 -MaxCount 20
# Ver actual: eb appversion lifecycle -p

param(
    [string]$ApplicationName = "eki-mvp-python",
    [string]$Region = "us-east-2",
    [int]$MaxCount = 20,
    [string]$ServiceRole = "arn:aws:iam::178773630934:role/aws-elasticbeanstalk-service-role"
)

Write-Host "Aplicando lifecycle: MaxCount=$MaxCount DeleteSourceFromS3=true"
$shorthand = "ServiceRole=$ServiceRole,VersionLifecycleConfig={MaxCountRule={Enabled=true,MaxCount=$MaxCount,DeleteSourceFromS3=true},MaxAgeRule={Enabled=false,MaxAgeInDays=180,DeleteSourceFromS3=false}}"

aws elasticbeanstalk update-application-resource-lifecycle `
    --application-name $ApplicationName `
    --region $Region `
    --resource-lifecycle-config $shorthand

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[OK] Política aplicada. Verificar:"
eb appversion lifecycle -p
