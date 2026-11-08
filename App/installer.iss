; Fontscape — Inno Setup installer script.
; Requires Inno Setup 6 (ISCC.exe). Built via App\build.bat.
; Source exe (dist\Fontscape.exe) is produced by PyInstaller first.

#define MyAppName "Fontscape"
#define MyAppExeName "Fontscape.exe"
#ifndef MyAppVersion
#define MyAppVersion "5.0.2"
#endif
#ifndef MyAppVersionFull
#define MyAppVersionFull "5.0.2.0"
#endif
#define MyAppPublisher "Fontscape"
#define MyAppURL "https://github.com/Carlos0902/FontWizard"

[Setup]
AppId={{8980A84E-5425-40CF-9222-DD3BD3C0F70E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
AppComments=Customize Windows system fonts
DefaultDirName={autopf}\Fontscape
DisableProgramGroupPage=yes
LicenseFile=..\LICENSE
SetupIconFile=src\assets\fontscape.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=dist
OutputBaseFilename=Fontscape Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern dynamic
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.10240
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#MyAppVersionFull}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Setup
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoCopyright=Copyright (c) 2026 {#MyAppPublisher}
VersionInfoOriginalFilename=Fontscape Setup.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\third-party-notices.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent runascurrentuser
