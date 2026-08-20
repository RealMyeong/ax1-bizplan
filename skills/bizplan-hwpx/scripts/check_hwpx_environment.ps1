[CmdletBinding()]
param(
    [string]$PluginPath,
    [string]$HwpExecutable
)

$ErrorActionPreference = "Stop"

function Resolve-Executable {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [string[]]$Fallbacks = @()
    )

    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    foreach ($candidate in $Fallbacks) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    return $null
}

$userProfile = if ($env:USERPROFILE) {
    $env:USERPROFILE
} else {
    [Environment]::GetFolderPath("UserProfile")
}
$uvPath = Resolve-Executable -Name "uv" -Fallbacks @(
    (Join-Path $userProfile ".local\bin\uv.exe"),
    (Join-Path $userProfile ".cargo\bin\uv.exe")
)
$uvxPath = Resolve-Executable -Name "uvx" -Fallbacks @(
    (Join-Path $userProfile ".local\bin\uvx.exe"),
    (Join-Path $userProfile ".cargo\bin\uvx.exe")
)

$uvVersion = $null
$uvxVersion = $null
if ($uvPath) {
    $uvVersion = (& $uvPath --version 2>$null | Select-Object -First 1)
}
if ($uvxPath) {
    $uvxVersion = (& $uvxPath --version 2>$null | Select-Object -First 1)
}

$pluginCandidates = @()
if ($PluginPath) {
    $pluginCandidates += Get-Item -LiteralPath $PluginPath -ErrorAction SilentlyContinue
} else {
    $pluginCacheRoots = @(
        (Join-Path $userProfile ".codex\plugins\cache\hwpx\hwpx-plugin"),
        (Join-Path $userProfile ".claude\plugins\cache\hwpx\hwpx-plugin")
    )
    foreach ($pluginCacheRoot in $pluginCacheRoots) {
        if (Test-Path -LiteralPath $pluginCacheRoot -PathType Container) {
            $pluginCandidates += Get-ChildItem -LiteralPath $pluginCacheRoot -Directory
        }
    }
}
$pluginRoot = $pluginCandidates |
    Where-Object { $_ -and $_.PSIsContainer } |
    Sort-Object { try { [version]$_.Name } catch { [version]"0.0.0" } } -Descending |
    Select-Object -First 1

$pluginVersion = $null
$pluginHost = $null
$pluginIdentityValid = $false
$manifestPath = $null
$mcpConfigPath = $null
$mcpConfigValid = $false
$pluginValidationError = $null
$corePin = $null
$automationPin = $null
if ($pluginRoot) {
    if ($pluginRoot.FullName -match '[\\/]\.codex[\\/]') {
        $pluginHost = "codex"
    } elseif ($pluginRoot.FullName -match '[\\/]\.claude[\\/]') {
        $pluginHost = "claude"
    } else {
        $pluginHost = "custom"
    }
    $manifestCandidates = @(
        (Join-Path $pluginRoot.FullName ".codex-plugin\plugin.json"),
        (Join-Path $pluginRoot.FullName ".claude-plugin\plugin.json")
    )
    $manifestPath = $manifestCandidates |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
        Select-Object -First 1
    $mcpConfigCandidate = Join-Path $pluginRoot.FullName ".mcp.json"
    if ($manifestPath) {
        try {
            $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
            $pluginVersion = $manifest.version
            $pluginIdentityValid = [bool]($manifest.name -eq "hwpx-plugin" -and $pluginVersion)
        } catch {
            $pluginValidationError = "manifest_parse_failed: $($_.Exception.Message)"
        }
    }
    if (Test-Path -LiteralPath $mcpConfigCandidate -PathType Leaf) {
        $mcpConfigPath = (Resolve-Path -LiteralPath $mcpConfigCandidate).Path
        try {
            $mcpConfig = Get-Content -LiteralPath $mcpConfigPath -Raw | ConvertFrom-Json
            $mcpServer = $mcpConfig.mcpServers.hwpx
            $mcpArgs = @($mcpServer.args)
            $corePin = $mcpArgs | Where-Object { $_ -match '^python-hwpx\[preview\]==' } | Select-Object -First 1
            $automationPin = $mcpArgs | Where-Object { $_ -match '^python-hwpx-automation\[mcp,oracle\]==' } | Select-Object -First 1
            $mcpConfigValid = [bool]($mcpServer -and $mcpServer.command -and $mcpArgs.Count -gt 0 -and $corePin -and $automationPin)
        } catch {
            $pluginValidationError = "mcp_config_parse_failed: $($_.Exception.Message)"
        }
    }
    if (-not $pluginIdentityValid -and -not $pluginValidationError) {
        $pluginValidationError = "manifest_missing_or_not_hwpx_plugin"
    } elseif (-not $mcpConfigValid -and -not $pluginValidationError) {
        $pluginValidationError = "mcp_config_missing_or_incomplete"
    }
}

