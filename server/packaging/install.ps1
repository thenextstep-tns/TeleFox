# Registers FoxyGram Server to start when you log in, restarts it if it stops, and opens its page.
$ErrorActionPreference = 'Stop'
$folder = Split-Path -Parent $MyInvocation.MyCommand.Path
$exe = Join-Path $folder 'FoxyGramServer.exe'
$taskName = 'FoxyGram Server'

$arguments = ''
$teleFoxEnv = Join-Path $env:USERPROFILE 'Documents\Telethon\.env'
if (Test-Path $teleFoxEnv) { $arguments = "--import-env `"$teleFoxEnv`"" }

$action = if ($arguments) {
    New-ScheduledTaskAction -Execute $exe -Argument $arguments -WorkingDirectory $folder
} else {
    New-ScheduledTaskAction -Execute $exe -WorkingDirectory $folder
}
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
Start-ScheduledTask -TaskName $taskName

Start-Sleep -Seconds 4
Start-Process 'http://127.0.0.1:8788/'
Write-Host 'FoxyGram Server is running and will start with Windows.'
