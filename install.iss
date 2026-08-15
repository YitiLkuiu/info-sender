[Setup]
AppId={{B6E2F3A8-4C1D-4E5F-9A2B-3C4D5E6F7A8B}
AppName=群发助手
AppVersion=1.0
AppPublisher=Eton Leeo
DefaultDirName={localappdata}\Programs\群发助手
DefaultGroupName=群发助手
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=群发助手安装程序
SetupIconFile=app_icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Files]
Source: "dist\MassSender.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\群发助手"; Filename: "{app}\MassSender.exe"; IconFilename: "{app}\app_icon.ico"
Name: "{autodesktop}\群发助手"; Filename: "{app}\MassSender.exe"; IconFilename: "{app}\app_icon.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标:"; Flags: checkedonce

[Run]
Filename: "{app}\MassSender.exe"; Description: "立即运行群发助手"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
