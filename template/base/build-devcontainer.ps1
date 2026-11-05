#Requires -Version 7.0
<#
.SYNOPSIS
Prepare and recreate this project's DevContainer from Windows PowerShell.
#>
[CmdletBinding()]
param(
    [string]$WslPath,
    [switch]$NoCache,
    [switch]$Help
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

trap {
    Write-Host ""
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    Pause
    exit 1
}

function Get-WslCheckout {
    param([string]$Path)
    $resolved = (Resolve-Path -LiteralPath $Path).ProviderPath
    if ($resolved -match '^[A-Za-z]:\\') {
        $drive = Get-PSDrive -Name $resolved.Substring(0, 1) -PSProvider FileSystem
        if ($drive.DisplayRoot) {
            $resolved = $drive.DisplayRoot.TrimEnd('\') + '\' + $resolved.Substring($drive.Root.Length)
        }
    }
    if ($resolved -notmatch '(?i)^\\\\wsl(?:\.localhost|\$)\\(?<Distribution>[^\\]+)(?<Checkout>\\.*)?$') {
        throw 'Use a WSL UNC checkout, such as \\wsl.localhost\Debian\work\project1.'
    }
    $distribution = $Matches.Distribution
    $linuxPath = if ($Matches['Checkout']) { $Matches['Checkout'].Replace('\', '/') } else { '/' }
    if ($linuxPath -match '^/mnt/[a-z](?:/|$)') { throw 'Use a checkout on the WSL Linux filesystem.' }
    # Compose escapes the dollar in \\wsl$; use the equivalent dollar-free share.
    $rootDir = "\\wsl.localhost\$distribution$($linuxPath.Replace('/', '\'))"
    [PSCustomObject]@{ RootDir = $rootDir; Distribution = $distribution; LinuxPath = $linuxPath }
}

function Invoke-WslCommand {
    param($Checkout, [string[]]$Command)
    # Fixed shell code and separate arguments preserve quotes/spaces with older
    # PowerShell versions. LF terminates the code before the pipeline's CRLF.
    ('exec "$@"' + "`n") | & wsl.exe --distribution $Checkout.Distribution --cd $Checkout.LinuxPath --exec bash -ls -- @Command
    if ($LASTEXITCODE -ne 0) { throw "WSL $($Command[0]) failed with exit code $LASTEXITCODE." }
}

function ConvertTo-CmdQuotedArgument {
    param([string]$Argument)
    return '"' + $Argument.Replace('"', '\"') + '"'
}

function Invoke-DevContainerRunner {
    param([string]$Runner, [string[]]$Arguments, [string]$WorkspaceFolder)
    # Match the reference bootstrap's UNC-safe invocation for Windows .cmd launchers.
    $quotedRunner = ConvertTo-CmdQuotedArgument $Runner
    $quotedWorkspace = ConvertTo-CmdQuotedArgument $WorkspaceFolder
    $quotedArguments = ($Arguments | ForEach-Object { ConvertTo-CmdQuotedArgument $_ }) -join ' '
    $command = "pushd $quotedWorkspace && call $quotedRunner $quotedArguments"
    $process = Start-Process -FilePath 'cmd.exe' -ArgumentList @('/d', '/s', '/c', $command) -NoNewWindow -Wait -PassThru
    if ($process.ExitCode -ne 0) { throw "$Runner failed with exit code $($process.ExitCode)." }
}

function Invoke-DevContainerBootstrap {
    param($Checkout, [switch]$NoCache)

    <#
    Context7 is off by default; pass only its enabled state to the state helper.
    #>
    $context7Enabled = -not [string]::IsNullOrEmpty($env:CONTEXT7_API_KEY)
    if (-not $context7Enabled) {
        Write-Host 'Context7 disabled: CONTEXT7_API_KEY not set'
    }

    <#
    Read public project configuration and check required names and versions.
    #>
    $project = Get-Content -LiteralPath (Join-Path $Checkout.RootDir 'project.json') -Raw | ConvertFrom-Json -AsHashtable
    $name = $project['projectName']
    if ($name -isnot [string] -or [string]::IsNullOrWhiteSpace($name)) {
        throw 'projectName must be a non-empty string.'
    }
    $tools = $project['toolchains']
    foreach ($tool in @('python', 'node', 'npm')) {
        if ($tool -eq 'npm' -and $tools -and -not $tools.Contains('npm')) { continue }
        if (-not $tools -or $tools[$tool] -isnot [string] -or [string]::IsNullOrWhiteSpace($tools[$tool])) {
            throw "toolchains.$tool must be a non-empty version string."
        }
    }

    <#
    Derive workspace/state paths and load the existing editor configuration.
    #>
    $workspace = "/workspaces/$name"
    $personalDirectory = "$($Checkout.LinuxPath.TrimEnd('/'))/.local/devcontainer"
    $configFile = Join-Path $Checkout.RootDir '.devcontainer/devcontainer.json'
    $devcontainer = Get-Content -LiteralPath $configFile -Raw | ConvertFrom-Json -AsHashtable

    <#
    Select the Windows CLI runner and check Docker access in WSL.
    #>
    $runner = Get-Command devcontainer.cmd, devcontainer.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    $runnerArguments = @()
    if ($runner) {
        $runnerDescription = "devcontainer ($($runner.Source))"
    } else {
        $runner = Get-Command npx.cmd, npx.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $runner) { throw 'Required command not found on Windows PATH: devcontainer or npx. Install the CLI through VS Code, or install Windows Node/npm for the npx fallback.' }
        $runnerArguments = @('-y', '@devcontainers/cli')
        $runnerDescription = "npx @devcontainers/cli ($($runner.Source))"
    }
    $dockerVersion = (Invoke-WslCommand $Checkout @('docker', 'info', '--format', '{{.ServerVersion}}')) -join ' '

    <#
    Show the resolved settings and wait for confirmation before making changes.
    #>
    Write-Host @"

DevContainer build settings:
  Checkout: $($Checkout.RootDir) ($($Checkout.Distribution): $($Checkout.LinuxPath))
  Workspace: $workspace
  Compose project: ${name}_devc
  Image: ${name}_build_devcontainer:local
  Shared runtime network: ${name}_default
  Personal state: $personalDirectory/{vscode,vscode-insiders,codex}
  Python: $($tools['python']); Node: $($tools['node']); npm: $(if ($tools.Contains('npm')) { $tools['npm'] } else { 'image default' })
  Runner: $runnerDescription
  PowerShell: 7 LTS; Docker engine: $dockerVersion
  NoCache: $($NoCache.IsPresent)

"@
    [void](Read-Host 'Press Enter to start the build, or press Ctrl+C to abort')

    <#
    Prepare persistent personal state without changing existing settings.
    #>
    $stateHelper = "$($Checkout.LinuxPath.TrimEnd('/'))/_tooling/devcontainer/prepare-state.sh"
    Invoke-WslCommand $Checkout @('bash', $stateHelper, $personalDirectory, $context7Enabled.ToString().ToLowerInvariant())

    <#
    Create or reuse the external network shared with runtime containers.
    #>
    Invoke-WslCommand $Checkout @('bash', '-c', 'docker network inspect "$1" >/dev/null 2>&1 || docker network create "$1" >/dev/null', '--', "${name}_default")

    <#
    Render the complete Compose configuration from the embedded template.
    JSON strings provide quoted YAML scalars; escape dollars for literal Compose values.
    #>
    $pythonVersion = ConvertTo-Json -InputObject $tools['python'].Replace('$', '$$') -Compress
    $nodeVersion = ConvertTo-Json -InputObject $tools['node'].Replace('$', '$$') -Compress
    $npmArgument = if ($tools.Contains('npm')) {
        "`n        NPM_VERSION: $(ConvertTo-Json -InputObject $tools['npm'].Replace('$', '$$') -Compress)"
    } else { '' }
    $context7Environment = if ($context7Enabled) { "`n      CONTEXT7_API_KEY: " } else { '' }
    $compose = @"
# -----
# Created by build-devcontainer.ps1 - do not modify manually!!!!
# Edit project.json or the script's template.
# -----
name: ${name}_devc
services:
  workspace:
    image: ${name}_build_devcontainer:local
    build:
      context: ..
      dockerfile: .devcontainer/Dockerfile
      args:
        PYTHON_VERSION: $pythonVersion
        NODE_VERSION: $nodeVersion$npmArgument
    command: sleep infinity
    init: true
    working_dir: $workspace
    environment:$context7Environment
      TZ: Europe/Vienna
      CODEX_HOME: /home/vscode/.codex
    extra_hosts:
      - host.docker.internal:host-gateway
    networks:
      - default
      - project_default
    volumes:
      - type: bind
        source: ..
        target: $workspace
        bind: { create_host_path: false }
      - type: bind
        source: ../.local/devcontainer/vscode
        target: /home/vscode/.vscode-server
        bind: { create_host_path: false }
      - type: bind
        source: ../.local/devcontainer/vscode-insiders
        target: /home/vscode/.vscode-server-insiders
        bind: { create_host_path: false }
      - type: bind
        source: ../.local/devcontainer/codex
        target: /home/vscode/.codex
        bind: { create_host_path: false }
networks:
  project_default:
    external: true
    name: ${name}_default
"@

    <#
    Write Compose and update editor/workspace identity, preserving other settings.
    #>
    $devcontainer['name'] = $name
    $devcontainer['workspaceFolder'] = $workspace
    $encoding = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText((Join-Path $Checkout.RootDir '.devcontainer/devcontainer-compose.yaml'), $compose.Replace("`r`n", "`n") + "`n", $encoding)
    [System.IO.File]::WriteAllText($configFile, ($devcontainer | ConvertTo-Json -Depth 100).Replace("`r`n", "`n") + "`n", $encoding)

    <#
    Run the Windows CLI after confirmation, downloading through npx only if needed.
    #>
    $arguments = $runnerArguments + @('up', '--workspace-folder', $Checkout.RootDir)
    # Standalone CLI 0.90 misresolves its automatic lockfile path on Windows UNC shares.
    if ($runnerArguments.Count) { $arguments += '--no-lockfile' }
    $arguments += '--remove-existing-container'
    if ($NoCache) { $arguments += '--build-no-cache' }
    Invoke-DevContainerRunner -Runner $runner.Source -Arguments $arguments -WorkspaceFolder $Checkout.RootDir
}

if ($Help) {
    Write-Output @'
Usage: .\build-devcontainer.ps1 [-WslPath <WSL UNC checkout>] [-NoCache] [-Help]
Run in Windows PowerShell 7 after editing project.json.
Context7 is optional: set CONTEXT7_API_KEY in the environment to enable it.
The script prepares the normal DevContainer files for later VS Code rebuilds.
Uses devcontainer command on Windows PATH, otherwise npx -y @devcontainers/cli.
Windows Node/npm is required only for the npx fallback.
'@
    return
}
if (-not $IsWindows) { throw 'Run build-devcontainer.ps1 in Windows PowerShell 7 at the WSL UNC checkout.' }
if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { throw 'wsl.exe is required.' }
$checkout = Get-WslCheckout $(if ($WslPath) { $WslPath } else { $PSScriptRoot })
Invoke-DevContainerBootstrap $checkout -NoCache:$NoCache

Pause
