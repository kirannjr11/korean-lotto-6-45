$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python -m lotto serve
