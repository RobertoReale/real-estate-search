<#
.SYNOPSIS
    Smoke-tests the packaged Windows app on a machine that has never had the toolchain.

.DESCRIPTION
    The release workflow already launches the frozen binary and waits for the API, so
    the bundle is smoke-tested on every tag. What it cannot be is a clean machine: the
    runner has Python, Node and a venv installed by the job that builds the bundle, so
    an import that only ever resolved because the dev venv had it passes there and
    fails on someone else's PC.

    Windows Sandbox is that clean machine. It is a throwaway Windows with no Python,
    no Node and no venv, it is discarded when it closes, and it takes a logon command,
    which makes it drivable without anyone watching. This script builds a .wsb around
    the release zip, lets the sandbox unzip it, start the app, answer on its own
    loopback, save a setting and come back with it after a restart, then prints one
    pass/fail line per step and closes the sandbox.

    The sandbox runs with networking disabled. It shares this machine's connection
    otherwise, and the app scans real portals on a schedule from whatever host it runs
    on: a scan leaving from here unbudgeted is exactly what gets this address blocked.
    So the half of the manual check that needs a portal is not automated here and stays
    manual - see docs/manual-tests.md.

.PARAMETER Zip
    The release zip to test, e.g. the asset from `gh release download v2.0.0`.

.PARAMETER Folder
    A one-folder build (`dist\RealEstateSearch` from `build_release.py --package`),
    compressed into a zip first so the sandbox sees the same thing a user downloads.

.PARAMETER TimeoutMinutes
    How long to wait for the sandbox's verdict before giving up. Default 15.

.PARAMETER KeepOpen
    Leave the sandbox running at the end instead of closing it, to look inside it.
    Everything in it is still discarded when it is closed by hand.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\windows\sandbox-smoke.ps1 -Zip RealEstateSearch-v2.0.0-windows-x64.zip

.NOTES
    Exit codes: 0 every step passed, 1 a step failed, 2 the sandbox could not be run
    at all (in which case the reason is printed and the check stays manual).
#>
[CmdletBinding(DefaultParameterSetName = 'Zip')]
param(
    [Parameter(Mandatory, ParameterSetName = 'Zip')]
    [string]$Zip,

    [Parameter(Mandatory, ParameterSetName = 'Folder')]
    [string]$Folder,

    [int]$TimeoutMinutes = 15,

    [switch]$KeepOpen
)

$ErrorActionPreference = 'Stop'

# The window process is what owns the running VM; the name changed across Windows
# builds, so both are tried and whichever exists is the one to stop.
$SandboxWindowProcesses = @('WindowsSandboxRemoteSession', 'WindowsSandboxClient')
$SandboxVmProcess = 'vmmemWindowsSandbox'

function Write-Step {
    param([string]$Status, [string]$Name, [string]$Detail)
    $colour = switch ($Status) {
        'PASS' { 'Green' }
        'FAIL' { 'Red' }
        default { 'DarkGray' }
    }
    Write-Host ("  {0,-4}  {1,-16} {2}" -f $Status, $Name, $Detail) -ForegroundColor $colour
}

function Get-SandboxWindowProcess {
    foreach ($name in $SandboxWindowProcesses) {
        $found = Get-Process -Name $name -ErrorAction SilentlyContinue
        if ($found) { return $found }
    }
    return $null
}

function Stop-Sandbox {
    $windows = Get-SandboxWindowProcess
    if (-not $windows) { return }
    $windows | Stop-Process -Force -ErrorAction SilentlyContinue
    $deadline = (Get-Date).AddSeconds(60)
    while ((Get-Date) -lt $deadline) {
        if (-not (Get-Process -Name $SandboxVmProcess -ErrorAction SilentlyContinue)) { return }
        Start-Sleep -Seconds 2
    }
}

# --------------------------------------------------------------------------
# Can the sandbox run here at all?
# --------------------------------------------------------------------------