$registryHwpPath = $null
try {
    $hwpxProgId = (Get-ItemProperty -LiteralPath "Registry::HKEY_CLASSES_ROOT\.hwpx" -ErrorAction Stop)."(default)"
    if ($hwpxProgId) {
        $openCommand = (Get-ItemProperty -LiteralPath ("Registry::HKEY_CLASSES_ROOT\{0}\shell\open\command" -f $hwpxProgId) -ErrorAction Stop)."(default)"
        if ($openCommand -match '^"([^"]+\.exe)"') {
            $registryHwpPath = $Matches[1]
        } elseif ($openCommand -match '^([^ ]+\.exe)') {
            $registryHwpPath = $Matches[1]
        }
    }
} catch {
    $registryHwpPath = $null
}

$hancomCandidates = @(
    $HwpExecutable,
    $registryHwpPath,
    "C:\Program Files (x86)\Hnc\Office 2024\HOffice130\Bin\Hwp.exe",
    "C:\Program Files\Hnc\Office 2024\HOffice130\Bin\Hwp.exe",
    "C:\Program Files (x86)\Hancom\Office\Hwp.exe",
    "C:\Program Files\Hancom\Office\Hwp.exe"
)
$hwpPath = $hancomCandidates |
    Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
    Select-Object -First 1
$hwpVersion = $null
if ($hwpPath) {
    $hwpVersion = (Get-Item -LiteralPath $hwpPath).VersionInfo.FileVersion
}

$queueVariables = @(
    "HWPX_RENDER_QUEUE_URL",
    "HWPX_RENDER_QUEUE_SECRET",
    "HWPX_RENDER_CA_FILE",
    "HWPX_RENDER_CLIENT_CERT_FILE",
    "HWPX_RENDER_CLIENT_KEY_FILE"
)
$missingQueueVariables = @($queueVariables | Where-Object {
    -not [Environment]::GetEnvironmentVariable($_)
})

$readyForMcpStartup = [bool]($uvxPath -and $pluginIdentityValid -and $mcpConfigValid)
$readyForManualHancomReview = [bool]$hwpPath

$result = [ordered]@{
    schemaVersion = "ax1.hwpx-environment.v1"
    checkedAt = (Get-Date).ToString("o")
    uv = [ordered]@{
        path = $uvPath
        version = $uvVersion
        uvxPath = $uvxPath
        uvxVersion = $uvxVersion
    }
    plugin = [ordered]@{
        installed = [bool]($pluginIdentityValid -and $mcpConfigValid)
        directoryFound = [bool]$pluginRoot
        host = $pluginHost
        root = if ($pluginRoot) { $pluginRoot.FullName } else { $null }
        manifest = $manifestPath
        identityValid = $pluginIdentityValid
        version = $pluginVersion
        mcpConfig = $mcpConfigPath
        mcpConfigValid = $mcpConfigValid
        corePin = $corePin
        automationPin = $automationPin
        validationError = $pluginValidationError
    }
    hancomViewer = [ordered]@{
        installed = [bool]$hwpPath
        path = $hwpPath
        fileVersion = $hwpVersion
        manualFullPageReviewRequired = $true
    }
    automatedRealHancom = [ordered]@{
        configured = ($missingQueueVariables.Count -eq 0)
        missingEnvironmentVariables = $missingQueueVariables
    }
    readiness = [ordered]@{
        mcpStartup = $readyForMcpStartup
        manualHancomReview = $readyForManualHancomReview
        mcpHealthStillRequired = $true
        applicationRestartRequiredAfterInstall = $true
    }
}

$result | ConvertTo-Json -Depth 6
