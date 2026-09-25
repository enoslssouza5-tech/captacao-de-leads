<#
  Registra o CRM para subir sozinho quando voce entrar no Windows e reiniciar se cair.
  Uso:   powershell -ExecutionPolicy Bypass -File instalar-inicializacao.ps1
  Teste: powershell -ExecutionPolicy Bypass -File instalar-inicializacao.ps1 -Nome CRM-TESTE -SemIniciar
  Remover: powershell -ExecutionPolicy Bypass -File remover-inicializacao.ps1
  A tarefa roda como o seu usuario (sem administrador), sem janela, so escuta em 127.0.0.1.
#>
param(
  [string]$Nome = "CRM Captacao de Leads",
  [switch]$SemIniciar
)
$ErrorActionPreference = "Stop"
$crm = Split-Path -Parent $MyInvocation.MyCommand.Path
$python = (& py -c "import sys; print(sys.executable)").Trim()
$pythonw = $python -replace "python\.exe$", "pythonw.exe"
if (-not (Test-Path $pythonw)) { $pythonw = $python }

$acao = New-ScheduledTaskAction -Execute $pythonw -Argument "server.py" -WorkingDirectory $crm
$gatilho = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$config = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -ExecutionTimeLimit ([TimeSpan]::Zero) `
  -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $Nome -Action $acao -Trigger $gatilho -Settings $config -Principal $principal -Force | Out-Null
Write-Output "Tarefa registrada: $Nome (sobe ao entrar no Windows, reinicia a cada 1 minuto se cair)."
if (-not $SemIniciar) {
  Start-ScheduledTask -TaskName $Nome
  Write-Output "CRM iniciado em segundo plano: http://127.0.0.1:4400"
}
