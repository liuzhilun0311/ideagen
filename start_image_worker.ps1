$ErrorActionPreference = 'Stop'
$workspace = $PSScriptRoot
$python = Join-Path $workspace '.venv\Scripts\python.exe'
$logs = Join-Path $workspace 'data'
$mutexName = 'Local\IdeaGenImageWorker-' + ($workspace -replace '[^a-zA-Z0-9]', '_')
$mutex = [System.Threading.Mutex]::new($false, $mutexName)
$acquired = $false
try {
    $acquired = $mutex.WaitOne(10000)
    if (-not $acquired) { throw 'Timed out checking the image worker.' }
    $existing = Get-CimInstance Win32_Process | Where-Object {
        $_.Name -like 'python*' -and
        $_.CommandLine -match 'manage\.py[" ]+process_images(?:\s|$)' -and
        ($_.ExecutablePath -eq $python -or $_.CommandLine.Contains($workspace))
    }
    if ($existing) {
        Write-Host 'Image worker is already running.'
        exit 0
    }
    New-Item -ItemType Directory -Path $logs -Force | Out-Null
    $process = Start-Process -FilePath $python `
        -ArgumentList ('"{0}" process_images' -f (Join-Path $workspace 'backend\manage.py')) `
        -WorkingDirectory $workspace -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logs 'postprocessing-worker.log') `
        -RedirectStandardError (Join-Path $logs 'postprocessing-worker-error.log') -PassThru
    Start-Sleep -Seconds 2
    if ($process.HasExited) { throw 'Image worker exited. Check data/postprocessing-worker-error.log.' }
    Write-Host 'Image worker started.'
} finally {
    if ($acquired) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
