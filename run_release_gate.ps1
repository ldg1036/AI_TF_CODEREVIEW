param(
    [ValidateSet("default", "live-ai", "ci")]
    [string]$Mode = "default",
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"

$rootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$argsList = @("tools/release_gate.py")

switch ($Mode) {
    "default" { }
    "live-ai" {
        $argsList += "--with-live-ai"
        $argsList += "--live-ai-with-context"
    }
    "ci" {
        $argsList += "--profile"
        $argsList += "ci"
    }
}

Push-Location $rootDir
try {
    Write-Host "[release-gate] mode=$Mode"
    & $Python @argsList
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
