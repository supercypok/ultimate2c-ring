$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $taskPythonPath)) { throw 'Run Setup.cmd first.' }
& $taskPythonPath -m ultimate2c_ring gui
if ($LASTEXITCODE -ne 0) { throw 'The program exited with an error. See README.md.' }
