Set-Location -LiteralPath $PSScriptRoot
Write-Host "Review:    http://127.0.0.1:8765/"
Write-Host "Dashboard: http://127.0.0.1:8765/dashboard"
& ".\.venv\Scripts\python.exe" -m app.review
exit $LASTEXITCODE