# Never turn the feature on from here: enabling an optional Windows feature needs an
# administrator and a reboot, and this is somebody's own machine. If it is off, say so
# and let the check stay manual.
$sandboxExe = Join-Path $env:WINDIR 'System32\WindowsSandbox.exe'
if (-not (Test-Path $sandboxExe)) {
    Write-Host "Windows Sandbox is not installed on this machine." -ForegroundColor Yellow
    Write-Host "It ships with Windows Pro/Enterprise as the optional feature"
    Write-Host "'Containers-DisposableClientVM', which an administrator enables from"
    Write-Host "'Turn Windows features on or off' followed by a reboot. This script does"
    Write-Host "not do that for you. Until then, check 7 stays a manual test on a second PC."
    exit 2
}

if ((Get-SandboxWindowProcess) -or (Get-Process -Name $SandboxVmProcess -ErrorAction SilentlyContinue)) {
    Write-Host "A Windows Sandbox is already running, and only one can exist at a time." -ForegroundColor Yellow
    Write-Host "Close it and run this again."
    exit 2
}

# --------------------------------------------------------------------------
# Stage: the zip and the guest script read-only, one folder for the verdict writable
# --------------------------------------------------------------------------

$staging = Join-Path ([System.IO.Path]::GetTempPath()) ('sandbox-smoke-' + [guid]::NewGuid().ToString('N').Substring(0, 8))
$pkgDir = Join-Path $staging 'pkg'
$outDir = Join-Path $staging 'out'
New-Item -ItemType Directory -Path $pkgDir -Force | Out-Null
New-Item -ItemType Directory -Path $outDir -Force | Out-Null

if ($PSCmdlet.ParameterSetName -eq 'Folder') {
    $source = (Resolve-Path -LiteralPath $Folder).Path
    if (-not (Test-Path (Join-Path $source 'RealEstateSearch.exe'))) {
        throw "No RealEstateSearch.exe in $source - point -Folder at the one-folder build, e.g. dist\RealEstateSearch."
    }
    $zipPath = Join-Path $pkgDir 'RealEstateSearch.zip'
    Write-Host "Compressing $source ..."
    # Zipped and unzipped again on purpose: a user gets a zip, and a file the archive
    # step drops is a file the sandbox must not find either.
    Compress-Archive -Path $source -DestinationPath $zipPath -CompressionLevel Fastest
} else {
    $source = (Resolve-Path -LiteralPath $Zip).Path
    $zipPath = Join-Path $pkgDir (Split-Path -Leaf $source)
    Copy-Item -LiteralPath $source -Destination $zipPath
}
$zipName = Split-Path -Leaf $zipPath
Write-Host "Package under test: $source"

# The guest script lives in the staging folder rather than being passed as a command
# line: the logon command is a single string, and a whole test run does not fit in one.
$guest = @'
# Runs inside Windows Sandbox, as its logon command. Windows PowerShell 5.1 only:
# there is no pwsh in there, so nothing newer than 5.1 syntax can appear below.
$ErrorActionPreference = 'Stop'

$OutDir = 'C:\out'
$PkgDir = 'C:\pkg'
$AppDir = 'C:\app'
$BaseUrl = 'http://127.0.0.1:8000'
$SettingProbe = 137  # a scan interval nothing else would pick, so reading it back means something

$steps = New-Object System.Collections.ArrayList
$notes = New-Object System.Collections.ArrayList
$failed = $false

function Log([string]$message) {
    $line = "{0}  {1}" -f (Get-Date -Format 'HH:mm:ss'), $message
    Add-Content -Path (Join-Path $OutDir 'progress.log') -Value $line
}

function Record([string]$name, [string]$status, [string]$detail) {
    [void]$steps.Add([pscustomobject]@{ name = $name; status = $status; detail = $detail })
    Log ("[{0}] {1} - {2}" -f $status, $name, $detail)
    if ($status -eq 'FAIL') { $script:failed = $true }
}

# A step that fails stops the ones after it: "the setting persisted" says nothing
# useful about a build whose API never answered.
function Step([string]$name, [scriptblock]$body) {
    if ($script:failed) {
        Record $name 'SKIP' 'an earlier step failed'
        return
    }
    try {
        $detail = & $body
        Record $name 'PASS' $detail
    } catch {
        Record $name 'FAIL' $_.Exception.Message
    }
}

function Get-Api([string]$path) {
    return Invoke-RestMethod -Uri ($BaseUrl + $path) -UseBasicParsing -TimeoutSec 15
}

