#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#ifndef PayloadDir
  #define PayloadDir "build\payload"
#endif
#ifndef ArtifactDir
  #define ArtifactDir "artifacts"
#endif

#define AppName "ParkHaven Studio"
#define AppPublisher "ParkHaven"
#define PluginId "7ff947f5-d80c-4be6-bc9b-88f77bdfe605"

[Setup]
AppId={{CEBCF625-4BE9-45EF-81A5-75AD999EABBD}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\ParkHaven Studio
DisableDirPage=yes
DefaultGroupName=ParkHaven Studio
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#ArtifactDir}
OutputBaseFilename=ParkHaven-Setup-v{#AppVersion}-win-x64
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
SetupLogging=yes
LicenseFile={#PayloadDir}\docs\EULA.txt
UninstallDisplayIcon={app}\ParkHaven.Desktop.exe
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "dutch"; MessagesFile: "compiler:Languages\Dutch.isl"

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "tools\MicrosoftEdgeWebView2RuntimeInstallerX64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{autoprograms}\ParkHaven Studio"; Filename: "{app}\ParkHaven.Desktop.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\ParkHaven Studio"; Filename: "{app}\ParkHaven.Desktop.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Snelkoppeling op het bureaublad maken"; GroupDescription: "Extra snelkoppelingen:"

[Registry]
Root: HKCU; Subkey: "Software\McNeel\Rhinoceros\8.0\Plug-ins\{#PluginId}"; ValueType: string; ValueName: "Name"; ValueData: "ParkHaven"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\McNeel\Rhinoceros\8.0\Plug-ins\{#PluginId}"; ValueType: string; ValueName: "FileName"; ValueData: "{app}\RhinoPlugin\ParkHaven.Rhino.rhp"
Root: HKCU; Subkey: "Software\McNeel\Rhinoceros\8.0\Plug-ins\{#PluginId}"; ValueType: dword; ValueName: "LoadMode"; ValueData: "1"
Root: HKCU; Subkey: "Software\McNeel\Rhinoceros\8.0\Plug-ins\{#PluginId}"; ValueType: dword; ValueName: "IsDotNETPlugIn"; ValueData: "1"
Root: HKCU; Subkey: "Software\McNeel\Rhinoceros\8.0\Plug-ins\{#PluginId}\PlugIn"; ValueType: string; ValueName: "FileName"; ValueData: "{app}\RhinoPlugin\ParkHaven.Rhino.rhp"

[Run]
Filename: "{tmp}\MicrosoftEdgeWebView2RuntimeInstallerX64.exe"; Parameters: "/silent /install"; StatusMsg: "Microsoft WebView2 Runtime controleren..."; Flags: waituntilterminated runhidden
Filename: "{app}\ParkHaven.Desktop.exe"; Description: "ParkHaven Studio starten"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
var
  RhinoPath: String;
begin
  RhinoPath := ExpandConstant('{commonpf64}\Rhino 8\System\Rhino.exe');
  Result := FileExists(RhinoPath);
  if not Result then
    MsgBox('Rhino 8 is niet gevonden. Installeer en activeer Rhino 8 voordat u ParkHaven Studio installeert.', mbError, MB_OK);
end;
