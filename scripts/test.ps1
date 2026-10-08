$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
& '.\.venv\Scripts\python.exe' -m pytest --cov=app --cov-report=term-missing
