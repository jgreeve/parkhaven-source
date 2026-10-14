[CmdletBinding()]
param(
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version = '0.1.0',
    [string]$AnalyzerRoot = '',
    [switch]$SkipInstaller
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Build = Join-Path $PSScriptRoot 'build'
$Payload = Join-Path $Build 'payload'
$Artifacts = Join-Path $Root 'artifacts'
$Tools = Join-Path $PSScriptRoot 'tools'
if (-not $AnalyzerRoot) {
    $AnalyzerRoot = Join-Path (Split-Path -Parent $Root) 'ParkHaven_Analyzer_App_v0.2'
}

function Require-File([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Vereist bestand ontbreekt: $Path" }
}

function Get-DotNet {
    $local = Join-Path $Tools 'dotnet\dotnet.exe'
    if (-not (Test-Path -LiteralPath $local)) {
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $local) | Out-Null
        $archive = Join-Path $Build 'dotnet-sdk-8.0.425-win-x64.zip'
        Invoke-WebRequest 'https://builds.dotnet.microsoft.com/dotnet/Sdk/8.0.425/dotnet-sdk-8.0.425-win-x64.zip' -OutFile $archive
        $expected = 'f0b6f15bf6f1a0507205c0cb102ab99e1dee875c4682c8ed94665be1d580186a06b21455e83b3a01a0ff7f4cd887b67420f2e2fe09ed985534a4cea488ae1af9'
        if ((Get-FileHash -LiteralPath $archive -Algorithm SHA512).Hash.ToLowerInvariant() -ne $expected) {
            throw '.NET 8 SDK-download heeft een ongeldige SHA-512-hash.'
        }
        Expand-Archive -LiteralPath $archive -DestinationPath (Split-Path -Parent $local)
    }
    if ((& $local --version) -ne '8.0.425') { throw 'De lokale .NET SDK is niet versie 8.0.425.' }
    return $local
}

function Require-SignedPublisher([string]$Path, [string]$PublisherPattern) {
    $signature = Get-AuthenticodeSignature -LiteralPath $Path
    if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch $PublisherPattern) {
        throw "Ongeldige uitgevershandtekening voor $Path"
    }
}

function Get-InnoCompiler {
    $candidate = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($candidate) { return $candidate.Source }
    $local = Join-Path $Tools 'Inno Setup 6\ISCC.exe'
    if (-not (Test-Path -LiteralPath $local)) {
        New-Item -ItemType Directory -Force -Path $Tools | Out-Null
        $installer = Join-Path $Build 'innosetup-6.7.3.exe'
        Invoke-WebRequest 'https://github.com/jrsoftware/issrc/releases/download/is-6_7_3/innosetup-6.7.3.exe' -OutFile $installer
        if ((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash.ToLowerInvariant() -ne '9c73c3bae7ed48d44112a0f48e66742c00090bdb5bef71d9d3c056c66e97b732') {
            throw 'Inno Setup-download heeft een ongeldige SHA-256-hash.'
        }
        Require-SignedPublisher $installer 'Pyrsys B\.V\.'
        & $installer /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CURRENTUSER /DIR="$(Join-Path $Tools 'Inno Setup 6')" | Out-Host
        if ($LASTEXITCODE -ne 0) { throw 'Inno Setup-installatie is mislukt.' }
    }
    Require-File $local
    Require-SignedPublisher $local 'Pyrsys B\.V\.'
    return $local
}

$Required = @(
    (Join-Path $AnalyzerRoot 'ParkHaven_MVP.3dm'),
    (Join-Path $AnalyzerRoot 'ParkHaven_MVP.ghx'),
    (Join-Path $AnalyzerRoot 'weather\NLD_ZH_Rotterdam.Geulhaven.AWS.063430_TMYx.epw'),
    (Join-Path $AnalyzerRoot 'app\static\vendor\three\three.module.min.js'),
    (Join-Path $AnalyzerRoot 'app\static\vendor\three\three.core.min.js'),
    (Join-Path $AnalyzerRoot 'app\static\vendor\three\OrbitControls.js'),
    (Join-Path $AnalyzerRoot 'app\static\vendor\three\LICENSE'),
    (Join-Path $Root 'site-context\manifest.json'),
    (Join-Path $Root 'site-context\parkhaven-aerial-2025.jpg')
)
$Required | ForEach-Object { Require-File $_ }

$ConfigRoot = Join-Path $Root 'config'
$LocalTrustConfig = Join-Path $ConfigRoot 'ai-trust.local.json'
$TrustConfig = if (Test-Path -LiteralPath $LocalTrustConfig -PathType Leaf) {
    $LocalTrustConfig
} else {
    Join-Path $ConfigRoot 'ai-trust.json'
}
Require-File $TrustConfig
try {
    $TrustProfiles = @((Get-Content -LiteralPath $TrustConfig -Raw | ConvertFrom-Json).endpoints)
} catch {
    throw "AI-certificaatconfiguratie is geen geldige JSON: $TrustConfig"
}
$TrustDataArgs = @('--add-data', "$TrustConfig;config")
$ConfigRootFull = [IO.Path]::GetFullPath($ConfigRoot + [IO.Path]::DirectorySeparatorChar)
foreach ($Profile in $TrustProfiles) {
    if (-not $Profile.ca_file -or [IO.Path]::IsPathRooted($Profile.ca_file)) {
        throw 'Elk AI-trustprofiel moet een relatief ca_file bevatten.'
    }
    $CaFile = [IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $TrustConfig) $Profile.ca_file))
    if (-not $CaFile.StartsWith($ConfigRootFull, [StringComparison]::OrdinalIgnoreCase)) {
        throw "AI-certificaat valt buiten de configmap: $($Profile.ca_file)"
    }
    Require-File $CaFile
    if ((Get-Content -LiteralPath $CaFile -Raw) -match '-----BEGIN [^-]*PRIVATE KEY-----') {
        throw "AI-certificaatbestand bevat privésleutelmateriaal: $CaFile"
    }
    $CaDestination = 'config/' + (Split-Path -Parent $Profile.ca_file).Replace('\', '/')
    $TrustDataArgs += @('--add-data', "$CaFile;$CaDestination")
}

