$ErrorActionPreference = 'Stop'
$log = Join-Path $PSScriptRoot 'docker-engine-install.log'

function Write-Log([string]$message) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $message"
    Add-Content -Path $log -Value $line -Encoding UTF8
    Write-Host $line
}

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Log 'Requesting UAC elevation...'
    $arguments = @(
        '-NoProfile',
        '-ExecutionPolicy', 'Bypass',
        '-File', ('"{0}"' -f $PSCommandPath)
    )
    try {
        $elevated = Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList $arguments -PassThru
        if ($elevated) {
            Wait-Process -Id $elevated.Id -ErrorAction SilentlyContinue
        }
    } catch {
        Write-Log ("Elevation was cancelled or failed: {0}" -f $_.Exception.Message)
    }
    if (Test-Path $log) {
        Write-Host ''
        Write-Host '--- Install log ---'
        Get-Content -Path $log -Tail 80
    }
    exit 0
}

Write-Log 'Administrator privileges acquired.'

Write-Log 'Stopping the stalled previous installer...'
$stalled = Get-CimInstance Win32_Process | Where-Object {
    $_.CommandLine -like '*install-docker.ps1*' -or $_.Name -eq 'wsl.exe'
}
foreach ($proc in $stalled) {
    try {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction Stop
        Write-Log ("Stopped process {0} ({1})" -f $proc.ProcessId, $proc.Name)
    } catch {
        Write-Log ("Could not stop {0}: {1}" -f $proc.ProcessId, $_.Exception.Message)
    }
}
Start-Sleep -Seconds 2

Write-Log 'Enabling VirtualMachinePlatform...'
$dism = Start-Process -FilePath 'dism.exe' -ArgumentList @(
    '/online', '/enable-feature', '/featurename:VirtualMachinePlatform', '/all', '/norestart'
) -Wait -PassThru -NoNewWindow
Write-Log ("dism exit code: {0} (3010 means reboot required)" -f $dism.ExitCode)

$msi = Join-Path $PSScriptRoot 'downloads\wsl.msi'
if (-not (Test-Path $msi)) {
    throw "WSL installer not found: $msi"
}
$expectedWslHash = 'AE977286974255BD26BF925F00F40F5692C6B2084155CBC0563C09AEA091F211'
$wslHash = (Get-FileHash -Path $msi -Algorithm SHA256).Hash
if ($wslHash -ne $expectedWslHash) {
    throw "WSL installer checksum mismatch. Got $wslHash"
}
Write-Log 'WSL installer checksum verified.'

$msiLog = Join-Path $PSScriptRoot 'wsl-msi-install.log'
Write-Log 'Installing WSL...'
$msiArgs = @('/i', ('"{0}"' -f $msi), '/qn', '/norestart', '/L*v', ('"{0}"' -f $msiLog))
$install = Start-Process -FilePath 'msiexec.exe' -ArgumentList $msiArgs -Wait -PassThru -NoNewWindow
Write-Log ("msiexec exit code: {0}" -f $install.ExitCode)

$wslExe = 'C:\Program Files\WSL\wsl.exe'
if (-not (Test-Path $wslExe)) {
    throw "WSL executable not found after install: $wslExe"
}
Write-Log 'WSL installed.'

$distro = 'DockerAlpine'
$installDir = 'C:\WSL\DockerAlpine'
$rootfs = Join-Path $PSScriptRoot 'downloads\alpine-rootfs.tar.gz'
if (-not (Test-Path $rootfs)) {
    throw "Alpine rootfs not found: $rootfs"
}
$expectedRootfsHash = '6EA461B0225FAAD280B7E13DF878B30FDD6D969DDE25EF05F85A1BCEC9033348'
$rootfsHash = (Get-FileHash -Path $rootfs -Algorithm SHA256).Hash
if ($rootfsHash -ne $expectedRootfsHash) {
    throw "Alpine rootfs checksum mismatch. Got $rootfsHash"
}
Write-Log 'Alpine rootfs checksum verified.'

