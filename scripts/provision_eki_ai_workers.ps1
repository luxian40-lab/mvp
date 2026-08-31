# Wrapper — ver provision_eki_ai_stack.ps1
param(
    [string]$RedisEndpoint = "",
    [switch]$CreateOnly,
    [switch]$SkipCreate
)
$args = @()
if ($RedisEndpoint) { $args += @("-RedisEndpoint", $RedisEndpoint) }
if ($CreateOnly) { $args += @("-SkipDeploy") }
if ($SkipCreate) { $args += @("-SkipEbCreate") }
& "$PSScriptRoot/provision_eki_ai_stack.ps1" @args
