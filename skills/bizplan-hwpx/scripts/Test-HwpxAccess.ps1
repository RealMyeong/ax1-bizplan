param(
    [Parameter(Mandatory=$true)][string]$LiteralPath,
    [Parameter(Mandatory=$true)][string]$ExpectedUserSid
)
$ErrorActionPreference = 'Stop'
# Run in the actual document user's security context, not the sandbox identity.
# No ACL changes, no file contents written, no blanket permission grants.
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
if ($identity.User.Value -ne $ExpectedUserSid) {
    throw 'Wrong security context: test under the intended desktop user, not the agent sandbox account.'
}
$resolved = (Resolve-Path -LiteralPath $LiteralPath).Path
$item = Get-Item -LiteralPath $resolved -Force
if ($item.PSIsContainer -or $item.Extension -ne '.hwpx') { throw 'An existing HWPX file is required.' }
for ($cursor = $item; $null -ne $cursor; $cursor = $cursor.Parent) {
    if ($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse path requires separate review.' }
    if ($cursor -is [IO.FileInfo]) { $cursor = $cursor.Directory; if ($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Reparse directory requires review.' } }
}
$result = [ordered]@{path=$resolved;user_sid=$identity.User.Value;status='unverified';sha256_before=$null;sha256_after=$null;error_code=$null}
try {
    $result.sha256_before = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash
    $stream = [IO.File]::Open($resolved,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::ReadWrite)
    $stream.Dispose()
    $result.sha256_after = (Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash
    if ($result.sha256_before -ne $result.sha256_after) { throw 'File changed during permission check; revalidate document.' }
    $result.status = 'read_write_open_verified'
} catch {
    $exception = $_.Exception
    while ($exception.InnerException) { $exception = $exception.InnerException }
    $code = $exception.HResult -band 0xffff
    $result.error_code = $code
    if ($code -in @(32,33)) { $result.status = 'file_locked' }
    elseif ($code -eq 5) { $result.status = 'access_denied' }
    else { $result.status = 'check_failed' }
    $result | ConvertTo-Json
    exit 2
}
$result | ConvertTo-Json