$existingNames = & $wslExe --list --quiet 2>$null
$names = @($existingNames | ForEach-Object { ($_ -replace "`0", '').Trim() } | Where-Object { $_ })
if ($names -contains $distro) {
    Write-Log ("Distro {0} already exists; skipping import." -f $distro)
} else {
    New-Item -ItemType Directory -Path $installDir -Force | Out-Null
    Write-Log ("Importing Alpine into {0}..." -f $installDir)
    $importArgs = @('--import', $distro, $installDir, ('"{0}"' -f $rootfs), '--version', '2')
    $import = Start-Process -FilePath $wslExe -ArgumentList $importArgs -Wait -PassThru -NoNewWindow
    Write-Log ("wsl --import exit code: {0}" -f $import.ExitCode)
    if ($import.ExitCode -ne 0) {
        throw 'WSL import failed. A reboot may be required before continuing.'
    }
}
& $wslExe --set-default $distro | Out-Null

$setup = @'
#!/bin/sh
set -e
cat > /etc/apk/repositories <<'EOF'
https://mirrors.aliyun.com/alpine/v3.21/main
https://mirrors.aliyun.com/alpine/v3.21/community
EOF
apk update
apk add --no-cache ca-certificates curl docker docker-cli-compose docker-cli-buildx
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{
  "registry-mirrors": ["https://docker.m.daocloud.io"],
  "userland-proxy-path": "/usr/bin/docker-proxy",
  "log-driver": "json-file",
  "log-opts": {"max-size": "10m", "max-file": "3"}
}
EOF
cat > /usr/local/bin/start-docker.sh <<'EOF'
#!/bin/sh
if ! pidof dockerd >/dev/null 2>&1; then
  setsid /usr/bin/dockerd </dev/null >/var/log/dockerd.log 2>&1 &
fi
EOF
chmod +x /usr/local/bin/start-docker.sh
cat > /etc/wsl.conf <<'EOF'
[user]
default = root
EOF
/usr/local/bin/start-docker.sh
sleep 8
docker version
docker compose version
'@

$setupPath = Join-Path $env:TEMP 'alpine-docker-setup.sh'
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($setupPath, ($setup -replace "`r`n", "`n"), $utf8NoBom)

$drive = $setupPath.Substring(0, 1).ToLower()
$rest = $setupPath.Substring(2).Replace('\', '/')
$wslSetupPath = "/mnt/$drive$rest"

Write-Log 'Configuring Alpine and installing Docker Engine...'
$setupArgs = @('-d', $distro, '-u', 'root', '--', 'sh', $wslSetupPath)
$setupRun = Start-Process -FilePath $wslExe -ArgumentList $setupArgs -Wait -PassThru -NoNewWindow
Write-Log ("Alpine setup exit code: {0}" -f $setupRun.ExitCode)

$version = & $wslExe -d $distro -u root -- docker version 2>&1 | Out-String
Write-Log ('docker version output: ' + $version.Trim())

$compose = & $wslExe -d $distro -u root -- docker compose version 2>&1 | Out-String
Write-Log ('docker compose output: ' + $compose.Trim())

$info = & $wslExe -d $distro -u root -- docker info 2>&1 | Out-String
$infoTail = ($info -split "`r?`n" | Select-Object -Last 12) -join ' | '
Write-Log ('docker info tail: ' + $infoTail)

if ($setupRun.ExitCode -ne 0) {
    $daemonLog = & $wslExe -d $distro -u root -- tail -n 60 /var/log/dockerd.log 2>&1 | Out-String
    Write-Log ('dockerd log: ' + $daemonLog.Trim())
}

$readyFile = Join-Path $PSScriptRoot 'docker-engine-ready.txt'
if ($setupRun.ExitCode -eq 0) {
    Set-Content -Path $readyFile -Value 'ready' -Encoding UTF8
    Write-Log 'Docker Engine installation completed.'
} else {
    Set-Content -Path $readyFile -Value ('failed:' + $setupRun.ExitCode) -Encoding UTF8
    Write-Log 'Docker Engine installation failed. See the log above.'
}
