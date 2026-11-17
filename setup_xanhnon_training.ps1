param([switch]$CheckOnly)
$ErrorActionPreference = 'Stop'
$projectPath = $PSScriptRoot
$pythonPath = Join-Path $projectPath '.venv\Scripts\pythonw.exe'
$trainerPath = Join-Path $projectPath 'daily_train_xanhnon.py'
if (!(Test-Path -LiteralPath $pythonPath) -or !(Test-Path -LiteralPath $trainerPath)) {
    throw 'Missing project Python or local trainer.'
}
$taskName = 'XanhNon-Train-Reviewed-Data'
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument ('"' + $trainerPath + '"') -WorkingDirectory $projectPath
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) -RepetitionInterval (New-TimeSpan -Hours 1)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
if ($CheckOnly) {
    [pscustomobject]@{Task=$taskName; Python=$pythonPath; Trainer=$trainerPath; Interval='1 hour'; User=$identity}
} else {
    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
        -Settings $settings -Principal $principal -Description 'Check reviewed Xanh Non data hourly; train only changed data; preserve active model.' -Force | Out-Null
    Get-ScheduledTask -TaskName $taskName | Select-Object TaskName,State
    Get-ScheduledTaskInfo -TaskName $taskName | Select-Object NextRunTime,LastTaskResult
}