Remove-Item -LiteralPath $Build -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $Artifacts -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Payload, $Artifacts | Out-Null

$DotNet = Get-DotNet
$env:DOTNET_ROOT = Split-Path -Parent $DotNet
& $DotNet publish (Join-Path $Root 'desktop\ParkHaven.Desktop\ParkHaven.Desktop.csproj') -c Release -r win-x64 --self-contained true -p:Version=$Version -o $Payload
if ($LASTEXITCODE -ne 0) { throw 'Desktop-publicatie is mislukt.' }
$PluginBuild = Join-Path $Build 'rhino-plugin'
& $DotNet build (Join-Path $Root 'rhino-plugin\ParkHaven.Rhino.csproj') -c Release -p:Version=$Version -o $PluginBuild
if ($LASTEXITCODE -ne 0) { throw 'Rhino-plug-inbuild is mislukt.' }
New-Item -ItemType Directory -Force -Path (Join-Path $Payload 'RhinoPlugin') | Out-Null
Copy-Item (Join-Path $PluginBuild 'ParkHaven.Rhino.rhp') (Join-Path $Payload 'RhinoPlugin')

$BackendDist = Join-Path $Build 'backend-dist'
$PyInstallerArgs = @(
    'run', '--python', '3.13', '--with-requirements', (Join-Path $PSScriptRoot 'requirements-build.lock.txt'),
    'pyinstaller', '--noconfirm', '--clean', '--onedir',
    '--name', 'ParkHaven.Backend', '--distpath', $BackendDist,
    '--workpath', (Join-Path $Build 'pyinstaller-work'), '--specpath', (Join-Path $Build 'pyinstaller-spec'),
    '--paths', $Root, '--collect-submodules', 'uvicorn',
    '--add-data', "$(Join-Path $Root 'app\static');app/static",
    '--add-data', "$(Join-Path $Root 'app\rhino\run_analysis.py');app/rhino",
    '--add-data', "$(Join-Path $Root 'site-context');site-context",
    '--add-data', "$(Join-Path $AnalyzerRoot 'ParkHaven_MVP.3dm');analyzer",
    '--add-data', "$(Join-Path $AnalyzerRoot 'ParkHaven_MVP.ghx');analyzer",
    '--add-data', "$(Join-Path $AnalyzerRoot 'weather');analyzer/weather",
    '--add-data', "$(Join-Path $AnalyzerRoot 'app\static\vendor\three');analyzer/app/static/vendor/three"
)
$PyInstallerArgs += $TrustDataArgs
$PyInstallerArgs += (Join-Path $PSScriptRoot 'backend_entry.py')
& uv @PyInstallerArgs
if ($LASTEXITCODE -ne 0) { throw 'Backendbundel is mislukt.' }
Copy-Item (Join-Path $BackendDist 'ParkHaven.Backend') (Join-Path $Payload 'backend') -Recurse

New-Item -ItemType Directory -Force -Path (Join-Path $Payload 'docs') | Out-Null
Copy-Item (Join-Path $Root 'LICENSE') (Join-Path $Payload 'docs\EULA.txt')
Copy-Item (Join-Path $Root 'THIRD_PARTY_NOTICES.md') (Join-Path $Payload 'docs')
& uv run --python 3.13 (Join-Path $PSScriptRoot 'verify_bundle.py') $Payload
if ($LASTEXITCODE -ne 0) { throw 'Payload-smoketest is mislukt.' }

$Manifest = Get-ChildItem -LiteralPath $Payload -File -Recurse | Sort-Object FullName | ForEach-Object {
    [ordered]@{
        path = $_.FullName.Substring($Payload.Length + 1).Replace('\', '/')
        size = $_.Length
        sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}
[ordered]@{ version = $Version; platform = 'win-x64'; files = $Manifest } |
    ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $Artifacts 'payload-manifest.json') -Encoding UTF8

if (-not $SkipInstaller) {
    $WebViewInstaller = Join-Path $Tools 'MicrosoftEdgeWebView2RuntimeInstallerX64.exe'
    if (-not (Test-Path -LiteralPath $WebViewInstaller)) {
        New-Item -ItemType Directory -Force -Path $Tools | Out-Null
        Invoke-WebRequest 'https://go.microsoft.com/fwlink/p/?LinkId=2124703' -OutFile $WebViewInstaller
    }
    Require-SignedPublisher $WebViewInstaller 'Microsoft Corporation'
    $Inno = Get-InnoCompiler
    & $Inno "/DAppVersion=$Version" "/DPayloadDir=$Payload" "/DArtifactDir=$Artifacts" (Join-Path $PSScriptRoot 'ParkHaven.iss')
    if ($LASTEXITCODE -ne 0) { throw 'Installerbuild is mislukt.' }
    $Setup = Join-Path $Artifacts "ParkHaven-Setup-v$Version-win-x64.exe"
    Require-File $Setup
    $Hash = (Get-FileHash -LiteralPath $Setup -Algorithm SHA256).Hash.ToLowerInvariant()
    "$Hash  $(Split-Path -Leaf $Setup)" | Set-Content -LiteralPath (Join-Path $Artifacts 'SHA256SUMS.txt') -Encoding ASCII
}

Write-Host "Testerbuild gereed: $Artifacts"
