[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Root
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$resolvedRoot = [System.IO.Path]::GetFullPath($Root)
if (-not [System.IO.Directory]::Exists($resolvedRoot)) {
    throw "Project root does not exist or is not a directory: $resolvedRoot"
}

$normalizedRoot = $resolvedRoot.TrimEnd([char[]]@(92, 47))
$driveRoot = [System.IO.Path]::GetPathRoot($resolvedRoot).TrimEnd([char[]]@(92, 47))
$userProfileRoot = [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile).TrimEnd([char[]]@(92, 47))
$skillInstallRoot = [System.IO.Path]::Combine($userProfileRoot, ".codex", "skills").TrimEnd([char[]]@(92, 47))

if ($normalizedRoot -ieq $driveRoot) {
    throw "Refusing to scaffold a drive root: $resolvedRoot"
}
if ($normalizedRoot -ieq $userProfileRoot) {
    throw "Refusing to scaffold the user profile root: $resolvedRoot"
}
if ($normalizedRoot -ieq $skillInstallRoot -or $normalizedRoot.StartsWith($skillInstallRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to scaffold inside the Codex skill installation directory: $resolvedRoot"
}

$relativeDirectories = @(
    "00_공고_RFP",
    "01_양식_작성지침",
    "02_사업기획_구현구상",
    "03_기관_인력_역할",
    "04_기술_선행성과",
    "05_시장_정책_사업화",
    "06_데이터_실증_KPI",
    "07_예산_일정",
    "08_작성중",
    "08_작성중\01_본문",
    "08_작성중\02_표_그림",
    "08_작성중\03_근거_수치원장",
    "09_검토_수정",
    "09_검토_수정\01_검토의견",
    "09_검토_수정\02_수정본",
    "09_검토_수정\03_반영대장",
    "10_제출본",
    "10_제출본\01_최종문서",
    "10_제출본\02_발표자료",
    "10_제출본\03_제출증빙",
    "90_참고자료",
    "99_임시작업"
)

$checklistPath = Join-Path -Path $resolvedRoot -ChildPath "사업계획서_준비현황.md"
$conflicts = [System.Collections.Generic.List[string]]::new()

foreach ($relativePath in $relativeDirectories) {
    $targetPath = Join-Path -Path $resolvedRoot -ChildPath $relativePath
    if ([System.IO.File]::Exists($targetPath)) {
        $conflicts.Add($targetPath)
    }
}
if ([System.IO.Directory]::Exists($checklistPath)) {
    $conflicts.Add($checklistPath)
}

if ($conflicts.Count -gt 0) {
    $conflictList = $conflicts -join [Environment]::NewLine
    throw "A file/directory type conflict prevents safe setup. No changes were made:`n$conflictList"
}

$createdDirectories = [System.Collections.Generic.List[string]]::new()
$existingDirectories = [System.Collections.Generic.List[string]]::new()

foreach ($relativePath in $relativeDirectories) {
    $targetPath = Join-Path -Path $resolvedRoot -ChildPath $relativePath
    if ([System.IO.Directory]::Exists($targetPath)) {
        $existingDirectories.Add($targetPath)
    }
    else {
        [System.IO.Directory]::CreateDirectory($targetPath) | Out-Null
        $createdDirectories.Add($targetPath)
    }
}

$checklistStatus = "existing"
if (-not [System.IO.File]::Exists($checklistPath)) {
    $assetPath = [System.IO.Path]::GetFullPath((Join-Path -Path $PSScriptRoot -ChildPath "..\assets\preparation-status-template.md"))
    if (-not [System.IO.File]::Exists($assetPath)) {
        throw "Preparation checklist template is missing: $assetPath"
    }

    $projectName = [System.IO.Path]::GetFileName($normalizedRoot)
    $templateContent = [System.IO.File]::ReadAllText($assetPath, [System.Text.Encoding]::UTF8)
    $preparedContent = $templateContent.Replace("{{PROJECT_NAME}}", $projectName).Replace("{{CREATED_DATE}}", (Get-Date -Format "yyyy-MM-dd"))
    $utf8WithoutBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($checklistPath, $preparedContent, $utf8WithoutBom)
    $checklistStatus = "created"
}

$result = [ordered]@{
    root = $resolvedRoot
    created_directories = @($createdDirectories)
    existing_directories = @($existingDirectories)
    checklist_path = $checklistPath
    checklist_status = $checklistStatus
}

$result | ConvertTo-Json -Depth 4
