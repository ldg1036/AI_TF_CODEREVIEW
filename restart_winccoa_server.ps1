param(
    [int]$Port = 8765,
    [string]$PythonExe = "C:\Users\39145\AppData\Local\Programs\Python\Python314\python.exe"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$serverScript = Join-Path $repoRoot "backend\server.py"

if (-not (Test-Path $serverScript)) {
    throw "server.py not found: $serverScript"
}

if (-not (Test-Path $PythonExe)) {
    $fallback = (Get-Command python -ErrorAction SilentlyContinue)
    if ($fallback) {
        $PythonExe = $fallback.Source
    } else {
        throw "Python executable not found: $PythonExe"
    }
}

$listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($listener) {
    try {
        Stop-Process -Id $listener.OwningProcess -Force -ErrorAction Stop
        Start-Sleep -Seconds 1
    } catch {
        throw "Failed to stop existing server on port $Port (PID $($listener.OwningProcess)): $($_.Exception.Message)"
    }
}

$stdoutLog = Join-Path $env:TEMP "winccoa_server_stdout.log"
$stderrLog = Join-Path $env:TEMP "winccoa_server_stderr.log"

Remove-Item $stdoutLog, $stderrLog -ErrorAction SilentlyContinue

$proc = Start-Process `
    -FilePath $PythonExe `
    -ArgumentList "-u", $serverScript `
    -WorkingDirectory $repoRoot `
    -RedirectStandardOutput $stdoutLog `
    -RedirectStandardError $stderrLog `
    -PassThru

Start-Sleep -Seconds 2

Write-Output ("Server restarted on http://127.0.0.1:{0}" -f $Port)
Write-Output ("PID: {0}" -f $proc.Id)
Write-Output ("stdout: {0}" -f $stdoutLog)
Write-Output ("stderr: {0}" -f $stderrLog)
