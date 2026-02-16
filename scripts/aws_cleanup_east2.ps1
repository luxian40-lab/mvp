<#
Cleanup helper for resources created by Elastic Beanstalk / eki-mvp in us-east-2.
This script runs in dry-run mode by default. To perform deletions, pass -Execute.

Usage (PowerShell):
  Set-AWSCredentials or ensure AWS CLI is configured, then:
  .\scripts\aws_cleanup_east2.ps1         # list resources, no deletion
  .\scripts\aws_cleanup_east2.ps1 -Execute  # perform deletions

WARNING: Deletions are irreversible. Review the printed lists before running with -Execute.
#>

param(
  [switch]$Execute
)

$Region = 'us-east-2'
Write-Host "Region: $Region"

function RunAws([string]$cmd) {
  Write-Host "> $cmd"
  if ($Execute) {
    & aws $cmd
  } else {
    Write-Host "(dry-run)"
  }
}

Write-Host "== Elastic Beanstalk Environments matching 'eki' or 'produccion' =="
$eb = aws elasticbeanstalk describe-environments --region $Region --query "Environments[?contains(EnvironmentName, 'eki') || contains(EnvironmentName, 'produccion')]" --output json | ConvertFrom-Json
if ($eb) { $eb | ForEach-Object { Write-Host $_.EnvironmentName } } else { Write-Host "(none)" }

Write-Host "`n== Auto Scaling Groups (awseb) =="
$asgs = aws autoscaling describe-auto-scaling-groups --region $Region --query "AutoScalingGroups[?contains(AutoScalingGroupName, 'awseb')].[AutoScalingGroupName]" --output text
if ($asgs) { $asgs -split "`n" | ForEach-Object { Write-Host $_ } } else { Write-Host "(none)" }

Write-Host "`n== Load Balancers (ELBv2) =="
$lbs = aws elbv2 describe-load-balancers --region $Region --output json | ConvertFrom-Json
if ($lbs.LoadBalancers) { $lbs.LoadBalancers | ForEach-Object { Write-Host $_.LoadBalancerName } } else { Write-Host "(none)" }

Write-Host "`n== Security Groups named awseb-e-* =="
$sgs = aws ec2 describe-security-groups --region $Region --filters Name=group-name,Values="awseb-e-*" --query 'SecurityGroups[].{Id:GroupId,Name:GroupName}' --output json | ConvertFrom-Json
if ($sgs) { $sgs | ForEach-Object { Write-Host "$($_.GroupId)  $($_.Name)" } } else { Write-Host "(none)" }

Write-Host "`n== Volumes tagged with Elastic Beanstalk env names =="
# list volumes with tag key 'elasticbeanstalk:environment-name' values 'produccion' or 'eki-mvp-prod'
$vols = aws ec2 describe-volumes --region $Region --filters Name=tag:elasticbeanstalk:environment-name,Values=produccion,eki-mvp-prod --query 'Volumes[].{Id:VolumeId,State:State,Tags:Tags}' --output json | ConvertFrom-Json
if ($vols) { $vols | ForEach-Object { Write-Host "Volume:$($_.Id) State:$($_.State)" } } else { Write-Host "(none)" }

Write-Host "`n== Elastic IPs (associated with terminated instances maybe) =="
$addrs = aws ec2 describe-addresses --region $Region --output json | ConvertFrom-Json
if ($addrs) { $addrs | ForEach-Object { Write-Host "AllocationId:$($_.AllocationId) PublicIp:$($_.PublicIp) InstanceId:$($_.InstanceId)" } } else { Write-Host "(none)" }

if (-not $Execute) {
  Write-Host "`nDry-run complete. To perform deletions, re-run with -Execute.`n" -ForegroundColor Yellow
  exit 0
}

Write-Host "`n== EXECUTING deletions ==" -ForegroundColor Red

# 1) Terminate Elastic Beanstalk environments that match
foreach ($env in $eb) {
  $name = $env.EnvironmentName
  Write-Host "Terminating EB environment: $name"
  RunAws "elasticbeanstalk terminate-environment --environment-name $name --region $Region"
}

# 2) Delete AutoScaling groups matching awseb-*
foreach ($asg in ($asgs -split "`n")) {
  if ($asg.Trim()) {
    Write-Host "Deleting ASG: $asg"
    RunAws "autoscaling delete-auto-scaling-group --auto-scaling-group-name $asg --force-delete --region $Region"
  }
}

# 3) Delete load balancers whose names contain awseb
foreach ($lb in $lbs.LoadBalancers) {
  if ($lb.LoadBalancerName -like '*awseb*') {
    Write-Host "Deleting LB: $($lb.LoadBalancerName)"
    RunAws "elbv2 delete-load-balancer --load-balancer-arn $($lb.LoadBalancerArn) --region $Region"
  }
}

# 4) Delete security groups awseb-e-* if not in use
foreach ($sg in $sgs) {
  $gid = $sg.GroupId
  Write-Host "Checking usage for SG $gid"
  $nis = aws ec2 describe-network-interfaces --filters Name=group-id,Values=$gid --region $Region --query 'NetworkInterfaces' --output json | ConvertFrom-Json
  if ($nis.Count -eq 0) {
    Write-Host "Deleting SG $gid"
    RunAws "ec2 delete-security-group --group-id $gid --region $Region"
  } else {
    Write-Host "SG $gid is in use; skipping"
  }
}

# 5) Snapshot and delete volumes found
foreach ($v in $vols) {
  $volId = $v.Id
  Write-Host "Creating snapshot for $volId"
  RunAws "ec2 create-snapshot --volume-id $volId --description \"cleanup-snapshot-$volId-$(Get-Date -Format yyyyMMdd)\" --region $Region"
  Write-Host "Deleting volume $volId"
  RunAws "ec2 delete-volume --volume-id $volId --region $Region"
}

# 6) Release Elastic IPs that are not associated
foreach ($a in $addrs) {
  if (-not $a.InstanceId) {
    if ($a.AllocationId) {
      Write-Host "Releasing EIP allocation $($a.AllocationId)"
      RunAws "ec2 release-address --allocation-id $($a.AllocationId) --region $Region"
    }
  } else {
    Write-Host "EIP $($a.PublicIp) associated to instance $($a.InstanceId); skipping"
  }
}

Write-Host "`nCleanup commands issued. Monitor AWS Console for progress." -ForegroundColor Green
