$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3.12 -m venv .venv
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -c "import sys; assert sys.version_info[:2] == (3, 12), 'Install Python 3.12 (64-bit) first.'"
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.12 is required.' }
    & python -m venv .venv
} else {
    throw 'Install Python 3.12 (64-bit), then run Setup.cmd again.'
}
if ($LASTEXITCODE -ne 0) { throw 'Could not create the local Python environment.' }
& .\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the internet connection.' }
Write-Host 'Setup complete. Run Start.cmd to open the application.'
