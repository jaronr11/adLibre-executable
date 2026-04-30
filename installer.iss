[Setup]
AppName=adLibre
AppVersion=1.0.0
AppPublisher=adLibre
AppPublisherURL=https://adlibre.io
DefaultDirName={autopf}\adLibre
DefaultGroupName=adLibre
OutputDir=dist
OutputBaseFilename=adLibre-Setup
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\adLibre.exe
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
WizardStyle=modern

[Files]
Source: "dist\adLibre.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\adLibre"; Filename: "{app}\adLibre.exe"
Name: "{group}\Uninstall adLibre"; Filename: "{uninstallexe}"
Name: "{autodesktop}\adLibre"; Filename: "{app}\adLibre.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "startup"; Description: "Run adLibre on Windows startup"; GroupDescription: "Startup:"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "adLibre"; ValueData: """{app}\adLibre.exe"""; Flags: uninsdeletevalue; Tasks: startup
