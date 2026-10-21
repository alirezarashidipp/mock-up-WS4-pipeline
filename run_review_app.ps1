Set-Location -LiteralPath $PSScriptRoot
Write-Host "Review:    http://127.0.0.1:8765/"
& ".\.venv\Scripts\python.exe" -m app.review_app
exit $LASTEXITCODE