function Wait-Api([int]$seconds) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $null = Get-Api '/api/settings'
            return $true
        } catch {
            Start-Sleep -Seconds 3
        }
    }
    return $false
}

function Wait-ApiGone([int]$seconds) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $null = Get-Api '/api/settings'
            Start-Sleep -Seconds 2
        } catch {
            return $true
        }
    }
    return $false
}

function Start-App([string]$exe) {
    # WorkingDirectory matters: a one-folder PyInstaller build resolves its data
    # files from next to the executable, and starting it from elsewhere is how a
    # collection gap shows up as a missing file rather than as nothing at all.
    return Start-Process -FilePath $exe -WorkingDirectory (Split-Path -Parent $exe) -PassThru
}

$exePath = $null
$appProcess = $null

try {
    Log 'sandbox logon command started'

    Step 'clean-machine' {
        # The premise of the whole check. An interpreter on PATH here would mean the
        # sandbox is not the clean machine it is supposed to be, and a bundle that
        # leans on one would pass for the wrong reason.
        $found = @()
        foreach ($name in @('python', 'python3', 'py', 'node', 'npm')) {
            $cmd = Get-Command $name -ErrorAction SilentlyContinue
            if (-not $cmd) { continue }
            $path = $cmd.Source
            if (-not $path) { continue }
            # The Store app-execution aliases are zero-length reparse points that
            # open the Store instead of running anything: not an interpreter.
            if ($path -like '*\WindowsApps\*') { continue }
            if ((Get-Item -LiteralPath $path).Length -eq 0) { continue }
            $found += "$name ($path)"
        }
        if ($found.Count -gt 0) { throw ("a toolchain is present: " + ($found -join ', ')) }
        "no python, no node, no venv on PATH"
    }

    Step 'unzip' {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zip = Get-ChildItem -Path $PkgDir -Filter *.zip | Select-Object -First 1
        if (-not $zip) { throw "no zip in $PkgDir" }
        [System.IO.Compression.ZipFile]::ExtractToDirectory($zip.FullName, $AppDir)
        $exe = Get-ChildItem -Path $AppDir -Filter 'RealEstateSearch.exe' -Recurse | Select-Object -First 1
        if (-not $exe) { throw "no RealEstateSearch.exe anywhere in the zip" }
        $script:exePath = $exe.FullName
        $count = (Get-ChildItem -Path $AppDir -Recurse -File).Count
        "$count files, executable at $($exe.FullName)"
    }

    Step 'start' {
        $script:appProcess = Start-App $script:exePath
        Start-Sleep -Seconds 5
        if ($script:appProcess.HasExited) {
            throw "the executable exited immediately with code $($script:appProcess.ExitCode)"
        }
        "started, pid $($script:appProcess.Id)"
    }

    Step 'api' {
        if (-not (Wait-Api 240)) { throw "no answer from $BaseUrl/api/settings within 240s" }
        # A message box is how a windowed build reports a missing DLL or data file:
        # there is no console for it to print to. It would be the process's only
        # window, so a window title here is a startup failure the API cannot see.
        $proc = Get-Process -Id $script:appProcess.Id -ErrorAction SilentlyContinue
        if ($proc -and $proc.MainWindowTitle) {
            throw "the app raised a dialog: '$($proc.MainWindowTitle)'"
        }
        "GET /api/settings answered"
    }

    Step 'dashboard' {
        $page = Invoke-WebRequest -Uri ($BaseUrl + '/') -UseBasicParsing -TimeoutSec 30
        if ($page.StatusCode -ne 200) { throw "GET / returned $($page.StatusCode)" }
        $html = $page.Content
        if ($html -notmatch '<div id="root"') { throw "GET / did not return the dashboard shell" }
        # The built bundle, not a stray source index: a package missing frontend/dist
        # still serves an index.html and would otherwise look fine here.
        if ($html -notmatch '/assets/[^"]+\.js') { throw "the served page references no built asset" }
        "GET / served the dashboard and its built bundle"
    }

    Step 'save-setting' {
        $body = @{ scan_interval_minutes = $SettingProbe } | ConvertTo-Json
        $saved = Invoke-RestMethod -Uri ($BaseUrl + '/api/settings') -Method Put -Body $body `
            -ContentType 'application/json' -UseBasicParsing -TimeoutSec 30
        if ([int]$saved.scan_interval_minutes -ne $SettingProbe) {
            throw "the API echoed scan_interval_minutes=$($saved.scan_interval_minutes)"
        }
        "scan_interval_minutes = $SettingProbe"
    }

    Step 'restart' {
        # Killed rather than quit through the tray menu, which no script can click.
        # It is also the harsher of the two gestures, so a setting that survives this
        # survives the clean one.
        Stop-Process -Id $script:appProcess.Id -Force
        if (-not (Wait-ApiGone 60)) { throw "the API still answered 60s after the process was stopped" }
        $script:appProcess = Start-App $script:exePath
        if (-not (Wait-Api 240)) { throw "no answer from the API 240s after restarting" }
        "stopped and started again, pid $($script:appProcess.Id)"
    }

    Step 'persisted' {
        $settings = Get-Api '/api/settings'
        if ([int]$settings.scan_interval_minutes -ne $SettingProbe) {
            throw "scan_interval_minutes came back as $($settings.scan_interval_minutes), not $SettingProbe"
        }
        "scan_interval_minutes is still $SettingProbe after the restart"
    }
} catch {
    Record 'harness' 'FAIL' $_.Exception.Message
} finally {
    # The app's own log is the only thing that explains a failure from in here, and
    # the sandbox takes everything else with it when it closes.
    try {
        $dataDir = Join-Path $env:LOCALAPPDATA 'RealEstateSearch'
        $logPath = Join-Path $dataDir 'app.log'
        if (Test-Path $logPath) {
            Copy-Item -LiteralPath $logPath -Destination (Join-Path $OutDir 'app.log') -ErrorAction SilentlyContinue
            [void]$notes.Add("app.log copied from $dataDir")
        } else {
            [void]$notes.Add("no app.log under $dataDir")
        }
    } catch {
        [void]$notes.Add("could not collect app.log: $($_.Exception.Message)")
    }

    try { if ($appProcess -and -not $appProcess.HasExited) { Stop-Process -Id $appProcess.Id -Force } } catch { }

    $result = [pscustomobject]@{
        finishedAt = (Get-Date).ToString('o')
        passed     = (-not $failed)
        executable = $exePath
        steps      = $steps
        notes      = $notes
    }
    # Written aside and moved into place, so the host never reads half a verdict.
    $tmp = Join-Path $OutDir 'result.tmp'
    $result | ConvertTo-Json -Depth 6 | Set-Content -Path $tmp -Encoding UTF8
    Move-Item -LiteralPath $tmp -Destination (Join-Path $OutDir 'result.json') -Force
    Log 'verdict written'
}
'@

Set-Content -Path (Join-Path $pkgDir 'guest.ps1') -Value $guest -Encoding UTF8

# --------------------------------------------------------------------------
# The .wsb
# --------------------------------------------------------------------------

# Networking off: see the note at the top of this file. vGPU, clipboard, camera and
# microphone off because nothing here needs them and the sandbox is a machine this one
# just handed a folder to.
$wsbPath = Join-Path $staging 'smoke.wsb'
$wsb = @"
<Configuration>
  <Networking>Disable</Networking>
  <vGPU>Disable</vGPU>
  <ClipboardRedirection>Disable</ClipboardRedirection>
  <AudioInput>Disable</AudioInput>
  <VideoInput>Disable</VideoInput>
  <MappedFolders>
    <MappedFolder>
      <HostFolder>$pkgDir</HostFolder>
      <SandboxFolder>C:\pkg</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
    <MappedFolder>
      <HostFolder>$outDir</HostFolder>
      <SandboxFolder>C:\out</SandboxFolder>
      <ReadOnly>false</ReadOnly>
    </MappedFolder>
  </MappedFolders>
  <LogonCommand>
    <Command>cmd.exe /c powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\pkg\guest.ps1 &gt; C:\out\guest-stdout.txt 2&gt;&amp;1</Command>
  </LogonCommand>
</Configuration>
"@
Set-Content -Path $wsbPath -Value $wsb -Encoding UTF8

# --------------------------------------------------------------------------
# Run it
# --------------------------------------------------------------------------

$resultPath = Join-Path $outDir 'result.json'
$progressPath = Join-Path $outDir 'progress.log'

Write-Host "Starting Windows Sandbox ($zipName), up to $TimeoutMinutes minutes..."
Start-Process -FilePath $sandboxExe -ArgumentList "`"$wsbPath`"" | Out-Null

$exitCode = 2
try {
    # If the VM never appears the feature is present but cannot start - a disabled
    # virtualization extension in firmware is the usual reason, and it is not
    # something to fix from a script either.
    $bootDeadline = (Get-Date).AddSeconds(120)
    $booted = $false
    while ((Get-Date) -lt $bootDeadline) {
        if (Get-Process -Name $SandboxVmProcess -ErrorAction SilentlyContinue) { $booted = $true; break }
        if (Test-Path $resultPath) { $booted = $true; break }
        Start-Sleep -Seconds 3
    }
    if (-not $booted) {
        Write-Host "The sandbox did not start within 120 seconds." -ForegroundColor Yellow
        Write-Host "WindowsSandbox.exe is installed, so the feature is on; what is left is"
        Write-Host "usually hardware virtualization disabled in firmware, or no interactive"
        Write-Host "desktop for the session running this script. Neither is changed from here."
        Write-Host "Check 7 stays a manual test until it is sorted out."
        exit 2
    }

    # Every new line, not the newest one: two steps can land between polls, and a
    # stream that shows only the last of them hides the one that took the time.
    $deadline = (Get-Date).AddMinutes($TimeoutMinutes)
    $reported = 0
    while ((Get-Date) -lt $deadline) {
        if (Test-Path $resultPath) { break }
        if (Test-Path $progressPath) {
            $lines = @(Get-Content -Path $progressPath -ErrorAction SilentlyContinue)
            if ($lines.Count -gt $reported) {
                $lines[$reported..($lines.Count - 1)] | ForEach-Object {
                    Write-Host "  ... $_" -ForegroundColor DarkGray
                }
                $reported = $lines.Count
            }
        }
        Start-Sleep -Seconds 5
    }

    if (-not (Test-Path $resultPath)) {
        Write-Host ""
        Write-Host "No verdict after $TimeoutMinutes minutes." -ForegroundColor Red
        if (Test-Path $progressPath) {
            Write-Host "How far it got:"
            Get-Content -Path $progressPath | ForEach-Object { Write-Host "  $_" }
        } else {
            Write-Host "The sandbox wrote nothing at all: its logon command never ran."
        }
        $exitCode = 1
        exit $exitCode
    }

    $result = Get-Content -Path $resultPath -Raw | ConvertFrom-Json
    Write-Host ""
    Write-Host "Result:"
    foreach ($step in $result.steps) { Write-Step $step.status $step.name $step.detail }
    foreach ($note in $result.notes) { Write-Host "  note  $note" -ForegroundColor DarkGray }
    Write-Host ""
    if ($result.passed) {
        Write-Host "PASS - the package runs on a machine with no toolchain." -ForegroundColor Green
        $exitCode = 0
    } else {
        Write-Host "FAIL - see the steps above." -ForegroundColor Red
        $appLog = Join-Path $outDir 'app.log'
        if (Test-Path $appLog) {
            Write-Host ""
            Write-Host "Last 40 lines of the app's own log:"
            Get-Content -Path $appLog -Tail 40 | ForEach-Object { Write-Host "  $_" }
        }
        $exitCode = 1
    }
} finally {
    if ($KeepOpen) {
        Write-Host ""
        Write-Host "Sandbox left running (-KeepOpen). Close its window to discard it."
        Write-Host "What it wrote is in $outDir"
    } else {
        Stop-Sandbox
        # Kept when something failed: the sandbox is gone and this is all that is left
        # of it. Deleted when everything passed, because then it says nothing.
        if ($exitCode -eq 0) {
            Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
        } else {
            Write-Host ""
            Write-Host "What the sandbox wrote is kept in $outDir"
        }
    }
}

exit $exitCode
