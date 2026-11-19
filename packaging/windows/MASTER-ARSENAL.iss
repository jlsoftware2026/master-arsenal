#define AppName "MASTER ARSENAL"
#define AppVersion "0.3.0"
#define AppPublisher "MASTER ARSENAL"
#define AppExeLocal "ma-local.exe"
#define AppExeBinance "ma-binance.exe"

[Setup]
AppId={{7E45CBAA-8F52-4A5B-A6B7-4E3D8C28A9D2}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\MASTER-ARSENAL
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19045
OutputDir=..\..\dist\installer
OutputBaseFilename=MASTER-ARSENAL-Setup-{#AppVersion}-Windows-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\ma-local\{#AppExeLocal}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut to the Local Engine console"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\..\dist\payload\ma-local\*"; DestDir: "{app}\ma-local"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\dist\payload\ma-binance\*"; DestDir: "{app}\ma-binance"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "QUICKSTART.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\dist\payload\runtime-lock.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\dist\payload\release-manifest.json"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\MASTER ARSENAL - Local Engine Console"; Filename: "{cmd}"; Parameters: "/k ""{app}\ma-local\{#AppExeLocal}"" --help"; WorkingDir: "{app}\ma-local"
Name: "{group}\MASTER ARSENAL - Binance Console"; Filename: "{cmd}"; Parameters: "/k ""{app}\ma-binance\{#AppExeBinance}"" --help"; WorkingDir: "{app}\ma-binance"
Name: "{group}\MASTER ARSENAL Quick Start"; Filename: "{app}\QUICKSTART.txt"
Name: "{autodesktop}\MASTER ARSENAL - Local Engine"; Filename: "{cmd}"; Parameters: "/k ""{app}\ma-local\{#AppExeLocal}"" --help"; WorkingDir: "{app}\ma-local"; Tasks: desktopicon
