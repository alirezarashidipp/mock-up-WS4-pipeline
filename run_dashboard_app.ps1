Set-Location -LiteralPath $PSScriptRoot
Write-Host "Dashboard: http://127.0.0.1:8766/"
& ".\.venv\Scripts\python.exe" -m app.dashboard_app
exit $LASTEXITCODE
