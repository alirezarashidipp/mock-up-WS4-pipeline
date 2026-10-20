Set-Location -LiteralPath $PSScriptRoot
& ".\.venv\Scripts\python.exe" -m app.main
exit $LASTEXITCODE
