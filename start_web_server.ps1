param([switch]$NoBrowser, [switch]$CheckOnly)

$ErrorActionPreference = 'Stop'
$workspace = $PSScriptRoot
$python = Join-Path $workspace '.venv\Scripts\python.exe'
$port = 12399
$url = "http://127.0.0.1:$port"
$logs = Join-Path $workspace 'data'
$mutex = [System.Threading.Mutex]::new($false, ('Local\IdeaGenWeb-' + ($workspace -replace '[^a-zA-Z0-9]', '_')))
$acquired = $false

function Test-ApplicationReady {
    try {
        $page = Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 3
        if ($page.StatusCode -ne 200 -or $page.Content -notmatch '(?i)ideagen') { return $false }
        # An unauthenticated request must reach the protected candidate API, not a 404 page.
        try {
            Invoke-WebRequest "$url/api/image-candidates/launcher-check" -UseBasicParsing -TimeoutSec 3 | Out-Null
            return $false
        } catch {
            return ($null -ne $_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 401)
        }
    } catch { return $false }
}

try {
    $acquired = $mutex.WaitOne(10000)
    if (-not $acquired) { throw 'Another launcher is busy. Please try again shortly.' }
    $listeners = @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)
    if ($listeners.Count -gt 0) {
        foreach ($listener in $listeners) {
            $owner = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)"
            $commandLine = if ($owner) { [string]$owner.CommandLine } else { '' }
            $executablePath = if ($owner) { [string]$owner.ExecutablePath } else { '' }
            $isProjectServer = $commandLine -match '(?i)manage\.py["\s]+runserver'
            $usesProjectPython = [IO.Path]::GetFullPath($executablePath) -eq [IO.Path]::GetFullPath($python)
            if (-not $owner -or -not $commandLine -or -not $isProjectServer -or
                (-not $commandLine.Contains($workspace) -and -not $usesProjectPython)) {
                throw "Port $port is occupied by another application. No process was stopped."
            }
        }
    } elseif ($CheckOnly) {
        throw "IdeaGen is not running at $url."
    } else {
        New-Item -ItemType Directory -Path $logs -Force | Out-Null
        $process = Start-Process -FilePath $python `
            -ArgumentList ('"{0}" runserver 0.0.0.0:{1}' -f (Join-Path $workspace 'backend\manage.py'), $port) `
            -WorkingDirectory $workspace -WindowStyle Hidden `
            -RedirectStandardOutput (Join-Path $logs 'dev-server-12399.log') `
            -RedirectStandardError (Join-Path $logs 'dev-server-12399-error.log') -PassThru
    }
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if (Test-ApplicationReady) { $ready = $true; break }
        if ($CheckOnly) { break }
        if ($process -and $process.HasExited) { break }
        Start-Sleep -Seconds 1
    }
    if (-not $ready) {
        throw "IdeaGen is not ready or its backend is outdated. Check data/dev-server-12399-error.log. Close its old server window and double-click start_dev.bat again."
    }
    Write-Host "IdeaGen is ready: $url"
    if (-not $NoBrowser -and -not $CheckOnly) { Start-Process $url }
} catch {
    Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    if ($acquired) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
