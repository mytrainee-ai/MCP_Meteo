$pythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) {
    [Console]::Error.WriteLine('Python was not found in .venv. See README.md for setup.')
    exit 1
}

Push-Location -LiteralPath $PSScriptRoot
try {
    & $pythonPath -m streamlit run streamlit_app.py --server.address=127.0.0.1 --browser.gatherUsageStats=false
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
