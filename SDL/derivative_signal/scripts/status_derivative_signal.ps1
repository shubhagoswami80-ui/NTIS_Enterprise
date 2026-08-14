$Port = 8505
$connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue

if ($connections) {
    Write-Host "Decision Signals: RUNNING"
    Write-Host "URL: http://localhost:$Port/"
    $connections | Select-Object LocalAddress,LocalPort,OwningProcess
} else {
    Write-Host "Decision Signals: STOPPED"
}
