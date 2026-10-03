; Instalador de Windows (Inno Setup 6). Compilar con:
;   iscc /DVersion=1.1.0 packaging\instalador.iss
; Requiere haber generado antes dist\Posteos con PyInstaller.

#ifndef Version
  #define Version "1.1.0"
#endif

[Setup]
AppId={{6F0E7B1C-3D4A-4E59-9B7A-5C1D2E3F4A5B}
AppName=Posteos
AppVersion={#Version}
AppVerName=Posteos {#Version}
AppPublisher=Posteos
DefaultDirName={autopf}\Posteos
DefaultGroupName=Posteos
DisableProgramGroupPage=yes
OutputDir=..\dist\instalador
OutputBaseFilename=Posteos-Instalador-{#Version}
SetupIconFile=posteos.ico
UninstallDisplayIcon={app}\Posteos.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "..\dist\Posteos\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Posteos"; Filename: "{app}\Posteos.exe"
Name: "{group}\Desinstalar Posteos"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Posteos"; Filename: "{app}\Posteos.exe"; Tasks: escritorio

[Run]
Filename: "{app}\Posteos.exe"; Description: "Abrir Posteos"; Flags: nowait postinstall skipifsilent
