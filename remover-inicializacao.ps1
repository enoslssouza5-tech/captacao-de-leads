param([string]$Nome = "CRM Captacao de Leads")
$ErrorActionPreference = "Stop"
if (Get-ScheduledTask -TaskName $Nome -ErrorAction SilentlyContinue) {
  Stop-ScheduledTask -TaskName $Nome -ErrorAction SilentlyContinue
  Unregister-ScheduledTask -TaskName $Nome -Confirm:$false
  Write-Output "Tarefa removida: $Nome"
} else {
  Write-Output "Tarefa nao encontrada: $Nome"
}
